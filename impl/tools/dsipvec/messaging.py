"""Messaging Profile 1.0 reference semantics (v0.8 draft, cited M§n).

Spec: `v1.0/dsip-messaging-profile-v1.0.md`. Written before any Rust implementation; the
`messaging/` vectors pin this module's choices and `dsip-messaging` mirrors it.

Checks (`input.check`):
- `payload`  JSON Schema shape of a profile message or object (M§5, M§8).
- `message`  schema + stateless semantic rules for a profile message payload (M§5).
- `object`   schema + stateless rules for a decrypted content object (M§8, M§10, M§11, M§12).
- `hub-trace`, `mailbox-trace`  scripted state traces of the hub (M§6.5–M§6.8, M§7.3, M§9.3,
  M§11.2) and the mailbox (M§4.4, M§5.4–M§5.7, M§6.6, M§12.2, M§14.2).
- `resume-trace`  what a device holds durably across a restart: ack cursor and seq positions (M§5.4,
  M§8.5, spec-gap 44).

MLS itself is abstracted: traces carry what a hub or mailbox can observe (epoch, commit adds and
removes, validity, digests), exactly as relay traces abstract signatures.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

from . import ulid as U

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "v1.0" / "dsip-messaging-schemas-draft" / "schemas"

MAX_MLS_BYTES = 24576          # M§5.1
MAX_LIFETIME_S = 60            # M§5.1: delivery envelopes, not records
EPHEMERAL_LIFETIME_S = 10      # M§11.2
ULID_TOLERANCE_S = 300         # M§8.1 (§20.6 applied to content)
REACTION_MAX_BYTES = 32        # M§8.2
KEY_PACKAGES_PER_DEVICE = 100  # M§5.5 RECOMMENDED bound
ORIGIN_SKEW_S = 300            # M§14.2 (spec-gap 118): origin issued_at no later than the hub deposit's + 300 s …
                               # … and no older than pending_group_ttl before it (the hub re-signs each retry; a welcome
                               # re-sent after an outage carries the same origin)
HANDOVER_WAIT_S = 300          # M§7.4 (spec-gap 71): how long a mailbox holds a new hub off for the old hub's last items

MESSAGE_SCHEMAS = ["deposit", "accepted", "sync", "items", "key-packages", "key-package-fetch", "blob-put",
                   "mailbox-config"]
OBJECT_SCHEMAS = ["content", "receipt", "activity", "archive-key", "call-event", "archive-record", "recording-acceptance",
                  "call-record"]
MESSAGING_PROFILE = "messaging/1.0"

# Registries (M§17). Membership is checked here; the schemas only check token shape.
DEPOSIT_CLASSES = {"handshake", "application", "welcome", "group-info", "ephemeral", "archive", "introduction", "grant"}
FIRST_CONTACT_CLASSES = ("introduction", "grant")  # M§14.1 (spec-gap 54): carry a signed core envelope, no group
CONTENT_KINDS = {"text", "audio", "video", "image", "file", "contact", "location",
                 "device-event", "alarm-ack"}  # v0.9: the Device Events Profile's objects (E§5)
CONTENT_PURPOSES = {"message", "voice-message", "video-message", "voicemail", "attachment", "reaction",
                    "callback-request"}
RECEIPT_KINDS = {"delivered", "read", "played"}
ACTIVITIES = {"typing", "recording-audio", "recording-video", "uploading"}
MAILBOX_MODES = {"sync", "queue"}
CONVERSATION_KINDS = {"personal", "direct", "group"}
MESSAGE_GRANT_SCOPES = {"dsip.message", "dsip.invite"}  # M§14.2 condition 2

# M§5.2 class table: required and permitted class-specific fields.
_DEPOSIT_BASE = {"dsip", "type", "id", "from", "to", "issued_at", "expires_at", "group", "class", "recipient"}
DEPOSIT_REQUIRED = {
    "handshake": {"mls"},
    "application": {"mls"},
    "welcome": {"mls", "hub"},
    "group-info": {"mls"},
    "ephemeral": {"sealed"},
    "archive": {"archive", "akid", "ref_group", "ref_seq"},
    "introduction": {"envelope"},
    "grant": {"envelope"},
}
DEPOSIT_ALLOWED = {
    "handshake": {"mls", "seq", "welcome", "group_info", "ratchet_tree_blob", "grants"},
    "application": {"mls", "seq", "blobs"},
    # `seq`: the adding commit's, so the new member knows where it starts counting the group (spec-gap 83)
    "welcome": {"mls", "hub", "grants", "origin", "successor_of", "ratchet_tree_blob", "seq"},
    "group-info": {"mls", "ratchet_tree_blob", "handover_seq"},
    "ephemeral": {"sealed"},
    "archive": {"archive", "akid", "ref_group", "ref_seq"},
    "introduction": {"envelope"},
    "grant": {"envelope"},
}
INTRODUCTION_MAX_BYTES = 4096   # §19.4
SIZED_FIELDS = ("mls", "welcome", "group_info", "sealed", "archive")


def accept(**extra) -> dict:
    out = {"verdict": "accept"}
    out.update(extra)
    return out


def reject(code: str, reason: str | None = None) -> dict:
    out = {"verdict": "reject", "code": code}
    if reason:
        out["reason"] = reason
    return out


@lru_cache(maxsize=None)
def validator(name: str) -> Draft202012Validator:
    from .schema import Validator
    return Validator(json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text()))


def has_float(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, float):
        return True
    if isinstance(v, dict):
        return any(has_float(x) for x in v.values())
    if isinstance(v, list):
        return any(has_float(x) for x in v)
    return False


def decoded_len(b64: str) -> int:
    """Decoded length of unpadded base64url, from its length alone (alphabet is a schema check)."""
    return len(b64) * 3 // 4


def schema_ok(name: str, value) -> bool:
    return not any(True for _ in validator(name).iter_errors(value))


# ---------------------------------------------------------------- messages (M§5)

def check_message(p: dict) -> dict:
    t = p.get("type") if isinstance(p, dict) else None
    if t not in MESSAGE_SCHEMAS:
        return reject("unknown-type")
    if not schema_ok(t, p):
        return reject("schema-invalid")
    if p["expires_at"] - p["issued_at"] > MAX_LIFETIME_S:  # M§5.1
        return reject("lifetime-exceeded")
    if t == "deposit":
        return check_deposit(p)
    if t == "mailbox-config" and "mode" in p and p["mode"] not in MAILBOX_MODES:  # M§4.4, M§16
        return reject("mailbox-mode-unsupported", "mailbox.unsupported-mode")
    if t == "key-packages" and not p.get("key_packages") and "last_resort" not in p:  # M§5.5
        return reject("key-packages-empty")
    return accept()


def check_deposit(p: dict) -> dict:
    cls = p["class"]
    if cls not in DEPOSIT_CLASSES:  # M§5.2: class is structural, unknown is refused
        return reject("deposit-class-unsupported", "mailbox.unsupported-class")
    if cls == "ephemeral" and p["expires_at"] - p["issued_at"] > EPHEMERAL_LIFETIME_S:  # M§11.2
        return reject("lifetime-exceeded")
    present = set(p) - _DEPOSIT_BASE
    if not DEPOSIT_REQUIRED[cls] <= set(p) or not present <= DEPOSIT_ALLOWED[cls]:
        return reject("deposit-fields")
    if (cls in FIRST_CONTACT_CLASSES) != ("group" not in p) or (cls in FIRST_CONTACT_CLASSES and "recipient" not in p):
        return reject("deposit-fields")  # spec-gap 54: first-contact deposits name a recipient and no group
    if cls == "introduction" and len(p["envelope"]) > INTRODUCTION_MAX_BYTES:  # §19.4 on the compact envelope
        return reject("introduction-too-large", "transport.envelope-too-large")
    for f in SIZED_FIELDS:  # M§5.1
        if f in p and decoded_len(p[f]) > MAX_MLS_BYTES:
            return reject("object-too-large", "mailbox.object-too-large")
    return accept()


# ---------------------------------------------------------------- objects (M§8, M§10–M§13)

def check_object(o: dict, ctx: dict) -> dict:
    if has_float(o):  # §10.3 applies to MLS plaintext too (M§8.1)
        return reject("payload-float")
    name = o.get("object") if isinstance(o, dict) else None
    if name not in OBJECT_SCHEMAS:
        return accept(effective={"render": "ignore"})  # M§8.1: unknown object ignored
    if not schema_ok(name, o):
        return reject("schema-invalid")
    if name in ("content", "receipt", "activity"):
        if o["sender"] != ctx.get("leaf_identity"):  # M§8.1: sender = MLS leaf identity
            return reject("sender-mismatch")
        # spec-gap 52: an undisclosed read watermark travels in the personal group (M§10.5) and names the
        # conversation it describes, not the personal group's own
        private_read = name == "receipt" and o.get("kind") == "read" and ctx.get("conversation_kind") == "personal"
        if o["conversation"] != ctx.get("conversation") and not private_read:
            return reject("conversation-mismatch")
    if name in ("content", "receipt"):
        if abs(U.timestamp_ms(o["id"]) // 1000 - o["sent_at"]) > ULID_TOLERANCE_S:
            return reject("ulid-sent-at-mismatch")
    if name in ("archive-key", "call-event", "recording-acceptance") and ctx.get("conversation_kind") != "personal":  # M§12.1, M§13.3, C§5
        return reject("personal-group-only")
    if name == "call-record":
        return check_call_record(o, ctx)
    if name == "content":
        return check_content(o, ctx)
    if name == "receipt":
        if o["kind"] not in RECEIPT_KINDS:
            return accept(effective={"render": "ignore"})
        if o["kind"] == "read":
            ok = "through" in o and "targets" not in o
        else:
            ok = "targets" in o and "through" not in o
        return accept(effective={"receipt": o["kind"]}) if ok else reject("receipt-shape")
    if name == "activity":
        return accept(effective={"activity": o["activity"] if o["activity"] in ACTIVITIES else "active"})
    return accept()


def check_call_record(o: dict, ctx: dict) -> dict:
    """Recording Profile C§9 (v0.13, spec-gap 121): a leg's record at the record-keeper."""
    if o["device"] != ctx.get("leaf_device"):  # the sender leaf's own device
        return reject("sender-mismatch")
    if ctx.get("conversation_kind") != "direct":  # the record-keeper's direct conversation only
        return reject("recorder-conversation-only")
    answered = o["outcome"] == "answered"
    times = [o["invited_at"]] + ([o["answered_at"]] if "answered_at" in o else []) + [o["ended_at"]]
    if ("answered_at" in o) != answered or times != sorted(times):
        return reject("call-record-invalid")
    return accept(effective={"render": "ignore", "store": "call-record"})


_KIND_BODY = {
    "text": ("text",),
    "audio": ("blob", "duration_ms"),
    "video": ("blob", "duration_ms"),
    "image": ("blob",),
    "file": ("blob", "name"),
    "contact": ("did",),
    "location": ("lat_e7", "lon_e7"),
    "device-event": ("event",),         # E§5
    "alarm-ack": ("alarm", "state"),    # E§5
}


def _str(v, nonempty=False) -> bool:
    return isinstance(v, str) and (bool(v) or not nonempty)


def _opt_str(o: dict, f: str) -> bool:
    return f not in o or isinstance(o[f], str)


def _device_event_body(e) -> bool:
    """E§5 Bodies (spec-gap 166): required members and types only; unknown members and tokens are not checked."""
    if not isinstance(e, dict):
        return False
    if "heartbeat" in e:
        h = e["heartbeat"]
        if not (isinstance(h, dict) and type(h.get("interval_s")) is int and h["interval_s"] >= 1):
            return False
    if "source" in e or "heartbeat" not in e:
        src = e.get("source")
        if not (isinstance(src, dict) and _str(src.get("address"), True) and _str(src.get("basis"))):
            return False
    if "alarm" in e:
        a = e["alarm"]
        if not (isinstance(a, dict) and _str(a.get("resource")) and _str(a.get("type"), True)
                and (a.get("severity", 0) is None or _str(a.get("severity"))) and type(a.get("cleared")) is bool
                and _opt_str(a, "qualifier") and _opt_str(a, "text")):
            return False
    return all(f not in e or isinstance(e[f], dict) for f in ("raw", "syslog_gap"))


def _alarm_ack_body(o: dict) -> bool:
    a = o["alarm"]
    return (isinstance(a, dict) and _str(a.get("resource")) and _str(a.get("type"), True) and _opt_str(a, "qualifier")
            and _str(o["state"]))


def check_content(o: dict, ctx: dict) -> dict:
    kind, purpose = o["kind"], o["purpose"]
    if kind in CONTENT_KINDS:
        if not all(f in o for f in _KIND_BODY[kind]):
            return reject("content-body")
        if kind == "device-event" and not _device_event_body(o["event"]) or kind == "alarm-ack" and not _alarm_ack_body(o):
            return reject("content-body")
        # spec-gap 165: only a gateway, delegated with dsip.events, raises alarms (E§2)
        if kind == "device-event" and "dsip.events" not in (ctx.get("leaf_capabilities") or []):
            return reject("delegation-capability")
        eff_kind = kind
    else:  # M§8.2 fallback
        eff_kind = "file" if "blob" in o else "unsupported"
    if purpose == "reaction":
        if kind != "text" or not o.get("reply_to") or len(o.get("text", "").encode("utf-8")) > REACTION_MAX_BYTES:
            return reject("reaction-invalid")
    if purpose == "voicemail" and (kind not in ("audio", "video") or "session" not in o):  # M§13.2
        return reject("content-body")
    eff_purpose = purpose if purpose in CONTENT_PURPOSES else "message"
    return accept(effective={"kind": eff_kind, "purpose": eff_purpose})


def check_conversation_update(before: dict, after: dict) -> dict:
    """M§6.3, M§7.4 (spec-gap 60): a GroupContextExtensions commit may change only the hub; `moves_to` names a new hub DID."""
    if not schema_ok("dsip-conversation", before) or not schema_ok("dsip-conversation", after):
        return reject("schema-invalid")
    if any(before.get(k) != after.get(k) for k in ("conversation", "kind", "successor_of")):
        return reject("conversation-immutable")
    moved = before["hub"]["did"] != after["hub"]["did"]
    return accept(effective={"moves_to": after["hub"]["did"] if moved else None, "hub": after["hub"]})


def check_conversation_ext(ext: dict) -> dict:
    if not schema_ok("dsip-conversation", ext):
        return reject("schema-invalid")
    return accept(effective={"kind": ext["kind"] if ext["kind"] in CONVERSATION_KINDS else "group"})


# ---------------------------------------------------------------- hub (M§6.5–M§6.8, M§7.3)

def leave_proposals(inp: dict) -> dict:
    """M§7.3 "Leaving" (spec-gap 125): a member's device and an identity's pending Remove proposals."""
    if inp["others"] > 0:
        return {"action": "ignore", "reason": "not-a-leave"}
    who = inp["proposer"]["identity"]
    leaves = {r["device"] for r in inp["roster"] if r["identity"] == who}
    removed = set()
    for r in inp["removes"]:
        if r["identity"] != who or r["device"] not in leaves:
            return {"action": "ignore", "reason": "not-own-leaves"}
        removed.add(r["device"])
    if removed != leaves:
        return {"action": "wait"}
    if who == inp["me"]:
        return {"action": "left"}
    return {"action": "commit"}


def check_roster_change(inp: dict) -> dict:
    """M§7.3 (spec-gap 126): the roster rules a member checks on a commit, the hub's being defense in depth.

    Another member identity's devices are added only by that identity; another identity's leaves are removed all
    together, or each because its delegation no longer verifies (M§6.2). The committer's own identity is free.
    """
    me = inp["committer"]
    members = {r["identity"] for r in inp["roster"]}
    if any(a["identity"] in members and a["identity"] != me for a in inp["adds"]):
        return reject("roster-adds-other-devices")
    by_ident: dict[str, list] = {}
    for r in inp["removes"]:
        by_ident.setdefault(r["identity"], []).append(r)
    for who, rs in by_ident.items():
        if who == me:
            continue
        leaves = {r["device"] for r in inp["roster"] if r["identity"] == who}
        whole = leaves <= {r["device"] for r in rs}
        lapsed = all(r.get("delegation_valid", True) is False for r in rs)
        if not (whole or lapsed):
            return reject("roster-removes-part-of-identity")
    return accept()


def check_external_join(inp: dict) -> dict:
    """M§6.8 (spec-gap 62): what an external commit may do, checked alike by the hub and by every member.

    The joiner is the identity and device of the commit's own (path) leaf. It must already be a member identity, or
    the group is its own personal group; the commit adds nothing but the joiner's device; it removes only leaves of
    the joiner's identity (the stale leaves it replaces).
    """
    j = inp["joiner"]
    if [(a["identity"], a["device"]) for a in inp.get("adds", [])] != [(j["identity"], j["device"])]:
        return reject("external-join-adds")
    if not (j["identity"] in inp["roster"] or (inp.get("kind") == "personal" and j["identity"] == inp.get("owner"))):
        return reject("external-join-not-member")
    if any(r["identity"] != j["identity"] for r in inp.get("removes", [])):
        return reject("external-join-removes-other")
    return accept()


class Hub:
    def __init__(self, ctx: dict):
        self.now = ctx["now"]
        self.kind = ctx.get("kind", "direct")
        self.owner = ctx.get("owner")
        self.epoch = ctx["epoch"]
        self.next_seq = ctx.get("next_seq", 1)
        self.roster = {i: set(d) for i, d in ctx["roster"].items()}
        self.digests: dict[str, int] = {}
        self.seq_class: dict[int, str] = {}
        self.pending: dict[str, list[int]] = {}
        self.group_info = False
        self.moved_to: str | None = None
        self.welcomes: dict[str, list[int]] = {}
        # Identities a commit brought in whose welcome is not yet acknowledged: their mailbox has no registration for
        # the group and would refuse a sequenced item (M§6.6), so their queue is held (spec-gap 66). A member that
        # gained a device is not among them (spec-gap 87).
        self.unregistered: set[str] = set()
        # spec-gap 119: per identity, when its queues last went from empty to not or saw a head acknowledged
        self.retention = ctx.get("mls_retention_s", MLS_RETENTION_S)
        self.waiting: dict[str, int] = {}

    def _queued(self, ident: str) -> bool:
        return bool(self.pending.get(ident)) or bool(self.welcomes.get(ident))

    def _start_clock(self, ident: str) -> None:
        if ident not in self.waiting:
            self.waiting[ident] = self.now

    def step(self, ev: dict) -> list:
        if "advance" in ev:
            self.now += ev["advance"]
            # spec-gap 119: a member that acknowledged nothing for mls_retention_s has its queues dropped
            out = []
            for i in sorted(i for i, t in self.waiting.items() if self.now - t >= self.retention):
                out.append({"dropped": {"identity": i, "pending": list(self.pending.pop(i, [])),
                                        "welcomes": list(self.welcomes.pop(i, []))}})
                self.unregistered.discard(i)
                del self.waiting[i]
            return out
        if "ack" in ev:
            return self._ack(ev["ack"]["identity"], ev["ack"]["seq"], ev["ack"].get("class", ""))
        if "restart" in ev:
            return self.restart()
        return self._deposit(ev["deposit"])

    @staticmethod
    def _error(d, reason):
        return [{"error": {"to": d["device"], "in_reply_to": d["id"], "reason": reason}}]

    def _deposit(self, d: dict) -> list:
        cls, ident = d["class"], d["identity"]
        if self.moved_to is not None and cls == "group-info" and "handover_seq" in d:
            return self._returned(d)
        if self.moved_to is not None:
            # M§7.4: after ordering the commit that moved the group, the old hub refuses further deposits for it
            return self._error(d, "mailbox.unknown-group")
        if cls not in ("handshake", "application", "ephemeral", "group-info"):
            return self._error(d, "mailbox.unsupported-class")
        if cls == "group-info":
            # M§6.5 rule 6 / M§6.8: the hub keeps the latest GroupInfo so a returning device can
            # external-join, and forwards it to the members' mailboxes. Never sequenced.
            if ident not in self.roster:
                return self._error(d, "policy.blocked")
            self.group_info = True
            return [{"accepted": {"to": d["device"], "in_reply_to": d["id"]}}] + [
                {"fanout": {"to": i, "class": "group-info"}} for i in sorted(self.roster)
            ]
        if cls == "ephemeral":  # M§11.2: never sequenced or stored; dropped once expired (from expires_at, spec-gap 141)
            if d["expires_at"] <= self.now:
                return []
            if ident not in self.roster:
                return self._error(d, "policy.blocked")
            return [{"forward": {"to": i, "class": "ephemeral"}} for i in sorted(self.roster) if i != ident]
        if d["digest"] in self.digests:  # M§9.3
            return [{"accepted": {"to": d["device"], "in_reply_to": d["id"], "seq": self.digests[d["digest"]],
                                  "duplicate": True}}]
        commit = d.get("commit")
        external = bool(commit and commit.get("external"))
        if external:  # M§6.8 (spec-gap 62)
            v = check_external_join({"kind": self.kind, "owner": self.owner, "roster": sorted(self.roster),
                                     "joiner": {"identity": ident, "device": d["device"]},
                                     "adds": commit.get("adds", []), "removes": commit.get("removes", [])})
            if v["verdict"] != "accept":
                return self._error(d, "policy.blocked")
        elif ident not in self.roster:  # M§6.5 rule 1
            return self._error(d, "policy.blocked")
        e = d["epoch"]
        if cls == "application":
            if e not in (self.epoch, self.epoch - 1):  # M§6.5 rule 3
                return self._error(d, "mailbox.stale-epoch")
            return self._sequence(d, sorted(self.roster))
        # handshake
        if e != self.epoch:  # M§6.5 rule 2
            return self._error(d, "mailbox.commit-conflict" if (commit and e == self.epoch - 1) else "mailbox.stale-epoch")
        if not commit:  # standalone proposal: sequenced, no epoch change
            return self._sequence(d, sorted(self.roster))
        if not commit.get("valid", True):
            return self._error(d, "policy.blocked")
        roster = [{"identity": i, "device": dev} for i, devs in self.roster.items() for dev in devs]
        if check_roster_change({"committer": ident, "roster": roster, "adds": commit.get("adds", []),
                                "removes": commit.get("removes", [])})["verdict"] != "accept":
            return self._error(d, "policy.blocked")  # M§7.3: the rule every member checks too (spec-gap 126)
        targets = sorted(self.roster)
        out = self._sequence(d, targets)
        before = {i: set(devs) for i, devs in self.roster.items()}
        for r in commit.get("removes", []):
            devs = self.roster.get(r["identity"])
            if devs is not None:
                devs.discard(r["device"])
                if not devs:
                    del self.roster[r["identity"]]
        for a in commit.get("adds", []):
            self.roster.setdefault(a["identity"], set()).add(a["device"])
        self.epoch += 1
        if commit.get("moves_to"):  # M§7.4: ordered and fanned out here; everything after goes to the new hub
            self.moved_to = commit["moves_to"]
        if not external:  # an external joiner joined by its own commit; welcomes go only to identities others added
            # spec-gap 50: to every identity that gained a device, including a member adding its own new device
            gained = {a["identity"] for a in commit.get("adds", []) if a["device"] not in before.get(a["identity"], set())}
            # spec-gap 87: only an identity the commit brought in has no registration to receive sequenced items with
            self.unregistered |= gained - set(before)
            seq = self.digests[d["digest"]]
            for i in sorted(gained):
                # spec-gap 66: a welcome is queued and retried like any other fan-out, so an identity whose mailbox is
                # down when it is added still learns of the group. Its own queue: a member adding its own device needs
                # both the commit (its other devices) and the welcome (the new one) for the same seq.
                self._start_clock(i)
                q = self.welcomes.setdefault(i, [])
                q.append(seq)
                if len(q) == 1:
                    out.append({"fanout": {"to": i, "seq": seq, "class": "welcome"}})
        return out

    def restart(self) -> list:
        """spec-gap 59: a hub restart keeps epoch, roster, sequence, digests and fan-out queues, and re-sends the head of
        every unacknowledged queue (M§6.5 rule 5: retry before later items)."""
        state = json.loads(json.dumps({
            "now": self.now, "kind": self.kind, "owner": self.owner, "epoch": self.epoch, "next_seq": self.next_seq,
            "roster": {i: sorted(d) for i, d in self.roster.items()}, "digests": self.digests,
            "seq_class": {str(k): v for k, v in self.seq_class.items()}, "pending": self.pending, "group_info": self.group_info,
            "moved_to": self.moved_to, "welcomes": self.welcomes, "unregistered": sorted(self.unregistered),
            "retention": self.retention, "waiting": self.waiting}))
        for k in ("now", "kind", "owner", "epoch", "next_seq", "digests", "pending", "group_info", "moved_to", "welcomes",
                  "retention", "waiting"):
            setattr(self, k, state[k])
        self.roster = {i: set(d) for i, d in state["roster"].items()}
        self.seq_class = {int(k): v for k, v in state["seq_class"].items()}
        self.unregistered = set(state["unregistered"])
        heads = [{"fanout": {"to": i, "seq": q[0], "class": self.seq_class[q[0]]}}
                 for i, q in sorted(self.pending.items()) if q and i not in self.unregistered]
        return heads + [{"fanout": {"to": i, "seq": q[0], "class": "welcome"}} for i, q in sorted(self.welcomes.items()) if q]

    def _returned(self, d: dict) -> list:
        """spec-gap 128: the group comes back to this hub, which it left. `view` is the epoch and roster of the GroupInfo
        the daemon read (it names this hub); numbering goes on from `handover_seq` + 1, never reusing a seq this hub gave
        (M§12.2), and what was ordered before the group left keeps draining."""
        view = d.get("view") or {}
        roster = {i: set(devs) for i, devs in (view.get("roster") or {}).items()}
        if d["identity"] not in roster:
            return self._error(d, "policy.blocked")
        if d["handover_seq"] < self.next_seq:
            return self._error(d, "policy.blocked")
        self.moved_to = None
        self.epoch = view["epoch"]
        self.roster = roster
        self.next_seq = d["handover_seq"] + 1
        self.group_info = True
        return [{"accepted": {"to": d["device"], "in_reply_to": d["id"]}}] + [
            {"fanout": {"to": i, "class": "group-info"}} for i in sorted(self.roster)
        ]

    def _sequence(self, d: dict, targets: list) -> list:
        seq = self.next_seq
        self.next_seq += 1
        self.digests[d["digest"]] = seq
        self.seq_class[seq] = d["class"]
        out = [{"accepted": {"to": d["device"], "in_reply_to": d["id"], "seq": seq}}]
        for i in targets:  # M§6.5 rule 5: per-mailbox seq order, retry before later items
            self._start_clock(i)
            q = self.pending.setdefault(i, [])
            q.append(seq)
            # spec-gap 66: nothing goes to a mailbox the commit brought in before it acknowledges its welcome — until then
            # it has no registration for the group and would refuse the item (M§6.6); a member that gained a device is
            # registered and gets the commit at once (spec-gap 87)
            if len(q) == 1 and i not in self.unregistered:
                out.append({"fanout": {"to": i, "seq": seq, "class": d["class"]}})
        return out

    def _ack(self, ident: str, seq: int, cls: str = "") -> list:
        q = self.welcomes.get(ident, []) if cls == "welcome" else self.pending.get(ident, [])
        if not q or q[0] != seq:
            return []
        q.pop(0)
        # spec-gap 119: progress restarts the clock; nothing left queued stops it
        if self._queued(ident):
            self.waiting[ident] = self.now
        else:
            self.waiting.pop(ident, None)
        if q and (cls == "welcome" or ident not in self.unregistered):
            # the hold behind an unacknowledged welcome applies here too: the queue moves, nothing is sent (spec-gap 87)
            return [{"fanout": {"to": ident, "seq": q[0], "class": cls or self.seq_class[q[0]]}}]
        if cls == "welcome" and ident in self.unregistered:
            # the group is registered now: whatever waited behind the welcome goes (a member that gained a device
            # waited for nothing: its head went out with the commit, spec-gap 87)
            self.unregistered.discard(ident)
            waiting = self.pending.get(ident, [])
            if waiting:
                return [{"fanout": {"to": ident, "seq": waiting[0], "class": self.seq_class[waiting[0]]}}]
        return []

    def snapshot(self) -> dict:
        return {"epoch": self.epoch, "next_seq": self.next_seq,
                "roster": {i: sorted(d) for i, d in sorted(self.roster.items())},
                "pending": {i: list(q) for i, q in sorted(self.pending.items()) if q},
                "group_info": self.group_info, "moved_to": self.moved_to,
                "welcomes": {i: list(q) for i, q in sorted(self.welcomes.items()) if q}}


# ---------------------------------------------------------------- mailbox (M§4.4, M§5, M§6.6, M§12.2, M§14.2)

def cursor(n: int) -> str:
    return f"c:{n:016x}"


def cursor_num(c) -> int | None:
    if not isinstance(c, str) or not c.startswith("c:") or len(c) != 18:
        return None
    try:
        return int(c[2:], 16)
    except ValueError:
        return None


class Mailbox:
    def __init__(self, ctx: dict):
        self.now = ctx["now"]
        self.owner = ctx["owner"]
        self.serves = set(ctx.get("serves", [self.owner]))
        self.devices = sorted(ctx["devices"])
        self.mode = ctx.get("mode", "sync")
        self.admit = ctx.get("admit", "grant")
        self.pending_ttl = ctx.get("pending_group_ttl", 604800)
        self.pending_max = ctx.get("pending_group_max_items", 500)
        # M§4.3 quota_bytes (spec-gap 99): None = unlimited; items carry the `size` their deposit declared
        self.quota = ctx.get("quota_bytes")
        self.handover_wait = ctx.get("handover_wait", HANDOVER_WAIT_S)
        self.groups = {g: {"hub": r["hub"], "state": r["state"], "since": self.now, "items": 0}
                       for g, r in ctx.get("groups", {}).items()}
        self.kp = {dv: {"one_time": k.get("one_time", 0), "last_resort": k.get("last_resort", False)}
                   for dv, k in ctx.get("key_packages", {}).items()}
        self.revoked: set[str] = set()
        self.items: list[dict] = []
        self.counter = 0
        self.acks: dict[str, int] = {}
        self.bound: set[str] = set()
        self.archived: dict[tuple, str] = {}
        self.intro_limit = ctx.get("intro_limit", 5)
        self.intro_window = ctx.get("intro_window", 3600)
        self.inbox_cap = ctx.get("inbox_cap", 16)
        self.intro_log: dict[str, list] = {}
        self.introductions_sent: list = []  # mailbox-config introductions_sent (spec-gap 81), durable

    # --- helpers
    @staticmethod
    def _error(to, eid, reason):
        return [{"error": {"to": to, "in_reply_to": eid, "reason": reason}}]

    def _grant_ok(self, grant, grantee: str, target: str) -> bool:
        return (isinstance(grant, dict) and grant.get("from") == target and grant.get("to") == grantee
                and bool(MESSAGE_GRANT_SCOPES & set(grant.get("scope", [])))
                and grant.get("valid_until", 0) > self.now and grant.get("id") not in self.revoked)

    def _used(self) -> int:
        return sum(it.get("size", 0) for it in self.items)

    def _over_quota(self, e: dict) -> bool:
        """spec-gap 99: would storing this deposit's `size` take the owner past quota_bytes?"""
        return self.quota is not None and self._used() + e.get("size", 0) > self.quota

    def _store(self, cls: str, group: str, **extra) -> tuple[str, list]:
        if cls == "group-info":  # M§5.2: latest per group only
            self.items = [it for it in self.items if not (it["group"] == group and it["class"] == "group-info")]
        self.counter += 1
        c = cursor(self.counter)
        self.items.append({"cursor": c, "n": self.counter, "class": cls, "group": group, **extra})
        return c, [{"push": {"to": dv, "cursor": c}} for dv in sorted(self.bound) if dv != extra.get("depositor")]

    # --- events
    def step(self, ev: dict) -> list:
        (name, e), = ev.items()
        return getattr(self, "_" + name.replace("-", "_"))(e)

    def _first_contact(self, e: dict) -> list:
        """M§14.1 (spec-gap 54): an introduction or grant deposited for an identity, under §19.4's relay rules."""
        keys = ["sender:" + e["sender_identity"], "inbox:" + e["recipient"]]
        if e["kind"] == "grant" and e.get("session") in self.introductions_sent:
            # M§14.1 (spec-gap 81): a grant answering an introduction the owner sent is the reply it asked for — not
            # metered, and the entry is consumed: one introduction, one answer. Any other grant is an unsolicited write
            # into the mailbox and takes the introduction budget below.
            self.introductions_sent.remove(e["session"])
            keys = []
        for k in keys:  # §19.4: rate-limited per sender identity and per recipient inbox
            log = [t for t in self.intro_log.get(k, []) if t > self.now - self.intro_window]
            self.intro_log[k] = log
            if len(log) >= self.intro_limit:
                return [{"error": {"to": e["from"], "in_reply_to": e["id"], "reason": "policy.rate-limited",
                                   "retry_after": log[0] + self.intro_window - self.now}}]
        for k in keys:
            self.intro_log[k].append(self.now)
        accepted = [{"accepted": {"to": e["from"], "in_reply_to": e["id"]}}]
        if e["recipient"] not in self.serves:
            return accepted  # §19.4 anti-enumeration: accepted and dropped, indistinguishable from delivery
        pending = sum(1 for it in self.items if it["class"] == e["kind"])
        if e["kind"] == "introduction" and pending >= self.inbox_cap:
            return accepted  # §19.4 bounded inbox: held no further, silently
        c, pushes = self._store(e["kind"], "", expires_at=e["expires_at"])
        return [{"accepted": {"to": e["from"], "in_reply_to": e["id"], "cursor": c}}] + pushes

    def _advance(self, n: int) -> list:
        self.now += n
        # §19.4: a held introduction or grant is kept only until its envelope expires (at expires_at, spec-gap 141)
        self.items = [it for it in self.items if it.get("expires_at") is None or it["expires_at"] > self.now]
        for g in [g for g, r in self.groups.items() if r["state"] == "pending" and r["since"] + self.pending_ttl < self.now]:
            del self.groups[g]  # M§6.6: unconfirmed pending group dropped with its items
            self.items = [it for it in self.items if not (it["group"] == g and it["class"] != "archive")]
        return []

    def _welcome(self, e: dict) -> list:
        if e["recipient"] not in self.serves:
            return self._error(e["from"], e["id"], "transport.unknown-recipient")
        adder = e.get("adder_identity")
        if e.get("via_hub"):
            # M§14.2 (spec-gap 46): a hub-forwarded welcome proves its adder only by `origin`, the adder
            # device's signed deposit for this group; the hub connection proves nothing. Its age (spec-gap 118): not
            # from the future beyond 300 s of skew, and not older than the pending-group retention — the hub re-signs
            # every retry, so a welcome delivered after an outage carries an origin as old as the outage.
            o = e.get("origin")
            if o is None or o["group"] != e["group"]:
                return self._error(e["from"], e["id"], "policy.blocked")
            age = e["issued_at"] - o["issued_at"]
            if age < -ORIGIN_SKEW_S or age > self.pending_ttl:
                return self._error(e["from"], e["id"], "policy.blocked")
            adder = o["identity"]
        succ = e.get("successor_of")
        ok = (self.admit == "open" or adder == self.owner or self._grant_ok(e.get("grant"), adder, e["recipient"])
              or (succ is not None and succ in self.groups))
        if not ok:  # M§14.2
            return self._error(e["from"], e["id"], "policy.first-contact-required")
        if e.get("digest") is not None:
            # spec-gap 66: the hub retries a welcome it saw no acknowledgement for. A redelivery is the same MLS bytes
            # (M§9.3), not merely another welcome for the group: adding a sibling device sends a new one (M§6.7).
            # Among the welcomes still held for that group: one dropped with an expired pending registration is held no
            # more, and the same bytes for another group are not this group's welcome (spec-gap 94).
            for it in self.items:
                if it["class"] == "welcome" and it["group"] == e["group"] and it.get("digest") == e["digest"]:
                    return [{"accepted": {"to": e["from"], "in_reply_to": e["id"], "cursor": it["cursor"], "duplicate": True}}]
        if self._over_quota(e):
            return self._error(e["from"], e["id"], "mailbox.quota-exceeded")
        if e["group"] not in self.groups:
            self.groups[e["group"]] = {"hub": e["hub"], "state": "pending", "since": self.now, "items": 0}
        c, pushes = self._store("welcome", e["group"], digest=e.get("digest"), size=e.get("size", 0))
        return [{"accepted": {"to": e["from"], "in_reply_to": e["id"], "cursor": c}}] + pushes

    def _hub_deposit(self, e: dict) -> list:
        if e["recipient"] not in self.serves:
            return self._error(e["from"], e["id"], "transport.unknown-recipient")
        reg = self.groups.get(e["group"])
        prev = reg.get("previous") if reg else None
        late = False  # an item of the previous hub arriving after the wait for it expired (spec-gap 71)
        out = []
        if reg is not None and prev is not None and e["from"] == prev["hub"] and reg["hub"] != e["from"]:
            # spec-gap 60: the previous hub still delivers what it ordered, through the commit that moved the group
            if e.get("seq") is None or e["seq"] > prev["through"]:
                return self._error(e["from"], e["id"], "mailbox.unknown-group")
            if prev.get("released") is not None and e["seq"] > prev["released"] and e["seq"] not in prev["late"]:
                # spec-gap 71: after the wait, what the previous hub still delivers at or below handover_seq is stored
                # (the owner's devices fill their gap with it); what was stored before is a redelivery as usual
                late = True
        elif reg is None or reg["hub"] != e["from"]:  # M§6.6
            return self._error(e["from"], e["id"], "mailbox.unknown-group")
        elif prev is not None:
            if reg.get("high_seq", 0) < prev["through"] and prev.get("released") is None:
                if self.now - prev["since"] < self.handover_wait:
                    # spec-gap 60: not before the previous hub's items through the move are stored (the new hub retries)
                    return self._error(e["from"], e["id"], "mailbox.unknown-group")
                # spec-gap 71: the previous hub did not finish within handover_wait of the owner naming the new one;
                # the new hub is admitted and the missing seqs are left to the owner's devices (M§6.5 gap handling)
                prev["released"], prev["late"] = reg.get("high_seq", 0), []
                out.append({"handover_expired": {"group": e["group"], "hub": prev["hub"],
                                                 "missing": list(range(prev["released"] + 1, prev["through"] + 1))}})
            if e.get("seq") is not None and e["seq"] <= prev["through"]:
                # spec-gap 60: the new hub continues the numbering — and the expiry just noticed is still announced
                # (spec-gap 88)
                return out + self._error(e["from"], e["id"], "policy.blocked")
        if e["class"] == "ephemeral":  # M§11.2: pushed to bound devices, never stored, never acknowledged
            if e.get("expires_at") is not None and e["expires_at"] <= self.now:
                return out  # M§11.2: dropped at expires_at (spec-gap 49: the originating deposit's)
            return out + [{"push": {"to": dv, "class": "ephemeral"}} for dv in sorted(self.bound)]
        seq = e.get("seq")
        if seq is not None and seq <= reg.get("high_seq", 0) and not late:
            # spec-gap 59: a hub retries an unacknowledged fan-out (M§6.5 rule 5) and delivers in seq order, so a seq at
            # or below the highest stored for the group is a redelivery: acknowledged, duplicate, not stored or pushed
            # again (with the original cursor while the item is still retained)
            acc = {"to": e["from"], "in_reply_to": e["id"], "duplicate": True}
            # by group and seq, across a registration the owner left and made again; an archive record shares the seq
            # space (its ref_seq) and is never the item (spec-gap 92)
            c = next((it["cursor"] for it in self.items
                      if it["group"] == e["group"] and it.get("seq") == seq and it["class"] != "archive"), None)
            if c is not None:
                acc["cursor"] = c
            return [{"accepted": acc}]
        if reg["state"] == "pending" and reg["items"] >= self.pending_max:
            return self._error(e["from"], e["id"], "mailbox.quota-exceeded")
        if self._over_quota(e):
            return out + self._error(e["from"], e["id"], "mailbox.quota-exceeded")
        reg["items"] += 1
        if late:
            prev["late"].append(seq)
        elif seq is not None:
            reg["high_seq"] = seq
        c, pushes = self._store(e["class"], e["group"], seq=seq, size=e.get("size", 0))
        return out + [{"accepted": {"to": e["from"], "in_reply_to": e["id"], "cursor": c}}] + pushes

    def _forward_failed(self, e: dict) -> list:
        # M§9.4 (spec-gap 72): a forwarded deposit the mailbox could not hand to the hub (connection refused or lost)
        # is answered mailbox.hub-unreachable so the device keeps it pending and retries with the §13.2 backoff
        return self._error(e["device"], e["id"], "mailbox.hub-unreachable")

    def _forward(self, e: dict) -> list:
        # M§5.2, M§6.6 (spec-gap 45): an owner device's deposit addressed to another service is forwarded
        # unchanged, only to the hub registered for its group; the mailbox stores nothing
        if e["identity"] != self.owner:
            return self._error(e["device"], e["id"], "policy.blocked")
        reg = self.groups.get(e["group"])
        if reg is None or reg["hub"] != e["to"]:
            return self._error(e["device"], e["id"], "mailbox.unknown-group")
        return [{"forward": {"to": e["to"], "id": e["id"]}}]

    def _sync(self, e: dict) -> list:
        dev = e["device"]
        since = e.get("since")
        n_since = 0
        if since is not None:
            n_since = cursor_num(since)
            if n_since is None or n_since > self.counter:
                return self._error(dev, e["id"], "mailbox.cursor-invalid")
        if "ack_through" in e:
            n_ack = cursor_num(e["ack_through"])
            if n_ack is None or n_ack > self.counter:
                return self._error(dev, e["id"], "mailbox.cursor-invalid")
            self.acks[dev] = max(self.acks.get(dev, 0), n_ack)
            if self.mode == "queue":  # M§4.4: deleted once every registered device has acknowledged
                floor = min(self.acks.get(dv, 0) for dv in self.devices)
                self.items = [it for it in self.items if it["n"] > floor]
        if e.get("live"):
            self.bound.add(dev)
        limit = e.get("limit", 200)
        avail = [it for it in self.items if it["n"] > n_since]
        page = avail[:limit]
        nxt = page[-1]["cursor"] if len(avail) > limit else None
        return [{"items": {"to": dev, "in_reply_to": e["id"], "cursors": [it["cursor"] for it in page], "next": nxt}}]

    def _unbind(self, e: dict) -> list:
        self.bound.discard(e["device"])
        return []

    def _config(self, e: dict) -> list:
        dev = e["device"]
        if "mode" in e and e["mode"] not in MAILBOX_MODES:
            return self._error(dev, e["id"], "mailbox.unsupported-mode")
        if "mode" in e:
            self.mode = e["mode"]
        if "admit" in e:
            self.admit = e["admit"]
        for g in e.get("groups", []):
            if g["state"] == "left":
                self.groups.pop(g["group"], None)
            elif g["group"] in self.groups:
                reg = self.groups[g["group"]]
                reg["state"] = "joined"
                if "hub" in g and g["hub"] != reg["hub"]:
                    # M§7.4 (spec-gap 60): an owner device that processed the commit moving the group names the new hub
                    # and the seq of that commit; the old hub's items through it are still admitted
                    reg["previous"] = {"hub": reg["hub"], "through": g.get("handover_seq", reg.get("high_seq", 0)),
                                       "since": self.now}  # spec-gap 71: the wait for the old hub starts here
                    reg["hub"] = g["hub"]
            elif "hub" in g:
                self.groups[g["group"]] = {"hub": g["hub"], "state": "joined", "since": self.now, "items": 0}
        self.revoked |= set(e.get("revoked_grants", []))
        self.introductions_sent += [i for i in e.get("introductions_sent", []) if i not in self.introductions_sent]
        out = [{"accepted": {"to": dev, "in_reply_to": e["id"]}}]
        for d in e.get("revoked_devices", []):
            # spec-gap 57: a revoked device loses its binding now, its registration and its KeyPackages
            if d in self.bound:
                self.bound.discard(d)
                out.append({"close": {"device": d, "reason": "delegation-revoked"}})
            self.devices = [x for x in self.devices if x != d]
            self.kp.pop(d, None)
        return out

    def _archive(self, e: dict) -> list:
        dev = e["device"]
        if self.mode == "queue":  # M§12.2
            return self._error(dev, e["id"], "mailbox.unsupported-class")
        key = (e["ref_group"], e["ref_seq"])
        if key in self.archived:
            return [{"accepted": {"to": dev, "in_reply_to": e["id"], "cursor": self.archived[key], "duplicate": True}}]
        if self._over_quota(e):
            return self._error(dev, e["id"], "mailbox.quota-exceeded")
        c, pushes = self._store("archive", e["ref_group"], depositor=dev, size=e.get("size", 0))
        self.archived[key] = c
        return [{"accepted": {"to": dev, "in_reply_to": e["id"], "cursor": c}}] + pushes

    def _kp_upload(self, e: dict) -> list:
        dev = e["device"]
        if dev not in self.devices:
            return self._error(dev, e["id"], "policy.blocked")
        k = self.kp.setdefault(dev, {"one_time": 0, "last_resort": False})
        k["one_time"] = min(k["one_time"] + e.get("count", 0), KEY_PACKAGES_PER_DEVICE)
        if e.get("last_resort"):
            k["last_resort"] = True
        return [{"accepted": {"to": dev, "in_reply_to": e["id"]}}]

    def _kp_fetch(self, e: dict) -> list:
        if e["target"] not in self.serves:
            return self._error(e["from"], e["id"], "transport.unknown-recipient")
        who = e["from_identity"]
        # M§7.5 (spec-gap 61): a successor's creator re-adds members it may hold no grant from; a registered predecessor
        # authorizes the fetch as it authorizes the successor's welcome
        successor = e.get("successor_of") is not None and e["successor_of"] in self.groups
        if not (self.admit == "open" or who == e["target"] or successor or self._grant_ok(e.get("grant"), who, e["target"])):
            return self._error(e["from"], e["id"], "policy.first-contact-required")
        served = {}
        for dv in self.devices:  # M§5.5: one per device, single use, then last resort
            k = self.kp.get(dv, {"one_time": 0, "last_resort": False})
            if k["one_time"] > 0:
                k["one_time"] -= 1
                served[dv] = "one-time"
            elif k["last_resort"]:
                served[dv] = "last-resort"
        if not served:
            return self._error(e["from"], e["id"], "mailbox.no-key-packages")
        return [{"key_packages": {"to": e["from"], "in_reply_to": e["id"], "devices": served}}]

    def _restart(self, _e) -> list:
        """spec-gap 59: a mailbox restart keeps everything durable and loses its live bindings (connections)."""
        state = json.loads(json.dumps({
            "now": self.now, "owner": self.owner, "serves": sorted(self.serves), "devices": self.devices, "mode": self.mode,
            "admit": self.admit, "pending_ttl": self.pending_ttl, "pending_max": self.pending_max, "groups": self.groups,
            "handover_wait": self.handover_wait,
            "kp": self.kp, "revoked": sorted(self.revoked), "items": self.items, "counter": self.counter, "acks": self.acks,
            "archived": [[g, s, c] for (g, s), c in self.archived.items()], "intro_limit": self.intro_limit,
            "intro_window": self.intro_window, "inbox_cap": self.inbox_cap, "intro_log": self.intro_log,
            "introductions_sent": self.introductions_sent, "quota": self.quota}))
        for k in ("now", "owner", "devices", "mode", "admit", "pending_ttl", "pending_max", "handover_wait", "groups", "kp",
                  "items", "counter", "acks", "intro_limit", "intro_window", "inbox_cap", "intro_log", "introductions_sent",
                  "quota"):
            setattr(self, k, state[k])
        self.serves, self.revoked = set(state["serves"]), set(state["revoked"])
        self.archived = {(g, s): c for g, s, c in state["archived"]}
        self.bound = set()  # volatile: a device re-binds with sync live
        return []

    def snapshot(self) -> dict:
        return {"items": [it["cursor"] for it in self.items],
                "groups": {g: r["state"] for g, r in sorted(self.groups.items())},
                "key_packages": {dv: dict(k) for dv, k in sorted(self.kp.items())},
                **({"used_bytes": self._used()} if self.quota is not None else {})}


# ---------------------------------------------------------------- tranche 2: client rules (M§6.5, M§7.2, M§7.5, M§10, M§11, M§13.2)

VOICEMAIL_REJECT_REASONS = {"user.no-answer", "user.declined", "endpoint.busy", "endpoint.unavailable"}  # M§13.2
MEDIA_KINDS = ("audio", "video")
DELIVERED_MAX_GROUP = 32      # M§10.2: no delivered receipts in larger groups
RECEIPT_MAX_TARGETS = 256     # M§10.2
READ_MIN_INTERVAL_S = 5       # M§10.3
ACTIVITY_REFRESH_S = 5        # M§11.2
GAP_TIMEOUT_S = 300           # M§6.5
HUB_TIMEOUT_S = 86400         # M§9.4 RECOMMENDED: a hub unreachable this long triggers a successor group (M§7.5)
RETRY_INITIAL_S = 1           # §13.2 backoff: initial 1 s, factor 2, max 60 s (the ceiling; hosts add full jitter)
RETRY_MAX_S = 60


def call_event_decision(inp: dict) -> dict:
    """M§13.3 (spec-gap 63): whether a callee device sends a `call-event` for a leg that ended, and with what outcome.

    A leg that never alerted, or was answered on this device, sends nothing; nor does one cancelled with
    `session.answered-elsewhere` (§12.7). A leg this device rejected on the user's decision is `declined`; any other
    alerted, unanswered leg is `missed`.
    """
    if not inp.get("alerted") or inp.get("answered_here"):
        return {"send": False}
    reason = inp.get("reason", "")
    if reason == "session.answered-elsewhere":
        return {"send": False}
    if inp.get("ended_by") == "local" and reason == "user.declined":
        return {"send": True, "outcome": "declined"}
    return {"send": True, "outcome": "missed"}


def peer_timeline(inp: dict) -> dict:
    """M§13.3 (spec-gap 63): one timeline per peer identity from its conversation's content (in seq order) and the
    personal group's call events for that peer (in seq order).

    Call events collapse by `session` (every alerted device of the identity may send one; the first by seq is kept).
    A call is placed before the first content item whose `at` is later than the call's, content never moving relative
    to other content (M§8.5: time does not reorder history).
    """
    calls, seen, collapsed = [], set(), []
    for cev in inp.get("calls", []):
        if cev["session"] in seen:
            collapsed.append(cev["session"])
            continue
        seen.add(cev["session"])
        calls.append(cev)
    calls.sort(key=lambda cev: cev["at"])  # stable: equal times keep seq order
    out, k = [], 0
    for item in inp.get("content", []):
        while k < len(calls) and calls[k]["at"] < item["at"]:
            out.append("call:" + calls[k]["session"])
            k += 1
        out.append("content:" + item["id"])
    out += ["call:" + cev["session"] for cev in calls[k:]]
    return {"timeline": out, "collapsed": collapsed}


def voicemail_offer(inp: dict) -> dict:
    """M§13.2: may the caller's client offer to record a voicemail after this attempt outcome?"""
    from .registry import REASONS
    vm = inp.get("voicemail")
    if not isinstance(vm, dict) or not inp.get("can_send"):
        return {"offer": False}
    out = inp.get("outcome", {})
    t, reason = out.get("type"), out.get("reason", "")
    if t == "reject":
        ok = reason in VOICEMAIL_REJECT_REASONS or (reason not in REASONS and reason.split(".")[0] == "endpoint")
    else:
        ok = t == "cancel" and reason == "session.timeout"
    if not ok:
        return {"offer": False}
    res = {"offer": True}
    if "max_duration_s" in vm:
        res["max_duration_s"] = vm["max_duration_s"]
    return res


def select_direct(candidates: list) -> dict:
    """M§7.2: converge on the lowest conversation ULID, after the §20.6 consistency check."""
    kept, discarded = [], []
    for c in candidates:
        conv = c["conversation"]
        if not U.is_valid(conv) or abs(U.timestamp_ms(conv) // 1000 - c["issued_at"]) > ULID_TOLERANCE_S:
            discarded.append(conv)
        else:
            kept.append(conv)
    return {"winner": min(kept) if kept else None, "discarded": discarded}


def check_successor(inp: dict) -> dict:
    """M§7.5: a successor is accepted only from a predecessor member re-adding predecessor members."""
    pred = set(inp["predecessor_roster"])
    if inp["creator"] in pred and set(inp["roster"]) <= pred:
        return accept()
    return reject("successor-invalid")


def select_successor(candidates: list) -> dict:
    """M§7.5: lowest group_id wins, compared as the decoded ULID, not as base64url text."""
    from .crypto import b64url_decode
    kept, discarded = [], []
    for g in candidates:
        try:
            u = b64url_decode(g).decode("ascii")
        except (ValueError, UnicodeDecodeError):
            u = None
        if u is not None and U.is_valid(u):
            kept.append((u, g))
        else:
            discarded.append(g)
    return {"winner": min(kept)[1] if kept else None, "discarded": discarded}


class SuccessorTracker:
    """A device converging on one successor per dead group (M§7.5; spec-gap 61).

    `groups` are the groups the device is (or was) a member of, with their last known roster by identity. A successor
    welcome for an unknown group, or failing `check_successor`, is a new conversation under first contact. Valid
    successors of one predecessor are candidates: the device keeps only the lowest `group_id` (decoded ULID),
    declining any other and leaving one it had kept when a lower one appears. A request to create a successor when
    one exists uses it instead.
    """

    def __init__(self, ctx: dict):
        self.groups = {g: sorted(r) for g, r in ctx.get("groups", {}).items()}
        self.candidates: dict[str, list[str]] = {}
        self.winner: dict[str, str] = {}

    def step(self, ev: dict) -> list:
        (name, e), = ev.items()
        return getattr(self, "_" + name)(e)

    def _create(self, e: dict) -> list:
        pred = e["predecessor"]
        if pred in self.winner:
            return [{"use": self.winner[pred]}]
        if pred not in self.groups:
            return [{"refuse": "not-a-member"}]
        return [{"create": {"successor_of": pred, "roster": self.groups[pred]}}]

    def _created(self, e: dict) -> list:
        return self._candidate(e["group"], e["successor_of"], self.groups.get(e["successor_of"], []), mine=True)

    def _welcome(self, e: dict) -> list:
        pred = e["successor_of"]
        if pred not in self.groups or check_successor(
                {"predecessor_roster": self.groups[pred], "creator": e["creator"], "roster": e["roster"]})["verdict"] != "accept":
            return [{"first_contact": e["group"]}]
        return self._candidate(e["group"], pred, e["roster"], mine=False)

    def _candidate(self, group: str, pred: str, roster: list, mine: bool) -> list:
        cands = self.candidates.setdefault(pred, [])
        if group not in cands:
            cands.append(group)
        best = select_successor(cands)["winner"]
        prev = self.winner.get(pred)
        if best != group:
            return [{"leave" if mine else "decline": group}]
        self.winner[pred] = group
        self.groups[group] = sorted(roster)  # a successor can itself be succeeded
        out = [] if mine else [{"join": group}]
        if prev is not None and prev != group:
            out.append({"leave": prev})
        return out

    def snapshot(self) -> dict:
        return {p: {"successor": self.winner.get(p), "candidates": sorted(c)} for p, c in sorted(self.candidates.items())}


class Client:
    """One device's view of one conversation: receipt collapse, watermarks, and what it sends (M§10, M§11)."""

    def __init__(self, ctx: dict):
        self.now = ctx["now"]
        self.me = ctx["me"]
        self.policy = ctx.get("policy", {})
        self.members = ctx.get("member_identities", 2)
        self.content: dict[str, dict] = {}      # id -> {sender, seq, kind}
        self.timeline: list[str] = []
        self.delivered: dict[str, dict] = {}
        self.played: dict[str, dict] = {}
        self.read_seq: dict[str, int] = {}
        self.read_through: dict[str, str] = {}
        self.sent_delivered: set[str] = set()
        self.sent_played: set[str] = set()
        self.last_read_sent: int | None = None
        self.pending_read = False
        self.last_activity: dict[str, int] = {}
        self.shown: dict[str, dict[str, int]] = {}  # sender -> activity -> expires_at

    def step(self, ev: dict) -> list:
        (name, e), = ev.items()
        return getattr(self, "_" + name)(e)

    def _sync(self, e: dict) -> list:
        fresh, archive = [], []
        for it in e["items"]:
            o, seq = it["object"], it["seq"]
            if o["object"] == "content":
                if o["id"] in self.content:  # M§8.5: duplicates collapse silently
                    continue
                self.content[o["id"]] = {"sender": o["sender"], "seq": seq, "kind": o["kind"]}
                self.timeline.append(o["id"])
                fresh.append(o["id"])
            elif o["object"] == "receipt":
                if self._receipt(o):
                    # M§12.2 (spec-gap 64): a receipt that changes rendering is archived like content
                    archive.append({"archive": {"seq": seq}})
        out = archive
        if self.policy.get("delivered") and self.members <= DELIVERED_MAX_GROUP:
            # M§10.2: the whole batch is processed first, so a sibling's receipt in it suppresses ours
            targets = [i for i in fresh if self.content[i]["sender"] != self.me
                       and self.me not in self.delivered.get(i, {}) and i not in self.sent_delivered]
            for k in range(0, len(targets), RECEIPT_MAX_TARGETS):
                chunk = targets[k:k + RECEIPT_MAX_TARGETS]
                out.append({"send": {"to": "conversation", "receipt": "delivered", "targets": chunk}})
            self.sent_delivered |= set(targets)
        return out

    def _restore(self, e: dict) -> list:
        """spec-gap 64: content and receipts opened from archive update the rendering state and send nothing — no
        delivered receipt for history, and no second archive of what already is archived."""
        for it in e["items"]:
            o, seq = it["object"], it["seq"]
            if o["object"] == "content" and o["id"] not in self.content:
                self.content[o["id"]] = {"sender": o["sender"], "seq": seq, "kind": o["kind"]}
                self.timeline.append(o["id"])
            elif o["object"] == "receipt":
                self._receipt(o)
        return []

    def _receipt(self, o: dict) -> bool:
        """Apply a receipt; True when it changed what is rendered."""
        kind, who = o["kind"], o["sender"]
        changed = False
        if kind in ("delivered", "played"):
            book = self.delivered if kind == "delivered" else self.played
            for t in o.get("targets", []):
                c = self.content.get(t)
                if c is None or c["sender"] == who:  # the content's own identity does not receipt itself
                    continue
                if kind == "played" and c["kind"] not in MEDIA_KINDS:
                    continue
                if who not in book.get(t, {}):
                    book.setdefault(t, {})[who] = o["sent_at"]  # first by seq wins
                    changed = True
        elif kind == "read":
            c = self.content.get(o.get("through"))
            if c is not None and c["seq"] > self.read_seq.get(who, 0):  # M§10.3: monotone
                self.read_seq[who], self.read_through[who] = c["seq"], o["through"]
                changed = True
        return changed

    def _read_send(self) -> list:
        self.last_read_sent, self.pending_read = self.now, False
        to = "conversation" if self.policy.get("read") else "personal"  # M§10.5
        return [{"send": {"to": to, "receipt": "read", "through": self.read_through[self.me]}}]

    def _read(self, e: dict) -> list:
        c = self.content.get(e["through"])
        if c is None or c["seq"] <= self.read_seq.get(self.me, 0):
            return []
        self.read_seq[self.me], self.read_through[self.me] = c["seq"], e["through"]
        if self.last_read_sent is not None and self.now - self.last_read_sent < READ_MIN_INTERVAL_S:
            self.pending_read = True
            return []
        return self._read_send()

    def _activity_in(self, e: dict) -> list:
        # M§11.2: shown until the last refresh's expires_at (spec-gap 49), cleared at once by stopped
        acts = self.shown.setdefault(e["sender"], {})
        if e["state"] == "stopped":
            acts.pop(e["activity"], None)
        elif e["expires_at"] > self.now:
            acts[e["activity"]] = e["expires_at"]
        if not acts:
            del self.shown[e["sender"]]
        return []

    def _advance(self, n: int) -> list:
        self.now += n
        for who in list(self.shown):
            self.shown[who] = {a: t for a, t in self.shown[who].items() if t > self.now}
            if not self.shown[who]:
                del self.shown[who]
        if self.pending_read and self.now - self.last_read_sent >= READ_MIN_INTERVAL_S:
            return self._read_send()
        return []

    def _play(self, e: dict) -> list:
        i = e["id"]
        c = self.content.get(i)
        if (c is None or c["kind"] not in MEDIA_KINDS or not self.policy.get("played")
                or self.me in self.played.get(i, {}) or i in self.sent_played):
            return []
        self.sent_played.add(i)
        return [{"send": {"to": "conversation", "receipt": "played", "targets": [i]}}]

    def _activity(self, e: dict) -> list:
        if not self.policy.get("activity"):  # M§11.2: same opt-in as read receipts
            return []
        a, state = e["activity"], e["state"]
        if state == "active":
            last = self.last_activity.get(a)
            if last is not None and self.now - last < ACTIVITY_REFRESH_S:
                return []
            self.last_activity[a] = self.now
        else:
            self.last_activity.pop(a, None)
        return [{"send": {"to": "conversation", "activity": a, "state": state}}]

    def snapshot(self) -> dict:
        return {"timeline": list(self.timeline),
                "delivered": {i: dict(m) for i, m in sorted(self.delivered.items()) if m},
                "played": {i: dict(m) for i, m in sorted(self.played.items()) if m},
                "read_through": dict(sorted(self.read_through.items())),
                "activity": {w: dict(sorted(a.items())) for w, a in sorted(self.shown.items())}}


class HubOutage:
    """A device's outbox for one group while its hub cannot be reached (M§9.4; spec-gap 72).

    A deposit is forwarded at once while the hub is up and queued behind the pending ones while it is down. The hub is
    down from the first `mailbox.hub-unreachable` (or no answer at all) until an `accepted`: pending items are
    re-deposited as the same bytes (M§9.3), the head first, with the §13.2 backoff (1 s, doubling, 60 s ceiling); an
    `accepted` flushes the rest in order and resets the backoff. Down for `hub_timeout` (24 h RECOMMENDED), the device
    creates the successor group (M§7.5) and hands it the pending items to re-encrypt; the dead group's outbox is then
    abandoned. Nothing is ever deposited into members' mailboxes directly. Any other refusal is not an outage: the item
    leaves the outbox and the refusal is the caller's (M§6.5 handles a commit's).

    The hand-over to the successor can fail: once abandoned, `handover_failed` is answered with the §13.2 backoff started
    afresh, and the `advance` that reaches it emits one `{"handover": "retry"}`; in any other state it is nothing.
    """

    def __init__(self, ctx: dict):
        self.now = ctx["now"]
        self.hub_timeout = ctx.get("hub_timeout", HUB_TIMEOUT_S)
        # a host restoring its outbox passes `pending` and `down_since`; the first retry is then due at once
        self.pending: list[str] = list(ctx.get("pending", []))
        self.down_since: int | None = ctx.get("down_since")
        self.attempt = 0
        self.retry_at: int | None = self.now if self.down_since is not None else None
        self.state = "down" if self.down_since is not None else "up"
        self.handover_attempt = 0
        self.handover_at: int | None = None

    def step(self, ev: dict) -> list:
        (name, e), = ev.items()
        return getattr(self, "_" + name)(e)

    def _deposit(self, e: dict) -> list:
        if self.state == "abandoned":
            return [{"refuse": "group-abandoned"}]
        self.pending.append(e["id"])
        return [{"forward": e["id"]}] if self.state == "up" else [{"queued": e["id"]}]

    def _unreachable(self, item_id: str) -> list:
        if item_id not in self.pending:
            return []
        if self.down_since is None:
            self.down_since = self.now
            self.state = "down"
        self.attempt += 1
        delay = min(RETRY_INITIAL_S * 2 ** (self.attempt - 1), RETRY_MAX_S)
        self.retry_at = self.now + delay
        return [{"retry_in": delay}]

    def _no_answer(self, e: dict) -> list:
        return self._unreachable(e["id"])

    def _answer(self, e: dict) -> list:
        reason = e.get("reason")
        if reason in ("mailbox.hub-unreachable", "mailbox.quota-exceeded"):  # spec-gap 99: a hub that cannot store
            return self._unreachable(e["id"])
        if e["id"] not in self.pending:
            return []
        self.pending.remove(e["id"])
        if reason is not None:
            return [{"refused": {"id": e["id"], "reason": reason}}]
        out = [{"sent": e["id"]}]
        if self.state == "down":
            self.state, self.down_since, self.attempt, self.retry_at = "up", None, 0, None
            out += [{"forward": p} for p in self.pending]  # the hub is back: flush in order
        return out

    def _handover_failed(self, _e: dict) -> list:
        if self.state != "abandoned":
            return []
        self.handover_attempt += 1
        delay = min(RETRY_INITIAL_S * 2 ** (self.handover_attempt - 1), RETRY_MAX_S)
        self.handover_at = self.now + delay
        return [{"handover_retry_in": delay}]

    def _advance(self, n: int) -> list:
        self.now += n
        if self.state == "abandoned" and self.handover_at is not None and self.now >= self.handover_at:
            self.handover_at = None  # the next failure schedules the next attempt
            return [{"handover": "retry"}]
        if self.state != "down":
            return []
        if self.now - self.down_since >= self.hub_timeout:
            # M§9.4: the successor-group trigger of M§7.5; the pending items are re-encrypted for the successor
            out = [{"successor": {"pending": list(self.pending)}}]
            self.pending, self.state, self.retry_at = [], "abandoned", None
            return out
        if self.pending and self.retry_at is not None and self.now >= self.retry_at:
            self.retry_at = None  # the answer schedules the next attempt
            return [{"forward": self.pending[0]}]
        return []

    def snapshot(self) -> dict:
        return {"state": self.state, "pending": list(self.pending), "attempt": self.attempt,
                "down_for": None if self.down_since is None else self.now - self.down_since,
                "handover_attempt": self.handover_attempt}


MLS_RETENTION_S = 2592000      # M§4.4 RECOMMENDED: 30 days; a registered device completed a verified hello within it
ARRIVAL_WAIT_S = 300          # M§7.4 (spec-gap 129): how long a member waits for the hub a group moved to, as handover_wait


class MoveArrival:
    """A member reaching the hub a group moved to before the committer's group-info has set it up (M§7.4; spec-gap 129).

    `moved` names the new hub (the device processed the moving commit, or its own move was accepted). Until that hub
    accepts a deposit, its `mailbox.unknown-group` is not final: the same deposit is retried with the §13.2 backoff
    (1 s, doubling, 60 s ceiling), for at most `arrival_wait` from the move. The first such refusal at or past the bound
    emits `expired`, once. Every other answer, and any answer from another hub, emits nothing: the caller handles it as
    usual (M§7.4 sync, M§9.4 outage, M§6.5). A later `moved` starts afresh.
    """

    def __init__(self, ctx: dict):
        self.now = ctx["now"]
        self.wait = ctx.get("arrival_wait", ARRIVAL_WAIT_S)
        self.state, self.hub, self.since, self.attempt = "none", None, None, 0

    def step(self, ev: dict) -> list:
        (name, e), = ev.items()
        return getattr(self, "_" + name)(e)

    def _moved(self, e: dict) -> list:
        self.state, self.hub, self.since, self.attempt = "arriving", e["hub"], self.now, 0
        return []

    def _answer(self, e: dict) -> list:
        if self.state != "arriving" or e["hub"] != self.hub:
            return []
        reason = e.get("reason")
        if reason is None:
            self.state = "hosted"
            return []
        if reason != "mailbox.unknown-group":
            return []
        if self.now - self.since >= self.wait:
            self.state = "expired"
            return [{"expired": {}}]
        self.attempt += 1
        return [{"retry_in": min(RETRY_INITIAL_S * 2 ** (self.attempt - 1), RETRY_MAX_S)}]

    def _advance(self, n: int) -> list:
        self.now += n
        return []

    def snapshot(self) -> dict:
        return {"state": self.state, "hub": self.hub, "attempt": self.attempt,
                "waited": None if self.since is None else self.now - self.since}


class Enrolment:
    """Whom a mailbox serves, and when an enrolment ends (M§4.1; spec-gaps 115, 130).

    Configured identities are always served and never count against the bound. Any other identity enrols with its
    first owner operation while fewer than `serve_any` are enrolled; past the bound its owner operations are refused
    `mailbox.not-served`. An enrolment ends by `mailbox-config` `release: true` (a configured identity is refused
    `mailbox.not-enrolled`), by its operator (spec-gap 164) or, when the operator chose idle expiry, once no device of
    the identity has completed a verified `hello` within `mls_retention_s` (M§4.4: it has no registered device).
    `released` tells the host to delete everything it holds for the identity and close its bindings.
    """

    def __init__(self, ctx: dict):
        self.now = ctx["now"]
        self.configured = set(ctx.get("configured", []))
        self.serve_any = ctx.get("serve_any", 0)
        self.expire_idle = ctx.get("expire_idle", False)
        self.retention = ctx.get("mls_retention_s", MLS_RETENTION_S)
        self.enrolled: dict[str, int] = {}  # identity → last verified hello, in enrolment order

    def step(self, ev: dict) -> list:
        (name, e), = ev.items()
        return getattr(self, "_" + name)(e)

    @staticmethod
    def _error(e: dict, reason: str) -> list:
        return [{"error": {"to": e["device"], "in_reply_to": e["id"], "reason": reason}}]

    def _owner_op(self, e: dict) -> list:
        who = e["identity"]
        if who in self.configured or who in self.enrolled:
            return []
        if len(self.enrolled) >= self.serve_any:
            return self._error(e, "mailbox.not-served")  # M§4.1 (spec-gap 130)
        self.enrolled[who] = self.now  # enrolment happens on a verified binding: it counts as a hello
        return [{"enrolled": {"identity": who}}]

    def _release(self, e: dict) -> list:
        who = e["identity"]
        if who in self.configured:
            return self._error(e, "mailbox.not-enrolled")  # its operator ends it
        if who not in self.enrolled:
            return self._error(e, "mailbox.not-served")  # a release never enrols
        del self.enrolled[who]
        return [{"accepted": {"to": e["device"], "in_reply_to": e["id"]}},
                {"released": {"identity": who, "cause": "owner"}}]

    def _operator_release(self, e: dict) -> list:
        # spec-gap 164: as a release, with nothing sent; a configured identity leaves by the configuration
        who = e["identity"]
        if who not in self.enrolled:
            return []
        del self.enrolled[who]
        return [{"released": {"identity": who, "cause": "operator"}}]

    def _hello(self, e: dict) -> list:
        if e["identity"] in self.enrolled:
            self.enrolled[e["identity"]] = self.now
        return []

    def _advance(self, n: int) -> list:
        self.now += n
        if not self.expire_idle:
            return []
        # M§4.4: registered while its last hello is within mls_retention_s; at exactly the bound it still is
        idle = [who for who, seen in self.enrolled.items() if self.now - seen > self.retention]
        for who in idle:
            del self.enrolled[who]
        return [{"released": {"identity": who, "cause": "idle"}} for who in idle]

    def snapshot(self) -> dict:
        return {"enrolled": list(self.enrolled), "free": self.serve_any - len(self.enrolled)}


class GapTracker:
    """M§6.5: a device holds handshake items (and anything after them) across a seq gap; rejoin on timeout."""

    def __init__(self, ctx: dict):
        self.now = ctx["now"]
        self.contiguous = ctx.get("contiguous", 0)
        self.timeout = ctx.get("gap_timeout", GAP_TIMEOUT_S)  # M§6.5 RECOMMENDED 300 s; a device may use less
        self.seen: set[int] = set()
        self.held: list[int] = []
        self.gap_since: int | None = None

    def step(self, ev: dict) -> list:
        if "advance" in ev:
            self.now += ev["advance"]
            if self.held and self.now - self.gap_since >= self.timeout:
                out = [{"rejoin": {"held": list(self.held)}}]
                self.contiguous = max(self.held + list(self.seen))
                self.seen.clear()
                self.held, self.gap_since = [], None
                return out
            return []
        it = ev["item"]
        seq, cls = it["seq"], it["class"]
        if seq <= self.contiguous or seq in self.seen:
            return [{"duplicate": seq}]
        self.seen.add(seq)
        out = []
        blocked = cls == "handshake" and seq > self.contiguous + 1
        if blocked or (self.held and seq > self.held[0]):
            self.held = sorted(self.held + [seq])
            if self.gap_since is None:
                self.gap_since = self.now
            out.append({"hold": seq})
        else:
            out.append({"process": seq})
        while self.contiguous + 1 in self.seen:
            self.contiguous += 1
            self.seen.discard(self.contiguous)
        while self.held and self.held[0] <= self.contiguous:
            out.append({"process": self.held.pop(0)})
        if not self.held:
            self.gap_since = None
        return out

    def snapshot(self) -> dict:
        return {"contiguous": self.contiguous, "held": list(self.held)}


class History:
    """One device's conversation history from MLS items and archive records (M§12.2, M§12.3, M§8.5; spec-gap 51).

    Archive records under an archive key the device does not hold yet are held (a new device syncs from null and
    meets records before the personal-group welcome that brings the key) and released when the key arrives. MLS
    items from epochs before the device joined the group are skipped: their history comes from archive. Archive
    and MLS copies of one object collapse by its key; the timeline is in (group, seq) order whatever the arrival
    order. A device archives what it shows from MLS, including its own sent content, under the current key: the
    one with the greatest `created_at`, ties broken by `akid`.
    """

    def __init__(self, ctx: dict):
        self.keys = {k["akid"]: k["created_at"] for k in ctx.get("keys", [])}
        self.joined = dict(ctx.get("joined", {}))
        self.held: list[dict] = []
        self.shown: dict[str, tuple] = {}
        self.applied: set[str] = set()

    def step(self, ev: dict) -> list:
        (name, e), = ev.items()
        return getattr(self, "_" + name)(e)

    def _current(self):
        return max(self.keys.items(), key=lambda kv: (kv[1], kv[0]))[0] if self.keys else None

    def _show(self, e: dict) -> dict:
        if e["id"] in self.shown:
            return {"duplicate": e["id"]}
        self.shown[e["id"]] = (e["group"], e["seq"])
        return {"show": e["id"]}

    def _joined(self, e: dict) -> list:
        self.joined[e["group"]] = e["epoch"]
        return []

    def _archive_key(self, e: dict) -> list:
        self.keys[e["akid"]] = e["created_at"]
        out, keep = [], []
        for h in self.held:
            if h["akid"] == e["akid"]:
                out.append(self._open(h))
            else:
                keep.append(h)
        self.held = keep
        return out

    def _archive(self, e: dict) -> list:
        if e["akid"] not in self.keys:
            self.held.append(e)
            return [{"hold": e["cursor"]}]
        return [self._open(e)]

    def _open(self, e: dict) -> dict:
        if e.get("object", "content") in ("receipt", "call-event"):
            # spec-gaps 63, 64: an archived receipt or call event restores state; it is not a conversation timeline entry
            if e["id"] in self.applied:
                return {"duplicate": e["id"]}
            self.applied.add(e["id"])
            return {"apply": e["cursor"]}
        return self._show(e)

    def _mls(self, e: dict) -> list:
        if e["group"] in self.joined and e["epoch"] < self.joined[e["group"]]:
            return [{"prejoin": e["seq"]}]
        return self._sent(e)

    def _sent(self, e: dict) -> list:
        if e.get("object", "content") in ("receipt", "call-event"):
            # spec-gap 68: a device archives the read watermark it sends, so a device added later knows where its
            # user had read (M§10.3, M§10.5); like any archived receipt it is state, not a timeline entry; a call
            # event too, sent or received (spec-gap 63)
            if e["id"] in self.applied:
                return [{"duplicate": e["id"]}]
            self.applied.add(e["id"])
            akid = self._current()
            return [] if akid is None else [{"archive": {"group": e["group"], "seq": e["seq"], "akid": akid}}]
        return self._from_mls(e)

    def _from_mls(self, e: dict) -> list:
        shown = self._show(e)
        out = [shown]
        if "show" in shown and self._current() is not None:
            out.append({"archive": {"group": e["group"], "seq": e["seq"], "akid": self._current()}})
        return out

    def snapshot(self) -> dict:
        order = sorted(self.shown.items(), key=lambda kv: kv[1])
        return {"timeline": [k for k, _ in order], "held": [h["cursor"] for h in self.held], "current_akid": self._current()}


class CommitRetry:
    """What a committing device does with the hub's answer (M§6.5; spec-gap 58).

    accepted → merge. `mailbox.commit-conflict` and `mailbox.stale-epoch` → discard the pending commit, sync until the
    winning commit is processed, and re-propose if the operation is still needed, at most `max_attempts` proposals in
    all, then surface. An unregistered `mailbox.*` condition takes the category fallback (core §15.3): re-sync, retry
    once, then surface. `mailbox.unknown-group` from a hub (spec-gap 60) is handled like a conflict when the sync shows
    the group moved to another hub (M§7.4), and surfaced otherwise. Any other refusal — `policy.blocked`, a registered
    token of any other kind, an unknown category — is discarded and surfaced without retry.
    """

    RETRY_REASONS = ("mailbox.commit-conflict", "mailbox.stale-epoch", "mailbox.unknown-group")

    def __init__(self, ctx: dict):
        self.max_attempts = ctx.get("max_attempts", 3)
        self.attempt = 1
        self.state = "pending"
        self.unknown_retry_used = False
        self.last_reason = None

    def step(self, ev: dict) -> list:
        (name, e), = ev.items()
        return getattr(self, "_" + name)(e)

    def _surface(self, reason: str) -> list:
        self.state = "surfaced"
        return [{"discard": {}}, {"surface": reason}]

    def _answer(self, e: dict) -> list:
        reason = e.get("reason")
        self.last_reason = reason
        if reason is None:
            self.state = "merged"
            return [{"merge": {}}]
        from .registry import REASONS
        if reason in self.RETRY_REASONS:
            if self.attempt >= self.max_attempts:
                return self._surface(reason)
        elif (reason.split(".", 1)[0] == "mailbox" and reason not in REASONS and not self.unknown_retry_used
              and self.attempt < self.max_attempts):
            # §15.3 mailbox fallback: re-sync, retry once, then surface — inside M§6.5's bound of three proposals
            self.unknown_retry_used = True
        else:
            return self._surface(reason)
        self.state = "syncing"
        return [{"discard": {}}, {"sync": {}}]

    def _synced(self, e: dict) -> list:
        if self.last_reason == "mailbox.unknown-group" and not e.get("hub_moved", False):
            # spec-gap 60: the old hub of a moved group answers unknown-group; unless the sync showed a move, it is final
            self.state = "surfaced"
            return [{"surface": self.last_reason}]
        if not e["still_needed"]:
            self.state = "done"
            return [{"done": "no-longer-needed"}]
        self.attempt += 1
        self.state = "pending"
        return [{"repropose": {"attempt": self.attempt}}]

    def snapshot(self) -> dict:
        return {"attempt": self.attempt, "state": self.state}


SEQUENCED_CLASSES = ("handshake", "application")


class Resume:
    """M§5.4 `ack_through` and M§8.5 across a device restart (spec-gap 44).

    The state is exactly what the device holds durably: the ack cursor, per-group seq positions and
    the joined groups. Each item is processed and committed together with that state, or not at all.
    A redelivered sequenced item is recognised by its seq, never by decrypting it: MLS consumed its
    secret the first time. Holding across a seq gap is `GapTracker`'s job; traces here hold nothing.
    """

    def __init__(self, ctx: dict):
        self.cursor = ctx.get("cursor")
        self.groups = {g: {"contiguous": p["contiguous"], "seen": set(p["seen"])} for g, p in ctx.get("groups", {}).items()}
        self.joined = set(ctx.get("joined", []))
        # spec-gap 180: the `limit` the device syncs with, when the trace states one; halved for every envelope over the
        # cap, and back to this on restart (it is not durable state)
        self.base_limit = ctx.get("limit")
        self.limit = self.base_limit

    def step(self, ev: dict) -> list:
        (name, e), = ev.items()
        return getattr(self, "_" + name)(e)

    def _duplicate(self, it: dict) -> bool:
        if it["class"] in SEQUENCED_CLASSES:
            p = self.groups.get(it["group"])
            return p is not None and (it["seq"] <= p["contiguous"] or it["seq"] in p["seen"])
        return it["class"] == "welcome" and it["group"] in self.joined

    def _items(self, e: dict) -> list:
        out = []
        for it in e["items"]:
            if it["cursor"] == e.get("crash_at"):
                out.append({"crash": it["cursor"]})  # processed in memory, never committed: rolled back
                break
            dup = self._duplicate(it)
            if not dup and it.get("sibling"):
                # spec-gap 51: a welcome for another device of this identity holds none of this device's
                # KeyPackages; it is acknowledged but is not a join, so this device's own welcome still counts
                out.append({"sibling": it["cursor"]})
                self.cursor = it["cursor"]
                continue
            out.append({"duplicate" if dup else "process": it["cursor"]})
            # commit: the cursor advances past duplicates too, so they are acknowledged
            self.cursor = it["cursor"]
            if dup:
                continue
            if it["class"] in SEQUENCED_CLASSES:
                self._position(it["group"], it["seq"])
            elif it["class"] == "welcome":
                self.joined.add(it["group"])
                if it.get("seq") is not None:
                    # spec-gap 83: the welcome carries the seq of the commit that added this device — its exact position.
                    # What is at or below it is pre-join history; what follows is counted from there.
                    self.groups[it["group"]] = {"contiguous": it["seq"], "seen": set()}
        return out

    def _sent(self, e: dict) -> list:
        # spec-gap 47: the hub fans a device's own item back to its identity (M§6.5 rule 5), and MLS cannot
        # decrypt a device's own message; the seq in its `accepted` marks the copy as already processed
        self._position(e["group"], e["seq"])
        return []

    def _rejoined(self, e: dict) -> list:
        """M§6.5, M§6.8 (spec-gap 69): after re-joining by external commit the device treats every seq up to the
        highest it has seen as passed — those items are gone, or for epochs it can no longer reach."""
        p = self.groups.setdefault(e["group"], {"contiguous": 0, "seen": set()})
        p["contiguous"] = max([e["seq"], p["contiguous"], *p["seen"]])
        p["seen"] = set()
        self.joined.add(e["group"])
        return []

    def _removed(self, e: dict) -> list:
        """M§7.3 (spec-gap 127): a commit removed this device's identity. The group is no longer joined, so a welcome
        adding it back is a join; its seq positions stay, so items already processed remain duplicates."""
        self.joined.discard(e["group"])
        return []

    def _position(self, group: str, seq: int) -> None:
        if group not in self.groups:
            # spec-gap 69, the fallback of spec-gap 83: with no position from a welcome, a device counts from where it
            # starts — the first sequenced item it processes — not from seq 1
            self.groups[group] = {"contiguous": seq, "seen": set()}
            return
        p = self.groups[group]
        if seq > p["contiguous"]:
            p["seen"].add(seq)
        while p["contiguous"] + 1 in p["seen"]:
            p["contiguous"] += 1
            p["seen"].discard(p["contiguous"])

    def _sync(self, _e: dict) -> list:
        s = {"since": self.cursor}
        if self.cursor is not None:
            s["ack_through"] = self.cursor  # never ahead of what is committed
        if self.limit is not None:
            s["limit"] = self.limit
        return [{"sync": s}]

    def _restart(self, e: dict) -> list:
        self.__init__({**self.snapshot(), "limit": self.base_limit})  # only durable state survives
        return self._sync(e)

    def _too_large(self, e: dict) -> list:
        """M§5.4 (spec-gap 180): the mailbox answered the last `sync` with an envelope over the cap (§13.2). The same
        `sync` would get the same envelope, so the device syncs from the same cursor with half the limit, at least 1."""
        if self.limit == 1:
            # MAX_MLS_BYTES makes any one item fit: the mailbox is at fault, and the same sync waits out the §13.2 backoff
            return [{"backoff": {}}] + self._sync(e)
        self.limit = max(1, self.limit // 2)  # traces with `too_large` state the device's `limit` in context
        return self._sync(e)

    def _cursor_invalid(self, e: dict) -> list:
        self.cursor = None  # M§5.4: re-sync from null; seq positions and joined groups are kept
        return self._sync(e)

    def snapshot(self) -> dict:
        return {"cursor": self.cursor,
                "groups": {g: {"contiguous": p["contiguous"], "seen": sorted(p["seen"])} for g, p in sorted(self.groups.items())},
                "joined": sorted(self.joined)}


def items_pages(v: dict) -> dict:
    """M§5.4 (spec-gap 180): a mailbox answers `sync` with `items` envelopes that each fit the `ws/1.0` cap (§13.2) as
    encoded and signed, never paging by count alone; the device follows `next` until it is `null`.

    The mailbox signs with the fixture key `context.mailbox_key`; each item's `mls` is `mls_bytes` zero bytes. What is
    reported is what every conforming mailbox shares, not where it splits: the cursors delivered, in order; whether every
    page fits the cap and holds at most `limit` items; and whether each page's `next` is its last cursor (`null` on the
    last page), with no empty page before it.
    Impl: a page is the longest prefix of the remaining items that fits, at most `limit`.
    """
    from .crypto import keypair_from_seed_name, b64url_encode as b64
    from . import envelope as env
    ctx, inp = v["context"], v["input"]
    key = keypair_from_seed_name(ctx["mailbox_key"])
    kid = key.did + "#" + key.did.split(":")[-1]
    now, limit = ctx["now"], inp.get("limit", 200)
    stored = [{**{k: x for k, x in it.items() if k != "mls_bytes"}, "mls": b64(bytes(it["mls_bytes"]))} for it in inp["items"]]
    sync_id = U.encode(now * 1000, bytes(10))

    def frame(page: list, nxt, n: int) -> str:
        payload = {"dsip": {"core": "1.0", "min_core": "1.0", "profiles": ["messaging/1.0"], "extensions": [], "critical": []},
                   "type": "items", "id": U.encode(now * 1000, n.to_bytes(10, "big")), "from": key.did, "to": ctx["device"],
                   "in_reply_to": sync_id, "items": page, "next": nxt, "issued_at": now, "expires_at": now + 30}
        return env.frame(env.sign(payload, key, kid))

    def fits(f: str) -> bool:
        return len(f.encode("utf-8")) <= env.WS_MAX_ENVELOPE_BYTES

    cursors, fit, within, chain, rest, n = [], True, True, True, stored, 0
    while True:
        k = min(limit, len(rest))
        while k > 1 and not fits(frame(rest[:k], rest[k - 1]["cursor"], n)):
            k -= 1
        page = rest[:k]
        nxt = page[-1]["cursor"] if len(rest) > k else None
        f = frame(page, nxt, n)
        n += 1
        fit &= fits(f)
        within &= len(page) <= limit
        cursors += [it["cursor"] for it in page]
        rest = rest[k:]
        if nxt is None:
            chain &= not rest
            break
        chain &= bool(page) and nxt == page[-1]["cursor"]
    return {"cursors": cursors, "fit": fit, "within_limit": within, "next_chain": chain}


# ---------------------------------------------------------------- tranche 3: the MLS layer (M§6.2, M§6.3, M§8.4, M§11.1, M§12.2)

EXT_DSIP_DELEGATION = 0xF0D1   # M§17: private-use MLS ExtensionType (LeafNode) until registered
EXT_DSIP_CONVERSATION = 0xF0D2  # M§17: private-use MLS ExtensionType (GroupContext) until registered
CREDENTIAL_BASIC = 0x0001      # RFC 9420 CredentialType basic
MESSAGING_CAPABILITY = "dsip.messaging"  # M§6.2 (spec-gap 39)
NONCE_LEN, TAG_LEN = 12, 16


def vl_len(n: int) -> bytes:
    """RFC 9420 §2.1.2 variable-length vector length: minimal 1-, 2- or 4-byte QUIC-style integer."""
    if n < 1 << 6:
        return bytes([n])
    if n < 1 << 14:
        return (0x4000 | n).to_bytes(2, "big")
    if n < 1 << 30:
        return (0x80000000 | n).to_bytes(4, "big")
    raise ValueError("vector too long for MLS")


def encode_extension(ext_type: int, data: bytes) -> bytes:
    return ext_type.to_bytes(2, "big") + vl_len(len(data)) + data


def decode_extension(b: bytes) -> dict:
    if len(b) < 3:
        return reject("mls-truncated")
    prefix = b[2] >> 6
    if prefix == 3:  # 8-byte lengths exceed MLS's 30-bit bound
        return reject("mls-length-invalid")
    n = {0: 1, 1: 2, 2: 4}[prefix]
    if len(b) < 2 + n:
        return reject("mls-truncated")
    length = int.from_bytes(b[2:2 + n], "big") & ((1 << (8 * n - 2)) - 1)
    if (n == 2 and length < 1 << 6) or (n == 4 and length < 1 << 14):
        return reject("mls-length-non-minimal")
    data = b[2 + n:2 + n + length]
    if len(data) < length:
        return reject("mls-truncated")
    if len(b) > 2 + n + length:
        return reject("mls-trailing-bytes")
    return accept(extension_type=int.from_bytes(b[:2], "big"), data_hex=data.hex())


def check_mls_credential(inp: dict, ctx: dict) -> dict:
    """M§6.2: the DSIP authentication service for an MLS leaf."""
    from . import envelope as E
    from .crypto import public_from_did_key
    cred = inp["credential"]
    if cred.get("credential_type") != CREDENTIAL_BASIC:
        return reject("credential-type")
    try:
        device = bytes.fromhex(cred["identity_hex"]).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return reject("credential-identity")
    import re
    if not re.match(r"^did:[a-z0-9]+:[A-Za-z0-9.%_:-]+$", device):
        return reject("credential-identity")
    exts = [e for e in inp.get("extensions", []) if e["extension_type"] == EXT_DSIP_DELEGATION]
    if not exts:
        return reject("delegation-missing")
    if len(exts) > 1:
        return reject("delegation-invalid")
    try:
        parts = bytes.fromhex(exts[0]["data_hex"]).decode("ascii").split(".")
    except (ValueError, UnicodeDecodeError):
        return reject("delegation-invalid")
    if len(parts) != 3:
        return reject("delegation-invalid")
    deleg = {"protected": parts[0], "payload": parts[1], "signature": parts[2]}
    names = E._names(deleg)
    if names is None or names[1] != device or not isinstance(names[0], str):
        return reject("delegation-invalid")
    v = E.verify_delegation(deleg, names[0], device, E.Context.from_vector(ctx), capability=MESSAGING_CAPABILITY)
    if not v.ok:
        return reject(v.code)
    try:
        pub = public_from_did_key(device)
    except Exception:
        pub = None
    if pub is None or pub.hex() != inp["signature_key_hex"]:  # M§6.2: leaf key = the device's Ed25519 key
        return reject("credential-key-mismatch")
    return accept(identity=names[0], device=device)


def check_conversation_bytes(data: bytes) -> dict:
    """M§6.3: dsip_conversation extension data is UTF-8 JSON under §10.3, then the schema."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return reject("payload-not-utf8")
    try:
        obj = json.loads(text)
    except ValueError:
        return reject("payload-not-json")
    if not isinstance(obj, dict):
        return reject("payload-not-json")
    if has_float(obj):
        return reject("payload-float")
    return check_conversation_ext(obj)


def seal_aad(inp: dict) -> bytes:
    """AAD by use: blob none (M§8.4); activity group_id ‖ epoch (M§11.1); archive group_id ‖ seq (M§12.2)."""
    use = inp["use"]
    if use == "blob":
        return b""
    counter = inp["epoch"] if use == "activity" else inp["seq"]
    return bytes.fromhex(inp["group_hex"]) + counter.to_bytes(8, "big")


def seal(inp: dict) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key, nonce = bytes.fromhex(inp["key_hex"]), bytes.fromhex(inp["nonce_hex"])
    ct = AESGCM(key).encrypt(nonce, bytes.fromhex(inp["plaintext_hex"]), seal_aad(inp) or None)
    return {"sealed_hex": (nonce + ct).hex()}


def open_sealed(inp: dict) -> dict:
    import hashlib
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    stored = bytes.fromhex(inp["sealed_hex"])
    if inp["use"] == "blob":  # M§8.4 rule 7: size and hash before decrypting
        if len(stored) != inp["size"]:
            return reject("blob-size-mismatch")
        if hashlib.sha256(stored).hexdigest() != inp["sha256"]:
            return reject("blob-hash-mismatch")
    if len(stored) < NONCE_LEN + TAG_LEN:
        return reject("sealed-too-short")
    try:
        pt = AESGCM(bytes.fromhex(inp["key_hex"])).decrypt(stored[:NONCE_LEN], stored[NONCE_LEN:], seal_aad(inp) or None)
    except InvalidTag:
        return reject("aead-open-failed")
    return accept(plaintext_hex=pt.hex())


def registration_on_removal(inp: dict) -> dict:
    """M§5.7, M§6.6 (spec-gap 53): a group registration belongs to the identity, so a device removed from a group
    ends it (`left`) only when no leaf of its identity remains in the group."""
    return {"left": inp["me"] not in inp["remaining_identities"]}


# ---------------------------------------------------------------- first contact: HPKE and sealed introductions (M§6.9, M§14.1)

import hashlib as _hashlib
import hmac as _hmac

HPKE_KEM_ID, HPKE_KDF_ID, HPKE_AEAD_ID = 0x0020, 0x0001, 0x0001  # DHKEM(X25519, HKDF-SHA256), HKDF-SHA256, AES-128-GCM
SEALED_ALG = "hpke-base-x25519-sha256-aes128gcm"
SEALED_INFO = b"dsip sealed introduction v1"
PURPOSE_MAX_CHARS = 280  # §19.4


def _i2osp(n: int, w: int) -> bytes:
    return n.to_bytes(w, "big")


_KEM_SUITE = b"KEM" + _i2osp(HPKE_KEM_ID, 2)
_HPKE_SUITE = b"HPKE" + _i2osp(HPKE_KEM_ID, 2) + _i2osp(HPKE_KDF_ID, 2) + _i2osp(HPKE_AEAD_ID, 2)


def _labeled_extract(salt: bytes, label: bytes, ikm: bytes, suite: bytes) -> bytes:
    return _hmac.new(salt or b"\0" * 32, b"HPKE-v1" + suite + label + ikm, _hashlib.sha256).digest()


def _labeled_expand(prk: bytes, label: bytes, info: bytes, n: int, suite: bytes) -> bytes:
    labeled = _i2osp(n, 2) + b"HPKE-v1" + suite + label + info
    out, t, i = b"", b"", 1
    while len(out) < n:
        t = _hmac.new(prk, t + labeled + bytes([i]), _hashlib.sha256).digest()
        out += t
        i += 1
    return out[:n]


def _x25519(sk: bytes, pk: bytes) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    return X25519PrivateKey.from_private_bytes(sk).exchange(X25519PublicKey.from_public_bytes(pk))


def x25519_public(sk: bytes) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    return X25519PrivateKey.from_private_bytes(sk).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _shared_secret(dh: bytes, enc: bytes, pk_r: bytes) -> bytes:
    prk = _labeled_extract(b"", b"eae_prk", dh, _KEM_SUITE)
    return _labeled_expand(prk, b"shared_secret", enc + pk_r, 32, _KEM_SUITE)


def _key_schedule(shared: bytes, info: bytes) -> tuple:
    ctx = _i2osp(0, 1) + _labeled_extract(b"", b"psk_id_hash", b"", _HPKE_SUITE) + _labeled_extract(b"", b"info_hash", info, _HPKE_SUITE)
    secret = _labeled_extract(shared, b"secret", b"", _HPKE_SUITE)
    return _labeled_expand(secret, b"key", ctx, 16, _HPKE_SUITE), _labeled_expand(secret, b"base_nonce", ctx, 12, _HPKE_SUITE)


def hpke_seal(pk_r: bytes, info: bytes, aad: bytes, pt: bytes, sk_e: bytes) -> tuple:
    """RFC 9180 base mode, single shot, with the ephemeral key supplied (generator use: deterministic vectors)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    enc = x25519_public(sk_e)
    key, nonce = _key_schedule(_shared_secret(_x25519(sk_e, pk_r), enc, pk_r), info)
    return enc, AESGCM(key).encrypt(nonce, pt, aad or None)


def hpke_open(enc: bytes, sk_r: bytes, info: bytes, aad: bytes, ct: bytes):
    """RFC 9180 base mode, single shot; None when it does not open."""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        pk_r = x25519_public(sk_r)
        key, nonce = _key_schedule(_shared_secret(_x25519(sk_r, enc), enc, pk_r), info)
        return AESGCM(key).decrypt(nonce, ct, aad or None)
    except (InvalidTag, ValueError):
        return None


def hpke_derive_sk(ikm: bytes) -> bytes:
    """RFC 9180 §7.1.3 DeriveKeyPair for X25519."""
    return _labeled_expand(_labeled_extract(b"", b"dkp_prk", ikm, _KEM_SUITE), b"sk", b"", 32, _KEM_SUITE)


def x25519_from_ed25519_seed(seed: bytes) -> bytes:
    """M§6.9: the X25519 key agreement key of an Ed25519 key, as the did:key method derives it (clamped by X25519)."""
    return _hashlib.sha512(seed).digest()[:32]


def sealed_aad(p: dict) -> bytes:
    """M§14.1: id ‖ 0x00 ‖ from ‖ 0x00 ‖ to, so a sealed body cannot be spliced into another introduction."""
    return p["id"].encode() + b"\0" + p["from"].encode() + b"\0" + p["to"].encode()


def check_introduction(p: dict) -> dict:
    """M§14.1: an introduction under the profile — core §19.4 shape plus `sealed`, never both `purpose` and `sealed`."""
    from .schema import schema_errors  # the core v0.8 introduction schema carries `sealed`
    if schema_errors("introduction", p):
        return reject("schema-invalid")
    if "purpose" in p and "sealed" in p:
        return reject("introduction-purpose-and-sealed")
    if "sealed" in p and p["sealed"]["alg"] != SEALED_ALG:
        return reject("sealed-alg-unsupported")
    return accept(effective={"sealed": "sealed" in p})


def open_sealed_introduction(p: dict, recipient_seed: bytes) -> dict:
    v = check_introduction(p)
    if v["verdict"] != "accept":
        return v
    if "sealed" not in p:
        return accept(purpose=p.get("purpose"))
    sk = x25519_from_ed25519_seed(recipient_seed)
    from .crypto import b64url_decode
    pt = hpke_open(b64url_decode(p["sealed"]["enc"]), sk, SEALED_INFO, sealed_aad(p), b64url_decode(p["sealed"]["ct"]))
    if pt is None:
        return reject("sealed-open-failed")
    try:
        body = json.loads(pt)
    except ValueError:
        return reject("sealed-plaintext-invalid")
    if not isinstance(body, dict) or set(body) != {"purpose"} or not isinstance(body["purpose"], str):
        return reject("sealed-plaintext-invalid")
    if len(body["purpose"]) > PURPOSE_MAX_CHARS:
        return reject("purpose-too-long")
    return accept(purpose=body["purpose"])


# ---------------------------------------------------------------- blob endpoint (M§5.6, M§8.4)

def blob_put(inp: dict) -> dict:
    """M§5.6: what a mailbox answers to `PUT {blob_endpoint}/{sha256}` (spec-gap 48 for statuses and tokens).

    `authorization` is the verified `Authorization: DSIP` envelope — `{identity, payload}` once the envelope
    pipeline, the device's delegation and the message rules (M§5.1) have passed — or null. Checks run in the
    order a server can make them: credential, addressee, served identity, URL binding, declared size (before
    reading the body), then the body itself; a blob already stored under that hash is an idempotent success.
    """
    mbx, req, auth = inp["mailbox"], inp["request"], inp.get("authorization")
    if auth is None:
        return {"status": 401, "reason": "policy.blocked"}
    p = auth["payload"]
    if p["to"] != mbx["did"]:  # an authorization minted for another mailbox
        return {"status": 403, "reason": "policy.blocked"}
    if auth["identity"] not in mbx["serves"]:  # M§5.6: the device must be delegated by an identity it serves
        return {"status": 403, "reason": "transport.unknown-recipient"}
    if req["path_sha256"] != p["sha256"]:  # the URL names the authorized blob
        return {"status": 400, "reason": "policy.blocked"}
    if p["size"] > mbx["max_blob_bytes"]:  # M§16
        return {"status": 413, "reason": "mailbox.object-too-large"}
    # spec-gap 99: the owner's quota, from the authorized size before the body is read; a hash already stored stores
    # nothing more, so it is never refused for quota (and is answered as the idempotent duplicate below)
    if (mbx.get("quota_bytes") is not None and p["sha256"] not in inp.get("stored", [])
            and mbx.get("used_bytes", 0) + p["size"] > mbx["quota_bytes"]):
        return {"status": 507, "reason": "mailbox.quota-exceeded"}
    if req["body_size"] != p["size"] or req["body_sha256"] != p["sha256"]:  # M§5.6
        return {"status": 400, "reason": "mailbox.blob-mismatch"}
    if p["sha256"] in inp.get("stored", []):
        return {"status": 200, "accepted": {"in_reply_to": p["id"], "duplicate": True}}
    return {"status": 201, "accepted": {"in_reply_to": p["id"]}}


def blob_get(inp: dict) -> dict:
    """M§8.4 rule 5: the hash is a capability; the mailbox serves exactly what it stored under it."""
    return {"status": 200 if inp["path_sha256"] in inp.get("stored", []) else 404}


def blob_replicate(inp: dict) -> dict:
    """M§8.4 rule 6 (spec-gap 65): whether a member mailbox replicates a manifest blob, and whether it keeps what it fetched.

    Without `fetched`: `fetch`, or `skip` with a reason — the owner's mode is not `sync`, the blob is already stored,
    it is larger than this mailbox's `max_blob_bytes`, or its `uri` is not https. With `fetched` (`{status, sha256,
    size}` of the response body): `store` only for a 200 whose body matches the manifest's `sha256` and `size`,
    otherwise `discard` (the item keeps the original `uri`).
    """
    e = inp["entry"]
    max_attempts = inp.get("max_attempts", BLOB_REPLICATION_ATTEMPTS)
    if "fetched" not in inp:
        if inp.get("mode") != "sync":
            return {"action": "skip", "reason": "mode"}
        if e["sha256"] in inp.get("stored", []):
            return {"action": "skip", "reason": "stored"}
        if e["size"] > inp["max_blob_bytes"]:
            return {"action": "skip", "reason": "too-large"}
        if not str(e.get("uri", "")).startswith("https://"):
            return {"action": "skip", "reason": "not-https"}
        return {"action": "fetch"}
    f = inp["fetched"]
    if f.get("status") != 200:
        # spec-gap 67: the origin was unreachable or had nothing to serve — worth trying again, boundedly
        return {"action": "discard", "reason": "unavailable", "retry": inp.get("attempt", 1) < max_attempts}
    if f.get("sha256") != e["sha256"] or f.get("size") != e["size"]:
        # the origin served something else: retrying fetches the same wrong bytes
        return {"action": "discard", "reason": "mismatch", "retry": False}
    return {"action": "store"}


BLOB_REPLICATION_ATTEMPTS = 5   # spec-gap 67


def blob_fetch(inp: dict) -> dict:
    """M§8.4 "Fetching" (spec-gap 106): what a device does after trying a content's blob sources in order.

    `tried` holds each source's result `{uri, status, sha256?, size?}`. The first 200 whose body matches the
    content's `blob` `sha256` and `size` is played. Otherwise, if any source had nothing to serve (not 200) the fetch
    is tried again, boundedly, like a mailbox's replication (spec-gap 67); if every source served the wrong bytes it
    is given up at once, since they would serve the same bytes again.
    """
    b = inp["blob"]
    for t in inp.get("tried", []):
        if t.get("status") == 200 and t.get("sha256") == b["sha256"] and t.get("size") == b["size"]:
            return {"action": "play", "source": t["uri"]}
    if any(t.get("status") != 200 for t in inp.get("tried", [])) or not inp.get("tried"):
        more = inp.get("attempt", 1) < inp.get("max_attempts", BLOB_REPLICATION_ATTEMPTS)
        return {"action": "retry" if more else "give-up", "reason": "unavailable"}
    return {"action": "give-up", "reason": "mismatch"}


def items_blobs(inp: dict) -> dict:
    """M§8.4 rule 6 (spec-gap 65): the `blobs` manifest a mailbox puts in `items` — `uri` rewritten to its own blob
    endpoint for every blob it holds, unchanged otherwise."""
    out = []
    for e in inp["manifest"]:
        e = dict(e)
        if e["sha256"] in inp.get("stored", []):
            e["uri"] = inp["blob_endpoint"].rstrip("/") + "/" + e["sha256"]
        out.append(e)
    return {"blobs": out}


def blob_sources(inp: dict) -> dict:
    """M§8.4 rules 6–7 (spec-gap 65): where a device fetches a content blob from, in order. A manifest entry for the
    same `sha256` and `size` at another `uri` (its own mailbox's copy) comes first, then the `uri` in the content
    object. Either way the device verifies `sha256` and `size` before decrypting."""
    b = inp["blob"]
    first = [e["uri"] for e in inp.get("manifest") or []
             if e.get("sha256") == b["sha256"] and e.get("size") == b["size"] and e.get("uri") != b["uri"]]
    return {"sources": first[:1] + [b["uri"]]}


# ---------------------------------------------------------------- discovery (M§4.2, §8.1)

def select_mailbox(inp: dict) -> dict:
    """M§4.2: the DID document is authoritative; hints serve only identities with no document entry.

    Entries are usable when they satisfy the service schema (wss, bindings, mailbox DID) and
    advertise `messaging/1.0`. Order is by `priority` (absent = 0), stable within a priority. The
    selected mailbox is the first usable one that accepts a connection; the owner's devices sync
    every usable one.
    """
    doc, hints = inp.get("document_entries") or [], inp.get("hint_entries") or []
    source = "did-document" if doc else ("hint" if hints else None)
    entries = doc or hints                      # §8.1 rule 6: no falling back to hints past a document
    usable, discarded = [], []
    for e in entries:
        if not schema_ok("mailbox-service", e) or MESSAGING_PROFILE not in (e.get("profiles") or []):
            discarded.append(e.get("uri"))
        else:
            usable.append(e)
    usable.sort(key=lambda e: e.get("priority", 0))   # Python's sort is stable
    order = [e["mailbox"] for e in usable]
    reachable = inp.get("reachable")
    selected = next((m for m in order if reachable is None or m in reachable), None)
    return {"source": source, "selected": selected, "order": order, "sync_targets": order, "discarded": discarded}


def mailbox_switch(inp: dict) -> dict:
    """M§4.2, M§15.4: an established conversation's mailbox never moves on a hint alone."""
    established, candidate = inp["established"], inp["candidate"]
    if candidate["mailbox"] == established["mailbox"]:
        return {"switch": False, "reason": "unchanged"}
    if candidate.get("source") != "did-document":
        return {"switch": False, "reason": "hint-sourced"}
    return {"switch": True, "reason": "did-document"}


# ---------------------------------------------------------------- runner

def run(v: dict) -> dict:
    inp = v["input"]
    check = inp.get("check")
    if check == "payload":
        name = inp["schema"]
        return accept() if schema_ok(name, inp["payload"]) else reject("schema-invalid")
    if check == "message":
        return check_message(inp["payload"])
    if check == "object":
        return check_object(inp["object"], v["context"])
    if check == "conversation-ext":
        return check_conversation_ext(inp["extension"])
    if check == "conversation-update":
        return check_conversation_update(inp["before"], inp["after"])
    if check == "mailbox-select":
        return select_mailbox(inp)
    if check == "mailbox-switch":
        return mailbox_switch(inp)
    if check == "mls-extension-encode":
        return {"hex": encode_extension(inp["extension_type"], bytes.fromhex(inp["data_hex"])).hex()}
    if check == "mls-extension-decode":
        return decode_extension(bytes.fromhex(inp["hex"]))
    if check == "mls-credential":
        return check_mls_credential(inp, v["context"])
    if check == "mls-conversation-bytes":
        return check_conversation_bytes(bytes.fromhex(inp["data_hex"]))
    if check == "seal":
        return seal(inp)
    if check == "open":
        return open_sealed(inp)
    if check == "hpke-open":
        pt = hpke_open(bytes.fromhex(inp["enc_hex"]), bytes.fromhex(inp["sk_r_hex"]), bytes.fromhex(inp["info_hex"]),
                       bytes.fromhex(inp["aad_hex"]), bytes.fromhex(inp["ct_hex"]))
        return reject("hpke-open-failed") if pt is None else accept(plaintext_hex=pt.hex())
    if check == "hpke-derive-key-pair":
        sk = hpke_derive_sk(bytes.fromhex(inp["ikm_hex"]))
        return {"sk_hex": sk.hex(), "pk_hex": x25519_public(sk).hex()}
    if check == "x25519-key-agreement":
        sk = x25519_from_ed25519_seed(bytes.fromhex(inp["ed25519_seed_hex"]))
        return {"x25519_pk_hex": x25519_public(sk).hex()}
    if check == "introduction":
        return check_introduction(inp["payload"])
    if check == "sealed-introduction-open":
        return open_sealed_introduction(inp["payload"], bytes.fromhex(inp["recipient_ed25519_seed_hex"]))
    if check == "registration-on-removal":
        return registration_on_removal(inp)
    if check == "blob-put":
        return blob_put(inp)
    if check == "blob-fetch":
        return blob_fetch(inp)
    if check == "blob-replicate":
        return blob_replicate(inp)
    if check == "items-blobs":
        return items_blobs(inp)
    if check == "blob-sources":
        return blob_sources(inp)
    if check == "blob-get":
        return blob_get(inp)
    if check == "voicemail-offer":
        return voicemail_offer(inp)
    if check == "direct-select":
        return select_direct(inp["candidates"])
    if check == "call-event":
        return call_event_decision(inp)
    if check == "peer-timeline":
        return peer_timeline(inp)
    if check == "external-join":
        return check_external_join(inp)
    if check == "leave-proposals":
        return leave_proposals(inp)
    if check == "roster-change":
        return check_roster_change(inp)
    if check == "successor-check":
        return check_successor(inp)
    if check == "successor-select":
        return select_successor(inp["candidates"])
    if check == "items-pages":
        return items_pages(v)
    if check in ("hub-trace", "mailbox-trace", "client-trace", "gap-trace", "resume-trace", "history-trace", "commit-retry-trace",
                 "successor-trace", "hub-outage-trace", "move-arrival-trace", "enrolment-trace"):
        comp = {"hub-trace": Hub, "mailbox-trace": Mailbox, "client-trace": Client, "gap-trace": GapTracker,
                "resume-trace": Resume, "history-trace": History, "commit-retry-trace": CommitRetry,
                "successor-trace": SuccessorTracker, "hub-outage-trace": HubOutage,
                "move-arrival-trace": MoveArrival, "enrolment-trace": Enrolment}[check](v["context"])
        steps = []
        for st in inp["steps"]:
            emit = comp.step(st["event"])
            steps.append({"emit": emit, "state": comp.snapshot()})
        return {"steps": steps}
    return {"error": f"unknown messaging check {check}"}
