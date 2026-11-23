"""§12 session state engine — Python reference for the state-trace vectors.

One `Endpoint` holds any number of sessions (initiator or responder role),
a mock clock, and the §12.9 timers. Events and emissions follow the
vocabulary in vectors/README.md ("Kind: state").

Every `Impl:` comment marks a choice the spec leaves open; each has an entry
in impl/docs/spec-gaps.md.
"""
from __future__ import annotations

import re

from dataclasses import dataclass, field
from typing import Any

from .registry import effective_progress_status, effective_answered_by, resolve_reason

# §12.9 defaults and bounds
T_ESTABLISH_DEFAULT, T_ESTABLISH_BOUNDS = 15, (5, 60)
T_RING_DEFAULT, T_RING_BOUNDS = 120, (30, 300)
T_QUEUE_CAP = 1800
T_RING_LOCAL_DEFAULT, T_RING_LOCAL_BOUNDS = 120, (30, 300)
T_PRESENCE_ROTATE_DEFAULT, T_PRESENCE_ROTATE_BOUNDS = 60, (0, 3600)  # P§8
MAX_CONSECUTIVE_REQUEUES = 3   # §12.10 RECOMMENDED
KNOWN_INFO_ABOUT = {"transport:webrtc", "media:dtmf"}  # registry dsip-info-about (§12.12, spec-gap 70)


def clamp(v: int, bounds: tuple[int, int]) -> int:
    return max(bounds[0], min(bounds[1], v))


@dataclass
class Timer:
    name: str
    session: str
    deadline: int
    seq: int


@dataclass
class Session:
    id: str
    role: str                        # initiator | responder
    state: str                       # §12.4 state names
    peer: str                        # DID we address session messages to
    invite_to: str | None = None     # initiator: identity/device the invite was addressed to
    invite_expires_at: int | None = None
    answered_device: str | None = None
    outstanding: dict | None = None  # {"id":…, "direction": "outbound"|"inbound"}
    update_expires_at: int | None = None  # §12.8 rule 7: the outstanding update's expires_at
    cancelled: bool = False          # initiator sent cancel (any reason)
    was_active: bool = False
    post_answer_seen: bool = False   # responder: initiator message observed after our answer
    queue_count: int = 0

    @property
    def renegotiating(self) -> bool:
        # §12.8 rule 2: RENEGOTIATING is the *sender's* sub-state while its update is outstanding
        return self.outstanding is not None and self.outstanding["direction"] == "outbound"

    def snapshot(self) -> dict:
        return {"role": self.role, "state": self.state, "renegotiating": self.renegotiating,
                "outstanding_update": dict(self.outstanding) if self.outstanding else None}


class Endpoint:
    """Spec: §12.4–§12.12, §14.4."""

    def __init__(self, ctx: dict):
        self.device: str = ctx["self"]["device"]
        self.identity: str = ctx["self"]["identity"]
        self.identities: dict[str, str] = dict(ctx.get("identities", {}))
        self.now: int = ctx.get("start", 0)
        t = ctx.get("timers", {}) or {}
        self.t_establish = clamp(t.get("t_establish", T_ESTABLISH_DEFAULT), T_ESTABLISH_BOUNDS)
        self.t_ring = clamp(t.get("t_ring", T_RING_DEFAULT), T_RING_BOUNDS)
        self.t_ring_local = clamp(t.get("t_ring_local", T_RING_LOCAL_DEFAULT), T_RING_LOCAL_BOUNDS)
        self.sessions: dict[str, Session] = {}
        self.timers: list[Timer] = []
        self._seq = 0
        self.out: list[dict] = []
        # §19.4 first contact (Phase 2): policy, allowlist, grants, pending introductions
        pol = ctx.get("policy", {}) or {}
        self.first_contact_required: bool = bool(pol.get("first_contact_required", False))
        self.allow: set[str] = set(pol.get("allow", []))
        self.grants_issued: dict[str, dict] = {}   # grant id → {"grantee", "scope", "valid_until"}
        self.grants_held: dict[str, dict] = {}     # grant id → {"by", "scope", "valid_until"}
        self.requests: dict[str, dict] = {}        # introduction id → {"from": identity, "token": …}
        self.pending_sent: dict[str, str] = {}     # introduction id → to identity
        self.tokens: dict[str, str] = {}           # contact token → grant id to issue on match
        self.seen_introductions: set[str] = set()
        # P§12.3, P§12.5: presence keys, only when the context turns them on
        pk = ctx.get("presence_keys")
        self.keys_on = pk is not None
        pk = pk or {}
        self.sealed: set[str] = set(pk.get("sealed", []))
        self.t_rotate = clamp(pk.get("t_rotate", T_PRESENCE_ROTATE_DEFAULT), T_PRESENCE_ROTATE_BOUNDS)
        self.grant_ids: list[str] = list(pk.get("grant_ids", []))
        self.epochs: dict[str, int] = ({"main": 0} | {sc: 0 for sc in self.sealed}) if self.keys_on else {}
        self.last_rotated: dict[str, int] = {}
        self.due: dict[str, int] = {}               # scope → when it rotates
        self.held_keys: dict[str, dict[str, set[int]]] = {}  # grantor identity → scope → epochs (P§12.4)

    def contacts_snapshot(self) -> dict:
        return {"allow": sorted(self.allow), "grants_issued": sorted(self.grants_issued),
                "grants_held": sorted(self.grants_held), "requests": sorted(self.requests),
                "pending_sent": sorted(self.pending_sent)}

    def presence_keys_snapshot(self) -> dict:
        return {"epochs": dict(self.epochs), "due": dict(self.due),
                "chains": {gid: list(g["chain"]) for gid, g in sorted(self.grants_issued.items()) if g["chain"]},
                "held": {by: [f"{sc}.{e}" for sc in sorted(scopes) for e in sorted(scopes[sc])]
                         for by, scopes in sorted(self.held_keys.items())}}

    def has_grant(self, identity: str) -> bool:
        """§19.4: a live grant (scope dsip.invite) issued to this identity. The invite's `grant` reference is a hint for
        finding it and never admits or refuses on its own (spec-gap 151)."""
        return any(g["grantee"] == identity and g["valid_until"] > self.now and "dsip.invite" in g["scope"]
                   for g in self.grants_issued.values())

    # ------------------------------------------------------------ helpers

    def identity_of(self, did: str) -> str:
        return self.identities.get(did, did)

    def emit(self, e: dict) -> None:
        self.out.append(e)

    def send(self, **fields) -> None:
        self.emit({"send": {k: v for k, v in fields.items() if v is not None}})

    def error(self, msg: dict, reason: str) -> None:
        self.send(type="error", to=msg["from"], session=msg.get("session"), reason=reason, in_reply_to=msg["id"])

    def running(self, s: Session, name: str) -> Timer | None:
        for t in self.timers:
            if t.session == s.id and t.name == name:
                return t
        return None

    def start_timer(self, s: Session, name: str, seconds: int) -> None:
        self.stop_timer(s, name, silent=True)
        self._seq += 1
        self.timers.append(Timer(name, s.id, self.now + seconds, self._seq))
        self.emit({"timer": "start", "name": name, "seconds": seconds})

    def stop_timer(self, s: Session, name: str, silent: bool = False) -> bool:
        t = self.running(s, name)
        if t is None:
            return False
        self.timers.remove(t)
        if not silent:
            self.emit({"timer": "stop", "name": name})
        return True

    def stop_all(self, s: Session) -> None:
        for name in ("T-Establish", "T-Ring", "T-Queue", "T-Ring-Local"):
            self.stop_timer(s, name)

    def end(self, s: Session, ui_reason: str | None, media_stop: bool = False) -> None:
        self.stop_all(s)
        s.outstanding = None  # §12.8 rule 6: bye wins; pending update discarded
        if media_stop:
            self.emit({"media": "stop"})
        s.state = "ENDED"
        if ui_reason is not None:
            self.emit({"ui": "ended", "reason": ui_reason})

    # ------------------------------------------------------------ driver

    def step(self, event: dict) -> list[dict]:
        self.out = []
        if "advance" in event:
            self.advance(event["advance"])
        elif "recv" in event:
            self.recv(event["recv"])
        elif "local" in event:
            self.local(event)
        else:
            raise ValueError(f"unknown event {event}")
        return self.out

    def advance(self, seconds: int) -> None:
        target = self.now + seconds
        while True:
            instants = [t.deadline for t in self.timers]
            instants += [g["valid_until"] for g in self.grants_issued.values() if g["keys"] and not g["ended"]]
            instants += list(self.due.values())
            instants += [s.update_expires_at for s in self.sessions.values() if s.outstanding is not None]
            instants = [t for t in instants if t <= target]
            if not instants:
                break
            self.now = max(self.now, min(instants))
            while True:  # the session timers due now, in deadline order, ties by start order
                due = [t for t in self.timers if t.deadline <= self.now]
                if not due:
                    break
                t = min(due, key=lambda t: (t.deadline, t.seq))
                self.timers.remove(t)
                self.fire(t)
            for sid in sorted(self.sessions):  # §12.8 rule 7: updates reaching their expires_at lapse, in session order
                s = self.sessions[sid]
                if s.outstanding is not None and s.update_expires_at <= self.now:
                    outbound = s.outstanding["direction"] == "outbound"
                    s.outstanding = None
                    # the sender treats it as rejected (rule 5: prior state); the receiver may no longer answer it
                    self.emit({"ui": "update_rejected", "reason": "session.expired"} if outbound else {"ui": "update_lapsed"})
            for gid in sorted(self.grants_issued):  # P§12.5: grants reaching their valid_until end, in id order
                g = self.grants_issued[gid]
                if g["keys"] and not g["ended"] and g["valid_until"] <= self.now:
                    self.end_grant(g)
            self.rotate_due()
        self.now = target

    def fire(self, t: Timer) -> None:
        s = self.sessions[t.session]
        self.emit({"timer": "fire", "name": t.name})
        if t.name in ("T-Establish", "T-Ring", "T-Queue") and s.state in ("INVITING", "PROCEEDING"):
            # Spec §12.9: on expiry, cancel with reason session.timeout
            self.stop_all(s)
            self.send(type="cancel", to=s.invite_to, session=s.id, reason="session.timeout")
            s.cancelled = True
            self.end(s, "session.timeout")
        elif t.name == "T-Ring-Local" and s.state == "ALERTING":
            # Spec §12.9: on expiry, reject with reason user.no-answer
            self.send(type="reject", to=s.peer, session=s.id, reason="user.no-answer")
            self.end(s, "user.no-answer")

    def key_scopes(self, scope: list, audience: str | None) -> list[str]:
        """P§12.3: the scopes a grant carries keys for: `main` and its audience, when it admits presence and either is
        sealed."""
        if not self.keys_on or "dsip.subscribe" not in scope:
            return []
        if "main" not in self.sealed and audience not in self.sealed:
            return []
        return ["main"] + ([audience] if audience is not None else [])

    def issue_grant(self, gid: str, grantee: str, scope: list, valid_until: int, introduction: str,
                    presence_audience: str | None = None, chain: list | None = None) -> None:
        """§19.4 outcome 1: a signed contact grant; the consent receipt (§19.3) in message form. P§6: it may name the
        presence audience it admits to; P§12.3: it carries the keys of its scopes at their current epochs."""
        keys = self.key_scopes(scope, presence_audience)
        for sc in keys:
            self.epochs.setdefault(sc, 0)
        self.grants_issued[gid] = {"grantee": grantee, "scope": list(scope), "valid_until": valid_until,
                                   "audience": presence_audience, "keys": keys, "chain": list(chain or []),
                                   "ended": False}
        self.send(type="grant", to=grantee, session=introduction, id=gid, scope=list(scope), valid_until=valid_until,
                  presence_audience=presence_audience,
                  presence_keys=[f"{sc}.{self.epochs[sc]}" for sc in keys] or None)

    def end_grant(self, g: dict, keep: list | tuple = ()) -> None:
        """P§12.5 (spec-gap 161): an ending grant makes the scopes it carried keys for due, except those in `keep`."""
        if g["ended"]:  # a grant ends once (advance ends it at its valid_until)
            return
        g["ended"] = True
        for sc in g["keys"]:
            if sc in keep or sc in self.due:
                continue
            last = self.last_rotated.get(sc)
            self.due[sc] = self.now if last is None or self.now >= last + self.t_rotate else last + self.t_rotate

    def rotate_due(self) -> None:
        """P§12.5: every scope due now rotates together, then the live grants carrying any of them are re-granted."""
        scopes = sorted((sc for sc, t in self.due.items() if t <= self.now), key=lambda sc: (sc != "main", sc))
        for sc in scopes:
            del self.due[sc]
            self.epochs[sc] += 1
            self.last_rotated[sc] = self.now
            self.emit({"keys": "rotated", "scope": sc, "epoch": self.epochs[sc]})
        self.regrant_carrying(set(scopes))

    def regrant_carrying(self, scopes: set) -> None:
        """P§12.5: a grant that follows each live grant carrying a key of `scopes`; the followed one heads its chain
        (spec-gap 159) and is not revoked."""
        if not scopes:
            return
        for gid in sorted(self.grants_issued):
            g = self.grants_issued[gid]
            if g["valid_until"] <= self.now or not scopes & set(g["keys"]):
                continue
            if not self.grant_ids:
                raise ValueError("context.presence_keys.grant_ids exhausted")
            del self.grants_issued[gid]
            self.issue_grant(self.grant_ids.pop(0), g["grantee"], g["scope"], g["valid_until"], gid, g["audience"],
                             [gid] + g["chain"])

    def held_grant_for(self, identity: str) -> str | None:
        for gid, g in sorted(self.grants_held.items()):
            if g["by"] == identity and g["valid_until"] > self.now and "dsip.invite" in g["scope"]:
                return gid
        return None

    # ------------------------------------------------------------ local events

    def local(self, ev: dict) -> None:
        kind = ev["local"]
        if kind == "place_call":
            sid = ev["session"]
            if sid in self.sessions:
                # spec-gap 90: a session id is used once (§12.9); a held session, live or ended, is never overwritten
                self.emit({"refused": "invalid-state"})
                return
            s = Session(sid, "initiator", "INVITING", peer=ev["to"], invite_to=ev["to"])
            self.sessions[sid] = s
            # §19.4: the grantee MAY reference a held grant in a future invite to aid stateless relays
            self.send(type="invite", to=ev["to"], session=sid, grant=self.held_grant_for(self.identity_of(ev["to"])))
            self.start_timer(s, "T-Establish", self.t_establish)  # §12.9: started on sending invite
            return
        if kind == "introduce":
            # §19.4: media-less, session-less request for permission to contact
            self.pending_sent[ev["id"]] = ev["to"]
            self.send(type="introduction", to=ev["to"], id=ev["id"], purpose=ev.get("purpose"),
                      contact_token=ev.get("contact_token"))
            return
        if kind == "grant":
            if ev["introduction"] not in self.requests:
                self.emit({"refused": "unknown-introduction"})
                return
            audience = ev.get("presence_audience")
            if audience is not None and not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", audience):
                # P§6: an audience is a token [a-z][a-z0-9-]*, at most 64 characters; nothing is sent, the request stays
                self.emit({"refused": "invalid-audience"})
                return
            req = self.requests.pop(ev["introduction"])
            self.issue_grant(ev["id"], req["from"], ev.get("scope", ["dsip.invite"]), ev["valid_until"], ev["introduction"],
                             audience)
            return
        if kind == "regrant":
            # §19.4 (spec-gap 150): a grant may follow a live grant we issued, without an introduction
            old = self.grants_issued.get(ev["grant"])
            if old is None or old["valid_until"] <= self.now:
                self.emit({"refused": "unknown-grant"})
                return
            audience = ev.get("presence_audience")
            if audience is not None and not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", audience):
                self.emit({"refused": "invalid-audience"})  # P§6, as for a grant; the old grant is kept
                return
            # P§7 (spec-gap 159): the followed grant and its rotation chain are revoked at the authority
            self.emit({"revoke": [ev["grant"]] + old["chain"]})
            del self.grants_issued[ev["grant"]]  # issuing the new grant withdraws the one it follows
            self.issue_grant(ev["id"], old["grantee"], ev.get("scope", ["dsip.invite"]), ev["valid_until"], ev["grant"],
                             audience)
            # P§12.5 (spec-gap 161): what the grantee keeps through the new grant is not rotated
            self.end_grant(old, keep=self.grants_issued[ev["id"]]["keys"])
            self.rotate_due()
            return
        if kind == "reject_introduction":
            req = self.requests.pop(ev["introduction"], None)
            if req is None:
                self.emit({"refused": "unknown-introduction"})
                return
            # §19.4 outcome 2: reject with session = introduction id; a policy choice, not an obligation
            # spec-gap 74: like a grant, the rejection is addressed to the introducing identity
            self.send(type="reject", to=req["from"], session=ev["introduction"], reason=ev.get("reason", "user.declined"))
            return
        if kind == "revoke":
            g = self.grants_issued.pop(ev["grant"], None)
            if g is None:
                self.emit({"refused": "unknown-grant"})
                return
            self.emit({"revoke": [ev["grant"]] + g["chain"]})  # P§7 (spec-gap 159): with its rotation chain
            self.end_grant(g)
            self.rotate_due()
            return
        if kind == "issue_token":
            self.tokens[ev["token"]] = ev["grant_id"]
            return
        s = self.sessions.get(ev["session"])
        if s is None:
            self.emit({"refused": "unknown-session"})
            return
        if kind == "cancel":
            if s.role == "initiator" and s.state in ("INVITING", "PROCEEDING"):
                self.stop_all(s)
                self.send(type="cancel", to=s.invite_to, session=s.id, reason="user.cancelled")
                s.cancelled = True
                s.state = "ENDED"
            else:
                self.emit({"refused": "invalid-state"})
        elif kind == "hangup":
            if s.state == "ACTIVE":
                # Impl: ENDING is collapsed into ENDED — local teardown is synchronous in this engine.
                self.stop_all(s)
                s.outstanding = None
                # B§8: the media layer ends a failed path with `media.failed`; default is user.hangup
                self.send(type="bye", to=s.peer, session=s.id, reason=ev.get("reason") or "user.hangup")
                self.emit({"media": "stop"})
                s.state = "ENDED"
            else:
                self.emit({"refused": "invalid-state"})
        elif kind == "alert":
            if s.role == "responder" and s.state == "OFFERED":
                if self.now >= s.invite_expires_at:
                    # Spec §12.4/§12.9: invite expired (from expires_at, spec-gap 141) before alerting began → session.expired
                    self.send(type="reject", to=s.peer, session=s.id, reason="session.expired")
                    self.end(s, None)
                    return
                rt = ev.get("ring_timeout")
                self.send(type="progress", to=s.peer, session=s.id, status="ringing", ring_timeout=rt)
                s.state = "ALERTING"
                # §12.9 T-Ring-Local SHOULD be ≤ the advertised ring_timeout
                self.start_timer(s, "T-Ring-Local", clamp(rt, T_RING_LOCAL_BOUNDS) if rt else self.t_ring_local)
            else:
                self.emit({"refused": "invalid-state"})
        elif kind == "auto_reject":
            if s.role == "responder" and s.state == "OFFERED":
                self.send(type="reject", to=s.peer, session=s.id, reason=ev["reason"])
                self.end(s, None)
            else:
                self.emit({"refused": "invalid-state"})
        elif kind == "accept":
            if s.role == "responder" and s.state == "ALERTING":
                self.stop_all(s)
                self.send(type="answer", to=s.peer, session=s.id, answered_by=ev.get("answered_by", "user"))
                s.state = "ACTIVE"
                s.was_active = True
                self.emit({"media": "start"})
            else:
                self.emit({"refused": "invalid-state"})
        elif kind == "decline":
            if s.role == "responder" and s.state == "ALERTING":
                self.stop_all(s)
                self.send(type="reject", to=s.peer, session=s.id, reason=ev.get("reason", "user.declined"))
                self.end(s, None)
            else:
                self.emit({"refused": "invalid-state"})
        elif kind == "update":
            if s.state != "ACTIVE":
                self.emit({"refused": "invalid-state"})
            elif s.outstanding is not None:
                self.emit({"refused": "update-pending"})  # §12.8 rule 2: one outstanding, both directions
            else:
                self.send(type="update", to=s.peer, session=s.id, id=ev["id"], answered_by=ev.get("answered_by"))
                s.outstanding = {"id": ev["id"], "direction": "outbound"}
                s.update_expires_at = self.now + ev.get("validity", 30)  # §12.9: the update's validity, 30 s by default
        elif kind in ("answer_update", "reject_update"):
            if (s.state == "ACTIVE" and s.outstanding is not None and s.outstanding["direction"] == "inbound"
                    and s.outstanding["id"] == ev["in_reply_to"]):
                if kind == "answer_update":
                    self.send(type="answer", to=s.peer, session=s.id, answered_by=ev.get("answered_by", "user"),
                              in_reply_to=ev["in_reply_to"])
                    self.emit({"media": "apply_update"})
                else:
                    self.send(type="reject", to=s.peer, session=s.id, reason=ev["reason"], in_reply_to=ev["in_reply_to"])
                s.outstanding = None
            else:
                self.emit({"refused": "no-pending-update"})
        elif kind == "info":
            if s.state == "ACTIVE":
                self.send(type="info", to=s.peer, session=s.id)
            else:
                self.emit({"refused": "invalid-state"})
        else:
            raise ValueError(f"unknown local event {kind}")

    # ------------------------------------------------------------ received messages

    def recv(self, m: dict) -> None:
        t = m["type"]
        if t == "invite":
            return self.recv_invite(m)
        if t == "error":
            s = self.sessions.get(m.get("session"))
            if (m.get("reason") == "transport.no-response" and s is not None and s.role == "initiator"
                    and s.state in ("INVITING", "PROCEEDING")):
                # §12.7 rule 6 (spec-gap 76): the relay's own error is the attempt outcome when every leg stayed
                # silent; no cancel follows — the relay has closed every leg
                self.end(s, "transport.no-response")
                return
            self.emit({"ui": "error", "reason": m.get("reason")})
            return
        if t == "introduction":
            return self.recv_introduction(m)
        if t == "grant":
            return self.recv_grant(m)
        if t == "presence":
            return self.recv_own_record(m)
        if t == "reject" and m.get("session") in self.pending_sent:
            # §19.4 outcome 2: rejection addressed to the introduction id
            self.pending_sent.pop(m["session"])
            self.emit({"ui": "introduction_rejected", "reason": resolve_reason(m["reason"], "reject").effective})
            return
        s = self.sessions.get(m.get("session"))
        if s is None:
            # Spec §12.2: unknown session reference
            self.error(m, "session.unknown-session")
            return
        if s.state == "ENDED":
            if t == "answer" and s.role == "initiator" and "in_reply_to" not in m:
                # Spec §12.5 rule 3 / §12.7 rule 4: late answers to a finished attempt
                if s.cancelled:
                    reason = "session.cancelled"
                elif s.was_active:
                    reason = "session.already-answered"
                else:
                    reason = "session.failed"  # Impl: answer after a terminal reject; no spec token fits
                self.send(type="bye", to=m["from"], session=s.id, reason=reason)
            else:
                self.emit({"drop": "ended-session"})
            return
        if s.role == "responder" and s.state == "ACTIVE" and t != "cancel":
            s.post_answer_seen = True
        handler = getattr(self, f"recv_{t}")
        handler(s, m)

    def recv_introduction(self, m: dict) -> None:
        if m["id"] in self.seen_introductions:
            self.emit({"drop": "duplicate-introduction"})
            return
        self.seen_introductions.add(m["id"])
        identity = self.identity_of(m["from"])
        token = m.get("contact_token")
        if token is not None and token in self.tokens:
            # §19.4: a valid out-of-band contact token MAY be auto-granted per recipient policy
            gid = self.tokens.pop(token)
            self.emit({"ui": "introduction_received", "from": identity, "token": True})
            self.issue_grant(gid, identity, ["dsip.invite"], self.now + 31_536_000, m["id"])
            return
        # §19.4 UX requirement: a distinct requests surface — never a ring, never call history
        self.requests[m["id"]] = {"from": identity, "device": m["from"]}
        self.emit({"ui": "introduction_received", "from": identity})

    def recv_grant(self, m: dict) -> None:
        intro = m.get("session")
        by = self.identity_of(m["from"])
        followed = self.grants_held.get(intro)
        if intro in self.pending_sent:
            self.pending_sent.pop(intro)
        elif followed is not None and followed["by"] == by and followed["valid_until"] > self.now:
            del self.grants_held[intro]  # §19.4 (spec-gap 150): it follows a live grant we hold from them, and replaces it
        else:
            self.emit({"drop": "unknown-introduction"})
            return
        self.grants_held[m["id"]] = {"by": by, "scope": list(m.get("scope", [])), "valid_until": m.get("valid_until", 0)}
        for kid in m.get("presence_keys", []):  # P§12.4: per scope, the keys of the two highest epochs
            sc, _, e = kid.rpartition(".")
            if not re.fullmatch(r"[0-9]+", e):
                continue
            epochs = self.held_keys.setdefault(by, {}).setdefault(sc, set())
            epochs.add(int(e))
            while len(epochs) > 2:
                epochs.remove(min(epochs))
        self.emit({"ui": "granted", "by": by})

    def recv_own_record(self, m: dict) -> None:
        """P§12.5: a record of our own identity from a sibling, seen through our own watch; a higher epoch is adopted and
        our live grants carrying that scope are re-granted. Anything else is ignored."""
        kid = m.get("kid")
        if not self.keys_on or m.get("subject") != self.identity or kid is None:
            return
        sc, _, e = kid.rpartition(".")
        if not re.fullmatch(r"[0-9]+", e) or int(e) <= self.epochs.get(sc, -1):
            return
        self.epochs[sc] = int(e)
        self.emit({"keys": "seen", "scope": sc, "epoch": int(e)})
        self.regrant_carrying({sc})

    def recv_invite(self, m: dict) -> None:
        sid = m["id"]
        from_identity = self.identity_of(m["from"])
        if self.first_contact_required and from_identity not in self.allow and not self.has_grant(from_identity):
            # §19.4: an invite from an identity holding no grant (and matching no allow policy) is rejected
            # with policy.first-contact-required — the rejection that points the sender at the mechanism.
            # §12.4 responder: "Policy: auto-reject → send reject → ENDED" (no alerting, no missed call).
            self.send(type="reject", to=m["from"], session=sid, reason="policy.first-contact-required")
            self.sessions[sid] = Session(sid, "responder", "ENDED", peer=m["from"])
            return
        # §12.6 glare: an outbound invite to the identity this invite comes from
        from_identity = self.identity_of(m["from"])
        # Every live attempt of ours to that identity is a rival; the smallest id of all the invites wins.
        rivals = sorted((s for s in self.sessions.values()
                         if s.role == "initiator" and s.state in ("INVITING", "PROCEEDING")
                         and self.identity_of(s.invite_to) == from_identity), key=lambda s: s.id)
        if not rivals and sid in self.sessions:
            if self.sessions[sid].state == "ENDED":
                self.emit({"drop": "ended-session"})
            else:
                self.error({"from": m["from"], "id": sid, "session": sid}, "session.invalid-state")
            return
        if rivals:
            if rivals[0].id < sid:
                # We win: reject the inbound losing invite; proceed as initiator.
                self.send(type="reject", to=m["from"], session=sid, reason="session.glare")
                self.sessions[sid] = Session(sid, "responder", "ENDED", peer=m["from"])
                return
            # We lose (or pathological equal id): each of our invites lost, so each is withdrawn, in id order.
            # Impl (spec-gap 2): the loser withdraws via `cancel session.glare` (cancel is the
            # initiator's withdrawal message; §15.4 lists session.glare as valid on cancel).
            for glare in rivals:
                self.stop_all(glare)
                self.send(type="cancel", to=glare.invite_to, session=glare.id, reason="session.glare")
                glare.cancelled = True
                glare.state = "ENDED"
                self.emit({"ui": "ended", "reason": "session.glare"})
            if rivals[0].id == sid:
                # §12.6: equal ids — both invites rejected; MAY retry after 1–4 s.
                # The id collides with our own session record, which stays as the initiator's ENDED entry.
                self.send(type="reject", to=m["from"], session=sid, reason="session.glare")
                self.emit({"ui": "glare_retry"})
                return
            # fall through: proceed as responder for the winning invite
        s = Session(sid, "responder", "OFFERED", peer=m["from"], invite_to=m.get("to"),
                    invite_expires_at=m.get("expires_at"))
        self.sessions[sid] = s
        self.emit({"ui": "offered"})

    def recv_progress(self, s: Session, m: dict) -> None:
        if s.role != "initiator" or s.state not in ("INVITING", "PROCEEDING"):
            return self.error(m, "session.invalid-state")
        status = effective_progress_status(m["status"])
        self.stop_timer(s, "T-Establish")  # §12.9: stopped by first progress
        s.state = "PROCEEDING"
        self.emit({"ui": "progress", "status": status})
        if status == "ringing":
            s.queue_count = 0
            self.stop_timer(s, "T-Queue")  # §12.10: subsequent ringing cancels T-Queue
            rt = m.get("ring_timeout")
            if rt is not None:
                # §12.9: responder MAY extend via ring_timeout; honored up to the upper bound.
                # Impl (spec-gap 4): a ringing progress carrying ring_timeout (re)starts T-Ring.
                self.start_timer(s, "T-Ring", clamp(rt, T_RING_BOUNDS))
            elif self.running(s, "T-Ring") is None:
                self.start_timer(s, "T-Ring", self.t_ring)
        elif status == "queued":
            s.queue_count += 1
            if s.queue_count > MAX_CONSECUTIVE_REQUEUES:
                # Impl (spec-gap 11): exceeding the re-queue limit is treated as T-Queue expiry.
                self.stop_all(s)
                self.send(type="cancel", to=s.invite_to, session=s.id, reason="session.timeout")
                s.cancelled = True
                self.end(s, "session.timeout")
                return
            self.stop_timer(s, "T-Ring")  # §12.10: queued suspends T-Ring
            self.start_timer(s, "T-Queue", min(m["queue_timeout"], T_QUEUE_CAP))
        else:
            # Impl (spec-gap 4): trying/forwarded stop T-Establish but start no timer in the
            # spec text; T-Ring is started as the backstop so PROCEEDING is always bounded.
            if self.running(s, "T-Ring") is None and self.running(s, "T-Queue") is None:
                self.start_timer(s, "T-Ring", self.t_ring)

    def recv_answer(self, s: Session, m: dict) -> None:
        if s.role != "initiator" and not (s.state == "ACTIVE" and "in_reply_to" in m):
            # Responders only ever receive answers to their own updates (§12.8 rule 1)
            return self.error(m, "session.invalid-state")
        if s.state in ("INVITING", "PROCEEDING"):
            if "in_reply_to" in m:
                return self.error(m, "session.invalid-state")
            # §12.7 rule 2: first accepted answer establishes the session
            self.stop_all(s)
            s.state = "ACTIVE"
            s.was_active = True
            s.answered_device = m["from"]
            s.peer = m["from"]
            self.emit({"media": "start"})
            self.emit({"ui": "answered", "answered_by": effective_answered_by(m["answered_by"])})
            if m["from"] != s.invite_to:
                # §12.4/§12.7 rule 3: forked delivery → withdraw the other legs.
                # Impl (spec-gap 5): "forked" is inferred from the answer arriving from a device
                # other than the addressed identity/device.
                self.send(type="cancel", to=s.invite_to, session=s.id, reason="session.answered-elsewhere")
            return
        if s.state == "ACTIVE":
            if "in_reply_to" in m:
                if s.outstanding and s.outstanding["direction"] == "outbound" and s.outstanding["id"] == m["in_reply_to"]:
                    s.outstanding = None
                    self.emit({"media": "apply_update"})
                else:
                    self.emit({"drop": "stale-update-reply"})
                return
            if m["from"] != s.answered_device:
                # §12.7 rule 4: later answer from another leg
                self.send(type="bye", to=m["from"], session=s.id, reason="session.already-answered")
            else:
                self.error(m, "session.invalid-state")
            return
        self.error(m, "session.invalid-state")

    def recv_reject(self, s: Session, m: dict) -> None:
        reason = resolve_reason(m["reason"], "reject").effective
        if s.role == "initiator" and s.state in ("INVITING", "PROCEEDING") and "in_reply_to" not in m:
            self.end(s, reason)
            return
        if s.state == "ACTIVE" and "in_reply_to" in m:
            if s.outstanding and s.outstanding["direction"] == "outbound" and s.outstanding["id"] == m["in_reply_to"]:
                # §12.8 rule 5: rejected update leaves the session in its prior state
                s.outstanding = None
                self.emit({"ui": "update_rejected", "reason": reason})
            else:
                self.emit({"drop": "stale-update-reply"})
            return
        self.error(m, "session.invalid-state")

    def recv_cancel(self, s: Session, m: dict) -> None:
        reason = resolve_reason(m["reason"], "cancel").effective
        if s.role != "responder":
            return self.error(m, "session.invalid-state")
        if s.state == "OFFERED":
            self.end(s, reason)
        elif s.state == "ALERTING":
            self.stop_all(s)
            if reason != "session.answered-elsewhere":
                # §12.4/§12.11: answered-elsewhere MUST NOT surface as a missed call
                self.emit({"ui": "missed_call"})
            self.end(s, reason)
        elif s.state == "ACTIVE":
            if reason != "session.answered-elsewhere" and not s.post_answer_seen:
                # §12.5 rule 2: crossed cancel — our answer was in flight; tear down, no error.
                # Impl (spec-gap 1): "crossed" = no initiator message observed since our answer, and the
                # reason is a withdrawal of intent. `session.answered-elsewhere` can only be meant for
                # non-answered legs (§12.7 rule 3); at the leg that answered it is misrouted, never crossed.
                self.end(s, reason, media_stop=True)
            else:
                # §12.4/§12.11: cancel for an ACTIVE session
                self.error(m, "session.invalid-state")
        else:
            self.error(m, "session.invalid-state")

    def recv_update(self, s: Session, m: dict) -> None:
        if s.state != "ACTIVE":
            return self.error(m, "session.invalid-state")
        if s.outstanding is not None:
            if s.outstanding["direction"] == "outbound":
                # §12.8 rule 3: update glare → smaller id proceeds
                if s.outstanding["id"] < m["id"]:
                    self.send(type="reject", to=m["from"], session=s.id, reason="session.glare", in_reply_to=m["id"])
                    return
                self.emit({"ui": "update_rejected", "reason": "session.glare"})
                s.outstanding = None
            else:
                # §12.8 rule 4: second update from the same sender while its first is outstanding.
                # Impl (spec-gap 3): "processes neither" → both the pending and the new update are discarded.
                s.outstanding = None
                self.error(m, "session.update-pending")
                return
        s.outstanding = {"id": m["id"], "direction": "inbound"}
        s.update_expires_at = m.get("expires_at", self.now + 30)  # the trace's default: 30 s from its receipt
        self.emit({"ui": "update_offered"})
        if "answered_by" in m:
            # §14.4 step 3: escalation signal (e.g. screening → user)
            self.emit({"ui": "answered", "answered_by": effective_answered_by(m["answered_by"])})

    def recv_info(self, s: Session, m: dict) -> None:
        if s.state != "ACTIVE":
            return self.error(m, "session.invalid-state")  # §12.12: ACTIVE-only
        if m.get("about") not in KNOWN_INFO_ABOUT:
            self.emit({"drop": "unknown-about"})           # §12.12: never critical
            return
        self.emit({"info": {"about": m["about"]}})

    def recv_bye(self, s: Session, m: dict) -> None:
        if s.state != "ACTIVE":
            return self.error(m, "session.invalid-state")
        self.end(s, resolve_reason(m["reason"], "bye").effective, media_stop=True)

    def recv_hello(self, s: Session, m: dict) -> None:  # pragma: no cover — transport scope
        self.error(m, "session.invalid-state")

    def snapshot(self, ids) -> dict:
        return {i: self.sessions[i].snapshot() if i in self.sessions else None for i in ids}
