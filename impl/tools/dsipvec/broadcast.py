"""§22 Verified Broadcast + §9.3 subscription protocol — Python reference for the broadcast vectors.

Components:
- `Authority`: the target's relay/domain endpoint. Holds signed publication records and devices' presence records
  (Presence Profile P§3), answers `subscribe` with policy (public / allowlist / capability token; anti-enumeration),
  emits seq-ordered `notify`s, terminates lapsed subscriptions, attaches provenance statements.
- `Subscriber`: tracks its subscriptions, enforces seq ordering and terminal state.
- `evaluate_publication` / `evaluate_provenance` / `select_variant`: the receiver's stateless checks.

Every `Impl:` comment marks a choice the spec leaves open (impl/docs/spec-gaps.md 18–21).
"""
from __future__ import annotations

from .registry import SUBSCRIPTION_EVENTS, resolve_reason
from .presence import RECORD_MIN_LIFETIME_S, RECORD_MAX_LIFETIME_S, PRESENCE_GRACE_S, PUBLISH_INTERVAL_S

INTEGRITY_MODES = ("metadata-only", "derivative-bound")           # §22.2 core; others reserved
PROVENANCE_OPERATIONS = ("transcode", "relay", "repackage")        # dsip-provenance-operation (§22.3, v0.7)


def stream_in_namespace(stream_id: str, publisher: str) -> bool:
    """Impl (spec-gap 18): a stream_id is the publisher DID or a colon-suffixed extension of it."""
    return stream_id == publisher or stream_id.startswith(publisher + ":")


# ---------------------------------------------------------------- authority

class Authority:
    """Spec: §9.3 (subscribe/notify, authorization, anti-enumeration), §22.1 (publication records),
    §22.3 (provenance statements carried with the record); P§3 (presence records published, kept, expired, held through
    an unbind's grace), P§4 (one record per device), P§6 (who may watch, audiences, a body per subscription) and P§7
    (a grant's expiry and revocation end the subscriptions it admitted)."""

    def __init__(self, ctx: dict):
        self.now = ctx.get("start", 0)
        self.identities: dict[str, str] = dict(ctx.get("identities", {}))
        self.publications: dict[str, dict] = {}      # stream_id → {"publication", "publisher", "state", "expires_at", "variants", "policy"}
        self.provenance: dict[str, list[dict]] = {}  # stream_id → provenance statements (abbrev)
        self.subscriptions: dict[str, dict] = {}     # subscription id → {...}
        self.policy: dict[str, dict] = {}            # target → {"mode": "public"|"allow", "allow": [...], "audience"?}
        self.capabilities: dict[str, str] = {}       # token → target
        self.bound: dict[str, set[str]] = {}         # identity → its bound devices (presence)
        # (subject, device, audience) → the device's current record for that audience (P§3, P§6; "" = no audience)
        self.records: dict[tuple[str, str, str], dict] = {}
        self.grace_until: dict[str, int] = {}        # device → when its records are dropped, after an unbind (P§3)
        self.last_accepted: dict[tuple[str, str], int] = {}  # (device, audience) → its last accepted record (P§8, P§6)
        self.revoked: dict[tuple[str, str], int] = {}  # (granting identity, grant id) → the grant's valid_until (P§7)
        self.grace = ctx.get("presence_grace", PRESENCE_GRACE_S)  # P§8 T-Presence-Grace, the authority's choice
        self.out: list[dict] = []

    def identity_of(self, did: str) -> str:
        return self.identities.get(did, did)

    def emit(self, e: dict) -> None:
        self.out.append(e)

    def send(self, **f) -> None:
        self.emit({"send": {k: v for k, v in f.items() if v is not None}})

    def step(self, event: dict) -> list[dict]:
        self.out = []
        if "advance" in event:
            self.now += event["advance"]
            self.expire()
        elif "recv" in event:
            self.recv(event["recv"])
        elif "local" in event:
            self.local(event)
        elif "relay" in event:
            identity, device = event["identity"], event["device"]
            if event["relay"] == "bind":
                self.bound.setdefault(identity, set()).add(device)
                self.grace_until.pop(device, None)  # P§3: back within the grace, the record stays
            elif event["relay"] == "unbind":
                self.bound.get(identity, set()).discard(device)
                if self.holds_record(identity, device) and device not in self.grace_until:
                    # P§3: the records outlive the binding by T-Presence-Grace, from the first unbind; 0 drops them now
                    if self.grace == 0:
                        self.drop_device(identity, device)
                    else:
                        self.grace_until[device] = self.now + self.grace
            # P§3, P§6: a binding change notifies only the subscriptions whose body it changes
            self.presence_changed(identity)
        else:
            raise ValueError(event)
        return self.out

    # ------------------------------------------------------------ local policy

    def local(self, ev: dict) -> None:
        if ev["local"] == "policy":
            self.policy[ev["target"]] = {"mode": ev["mode"], "allow": list(ev.get("allow", [])), "audience": ev.get("audience")}
        elif ev["local"] == "issue_capability":
            self.capabilities[ev["token"]] = ev["target"]
        else:
            raise ValueError(ev)

    # ------------------------------------------------------------ records

    def recv(self, m: dict) -> None:
        t = m["type"]
        identity = self.identity_of(m["from"])
        if t == "publish":
            # §22.1: a publication record is signed by the publisher (or a delegate); the record's `publisher`
            # MUST be the verified identity (Impl, spec-gap 18), and stream_id lives under it.
            if m["publisher"] != identity:
                return self.emit({"drop": "publisher-mismatch"})
            if not stream_in_namespace(m["stream_id"], m["publisher"]):
                return self.emit({"drop": "stream-id-namespace"})
            cur = self.publications.get(m["stream_id"])
            if cur is not None and m["id"] <= cur["publication"]:
                # §8.3 spirit: newer replaces older; ULIDs order publications of one stream (Impl)
                return self.emit({"drop": "stale-publication"})
            self.publications[m["stream_id"]] = {"publication": m["id"], "publisher": m["publisher"], "state": m["state"],
                                                 "expires_at": m["expires_at"], "variants": list(m.get("variants", [])),
                                                 "policy": dict(m.get("policy", {}))}
            # Statements reference a specific publication id (§22.3); a replacing record starts with none.
            self.provenance.pop(m["stream_id"], None)
            self.emit({"publication": {"stream": m["stream_id"], "state": m["state"]}})
            self.notify_all("publication", m["stream_id"])
        elif t == "unpublish":
            cur = self.publications.get(m["stream_id"])
            if cur is None or cur["publication"] != m["publication"]:
                return self.emit({"drop": "unknown-publication"})
            if cur["publisher"] != identity:
                return self.emit({"drop": "publisher-mismatch"})
            cur["state"] = "withdrawn"
            self.emit({"publication": {"stream": m["stream_id"], "state": "withdrawn"}})
            self.notify_all("publication", m["stream_id"])
        elif t == "provenance":
            # §22.3: a processor adds its own signed statement; it never overwrites the publisher's record.
            cur = self.publications.get(m["original_stream"])
            if cur is None or cur["publication"] != m["original_publication"]:
                return self.emit({"drop": "provenance-unknown-publication"})
            if m["processor"] != identity:
                return self.emit({"drop": "provenance-processor-mismatch"})
            if m["input_variant"] not in [v["id"] for v in cur["variants"]]:
                return self.emit({"drop": "provenance-variant-unknown"})
            self.provenance.setdefault(m["original_stream"], []).append(
                {"processor": m["processor"], "operation": m["operation"], "input_variant": m["input_variant"],
                 "output_variant": m["output_variant"]})
            self.emit({"provenance": {"stream": m["original_stream"], "processor": m["processor"]}})
            self.notify_all("publication", m["original_stream"])
        elif t == "subscribe":
            self.recv_subscribe(m, identity)
        elif t == "presence":
            self.recv_presence(m, identity)
        elif t == "grant-revocation":
            self.recv_revocation(m, identity)
        else:
            self.emit({"drop": "not-broadcast"})

    # ------------------------------------------------------------ presence records (P§3)

    def recv_presence(self, m: dict, identity: str) -> None:
        """P§3: a device's own record, checked in the profile's order; accepted silently, refused with `error`."""
        def refuse(reason: str, **extra) -> None:
            self.send(type="error", to=m["from"], in_reply_to=m["id"], reason=reason, **extra)

        device = m.get("device")
        if device is None or device != m["from"] or m["subject"] != identity:
            return refuse("presence.signer-mismatch")
        if not RECORD_MIN_LIFETIME_S <= m["expires_at"] - m["issued_at"] <= RECORD_MAX_LIFETIME_S:
            return refuse("presence.lifetime")  # P§8
        audience = m.get("audience", "")
        key = (identity, device, audience)
        held = self.records.get(key)
        if held is not None and m["seq"] <= held["seq"]:
            return refuse("presence.stale")  # P§4, P§6: seq is ordered per (subject, device, audience)
        last = self.last_accepted.get((device, audience))
        if last is not None and self.now - last < PUBLISH_INTERVAL_S:
            return refuse("policy.rate-limited", retry_after=PUBLISH_INTERVAL_S - (self.now - last))  # P§8, per audience
        rec = {"id": m["id"], "device": device, "seq": m["seq"], "expires_at": m["expires_at"]}
        # P§12.6: a sealed record is kept and routed as any other; its state is not the authority's to read
        rec.update({k: m[k] for k in ("state", "kid", "sealed_state") if k in m})
        if audience:
            rec["audience"] = audience
        self.records[key] = rec
        self.last_accepted[(device, audience)] = self.now
        self.presence_changed(identity)

    def recv_revocation(self, m: dict, identity: str) -> None:
        """P§7, §19.4: a grant withdrawn by its grantor's device; every subscription it admitted ends at once."""
        self.revoked[(identity, m["grant"])] = m["valid_until"]
        for sid in sorted(self.subscriptions):
            sub = self.subscriptions[sid]
            if sub.get("grant") == m["grant"] and sub["target"] == identity:
                self.notify(sid, "terminated", "policy.terminated")

    def holds_record(self, subject: str, device: str) -> bool:
        return any(s == subject and d == device for (s, d, _) in self.records)

    def drop_device(self, subject: str, device: str) -> None:
        """P§3: a device whose grace ran out loses every record, and their seqs are forgotten."""
        for key in [k for k in self.records if k[0] == subject and k[1] == device]:
            del self.records[key]
        self.grace_until.pop(device, None)

    def presence_body(self, subject: str, sub: dict | None = None) -> dict:
        """P§3, P§6: over the records `sub` sees, the assertion for the bound devices that hold none of them, and those
        records by device, then audience (none first). `sub` None: every record (the subject's own view)."""
        def sees(rec: dict) -> bool:
            # P§12.6 (spec-gap 156): a subscription that did not list presence/0.2 is given no sealed record
            if "sealed_state" in rec and sub is not None and not sub.get("sealed"):
                return False
            a = rec.get("audience")
            return sub is None or sub.get("own") or a is None or a == sub.get("audience")
        recs = [r for (subj, _, _), r in sorted(self.records.items()) if subj == subject and sees(r)]
        bound = self.bound.get(subject, set())
        asserted = "available" if any(all(r["device"] != d for r in recs) for d in bound) else "offline"
        body: dict = {"event": "presence", "state": asserted}
        if recs:
            body["records"] = recs
        return body

    # ------------------------------------------------------------ subscriptions (§9.3)

    def authorized(self, target: str, identity: str, token: str | None) -> bool:
        if token is not None and self.capabilities.get(token) == target:
            return True
        pol = self.policy.get(target, {"mode": "public", "allow": []})
        return pol["mode"] == "public" or identity in pol["allow"]

    def admit_presence(self, target: str, identity: str, m: dict) -> dict | None:
        """P§6 (spec-gap 144): the first rule that admits a presence subscriber — its own identity, a presented grant,
        a capability, the authority's policy — and what it fixes: the audience (spec-gap 145), the admitting grant. With
        no policy for the target only the first three can admit: presence is private by default (§9.2)."""
        if identity == target:
            return {"own": True}
        for claim in m.get("claims", []):
            g = claim.get("grant") if claim.get("type") == "dsip-grant" else None
            if (g is not None and g.get("verified", True) and g["identity"] == target and g["to"] == identity
                    and "dsip.subscribe" in g["scope"] and g["valid_until"] > self.now
                    and (target, g["id"]) not in self.revoked):
                return {"grant": g["id"], "grant_until": g["valid_until"], "audience": g.get("presence_audience")}
        token = m.get("capability")
        if token is not None and self.capabilities.get(token) == target:
            return {}
        pol = self.policy.get(target)
        if pol is not None and (pol["mode"] == "public" or identity in pol["allow"]):
            return {"audience": pol.get("audience")}
        return None

    def target_exists(self, target: str, events: list) -> bool:
        """§9.3: a target this authority has seen. Spec-gap 149 (a): for presence, an identity it holds a device for, one
        with a bound device, or one it holds a policy or an issued capability for; for publication, a published stream."""
        if "publication" in events:
            return target in self.publications
        return (target in self.identities.values() or bool(self.bound.get(target)) or target in self.policy
                or target in self.capabilities.values())

    def recv_subscribe(self, m: dict, identity: str) -> None:
        target, events = m["target"], list(m["events"])
        # §9.3 (spec-gap 177): a subscription is the subscribing device's; renewal and termination match its device
        existing = next((sid for sid, s in self.subscriptions.items()
                         if s["device"] == m["from"] and s["target"] == target and s["events"] == events), None)
        if m["expires_in"] == 0:
            # §9.3: expires_in 0 terminates a matching subscription (no notify is owed to the requester)
            if existing is not None:
                del self.subscriptions[existing]
                self.emit({"subscription": {"id": existing, "state": "terminated"}})
            else:
                self.emit({"drop": "no-matching-subscription"})
            return
        # §9.3 anti-enumeration: unauthorized and nonexistent targets get the identical reject
        admitted = {} if "presence" not in events else self.admit_presence(target, identity, m)
        if (not self.target_exists(target, events) or admitted is None
                or ("presence" not in events and not self.authorized(target, identity, m.get("capability")))):
            self.send(type="reject", to=m["from"], session=m["id"], reason="policy.blocked")
            return
        cap = min(SUBSCRIPTION_EVENTS.get(e, 86400) for e in events)
        lifetime = min(m["expires_in"], cap)
        if existing is not None:
            # renewal replaces the prior subscription (same device, target and events)
            del self.subscriptions[existing]
            self.emit({"subscription": {"id": existing, "state": "replaced"}})
        sub = {"subscriber": identity, "device": m["from"], "target": target, "events": events,
               "expires_at": self.now + lifetime, "seq": 0, **{k: v for k, v in admitted.items() if v is not None}}
        if "presence/0.2" in m.get("profiles", []):
            sub["sealed"] = True  # P§12.6: the subscriber reads sealed records
        self.subscriptions[m["id"]] = sub
        # Acceptance is signaled by the first notify, which carries the current state
        self.notify(m["id"], "active")

    def body_for(self, sub: dict) -> dict:
        if "publication" in sub["events"]:
            pub = self.publications.get(sub["target"])
            body = {"event": "publication", "state": pub["state"] if pub else "unknown"}
            if pub:
                body["publication"] = pub["publication"]
                prov = self.provenance.get(sub["target"], [])
                if prov:
                    body["provenance"] = [p["processor"] for p in prov]
            return body
        return self.presence_body(sub["target"], sub)

    def notify(self, sid: str, state: str, reason: str | None = None) -> None:
        sub = self.subscriptions[sid]
        sub["seq"] += 1
        sub["body"] = self.body_for(sub)
        self.send(type="notify", to=sub["device"], subscription=sid, seq=sub["seq"], state=state, reason=reason,
                  body=sub["body"])
        if state == "terminated":
            del self.subscriptions[sid]

    def notify_all(self, event: str, target: str) -> None:
        for sid in sorted(s for s, sub in self.subscriptions.items() if sub["target"] == target and event in sub["events"]):
            self.notify(sid, "active")

    def presence_changed(self, identity: str) -> None:
        """P§6 (spec-gap 146): each presence subscription to the subject is notified exactly when its own body changed."""
        for sid in sorted(s for s, sub in self.subscriptions.items() if sub["target"] == identity and "presence" in sub["events"]):
            sub = self.subscriptions[sid]
            if self.body_for(sub) != sub.get("body"):
                self.notify(sid, "active")

    def expire(self) -> None:
        for sid in sorted(self.subscriptions):
            sub = self.subscriptions[sid]
            if sub["expires_at"] <= self.now:
                # §9.3: soft state — lapsed subscriptions end with a terminal notify carrying session.expired
                self.notify(sid, "terminated", "session.expired")
            elif "grant_until" in sub and sub["grant_until"] <= self.now:
                self.notify(sid, "terminated", "policy.terminated")  # P§7: the admitting grant (the share) has ended
        # P§7: a revocation is kept until the revoked grant's valid_until
        self.revoked = {k: until for k, until in self.revoked.items() if until > self.now}
        for stream, pub in list(self.publications.items()):
            if pub["state"] in ("live", "scheduled") and pub["expires_at"] <= self.now:
                pub["state"] = "expired"
                self.emit({"publication": {"stream": stream, "state": "expired"}})
                self.notify_all("publication", stream)
        # P§3: records past expires_at, and those whose grace ran out, are dropped; one notify per subject, in order
        changed = set()
        for (subject, device, audience), rec in sorted(self.records.items()):
            if (subject, device, audience) not in self.records:
                continue  # dropped with its device's other records
            if self.grace_until.get(device, self.now + 1) <= self.now:
                self.drop_device(subject, device)
                changed.add(subject)
            elif rec["expires_at"] <= self.now:
                del self.records[(subject, device, audience)]
                changed.add(subject)
        # P§3: a grace that ran out is over even when the device's records expired first; a later record has none
        self.grace_until = {d: until for d, until in self.grace_until.items() if until > self.now}
        for subject in sorted(changed):
            self.presence_changed(subject)

    def snapshot_publications(self) -> dict:
        return {s: {"publication": p["publication"], "publisher": p["publisher"], "state": p["state"]}
                for s, p in sorted(self.publications.items())}

    def snapshot_presence(self) -> dict:
        """P§3: `{subject: {device: {seq, state, expires_at, grace_until?}}}`, the key `device/audience` for a record with
        an audience (P§6)."""
        out: dict = {}
        for (subject, device, audience), r in sorted(self.records.items()):
            snap = {"seq": r["seq"], **({"state": r["state"]} if "state" in r else {"kid": r["kid"]}),
                    "expires_at": r["expires_at"]}
            if device in self.grace_until:
                snap["grace_until"] = self.grace_until[device]
            out.setdefault(subject, {})[f"{device}/{audience}" if audience else device] = snap
        return out

    def snapshot_subscriptions(self) -> dict:
        out = {}
        for sid, s in sorted(self.subscriptions.items()):
            snap = {"subscriber": s["subscriber"], "target": s["target"], "events": s["events"], "seq": s["seq"],
                    "expires_at": s["expires_at"]}
            # P§6: how a presence subscription was admitted, when it was not by policy or a capability
            snap.update({k: s[k] for k in ("own", "grant", "audience", "sealed") if k in s})
            out[sid] = snap
        return out


# ---------------------------------------------------------------- subscriber

class Subscriber:
    """Spec: §9.3 — seq ordering (discard lower-than-seen), terminal state, renewal as a fresh subscribe."""

    def __init__(self, ctx: dict):
        self.now = ctx.get("start", 0)
        self.subs: dict[str, dict] = {}
        self.out: list[dict] = []

    def emit(self, e: dict) -> None:
        self.out.append(e)

    def step(self, event: dict) -> list[dict]:
        self.out = []
        if "advance" in event:
            self.now += event["advance"]
            for sid, s in sorted(self.subs.items()):
                if s["state"] == "active" and s["expires_at"] <= self.now:
                    s["state"] = "lapsed"
                    self.emit({"ui": "subscription_lapsed", "subscription": sid})
        elif "local" in event and event["local"] == "subscribe":
            ev = event
            self.subs[ev["id"]] = {"target": ev["target"], "events": list(ev["events"]), "state": "pending", "seq": 0,
                                   "expires_at": self.now + ev["expires_in"]}
            self.emit({"send": {"type": "subscribe", "to": ev["to"], "id": ev["id"], "target": ev["target"],
                                "events": list(ev["events"]), "expires_in": ev["expires_in"]}})
        elif "recv" in event:
            self.recv(event["recv"])
        else:
            raise ValueError(event)
        return self.out

    def recv(self, m: dict) -> None:
        if m["type"] == "reject":
            s = self.subs.get(m.get("session"))
            if s is None:
                return self.emit({"drop": "unknown-subscription"})
            s["state"] = "rejected"
            self.emit({"ui": "subscription_rejected", "reason": resolve_reason(m["reason"], "reject").effective})
            return
        if m["type"] != "notify":
            return self.emit({"drop": "not-subscription"})
        s = self.subs.get(m["subscription"])
        if s is None:
            return self.emit({"drop": "unknown-subscription"})
        if s["state"] in ("terminated", "rejected"):
            return self.emit({"drop": "terminated-subscription"})
        if m["seq"] <= s["seq"]:
            return self.emit({"drop": "stale-seq"})  # §9.3: receivers discard lower-than-seen seq
        s["seq"] = m["seq"]
        if m["state"] == "terminated":
            s["state"] = "terminated"
            self.emit({"ui": "subscription_terminated", "reason": m.get("reason")})
            return
        s["state"] = "active"
        body = m.get("body", {})
        self.emit({"ui": "notify", "event": body.get("event"), "state": body.get("state")})

    def snapshot(self) -> dict:
        return {sid: {"target": s["target"], "state": s["state"], "seq": s["seq"]} for sid, s in sorted(self.subs.items())}


# ---------------------------------------------------------------- receiver (stateless)

def select_variant(variants: list, caps: dict) -> str | None:
    """Receiver picks the first advertised variant whose codec and transport it supports (§22.1 order = publisher preference)."""
    for v in variants:
        if v.get("codec") in caps.get("codecs", []) and v.get("transport") in caps.get("transports", []):
            return v["id"]
    return None


def evaluate_provenance(stmt: dict, stmt_identity: str, publication: dict) -> dict:
    """§22.3 checks for one statement against the verified publication it references."""
    if stmt.get("original_publication") != publication["id"]:
        return {"verdict": "reject", "code": "provenance-unknown-publication"}
    if stmt.get("original_stream") != publication["stream_id"]:
        return {"verdict": "reject", "code": "provenance-stream-mismatch"}
    if stmt.get("processor") != stmt_identity:
        return {"verdict": "reject", "code": "provenance-processor-mismatch"}
    if stmt.get("input_variant") not in [v["id"] for v in publication.get("variants", [])]:
        return {"verdict": "reject", "code": "provenance-variant-unknown"}
    # spec-gap 77: a statement has no integrity mode of its own; the delivered stream's mode is the display's
    out = {"verdict": "accept", "processor": stmt["processor"], "operation": stmt["operation"]}
    pol = publication.get("policy", {})
    if stmt["operation"] == "transcode" and pol.get("transcoding") in ("forbidden", "denied"):
        out["policy_violation"] = "transcoding"  # §16.4: policy is displayed/enforced by receivers, not magic
    if pol.get("redistribution") == "forbidden":
        out["policy_violation"] = "redistribution"
    return out
