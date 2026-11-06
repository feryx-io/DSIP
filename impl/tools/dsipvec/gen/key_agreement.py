"""`key-agreement/` vectors — key agreement delegation (core §7.3, 1.x; spec-gap 179). Expectations are written out by
hand: verdicts from the rules, and the keys computed by a path the reference does not use (the derived key from the
Ed25519 seed through SHA-512, not the Montgomery map from the public key)."""
from __future__ import annotations

from .. import fixtures as F
from ..crypto import b58_encode, b64url_decode, b64url_encode, keypair_from_seed_name
from ..messaging import x25519_from_ed25519_seed, x25519_public
from .common import NOW, default_context, signed, vector

ALICE, BOB, APH = F.did("alice"), F.did("bob"), F.did("alice-phone")
CAP = 31_536_000
REFS = ["§7.3"]


def x25519_secret(name: str) -> bytes:
    """An independent X25519 key agreement secret (not derived from any identity key)."""
    return bytes(keypair_from_seed_name(f"key-agreement-{name}").signing_key)


def mb(pub: bytes) -> str:
    return "z" + b58_encode(bytes([0xEC, 0x01]) + pub)


K1 = x25519_public(x25519_secret("one"))
K2 = x25519_public(x25519_secret("two"))
K3 = x25519_public(x25519_secret("three"))


def not_x25519() -> str:
    """A `z6LS…` string of the pattern's length whose bytes are not 0xec 0x01 and 32 bytes (found deterministically)."""
    import hashlib
    i = 0
    while True:
        s = "z" + b58_encode(bytes([0xEC, 0x02]) + hashlib.sha256(f"ka-not-x25519-{i}".encode()).digest())
        if s.startswith("z6LS") and len(s) == 48:
            return s
        i += 1


def ka(subject: str, kpub: bytes, issued_at: int = NOW - 60, life: int = 86_400 * 30, **over) -> dict:
    p = {"type": "KeyAgreementDelegation", "subject": subject, "key": mb(kpub), "issued_at": issued_at,
         "expires_at": issued_at + life}
    p.update(over)
    return p


def cred(payload: dict, signer: str = "alice", kid: str | None = None) -> dict:
    return signed(payload, signer, kid)


def derived(name: str) -> bytes:
    return x25519_public(x25519_from_ed25519_seed(bytes(F.KEYS[name].signing_key)))


def accept_cred(subject: str, key: bytes, expires_at: int) -> dict:
    return {"verdict": "accept", "subject": subject, "key": mb(key), "x25519_pk_hex": key.hex(), "expires_at": expires_at}


def rk(source: str, key: bytes | None = None) -> dict:
    out = {"verdict": "accept", "source": source}
    if key is not None:
        out.update(key=mb(key), x25519_pk_hex=key.hex())
    return out


def vectors() -> list[dict]:
    out = []
    ctx = default_context()

    def dv(vid, desc, c, expect, subject=None, refs=None):
        inp = {"check": "delegation", "delegation": c}
        if subject is not None:
            inp["subject"] = subject
        out.append(vector(f"key-agreement/{vid}", "key-agreement", desc, refs or REFS, ctx, inp, expect))

    good = ka(ALICE, K1)
    dv("valid", "An identity names an independent X25519 key: the credential verifies, its key in hex.",
       cred(good), accept_cred(ALICE, K1, good["expires_at"]))
    dv("valid-for-the-subject-asked", "Asked for its own subject: it verifies.", cred(good),
       accept_cred(ALICE, K1, good["expires_at"]), subject=ALICE)
    dv("subject-mismatch", "Bob's credential, asked for as Alice's.", cred(ka(BOB, K1), "bob"),
       {"verdict": "reject", "code": "subject-mismatch"}, subject=ALICE)
    dv("device-signed", "Signed by alice-phone, a device Alice delegated: a device never signs it (§7.3, as §7.4).",
       cred(good, "alice-phone"), {"verdict": "reject", "code": "not-subject-signed"})
    dv("other-signer", "Mallory signs a credential naming Alice as subject.", cred(good, "mallory"),
       {"verdict": "reject", "code": "not-subject-signed"})
    web = ka(F.BOB_WEB, K2)
    dv("did-web-subject", "A did:web identity signs one with its document's key (it is ignored where the document names "
       "a keyAgreement method; verification is the same).", cred(web, "bob", F.web_kid(F.BOB_WEB)),
       accept_cred(F.BOB_WEB, K2, web["expires_at"]))
    c = cred(good)
    raw = b64url_decode(c["payload"]).decode().replace(mb(K1), mb(K2))
    dv("tampered", "The key changed after signing.", {**c, "payload": b64url_encode(raw.encode())},
       {"verdict": "reject", "code": "credential-invalid"})
    dv("not-an-envelope", "A string, not an envelope object.", "a.b.c", {"verdict": "reject", "code": "credential-invalid"})
    dv("ed25519-key", "`key` is an Ed25519 multibase key (z6Mk…), not an X25519 one.",
       cred(ka(ALICE, K1, key=F.multibase_pub("bob"))), {"verdict": "reject", "code": "schema-invalid"})
    dv("key-not-x25519", "`key` matches the schema's pattern but decodes to another multicodec (0xec 0x02): refused "
       "as schema-invalid, before the signer.", cred(ka(ALICE, K1, key=not_x25519()), "mallory"),
       {"verdict": "reject", "code": "schema-invalid"})
    dv("extra-member", "A member the credential does not have.", cred(ka(ALICE, K1, purpose="all")),
       {"verdict": "reject", "code": "schema-invalid"})
    dv("other-type", "A DeviceDelegation-typed payload is not this credential.",
       cred(ka(ALICE, K1, type="DeviceDelegation")), {"verdict": "reject", "code": "schema-invalid"})
    dv("expires-before-issued", "`expires_at` not after `issued_at`.", cred(ka(ALICE, K1, life=0)),
       {"verdict": "reject", "code": "validity-invalid"})
    at_cap = ka(ALICE, K1, issued_at=NOW - 60, life=CAP)
    dv("lifetime-at-cap", "A lifetime of exactly one year (31,536,000 s) is allowed.", cred(at_cap),
       accept_cred(ALICE, K1, at_cap["expires_at"]))
    dv("lifetime-over-cap", "One second over a year.", cred(ka(ALICE, K1, life=CAP + 1)),
       {"verdict": "reject", "code": "validity-invalid"})
    soon = ka(ALICE, K1, issued_at=NOW + 300)
    dv("issued-at-window-edge", "`issued_at` 300 s ahead is within the replay window.", cred(soon),
       accept_cred(ALICE, K1, soon["expires_at"]))
    dv("not-yet-valid", "`issued_at` 301 s ahead.", cred(ka(ALICE, K1, issued_at=NOW + 301)),
       {"verdict": "reject", "code": "not-yet-valid"})
    dv("expired", "Now is its `expires_at`: expired at that second.", cred(ka(ALICE, K1, issued_at=NOW - 100, life=100)),
       {"verdict": "reject", "code": "expired"})
    dv("validity-before-timing", "A lifetime over the cap is refused as such even when it has expired too.",
       cred(ka(ALICE, K1, issued_at=NOW - CAP - 100, life=CAP + 1)), {"verdict": "reject", "code": "validity-invalid"})

    def rv(vid, desc, did, dels, expect, document=None, refs=None):
        inp = {"check": "recipient-key", "did": did, "delegations": dels}
        if document is not None:
            inp["document_key_agreement"] = document
        out.append(vector(f"key-agreement/{vid}", "key-agreement", desc, refs or ["§7.3", "§10.4", "M§6.9"], ctx, inp,
                          expect))

    rv("recipient-derived", "A did:key identity with no delegation: the key the did:key method derives (M§6.9).",
       ALICE, [], rk("derived", derived("alice")))
    rv("recipient-delegation", "A did:key identity with a verified delegation: its key, not the derived one.",
       ALICE, [cred(good)], rk("delegation", K1))
    newer = ka(ALICE, K2, issued_at=NOW - 30)
    rv("recipient-newest", "Two verified delegations: the greater `issued_at` is current, whatever the order given.",
       ALICE, [cred(newer), cred(good)], rk("delegation", K2))
    lo, hi = sorted([K2, K3], key=mb)
    rv("recipient-tie-smaller-key", "Two with the same `issued_at`: the smaller `key`, compared as strings.",
       ALICE, [cred(ka(ALICE, hi)), cred(ka(ALICE, lo))], rk("delegation", lo))
    rv("recipient-ignores-unverified", "Delegations that do not verify for the DID (expired, another subject's, a "
       "device's) count for nothing: the derived key.", ALICE,
       [cred(ka(ALICE, K1, issued_at=NOW - 100, life=100)), cred(ka(BOB, K2), "bob"), cred(ka(ALICE, K3), "alice-phone")],
       rk("derived", derived("alice")))
    rv("recipient-expired-newer-falls-back", "The newest has expired: the older one still in force is current.",
       ALICE, [cred(ka(ALICE, K2, issued_at=NOW - 50, life=40)), cred(good)], rk("delegation", K1))
    rv("recipient-document-first", "A DID document's keyAgreement method comes first; a delegation is ignored (§8.1).",
       ALICE, [cred(good)], rk("document", K3), document=mb(K3))
    rv("recipient-did-web-delegation", "A did:web identity whose document names no keyAgreement, with a delegation.",
       F.BOB_WEB, [cred(web, "bob", F.web_kid(F.BOB_WEB))], rk("delegation", K2))
    rv("recipient-did-web-none", "A did:web identity with neither: no key to seal to (nothing is derived).",
       F.BOB_WEB, [], rk("none"))
    return out


def hint_vectors(hint, dv, accept) -> list[dict]:
    """`dht/` vectors for a hint carrying `key_agreement` (DHT Hints Profile §2, §4); built with the dht generator's
    helpers so they share its context."""
    out = []
    good = cred(ka(ALICE, K1))
    out.append(dv("key-agreement-carried", "A hint carrying the subject's key agreement delegation (spec-gap 179).",
                  ["§7.3", "§8.3"], signed({**hint("hka", ALICE, ALICE, 1), "key_agreement": good}, "alice"),
                  accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="input", conflict="none")))
    out.append(dv("key-agreement-carried-by-device", "A device's hint carries the identity's delegation, signed by the "
                  "identity: the hint verifies by the device's delegation, the credential by the identity.",
                  ["§7.3", "§8.3"], signed({**hint("hkad", ALICE, ALICE, 1, at=NOW - 60), "key_agreement": good}, "alice-phone"),
                  accept(type="reachability-hint", signer=APH, identity=ALICE, winner="input", conflict="none")))
    for vid, desc, c in [
        ("key-agreement-other-subject", "The member is Bob's delegation: the hint is refused as a whole.", cred(ka(BOB, K1), "bob")),
        ("key-agreement-expired", "The member has expired.", cred(ka(ALICE, K1, issued_at=NOW - 100, life=100))),
        ("key-agreement-device-signed", "The member is signed by a device, not the identity.", cred(ka(ALICE, K1), "alice-phone")),
        ("key-agreement-tampered", "The member's key changed after signing.",
         {**good, "payload": b64url_encode(b64url_decode(good["payload"]).decode().replace(mb(K1), mb(K2)).encode())}),
    ]:
        out.append(dv(vid, desc, ["§7.3", "§8.3"], signed({**hint(vid, ALICE, ALICE, 1), "key_agreement": c}, "alice"),
                      {"verdict": "reject", "code": "key-agreement-invalid"}))
    out.append(dv("key-agreement-not-an-object", "The member is a string: the hint schema refuses it.", ["§8.3"],
                  signed({**hint("hkas", ALICE, ALICE, 1), "key_agreement": "a.b.c"}, "alice"),
                  {"verdict": "reject", "code": "schema-invalid"}))
    return out
