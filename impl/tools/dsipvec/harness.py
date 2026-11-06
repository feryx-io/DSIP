"""Run vectors through the Python reference semantics and compare with `expect`."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator

from . import envelope as E
from . import semantic as SEM
from .crypto import b64url_decode
from .session import Endpoint
from .relay import Relay
from .broadcast import Authority, Subscriber, evaluate_provenance, select_variant, stream_in_namespace
from . import binding as BINDING
from . import gateway as GATEWAY
from . import trust as TRUST
from . import webvh as WEBVH
from . import events as EVENTS
from . import kt as KT
from . import pkarr as PKARR
from . import messaging as MESSAGING
from .verdict import Verdict

IMPL_ROOT = Path(__file__).resolve().parents[2]
VECTOR_DIR = IMPL_ROOT / "vectors"
from .schema import validator as spec_validator  # v0.7: hint and provenance schemas are in the spec set
from .registry import effective_integrity


@dataclass
class Result:
    vector: str
    ok: bool
    expected: object
    actual: object
    note: str = ""
    steps: list = field(default_factory=list)


def load_vectors(root: Path = VECTOR_DIR, only: str | None = None) -> list[dict]:
    out = []
    for p in sorted(root.rglob("*.json")):
        if p.name == "fixtures.json":
            continue
        v = json.loads(p.read_text())
        if only and not v["vector"].startswith(only):
            continue
        out.append(v)
    return out


# ---------------------------------------------------------------- per-kind runners

def run_envelope_like(v: dict) -> dict:
    ctx = E.Context.from_vector(v["context"])
    frame_text = v["input"].get("frame")
    verdict, ver = E.verify(v["input"]["envelope"], ctx, frame_text)
    if not verdict.ok:
        return verdict.to_expect()
    p = ver.payload
    # ws/1.0 binding state (§13.2): nothing but hello before a verified hello
    if v["context"].get("hello_verified") is False and p["type"] != "hello":
        return Verdict.reject("hello-required", "transport.hello-required").to_expect()
    size = len((frame_text or E.frame(v["input"]["envelope"])).encode("utf-8"))
    if v["kind"] == "dht":
        return run_dht_tail(v, verdict, ver)
    pv = SEM.check_payload(p, v["context"], encoded_size=size)
    if not pv.ok:
        return pv.to_expect()
    out = verdict.to_expect()
    out.update(pv.extra)
    return out


def run_payload(v: dict) -> dict:
    from .schema import schema_errors
    errs = schema_errors(v["input"]["schema"], v["input"]["payload"])
    return Verdict.reject("schema-invalid", detail=errs[0] if errs else None).to_expect() if errs else Verdict.accept().to_expect()


def run_semantic(v: dict) -> dict:
    return SEM.check_payload(v["input"]["payload"], v["context"]).to_expect()




def hint_validator() -> Draft202012Validator:
    return spec_validator("reachability-hint")


def run_dht_tail(v: dict, verdict: Verdict, ver) -> dict:
    p = ver.payload
    ctx = v["context"]
    # A hint binds to its subject: whoever signed must be (or be delegated by) the subject.
    if verdict.extra.get("identity") != p.get("subject"):
        return Verdict.reject("hint-subject-mismatch").to_expect()
    vv = SEM.check_version(p, ctx.get("supported") or {})
    if not vv.ok:
        return vv.to_expect()
    if list(hint_validator().iter_errors(p)):
        return Verdict.reject("schema-invalid").to_expect()
    # 1.x, spec-gap 179: a key agreement delegation the hint carries verifies for its subject, or the hint is refused
    if "key_agreement" in p:
        from . import key_agreement as KA
        if KA.verify(p["key_agreement"], ctx["now"], p["subject"], ctx)[0] is None:
            return Verdict.reject("key-agreement-invalid").to_expect()
    out = verdict.to_expect()
    existing = ctx.get("existing")
    winner, conflict = "input", "none"
    if existing is not None:
        ex = json.loads(b64url_decode(existing["payload"]).decode("utf-8"))
        if ex.get("expires_at", 0) <= ctx["now"]:
            winner, conflict = "input", "none"          # §8.3: expired records are invalid (§12.9, spec-gap 141: at expires_at)
        elif p["seq"] > ex["seq"]:
            winner, conflict = "input", "newer-seq"      # §8.3: newer sequence wins
        elif p["seq"] < ex["seq"]:
            winner, conflict = "existing", "older-seq"
        elif existing["payload"] == v["input"]["envelope"]["payload"]:
            winner, conflict = "existing", "none"        # identical record
        else:
            winner, conflict = "existing", "same-seq-live"  # §8.3: conflicting live records → warn
    out.update(winner=winner, conflict=conflict)
    return out




def prov_validator() -> Draft202012Validator:
    return spec_validator("provenance")


def run_broadcast(v: dict) -> dict:
    """Receiver-side: verify the publication, evaluate provenance statements, select a variant (§22)."""
    ctx = E.Context.from_vector(v["context"])
    verdict, ver = E.verify(v["input"]["publication"], ctx)
    if not verdict.ok:
        return verdict.to_expect()
    p = ver.payload
    if p.get("publisher") != verdict.extra["identity"]:
        return Verdict.reject("publisher-mismatch").to_expect()
    if not stream_in_namespace(p.get("stream_id", ""), p["publisher"]):
        return Verdict.reject("stream-id-namespace").to_expect()
    pv = SEM.check_payload(p, v["context"])
    if not pv.ok:
        return pv.to_expect()
    out = verdict.to_expect()
    out["selected_variant"] = select_variant(p.get("variants", []), v["input"].get("capabilities", {}))
    results, delivered, transcoded = [], [], []
    for env in v["input"].get("provenance", []):
        pverdict, pver = E.verify(env, ctx)
        if not pverdict.ok:
            results.append(pverdict.to_expect())
            continue
        sp = pver.payload
        vv = SEM.check_version(sp, v["context"].get("supported") or {})
        if not vv.ok:
            results.append(vv.to_expect())
            continue
        if list(prov_validator().iter_errors(sp)):
            results.append({"verdict": "reject", "code": "schema-invalid"})
            continue
        r = evaluate_provenance(sp, pverdict.extra["identity"], p)
        results.append(r)
        if r["verdict"] == "accept":
            (transcoded if r["operation"] == "transcode" else delivered).append(r["processor"])
    out["provenance"] = results
    # §22.2 (v0.7, spec-gap 20): the record declares its mode (variant override allowed; unknown → metadata-only);
    # a verified transcode statement makes the delivered stream derivative-bound regardless.
    declared = effective_integrity(p.get("integrity"))
    sel = next((v for v in p.get("variants", []) if v.get("id") == out["selected_variant"]), None)
    if sel is not None and "integrity" in sel:
        declared = effective_integrity(sel["integrity"])
    out["display"] = {"original_publisher": p["publisher"], "delivered_by": delivered, "transcoded_by": transcoded,
                      "integrity_mode": "derivative-bound" if transcoded else declared}
    return out


def snapshot_for(comp, key: str, expected) -> object:
    if key in ("sessions", "attempts"):
        return comp.snapshot(expected.keys())
    if key == "contacts":
        return comp.contacts_snapshot()
    if key == "presence_keys":
        return comp.presence_keys_snapshot()
    if key == "inbox":
        return comp.inbox_snapshot()
    if key == "publications":
        return comp.snapshot_publications()
    if key == "presence":
        return comp.snapshot_presence()
    if key == "subscriptions":
        return comp.snapshot_subscriptions() if isinstance(comp, Authority) else comp.snapshot()
    raise KeyError(key)


def run_state(v: dict) -> tuple[bool, list]:
    ctx = v["context"]
    component = ctx.get("component", "endpoint")
    comp = {"relay": Relay, "authority": Authority, "subscriber": Subscriber}.get(component, Endpoint)(ctx)
    results, ok = [], True
    for i, st in enumerate(v["input"]["steps"]):
        emit = comp.step(st["event"])
        exp = st["expect"]
        actual = {"emit": emit}
        for k in exp:
            if k != "emit":
                actual[k] = snapshot_for(comp, k, exp[k])
        step_ok = actual == exp
        ok = ok and step_ok
        results.append({"step": i, "ok": step_ok, "expected": exp, "actual": actual})
    return ok, results


def run_vector(v: dict) -> Result:
    kind = v["kind"]
    try:
        if kind == "state":
            ok, steps = run_state(v)
            return Result(v["vector"], ok, None, None, steps=steps)
        if kind in ("envelope", "transport", "dht"):
            actual = run_envelope_like(v)
        elif kind == "payload":
            actual = run_payload(v)
        elif kind == "semantic":
            actual = run_semantic(v)
        elif kind == "broadcast":
            actual = run_broadcast(v)
        elif kind == "media-binding":
            actual = BINDING.run(v)
        elif kind == "gateway":
            actual = GATEWAY.run(v)
        elif kind == "trust":
            actual = TRUST.run(v)
        elif kind == "messaging":
            actual = MESSAGING.run(v)
        elif kind == "pkarr":
            actual = PKARR.run(v)
        elif kind == "alias-transparency":
            actual = KT.run(v)
        elif kind == "device-events":
            actual = EVENTS.run(v)
        elif kind == "tn-binding":
            from . import tnbinding as TNBINDING
            actual = TNBINDING.run(v)
        elif kind == "recording":
            from . import recording as RECORDING
            actual = RECORDING.run(v)
        elif kind == "presence":
            from . import presence as PRESENCE
            actual = PRESENCE.run(v)
        elif kind == "wake":
            from . import wake as WAKE
            actual = WAKE.run(v)
        elif kind == "key-agreement":
            from . import key_agreement as KA
            actual = KA.run(v)
        elif kind == "did-webvh":
            i = v["input"]
            actual = WEBVH.resolve(i["did"], i["log"], i["witness"], i["cache"], i["now"])
        else:
            return Result(v["vector"], False, v["expect"], None, note=f"unknown kind {kind}")
    except Exception as e:  # a crash is a failure, never a pass
        return Result(v["vector"], False, v["expect"], None, note=f"exception: {type(e).__name__}: {e}")
    return Result(v["vector"], actual == v["expect"], v["expect"], actual)
