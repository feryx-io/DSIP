"""Wire-format payload rules enforced at parse (spec §10.3): UTF-8, no floats, integer timestamps."""
from __future__ import annotations

import json
import re

from .verdict import Verdict
from .ulid import ULID_RE

DID_RE = re.compile(r"^did:[a-z0-9]+:[A-Za-z0-9.%_:-]+\Z")


class _IntOnly(json.JSONDecoder):
    """Decoder that refuses any non-integer number (§10.3 "avoid floating point")."""

    def __init__(self, *a, **kw):
        kw["parse_float"] = self._reject_float
        super().__init__(*a, **kw)

    @staticmethod
    def _reject_float(s):
        raise FloatFound(s)


class FloatFound(Exception):
    pass


def _no_constant(name):
    raise ValueError(f"{name} is not JSON")


def has_lone_surrogate(v) -> bool:
    """§10.3 (spec-gap 188): whether any string or member name holds an unpaired surrogate (json pairs the paired)."""
    if isinstance(v, str):
        return any(0xD800 <= ord(c) <= 0xDFFF for c in v)
    if isinstance(v, dict):
        return any(has_lone_surrogate(k) or has_lone_surrogate(x) for k, x in v.items())
    if isinstance(v, list):
        return any(has_lone_surrogate(x) for x in v)
    return False


def _has_float(v) -> bool:
    if isinstance(v, float):
        return True
    if isinstance(v, dict):
        return any(_has_float(x) for x in v.values())
    return isinstance(v, list) and any(_has_float(x) for x in v)


def parse_payload(raw: bytes, core_shape: bool = True) -> tuple[Verdict, dict | None]:
    """Stage 6 of the pipeline. Returns (verdict, payload)."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return Verdict.reject("payload-not-utf8"), None
    try:
        payload = json.loads(text, parse_constant=_no_constant)
    except (ValueError, RecursionError):
        return Verdict.reject("payload-not-json"), None
    # §10.3 (spec-gap 188): a lone surrogate, escaped or not, in any string or member name is not a payload
    if not isinstance(payload, dict) or has_lone_surrogate(payload):
        return Verdict.reject("payload-not-json"), None
    if _has_float(payload):
        return Verdict.reject("payload-float"), None
    if core_shape:
        v = check_core_shape(payload)
        if not v.ok:
            return v, None
    return Verdict.accept(), payload


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def check_core_shape(payload: dict) -> Verdict:
    """Fields every payload must carry with the right primitive type, before schema.

    These are the fields the pipeline itself reads (stages 7–12); the schema
    re-validates them, but parse-level typing must never depend on the schema.
    """
    if not isinstance(payload.get("dsip"), dict):
        return Verdict.reject("payload-shape", detail="dsip")
    if not isinstance(payload.get("type"), str):
        return Verdict.reject("payload-shape", detail="type")
    if not isinstance(payload.get("id"), str) or not ULID_RE.match(payload["id"]):
        return Verdict.reject("payload-shape", detail="id")
    if not isinstance(payload.get("from"), str) or not DID_RE.match(payload["from"]):
        return Verdict.reject("payload-shape", detail="from")
    if not _is_int(payload.get("issued_at")) or not _is_int(payload.get("expires_at")):
        return Verdict.reject("payload-shape", detail="timestamps")
    if payload["issued_at"] < 0 or payload["expires_at"] < 0:
        return Verdict.reject("payload-shape", detail="timestamps")
    return Verdict.accept()
