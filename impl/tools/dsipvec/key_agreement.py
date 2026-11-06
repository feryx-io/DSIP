"""Key agreement delegation (core §7.3, 1.x, spec-gap 179) — reference for the `key-agreement/` vectors, and the
check a reachability hint's `key_agreement` member gets (DHT Hints Profile §2, §4).

Spec: §7.3 (the credential, its verification, which is current, the key agreement key of a DID), §10.4 rule 3 and
M§6.9 (the recipient key). Contract: impl/vectors/README.md, kind `key-agreement`.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import envelope as E
from .crypto import b58_decode, b58_encode, public_from_did_key

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = REPO_ROOT / "v1.0" / "dsip-schemas-v1.0" / "dsip-schemas" / "schemas" / "key-agreement-delegation.schema.json"

LIFETIME_CAP_S = 31_536_000   # §7.3: expires_at <= issued_at + one year
FUTURE_S = 300                # §7.3: issued_at at most the replay window ahead (§12.9)
X25519_PUB_MULTICODEC = bytes([0xEC, 0x01])
P = 2**255 - 19


@lru_cache(maxsize=None)
def _validator():
    from .schema import Validator
    return Validator(json.loads(SCHEMA.read_text()))


def multibase_x25519(pub: bytes) -> str:
    return "z" + b58_encode(X25519_PUB_MULTICODEC + pub)


def x25519_from_multibase(mb: str) -> bytes:
    raw = b58_decode(mb[1:])
    if not mb.startswith("z") or not raw.startswith(X25519_PUB_MULTICODEC) or len(raw) != 34:
        raise ValueError("not an x25519-pub multibase key")
    return raw[2:]


def x25519_from_ed25519_public(pub: bytes) -> bytes:
    """The did:key method's X25519 key for an Ed25519 public key: the Montgomery u = (1 + y) / (1 - y) mod p."""
    y = int.from_bytes(pub, "little") & ((1 << 255) - 1)
    u = (1 + y) * pow((1 - y) % P, P - 2, P) % P
    return u.to_bytes(32, "little")


def verify(cred, now: int, subject: str | None = None, ctx: dict | None = None) -> tuple[dict | None, str | None]:
    """§7.3: the delegation's payload, or the code of the first check it fails.

    In order: `credential-invalid` (stages 2–6 of the pipeline, as a delegation is verified: shape, header, kid
    resolution, signature, payload parse; no core-field check, no replay window), `schema-invalid` (the schema, or a
    `key` that is not `0xec 0x01` and 32 bytes),
    `not-subject-signed` (the signing kid's DID is not `subject`: a device's signature does not count),
    `subject-mismatch` (another subject than the one asked for), `validity-invalid` (not issued_at < expires_at <=
    issued_at + cap), `not-yet-valid` (issued_at > now + 300), `expired` (now >= expires_at)."""
    context = E.Context.from_vector({**(ctx or {}), "now": now}) if ctx else E.Context(now=now)
    v, ver = E.verify_raw(cred, context, core_shape=False)
    if not v.ok:
        return None, "credential-invalid"
    p = ver.payload
    if any(True for _ in _validator().iter_errors(p)):
        return None, "schema-invalid"
    try:
        x25519_from_multibase(p["key"])  # the pattern admits strings that are not 0xec 0x01 and 32 bytes
    except ValueError:
        return None, "schema-invalid"
    if ver.signer_did != p["subject"]:
        return None, "not-subject-signed"
    if subject is not None and p["subject"] != subject:
        return None, "subject-mismatch"
    if not (p["issued_at"] < p["expires_at"] <= p["issued_at"] + LIFETIME_CAP_S):
        return None, "validity-invalid"
    if p["issued_at"] > now + FUTURE_S:
        return None, "not-yet-valid"
    if now >= p["expires_at"]:
        return None, "expired"
    return p, None


def current(delegations: list, subject: str, now: int, ctx: dict | None = None) -> dict | None:
    """§7.3: of the delegations that verify for `subject`, the one with the greatest `issued_at`, ties to the smaller
    `key` (compared as strings)."""
    good = [p for p in (verify(d, now, subject, ctx)[0] for d in delegations) if p is not None]
    if not good:
        return None
    return min(good, key=lambda p: (-p["issued_at"], p["key"]))


def recipient_key(did: str, document_key: str | None, delegations: list, now: int, ctx: dict | None = None) -> dict:
    """§7.3, §10.4 rule 3: the key agreement key of `did`: the document's, else the current delegation's, else for
    did:key the derived key; `{source, key?, x25519_pk_hex?}`."""
    if document_key is not None:
        return {"source": "document", "key": document_key, "x25519_pk_hex": x25519_from_multibase(document_key).hex()}
    cur = current(delegations, did, now, ctx)
    if cur is not None:
        return {"source": "delegation", "key": cur["key"], "x25519_pk_hex": x25519_from_multibase(cur["key"]).hex()}
    try:
        pub = x25519_from_ed25519_public(public_from_did_key(did))
    except ValueError:
        return {"source": "none"}
    return {"source": "derived", "key": multibase_x25519(pub), "x25519_pk_hex": pub.hex()}


def run(v: dict) -> dict:
    i, ctx = v["input"], v["context"]
    now = ctx["now"]
    if i["check"] == "delegation":
        p, code = verify(i["delegation"], now, i.get("subject"), ctx)
        if p is None:
            return {"verdict": "reject", "code": code}
        return {"verdict": "accept", "subject": p["subject"], "key": p["key"],
                "x25519_pk_hex": x25519_from_multibase(p["key"]).hex(), "expires_at": p["expires_at"]}
    if i["check"] == "recipient-key":
        return {"verdict": "accept", **recipient_key(i["did"], i.get("document_key_agreement"), i.get("delegations", []), now, ctx)}
    raise ValueError(f"unknown key-agreement check {i['check']}")
