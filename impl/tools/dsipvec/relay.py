"""§12.7 forking relay attempt tracker — Python reference for `state/relay-*` traces.

The relay tracks which legs an invite was delivered to and which have
terminated, delivers `cancel` per-leg, and signals the attempt outcome with
the most informative reason when the last leg terminates without an answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# §12.7 rule 6 preference order; anything else ranks after these, first-seen first.
REASON_RANK = ["user.declined", "user.no-answer", "endpoint.busy", "endpoint.unavailable"]
TERMINAL = ("answered", "rejected", "expired", "cancelled")
# §12.9/§12.10: the T-Queue hard cap, the longest a caller waits on one progress. §13.3 (v0.16, spec-gap 131): an attempt is held
# until more than this passes with no message for it.
T_QUEUE_CAP_S = 1800


@dataclass
class Attempt:
    session: str
    initiator: str
    identity: str
    legs: dict[str, str] = field(default_factory=dict)          # device -> delivered|answered|rejected|expired|cancelled
    reasons: dict[str, str] = field(default_factory=dict)       # device -> reject reason
    outcome: str | None = None                                  # None | answered | rejected | cancelled
    order: list[str] = field(default_factory=list)
    last: int = 0                                               # when the relay last forked, flushed or heard from it (spec-gap 131)
    heard: set[str] = field(default_factory=set)                # legs that have sent progress, answer or reject (spec-gap 132)

    def snapshot(self) -> dict:
        return {"legs": dict(self.legs), "outcome": self.outcome}


class Relay:
    """Spec: §12.7 rules 3 and 6, §13.2 delivery semantics."""

    def __init__(self, ctx: dict):
        self.now = ctx.get("start", 0)
        self.attempts: dict[str, Attempt] = {}
        self.out: list[dict] = []
        self.bindings: dict[str, set[str]] = {}        # identity → bound devices (§13.2); a key = "known" identity
        self.devices: dict[str, str] = {}              # device → identity, for every device ever bound
        self.inbox: dict[str, list[dict]] = {}         # identity/device → queued envelopes (§13.3 store-and-forward)
        self.arrivals = 0                              # arrival counter: a flush delivers in arrival order (spec-gap 98)
        self.retention: int = ctx.get("offline_retention_s", 86400)
        self.invites: dict[str, dict] = {}             # session → invite message (for legs added mid-attempt)
        self.last_bound: dict[str, int] = {}           # identity or device → when its last binding ended (spec-gap 131)

    def emit(self, e: dict) -> None:
        self.out.append(e)

    def step(self, event: dict) -> list[dict]:
        self.out = []
        if "advance" in event:
            self.now += event["advance"]
            self.expire_queues()
            self.expire_silent_legs()
            self.forget()
        elif "relay" in event:
            self.relay_event(event)
        elif "recv" in event:
            self.recv(event["recv"])
        else:
            raise ValueError(f"unknown relay event {event}")
        return self.out

    def relay_event(self, ev: dict) -> None:
        if ev["relay"] == "invite":
            a = Attempt(ev["session"], ev["from"], ev["to"], last=self.now)
            for leg in ev["legs"]:
                a.legs[leg] = "delivered"
                self.emit({"deliver": {"leg": leg, "type": "invite"}})
            self.attempts[a.session] = a
        elif ev["relay"] == "bind":
            device, identity = ev["device"], ev["identity"]
            self.bindings.setdefault(identity, set()).add(device)
            self.devices[device] = identity
            self.last_bound.pop(identity, None)
            self.last_bound.pop(device, None)
            # §13.3: flush the store-and-forward queues for the identity and the device together, in the order the
            # envelopes arrived (spec-gap 98) — not the identity's queue first
            queued = self.inbox.pop(identity, []) + self.inbox.pop(device, [])
            for m in sorted(queued, key=lambda q: q["_arrival"]):
                self.flush_to(device, m)
            # §12.7 rule 3: a device that binds while an attempt for its identity is live becomes a new leg
            for sid, a in sorted(self.attempts.items()):  # id order when several attempts are live (spec-gap 89)
                if a.identity == identity and a.outcome is None and device not in a.legs:
                    inv = self.invites.get(sid)
                    # unexpired as the envelope pipeline means it: `expired` from expires_at (§12.9, spec-gap 141)
                    if inv is not None and inv.get("expires_at", self.now + 1) > self.now:
                        a.legs[device] = "delivered"
                        a.last = self.now
                        self.emit({"deliver": {"leg": device, "type": "invite", "id": sid}})
        elif ev["relay"] == "unbind":
            self.bindings.get(ev["identity"], set()).discard(ev["device"])
            self.last_bound[ev["device"]] = self.now
            if not self.bindings.get(ev["identity"]):
                self.last_bound[ev["identity"]] = self.now
        elif ev["relay"] == "leg_expired":
            a = self.attempts.get(ev["session"])  # an expiry for an attempt no longer held changes nothing
            if a is not None and a.legs.get(ev["leg"]) == "delivered":
                a.legs[ev["leg"]] = "expired"
                self.check_complete(a)
        else:
            raise ValueError(ev)

    def legs_for(self, to: str) -> list[str]:
        if to in self.devices:
            return [to] if to in self.bindings.get(self.devices[to], set()) else []
        return sorted(self.bindings.get(to, ()))

    def known(self, to: str) -> bool:
        """§13.3: a recipient is known if a device has bound for it here within the retention window. Impl (spec-gap
        131): while bound, and until `forget` drops it — offline_retention_s after its last binding ended, once nothing
        is held for it."""
        return to in self.bindings or to in self.devices

    def expire_silent_legs(self) -> None:
        """§12.7 rule 3 (v0.16, spec-gap 132): a leg that has sent nothing — no progress, answer or reject — once the invite has
        expired (from expires_at, §12.9, spec-gap 141) is expired. A responder acts only on an unexpired invite and acts at once
        (progress, answer or reject), so silence past expiry means the invite was never processed; a leg that rings
        ends itself with reject user.no-answer at T-Ring-Local (§12.9). When that leaves no leg outstanding the
        attempt completes as §12.7 rule 6 says. Attempts in id order, legs in device order (spec-gap 89); an attempt
        forked by a `relay invite` event carries no invite and is expired only by `leg_expired`."""
        for sid in sorted(self.attempts):
            a, inv = self.attempts[sid], self.invites.get(sid)
            if inv is None or "expires_at" not in inv or inv["expires_at"] > self.now:
                continue
            silent = [leg for leg in sorted(a.legs) if a.legs[leg] == "delivered" and leg not in a.heard]
            for leg in silent:
                a.legs[leg] = "expired"
            if silent:
                self.check_complete(a)

    def forget(self) -> None:
        """§13.3 (v0.16, spec-gap 131): what a relay stops holding. An attempt, once more than the T-Queue cap has passed since the
        relay last forked, flushed or added a leg for it or received a message of it from a leg or its initiator: its
        session is routed by `to` from then on, as after a restart (§13.3, spec-gap 82). An
        identity or device with nothing bound and nothing held, once its last binding ended more than offline_retention_s
        ago (§13.3 "within the relay's retention window"). Nothing is emitted."""
        for sid in [s for s, a in self.attempts.items() if a.last + T_QUEUE_CAP_S < self.now]:
            del self.attempts[sid]
            self.invites.pop(sid, None)
        for who in [w for w, t in self.last_bound.items() if t + self.retention < self.now and w not in self.inbox]:
            del self.last_bound[who]
            if who in self.devices:
                identity = self.devices[who]
                if who not in self.bindings.get(identity, set()):
                    del self.devices[who]
            elif not self.bindings.get(who):
                self.bindings.pop(who, None)

    def enqueue(self, m: dict) -> None:
        self.arrivals += 1
        self.inbox.setdefault(m["to"], []).append(dict(m, _arrival=self.arrivals, _deadline=min(m.get("expires_at", self.now + self.retention), self.now + self.retention)))
        self.emit({"queue": {"to": m["to"], "type": m["type"]}})

    def flush_to(self, device: str, m: dict) -> None:
        if m["type"] == "invite":
            # A queued invite becomes a tracked leg on delivery (§12.7 rule 3)
            sid = m["id"]
            a = self.attempts.get(sid)
            if a is None:
                a = Attempt(sid, m["from"], m["to"])
                self.attempts[sid] = a
                self.invites[sid] = m
            a.legs[device] = "delivered"
            a.last = self.now
            self.emit({"deliver": {"leg": device, "type": "invite", "id": sid}})
        else:
            self.emit({"deliver": {"leg": device, "type": m["type"], "id": m["id"]}})

    def expire_queues(self) -> None:
        for to in sorted(self.inbox):
            keep = []
            for m in self.inbox[to]:
                if m["_deadline"] <= self.now:
                    # §13.3: the relay holds envelopes only within the delivery boundary; the initiator's
                    # §12.9 timers are the backstop — nothing is signaled (Impl, spec-gap 17).
                    self.emit({"dequeue": {"to": to, "type": m["type"], "why": "expired"}})
                else:
                    keep.append(m)
            if keep:
                self.inbox[to] = keep
            else:
                del self.inbox[to]

    def recv(self, m: dict) -> None:
        if m["type"] == "introduction":
            # §19.4 anti-enumeration: an introduction to an unknown identity and one to an offline identity
            # get the identical treatment — queued, no error. (Impl, spec-gap 14: §13.2 "no silent drops"
            # yields to §19.4 here.) Bound devices receive it immediately.
            devices = self.legs_for(m["to"])
            if devices:
                for d in devices:
                    self.emit({"deliver": {"leg": d, "type": "introduction"}})
            else:
                self.enqueue(m)
            return
        if m["type"] == "invite":
            legs = self.legs_for(m["to"])
            if not legs:
                if self.known(m["to"]):
                    self.enqueue(m)  # §13.3 store-and-forward for a known, offline recipient
                else:
                    # Session traffic to an identity this relay has never seen is refused with a signed error (§13.2).
                    self.emit({"send": {"type": "error", "to": m["from"], "reason": "transport.unknown-recipient", "in_reply_to": m["id"]}})
                return
            self.invites[m["id"]] = m
            return self.relay_event({"relay": "invite", "session": m["id"], "from": m["from"], "to": m["to"], "legs": legs})
        a = self.attempts.get(m.get("session"))
        if a is None:
            if m["type"] == "cancel":
                # a cancel for an invite that is still queued: drop the queued invite (§12.11)
                queued = self.inbox.get(m["to"], [])
                remaining = [q for q in queued if not (q["type"] == "invite" and q["id"] == m["session"])]
                if len(remaining) != len(queued):
                    self.inbox[m["to"]] = remaining
                    if not remaining:
                        del self.inbox[m["to"]]
                    self.emit({"dequeue": {"to": m["to"], "type": "invite", "why": "cancelled"}})
                    return
            return self.route_plain(m)
        t = m["type"]
        if t not in ("progress", "answer", "reject", "cancel") or m.get("in_reply_to") is not None:
            # Post-answer and renegotiation traffic (update/info/bye, update replies) is not attempt-scoped:
            # plain routing by `to` (§13.2), queued for a known-offline device (§13.3).
            return self.route_plain(m)
        if t == "cancel" and m["from"] == a.initiator:
            # §12.7 rule 3: per-leg cancel to every leg that has not terminated — or, addressed to a device, to that
            # leg alone (§12.11: "a specific device DID (targeted cancel of one leg)")
            only = m.get("to") if m.get("to") in a.legs else None
            if only is None and m.get("to") not in (None, a.identity):
                # addressed to a device that is no leg of this attempt: not the attempt's business, and so not a message
                # that keeps it held (§13.3, spec-gap 187)
                return self.route_plain(m)
            a.last = self.now
            for leg in sorted(a.legs):  # device (DID) order, the suite's order wherever a relay fans out (spec-gap 89)
                st = a.legs[leg]
                if st == "delivered" and only in (None, leg):
                    a.legs[leg] = "cancelled"
                    self.emit({"deliver": {"leg": leg, "type": "cancel", "reason": m["reason"]}})
            if a.outcome is None and "delivered" not in a.legs.values():
                a.outcome = "cancelled"
            return
        leg = m["from"]
        if a.legs.get(leg) is None:
            return self.route_plain(m)  # spec-gap 82: not a leg of this attempt — routed like any envelope, never dropped
        a.last = self.now
        a.heard.add(leg)
        if t == "answer":
            # Never withheld, whatever the leg's state (spec-gap 86): only the initiator ends a leg that has
            # answered — bye already-answered / cancelled / failed (§12.7 rule 4, §12.5 rule 3, §12.4). The
            # record changes only for a leg that was still outstanding: a cancelled, expired or rejected leg
            # that answers stays recorded as such.
            if a.legs[leg] == "delivered":
                a.legs[leg] = "answered"
                if a.outcome is None:
                    a.outcome = "answered"
            self.emit({"forward": {"type": "answer", "from": leg}})
            return
        if a.legs[leg] in TERMINAL:
            # A stale progress or a second reject from a leg that is done would read, at an initiator that
            # cannot see legs, as the attempt's own; nobody needs it, so the relay screens it (spec-gap 86).
            self.emit({"drop": "leg-terminated"})
            return
        if t == "progress":
            self.emit({"forward": {"type": "progress", "status": m.get("status"), "from": leg}})
        elif t == "reject":
            a.legs[leg] = "rejected"
            a.reasons[leg] = m["reason"]
            self.check_complete(a)
        else:
            self.emit({"drop": "not-attempt-scoped"})

    def route_plain(self, m: dict) -> None:
        legs = self.legs_for(m.get("to", ""))
        if legs:
            for d in legs:
                self.emit({"deliver": {"leg": d, "type": m["type"], "id": m["id"]}})
        elif self.known(m.get("to", "")):
            self.enqueue(m)
        else:
            # spec-gap 82: §13.2 — a relay MUST NOT silently drop an envelope on a live connection. Traffic for a session
            # it holds no attempt for is routed like any envelope; with no route, the sender is told so.
            self.emit({"send": {"type": "error", "to": m["from"], "reason": "transport.unknown-recipient", "in_reply_to": m["id"]}})

    def check_complete(self, a: Attempt) -> None:
        """§12.7 rule 6: when the final outstanding leg terminates without an answer, forward the
        most informative reject as the attempt outcome."""
        if a.outcome is not None or any(st == "delivered" for st in a.legs.values()):
            return
        reasons = list(a.reasons.values())
        if not reasons:
            # spec-gap 76: no leg said anything — nothing to forward, and the relay may not invent a reject in a
            # leg's name (§15.2): it speaks for itself, in its own signed error
            a.outcome = "no-response"
            self.emit({"send": {"type": "error", "to": a.initiator, "session": a.session, "reason": "transport.no-response",
                                "in_reply_to": a.session}})
            return
        a.outcome = "rejected"
        best = next((r for r in REASON_RANK if r in reasons), reasons[0])
        src = next(leg for leg, r in a.reasons.items() if r == best)
        self.emit({"forward": {"type": "reject", "reason": best, "from": src}})

    def snapshot(self, ids) -> dict:
        return {i: self.attempts[i].snapshot() if i in self.attempts else None for i in ids}

    def inbox_snapshot(self) -> dict:
        return {k: len(v) for k, v in sorted(self.inbox.items()) if v}
