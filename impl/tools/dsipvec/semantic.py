"""Stages 12–14: version negotiation, schema dispatch, stateless semantic checks.

Spec: §11, §10.3, §10.4, §9.3, §9.4, §13.2, §14.2, §15, §19.4; Presence Profile P§3, P§5; schema README checks 1, 2, 5,
7, 8, 9, 11.
"""
from __future__ import annotations

from typing import Any

from .registry import (resolve_reason, effective_answered_by, effective_progress_status, effective_integrity,
                       SUBSCRIPTION_EVENTS, REASON_BEARING_TYPES, INTEGRITY_MODES, PRESENCE_STATES,
                       PRESENCE_STATE_FALLBACK)
from .schema import schema_errors, dispatch_type
from .verdict import Verdict

INTRODUCTION_MAX_BYTES = 4096  # §19.4
INTRODUCTION_CARD_MAX_BYTES = 16384  # §19.4, profile-card/1.0 (spec-gap 186)
PROFILE_CARD_EXT = "profile-card/1.0"
DIRECTION_ANSWERS = {         # Impl (spec-gap 9): SDP-style offer→answer direction compatibility
    "sendrecv": {"sendrecv", "sendonly", "recvonly", "inactive"},
    "sendonly": {"recvonly", "inactive"},
    "recvonly": {"sendonly", "inactive"},
    "inactive": {"inactive"},
}


def _ver(s: str) -> tuple[int, int] | None:
    try:
        a, b = s.split(".")
        return int(a), int(b)
    except (ValueError, AttributeError):
        return None


def check_version(payload: dict, supported: dict) -> Verdict:
    """§11.2 compatibility rules. Malformed blocks are left to the schema stage."""
    blk = payload.get("dsip")
    if not isinstance(blk, dict):
        return Verdict.accept()
    core, min_core = _ver(blk.get("core")), _ver(blk.get("min_core"))
    mine = _ver(supported.get("core", "1.0"))
    if core is None or min_core is None or mine is None:
        return Verdict.accept()
    # Major versions are incompatible by default; the sender's floor must not exceed ours.
    if core[0] != mine[0] or min_core > mine:
        return Verdict.reject("version-unsupported", "session.unsupported-core-version")
    known = set(supported.get("profiles", [])) | set(supported.get("extensions", []))
    crit = blk.get("critical")
    if isinstance(crit, list):
        for c in crit:
            if c not in known:  # §11.2: unknown critical extensions require rejection
                return Verdict.reject("version-unsupported", "session.unsupported-critical-extension")
    profiles = blk.get("profiles")
    if isinstance(profiles, list) and profiles and not any(p in known for p in profiles):
        return Verdict.reject("version-unsupported", "session.unsupported-profile-version")
    return Verdict.accept()


# §10.4, extension sealed-body/1.0 (spec-gap 97): the fields no routing rule reads, per type
SEALED_BODY_EXT = "sealed-body/1.0"
SEALED_BODY_ALG = "hpke-base-x25519-sha256-aes128gcm"
SEALED_BODY_INFO = b"dsip sealed body v1"
SEALED_BODY_PAD = 256
SEALABLE = {
    "invite": {"identity", "intent", "policy", "media", "transports"},
    "answer": {"answered_by", "media", "policy", "transports"},
    "update": {"answered_by", "media", "policy", "transports"},
    "info": {"about", "data"},
    "reject": {"detail"},
    "cancel": {"detail"},
    "bye": {"detail"},
}


def sealed_body_aad(p: dict) -> bytes:
    """§10.4: type ‖ 0x00 ‖ id ‖ 0x00 ‖ from ‖ 0x00 ‖ to, so a ciphertext cannot move into another message."""
    return b"\0".join(str(p.get(k, "")).encode() for k in ("type", "id", "from", "to"))


def open_sealed_body(payload: dict, sk: bytes) -> tuple[Verdict, dict | None]:
    """Stage 12b (§10.4): open `sealed` and merge it into the clear fields; first failing condition wins.

    A `sealed` that is not `{alg, enc, ct}` strings, or a payload whose `type`/`id`/`from`/`to` (the AAD inputs)
    is not a string, is left for the schema stage to reject.
    """
    from .crypto import b64url_decode
    from .messaging import hpke_open
    from .wire import parse_payload
    sealed = payload["sealed"]
    if not isinstance(sealed, dict) or not all(isinstance(sealed.get(k), str) for k in ("alg", "enc", "ct")) \
            or not all(isinstance(payload.get(k), str) for k in ("type", "id", "from", "to")):
        return Verdict.accept(), payload  # §10.4: not opened; schema validation rejects the shape
    crit = (payload.get("dsip") or {}).get("critical")
    if not isinstance(crit, list) or SEALED_BODY_EXT not in crit:
        return Verdict.reject("sealed-not-critical"), None
    if sealed["alg"] != SEALED_BODY_ALG:
        return Verdict.reject("sealed-alg-unsupported"), None
    try:
        enc, ct = b64url_decode(sealed["enc"]), b64url_decode(sealed["ct"])
    except ValueError:
        return Verdict.reject("body-unseal-failed"), None
    pt = hpke_open(enc, sk, SEALED_BODY_INFO, sealed_body_aad(payload), ct)
    if pt is None:
        return Verdict.reject("body-unseal-failed"), None
    v, body = parse_payload(pt, core_shape=False)
    if not v.ok or not body or len(pt) % SEALED_BODY_PAD:
        return Verdict.reject("sealed-plaintext-invalid"), None
    if set(body) - SEALABLE.get(payload.get("type"), set()):
        return Verdict.reject("sealed-field-not-sealable"), None
    if set(body) & set(payload):
        return Verdict.reject("sealed-field-in-clear"), None
    merged = {k: v for k, v in payload.items() if k != "sealed"}
    merged.update(body)
    return Verdict.accept(sealed=sorted(body)), merged


def check_schema(payload: dict) -> Verdict:
    t = dispatch_type(payload)
    if t is None:
        return Verdict.reject("unknown-type")
    errs = schema_errors(t, payload)
    if errs:
        return Verdict.reject("schema-invalid", detail=errs[0][:200])
    return Verdict.accept()


def selection_is_subset(selection: dict, offer: dict) -> bool:
    """Check 9 (Impl, spec-gap 9)."""
    offered_media = offer.get("media", []) or []
    for sel in selection.get("media", []) or []:
        match = None
        for off in offered_media:
            if off.get("type") == sel.get("type") and off.get("purpose") == sel.get("purpose"):
                match = off
                break
        if match is None:
            return False
        offered_codecs = {c.get("id") for c in match.get("codecs", [])}
        if any(c.get("id") not in offered_codecs for c in sel.get("codecs", [])):
            return False
        if sel.get("direction") not in DIRECTION_ANSWERS.get(match.get("direction"), set()):
            return False
    offered_transports = {t.get("id") for t in offer.get("transports", []) or []}
    for t in selection.get("transports", []) or []:
        if t.get("id") not in offered_transports:
            return False
    return True


def check_semantic(payload: dict, ctx: dict, encoded_size: int | None = None) -> Verdict:
    """Stage 14. `ctx` is the raw vector context dict."""
    t = payload["type"]
    if t == "hello" and "in_reply_to" in payload and ctx.get("sent_hello_id") is not None:
        if payload["in_reply_to"] != ctx["sent_hello_id"]:  # §13.2 / §20.5 anti-splicing
            return Verdict.reject("hello-in-reply-to-mismatch")
    if t == "answer" and isinstance(ctx.get("offer"), dict):
        if not selection_is_subset(payload, ctx["offer"]):
            return Verdict.reject("selection-not-subset")
    if t == "subscribe":
        for ev in payload.get("events", []):
            cap = SUBSCRIPTION_EVENTS.get(ev)
            if cap is not None and payload["expires_in"] > cap:  # §9.3 hard caps → error policy.subscription-lifetime (v0.7)
                return Verdict.reject("subscription-lifetime-exceeded", "policy.subscription-lifetime")
    if t == "introduction":
        size = encoded_size if encoded_size is not None else ctx.get("encoded_size")
        exts = payload["dsip"].get("extensions", [])
        # §19.4: 16,384 with `sealed` and profile-card/1.0 listed (spec-gap 186), 4,096 otherwise
        cap = INTRODUCTION_CARD_MAX_BYTES if "sealed" in payload and PROFILE_CARD_EXT in exts else INTRODUCTION_MAX_BYTES
        if size is not None and size > cap:
            return Verdict.reject("introduction-too-large")
        if "purpose" in payload and "sealed" in payload:  # §19.4 (v0.8, spec-gap 36): sealed replaces purpose
            return Verdict.reject("introduction-purpose-and-sealed")
    if t == "delegation-revocation":  # §7.4 (v0.8, spec-gap 57): only the identity revokes, with its own key
        if payload["subject"] != payload["from"]:
            return Verdict.reject("revocation-subject-mismatch")
        signer = ctx.get("signer_kid")
        if signer is not None and signer.split("#", 1)[0] != payload["subject"]:
            return Verdict.reject("revocation-signer-not-subject")
    if t == "grant" and isinstance(ctx.get("known_introductions"), list):
        # §19.4: an introduction we sent, or (spec-gap 150) a live grant held from the signer's identity that this one follows
        if payload["session"] not in ctx["known_introductions"] and payload["session"] not in ctx.get("held_grants", []):
            return Verdict.reject("grant-unknown-introduction")
    if t == "presence" and "device" in payload and payload["device"] != payload["from"]:
        # P§3 (v0.17, spec-gap 135): a record describes the device that signs it
        return Verdict.reject("presence-signer-mismatch", "presence.signer-mismatch")
    if t == "presence" and "sealed_state" in payload:
        # P§12.2 (v0.17, spec-gaps 152, 157): a sealed record names presence/0.2, and its kid is for its audience
        profiles = payload["dsip"].get("profiles")
        audience = payload.get("audience")
        if (not isinstance(profiles, list) or "presence/0.2" not in profiles or audience == "main"
                or payload["kid"].rsplit(".", 1)[0] != (audience or "main")):
            return Verdict.reject("presence-sealed-invalid", "presence.sealed-invalid")
    if t == "key-rotation":  # §7.5 (v0.7, spec-gap 22)
        if payload["subject"] != payload["from"]:
            return Verdict.reject("rotation-subject-mismatch")
        if payload["next"] == payload["previous"]:
            return Verdict.reject("rotation-next-same-as-previous")
        signer = ctx.get("signer_kid")
        if signer is not None and not payload.get("recovery", False) and signer != payload["previous"]:
            return Verdict.reject("rotation-signer-not-previous")
    return Verdict.accept(**registry_effects(payload))


def registry_effects(payload: dict) -> dict:
    """Check 5 — membership with fallback. Never rejects."""
    t = payload["type"]
    eff: dict[str, Any] = {}
    warnings: list[str] = []
    if "reason" in payload and (t in REASON_BEARING_TYPES or t == "notify"):
        r = resolve_reason(payload["reason"], t)
        eff["reason"] = r.effective
        eff["fallback"] = r.fallback
        if not r.valid_on_type:
            warnings.append("reason-not-valid-on-type")
    if t in ("answer", "update") and "answered_by" in payload:
        eff["answered_by"] = effective_answered_by(payload["answered_by"])
    if t == "progress":
        eff["status"] = effective_progress_status(payload["status"])
    if t == "presence" and "state" in payload:  # a sealed record's state is not the pipeline's to read (P§12)
        # P§5 (spec-gap 136): an unknown state is accepted and shown as available
        eff["state"] = payload["state"] if payload["state"] in PRESENCE_STATES else PRESENCE_STATE_FALLBACK
        if payload["state"] not in PRESENCE_STATES:
            warnings.append("presence-state-unknown")
    if t == "publish" and "integrity" in payload:
        eff["integrity"] = effective_integrity(payload["integrity"])
        if payload["integrity"] not in INTEGRITY_MODES:
            warnings.append("integrity-mode-unknown")  # §22.2 registry fallback
    out: dict[str, Any] = {}
    if eff:
        out["effective"] = eff
    if warnings:
        out["warnings"] = warnings
    return out


def check_payload(payload: dict, ctx: dict, encoded_size: int | None = None) -> Verdict:
    """Stages 12–14 in order, with 12b (§10.4) opening a sealed body when the context holds the addressee's key.

    With `router: true` the receiver only routes: it never opens a seal, the critical-extension rule does not apply to
    sealed-body/1.0 (§10.4), and the clear part is validated as it stands.
    """
    supported = ctx.get("supported") or {"core": "1.0", "profiles": ["interactive-media/1.0"], "extensions": []}
    if ctx.get("router") and "sealed" in payload:
        # §10.4: a router routes a sealed payload whether or not it implements sealed-body/1.0
        supported = {**supported, "extensions": [*supported.get("extensions", []), SEALED_BODY_EXT]}
    v = check_version(payload, supported)
    if not v.ok:
        return v
    sealed_fields = None
    if "sealed" in payload and ctx.get("unseal_key_hex") and not ctx.get("router"):
        v, opened = open_sealed_body(payload, bytes.fromhex(ctx["unseal_key_hex"]))
        if not v.ok:
            return v
        sealed_fields, payload = v.extra.get("sealed"), opened
    v = check_schema(payload)
    if not v.ok:
        return v
    v = check_semantic(payload, ctx, encoded_size)
    if v.ok and sealed_fields:
        v.extra.setdefault("effective", {})["sealed"] = sealed_fields
    return v
