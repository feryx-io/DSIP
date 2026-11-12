"""`messaging/` vectors — DSIP Messaging Profile 1.0 (v0.8 draft, cited M§n), tranche 1: message and
object shapes and stateless rules, hub traces and mailbox traces. Expectations are authored by hand
from the profile text; `dsipvec.messaging` and `dsip-messaging` must both reproduce them."""
from __future__ import annotations

import copy
import hashlib
import json

from .. import fixtures as F
from ..crypto import b64url_encode
from .common import NOW, uid, vector, accept, reject

VERSION = {"core": "1.0", "min_core": "1.0", "profiles": ["messaging/1.0"], "extensions": [], "critical": []}
ALICE, BOB, CAROL, MALLORY = "did:web:alice.example", F.BOB_WEB, "did:web:carol.example", "did:web:mallory.example"
APH, ALA, BPH, BLA = F.did("alice-phone"), F.did("alice-laptop"), F.did("bob-phone"), F.did("bob-laptop")
BTAB, CPH, MPH = "did:key:z6MkBobTablet", F.did("carol-phone"), F.did("mallory")
HUB_A, MBX_B = "did:web:mbx.alice.example", "did:web:mbx.bob.example"
GROUP = b64url_encode(uid("group-1").encode())
GROUP2 = b64url_encode(uid("group-2").encode())
CONV = uid("conversation-1")
SHA = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
KEY32 = b64url_encode(bytes(range(32)))
MLS = b64url_encode(b"\x00\x01mls-message")


def mv(vid, desc, refs, inp, expect, ctx=None):
    return vector(f"messaging/{vid}", "messaging", desc, refs, ctx or {}, inp, expect)


def trace(vid, desc, refs, check, ctx, steps):
    """steps: (event, emit, state) triples, all authored by hand."""
    return mv(vid, desc, refs, {"check": check, "steps": [{"event": e} for e, _, _ in steps]},
              {"steps": [{"emit": em, "state": st} for _, em, st in steps]}, ctx=ctx)


def c(n: int) -> str:
    return f"c:{n:016x}"


# ---------------------------------------------------------------- payload builders

def msg(t, label, frm, to, ttl=30, at=NOW, **fields):
    p = {"dsip": copy.deepcopy(VERSION), "type": t, "id": uid(label, at), "from": frm, "to": to}
    p.update(fields)
    p["issued_at"], p["expires_at"] = at, at + ttl
    return p


def deposit(label="dep", cls="application", ttl=30, **fields):
    base = {"group": GROUP, "class": cls}
    if cls in ("handshake", "application", "welcome", "group-info"):
        base["mls"] = MLS
    base.update(fields)
    return msg("deposit", label, APH, HUB_A, ttl=ttl, **base)


def content(label="m1", kind="text", purpose="message", at=NOW, sender=ALICE, **fields):
    o = {"object": "content", "id": uid(label, at), "conversation": CONV, "sender": sender, "sent_at": at,
         "kind": kind, "purpose": purpose}
    if kind == "text" and "text" not in fields:
        o["content_type"], o["text"] = "text/plain", "Dinner at 7?"
    o.update(fields)
    return o


def blob(**over):
    b = {"uri": f"https://mbx.alice.example/blobs/{SHA}", "sha256": SHA, "size": 482220, "key": KEY32,
         "alg": "A256GCM", "content_type": "audio/ogg; codecs=opus"}
    b.update(over)
    return b


OBJ_CTX = {"conversation": CONV, "conversation_kind": "direct", "leaf_identity": ALICE}


def vectors() -> list[dict]:
    out = []
    out += message_vectors()
    out += object_vectors()
    out += hub_vectors()
    out += mailbox_vectors()
    out += voicemail_offer_vectors()
    out += conversation_vectors()
    out += client_vectors()
    out += gap_vectors()
    out += history_vectors()
    out += commit_retry_vectors()
    out += resume_vectors()
    out += items_pages_vectors()
    out += mls_layer_vectors()
    out += discovery_vectors()
    out += blob_vectors()
    out += removal_registration_vectors()
    out += first_contact_vectors()
    out += revocation_vectors()
    out += restart_vectors()
    out += hub_change_vectors()
    out += hub_outage_vectors()
    out += move_arrival_vectors()
    out += enrolment_vectors()
    out += successor_vectors()
    out += external_join_vectors()
    out += leave_vectors()
    out += roster_change_vectors()
    out += call_history_vectors()
    out += blob_replication_vectors()
    return out


# ---------------------------------------------------------------- messages (M§5)

def message_vectors():
    out = []

    def m(vid, desc, refs, payload, expect):
        out.append(mv(vid, desc, refs, {"check": "message", "payload": payload}, expect))

    m("deposit-application-valid", "Application deposit with an MLS message and a blob manifest.", ["M§5.2"],
      deposit(blobs=[{"uri": f"https://mbx.alice.example/blobs/{SHA}", "sha256": SHA, "size": 482220}]), accept())
    m("deposit-unknown-class-refused", "Deposit class is structural: an unregistered class is refused, not ignored.",
      ["M§5.2", "M§16"], deposit(cls="telemetry", sealed="AAAA"), reject("deposit-class-unsupported", "mailbox.unsupported-class"))
    m("deposit-lifetime-over-60s", "Profile messages are delivery envelopes: validity over 60 s is refused.", ["M§5.1"],
      deposit(ttl=61), reject("lifetime-exceeded"))
    m("deposit-ephemeral-valid", "Ephemeral deposit with sealed activity and a 10 s lifetime.", ["M§5.2", "M§11.2"],
      deposit(cls="ephemeral", ttl=10, sealed="c2VhbGVkLWFjdGl2aXR5"), accept())
    m("deposit-ephemeral-lifetime-over-10s", "Ephemeral activity may not outlive 10 s on the wire.", ["M§11.2"],
      deposit(cls="ephemeral", ttl=11, sealed="c2VhbGVkLWFjdGl2aXR5"), reject("lifetime-exceeded"))
    m("deposit-ephemeral-with-mls-refused", "Ephemeral activity never travels in the MLS secret tree.", ["M§5.2", "M§11.1"],
      deposit(cls="ephemeral", ttl=10, sealed="c2VhbGVk", mls=MLS), reject("deposit-fields"))
    m("deposit-application-with-archive-refused", "An application deposit may not carry archive fields.", ["M§5.2"],
      deposit(archive="YXJjaGl2ZQ"), reject("deposit-fields"))
    m("deposit-welcome-missing-hub", "A welcome must name the group's hub so the mailbox can register it.", ["M§5.2", "M§6.6"],
      deposit(cls="welcome"), reject("deposit-fields"))
    m("deposit-welcome-valid", "Hub-forwarded welcome with hub, grant and origin.", ["M§5.2", "M§14.2"],
      deposit(cls="welcome", recipient=BOB, hub={"did": HUB_A, "uri": "wss://mbx.alice.example/dsip"},
              grants=["eyJ.grant.sig"], origin="eyJ.origin.sig"), accept())
    blob = {"uri": "https://mbx.alice.example/blobs/" + "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "size": 482220}
    m("deposit-application-fanout-valid", "A hub's fan-out to a member mailbox: `recipient` and `seq` belong to the addressing, not to a class.",
      ["M§5.2", "M§6.5"], deposit("fanout", recipient=BOB, seq=7), accept())
    m("deposit-handshake-with-blobs-refused", "The blob manifest names what content references: a handshake carries no content.",
      ["M§5.2", "M§8.4"], deposit("hs-blobs", cls="handshake", blobs=[blob]), reject("deposit-fields"))
    m("deposit-welcome-ratchet-tree-blob-valid", "A welcome too large to inline its ratchet tree names the tree blob (M§6.4).",
      ["M§5.2", "M§6.4"], deposit("w-tree", cls="welcome", recipient=BOB, hub={"did": HUB_A, "uri": "wss://mbx.alice.example/dsip"},
                                  ratchet_tree_blob=blob), accept())
    m("deposit-group-info-ratchet-tree-blob-valid", "A GroupInfo for external joins may name the tree blob the same way.",
      ["M§5.2", "M§6.4", "M§6.8"], deposit("gi-tree", cls="group-info", ratchet_tree_blob=blob), accept())
    m("deposit-welcome-with-seq-valid", "A hub-forwarded welcome carries the seq of the commit that added the device: where the "
      "new member starts counting the group (spec-gap 83). Before it, a welcome with a seq was refused.", ["M§5.2", "M§6.5"],
      deposit("w-seq", cls="welcome", recipient=BOB, hub={"did": HUB_A, "uri": "wss://mbx.alice.example/dsip"}, seq=3), accept())
    m("deposit-ephemeral-with-seq-refused", "Activity is never sequenced (M§11.2): an ephemeral deposit carries no seq.", ["M§5.2", "M§11.2"],
      deposit("e-seq", cls="ephemeral", ttl=10, sealed="c2VhbGVk", seq=3), reject("deposit-fields"))
    m("deposit-archive-valid", "Archive deposit with akid and item reference.", ["M§5.2", "M§12.2"],
      msg("deposit", "arch", BPH, MBX_B, group=GROUP, **{"class": "archive"}, archive="YXJjaGl2ZQ",
          akid=uid("akid-1"), ref_group=GROUP, ref_seq=42), accept())
    m("deposit-archive-missing-akid", "An archive item without its archive key id cannot be decrypted later.", ["M§5.2", "M§12.2"],
      msg("deposit", "arch2", BPH, MBX_B, group=GROUP, **{"class": "archive"}, archive="YXJjaGl2ZQ",
          ref_group=GROUP, ref_seq=42), reject("deposit-fields"))
    m("deposit-mls-at-cap-accepted", "An MLS value of exactly 24,576 decoded bytes fits.", ["M§5.1"],
      deposit(mls=b64url_encode(b"\x00" * 24576)), accept())
    m("deposit-mls-over-cap-refused", "An MLS value one byte over 24,576 decoded bytes must go by blob.", ["M§5.1", "M§8.3"],
      deposit(mls=b64url_encode(b"\x00" * 24577)), reject("object-too-large", "mailbox.object-too-large"))
    m("sync-valid", "Sync from a cursor with an acknowledgement and live push.", ["M§5.4"],
      msg("sync", "sync", BPH, MBX_B, since=c(3), ack_through=c(3), limit=200, live=True), accept())
    m("sync-limit-over-1000", "sync.limit is capped at 1000.", ["M§5.4"],
      msg("sync", "sync2", BPH, MBX_B, since=None, limit=1001), reject("schema-invalid"))
    m("items-valid", "Items response with one application item.", ["M§5.4"],
      msg("items", "items", MBX_B, BPH, in_reply_to=uid("sync"), next=None,
          items=[{"cursor": c(4), "stored_at": NOW, "class": "application", "source": HUB_A, "group": GROUP, "seq": 42, "mls": MLS}]),
      accept())
    eph = {"class": "ephemeral", "source": HUB_A, "group": GROUP, "sealed": MLS, "expires_at": NOW + 10}
    m("items-ephemeral-push-valid", "A pushed ephemeral item: sealed activity with the originating expires_at, no cursor.",
      ["M§5.4", "M§11.2"], msg("items", "itp", MBX_B, BPH, next=None, items=[eph]), accept())
    m("items-ephemeral-with-cursor-refused", "An ephemeral item is never stored, so it cannot carry a cursor.",
      ["M§11.2"], msg("items", "itc", MBX_B, BPH, next=None, items=[{**eph, "cursor": c(4)}]), reject("schema-invalid"))
    m("items-ephemeral-without-expiry-refused", "A pushed ephemeral item must carry the expires_at its receiver clears it at.",
      ["M§11.2"], msg("items", "ite", MBX_B, BPH, next=None, items=[{k: v for k, v in eph.items() if k != "expires_at"}]),
      reject("schema-invalid"))
    m("items-stored-class-ephemeral-refused", "A stored item cannot claim class ephemeral.",
      ["M§11.2"], msg("items", "its", MBX_B, BPH, next=None,
                      items=[{"cursor": c(4), "stored_at": NOW, "class": "ephemeral", "source": HUB_A, "group": GROUP}]),
      reject("schema-invalid"))
    m("accepted-valid", "Hub acceptance with seq.", ["M§5.3"],
      msg("accepted", "acc", HUB_A, APH, in_reply_to=uid("dep"), group=GROUP, seq=42), accept())
    m("key-packages-upload-valid", "KeyPackage upload with a last resort.", ["M§5.5"],
      msg("key-packages", "kpu", BPH, MBX_B, subject=BOB, key_packages=[MLS, MLS], last_resort=MLS), accept())
    m("key-packages-empty-refused", "A key-packages message must carry at least one KeyPackage.", ["M§5.5"],
      msg("key-packages", "kpe", BPH, MBX_B, subject=BOB, key_packages=[]), reject("key-packages-empty"))
    m("key-package-fetch-valid", "Fetch with a grant.", ["M§5.5", "M§14.2"],
      msg("key-package-fetch", "kpf", CPH, MBX_B, target=BOB, grant="eyJ.grant.sig"), accept())
    m("blob-put-valid", "Blob upload authorization.", ["M§5.6"],
      msg("blob-put", "bp", APH, HUB_A, ttl=60, sha256=SHA, size=482220), accept())
    m("blob-put-uppercase-sha-refused", "sha256 is lowercase hex.", ["M§5.6"],
      msg("blob-put", "bp2", APH, HUB_A, sha256=SHA.upper(), size=482220), reject("schema-invalid"))
    m("mailbox-config-valid", "Mode, admit, group confirmation and a revoked grant.", ["M§5.7"],
      msg("mailbox-config", "cfg", BPH, MBX_B, subject=BOB, mode="sync", admit="grant",
          groups=[{"group": GROUP, "hub": HUB_A, "state": "joined"}], revoked_grants=[uid("grant-x")]), accept())
    m("mailbox-config-introductions-sent-valid", "An owner device tells its mailbox which introductions it sent, so their grants are not rate-limited.",
      ["M§5.7", "M§14.1"], msg("mailbox-config", "cfg-is", BPH, MBX_B, subject=BOB, introductions_sent=[uid("intro-out")]), accept())
    m("mailbox-config-introductions-sent-not-ulid-refused", "introductions_sent holds introduction ids: ULIDs.",
      ["M§5.7"], msg("mailbox-config", "cfg-is2", BPH, MBX_B, subject=BOB, introductions_sent=["01HZINTROABC"]), reject("schema-invalid"))
    m("mailbox-config-unknown-mode-refused", "An unregistered mailbox mode is refused.", ["M§4.4", "M§16"],
      msg("mailbox-config", "cfg2", BPH, MBX_B, subject=BOB, mode="archive-forever"),
      reject("mailbox-mode-unsupported", "mailbox.unsupported-mode"))
    m("mailbox-config-admit-invalid", "admit is grant or open.", ["M§5.7"],
      msg("mailbox-config", "cfg3", BPH, MBX_B, subject=BOB, admit="anyone"), reject("schema-invalid"))
    return out


# ---------------------------------------------------------------- objects (M§8, M§10–M§13)

def object_vectors():
    out = []

    def o(vid, desc, refs, obj, expect, ctx=None):
        out.append(mv(vid, desc, refs, {"check": "object", "object": obj}, expect, ctx=ctx or OBJ_CTX))

    o("content-text-valid", "Plain text message.", ["M§8.1", "M§8.2"], content(),
      accept(effective={"kind": "text", "purpose": "message"}))
    o("content-sender-not-leaf-identity", "content.sender must be the identity of the MLS sender leaf.", ["M§8.1", "M§6.2"],
      content(sender=BOB), reject("sender-mismatch"))
    o("content-wrong-conversation", "content.conversation must match the group's dsip_conversation.", ["M§8.1", "M§6.3"],
      content(conversation=uid("other-conv")), reject("conversation-mismatch"))
    o("content-ulid-sent-at-mismatch", "Content id timestamp more than 300 s from sent_at.", ["M§8.1", "§20.6"],
      {**content(), "id": uid("m-backdated", NOW - 3600)}, reject("ulid-sent-at-mismatch"))
    o("content-location-valid", "Location uses integer degrees × 10⁷.", ["M§8.2", "§10.3"],
      content("loc", kind="location", lat_e7=430481000, lon_e7=-761474000, accuracy_m=20),
      accept(effective={"kind": "location", "purpose": "message"}))
    o("content-location-float-refused", "A float coordinate violates §10.3 inside MLS plaintext too.", ["M§8.2", "§10.3"],
      content("locf", kind="location", lat_e7=43.0481, lon_e7=-76.1474), reject("payload-float"))
    ev = {"source": {"address": "192.0.2.7", "basis": "snmpv2c"},
          "alarm": {"resource": "192.0.2.7/3", "type": "link-down", "qualifier": "", "severity": "major", "cleared": False}}
    GW_CTX = {**OBJ_CTX, "leaf_capabilities": ["dsip.messaging", "dsip.events"]}  # a gateway's leaf (E§2)
    DEV = {"kind": "device-event", "purpose": "message"}
    o("content-device-event-valid", "A Device Events Profile `device-event` (v0.9, E§5) is a registered kind, from a gateway "
      "(its leaf's delegation carries `dsip.events`, E§2).", ["M§8.2", "E§5", "E§2"],
      content("dev", kind="device-event", event=ev), accept(effective=DEV), ctx=GW_CTX)
    o("content-device-event-without-capability", "A `device-event` from a device whose delegation lacks `dsip.events` is refused: "
      "only a gateway raises alarms (spec-gap 165).", ["E§2"],
      content("dev-nocap", kind="device-event", event=ev), reject("delegation-capability"),
      ctx={**OBJ_CTX, "leaf_capabilities": ["dsip.messaging"]})
    o("content-device-event-capabilities-absent", "No `leaf_capabilities` in the context is no capabilities (spec-gap 165).",
      ["E§2"], content("dev-nocap2", kind="device-event", event=ev), reject("delegation-capability"))
    o("content-device-event-without-event", "A `device-event` must carry `event`; `content-body` comes before the capability "
      "check.", ["M§8.2", "E§5"], content("dev0", kind="device-event"), reject("content-body"))

    def body(vid, desc, event, expect):  # spec-gap 166: E§5 Bodies, from a gateway
        o(vid, desc, ["E§5"], content(vid, kind="device-event", event=event), expect, ctx=GW_CTX)
    src = {"address": "192.0.2.7", "basis": "snmpv2c"}
    clear = {"resource": "192.0.2.7/3", "type": "link-down", "qualifier": "", "severity": None, "cleared": True}
    body("content-device-event-heartbeat-valid", "A heartbeat needs no `source`: its sender is the gateway itself.",
         {"heartbeat": {"interval_s": 60}}, accept(effective=DEV))
    body("content-device-event-clear-severity-null-valid", "A clear's severity is `null`.",
         {"source": src, "alarm": clear}, accept(effective=DEV))
    body("content-device-event-unknown-members-valid", "Unknown members are ignored, and tokens are not checked against "
         "their registries (an unknown basis renders as unauthenticated, E§2).",
         {"source": {"address": "192.0.2.7", "basis": "carrier-pigeon"}, "vendor": {"x": 1},
          "alarm": {**clear, "type": "smoke", "severity": "catastrophic", "cleared": False, "text": "smoke", "extra": True}},
         accept(effective=DEV))
    body("content-device-event-event-not-object", "`event` is an object.", "link down", reject("content-body"))
    body("content-device-event-without-source", "`source` is required unless `heartbeat` is present.",
         {"alarm": clear}, reject("content-body"))
    body("content-device-event-address-empty", "`source.address` is a non-empty string.",
         {"source": {"address": "", "basis": "snmpv2c"}}, reject("content-body"))
    body("content-device-event-basis-not-string", "`source.basis` is a string.",
         {"source": {"address": "192.0.2.7", "basis": 2}}, reject("content-body"))
    body("content-device-event-cleared-not-boolean", "`alarm.cleared` is a boolean.",
         {"source": src, "alarm": {**clear, "cleared": "true"}}, reject("content-body"))
    body("content-device-event-alarm-without-type", "`alarm.type` is required and non-empty.",
         {"source": src, "alarm": {**clear, "type": ""}}, reject("content-body"))
    body("content-device-event-qualifier-not-string", "`alarm.qualifier`, when present, is a string.",
         {"source": src, "alarm": {**clear, "qualifier": 3}}, reject("content-body"))
    body("content-device-event-heartbeat-interval-zero", "`heartbeat.interval_s` is an integer, at least 1.",
         {"heartbeat": {"interval_s": 0}}, reject("content-body"))
    body("content-device-event-raw-not-object", "`raw`, when present, is an object.",
         {"source": src, "raw": "trap"}, reject("content-body"))
    ALARM = {"resource": "192.0.2.7/3", "type": "link-down", "qualifier": ""}
    ACK = {"kind": "alarm-ack", "purpose": "message"}
    o("content-alarm-ack-valid", "An `alarm-ack` (E§5) names the alarm and the operator state; it needs no capability (E§2).",
      ["M§8.2", "E§5", "E§2"], content("ack", kind="alarm-ack", alarm=ALARM, state="ack"), accept(effective=ACK))
    o("content-alarm-ack-without-state", "An `alarm-ack` must carry `state`.", ["M§8.2", "E§5"],
      content("ack0", kind="alarm-ack", alarm=ALARM), reject("content-body"))
    o("content-alarm-ack-unknown-state-valid", "An unknown `state` is accepted; the alarm list ignores it (spec-gap 166).",
      ["E§5"], content("ack-shelved", kind="alarm-ack", alarm=ALARM, state="shelved"), accept(effective=ACK))
    o("content-alarm-ack-state-not-string", "`state` is a string.", ["E§5"],
      content("ack-num", kind="alarm-ack", alarm=ALARM, state=1), reject("content-body"))
    o("content-alarm-ack-without-resource", "The acknowledged `alarm` names its `resource`.", ["E§5"],
      content("ack-nores", kind="alarm-ack", alarm={"type": "link-down"}, state="ack"), reject("content-body"))
    o("content-unknown-kind-with-blob-is-file", "Unknown kind carrying a blob is offered as a file.", ["M§8.2"],
      content("hol", kind="hologram", blob=blob(content_type="model/gltf-binary")),
      accept(effective={"kind": "file", "purpose": "message"}))
    o("content-unknown-kind-without-blob-is-unsupported", "Unknown kind with no blob renders as an unsupported-message placeholder.",
      ["M§8.2"], content("poll", kind="poll", question="Pizza?"), accept(effective={"kind": "unsupported", "purpose": "message"}))
    o("content-unknown-purpose-is-message", "Unknown purpose is handled as message.", ["M§8.2"],
      content("pp", purpose="sticker"), accept(effective={"kind": "text", "purpose": "message"}))
    o("content-audio-missing-blob", "Audio content must carry its blob and duration.", ["M§8.2"],
      content("au", kind="audio", purpose="voice-message", duration_ms=5000), reject("content-body"))
    o("content-blob-key-wrong-length", "A blob key is exactly 32 bytes (43 base64url characters).", ["M§8.4"],
      content("au2", kind="audio", purpose="voice-message", duration_ms=5000, blob=blob(key=KEY32[:40])), reject("schema-invalid"))
    o("content-reaction-valid", "Reaction: one emoji replying to a target.", ["M§8.2"],
      content("r1", purpose="reaction", text="👍", reply_to=uid("m1")), accept(effective={"kind": "text", "purpose": "reaction"}))
    o("content-reaction-too-long", "A reaction text over 32 bytes is not a reaction.", ["M§8.2"],
      content("r2", purpose="reaction", text="👍" * 9, reply_to=uid("m1")), reject("reaction-invalid"))
    o("content-reaction-without-target", "A reaction must reply to a target.", ["M§8.2"],
      content("r3", purpose="reaction", text="👍", reply_to=None), reject("reaction-invalid"))
    o("content-voicemail-valid", "Voicemail: audio with blob, duration and the invite id.", ["M§13.1", "M§13.2"],
      content("vm", kind="audio", purpose="voicemail", duration_ms=28400, blob=blob(), session=uid("invite-1")),
      accept(effective={"kind": "audio", "purpose": "voicemail"}))
    o("content-voicemail-missing-session", "A voicemail names the unanswered session.", ["M§13.2"],
      content("vm2", kind="audio", purpose="voicemail", duration_ms=28400, blob=blob()), reject("content-body"))
    rc = {"object": "receipt", "id": uid("rc"), "conversation": CONV, "sender": ALICE, "sent_at": NOW}
    o("receipt-read-watermark-valid", "Read receipt is a per-conversation watermark.", ["M§10.3"],
      {**rc, "kind": "read", "through": uid("m1")}, accept(effective={"receipt": "read"}))
    o("receipt-read-with-targets-refused", "A read watermark carries through, not targets.", ["M§10.3"],
      {**rc, "kind": "read", "through": uid("m1"), "targets": [uid("m1")]}, reject("receipt-shape"))
    o("receipt-delivered-without-targets-refused", "delivered names its targets.", ["M§10.2"],
      {**rc, "kind": "delivered"}, reject("receipt-shape"))
    o("receipt-unknown-kind-ignored", "Unknown receipt kinds are ignored, never errors.", ["M§10", "M§17"],
      {**rc, "kind": "seen-by-ai", "targets": [uid("m1")]}, accept(effective={"render": "ignore"}))
    act = {"object": "activity", "conversation": CONV, "sender": ALICE, "state": "active"}
    o("activity-typing-valid", "Typing indicator.", ["M§11.1"], {**act, "activity": "typing"}, accept(effective={"activity": "typing"}))
    o("activity-unknown-is-generic", "Unknown activity renders as a generic active indicator.", ["M§11.1"],
      {**act, "activity": "drawing"}, accept(effective={"activity": "active"}))
    ak = {"object": "archive-key", "akid": uid("akid-1"), "key": KEY32, "created_at": NOW}
    o("archive-key-in-personal-group", "Archive keys travel in the personal group.", ["M§12.1"], ak, accept(),
      ctx={**OBJ_CTX, "conversation_kind": "personal"})
    o("archive-key-outside-personal-group-refused", "An archive key in a direct conversation would disclose it to the peer.",
      ["M§12.1"], ak, reject("personal-group-only"))
    ra = {"object": "recording-acceptance", "conversation": uid("rec-conv"), "recorders": ["did:key:z6MkBobRecorder"], "accepted_at": NOW}
    o("recording-acceptance-in-personal-group", "A recording acceptance travels in the personal group, to the identity's "
      "other devices (Recording Profile C§5).", ["C§5", "M§8.1"], ra, accept(), ctx={**OBJ_CTX, "conversation_kind": "personal"})
    o("recording-acceptance-outside-personal-group-refused", "A recording acceptance outside the personal group is refused.",
      ["C§5", "M§8.1"], ra, reject("personal-group-only"))
    o("recording-acceptance-no-recorders", "An acceptance must name at least one recorder.", ["C§5"],
      {**ra, "recorders": []}, reject("schema-invalid"), ctx={**OBJ_CTX, "conversation_kind": "personal"})
    # Recording Profile C§9 (v0.13, spec-gap 121): a call record, in the direct conversation with the record-keeper
    rc_ctx = {**OBJ_CTX, "leaf_device": "did:key:z6MkAlicePhone"}
    rc = {"object": "call-record", "session": uid("rec-call"), "device": "did:key:z6MkAlicePhone", "direction": "outbound",
          "peer": CAROL, "relay": "did:web:relay.alice.example", "invited_at": NOW, "answered_at": NOW + 4,
          "ended_at": NOW + 310, "outcome": "answered", "ended_by": "remote", "reason": "user.hangup", "media": ["audio"],
          "recording": {"state": "off"}, "evidence": ["a" * 64, "0123456789abcdef" * 4]}
    stored = accept(effective={"render": "ignore", "store": "call-record"})
    unanswered = {k: v for k, v in rc.items() if k != "answered_at"}
    o("call-record-valid", "A call record from the sending leaf's own device, in a direct conversation, is kept and never "
      "rendered (C§9).", ["C§9", "M§8.1"], rc, stored, ctx=rc_ctx)
    o("call-record-minimal", "Only session, device, direction, peer, the invite and end times, outcome and ended_by are "
      "required; a missed leg has no answered_at.", ["C§9"],
      {"object": "call-record", "session": uid("rec-call"), "device": "did:key:z6MkAlicePhone", "direction": "inbound",
       "peer": CAROL, "invited_at": NOW, "ended_at": NOW + 30, "outcome": "missed", "ended_by": "remote"}, stored, ctx=rc_ctx)
    o("call-record-times-equal", "invited_at, answered_at and ended_at may be equal: they only never decrease.", ["C§9"],
      {**rc, "answered_at": NOW, "ended_at": NOW}, stored, ctx=rc_ctx)
    o("call-record-unknown-outcome-kept", "An outcome outside the registry is kept as given (C§7: open registry).",
      ["C§9", "C§7"], {**unanswered, "outcome": "forwarded"}, stored, ctx=rc_ctx)
    o("call-record-device-not-sender-leaf", "A record's device must be the MLS sender leaf's device: a device cannot "
      "file another's records.", ["C§9", "M§6.2"], {**rc, "device": "did:key:z6MkAliceLaptop"}, reject("sender-mismatch"),
      ctx=rc_ctx)
    o("call-record-sender-checked-before-conversation", "Both wrong: the sender is checked first.", ["C§9"],
      {**rc, "device": "did:key:z6MkAliceLaptop"}, reject("sender-mismatch"), ctx={**rc_ctx, "conversation_kind": "personal"})
    o("call-record-in-personal-group-refused", "Call records go to the record-keeper's direct conversation, never the "
      "personal group.", ["C§9"], rc, reject("recorder-conversation-only"), ctx={**rc_ctx, "conversation_kind": "personal"})
    o("call-record-in-group-conversation-refused", "Nor a group conversation, whose other members would see them.",
      ["C§9"], rc, reject("recorder-conversation-only"), ctx={**rc_ctx, "conversation_kind": "group"})
    o("call-record-answered-without-answered-at", "An answered leg must carry answered_at.", ["C§9"], {**unanswered},
      reject("call-record-invalid"), ctx=rc_ctx)
    o("call-record-answered-at-on-missed-leg", "answered_at is present only on an answered leg.", ["C§9"],
      {**rc, "outcome": "missed", "direction": "inbound"}, reject("call-record-invalid"), ctx=rc_ctx)
    o("call-record-answered-before-invited", "Times never decrease: answered before invited is invalid.", ["C§9"],
      {**rc, "answered_at": NOW - 1}, reject("call-record-invalid"), ctx=rc_ctx)
    o("call-record-ended-before-answered", "Times never decrease: ended before answered is invalid.", ["C§9"],
      {**rc, "ended_at": NOW + 3}, reject("call-record-invalid"), ctx=rc_ctx)
    o("call-record-ended-before-invited", "Times never decrease, on a leg that was not answered too.", ["C§9"],
      {**unanswered, "outcome": "cancelled", "ended_at": NOW - 1}, reject("call-record-invalid"), ctx=rc_ctx)
    o("call-record-evidence-uppercase-refused", "Evidence is lowercase hex SHA-256.", ["C§9"],
      {**rc, "evidence": ["A" * 64]}, reject("schema-invalid"), ctx=rc_ctx)
    o("call-record-bad-ended-by-refused", "ended_by is local, remote or transport.", ["C§9"],
      {**rc, "ended_by": "peer"}, reject("schema-invalid"), ctx=rc_ctx)
    o("call-record-reason-not-a-reason-token", "reason is a category.condition token (§15).", ["C§9", "§15"],
      {**rc, "reason": "hangup"}, reject("schema-invalid"), ctx=rc_ctx)
    rd = {"object": "receipt", "id": uid("rp1"), "conversation": uid("other-conv"), "sender": ALICE, "sent_at": NOW,
          "kind": "read", "through": uid("m1")}
    o("receipt-read-in-personal-group-names-its-conversation",
      "An undisclosed read watermark travels in the personal group and names the conversation it describes.",
      ["M§10.5", "M§8.1"], rd, accept(effective={"receipt": "read"}), ctx={**OBJ_CTX, "conversation_kind": "personal"})
    o("receipt-delivered-in-personal-group-other-conversation-refused",
      "Only the read watermark is exempt: other objects in the personal group must name the personal group.",
      ["M§10.5", "M§8.1"], {**{k: v for k, v in rd.items() if k != "through"}, "kind": "delivered", "targets": [uid("m1")]},
      reject("conversation-mismatch"), ctx={**OBJ_CTX, "conversation_kind": "personal"})
    o("receipt-read-in-direct-conversation-other-conversation-refused",
      "Outside the personal group a read watermark must name its own conversation.", ["M§8.1"], rd, reject("conversation-mismatch"))
    o("unknown-object-ignored", "Unknown object types are ignored.", ["M§8.1"],
      {"object": "poll-vote", "choice": 2}, accept(effective={"render": "ignore"}))
    out.append(mv("conversation-ext-unknown-kind-is-group", "Unknown conversation kind is handled as group.", ["M§6.3"],
                  {"check": "conversation-ext", "extension": {"conversation": CONV, "kind": "channel", "hub": {"did": HUB_A},
                                                              "successor_of": None}},
                  accept(effective={"kind": "group"})))
    return out


# ---------------------------------------------------------------- hub traces (M§6.5–M§6.8, M§7.3, M§9.3, M§11.2)

def hub_ctx(epoch=1, roster=None, kind="direct", owner=None, retention=None):
    ctx = {"component": "hub", "hub": HUB_A, "group": GROUP, "kind": kind, "now": NOW, "epoch": epoch,
           "roster": roster if roster is not None else {ALICE: [ALA, APH], BOB: [BPH]}}
    if owner:
        ctx["owner"] = owner
    if retention is not None:
        ctx["mls_retention_s"] = retention
    return ctx


def dropped(identity, pending=(), welcomes=()):
    return {"dropped": {"identity": identity, "pending": list(pending), "welcomes": list(welcomes)}}


def hs(epoch, next_seq, roster, pending=None, group_info=False, moved_to=None, welcomes=None):
    return {"epoch": epoch, "next_seq": next_seq, "roster": roster, "pending": pending or {}, "group_info": group_info,
            "moved_to": moved_to, "welcomes": welcomes or {}}


def dep(label, device, identity, cls, epoch=None, digest=None, **kw):
    d = {"id": uid(label), "device": device, "identity": identity, "class": cls}
    if epoch is not None:
        d["epoch"] = epoch
    d["digest"] = digest or label
    d.update(kw)
    return {"deposit": d}


def acc(device, label, seq, dup=False):
    a = {"to": device, "in_reply_to": uid(label), "seq": seq}
    if dup:
        a["duplicate"] = True
    return {"accepted": a}


def acc_nc(device, label):
    """Acceptance with no seq: the item was stored but not sequenced."""
    return {"accepted": {"to": device, "in_reply_to": uid(label)}}


def err(device, label, reason):
    return {"error": {"to": device, "in_reply_to": uid(label), "reason": reason}}


def fan(to, seq, cls="application"):
    return {"fanout": {"to": to, "seq": seq, "class": cls}}


def hub_vectors():
    out = []
    R = {ALICE: [ALA, APH], BOB: [BPH]}
    refs = ["M§6.5"]

    out.append(trace("hub-application-sequenced-and-fanned-out",
                     "An application message is sequenced and fanned out to every member identity, the sender's own included.",
                     refs + ["M§9.1"], "hub-trace", hub_ctx(), [
                         (dep("a1", APH, ALICE, "application", 1), [acc(APH, "a1", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-commit-conflict",
                     "The first valid commit for an epoch wins; a second commit for the same epoch is refused.",
                     refs, "hub-trace", hub_ctx(), [
                         (dep("k1", APH, ALICE, "handshake", 1, commit={"adds": [], "removes": []}),
                          [acc(APH, "k1", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]})),
                         (dep("k2", BPH, BOB, "handshake", 1, commit={"adds": [], "removes": []}),
                          [err(BPH, "k2", "mailbox.commit-conflict")], hs(2, 2, R, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-stale-epoch",
                     "Application messages for the current or previous epoch are accepted; older ones are stale.",
                     refs, "hub-trace", hub_ctx(epoch=3), [
                         (dep("a2", APH, ALICE, "application", 2), [acc(APH, "a2", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(3, 2, R, {ALICE: [1], BOB: [1]})),
                         (dep("a3", BPH, BOB, "application", 1), [err(BPH, "a3", "mailbox.stale-epoch")],
                          hs(3, 2, R, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-idempotent-redeposit",
                     "Re-depositing the same MLS bytes returns the original seq with duplicate and fans out nothing.",
                     ["M§9.3"], "hub-trace", hub_ctx(), [
                         (dep("a4", APH, ALICE, "application", 1, digest="d-a4"), [acc(APH, "a4", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                         (dep("a4-retry", APH, ALICE, "application", 1, digest="d-a4"), [acc(APH, "a4-retry", 1, dup=True)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-non-member-refused", "A device of a non-member identity cannot deposit into the group.",
                     refs, "hub-trace", hub_ctx(), [
                         (dep("m1", MPH, MALLORY, "application", 1), [err(MPH, "m1", "policy.blocked")], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-fanout-waits-for-ack",
                     "Fan-out to each mailbox is in seq order: a later item waits until the earlier one is acknowledged.",
                     refs, "hub-trace", hub_ctx(), [
                         (dep("f1", APH, ALICE, "application", 1), [acc(APH, "f1", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                         ({"ack": {"identity": ALICE, "seq": 1}}, [], hs(1, 2, R, {BOB: [1]})),
                         (dep("f2", APH, ALICE, "application", 1), [acc(APH, "f2", 2), fan(ALICE, 2)],
                          hs(1, 3, R, {ALICE: [2], BOB: [1, 2]})),
                         ({"ack": {"identity": BOB, "seq": 2}}, [], hs(1, 3, R, {ALICE: [2], BOB: [1, 2]})),
                         ({"ack": {"identity": BOB, "seq": 1}}, [fan(BOB, 2)], hs(1, 3, R, {ALICE: [2], BOB: [2]})),
                     ]))
    out.append(trace("hub-commit-adds-identity-sends-welcome",
                     "A commit adding a new identity fans out to existing members and sends a welcome to the new one.",
                     refs + ["M§7.3"], "hub-trace", hub_ctx(kind="group"), [
                         (dep("add-carol", APH, ALICE, "handshake", 1, commit={"adds": [{"identity": CAROL, "device": CPH}], "removes": []}),
                          [acc(APH, "add-carol", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake"),
                           fan(CAROL, 1, "welcome")],
                          hs(2, 2, {ALICE: [ALA, APH], BOB: [BPH], CAROL: [CPH]}, {ALICE: [1], BOB: [1]}, welcomes={CAROL: [1]})),
                     ]))
    out.append(trace("hub-commit-adds-own-device-sends-welcome",
                     "A member adding its own new device gets a welcome to its own identity: the new device is not in the group yet.",
                     refs + ["M§6.7", "M§12.3"], "hub-trace", hub_ctx(kind="group"), [
                         (dep("add-bla", BPH, BOB, "handshake", 1, commit={"adds": [{"identity": BOB, "device": BLA}], "removes": []}),
                          [acc(BPH, "add-bla", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake"),
                           fan(BOB, 1, "welcome")],
                          hs(2, 2, {ALICE: [ALA, APH], BOB: [BLA, BPH]}, {ALICE: [1], BOB: [1]}, welcomes={BOB: [1]})),
                     ]))
    RC = {ALICE: [ALA, APH], BOB: [BPH], CAROL: [CPH]}
    addc = dep("add-carol", APH, ALICE, "handshake", 1, commit={"adds": [{"identity": CAROL, "device": CPH}], "removes": []})
    out.append(trace("hub-welcome-queued-and-retried",
                     "A welcome is queued for the added identity and retried like any fan-out (spec-gap 66); nothing else goes to "
                     "that mailbox until it acknowledges, since until then it has no registration for the group.",
                     refs + ["M§6.6", "M§7.3"], "hub-trace", hub_ctx(kind="group"), [
                         (addc, [acc(APH, "add-carol", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake"), fan(CAROL, 1, "welcome")],
                          hs(2, 2, RC, {ALICE: [1], BOB: [1]}, welcomes={CAROL: [1]})),
                         (dep("a1", APH, ALICE, "application", 2), [acc(APH, "a1", 2)],
                          hs(2, 3, RC, {ALICE: [1, 2], BOB: [1, 2], CAROL: [2]}, welcomes={CAROL: [1]})),
                         ({"ack": {"identity": CAROL, "seq": 1, "class": "welcome"}}, [fan(CAROL, 2)],
                          hs(2, 3, RC, {ALICE: [1, 2], BOB: [1, 2], CAROL: [2]})),
                         ({"ack": {"identity": CAROL, "seq": 2}}, [], hs(2, 3, RC, {ALICE: [1, 2], BOB: [1, 2]})),
                     ]))
    # spec-gap 119: a member's queues are bounded by mls_retention_s from the last acknowledgement
    ack_ = lambda i, n, cls=None: {"ack": dict({"identity": i, "seq": n}, **({"class": cls} if cls else {}))}
    out.append(trace("hub-queue-dropped-at-retention",
                     "A member identity that acknowledges nothing for mls_retention_s has its fan-out queue dropped; it stays "
                     "a member, and what is sequenced later is fanned out to it afresh (spec-gap 119).",
                     refs + ["M§4.4"], "hub-trace", hub_ctx(retention=100), [
                         (dep("a1", APH, ALICE, "application", 1), [acc(APH, "a1", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                         (ack_(ALICE, 1), [], hs(1, 2, R, {BOB: [1]})),
                         (dep("a2", APH, ALICE, "application", 1), [acc(APH, "a2", 2), fan(ALICE, 2)],
                          hs(1, 3, R, {ALICE: [2], BOB: [1, 2]})),
                         ({"advance": 60}, [], hs(1, 3, R, {ALICE: [2], BOB: [1, 2]})),
                         (ack_(ALICE, 2), [], hs(1, 3, R, {BOB: [1, 2]})),
                         ({"advance": 39}, [], hs(1, 3, R, {BOB: [1, 2]})),
                         ({"advance": 1}, [dropped(BOB, [1, 2])], hs(1, 3, R, {})),
                         (dep("a3", APH, ALICE, "application", 1), [acc(APH, "a3", 3), fan(ALICE, 3), fan(BOB, 3)],
                          hs(1, 4, R, {ALICE: [3], BOB: [3]})),
                     ]))
    out.append(trace("hub-queue-clock-restarts-on-acknowledgement",
                     "The retention bound counts from the member's last acknowledgement, not from the oldest item: a slow "
                     "mailbox that keeps acknowledging is never dropped (spec-gap 119).",
                     refs + ["M§4.4"], "hub-trace", hub_ctx(retention=100), [
                         (dep("a1", APH, ALICE, "application", 1), [acc(APH, "a1", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                         (dep("a2", APH, ALICE, "application", 1), [acc(APH, "a2", 2)], hs(1, 3, R, {ALICE: [1, 2], BOB: [1, 2]})),
                         (ack_(ALICE, 1), [fan(ALICE, 2)], hs(1, 3, R, {ALICE: [2], BOB: [1, 2]})),
                         (ack_(ALICE, 2), [], hs(1, 3, R, {BOB: [1, 2]})),
                         ({"advance": 90}, [], hs(1, 3, R, {BOB: [1, 2]})),
                         (ack_(BOB, 1), [fan(BOB, 2)], hs(1, 3, R, {BOB: [2]})),
                         ({"advance": 99}, [], hs(1, 3, R, {BOB: [2]})),
                         ({"advance": 1}, [dropped(BOB, [2])], hs(1, 3, R, {})),
                     ]))
    out.append(trace("hub-welcome-dropped-at-retention-member-rejoins",
                     "An added identity whose welcome is never acknowledged has its welcome and the items held behind it dropped "
                     "at mls_retention_s; it stays a member, no longer held, and later rejoins by external commit (M§6.8, "
                     "spec-gap 119).",
                     refs + ["M§4.4", "M§6.8"], "hub-trace", hub_ctx(kind="group", retention=100), [
                         (addc, [acc(APH, "add-carol", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake"), fan(CAROL, 1, "welcome")],
                          hs(2, 2, RC, {ALICE: [1], BOB: [1]}, welcomes={CAROL: [1]})),
                         (ack_(ALICE, 1), [], hs(2, 2, RC, {BOB: [1]}, welcomes={CAROL: [1]})),
                         (ack_(BOB, 1), [], hs(2, 2, RC, {}, welcomes={CAROL: [1]})),
                         (dep("a1", APH, ALICE, "application", 2), [acc(APH, "a1", 2), fan(ALICE, 2), fan(BOB, 2)],
                          hs(2, 3, RC, {ALICE: [2], BOB: [2], CAROL: [2]}, welcomes={CAROL: [1]})),
                         (ack_(ALICE, 2), [], hs(2, 3, RC, {BOB: [2], CAROL: [2]}, welcomes={CAROL: [1]})),
                         (ack_(BOB, 2), [], hs(2, 3, RC, {CAROL: [2]}, welcomes={CAROL: [1]})),
                         ({"advance": 100}, [dropped(CAROL, [2], [1])], hs(2, 3, RC, {})),
                         (dep("cj", CPH, CAROL, "handshake", 2, commit={"external": True, "adds": [{"identity": CAROL, "device": CPH}],
                                                                         "removes": [{"identity": CAROL, "device": CPH}]}),
                          # fan-out goes in identity order: Carol's DID sorts before Bob's
                          [acc(CPH, "cj", 3), fan(ALICE, 3, "handshake"), fan(CAROL, 3, "handshake"), fan(BOB, 3, "handshake")],
                          hs(3, 4, RC, {ALICE: [3], BOB: [3], CAROL: [3]})),
                     ]))
    out.append(trace("hub-welcome-resent-after-restart",
                     "A hub restart re-sends an unacknowledged welcome, so a member added while its mailbox was down still gets it "
                     "(spec-gap 66 closes the gap left open by spec-gap 59).", refs + ["M§7.3"], "hub-trace", hub_ctx(kind="group"), [
                         (addc, [acc(APH, "add-carol", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake"), fan(CAROL, 1, "welcome")],
                          hs(2, 2, RC, {ALICE: [1], BOB: [1]}, welcomes={CAROL: [1]})),
                         ({"ack": {"identity": ALICE, "seq": 1}}, [], hs(2, 2, RC, {BOB: [1]}, welcomes={CAROL: [1]})),
                         (dep("a1", APH, ALICE, "application", 2), [acc(APH, "a1", 2), fan(ALICE, 2)],
                          hs(2, 3, RC, {ALICE: [2], BOB: [1, 2], CAROL: [2]}, welcomes={CAROL: [1]})),
                         ({"restart": {}}, [fan(ALICE, 2), fan(BOB, 1, "handshake"), fan(CAROL, 1, "welcome")],
                          hs(2, 3, RC, {ALICE: [2], BOB: [1, 2], CAROL: [2]}, welcomes={CAROL: [1]})),
                     ]))
    RB = {ALICE: [ALA, APH], BOB: [BLA, BPH]}
    selfadd = dep("add-bob-laptop", BPH, BOB, "handshake", 1, commit={"adds": [{"identity": BOB, "device": BLA}], "removes": []})
    out.append(trace("hub-member-adding-its-own-device-is-not-held-behind-the-welcome",
                     "The hold behind an unacknowledged welcome is for an identity the commit brought in (no registration yet, M§6.6). "
                     "A member adding its own device is registered: it gets the commit at once, again after a restart, and the "
                     "welcome's acknowledgement re-sends nothing — its queue moves only on its own acknowledgements (spec-gap 87).",
                     refs + ["M§6.7"], "hub-trace", hub_ctx(kind="group"), [
                         (selfadd, [acc(BPH, "add-bob-laptop", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake"), fan(BOB, 1, "welcome")],
                          hs(2, 2, RB, {ALICE: [1], BOB: [1]}, welcomes={BOB: [1]})),
                         ({"restart": {}}, [fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake"), fan(BOB, 1, "welcome")],
                          hs(2, 2, RB, {ALICE: [1], BOB: [1]}, welcomes={BOB: [1]})),
                         ({"ack": {"identity": BOB, "seq": 1, "class": "welcome"}}, [], hs(2, 2, RB, {ALICE: [1], BOB: [1]})),
                         (dep("a1", APH, ALICE, "application", 2), [acc(APH, "a1", 2)], hs(2, 3, RB, {ALICE: [1, 2], BOB: [1, 2]})),
                         ({"ack": {"identity": BOB, "seq": 1}}, [fan(BOB, 2)], hs(2, 3, RB, {ALICE: [1, 2], BOB: [2]})),
                     ]))
    out.append(trace("hub-acknowledgement-does-not-lift-the-welcome-hold",
                     "An acknowledgement from an identity still waiting for its welcome moves its queue but sends nothing: the hold "
                     "lasts until the welcome itself is acknowledged (spec-gap 87).", refs, "hub-trace", hub_ctx(kind="group"), [
                         (addc, [acc(APH, "add-carol", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake"), fan(CAROL, 1, "welcome")],
                          hs(2, 2, RC, {ALICE: [1], BOB: [1]}, welcomes={CAROL: [1]})),
                         (dep("a1", APH, ALICE, "application", 2), [acc(APH, "a1", 2)],
                          hs(2, 3, RC, {ALICE: [1, 2], BOB: [1, 2], CAROL: [2]}, welcomes={CAROL: [1]})),
                         (dep("a2", APH, ALICE, "application", 2), [acc(APH, "a2", 3)],
                          hs(2, 4, RC, {ALICE: [1, 2, 3], BOB: [1, 2, 3], CAROL: [2, 3]}, welcomes={CAROL: [1]})),
                         ({"ack": {"identity": CAROL, "seq": 2}}, [],
                          hs(2, 4, RC, {ALICE: [1, 2, 3], BOB: [1, 2, 3], CAROL: [3]}, welcomes={CAROL: [1]})),
                         ({"ack": {"identity": CAROL, "seq": 1, "class": "welcome"}}, [fan(CAROL, 3)],
                          hs(2, 4, RC, {ALICE: [1, 2, 3], BOB: [1, 2, 3], CAROL: [3]})),
                     ]))
    out.append(trace("hub-commit-readds-existing-device-no-welcome",
                     "A commit that adds no device new to its identity sends no welcome.",
                     refs + ["M§6.7"], "hub-trace", hub_ctx(kind="group"), [
                         (dep("upd", BPH, BOB, "handshake", 1, commit={"adds": [], "removes": []}),
                          [acc(BPH, "upd", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-add-other-identitys-device-refused",
                     "Adding a device to another member identity is reserved to that identity's own devices.",
                     ["M§7.3"], "hub-trace", hub_ctx(kind="group"), [
                         (dep("add-bla", APH, ALICE, "handshake", 1, commit={"adds": [{"identity": BOB, "device": BLA}], "removes": []}),
                          [err(APH, "add-bla", "policy.blocked")], hs(1, 1, R)),
                     ]))
    RB2 = {ALICE: [ALA, APH], BOB: [BLA, BPH]}
    out.append(trace("hub-remove-whole-identity-allowed",
                     "Any member may remove another identity entirely; the removed identity still receives the commit.",
                     ["M§7.3", "M§6.5"], "hub-trace", hub_ctx(kind="group", roster=RB2), [
                         (dep("rm-bob", APH, ALICE, "handshake", 1,
                              commit={"adds": [], "removes": [{"identity": BOB, "device": BPH}, {"identity": BOB, "device": BLA}]}),
                          [acc(APH, "rm-bob", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")],
                          hs(2, 2, {ALICE: [ALA, APH]}, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-remove-partial-other-identity-refused",
                     "Removing only some devices of another identity is refused while their delegations are valid.",
                     ["M§7.3"], "hub-trace", hub_ctx(kind="group", roster=RB2), [
                         (dep("rm-bla", APH, ALICE, "handshake", 1, commit={"adds": [], "removes": [{"identity": BOB, "device": BLA}]}),
                          [err(APH, "rm-bla", "policy.blocked")], hs(1, 1, RB2)),
                     ]))
    out.append(trace("hub-remove-lapsed-delegation-leaf-allowed",
                     "Any member may remove a leaf whose delegation no longer verifies.",
                     ["M§7.3", "M§6.2"], "hub-trace", hub_ctx(kind="group", roster=RB2), [
                         (dep("rm-lapsed", APH, ALICE, "handshake", 1,
                              commit={"adds": [], "removes": [{"identity": BOB, "device": BLA, "delegation_valid": False}]}),
                          [acc(APH, "rm-lapsed", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")],
                          hs(2, 2, {ALICE: [ALA, APH], BOB: [BPH]}, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-external-commit-own-identity",
                     "A new device of a member identity may join by external commit, replacing that identity's stale leaf.",
                     ["M§6.8"], "hub-trace", hub_ctx(), [
                         (dep("ext-tab", BTAB, BOB, "handshake", 1,
                              commit={"external": True, "adds": [{"identity": BOB, "device": BTAB}],
                                      "removes": [{"identity": BOB, "device": BPH}]}),
                          [acc(BTAB, "ext-tab", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")],
                          hs(2, 2, {ALICE: [ALA, APH], BOB: [BTAB]}, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-external-commit-stranger-refused",
                     "An identity with no leaf in the group may not join by external commit.",
                     ["M§6.8"], "hub-trace", hub_ctx(), [
                         (dep("ext-carol", CPH, CAROL, "handshake", 1,
                              commit={"external": True, "adds": [{"identity": CAROL, "device": CPH}], "removes": []}),
                          [err(CPH, "ext-carol", "policy.blocked")], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-external-commit-personal-group-owner",
                     "The owner may re-join its own personal group by external commit even with no surviving leaf.",
                     ["M§6.8", "M§7.1"], "hub-trace", hub_ctx(kind="personal", owner=BOB, roster={}), [
                         (dep("ext-own", BTAB, BOB, "handshake", 1,
                              commit={"external": True, "adds": [{"identity": BOB, "device": BTAB}], "removes": []}),
                          [acc(BTAB, "ext-own", 1)], hs(2, 2, {BOB: [BTAB]})),
                     ]))
    out.append(trace("hub-invalid-commit-refused", "A commit that fails validation is refused and does not advance the epoch.",
                     refs, "hub-trace", hub_ctx(), [
                         (dep("bad", APH, ALICE, "handshake", 1, commit={"valid": False, "adds": [], "removes": []}),
                          [err(APH, "bad", "policy.blocked")], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-proposal-sequenced-no-epoch-change",
                     "A standalone proposal is sequenced and fanned out but does not advance the epoch.",
                     refs, "hub-trace", hub_ctx(), [
                         (dep("prop", BPH, BOB, "handshake", 1), [acc(BPH, "prop", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-ephemeral-forwarded-not-sequenced",
                     "Activity is forwarded to the other member identities: no seq, no acceptance, nothing queued.",
                     ["M§11.2"], "hub-trace", hub_ctx(), [
                         (dep("typ", APH, ALICE, "ephemeral", expires_at=NOW + 10), [{"forward": {"to": BOB, "class": "ephemeral"}}],
                          hs(1, 1, R)),
                     ]))
    out.append(trace("hub-ephemeral-expired-dropped", "Expired activity is dropped silently.",
                     ["M§11.2"], "hub-trace", hub_ctx(), [
                         (dep("typ-old", APH, ALICE, "ephemeral", expires_at=NOW - 1), [], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-ephemeral-at-expiry-dropped", "Activity reaching the hub at exactly its expires_at has expired "
                     "(§12.9, spec-gap 141) and is dropped silently.",
                     ["M§11.2", "§12.9"], "hub-trace", hub_ctx(), [
                         (dep("typ-edge", APH, ALICE, "ephemeral", expires_at=NOW), [], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-ephemeral-expiry-judged-at-the-hubs-clock",
                     "Expiry is judged at the hub's clock as time passes, not at the time it started: activity that was live at "
                     "the start is dropped once the hub's clock has passed its expires_at (found by fuzz.py, 2026-10-12).",
                     ["M§11.2"], "hub-trace", hub_ctx(), [
                         ({"advance": 20}, [], hs(1, 1, R)),
                         (dep("typ-late", APH, ALICE, "ephemeral", expires_at=NOW + 10), [], hs(1, 1, R)),
                         (dep("typ-live", APH, ALICE, "ephemeral", expires_at=NOW + 30), [{"forward": {"to": BOB, "class": "ephemeral"}}],
                          hs(1, 1, R)),
                     ]))
    # --- the order of a hub's refusals when several apply (spec-gap 81)
    out.append(trace("hub-refusal-order-class-before-membership",
                     "What a hub does not take at all is refused as such, whoever sends it: the class is checked before membership.",
                     ["M§6.5", "M§5.2"], "hub-trace", hub_ctx(), [
                         (dep("arch-m", MPH, MALLORY, "archive"), [err(MPH, "arch-m", "mailbox.unsupported-class")], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-refusal-order-expired-ephemeral-dropped-before-membership",
                     "Expired activity is dropped silently before the hub asks who sent it: nothing is answered, to anyone.",
                     ["M§11.2", "M§6.5"], "hub-trace", hub_ctx(), [
                         (dep("typ-old-m", MPH, MALLORY, "ephemeral", expires_at=NOW - 1), [], hs(1, 1, R)),
                         (dep("typ-m", MPH, MALLORY, "ephemeral", expires_at=NOW + 10), [err(MPH, "typ-m", "policy.blocked")], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-refusal-order-redeposit-before-membership",
                     "A sequenced item's bytes were authenticated when first accepted: the same bytes again are answered "
                     "`accepted` with `duplicate` before membership or epoch is looked at — a member removed since, or a "
                     "retry arriving an epoch late, still learns its item was ordered. group-info is state, not sequenced: "
                     "no such shortcut.",
                     ["M§9.3", "M§6.5"], "hub-trace", hub_ctx(), [
                         (dep("a4", APH, ALICE, "application", 1, digest="d-a4"), [acc(APH, "a4", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                         (dep("a4-m", MPH, MALLORY, "application", 0, digest="d-a4"), [acc(MPH, "a4-m", 1, dup=True)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                         (dep("gi-m", MPH, MALLORY, "group-info", 1, digest="d-a4"), [err(MPH, "gi-m", "policy.blocked")],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                     ]))
    out.append(trace("hub-refusal-order-external-join-authorization-before-epoch",
                     "A stranger's external commit is refused for who sent it, not for the epoch it names.",
                     ["M§6.8", "M§6.5"], "hub-trace", hub_ctx(), [
                         (dep("ext-carol-late", CPH, CAROL, "handshake", 0,
                              commit={"external": True, "adds": [{"identity": CAROL, "device": CPH}], "removes": []}),
                          [err(CPH, "ext-carol-late", "policy.blocked")], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-unsupported-class-refused", "A hub stores no history: an archive deposit is refused.",
                     ["M§6.5", "M§5.2"], "hub-trace", hub_ctx(), [
                         (dep("arch", APH, ALICE, "archive"), [err(APH, "arch", "mailbox.unsupported-class")], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-group-info-accepted-not-sequenced",
                     "The hub keeps each group's latest GroupInfo — what a returning device external-joins from — and "
                     "forwards it to the members' mailboxes. It is not sequenced and does not advance the epoch.",
                     ["M§6.5", "M§6.8"], "hub-trace", hub_ctx(), [
                         (dep("gi1", APH, ALICE, "group-info", 1),
                          [acc_nc(APH, "gi1"), {"fanout": {"to": ALICE, "class": "group-info"}},
                           {"fanout": {"to": BOB, "class": "group-info"}}], hs(1, 1, R, group_info=True)),
                         (dep("gi2", APH, ALICE, "group-info", 1, digest="gi2"),
                          [acc_nc(APH, "gi2"), {"fanout": {"to": ALICE, "class": "group-info"}},
                           {"fanout": {"to": BOB, "class": "group-info"}}], hs(1, 1, R, group_info=True)),
                         (dep("a1", APH, ALICE, "application", 1), [acc(APH, "a1", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]}, group_info=True)),
                     ]))
    out.append(trace("hub-group-info-from-non-member-refused",
                     "Only a member may publish the group's GroupInfo.", ["M§6.5"], "hub-trace", hub_ctx(), [
                         (dep("gi-m", MPH, MALLORY, "group-info", 1), [err(MPH, "gi-m", "policy.blocked")], hs(1, 1, R)),
                     ]))
    return out


# ---------------------------------------------------------------- mailbox traces (M§4.4, M§5.4–M§5.7, M§6.6, M§12.2, M§14.2)

def mbx_ctx(**over):
    ctx = {"component": "mailbox", "mailbox": MBX_B, "owner": BOB, "serves": [BOB], "devices": [BLA, BPH], "now": NOW,
           "mode": "sync", "admit": "grant", "pending_group_ttl": 604800, "pending_group_max_items": 2,
           "groups": {}, "key_packages": {}}
    ctx.update(over)
    return ctx


def ms(items=(), groups=None, kps=None):
    return {"items": list(items), "groups": groups or {}, "key_packages": kps or {}}


def grant(label="g1", scope=("dsip.message",), valid_until=NOW + 86400, frm=BOB, to=CAROL):
    return {"id": uid(label), "from": frm, "to": to, "scope": list(scope), "valid_until": valid_until}


def welcome(label="w1", adder=CAROL, device=CPH, grant_=None, group=GROUP, hub=HUB_A, recipient=BOB, successor_of=None,
            digest="d-welcome-1", size=None):
    e = {"id": uid(label), "from": device, "adder_identity": adder, "recipient": recipient, "group": group, "hub": hub,
         "grant": grant_, "digest": digest}
    if size is not None:
        e["size"] = size
    if successor_of is not None:
        e["successor_of"] = successor_of
    return {"welcome": e}


def macc(to, label, cur=None, dup=False):
    a = {"to": to, "in_reply_to": uid(label)}
    if cur is not None:
        a["cursor"] = cur
    if dup:
        a["duplicate"] = True
    return {"accepted": a}


def hubdep(label, seq, cls="application", group=GROUP, frm=HUB_A, recipient=BOB, size=None):
    e = {"id": uid(label), "from": frm, "recipient": recipient, "group": group, "seq": seq, "class": cls}
    if size is not None:
        e["size"] = size
    return {"hub_deposit": e}


def mailbox_vectors():
    out = []
    P = {GROUP: "pending"}
    J = {GROUP: "joined"}
    T = "mailbox-trace"

    out.append(trace("mailbox-welcome-with-grant-registers-pending",
                     "A welcome from an identity holding a dsip.message grant is stored and registers the group as pending.",
                     ["M§14.2", "M§6.6"], T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-welcome-redelivered-duplicate",
                     "A hub retrying a welcome it saw no acknowledgement for — the same MLS bytes — gets a duplicate "
                     "acknowledgement with the first welcome's cursor; the group is registered once (spec-gap 66).",
                     ["M§14.2", "M§6.6", "M§9.3"], T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         (welcome(label="w1-retry", grant_=grant()), [macc(CPH, "w1-retry", c(1), dup=True)], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-welcome-for-another-device-stored",
                     "A second welcome for a registered group with different MLS bytes is a new invitation — an owner device "
                     "adding a sibling (M§6.7) — and is stored.", ["M§14.2", "M§6.7", "M§12.3"], T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         (welcome(label="w2", adder=BOB, device=BPH, digest="d-welcome-2"), [macc(BPH, "w2", c(2))], ms([c(1), c(2)], P)),
                     ]))
    out.append(trace("mailbox-welcome-after-leaving-registers-again",
                     "Once the owner has left the group, a new welcome re-registers it as pending; a redelivery of the welcome "
                     "already stored stays a duplicate, whatever the registration.", ["M§14.2", "M§5.7"], T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         ({"config": {"id": uid("cfg"), "device": BPH, "groups": [{"group": GROUP, "state": "left"}]}},
                          [macc(BPH, "cfg")], ms([c(1)])),
                         (welcome(label="w1-again", grant_=grant()), [macc(CPH, "w1-again", c(1), dup=True)], ms([c(1)])),
                         (welcome(label="w2", grant_=grant(), digest="d-welcome-3"), [macc(CPH, "w2", c(2))], ms([c(1), c(2)], P)),
                     ]))
    out.append(trace("mailbox-welcome-without-grant-refused",
                     "Without a grant (and admit grant) the welcome is refused with first-contact-required.",
                     ["M§14.2", "§19.4"], T, mbx_ctx(), [
                         (welcome(), [err(CPH, "w1", "policy.first-contact-required")], ms()),
                     ]))
    out.append(trace("mailbox-welcome-revoked-grant-refused",
                     "A grant listed in revoked_grants no longer authorizes.", ["M§14.2", "M§5.7"], T, mbx_ctx(), [
                         ({"config": {"id": uid("cfg"), "device": BPH, "revoked_grants": [uid("g1")]}}, [macc(BPH, "cfg")], ms()),
                         (welcome(grant_=grant()), [err(CPH, "w1", "policy.first-contact-required")], ms()),
                     ]))
    out.append(trace("mailbox-welcome-expired-grant-refused", "A grant past valid_until no longer authorizes.",
                     ["M§14.2"], T, mbx_ctx(), [
                         (welcome(grant_=grant(valid_until=NOW)), [err(CPH, "w1", "policy.first-contact-required")], ms()),
                     ]))
    out.append(trace("mailbox-welcome-invite-grant-accepted",
                     "A dsip.invite grantee may create a conversation (to leave voicemail).", ["M§14.2", "M§13.2"], T, mbx_ctx(), [
                         (welcome(grant_=grant(scope=("dsip.invite",))), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-welcome-subscribe-grant-refused", "A dsip.subscribe-only grant does not authorize messaging.",
                     ["M§14.2", "§19.4"], T, mbx_ctx(), [
                         (welcome(grant_=grant(scope=("dsip.subscribe",))), [err(CPH, "w1", "policy.first-contact-required")], ms()),
                     ]))
    out.append(trace("mailbox-welcome-grant-for-other-grantee-refused", "A grant names its grantee; another identity cannot use it.",
                     ["M§14.2"], T, mbx_ctx(), [
                         (welcome(grant_=grant(to=MALLORY)), [err(CPH, "w1", "policy.first-contact-required")], ms()),
                     ]))
    out.append(trace("mailbox-welcome-admit-open", "An owner with admit open accepts welcomes without a grant.",
                     ["M§14.2", "M§5.7"], T, mbx_ctx(admit="open"), [
                         (welcome(), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-welcome-from-own-device", "A device of the owner identity needs no grant.",
                     ["M§14.2", "M§6.7"], T, mbx_ctx(), [
                         (welcome(adder=BOB, device=BPH), [macc(BPH, "w1", c(1))], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-welcome-successor-group-no-grant",
                     "A successor group of a registered group is admitted without a grant.", ["M§7.5", "M§14.2"], T,
                     mbx_ctx(groups={GROUP: {"hub": "did:web:dead-hub.example", "state": "joined"}}), [
                         (welcome(group=GROUP2, successor_of=GROUP), [macc(CPH, "w1", c(1))], ms([c(1)], {GROUP: "joined", GROUP2: "pending"})),
                     ]))
    out.append(trace("mailbox-welcome-unknown-recipient", "A mailbox refuses deposits for identities it does not serve.",
                     ["M§15.5", "§13.2"], T, mbx_ctx(), [
                         (welcome(recipient=ALICE, grant_=grant()), [err(CPH, "w1", "transport.unknown-recipient")], ms()),
                     ]))
    # --- hub-forwarded welcomes (M§14.2, spec-gap 46)
    def hub_welcome(label="w1", origin=None, issued_at=NOW, grant_=None, adder_claim=None):
        e = {"id": uid(label), "from": HUB_A, "via_hub": True, "recipient": BOB, "group": GROUP, "hub": HUB_A,
             "grant": grant_, "issued_at": issued_at}
        if origin is not None:
            e["origin"] = origin
        if adder_claim is not None:
            e["adder_identity"] = adder_claim
        return {"welcome": e}

    def origin(identity=CAROL, group=GROUP, issued_at=NOW - 2):
        return {"identity": identity, "group": group, "issued_at": issued_at}

    g46 = ["M§14.2", "M§6.5"]
    out.append(trace("mailbox-welcome-hub-forwarded-origin-proves-adder",
                     "A welcome fanned out by the hub is admitted when its origin (the adder device's signed deposit) proves "
                     "an adder holding the owner's grant.", g46, T, mbx_ctx(), [
                         (hub_welcome(origin=origin(), grant_=grant()), [macc(HUB_A, "w1", c(1))], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-welcome-hub-forwarded-origin-at-skew-bound",
                     "An origin issued 300 s before the hub deposit is accepted (spec-gap 118: age within the pending-group "
                     "retention, not skew).", g46, T, mbx_ctx(), [
                         (hub_welcome(origin=origin(issued_at=NOW - 300), grant_=grant()), [macc(HUB_A, "w1", c(1))], ms([c(1)], P)),
                     ]))
    g118 = ["M§14.2", "M§6.5", "M§6.6"]
    out.append(trace("mailbox-welcome-hub-forwarded-origin-after-outage-accepted",
                     "A welcome re-sent an hour after the commit (the hub retried through an outage) still proves its adder: "
                     "the origin's age is bounded by the pending-group retention, not by 300 s (spec-gap 118).", g118, T, mbx_ctx(), [
                         (hub_welcome(origin=origin(issued_at=NOW - 3600), grant_=grant()), [macc(HUB_A, "w1", c(1))], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-welcome-hub-forwarded-origin-older-than-retention-refused",
                     "An origin older than pending_group_ttl before the hub deposit proves nothing: policy.blocked (spec-gap 118).",
                     g118, T, mbx_ctx(), [
                         (hub_welcome(origin=origin(issued_at=NOW - 604801), grant_=grant()), [err(HUB_A, "w1", "policy.blocked")], ms()),
                     ]))
    out.append(trace("mailbox-welcome-hub-forwarded-origin-at-retention-bound",
                     "An origin exactly pending_group_ttl before the hub deposit is still accepted (spec-gap 118).", g118, T, mbx_ctx(), [
                         (hub_welcome(origin=origin(issued_at=NOW - 604800), grant_=grant()), [macc(HUB_A, "w1", c(1))], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-welcome-hub-forwarded-origin-at-future-bound",
                     "An origin issued 300 s after the hub deposit (clock skew) is still accepted (spec-gap 118).", g118, T, mbx_ctx(), [
                         (hub_welcome(origin=origin(issued_at=NOW + 300), grant_=grant()), [macc(HUB_A, "w1", c(1))], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-welcome-hub-forwarded-origin-from-the-future-refused",
                     "An origin more than 300 s after the hub deposit proves nothing: policy.blocked (spec-gap 118).", g118, T, mbx_ctx(), [
                         (hub_welcome(origin=origin(issued_at=NOW + 301), grant_=grant()), [err(HUB_A, "w1", "policy.blocked")], ms()),
                     ]))
    out.append(trace("mailbox-welcome-hub-forwarded-without-origin-refused",
                     "A hub-forwarded welcome without origin is refused: the hub's own connection does not prove who added the owner.",
                     g46, T, mbx_ctx(), [
                         (hub_welcome(grant_=grant(), adder_claim=CAROL), [err(HUB_A, "w1", "policy.blocked")], ms()),
                     ]))
    out.append(trace("mailbox-welcome-hub-forwarded-origin-other-group-refused",
                     "An origin deposit for another group cannot vouch for this welcome.", g46, T, mbx_ctx(), [
                         (hub_welcome(origin=origin(group=GROUP2), grant_=grant()), [err(HUB_A, "w1", "policy.blocked")], ms()),
                     ]))
    out.append(trace("mailbox-welcome-hub-forwarded-origin-identity-wins",
                     "The adder is the origin's identity, not any claim beside it: a grant to Carol does not admit Mallory's add.",
                     g46, T, mbx_ctx(), [
                         (hub_welcome(origin=origin(identity=MALLORY), grant_=grant(), adder_claim=CAROL),
                          [err(HUB_A, "w1", "policy.first-contact-required")], ms()),
                     ]))

    # --- forwarding a device's deposit to its group's hub (M§5.2, M§6.6, spec-gap 45)
    def fwd(label="f1", identity=BOB, device=BPH, group=GROUP, to=HUB_A):
        return {"forward": {"id": uid(label), "device": device, "identity": identity, "group": group, "to": to}}

    g45 = ["M§5.2", "M§6.6"]
    JG = {GROUP: {"hub": HUB_A, "state": "joined"}}
    out.append(trace("mailbox-forward-to-registered-hub",
                     "An owner device's deposit addressed to the hub registered for its group is forwarded unchanged; nothing is stored.",
                     g45, T, mbx_ctx(groups=JG), [
                         (fwd(), [{"forward": {"to": HUB_A, "id": uid("f1")}}], ms(groups=J)),
                     ]))
    out.append(trace("mailbox-forward-pending-group",
                     "A group registered by a welcome but not yet confirmed is forwarded too.", g45, T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         (fwd(), [{"forward": {"to": HUB_A, "id": uid("f1")}}], ms([c(1)], P)),
                     ]))
    out.append(trace("mailbox-forward-unregistered-group-refused",
                     "A mailbox does not forward for a group it has no registration for: it cannot tell a hub from any other service.",
                     g45, T, mbx_ctx(), [
                         (fwd(), [err(BPH, "f1", "mailbox.unknown-group")], ms()),
                     ]))
    out.append(trace("mailbox-forward-other-service-refused",
                     "A deposit for a registered group addressed to a service other than its hub is not forwarded.",
                     g45, T, mbx_ctx(groups=JG), [
                         (fwd(to="did:web:elsewhere.example"), [err(BPH, "f1", "mailbox.unknown-group")], ms(groups=J)),
                     ]))
    out.append(trace("mailbox-forward-other-identity-refused",
                     "A mailbox forwards only for its owner's devices; it is not an open relay.", g45, T, mbx_ctx(groups=JG), [
                         (fwd(identity=CAROL, device=CPH), [err(CPH, "f1", "policy.blocked")], ms(groups=J)),
                     ]))

    out.append(trace("mailbox-hub-deposit-unregistered-group", "Hub fan-out for a group not registered for the owner is refused.",
                     ["M§6.6"], T, mbx_ctx(), [
                         (hubdep("h1", 1), [err(HUB_A, "h1", "mailbox.unknown-group")], ms()),
                     ]))
    out.append(trace("mailbox-hub-deposit-wrong-hub", "Only the registered hub of a group may fan out into it.",
                     ["M§6.6"], T, mbx_ctx(groups={GROUP: {"hub": HUB_A, "state": "joined"}}), [
                         (hubdep("h1", 1, frm="did:web:rogue-hub.example"), [err("did:web:rogue-hub.example", "h1", "mailbox.unknown-group")], ms(groups=J)),
                     ]))
    out.append(trace("mailbox-pending-group-bounded",
                     "A pending group admits a bounded number of items before its owner confirms it.", ["M§6.6"], T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(2))], ms([c(1), c(2)], P)),
                         (hubdep("h2", 2), [macc(HUB_A, "h2", c(3))], ms([c(1), c(2), c(3)], P)),
                         (hubdep("h3", 3), [err(HUB_A, "h3", "mailbox.quota-exceeded")], ms([c(1), c(2), c(3)], P)),
                     ]))
    out.append(trace("mailbox-pending-group-confirmed",
                     "After the owner confirms the group, the pending bound no longer applies.", ["M§6.6", "M§5.7"], T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(2))], ms([c(1), c(2)], P)),
                         (hubdep("h2", 2), [macc(HUB_A, "h2", c(3))], ms([c(1), c(2), c(3)], P)),
                         ({"config": {"id": uid("cfg"), "device": BPH, "groups": [{"group": GROUP, "state": "joined"}]}},
                          [macc(BPH, "cfg")], ms([c(1), c(2), c(3)], J)),
                         (hubdep("h3", 3), [macc(HUB_A, "h3", c(4))], ms([c(1), c(2), c(3), c(4)], J)),
                     ]))
    out.append(trace("mailbox-pending-group-expires",
                     "An unconfirmed pending group is dropped with its items after pending_group_ttl.", ["M§6.6"], T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(2))], ms([c(1), c(2)], P)),
                         ({"advance": 604800}, [], ms([c(1), c(2)], P)),
                         ({"advance": 1}, [], ms()),
                     ]))
    out.append(trace("mailbox-pending-group-expiry-keeps-archive-records",
                     "What a pending group's expiry drops is the hub deposits it admitted. An archive record that references the group "
                     "is the owner's history (M§12.2), stored whatever the group's registration, and stays (spec-gap 91).",
                     ["M§6.6", "M§12.2"], T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(2))], ms([c(1), c(2)], P)),
                         ({"archive": {"id": uid("ar1"), "device": BPH, "ref_group": GROUP, "ref_seq": 1}}, [macc(BPH, "ar1", c(3))],
                          ms([c(1), c(2), c(3)], P)),
                         ({"advance": 604801}, [], ms([c(3)])),
                     ]))
    out.append(trace("mailbox-welcome-after-pending-group-expiry-is-stored-anew",
                     "A welcome is a redelivery only while the mailbox still holds one with those MLS bytes for the group: after the "
                     "pending registration expired and took the first welcome with it, the same welcome again is a new invitation "
                     "— stored, registered pending again, its own cursor (spec-gap 94).", ["M§6.6", "M§14.2"], T,
                     mbx_ctx(admit="open"), [
                         (welcome(), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         ({"advance": 604801}, [], ms()),
                         (welcome(label="w1-again"), [macc(CPH, "w1-again", c(2))], ms([c(2)], P)),
                     ]))
    out.append(trace("mailbox-welcome-same-bytes-for-another-group-is-its-own",
                     "The redelivery check is per group: a welcome for another group is stored on its own, whatever its bytes "
                     "(spec-gap 94).", ["M§6.6", "M§14.2"], T, mbx_ctx(admit="open"), [
                         (welcome(), [macc(CPH, "w1", c(1))], ms([c(1)], P)),
                         (welcome(label="w2", group=GROUP2), [macc(CPH, "w2", c(2))], ms([c(1), c(2)], {GROUP: "pending", GROUP2: "pending"})),
                     ]))
    out.append(trace("mailbox-sync-and-live-push",
                     "sync returns stored items; with live, new items are pushed to the bound device until it unbinds.",
                     ["M§5.4", "M§9.1"], T, mbx_ctx(groups={GROUP: {"hub": HUB_A, "state": "joined"}}), [
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         ({"sync": {"id": uid("s1"), "device": BPH, "since": None, "live": True}},
                          [{"items": {"to": BPH, "in_reply_to": uid("s1"), "cursors": [c(1)], "next": None}}], ms([c(1)], J)),
                         (hubdep("h2", 2), [macc(HUB_A, "h2", c(2)), {"push": {"to": BPH, "cursor": c(2)}}], ms([c(1), c(2)], J)),
                         ({"unbind": {"device": BPH}}, [], ms([c(1), c(2)], J)),
                         (hubdep("h3", 3), [macc(HUB_A, "h3", c(3))], ms([c(1), c(2), c(3)], J)),
                     ]))
    out.append(trace("mailbox-group-info-supersedes",
                     "A mailbox keeps only the latest GroupInfo per group; a new one replaces the stored copy "
                     "(M§5.2 class table), while other classes accumulate.",
                     ["M§5.2", "M§6.6"], T, mbx_ctx(groups={GROUP: {"hub": HUB_A, "state": "joined"}}), [
                         (hubdep("gi1", None, cls="group-info"), [macc(HUB_A, "gi1", c(1))], ms([c(1)], J)),
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(2))], ms([c(1), c(2)], J)),
                         (hubdep("gi2", None, cls="group-info"), [macc(HUB_A, "gi2", c(3))], ms([c(2), c(3)], J)),
                     ]))
    out.append(trace("mailbox-sync-cursor-invalid", "A cursor the mailbox never issued is refused; the device re-syncs from null.",
                     ["M§5.4"], T, mbx_ctx(), [
                         ({"sync": {"id": uid("s1"), "device": BPH, "since": c(9)}}, [err(BPH, "s1", "mailbox.cursor-invalid")], ms()),
                     ]))
    out.append(trace("mailbox-sync-pagination", "sync honours limit and returns next when more items remain.",
                     ["M§5.4"], T, mbx_ctx(groups={GROUP: {"hub": HUB_A, "state": "joined"}}), [
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (hubdep("h2", 2), [macc(HUB_A, "h2", c(2))], ms([c(1), c(2)], J)),
                         (hubdep("h3", 3), [macc(HUB_A, "h3", c(3))], ms([c(1), c(2), c(3)], J)),
                         ({"sync": {"id": uid("s1"), "device": BPH, "since": None, "limit": 2}},
                          [{"items": {"to": BPH, "in_reply_to": uid("s1"), "cursors": [c(1), c(2)], "next": c(2)}}], ms([c(1), c(2), c(3)], J)),
                         ({"sync": {"id": uid("s2"), "device": BPH, "since": c(2), "limit": 2}},
                          [{"items": {"to": BPH, "in_reply_to": uid("s2"), "cursors": [c(3)], "next": None}}], ms([c(1), c(2), c(3)], J)),
                     ]))
    QJ = {GROUP: {"hub": HUB_A, "state": "joined"}}
    out.append(trace("mailbox-queue-mode-deletes-after-every-device-acks",
                     "In queue mode an item is deleted only once every registered device has acknowledged it.",
                     ["M§4.4"], T, mbx_ctx(mode="queue", groups=QJ), [
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (hubdep("h2", 2), [macc(HUB_A, "h2", c(2))], ms([c(1), c(2)], J)),
                         ({"sync": {"id": uid("s1"), "device": BPH, "since": c(2), "ack_through": c(2)}},
                          [{"items": {"to": BPH, "in_reply_to": uid("s1"), "cursors": [], "next": None}}], ms([c(1), c(2)], J)),
                         ({"sync": {"id": uid("s2"), "device": BLA, "since": c(1), "ack_through": c(1)}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s2"), "cursors": [c(2)], "next": None}}], ms([c(2)], J)),
                         ({"sync": {"id": uid("s3"), "device": BLA, "since": c(2), "ack_through": c(2)}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s3"), "cursors": [], "next": None}}], ms([], J)),
                     ]))
    out.append(trace("mailbox-sync-mode-retains-after-ack",
                     "In sync mode acknowledged items are retained so later devices can reconstruct history.",
                     ["M§4.4", "M§12"], T, mbx_ctx(groups=QJ), [
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         ({"sync": {"id": uid("s1"), "device": BPH, "since": c(1), "ack_through": c(1)}},
                          [{"items": {"to": BPH, "in_reply_to": uid("s1"), "cursors": [], "next": None}}], ms([c(1)], J)),
                         ({"sync": {"id": uid("s2"), "device": BLA, "since": c(1), "ack_through": c(1)}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s2"), "cursors": [], "next": None}}], ms([c(1)], J)),
                     ]))
    out.append(trace("mailbox-ephemeral-pushed-never-stored",
                     "Ephemeral fan-out reaches only currently bound devices and is never stored or acknowledged.",
                     ["M§11.2"], T, mbx_ctx(groups=QJ), [
                         ({"sync": {"id": uid("s1"), "device": BLA, "since": None, "live": True}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s1"), "cursors": [], "next": None}}], ms([], J)),
                         (hubdep("typ", None, cls="ephemeral"), [{"push": {"to": BLA, "class": "ephemeral"}}], ms([], J)),
                     ]))
    out.append(trace("mailbox-ephemeral-expired-dropped",
                     "An ephemeral item past the originating deposit's expires_at is dropped, even for a bound device.",
                     ["M§11.2"], T, mbx_ctx(groups=QJ), [
                         ({"sync": {"id": uid("s1"), "device": BLA, "since": None, "live": True}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s1"), "cursors": [], "next": None}}], ms([], J)),
                         ({"hub_deposit": {**hubdep("typ", None, cls="ephemeral")["hub_deposit"], "expires_at": NOW + 10}},
                          [{"push": {"to": BLA, "class": "ephemeral"}}], ms([], J)),
                         ({"advance": 11}, [], ms([], J)),
                         ({"hub_deposit": {**hubdep("typ2", None, cls="ephemeral")["hub_deposit"], "expires_at": NOW + 10}}, [], ms([], J)),
                     ]))
    out.append(trace("mailbox-ephemeral-dropped-at-expiry",
                     "An ephemeral item is pushed a second before the originating deposit's expires_at and dropped at it "
                     "(§12.9, spec-gap 141).", ["M§11.2", "§12.9"], T, mbx_ctx(groups=QJ), [
                         ({"sync": {"id": uid("s1"), "device": BLA, "since": None, "live": True}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s1"), "cursors": [], "next": None}}], ms([], J)),
                         ({"advance": 9}, [], ms([], J)),
                         ({"hub_deposit": {**hubdep("typ", None, cls="ephemeral")["hub_deposit"], "expires_at": NOW + 10}},
                          [{"push": {"to": BLA, "class": "ephemeral"}}], ms([], J)),
                         ({"advance": 1}, [], ms([], J)),
                         ({"hub_deposit": {**hubdep("typ2", None, cls="ephemeral")["hub_deposit"], "expires_at": NOW + 10}}, [], ms([], J)),
                     ]))
    out.append(trace("mailbox-archive-first-wins",
                     "The first archive item per (group, seq) is kept; later ones are acknowledged as duplicates.",
                     ["M§12.2"], T, mbx_ctx(groups=QJ), [
                         ({"archive": {"id": uid("ar1"), "device": BPH, "ref_group": GROUP, "ref_seq": 42}}, [macc(BPH, "ar1", c(1))], ms([c(1)], J)),
                         ({"archive": {"id": uid("ar2"), "device": BLA, "ref_group": GROUP, "ref_seq": 42}},
                          [macc(BLA, "ar2", c(1), dup=True)], ms([c(1)], J)),
                     ]))
    out.append(trace("mailbox-archive-pushed-to-other-bound-devices",
                     "A new archive item is pushed to bound devices other than the one that deposited it.",
                     ["M§12.2", "M§5.4"], T, mbx_ctx(groups=QJ), [
                         ({"sync": {"id": uid("s1"), "device": BLA, "since": None, "live": True}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s1"), "cursors": [], "next": None}}], ms([], J)),
                         ({"sync": {"id": uid("s2"), "device": BPH, "since": None, "live": True}},
                          [{"items": {"to": BPH, "in_reply_to": uid("s2"), "cursors": [], "next": None}}], ms([], J)),
                         ({"archive": {"id": uid("ar1"), "device": BPH, "ref_group": GROUP, "ref_seq": 7}},
                          [macc(BPH, "ar1", c(1)), {"push": {"to": BLA, "cursor": c(1)}}], ms([c(1)], J)),
                     ]))
    out.append(trace("mailbox-archive-refused-in-queue-mode", "Queue-mode mailboxes keep no history and refuse archive items.",
                     ["M§12.2", "M§4.4"], T, mbx_ctx(mode="queue"), [
                         ({"archive": {"id": uid("ar1"), "device": BPH, "ref_group": GROUP, "ref_seq": 42}},
                          [err(BPH, "ar1", "mailbox.unsupported-class")], ms()),
                     ]))
    out.append(trace("mailbox-trace-config-unknown-mode-refused", "An unregistered mode is refused and nothing changes.",
                     ["M§4.4", "M§16"], T, mbx_ctx(), [
                         ({"config": {"id": uid("cfg"), "device": BPH, "mode": "forever"}}, [err(BPH, "cfg", "mailbox.unsupported-mode")], ms()),
                         ({"archive": {"id": uid("ar1"), "device": BPH, "ref_group": GROUP, "ref_seq": 1}}, [macc(BPH, "ar1", c(1))], ms([c(1)])),
                     ]))
    KP = {BLA: {"one_time": 1, "last_resort": True}, BPH: {"one_time": 0, "last_resort": False}}
    out.append(trace("mailbox-key-packages-single-use-then-last-resort",
                     "Each fetch consumes one KeyPackage per device; an exhausted device falls back to its last resort, "
                     "and a device with neither is omitted.",
                     ["M§5.5"], T, mbx_ctx(key_packages=KP), [
                         ({"kp_fetch": {"id": uid("f1"), "from": CPH, "from_identity": CAROL, "target": BOB, "grant": grant()}},
                          [{"key_packages": {"to": CPH, "in_reply_to": uid("f1"), "devices": {BLA: "one-time"}}}],
                          ms(kps={BLA: {"one_time": 0, "last_resort": True}, BPH: {"one_time": 0, "last_resort": False}})),
                         ({"kp_fetch": {"id": uid("f2"), "from": CPH, "from_identity": CAROL, "target": BOB, "grant": grant()}},
                          [{"key_packages": {"to": CPH, "in_reply_to": uid("f2"), "devices": {BLA: "last-resort"}}}],
                          ms(kps={BLA: {"one_time": 0, "last_resort": True}, BPH: {"one_time": 0, "last_resort": False}})),
                         ({"kp_upload": {"id": uid("u1"), "device": BPH, "count": 2, "last_resort": True}}, [macc(BPH, "u1")],
                          ms(kps={BLA: {"one_time": 0, "last_resort": True}, BPH: {"one_time": 2, "last_resort": True}})),
                         ({"kp_fetch": {"id": uid("f3"), "from": CPH, "from_identity": CAROL, "target": BOB, "grant": grant()}},
                          [{"key_packages": {"to": CPH, "in_reply_to": uid("f3"), "devices": {BLA: "last-resort", BPH: "one-time"}}}],
                          ms(kps={BLA: {"one_time": 0, "last_resort": True}, BPH: {"one_time": 1, "last_resort": True}})),
                     ]))
    out.append(trace("mailbox-key-package-fetch-unauthorized", "A fetch without authorization is refused and consumes nothing.",
                     ["M§5.5", "M§14.2"], T, mbx_ctx(key_packages={BPH: {"one_time": 3, "last_resort": True}}), [
                         ({"kp_fetch": {"id": uid("f1"), "from": MPH, "from_identity": MALLORY, "target": BOB, "grant": None}},
                          [err(MPH, "f1", "policy.first-contact-required")], ms(kps={BPH: {"one_time": 3, "last_resort": True}})),
                     ]))
    out.append(trace("mailbox-key-package-fetch-none-available", "With no KeyPackage and no last resort for any device the fetch fails.",
                     ["M§5.5", "M§16"], T, mbx_ctx(), [
                         ({"kp_fetch": {"id": uid("f1"), "from": CPH, "from_identity": CAROL, "target": BOB, "grant": grant()}},
                          [err(CPH, "f1", "mailbox.no-key-packages")], ms()),
                     ]))
    out.append(trace("mailbox-key-package-upload-bounded", "A mailbox keeps at most 100 one-time KeyPackages per device.",
                     ["M§5.5"], T, mbx_ctx(key_packages={BPH: {"one_time": 90, "last_resort": False}}), [
                         ({"kp_upload": {"id": uid("u1"), "device": BPH, "count": 20}}, [macc(BPH, "u1")],
                          ms(kps={BPH: {"one_time": 100, "last_resort": False}})),
                     ]))

    # --- owner quota (M§4.3 quota_bytes, M§4.4, M§14.3; spec-gap 99): a stored item's `size` counts against the
    # owner's quota_bytes; a deposit that would exceed it is refused mailbox.quota-exceeded before anything is
    # stored or registered. Redeliveries are never refused. Introductions are bounded by the §19.4 inbox instead.
    def mq(items=(), groups=None, used=0):
        return {**ms(items, groups), "used_bytes": used}
    QJ_ = {GROUP: {"hub": HUB_A, "state": "joined"}}
    Q = "mailbox.quota-exceeded"
    G99 = ["M§4.4", "M§14.3"]
    out.append(trace("mailbox-quota-refuses-a-deposit-that-would-exceed-it",
                     "600 of 1,000 bytes used: a 500-byte item is refused, a 400-byte one fills the quota exactly.", G99, T,
                     mbx_ctx(groups=QJ_, quota_bytes=1000), [
                         (hubdep("h1", 1, size=600), [macc(HUB_A, "h1", c(1))], mq([c(1)], J, 600)),
                         (hubdep("h2", 2, size=500), [err(HUB_A, "h2", Q)], mq([c(1)], J, 600)),
                         (hubdep("h3", 2, size=400), [macc(HUB_A, "h3", c(2))], mq([c(1), c(2)], J, 1000)),
                     ]))
    out.append(trace("mailbox-quota-never-refuses-a-redelivery",
                     "A full mailbox still acknowledges a hub's retry of an item it holds: nothing new is stored.", G99 + ["M§9.3"], T,
                     mbx_ctx(groups=QJ_, quota_bytes=1000), [
                         (hubdep("h1", 1, size=1000), [macc(HUB_A, "h1", c(1))], mq([c(1)], J, 1000)),
                         (hubdep("h1r", 1, size=1000), [macc(HUB_A, "h1r", c(1), dup=True)], mq([c(1)], J, 1000)),
                     ]))
    out.append(trace("mailbox-quota-counts-archive-records",
                     "Archive records are stored for the owner and count against the quota like any item.", G99 + ["M§12.2"], T,
                     mbx_ctx(groups=QJ_, quota_bytes=1000), [
                         (hubdep("h1", 1, size=900), [macc(HUB_A, "h1", c(1))], mq([c(1)], J, 900)),
                         ({"archive": {"id": uid("ar1"), "device": BPH, "ref_group": GROUP, "ref_seq": 1, "size": 200}},
                          [err(BPH, "ar1", Q)], mq([c(1)], J, 900)),
                         ({"archive": {"id": uid("ar2"), "device": BPH, "ref_group": GROUP, "ref_seq": 1, "size": 100}},
                          [macc(BPH, "ar2", c(2))], mq([c(1), c(2)], J, 1000)),
                     ]))
    out.append(trace("mailbox-quota-refused-welcome-registers-nothing",
                     "A welcome too large for the remaining quota is refused and leaves no pending group behind.", G99 + ["M§6.6"], T,
                     mbx_ctx(quota_bytes=500), [
                         (welcome("w1", grant_=grant(), size=600), [err(CPH, "w1", Q)], mq([], {}, 0)),
                         (welcome("w2", grant_=grant(), size=400, digest="d-welcome-2"), [macc(CPH, "w2", c(1))],
                          mq([c(1)], P, 400)),
                     ]))
    out.append(trace("mailbox-quota-freed-when-queue-mode-items-leave",
                     "In queue mode, an item every device has acknowledged is deleted and its bytes are free again.", G99, T,
                     mbx_ctx(mode="queue", groups=QJ_, quota_bytes=1000), [
                         (hubdep("h1", 1, size=600), [macc(HUB_A, "h1", c(1))], mq([c(1)], J, 600)),
                         (hubdep("h2", 2, size=500), [err(HUB_A, "h2", Q)], mq([c(1)], J, 600)),
                         ({"sync": {"id": uid("s1"), "device": BPH, "since": c(1), "ack_through": c(1)}},
                          [{"items": {"to": BPH, "in_reply_to": uid("s1"), "cursors": [], "next": None}}], mq([c(1)], J, 600)),
                         ({"sync": {"id": uid("s2"), "device": BLA, "since": c(1), "ack_through": c(1)}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s2"), "cursors": [], "next": None}}], mq([], J, 0)),
                         (hubdep("h3", 2, size=500), [macc(HUB_A, "h3", c(2))], mq([c(2)], J, 500)),
                     ]))
    out.append(trace("mailbox-quota-survives-restart",
                     "The quota and the bytes in use are durable: after a restart the same deposit is still refused.", G99 + ["M§9.3"], T,
                     mbx_ctx(groups=QJ_, quota_bytes=1000), [
                         (hubdep("h1", 1, size=700), [macc(HUB_A, "h1", c(1))], mq([c(1)], J, 700)),
                         ({"restart": {}}, [], mq([c(1)], J, 700)),
                         (hubdep("h2", 2, size=400), [err(HUB_A, "h2", Q)], mq([c(1)], J, 700)),
                     ]))
    out.append(trace("mailbox-quota-counts-the-group-info-a-deposit-would-replace",
                     "Only the latest GroupInfo is kept, but the one a deposit would replace still counts while the deposit is "
                     "checked: nothing is removed unless the deposit is accepted.", G99 + ["M§5.2"], T,
                     mbx_ctx(groups=QJ_, quota_bytes=1000), [
                         (hubdep("gi1", 1, cls="group-info", size=600), [macc(HUB_A, "gi1", c(1))], mq([c(1)], J, 600)),
                         (hubdep("gi2", 2, cls="group-info", size=500), [err(HUB_A, "gi2", Q)], mq([c(1)], J, 600)),
                         (hubdep("gi3", 2, cls="group-info", size=400), [macc(HUB_A, "gi3", c(2))], mq([c(2)], J, 400)),
                     ]))
    out.append(trace("mailbox-quota-does-not-apply-to-introductions",
                     "Introductions are bounded by the §19.4 inbox, never by quota: refusing one would tell a stranger the "
                     "recipient exists and is full. The held introduction's size is not counted.", G99 + ["§19.4"], T,
                     mbx_ctx(quota_bytes=100, intro_limit=5, intro_window=3600, inbox_cap=16), [
                         ({"first_contact": {"id": uid("i1"), "from": APH, "sender_identity": ALICE, "recipient": BOB,
                                             "kind": "introduction", "expires_at": NOW + 604800, "size": 500}},
                          [macc(APH, "i1", c(1))], mq([c(1)], {}, 0)),
                     ]))
    return out


# ---------------------------------------------------------------- tranche 2: voicemail offer (M§13.2)

def voicemail_offer_vectors():
    out = []
    VM = {"max_duration_s": 180}

    def vo(vid, desc, outcome, expect, voicemail=VM, can_send=True):
        inp = {"check": "voicemail-offer", "voicemail": voicemail, "can_send": can_send, "outcome": outcome}
        out.append(mv(f"voicemail-offer-{vid}", desc, ["M§13.2"], inp, expect))

    yes = {"offer": True, "max_duration_s": 180}
    no = {"offer": False}
    vo("no-answer", "reject user.no-answer offers voicemail.", {"type": "reject", "reason": "user.no-answer"}, yes)
    vo("declined", "reject user.declined offers voicemail.", {"type": "reject", "reason": "user.declined"}, yes)
    vo("busy", "reject endpoint.busy offers voicemail.", {"type": "reject", "reason": "endpoint.busy"}, yes)
    vo("unavailable", "reject endpoint.unavailable offers voicemail.", {"type": "reject", "reason": "endpoint.unavailable"}, yes)
    vo("caller-timeout", "The caller's own cancel session.timeout (T-Establish/T-Ring) offers voicemail.",
       {"type": "cancel", "reason": "session.timeout"}, yes)
    vo("blocked", "user.blocked never offers voicemail.", {"type": "reject", "reason": "user.blocked"}, no)
    vo("policy", "policy.* never offers voicemail.", {"type": "reject", "reason": "policy.first-contact-required"}, no)
    vo("identity", "identity.* never offers voicemail.", {"type": "reject", "reason": "identity.not-in-service"}, no)
    vo("media", "media.* never offers voicemail.", {"type": "reject", "reason": "media.unsupported"}, no)
    vo("answered-elsewhere", "session.answered-elsewhere is not a missed call and never offers voicemail.",
       {"type": "cancel", "reason": "session.answered-elsewhere"}, no)
    vo("registered-endpoint-capability", "A registered endpoint token outside the list (endpoint.capability) does not offer.",
       {"type": "reject", "reason": "endpoint.capability"}, no)
    vo("unregistered-endpoint-condition", "An unregistered endpoint.* condition falls back to its category and offers "
       "(endpoint state prevented the call, like busy or unavailable).", {"type": "reject", "reason": "endpoint.do-not-disturb"}, yes)
    vo("unregistered-user-condition", "An unregistered user.* condition does not offer (conservative: it may be block-like).",
       {"type": "reject", "reason": "user.stepped-out"}, no)
    vo("not-advertised", "No voicemail advertisement in the callee's DSIPMailbox entry: no offer.",
       {"type": "reject", "reason": "user.no-answer"}, no, voicemail=None)
    vo("cannot-send", "No conversation and no authorization to create one: no offer.",
       {"type": "reject", "reason": "user.no-answer"}, no, can_send=False)
    vo("no-max-duration", "An advertisement without max_duration_s still offers, with no duration bound in the result.",
       {"type": "reject", "reason": "user.no-answer"}, {"offer": True}, voicemail={})
    return out


# ---------------------------------------------------------------- tranche 2: conversation convergence (M§7.2, M§7.5)

def conversation_vectors():
    out = []
    c_early, c_late = uid("dc-a", NOW - 2), uid("dc-b", NOW)
    out.append(mv("direct-select-lower-ulid-wins", "Two concurrent direct conversations converge on the lower ULID.", ["M§7.2"],
                  {"check": "direct-select", "candidates": [{"conversation": c_late, "issued_at": NOW},
                                                           {"conversation": c_early, "issued_at": NOW - 2}]},
                  {"winner": c_early, "discarded": []}))
    backdated = uid("dc-backdated", NOW - 3600)
    out.append(mv("direct-select-backdated-discarded",
                  "A conversation ULID backdated an hour against its creating deposit's issued_at cannot win (§20.6 guard).",
                  ["M§7.2", "§20.6"],
                  {"check": "direct-select", "candidates": [{"conversation": c_late, "issued_at": NOW},
                                                           {"conversation": backdated, "issued_at": NOW}]},
                  {"winner": c_late, "discarded": [backdated]}))
    out.append(mv("successor-check-valid", "A predecessor member re-creating the group with predecessor members is accepted.",
                  ["M§7.5"], {"check": "successor-check", "predecessor_roster": [ALICE, BOB, CAROL], "creator": BOB,
                              "roster": [ALICE, BOB, CAROL]}, accept()))
    out.append(mv("successor-check-roster-shrink-valid", "A successor may omit predecessor members.", ["M§7.5"],
                  {"check": "successor-check", "predecessor_roster": [ALICE, BOB, CAROL], "creator": BOB, "roster": [ALICE, BOB]},
                  accept()))
    out.append(mv("successor-check-creator-not-member", "A successor created by a non-member is a new conversation, not a successor.",
                  ["M§7.5"], {"check": "successor-check", "predecessor_roster": [ALICE, BOB], "creator": MALLORY,
                              "roster": [ALICE, BOB, MALLORY]}, reject("successor-invalid")))
    out.append(mv("successor-check-adds-outsider", "A successor that adds an identity outside the predecessor roster is rejected.",
                  ["M§7.5"], {"check": "successor-check", "predecessor_roster": [ALICE, BOB], "creator": BOB,
                              "roster": [ALICE, BOB, MALLORY]}, reject("successor-invalid")))
    # Pick two group ULIDs whose base64url text sorts opposite to the ULIDs themselves.
    ga, gb = None, None
    for i in range(200):
        u1, u2 = uid(f"succ-a-{i}", NOW), uid(f"succ-b-{i}", NOW)
        lo, hi = sorted([u1, u2])
        b_lo, b_hi = b64url_encode(lo.encode()), b64url_encode(hi.encode())
        if b_lo > b_hi:
            ga, gb = b_lo, b_hi
            break
    assert ga is not None
    out.append(mv("successor-select-compares-decoded-ulid",
                  "Concurrent successors converge on the lowest group_id compared as the decoded ULID; here the base64url "
                  "text sorts the other way.", ["M§7.5"],
                  {"check": "successor-select", "candidates": [gb, ga]}, {"winner": ga, "discarded": []}))
    junk = b64url_encode(b"not-a-ulid")
    out.append(mv("successor-select-invalid-group-id-discarded", "A group_id that is not a ULID cannot win.", ["M§7.5", "M§6.3"],
                  {"check": "successor-select", "candidates": [junk, ga]}, {"winner": ga, "discarded": [junk]}))
    return out


# ---------------------------------------------------------------- tranche 2: client receipts and activity (M§10, M§11.2)

def cl_ctx(me=BOB, delivered=True, read=False, played=False, activity=False, members=2):
    return {"component": "client", "me": me, "device": BPH, "now": NOW, "member_identities": members,
            "policy": {"delivered": delivered, "read": read, "played": played, "activity": activity}}


def cs(timeline=(), delivered=None, played=None, read_through=None, activity=None):
    return {"timeline": list(timeline), "delivered": delivered or {}, "played": played or {}, "read_through": read_through or {},
            "activity": activity or {}}


def item(seq, obj):
    return {"seq": seq, "object": obj}


def ct(label, sender=ALICE, kind="text"):
    return {"object": "content", "id": uid(label), "sender": sender, "kind": kind}


def rc(kind, sender, at=NOW, **kw):
    return {"object": "receipt", "kind": kind, "sender": sender, "sent_at": at, **kw}


def sync(*items):
    return {"sync": {"items": list(items)}}


def send(to, receipt, **kw):
    return {"send": {"to": to, "receipt": receipt, **kw}}


def client_vectors():
    out = []
    T = "client-trace"
    m1, m2, m3, vm = uid("m1"), uid("m2"), uid("m3"), uid("vm")

    out.append(trace("client-delivered-sent-once-per-batch",
                     "After a sync batch the device sends one delivered receipt covering every new item from other identities.",
                     ["M§10.2"], T, cl_ctx(), [
                         (sync(item(1, ct("m1")), item(2, ct("m2")), item(3, ct("m3", sender=BOB))),
                          [send("conversation", "delivered", targets=[m1, m2])], cs([m1, m2, m3])),
                         (sync(item(1, ct("m1"))), [], cs([m1, m2, m3])),
                     ]))
    out.append(trace("client-delivered-suppressed-by-sibling-in-batch",
                     "A sibling device's delivered receipt later in the same batch suppresses this device's receipt for that item.",
                     ["M§10.2"], T, cl_ctx(), [
                         (sync(item(1, ct("m1")), item(2, ct("m2")), item(3, rc("delivered", BOB, targets=[m1]))),
                          [{"archive": {"seq": 3}}, send("conversation", "delivered", targets=[m2])], cs([m1, m2], delivered={m1: {BOB: NOW}})),
                     ]))
    out.append(trace("client-delivered-off-by-policy", "delivered receipts are not sent when the user has them off.",
                     ["M§10.2", "M§10.5"], T, cl_ctx(delivered=False), [
                         (sync(item(1, ct("m1"))), [], cs([m1])),
                     ]))
    out.append(trace("client-delivered-not-in-large-group", "No delivered receipts in groups over 32 member identities.",
                     ["M§10.2"], T, cl_ctx(members=33), [
                         (sync(item(1, ct("m1"))), [], cs([m1])),
                     ]))
    out.append(trace("client-receipts-collapse-first-by-seq",
                     "Duplicate delivered receipts from one identity collapse; the first by seq keeps its timestamp.",
                     ["M§10.2"], T, cl_ctx(me=ALICE, delivered=False), [
                         (sync(item(1, ct("m1")), item(2, rc("delivered", BOB, at=NOW + 1, targets=[m1])),
                               item(3, rc("delivered", BOB, at=NOW + 2, targets=[m1]))),
                          [{"archive": {"seq": 2}}], cs([m1], delivered={m1: {BOB: NOW + 1}})),
                     ]))
    out.append(trace("client-receipt-from-content-sender-ignored",
                     "An identity's receipt about its own content is not a sender-visible receipt.", ["M§10.2"], T,
                     cl_ctx(me=BOB, delivered=False), [
                         (sync(item(1, ct("m1")), item(2, rc("delivered", ALICE, targets=[m1]))), [], cs([m1])),
                     ]))
    out.append(trace("client-played-only-for-media", "played applies to audio and video content only.", ["M§10.4"], T,
                     cl_ctx(me=ALICE, delivered=False), [
                         (sync(item(1, ct("m1")), item(2, ct("vm", kind="audio")),
                               item(3, rc("played", BOB, targets=[m1, vm]))),
                          [{"archive": {"seq": 3}}], cs([m1, vm], played={vm: {BOB: NOW}})),
                     ]))
    out.append(trace("client-read-watermark-monotone",
                     "A read watermark only advances; a lower or unknown through is ignored.", ["M§10.3"], T,
                     cl_ctx(me=ALICE, delivered=False), [
                         (sync(item(1, ct("m1")), item(2, ct("m2")), item(3, rc("read", BOB, through=m2))),
                          [{"archive": {"seq": 3}}], cs([m1, m2], read_through={BOB: m2})),
                         (sync(item(4, rc("read", BOB, through=m1))), [], cs([m1, m2], read_through={BOB: m2})),
                         (sync(item(5, rc("read", BOB, through=uid("never-seen")))), [], cs([m1, m2], read_through={BOB: m2})),
                     ]))
    out.append(trace("client-read-through-the-readers-own-content",
                     "A watermark marks a position in the conversation, which may be the reader's own message: it is applied. "
                     "\"A receipt from the identity that sent the target\" (M§10.2) is about delivered and played.", ["M§10.3", "M§10.2"], T,
                     cl_ctx(me=ALICE, delivered=False), [
                         (sync(item(1, ct("m1")), item(2, ct("m2", sender=BOB)), item(3, rc("read", BOB, through=m2)),
                               item(4, rc("delivered", BOB, targets=[m2]))),
                          [{"archive": {"seq": 3}}], cs([m1, m2], read_through={BOB: m2})),
                     ]))
    out.append(trace("client-read-private-goes-to-personal-group",
                     "With read receipts off, the device still syncs its watermark, to its personal group only.",
                     ["M§10.5"], T, cl_ctx(delivered=False, read=False), [
                         (sync(item(1, ct("m1"))), [], cs([m1])),
                         ({"read": {"through": m1}}, [send("personal", "read", through=m1)], cs([m1], read_through={BOB: m1})),
                     ]))
    out.append(trace("client-read-disclosed-goes-to-conversation",
                     "With read receipts opted in, the watermark goes to the conversation group.", ["M§10.5", "M§10.3"], T,
                     cl_ctx(delivered=False, read=True), [
                         (sync(item(1, ct("m1"))), [], cs([m1])),
                         ({"read": {"through": m1}}, [send("conversation", "read", through=m1)], cs([m1], read_through={BOB: m1})),
                     ]))
    out.append(trace("client-read-sibling-watermark-suppresses",
                     "A sibling device's watermark already covering the item means reading it here sends nothing.",
                     ["M§10.3"], T, cl_ctx(delivered=False, read=True), [
                         (sync(item(1, ct("m1")), item(2, ct("m2")), item(3, rc("read", BOB, through=m2))),
                          [{"archive": {"seq": 3}}], cs([m1, m2], read_through={BOB: m2})),
                         ({"read": {"through": m1}}, [], cs([m1, m2], read_through={BOB: m2})),
                     ]))
    out.append(trace("client-read-rate-limited",
                     "At most one watermark per conversation per 5 s: a later read is held and the latest watermark sent when the "
                     "interval passes.", ["M§10.3"], T, cl_ctx(delivered=False, read=True), [
                         (sync(item(1, ct("m1")), item(2, ct("m2")), item(3, ct("m3"))), [], cs([m1, m2, m3])),
                         ({"read": {"through": m1}}, [send("conversation", "read", through=m1)], cs([m1, m2, m3], read_through={BOB: m1})),
                         ({"advance": 1}, [], cs([m1, m2, m3], read_through={BOB: m1})),
                         ({"read": {"through": m2}}, [], cs([m1, m2, m3], read_through={BOB: m2})),
                         ({"read": {"through": m3}}, [], cs([m1, m2, m3], read_through={BOB: m3})),
                         ({"advance": 3}, [], cs([m1, m2, m3], read_through={BOB: m3})),
                         ({"advance": 1}, [send("conversation", "read", through=m3)], cs([m1, m2, m3], read_through={BOB: m3})),
                     ]))
    out.append(trace("client-played-sent-once-when-opted-in", "A played receipt is sent once, for media, when opted in.",
                     ["M§10.4", "M§10.5"], T, cl_ctx(delivered=False, played=True), [
                         (sync(item(1, ct("vm", kind="audio")), item(2, ct("m1"))), [], cs([vm, m1])),
                         ({"play": {"id": m1}}, [], cs([vm, m1])),
                         ({"play": {"id": vm}}, [send("conversation", "played", targets=[vm])], cs([vm, m1])),
                         ({"play": {"id": vm}}, [], cs([vm, m1])),
                     ]))
    out.append(trace("client-played-off-by-default", "played receipts are not sent without opt-in.", ["M§10.5"], T,
                     cl_ctx(delivered=False), [
                         (sync(item(1, ct("vm", kind="audio"))), [], cs([vm])),
                         ({"play": {"id": vm}}, [], cs([vm])),
                     ]))
    out.append(trace("client-duplicate-content-collapses",
                     "The same content id arriving again (another mailbox, a successor group) is collapsed and keeps its first place.",
                     ["M§8.5"], T, cl_ctx(delivered=False), [
                         (sync(item(1, ct("m1")), item(2, ct("m2"))), [], cs([m1, m2])),
                         (sync(item(7, ct("m1"))), [], cs([m1, m2])),
                     ]))
    act = lambda a, st: {"activity": {"activity": a, "state": st}}
    typing = lambda st: {"send": {"to": "conversation", "activity": "typing", "state": st}}
    out.append(trace("client-activity-refresh-bounded",
                     "Typing refreshes are sent at most every 5 s; stopped is always sent.", ["M§11.2"], T,
                     cl_ctx(delivered=False, activity=True), [
                         (act("typing", "active"), [typing("active")], cs()),
                         ({"advance": 2}, [], cs()),
                         (act("typing", "active"), [], cs()),
                         ({"advance": 3}, [], cs()),
                         (act("typing", "active"), [typing("active")], cs()),
                         (act("typing", "stopped"), [typing("stopped")], cs()),
                         (act("typing", "active"), [typing("active")], cs()),
                     ]))
    out.append(trace("client-activity-off-by-default", "Activity is not sent without opt-in.", ["M§11.2", "M§10.5"], T,
                     cl_ctx(delivered=False), [
                         (act("typing", "active"), [], cs()),
                     ]))
    ain = lambda sender, activity="typing", state="active", exp=NOW + 10: {"activity_in": {"sender": sender, "activity": activity,
                                                                                      "state": state, "expires_at": exp}}
    out.append(trace("client-activity-shown-until-expiry",
                     "A received activity is shown until the expires_at of its last refresh, then cleared with no message: "
                     "shown a second before it, gone at it (§12.9, spec-gap 141).",
                     ["M§11.2", "§12.9"], T, cl_ctx(), [
                         (ain(ALICE), [], cs(activity={ALICE: {"typing": NOW + 10}})),
                         ({"advance": 9}, [], cs(activity={ALICE: {"typing": NOW + 10}})),
                         ({"advance": 1}, [], cs()),
                     ]))
    out.append(trace("client-activity-refresh-extends",
                     "A refresh before expiry moves the indicator's deadline to the refresh's expires_at.",
                     ["M§11.2"], T, cl_ctx(), [
                         (ain(ALICE), [], cs(activity={ALICE: {"typing": NOW + 10}})),
                         ({"advance": 5}, [], cs(activity={ALICE: {"typing": NOW + 10}})),
                         (ain(ALICE, exp=NOW + 15), [], cs(activity={ALICE: {"typing": NOW + 15}})),
                         ({"advance": 8}, [], cs(activity={ALICE: {"typing": NOW + 15}})),
                         ({"advance": 3}, [], cs()),
                     ]))
    out.append(trace("client-activity-stopped-clears",
                     "stopped clears that activity at once and leaves the sender's other activities.",
                     ["M§11.2"], T, cl_ctx(), [
                         (ain(ALICE), [], cs(activity={ALICE: {"typing": NOW + 10}})),
                         (ain(ALICE, "uploading"), [], cs(activity={ALICE: {"typing": NOW + 10, "uploading": NOW + 10}})),
                         (ain(ALICE, state="stopped"), [], cs(activity={ALICE: {"uploading": NOW + 10}})),
                     ]))
    out.append(trace("client-activity-expired-on-arrival-ignored",
                     "An activity that arrives after its expires_at is never shown.",
                     ["M§11.2"], T, cl_ctx(), [
                         ({"advance": 20}, [], cs()),
                         (ain(ALICE), [], cs()),
                     ]))
    return out


# ---------------------------------------------------------------- tranche 2: seq gaps (M§6.5)

def gap_vectors():
    out = []
    out.append(trace("gap-timeout-configurable",
                     "A device may hold for less than the RECOMMENDED 300 s before re-joining (spec-gap 69): the timeout is the "
                     "device's, the rule is not.", ["M§6.5", "M§6.8"], "gap-trace", {"component": "gap", "now": NOW, "contiguous": 1,
                                                                                     "gap_timeout": 5}, [
                         ({"item": {"seq": 3, "class": "handshake"}}, [{"hold": 3}], {"contiguous": 1, "held": [3]}),
                         ({"advance": 4}, [], {"contiguous": 1, "held": [3]}),
                         ({"advance": 1}, [{"rejoin": {"held": [3]}}], {"contiguous": 3, "held": []}),
                     ]))
    T = "gap-trace"
    ctx = {"component": "gap", "now": NOW, "contiguous": 0}
    it = lambda seq, cls="application": {"item": {"seq": seq, "class": cls}}
    g = lambda contiguous, held=(): {"contiguous": contiguous, "held": list(held)}
    out.append(trace("gap-in-order", "Items in seq order are processed as they arrive.", ["M§6.5"], T, ctx, [
        (it(1, "handshake"), [{"process": 1}], g(1)),
        (it(2), [{"process": 2}], g(2)),
    ]))
    out.append(trace("gap-application-across-gap-processed",
                     "An application item beyond a gap is processed; nothing is held.", ["M§6.5"], T, ctx, [
                         (it(1), [{"process": 1}], g(1)),
                         (it(3), [{"process": 3}], g(1)),
                         (it(2), [{"process": 2}], g(3)),
                     ]))
    out.append(trace("gap-handshake-held-until-filled",
                     "A handshake item beyond a gap is held, and so is everything after it, until the gap fills.", ["M§6.5"], T, ctx, [
                         (it(1), [{"process": 1}], g(1)),
                         (it(3, "handshake"), [{"hold": 3}], g(1, [3])),
                         (it(4), [{"hold": 4}], g(1, [3, 4])),
                         (it(2), [{"process": 2}, {"process": 3}, {"process": 4}], g(4)),
                     ]))
    out.append(trace("gap-timeout-rejoins",
                     "A gap not filled within 300 s of the first held item makes the device re-join by external commit.",
                     ["M§6.5", "M§6.8"], T, ctx, [
                         (it(1), [{"process": 1}], g(1)),
                         (it(3, "handshake"), [{"hold": 3}], g(1, [3])),
                         ({"advance": 299}, [], g(1, [3])),
                         ({"advance": 1}, [{"rejoin": {"held": [3]}}], g(3)),
                         (it(2), [{"duplicate": 2}], g(3)),
                     ]))
    out.append(trace("gap-duplicate-seq", "A seq already processed is reported as a duplicate and not processed again.",
                     ["M§6.5", "M§8.5"], T, ctx, [
                         (it(1), [{"process": 1}], g(1)),
                         (it(1), [{"duplicate": 1}], g(1)),
                     ]))
    return out


def resume_vectors():
    """What a device keeps across a restart (M§5.4 `ack_through`, M§8.5; spec-gap 44). Every item is
    processed and committed with the ack cursor and seq positions atomically, or not at all."""
    out = []
    T = "resume-trace"
    ctx = {"component": "resume", "cursor": None, "groups": {}, "joined": []}
    refs = ["M§5.4", "M§8.5"]

    def it(n, cls="application", seq=None, group=GROUP):
        d = {"cursor": c(n), "class": cls, "group": group}
        if seq is not None:
            d["seq"] = seq
        return d

    def items(*its, crash_at=None):
        e = {"items": list(its)}
        if crash_at is not None:
            e["crash_at"] = c(crash_at)
        return {"items": e}

    def st(cursor=None, groups=None, joined=()):
        return {"cursor": None if cursor is None else c(cursor),
                "groups": {g: {"contiguous": p[0], "seen": list(p[1]) if len(p) > 1 else []} for g, p in (groups or {}).items()},
                "joined": list(joined)}

    def sync(cursor):
        return [{"sync": {"since": None} if cursor is None else {"since": c(cursor), "ack_through": c(cursor)}}]

    W = it(1, "welcome")
    out.append(trace("resume-rejoin-passes-every-seq-seen",
                     "After re-joining by external commit (M§6.8) the device treats every seq up to the highest it has seen as "
                     "passed (spec-gap 69): those items are gone or for epochs it cannot reach, and a later redelivery is a "
                     "duplicate.", refs + ["M§6.5", "M§6.8"], T, ctx, [
                         (items(W, it(2, seq=1), it(3, seq=4)),
                          [{"process": c(1)}, {"process": c(2)}, {"process": c(3)}], st(3, {GROUP: (1, [4])}, [GROUP])),
                         ({"rejoined": {"group": GROUP, "seq": 6}}, [], st(3, {GROUP: (6,)}, [GROUP])),
                         (items(it(4, seq=5), it(5, seq=7)), [{"duplicate": c(4)}, {"process": c(5)}],
                          st(5, {GROUP: (7,)}, [GROUP])),
                     ]))
    out.append(trace("resume-restart-syncs-from-committed-cursor",
                     "After a restart the device resumes from, and acknowledges through, the last item it committed.", refs, T, ctx, [
                         (items(W, it(2, seq=1), it(3, seq=2)), [{"process": c(1)}, {"process": c(2)}, {"process": c(3)}],
                          st(3, {GROUP: (2,)}, [GROUP])),
                         ({"restart": {}}, sync(3), st(3, {GROUP: (2,)}, [GROUP])),
                     ]))
    out.append(trace("resume-crash-rolls-back-uncommitted-item",
                     "An item processed but not committed when the device dies is rolled back with its MLS state, "
                     "so it is not acknowledged and is processed normally when redelivered.", refs, T, ctx, [
                         (items(W, it(2, seq=1), it(3, seq=2), crash_at=3), [{"process": c(1)}, {"process": c(2)}, {"crash": c(3)}],
                          st(2, {GROUP: (1,)}, [GROUP])),
                         ({"restart": {}}, sync(2), st(2, {GROUP: (1,)}, [GROUP])),
                         (items(it(3, seq=2)), [{"process": c(3)}], st(3, {GROUP: (2,)}, [GROUP])),
                     ]))
    out.append(trace("resume-crash-before-first-commit-no-ack",
                     "A device that commits nothing before dying re-syncs from null and acknowledges nothing.", refs, T, ctx, [
                         (items(W, crash_at=1), [{"crash": c(1)}], st()),
                         ({"restart": {}}, sync(None), st()),
                         (items(W), [{"process": c(1)}], st(1, joined=[GROUP])),
                     ]))
    out.append(trace("resume-cursor-invalid-redelivery-collapses-by-seq",
                     "After mailbox.cursor-invalid the device re-syncs from null; sequenced items it already processed "
                     "are recognised by seq without decrypting them (their MLS secrets are gone), and new ones are processed.",
                     refs + ["M§6.5"], T, ctx, [
                         (items(W, it(2, seq=1), it(3, seq=2)), [{"process": c(1)}, {"process": c(2)}, {"process": c(3)}],
                          st(3, {GROUP: (2,)}, [GROUP])),
                         ({"cursor_invalid": {}}, sync(None), st(None, {GROUP: (2,)}, [GROUP])),
                         (items(it(7, seq=1), it(8, seq=2), it(9, seq=3)),
                          [{"duplicate": c(7)}, {"duplicate": c(8)}, {"process": c(9)}], st(9, {GROUP: (3,)}, [GROUP])),
                     ]))
    out.append(trace("resume-duplicate-is-acknowledged",
                     "A duplicate still advances the ack cursor: it is already durably processed, and an unacknowledged "
                     "item would be retained and redelivered forever.", refs + ["M§4.4"], T,
                     {"component": "resume", "cursor": c(3), "groups": {GROUP: {"contiguous": 2, "seen": []}}, "joined": [GROUP]}, [
                         (items(it(4, seq=2)), [{"duplicate": c(4)}], st(4, {GROUP: (2,)}, [GROUP])),
                         ({"sync": {}}, sync(4), st(4, {GROUP: (2,)}, [GROUP])),
                     ]))
    out.append(trace("resume-welcome-for-joined-group-is-duplicate",
                     "A redelivered welcome for a group the device already joined is a duplicate; its KeyPackage is consumed.",
                     refs + ["M§6.6"], T, ctx, [
                         (items(W), [{"process": c(1)}], st(1, joined=[GROUP])),
                         ({"cursor_invalid": {}}, sync(None), st(None, joined=[GROUP])),
                         (items(W), [{"duplicate": c(1)}], st(1, joined=[GROUP])),
                     ]))
    out.append(trace("resume-seq-positions-per-group",
                     "Seq positions are per group: the same seq in another group is not a duplicate.", refs + ["M§6.5"], T, ctx, [
                         (items(it(1, "welcome"), it(2, "welcome", group=GROUP2), it(3, seq=1), it(4, seq=1, group=GROUP2)),
                          [{"process": c(1)}, {"process": c(2)}, {"process": c(3)}, {"process": c(4)}],
                          st(4, {GROUP: (1,), GROUP2: (1,)}, sorted([GROUP, GROUP2]))),
                         ({"cursor_invalid": {}}, sync(None), st(None, {GROUP: (1,), GROUP2: (1,)}, sorted([GROUP, GROUP2]))),
                         (items(it(5, seq=1), it(6, seq=2, group=GROUP2)), [{"duplicate": c(5)}, {"process": c(6)}],
                          st(6, {GROUP: (1,), GROUP2: (2,)}, sorted([GROUP, GROUP2]))),
                     ]))
    # --- spec-gap 83: where a device starts counting a group
    WS = {**it(1, "welcome"), "seq": 7}
    out.append(trace("resume-welcome-seq-is-the-starting-position",
                     "A welcome carries the seq of the commit that added the device (spec-gap 83): that is the device's position in "
                     "the group at once. Everything at or below it is pre-join history — a duplicate, never a gap — and what "
                     "follows is counted from there.", refs + ["M§6.5", "M§12.3"], T, ctx, [
                         (items(WS), [{"process": c(1)}], st(1, {GROUP: (7,)}, [GROUP])),
                         (items(it(2, seq=5), it(3, seq=8), it(4, seq=10)), [{"duplicate": c(2)}, {"process": c(3)}, {"process": c(4)}],
                          st(4, {GROUP: (8, [10])}, [GROUP])),
                         (items(it(5, seq=9)), [{"process": c(5)}], st(5, {GROUP: (10,)}, [GROUP])),
                     ]))
    out.append(trace("resume-late-item-after-the-join-is-processed",
                     "Why the position comes from the welcome and not from arrival order: after a hub handover wait (spec-gap 71) a "
                     "mailbox stores the old hub's late items behind newer ones. The first item a new member meets is then not its "
                     "first: the lower one that follows is real, and is processed.", refs + ["M§6.5", "M§7.4"], T, ctx, [
                         (items(WS, it(2, seq=9)), [{"process": c(1)}, {"process": c(2)}], st(2, {GROUP: (7, [9])}, [GROUP])),
                         (items(it(3, seq=8)), [{"process": c(3)}], st(3, {GROUP: (9,)}, [GROUP])),
                     ]))
    out.append(trace("resume-welcome-without-seq-starts-at-the-first-item",
                     "A welcome with no seq (a hub that does not send it yet; a group the device created) leaves the old rule: the "
                     "first sequenced item the device processes is its position (spec-gap 69), and a lower one later is history.",
                     refs + ["M§6.5"], T, ctx, [
                         (items(W, it(2, seq=4)), [{"process": c(1)}, {"process": c(2)}], st(2, {GROUP: (4,)}, [GROUP])),
                         (items(it(3, seq=2), it(4, seq=5)), [{"duplicate": c(3)}, {"process": c(4)}], st(4, {GROUP: (5,)}, [GROUP])),
                     ]))
    out.append(trace("resume-rejoin-is-a-join",
                     "Re-joining by external commit (M§6.8) is a join like any other: the group is joined, and a welcome for it "
                     "that turns up later is a duplicate (found by fuzz.py).", refs + ["M§6.8"], T, ctx, [
                         ({"rejoined": {"group": GROUP, "seq": 6}}, [], st(None, {GROUP: (6,)}, [GROUP])),
                         (items(W), [{"duplicate": c(1)}], st(1, {GROUP: (6,)}, [GROUP])),
                     ]))
    out.append(trace("resume-sibling-welcome-seq-sets-no-position",
                     "A sibling's welcome is not a join (M§12.3): its seq says nothing about this device.", refs + ["M§12.3"], T, ctx, [
                         (items({**WS, "sibling": True}), [{"sibling": c(1)}], st(1, {}, [])),
                     ]))
    out.append(trace("resume-seq-beyond-gap-remembered",
                     "An application item processed beyond a seq gap is remembered durably, so its redelivery is a duplicate "
                     "while the missing seq is still processed.", refs + ["M§6.5"], T, ctx, [
                         (items(W, it(2, seq=1), it(3, seq=3)), [{"process": c(1)}, {"process": c(2)}, {"process": c(3)}],
                          st(3, {GROUP: (1, [3])}, [GROUP])),
                         ({"restart": {}}, sync(3), st(3, {GROUP: (1, [3])}, [GROUP])),
                         ({"cursor_invalid": {}}, sync(None), st(None, {GROUP: (1, [3])}, [GROUP])),
                         (items(it(4, seq=1), it(5, seq=2), it(6, seq=3)), [{"duplicate": c(4)}, {"process": c(5)}, {"duplicate": c(6)}],
                          st(6, {GROUP: (3,)}, [GROUP])),
                     ]))
    out.append(trace("resume-own-item-by-accepted-seq",
                     "A device's own item comes back through its identity's mailbox (M§6.5 rule 5) and cannot be decrypted by it; "
                     "the seq from its accepted marks the copy as processed, including past a gap.", refs + ["M§6.5", "M§5.3"], T,
                     {"component": "resume", "cursor": c(1), "groups": {GROUP: {"contiguous": 1, "seen": []}}, "joined": [GROUP]}, [
                         ({"sent": {"group": GROUP, "seq": 3}}, [], st(1, {GROUP: (1, [3])}, [GROUP])),
                         ({"sent": {"group": GROUP, "seq": 2}}, [], st(1, {GROUP: (3,)}, [GROUP])),
                         (items(it(2, seq=2), it(3, seq=3), it(4, seq=4)), [{"duplicate": c(2)}, {"duplicate": c(3)}, {"process": c(4)}],
                          st(4, {GROUP: (4,)}, [GROUP])),
                     ]))
    sib = {**it(1, "welcome"), "sibling": True}
    out.append(trace("resume-sibling-welcome-is-not-a-join",
                     "A new device syncing from null meets its sibling's welcome for a group: acknowledged, not a join, so the "
                     "device's own welcome for that group is still processed.", refs + ["M§12.3", "M§6.7"], T, ctx, [
                         (items(sib), [{"sibling": c(1)}], st(1)),
                         (items(it(2, "welcome")), [{"process": c(2)}], st(2, joined=[GROUP])),
                         (items({**it(3, "welcome"), "sibling": True}), [{"duplicate": c(3)}], st(3, joined=[GROUP])),
                     ]))
    out.append(trace("resume-group-info-not-deduplicated",
                     "Unsequenced group-info is state, not conversation: a redelivered one is processed again (it replaces the "
                     "latest GroupInfo idempotently).", refs + ["M§5.2", "M§6.8"], T, ctx, [
                         (items(it(1, "group-info")), [{"process": c(1)}], st(1)),
                         ({"cursor_invalid": {}}, sync(None), st()),
                         (items(it(1, "group-info")), [{"process": c(1)}], st(1)),
                     ]))
    # spec-gap 127: a device whose identity a commit removed is no longer in the group; a later welcome re-adding it is a join
    out.append(trace("resume-removed-then-welcome-is-a-join",
                     "A commit removed this device's identity (M§7.3); when a member adds it back, the new welcome is a join "
                     "from its seq, not a duplicate of the first one (spec-gap 127).", refs + ["M§7.3", "M§6.6"], T, ctx, [
                         (items(W, it(2, seq=1)), [{"process": c(1)}, {"process": c(2)}], st(2, {GROUP: (1,)}, [GROUP])),
                         ({"removed": {"group": GROUP}}, [], st(2, {GROUP: (1,)}, [])),
                         (items(it(3, "welcome", seq=14)), [{"process": c(3)}], st(3, {GROUP: (14,)}, [GROUP])),
                         (items(it(4, seq=15)), [{"process": c(4)}], st(4, {GROUP: (15,)}, [GROUP])),
                     ]))
    out.append(trace("resume-removed-keeps-seq-positions",
                     "Removal ends the join, not the seq positions: items already processed stay duplicates when redelivered "
                     "(spec-gap 127).", refs + ["M§7.3"], T, ctx, [
                         (items(W, it(2, seq=1), it(3, seq=2)), [{"process": c(1)}, {"process": c(2)}, {"process": c(3)}],
                          st(3, {GROUP: (2,)}, [GROUP])),
                         ({"removed": {"group": GROUP}}, [], st(3, {GROUP: (2,)}, [])),
                         ({"cursor_invalid": {}}, sync(None), st(None, {GROUP: (2,)}, [])),
                         (items(it(5, seq=1), it(6, seq=2)), [{"duplicate": c(5)}, {"duplicate": c(6)}], st(6, {GROUP: (2,)}, [])),
                     ]))
    out.append(trace("resume-removed-survives-restart",
                     "The removal is durable state: after a restart a welcome for the group is still a join (spec-gap 127).",
                     refs + ["M§7.3"], T, ctx, [
                         (items(W), [{"process": c(1)}], st(1, joined=[GROUP])),
                         ({"removed": {"group": GROUP}}, [], st(1)),
                         ({"restart": {}}, sync(1), st(1)),
                         (items(it(2, "welcome", seq=9)), [{"process": c(2)}], st(2, {GROUP: (9,)}, [GROUP])),
                     ]))
    # --- spec-gap 180: an envelope over the cap from the device's own mailbox
    L = {**ctx, "limit": 200}

    def lsync(cursor, limit):
        s_ = {"since": None} if cursor is None else {"since": c(cursor), "ack_through": c(cursor)}
        return [{"sync": {**s_, "limit": limit}}]

    out.append(trace("resume-too-large-halves-the-limit",
                     "A mailbox answered the sync with an envelope over the cap (spec-gap 180). The same sync would get the "
                     "same envelope, so the device syncs from the same cursor with half the limit, again on each refusal; "
                     "the reduced limit stays for later syncs, and a restart returns to the device's own.",
                     refs + ["§13.2"], T, L, [
                         (items(W, it(2, seq=1)), [{"process": c(1)}, {"process": c(2)}], st(2, {GROUP: (1,)}, [GROUP])),
                         ({"too_large": {}}, lsync(2, 100), st(2, {GROUP: (1,)}, [GROUP])),
                         ({"too_large": {}}, lsync(2, 50), st(2, {GROUP: (1,)}, [GROUP])),
                         (items(it(3, seq=2)), [{"process": c(3)}], st(3, {GROUP: (2,)}, [GROUP])),
                         ({"sync": {}}, lsync(3, 50), st(3, {GROUP: (2,)}, [GROUP])),
                         ({"restart": {}}, lsync(3, 200), st(3, {GROUP: (2,)}, [GROUP])),
                     ]))
    out.append(trace("resume-too-large-from-null",
                     "Before anything is committed the retry is from null, with no acknowledgement, at half the limit (spec-gap 180).",
                     refs + ["§13.2"], T, {**ctx, "limit": 7}, [
                         ({"too_large": {}}, lsync(None, 3), st()),
                         ({"too_large": {}}, lsync(None, 1), st()),
                     ]))
    out.append(trace("resume-too-large-at-one-backs-off",
                     "At a limit of 1 the mailbox is at fault, since MAX_MLS_BYTES makes any one item fit: the device does not "
                     "go below 1, and sends the same sync again only after the §13.2 reconnection backoff (spec-gap 180).",
                     refs + ["§13.2", "M§5.1"], T, {**ctx, "cursor": c(4), "limit": 2}, [
                         ({"too_large": {}}, lsync(4, 1), st(4)),
                         ({"too_large": {}}, [{"backoff": {}}] + lsync(4, 1), st(4)),
                         ({"cursor_invalid": {}}, lsync(None, 1), st()),
                     ]))
    out.append(trace("resume-removed-other-group-unaffected",
                     "Removal from one group leaves every other group joined.", refs + ["M§7.3"], T, ctx, [
                         (items(W, it(2, "welcome", group=GROUP2)), [{"process": c(1)}, {"process": c(2)}],
                          st(2, {}, sorted([GROUP, GROUP2]))),
                         ({"removed": {"group": GROUP}}, [], st(2, {}, [GROUP2])),
                         (items(it(3, "welcome", group=GROUP2)), [{"duplicate": c(3)}], st(3, {}, [GROUP2])),
                     ]))
    return out


# ---------------------------------------------------------------- tranche 3: the MLS layer (M§6.2, M§6.3, M§8.4, M§11.1, M§12.2)

EXT_DELEG, EXT_CONV = 0xF0D1, 0xF0D2


def compact(env: dict) -> str:
    return f"{env['protected']}.{env['payload']}.{env['signature']}"



def items_pages_vectors():
    """M§5.4: every `items` envelope fits the `ws/1.0` cap as encoded and signed (§13.2, spec-gap 180). Each vector holds
    items whose `mls` is `mls_bytes` long; the mailbox pages them however it likes, and what is expected is what every
    conforming paging shares: all cursors in order, every page within the cap and the limit, `next` chained."""
    out = []
    ctx = {"component": "mailbox-pages", "mailbox_key": "relay", "device": F.did("bob-phone"), "now": NOW}
    refs = ["M§5.4", "§13.2"]

    def items(*sizes):
        return [{"cursor": c(i + 1), "stored_at": NOW, "class": "application", "source": HUB_A, "group": GROUP,
                 "seq": i + 1, "mls_bytes": n} for i, n in enumerate(sizes)]

    def ok(n):
        return {"cursors": [c(i + 1) for i in range(n)], "fit": True, "within_limit": True, "next_chain": True}

    M = 24576  # MAX_MLS_BYTES, M§5.1
    out.append(mv("items-pages-fit-the-cap",
                  "Five items at MAX_MLS_BYTES under a limit of 200: one envelope would be about 170 KB, so the mailbox sends "
                  "several, each within the cap, and the device reaches every item by following next (spec-gap 180). Paging "
                  "by count alone sends one envelope the device must refuse.",
                  refs + ["M§5.1"], {"check": "items-pages", "limit": 200, "items": items(*[M] * 5)}, ok(5), ctx=ctx))
    out.append(mv("items-pages-many-small-items",
                  "Fifty-four items of 600 bytes each, the store that looped a phone: under the count limit, over the cap as "
                  "one envelope (spec-gap 180).",
                  refs, {"check": "items-pages", "limit": 200, "items": items(*[600] * 54)}, ok(54), ctx=ctx))
    out.append(mv("items-pages-mixed-sizes",
                  "Small items between large ones: every page fits and none is empty, wherever the mailbox splits (spec-gap 180).",
                  refs, {"check": "items-pages", "limit": 200, "items": items(100, M, 100, M, M, 100, 100, M)}, ok(8), ctx=ctx))
    out.append(mv("items-pages-limit-still-bounds",
                  "Items that fit easily are still paged by the device's limit.",
                  refs, {"check": "items-pages", "limit": 2, "items": items(100, 100, 100, 100, 100)}, ok(5), ctx=ctx))
    out.append(mv("items-pages-one-item-at-max",
                  "A single item at MAX_MLS_BYTES fits one envelope: next is null at once.",
                  refs + ["M§5.1"], {"check": "items-pages", "limit": 200, "items": items(M)}, ok(1), ctx=ctx))
    return out


def mls_layer_vectors():
    import struct
    import hashlib
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from .common import default_context
    out = []

    # --- Extension wire encoding (RFC 9420 §2.1.2 lengths), expected bytes built with struct, not the reference encoder
    def enc(vid, desc, ext_type, data: bytes, header: bytes):
        out.append(mv(f"mls-extension-encode-{vid}", desc, ["M§6.2", "M§6.3", "M§17"],
                      {"check": "mls-extension-encode", "extension_type": ext_type, "data_hex": data.hex()},
                      {"hex": (struct.pack(">H", ext_type) + header + data).hex()}))

    enc("1-byte-length", "63 bytes of data take a one-byte length.", EXT_DELEG, b"d" * 63, bytes([63]))
    enc("2-byte-length", "64 bytes of data need the two-byte length form (0b01 prefix).", EXT_DELEG, b"d" * 64, struct.pack(">H", 0x4000 | 64))
    enc("4-byte-length", "16,384 bytes of data need the four-byte form (0b10 prefix).", EXT_CONV, b"c" * 16384,
        struct.pack(">I", 0x80000000 | 16384))
    deleg_msg = F.make_delegation(F.KEYS["alice"], F.did("alice"), APH,
                                  capabilities=("dsip.signaling", "dsip.messaging"))
    enc("dsip-delegation-compact", "A real dsip_delegation: the compact delegation envelope as ASCII bytes.", EXT_DELEG,
        compact(deleg_msg).encode(), struct.pack(">H", 0x4000 | len(compact(deleg_msg))))

    def dec(vid, desc, raw: bytes, expect):
        out.append(mv(f"mls-extension-decode-{vid}", desc, ["M§6.2", "M§17"], {"check": "mls-extension-decode", "hex": raw.hex()}, expect))

    dec("valid", "A well-formed extension decodes to its type and data.", struct.pack(">HB", EXT_DELEG, 3) + b"abc",
        accept(extension_type=EXT_DELEG, data_hex=b"abc".hex()))
    dec("non-minimal-length", "A length of 3 in the two-byte form is non-minimal and rejected.",
        struct.pack(">HH", EXT_DELEG, 0x4003) + b"abc", reject("mls-length-non-minimal"))
    dec("eight-byte-length", "The 0b11 (8-byte) length form exceeds MLS's 30-bit bound.",
        struct.pack(">HQ", EXT_DELEG, 0xC000000000000003) + b"abc", reject("mls-length-invalid"))
    dec("truncated-header", "Two bytes of a two-byte length form is truncated.", struct.pack(">HB", EXT_DELEG, 0x40), reject("mls-truncated"))
    dec("truncated-data", "Declared length longer than the data.", struct.pack(">HB", EXT_DELEG, 5) + b"abc", reject("mls-truncated"))
    dec("trailing-bytes", "Bytes after the declared data are rejected.", struct.pack(">HB", EXT_DELEG, 3) + b"abcd", reject("mls-trailing-bytes"))

    # --- the DSIP authentication service (M§6.2)
    msg_caps = ("dsip.signaling", "dsip.messaging")
    ctx = default_context()

    def cred(vid, desc, device_did, sig_pub_hex, delegation, expect, credential_type=1, identity_hex=None, extra_ext=None):
        exts = [] if delegation is None else [{"extension_type": EXT_DELEG, "data_hex": delegation}]
        exts += extra_ext or []
        inp = {"check": "mls-credential",
               "credential": {"credential_type": credential_type, "identity_hex": identity_hex or device_did.encode().hex()},
               "signature_key_hex": sig_pub_hex, "extensions": exts}
        out.append(mv(f"mls-credential-{vid}", desc, ["M§6.2", "§7.4"], inp, expect, ctx=ctx))

    pub = lambda n: F.KEYS[n].public.hex()
    hx = lambda env: compact(env).encode().hex()
    good = F.make_delegation(F.KEYS["alice"], F.did("alice"), APH, capabilities=msg_caps)
    cred("valid-did-key-subject", "Basic credential naming alice-phone, its Ed25519 key, and a dsip.messaging delegation from alice.",
         APH, pub("alice-phone"), hx(good), accept(identity=F.did("alice"), device=APH))
    web = F.make_delegation(F.KEYS["bob"], F.BOB_WEB, BPH, capabilities=msg_caps, signer_kid=F.web_kid(F.BOB_WEB))
    cred("valid-did-web-subject", "A did:web identity's delegation, verified through its DID document.", BPH, pub("bob-phone"), hx(web),
         accept(identity=F.BOB_WEB, device=BPH))
    sig_only = F.make_delegation(F.KEYS["alice"], F.did("alice"), APH)
    cred("signaling-only-delegation", "A delegation for calls only (no dsip.messaging) does not admit an MLS leaf.",
         APH, pub("alice-phone"), hx(sig_only), reject("delegation-capability"))
    expired = F.make_delegation(F.KEYS["alice"], F.did("alice"), APH, capabilities=msg_caps, issued_at=NOW - 86400 * 10, expires_at=NOW - 1)
    cred("expired-delegation", "An expired delegation makes the leaf unauthenticated.", APH, pub("alice-phone"), hx(expired),
         reject("delegation-expired"))
    other = F.make_delegation(F.KEYS["alice"], F.did("alice"), ALA, capabilities=msg_caps)
    cred("delegation-for-other-device", "The delegation names alice-laptop but the credential names alice-phone.",
         APH, pub("alice-phone"), hx(other), reject("delegation-invalid"))
    forged = F.make_delegation(F.KEYS["mallory"], F.did("alice"), APH, capabilities=msg_caps, signer_kid=F.KEYS["mallory"].kid)
    cred("delegation-not-signed-by-subject", "mallory signs a delegation claiming alice as subject.", APH, pub("alice-phone"), hx(forged),
         reject("delegation-invalid"))
    cred("signature-key-mismatch", "The leaf signature key is not the key alice-phone's DID names.", APH, pub("alice-laptop"), hx(good),
         reject("credential-key-mismatch"))
    cred("delegation-missing", "A leaf without dsip_delegation cannot be authenticated.", APH, pub("alice-phone"), None,
         reject("delegation-missing"))
    cred("delegation-not-compact", "dsip_delegation data must be the compact envelope, not JSON.", APH, pub("alice-phone"),
         json.dumps(good).encode().hex(), reject("delegation-invalid"))
    cred("x509-credential", "Only the basic credential type is used in 1.0.", APH, pub("alice-phone"), hx(good), reject("credential-type"),
         credential_type=2)
    cred("identity-not-utf8", "The credential identity must be UTF-8.", APH, pub("alice-phone"), hx(good), reject("credential-identity"),
         identity_hex="ff" + APH.encode().hex())
    cred("identity-not-a-did", "The credential identity must be a device DID.", APH, pub("alice-phone"), hx(good),
         reject("credential-identity"), identity_hex=b"Alice's phone".hex())
    cred("duplicate-delegation-extension", "Two dsip_delegation extensions on one leaf are refused.", APH, pub("alice-phone"), hx(good),
         reject("delegation-invalid"), extra_ext=[{"extension_type": EXT_DELEG, "data_hex": hx(good)}])

    # --- dsip_conversation bytes (M§6.3)
    def conv(vid, desc, data: bytes, expect):
        out.append(mv(f"mls-conversation-bytes-{vid}", desc, ["M§6.3", "§10.3"], {"check": "mls-conversation-bytes", "data_hex": data.hex()},
                      expect))

    ext = {"conversation": CONV, "kind": "direct", "hub": {"did": HUB_A, "uri": "wss://mbx.alice.example/dsip"}, "successor_of": None}
    conv("valid", "UTF-8 JSON extension data naming the conversation and hub.", json.dumps(ext, separators=(",", ":")).encode(),
         accept(effective={"kind": "direct"}))
    conv("not-utf8", "Extension data that is not UTF-8.", b"\xff\xfe{}", reject("payload-not-utf8"))
    conv("not-json", "Extension data that is not a JSON object.", b"[1,2]", reject("payload-not-json"))
    conv("float", "A float anywhere violates §10.3.", json.dumps({**ext, "version": 1.5}).encode(), reject("payload-float"))
    conv("missing-hub", "The hub is required.", json.dumps({"conversation": CONV, "kind": "group"}).encode(), reject("schema-invalid"))

    # --- AES-GCM formats: stored = nonce(12) ‖ ciphertext ‖ tag(16). Expected values come from pyca/cryptography;
    #     dsip-messaging computes them independently with RustCrypto aes-gcm.
    key = bytes(range(32))
    nonce = bytes(range(100, 112))
    group = uid("group-1").encode()

    def sealed_of(pt: bytes, aad: bytes) -> bytes:
        return nonce + AESGCM(key).encrypt(nonce, pt, aad or None)

    blob_pt = b"OggS" + bytes(60)
    blob_sealed = sealed_of(blob_pt, b"")
    act_pt = b"eyJ.activity.sig"
    act_aad = group + (7).to_bytes(8, "big")
    arch_pt = json.dumps({"object": "archive-record", "seq": 42}).encode()
    arch_aad = group + (42).to_bytes(8, "big")
    base = {"key_hex": key.hex(), "nonce_hex": nonce.hex()}

    def sv(vid, desc, refs, inp, expect):
        out.append(mv(vid, desc, refs, inp, expect))

    sv("seal-blob", "Blob sealing: AES-256-GCM, empty AAD, stored as nonce ‖ ciphertext ‖ tag.", ["M§8.4"],
       {"check": "seal", "use": "blob", **base, "plaintext_hex": blob_pt.hex()}, {"sealed_hex": blob_sealed.hex()})
    sv("seal-activity", "Activity sealing binds group_id ‖ epoch (u64 big-endian) as AAD.", ["M§11.1"],
       {"check": "seal", "use": "activity", **base, "group_hex": group.hex(), "epoch": 7, "plaintext_hex": act_pt.hex()},
       {"sealed_hex": sealed_of(act_pt, act_aad).hex()})
    sv("seal-archive", "Archive sealing binds group_id ‖ seq (u64 big-endian) as AAD.", ["M§12.2"],
       {"check": "seal", "use": "archive", **base, "group_hex": group.hex(), "seq": 42, "plaintext_hex": arch_pt.hex()},
       {"sealed_hex": sealed_of(arch_pt, arch_aad).hex()})
    blob_ref = {"sha256": hashlib.sha256(blob_sealed).hexdigest(), "size": len(blob_sealed)}
    sv("open-blob-valid", "A blob whose size and hash match opens.", ["M§8.4"],
       {"check": "open", "use": "blob", "key_hex": key.hex(), "sealed_hex": blob_sealed.hex(), **blob_ref}, accept(plaintext_hex=blob_pt.hex()))
    tampered = bytearray(blob_sealed)
    tampered[20] ^= 1
    sv("open-blob-hash-mismatch", "A blob whose bytes do not match the manifest hash is discarded before decryption.", ["M§8.4"],
       {"check": "open", "use": "blob", "key_hex": key.hex(), "sealed_hex": bytes(tampered).hex(), **blob_ref}, reject("blob-hash-mismatch"))
    sv("open-blob-size-mismatch", "A blob whose length does not match the manifest size is discarded.", ["M§8.4"],
       {"check": "open", "use": "blob", "key_hex": key.hex(), "sealed_hex": blob_sealed[:-1].hex(), **blob_ref}, reject("blob-size-mismatch"))
    sv("open-activity-wrong-epoch", "Activity sealed for epoch 7 does not open as epoch 8: the AAD binds the epoch.", ["M§11.1"],
       {"check": "open", "use": "activity", "key_hex": key.hex(), "group_hex": group.hex(), "epoch": 8,
        "sealed_hex": sealed_of(act_pt, act_aad).hex()}, reject("aead-open-failed"))
    sv("open-archive-valid", "An archive record opens under its group and seq.", ["M§12.2"],
       {"check": "open", "use": "archive", "key_hex": key.hex(), "group_hex": group.hex(), "seq": 42,
        "sealed_hex": sealed_of(arch_pt, arch_aad).hex()}, accept(plaintext_hex=arch_pt.hex()))
    sv("open-archive-moved-to-other-seq", "An archive record replayed under another seq does not open.", ["M§12.2"],
       {"check": "open", "use": "archive", "key_hex": key.hex(), "group_hex": group.hex(), "seq": 43,
        "sealed_hex": sealed_of(arch_pt, arch_aad).hex()}, reject("aead-open-failed"))
    sv("open-too-short", "Sealed data shorter than nonce plus tag.", ["M§8.4"],
       {"check": "open", "use": "archive", "key_hex": key.hex(), "group_hex": group.hex(), "seq": 1, "sealed_hex": bytes(27).hex()},
       reject("sealed-too-short"))
    return out


# ---------------------------------------------------------------- step 1: mailbox discovery (M§4.2, §8.1; spec-gap 37)

MBX_A2 = "did:web:mbx2.bob.example"


def entry(mailbox=MBX_B, uri=None, priority=None, profiles=("messaging/1.0",), **over):
    e = {"uri": uri or f"wss://{mailbox.split(':')[-1]}/dsip", "bindings": ["ws/1.0"], "mailbox": mailbox}
    if priority is not None:
        e["priority"] = priority
    if profiles is not None:
        e["profiles"] = list(profiles)
    e.update(over)
    return e


def discovery_vectors():
    out = []

    def sel(vid, desc, inp, expect):
        out.append(mv(f"mailbox-select-{vid}", desc, ["M§4.2", "§8.1"], {"check": "mailbox-select", **inp}, expect))

    primary, secondary = entry(MBX_B, priority=0), entry(MBX_A2, priority=1)
    sel("priority-order", "The lowest priority entry is the primary mailbox; devices sync both.",
        {"document_entries": [secondary, primary]},
        {"source": "did-document", "selected": MBX_B, "order": [MBX_B, MBX_A2], "sync_targets": [MBX_B, MBX_A2], "discarded": []})
    sel("skips-unreachable", "A sender deposits to the lowest priority entry that accepts the connection.",
        {"document_entries": [primary, secondary], "reachable": [MBX_A2]},
        {"source": "did-document", "selected": MBX_A2, "order": [MBX_B, MBX_A2], "sync_targets": [MBX_B, MBX_A2], "discarded": []})
    sel("absent-priority-is-zero", "An entry with no priority sorts as priority 0, before an explicit 1.",
        {"document_entries": [secondary, entry(MBX_B)]},
        {"source": "did-document", "selected": MBX_B, "order": [MBX_B, MBX_A2], "sync_targets": [MBX_B, MBX_A2], "discarded": []})
    tie_a, tie_b = entry(MBX_B, priority=0), entry(MBX_A2, priority=0)
    sel("equal-priority-keeps-document-order", "Entries of equal priority keep the order the document lists them in.",
        {"document_entries": [tie_b, tie_a]},
        {"source": "did-document", "selected": MBX_A2, "order": [MBX_A2, MBX_B], "sync_targets": [MBX_A2, MBX_B], "discarded": []})
    plain = entry(MBX_A2, uri="ws://mbx2.bob.example/dsip", priority=0)
    sel("plaintext-uri-discarded", "A ws:// mailbox is never used (§13.2: wss only).",
        {"document_entries": [plain, secondary]},
        {"source": "did-document", "selected": MBX_A2, "order": [MBX_A2], "sync_targets": [MBX_A2],
         "discarded": ["ws://mbx2.bob.example/dsip"]})
    no_did = {"uri": "wss://mbx3.bob.example/dsip", "bindings": ["ws/1.0"], "profiles": ["messaging/1.0"]}
    sel("entry-without-mailbox-did-discarded",
        "Without the mailbox DID a client cannot check whose hello it got, so the entry is unusable.",
        {"document_entries": [no_did, primary]},
        {"source": "did-document", "selected": MBX_B, "order": [MBX_B], "sync_targets": [MBX_B],
         "discarded": ["wss://mbx3.bob.example/dsip"]})
    other_profile = entry(MBX_A2, priority=0, profiles=("verified-broadcast/1.0",))
    sel("profile-mismatch-discarded", "A service that does not advertise messaging/1.0 cannot serve the profile.",
        {"document_entries": [other_profile, secondary]},
        {"source": "did-document", "selected": MBX_A2, "order": [MBX_A2], "sync_targets": [MBX_A2],
         "discarded": ["wss://mbx2.bob.example/dsip"]})
    hint = entry(MBX_B, priority=0, service="DSIPMailbox")
    sel("did-key-uses-hints", "An identity with no DID document may advertise its mailbox in a signed DHT hint.",
        {"document_entries": [], "hint_entries": [hint]},
        {"source": "hint", "selected": MBX_B, "order": [MBX_B], "sync_targets": [MBX_B], "discarded": []})
    sel("document-wins-over-hint", "With a document entry present, hints are not consulted at all (§8.1 authority order).",
        {"document_entries": [secondary], "hint_entries": [hint]},
        {"source": "did-document", "selected": MBX_A2, "order": [MBX_A2], "sync_targets": [MBX_A2], "discarded": []})
    sel("unusable-document-does-not-fall-back-to-hints",
        "A document whose only entry is unusable does not hand the choice to a hint: a device-signed hint must not "
        "override the authoritative source.",
        {"document_entries": [plain], "hint_entries": [hint]},
        {"source": "did-document", "selected": None, "order": [], "sync_targets": [],
         "discarded": ["ws://mbx2.bob.example/dsip"]})
    sel("no-mailbox-advertised", "An identity with no mailbox cannot receive asynchronous content.",
        {"document_entries": [], "hint_entries": []},
        {"source": None, "selected": None, "order": [], "sync_targets": [], "discarded": []})

    def sw(vid, desc, established, candidate, expect):
        out.append(mv(f"mailbox-switch-{vid}", desc, ["M§4.2", "M§15.4"],
                      {"check": "mailbox-switch", "established": established, "candidate": candidate}, expect))

    sw("hint-refused", "A hint never moves an established conversation's mailbox.",
       {"mailbox": MBX_B, "source": "did-document"}, {"mailbox": MBX_A2, "source": "hint"},
       {"switch": False, "reason": "hint-sourced"})
    sw("document-allowed", "A changed DID document entry does move it.",
       {"mailbox": MBX_B, "source": "did-document"}, {"mailbox": MBX_A2, "source": "did-document"},
       {"switch": True, "reason": "did-document"})
    sw("unchanged", "The same mailbox is not a switch.",
       {"mailbox": MBX_B, "source": "did-document"}, {"mailbox": MBX_B, "source": "hint"},
       {"switch": False, "reason": "unchanged"})

    for vid, desc, e, ok in [
        ("valid", "A full DSIPMailbox serviceEndpoint.", entry(MBX_B, priority=0, accepts=["text", "audio"],
                                                              voicemail={"max_duration_s": 180}), True),
        ("plaintext-uri", "ws:// is refused by shape.", entry(MBX_B, uri="ws://mbx.bob.example/dsip"), False),
        ("unknown-field", "Unknown fields are refused by the closed schema.", entry(MBX_B, surprise=1), False),
    ]:
        out.append(mv(f"mailbox-service-{vid}", desc, ["M§4.2"], {"check": "payload", "schema": "mailbox-service", "payload": e},
                      accept() if ok else reject("schema-invalid")))
    return out


# ---------------------------------------------------------------- blob endpoint (M§5.6, M§8.4, spec-gap 48)

def blob_vectors():
    out = []
    sha = SHA
    other = "0" * 64
    MBX = {"did": HUB_A, "serves": [ALICE], "max_blob_bytes": 1048576}

    def put(label, desc, refs, expect, auth="ok", to=HUB_A, identity=ALICE, size=482220, path=sha, body_size=None,
            body_sha=None, stored=(), mbx=MBX):
        a = None
        if auth == "ok":
            a = {"identity": identity, "payload": {"type": "blob-put", "id": uid("bp"), "from": APH, "to": to,
                                                   "sha256": sha, "size": size}}
        inp = {"check": "blob-put", "mailbox": mbx, "authorization": a,
               "request": {"path_sha256": path, "body_size": size if body_size is None else body_size,
                           "body_sha256": sha if body_sha is None else body_sha},
               "stored": list(stored)}
        return mv(f"blob-put-{label}", desc, refs, inp, expect)

    acc = lambda dup=False: {"in_reply_to": uid("bp"), **({"duplicate": True} if dup else {})}
    R = ["M§5.6", "M§8.4"]
    out.append(put("stored-201", "An authorized upload whose body matches is stored: 201 with a signed accepted.", R,
                   {"status": 201, "accepted": acc()}))
    out.append(put("same-hash-again-200", "Re-uploading a stored hash is an idempotent success: 200, accepted with duplicate.",
                   R + ["M§9.3"], {"status": 200, "accepted": acc(True)}, stored=[sha]))
    out.append(put("unauthorized-401", "No verifiable Authorization: DSIP envelope: 401 policy.blocked.", R,
                   {"status": 401, "reason": "policy.blocked"}, auth=None))
    out.append(put("other-mailbox-403", "An authorization minted for another mailbox cannot be replayed here: 403 policy.blocked.",
                   R, {"status": 403, "reason": "policy.blocked"}, to=MBX_B))
    out.append(put("unserved-identity-403", "A device of an identity this mailbox does not serve: 403 transport.unknown-recipient.",
                   R + ["M§15.5"], {"status": 403, "reason": "transport.unknown-recipient"}, identity=BOB))
    out.append(put("path-mismatch-400", "The URL must name the hash the envelope authorizes: 400 policy.blocked.", R,
                   {"status": 400, "reason": "policy.blocked"}, path=other))
    out.append(put("over-max-413", "A declared size over max_blob_bytes is refused before the body is read: 413 mailbox.object-too-large.",
                   R + ["M§16"], {"status": 413, "reason": "mailbox.object-too-large"}, size=1048577))
    out.append(put("at-max-201", "A blob of exactly max_blob_bytes is accepted.", R, {"status": 201, "accepted": acc()}, size=1048576))
    out.append(put("body-size-mismatch-400", "A body whose length differs from the authorized size: 400 mailbox.blob-mismatch.",
                   R, {"status": 400, "reason": "mailbox.blob-mismatch"}, body_size=482219))
    out.append(put("body-hash-mismatch-400", "A body whose SHA-256 differs from the authorized hash: 400 mailbox.blob-mismatch.",
                   R, {"status": 400, "reason": "mailbox.blob-mismatch"}, body_sha=other))
    # owner quota (M§4.3 quota_bytes, M§14.3; spec-gap 99): checked from the authorized size, before the body is read
    QM = lambda used: {**MBX, "quota_bytes": 1000000, "used_bytes": used}
    R99 = R + ["M§4.3", "M§14.3"]
    out.append(put("over-quota-507", "600,000 of 1,000,000 quota bytes used and 482,220 more authorized: 507 mailbox.quota-exceeded, "
                   "refused before the body is read.", R99, {"status": 507, "reason": "mailbox.quota-exceeded"}, mbx=QM(600000)))
    out.append(put("fills-quota-201", "An upload that fills the quota exactly is stored.", R99,
                   {"status": 201, "accepted": acc()}, mbx=QM(517780)))
    out.append(put("over-quota-before-body-check-507", "Quota is decided from the authorization, so it is reported before a body "
                   "mismatch the server never reads.", R99, {"status": 507, "reason": "mailbox.quota-exceeded"},
                   mbx=QM(600000), body_sha=other))
    out.append(put("over-max-and-quota-413", "Over max_blob_bytes and over quota: the size bound comes first, 413.", R99,
                   {"status": 413, "reason": "mailbox.object-too-large"}, mbx=QM(600000), size=1048577))
    out.append(put("stored-hash-at-full-quota-200", "Re-uploading a stored hash stores nothing, so a full quota does not refuse it.",
                   R99 + ["M§9.3"], {"status": 200, "accepted": acc(True)}, mbx=QM(1000000), stored=[sha]))
    out.append(mv("blob-get-stored-200", "GET of a stored hash returns its ciphertext; the hash is the capability.", ["M§8.4"],
                  {"check": "blob-get", "path_sha256": sha, "stored": [sha]}, {"status": 200}))
    out.append(mv("blob-get-unknown-404", "GET of a hash the mailbox does not hold: 404.", ["M§8.4"],
                  {"check": "blob-get", "path_sha256": other, "stored": [sha]}, {"status": 404}))
    return out


# ---------------------------------------------------------------- history across devices (M§12, spec-gap 51)

def history_vectors():
    out = []
    T = "history-trace"
    refs = ["M§12.2", "M§12.3", "M§8.5"]
    K1, K2 = uid("akid-1"), uid("akid-2")
    ctx = {"component": "history", "keys": [], "joined": {}}

    def arch(n, seq, akid=K1, group=GROUP, label=None):
        return {"archive": {"cursor": c(n), "akid": akid, "group": group, "seq": seq, "id": label or f"m{seq}"}}

    def mls(seq, epoch=1, group=GROUP, label=None):
        return {"mls": {"group": group, "seq": seq, "epoch": epoch, "id": label or f"m{seq}"}}

    def key(akid=K1, at=NOW):
        return {"archive_key": {"akid": akid, "created_at": at}}

    def hst(timeline=(), held=(), current=None):
        return {"timeline": list(timeline), "held": [c(n) for n in held], "current_akid": current}

    ar = lambda seq, akid=K1, group=GROUP: {"archive": {"group": group, "seq": seq, "akid": akid}}
    out.append(trace("history-archive-before-key-held",
                     "A new device meets archive records before the personal-group welcome that brings their key: they are held, "
                     "then shown in seq order when the key arrives.", refs + ["M§12.1"], T, ctx, [
                         (arch(1, 2), [{"hold": c(1)}], hst(held=[1])),
                         (arch(2, 1), [{"hold": c(2)}], hst(held=[1, 2])),
                         (key(), [{"show": "m2"}, {"show": "m1"}], hst(["m1", "m2"], current=K1)),
                     ]))
    out.append(trace("history-held-released-per-key",
                     "Only records under the arriving key are released.", refs + ["M§12.4"], T, ctx, [
                         (arch(1, 1, K1), [{"hold": c(1)}], hst(held=[1])),
                         (arch(2, 2, K2), [{"hold": c(2)}], hst(held=[1, 2])),
                         (key(K2, NOW + 60), [{"show": "m2"}], hst(["m2"], held=[1], current=K2)),
                         (key(K1, NOW), [{"show": "m1"}], hst(["m1", "m2"], current=K2)),
                     ]))
    out.append(trace("history-archive-and-mls-copies-collapse",
                     "The archive record of an object the device already has from MLS is a duplicate, and so is the reverse.",
                     refs, T, {**ctx, "keys": [{"akid": K1, "created_at": NOW}]}, [
                         (mls(1), [{"show": "m1"}, {"archive": ar(1)["archive"]}], hst(["m1"], current=K1)),
                         (arch(5, 1), [{"duplicate": "m1"}], hst(["m1"], current=K1)),
                         (arch(6, 2), [{"show": "m2"}], hst(["m1", "m2"], current=K1)),
                         (mls(2), [{"duplicate": "m2"}], hst(["m1", "m2"], current=K1)),
                     ]))
    out.append(trace("history-timeline-in-seq-order",
                     "Display order is hub seq order, whatever order MLS items and archive records arrive in.",
                     refs, T, {**ctx, "keys": [{"akid": K1, "created_at": NOW}]}, [
                         (mls(3), [{"show": "m3"}, {"archive": ar(3)["archive"]}], hst(["m3"], current=K1)),
                         (arch(4, 1), [{"show": "m1"}], hst(["m1", "m3"], current=K1)),
                         (arch(5, 2), [{"show": "m2"}], hst(["m1", "m2", "m3"], current=K1)),
                     ]))
    out.append(trace("history-prejoin-mls-skipped",
                     "MLS items from epochs before the device joined cannot be decrypted by it and are skipped; its join epoch onward is shown.",
                     refs, T, ctx, [
                         ({"joined": {"group": GROUP, "epoch": 3}}, [], hst()),
                         (mls(4, epoch=2), [{"prejoin": 4}], hst()),
                         (mls(5, epoch=3), [{"show": "m5"}], hst(["m5"])),
                     ]))
    out.append(trace("history-no-key-no-archive",
                     "A device without an archive key shows MLS content but cannot archive it.", refs, T, ctx, [
                         (mls(1), [{"show": "m1"}], hst(["m1"])),
                     ]))
    out.append(trace("history-archives-under-newest-key",
                     "After a rotation the current key is the one created last, and new archive records use it.",
                     refs + ["M§12.4", "M§12.1"], T, ctx, [
                         (key(K2, NOW), [], hst(current=K2)),
                         (key(K1, NOW + 60), [], hst(current=K1)),
                         (mls(1), [{"show": "m1"}, {"archive": ar(1, K1)["archive"]}], hst(["m1"], current=K1)),
                     ]))
    out.append(trace("history-own-sent-content-archived",
                     "A device archives its own sent content too (with the seq of its accepted), so a later device sees both sides.",
                     refs + ["M§5.3"], T, {**ctx, "keys": [{"akid": K1, "created_at": NOW}]}, [
                         ({"sent": {"group": GROUP, "seq": 7, "id": "mine"}}, [{"show": "mine"}, {"archive": ar(7)["archive"]}],
                          hst(["mine"], current=K1)),
                     ]))
    return out


def removal_registration_vectors():
    refs = ["M§5.7", "M§6.6", "M§12.4"]
    return [
        mv("registration-on-removal-sibling-remains",
           "A device removed while another device of its identity stays in the group must not end the identity's registration.",
           refs, {"check": "registration-on-removal", "me": BOB, "remaining_identities": [ALICE, BOB]}, {"left": False}),
        mv("registration-on-removal-last-leaf",
           "When the removed device was its identity's last leaf, the registration ends with left.",
           refs + ["M§7.3"], {"check": "registration-on-removal", "me": BOB, "remaining_identities": [ALICE]}, {"left": True}),
    ]


# ---------------------------------------------------------------- first contact (M§6.9, M§14.1; spec-gaps 36, 54, 55)

# RFC 9180 Appendix A.1.1 — DHKEM(X25519, HKDF-SHA256), HKDF-SHA256, AES-128-GCM, base mode, sequence 0.
RFC9180_A1 = {
    "info": "4f6465206f6e2061204772656369616e2055726e",
    "ikmE": "7268600d403fce431561aef583ee1613527cff655c1343f29812e66706df3234",
    "skEm": "52c4a758a802cd8b936eceea314432798d5baf2d7e9235dc084ab1b9cfa2f736",
    "pkEm": "37fda3567bdbd628e88668c3c8d7e97d1d1253b6d4ea6d44c150f741f1bf4431",
    "skRm": "4612c550263fc8ad58375df3f557aac531d26850903e55a9f23f21d8534e8ac8",
    "pkRm": "3948cfe0ad1ddb695d780e59077195da6c56506b027329794ab02bca80815c4d",
    "enc": "37fda3567bdbd628e88668c3c8d7e97d1d1253b6d4ea6d44c150f741f1bf4431",
    "pt": "4265617574792069732074727574682c20747275746820626561757479",
    "aad": "436f756e742d30",
    "ct": "f938558b5d72f1a23810b4be2ab4f84331acc02fc97babc53a52ae82" "18a355a96d8770ac83d07bea87e13c512a",
}


def _hpke_self_test():
    """The reference is checked against the RFC and against an independent HPKE before any vector is written."""
    from .. import messaging as M
    from cryptography.hazmat.primitives import hpke
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    r = {k: bytes.fromhex(v) for k, v in RFC9180_A1.items()}
    assert M.hpke_derive_sk(r["ikmE"]) == r["skEm"] and M.x25519_public(r["skEm"]) == r["pkEm"], "RFC 9180 DeriveKeyPair"
    enc, ct = M.hpke_seal(r["pkRm"], r["info"], r["aad"], r["pt"], r["skEm"])
    assert (enc, ct) == (r["enc"], r["ct"]), "RFC 9180 A.1.1 seal"
    assert M.hpke_open(r["enc"], r["skRm"], r["info"], r["aad"], r["ct"]) == r["pt"], "RFC 9180 A.1.1 open"
    suite = hpke.Suite(hpke.KEM.X25519, hpke.KDF.HKDF_SHA256, hpke.AEAD.AES_128_GCM)
    sk = X25519PrivateKey.from_private_bytes(r["skRm"])
    blob = suite.encrypt(b"interop", sk.public_key(), b"dsip")
    assert M.hpke_open(blob[:32], r["skRm"], b"dsip", b"", blob[32:]) == b"interop", "cryptography interop (empty aad)"


def first_contact_vectors():
    from .. import messaging as M
    _hpke_self_test()
    out = []
    A = RFC9180_A1
    open_inp = lambda **o: {"check": "hpke-open", "enc_hex": A["enc"], "sk_r_hex": A["skRm"], "info_hex": A["info"],
                            "aad_hex": A["aad"], "ct_hex": A["ct"], **o}
    out.append(mv("hpke-open-rfc9180-a1", "RFC 9180 A.1.1 (base mode, sequence 0) opens to its plaintext: the HPKE suite of M§6.9.",
                  ["M§6.9"], open_inp(), accept(plaintext_hex=A["pt"])))
    out.append(mv("hpke-open-rfc9180-a1-wrong-aad", "The same ciphertext under another AAD does not open.", ["M§6.9"],
                  open_inp(aad_hex="436f756e742d31"), reject("hpke-open-failed")))
    out.append(mv("hpke-open-rfc9180-a1-wrong-info", "Nor under another info.", ["M§6.9"],
                  open_inp(info_hex="00" + A["info"]), reject("hpke-open-failed")))
    out.append(mv("hpke-derive-key-pair-rfc9180-a1", "DeriveKeyPair from RFC 9180 A.1.1 ikmE.", ["M§6.9"],
                  {"check": "hpke-derive-key-pair", "ikm_hex": A["ikmE"]}, {"sk_hex": A["skEm"], "pk_hex": A["pkEm"]}))

    bob_seed = hashlib.sha256(b"dsip-vector:bob").digest()
    mallory_seed = hashlib.sha256(b"dsip-vector:mallory").digest()
    bob_x = M.x25519_public(M.x25519_from_ed25519_seed(bob_seed))
    out.append(mv("x25519-key-agreement-from-ed25519",
                  "The X25519 key agreement key of an Ed25519 identity key, as did:key derives it (M§6.9; spec-gap 55 for did:web).",
                  ["M§6.9"], {"check": "x25519-key-agreement", "ed25519_seed_hex": bob_seed.hex()}, {"x25519_pk_hex": bob_x.hex()}))

    def intro(label="intro", purpose=None, frm=ALICE, to=BOB):
        p = {"dsip": {**VERSION, "profiles": ["messaging/1.0"]}, "type": "introduction", "id": uid(label), "from": frm, "to": to,
             "identity": {"display_name": "Alice"}, "issued_at": NOW, "expires_at": NOW + 604800}
        if purpose is not None:
            p["purpose"] = purpose
        return p

    def sealed(p, body: bytes, pk=bob_x, eph=b"eph"):
        sk_e = M.hpke_derive_sk(hashlib.sha256(b"dsip-vector:ephemeral:" + eph).digest())
        enc, ct = M.hpke_seal(pk, M.SEALED_INFO, M.sealed_aad(p), body, sk_e)
        return {**p, "sealed": {"alg": M.SEALED_ALG, "enc": b64url_encode(enc), "ct": b64url_encode(ct)}}

    purpose = "We met at the Syracuse mesh meetup; following up about the antenna group buy."
    good = sealed(intro(), json.dumps({"purpose": purpose}).encode())
    R = ["M§14.1", "M§6.9"]
    so = lambda vid, desc, p, expect, seed=bob_seed, refs=R: out.append(mv(vid, desc, refs,
        {"check": "sealed-introduction-open", "payload": p, "recipient_ed25519_seed_hex": seed.hex()}, expect))
    so("sealed-introduction-opens", "A sealed introduction opens under the recipient's key agreement key to its purpose.", good,
       accept(purpose=purpose))
    so("sealed-introduction-wrong-recipient", "Only the recipient's key opens it.", good, reject("sealed-open-failed"), seed=mallory_seed)
    so("sealed-introduction-spliced-to-other-recipient",
       "The AAD binds id, from and to: the same sealed body under another `to` does not open.", {**good, "to": CAROL},
       reject("sealed-open-failed"))
    so("sealed-introduction-spliced-to-other-sender", "Nor under another `from`.", {**good, "from": MALLORY}, reject("sealed-open-failed"))
    so("sealed-introduction-spliced-to-other-id", "Nor under another `id`.", {**good, "id": uid("other-intro")}, reject("sealed-open-failed"))
    so("sealed-introduction-unsupported-alg", "An unknown sealing algorithm is refused before any attempt to open.",
       {**good, "sealed": {**good["sealed"], "alg": "hpke-base-p256-sha256-aes128gcm"}}, reject("sealed-alg-unsupported"))
    so("sealed-introduction-purpose-too-long", "A sealed purpose is still at most 280 characters.",
       sealed(intro("long"), json.dumps({"purpose": "x" * 281}).encode()), reject("purpose-too-long"))
    so("sealed-introduction-plaintext-not-purpose", "The plaintext is exactly {\"purpose\": …}.",
       sealed(intro("extra"), json.dumps({"purpose": "hi", "phone": "+1"}).encode()), reject("sealed-plaintext-invalid"))
    so("sealed-introduction-plaintext-not-json", "A plaintext that is not JSON is refused.", sealed(intro("raw"), b"hello"),
       reject("sealed-plaintext-invalid"))
    so("sealed-introduction-plain-purpose-passes-through", "An unsealed introduction yields its purpose unchanged.",
       intro("plain", purpose="Hello"), accept(purpose="Hello"))
    ic = lambda vid, desc, p, expect: out.append(mv(vid, desc, ["M§14.1", "§19.4"], {"check": "introduction", "payload": p}, expect))
    ic("introduction-sealed-valid", "The profile's introduction may carry sealed instead of purpose.", good, accept(effective={"sealed": True}))
    ic("introduction-purpose-and-sealed-refused", "purpose and sealed MUST NOT both be present.", {**good, "purpose": "Hi"},
       reject("introduction-purpose-and-sealed"))
    ic("introduction-sealed-missing-ct-refused", "A sealed body names alg, enc and ct.",
       {**good, "sealed": {k: v for k, v in good["sealed"].items() if k != "ct"}}, reject("schema-invalid"))
    ic("introduction-neither-purpose-nor-sealed", "As in core §19.4, purpose is optional.", intro("bare"), accept(effective={"sealed": False}))

    # deposits carrying first contact (spec-gap 54)
    env = "eyJ.introduction.sig"
    m = lambda vid, desc, payload, expect: out.append(mv(vid, desc, ["M§14.1", "M§5.2"], {"check": "message", "payload": payload}, expect))
    fc = lambda cls, label, **f: msg("deposit", label, APH, MBX_B, **{"class": cls, **f})
    m("deposit-introduction-valid", "An introduction travels to the recipient's mailbox as a deposit: the signed envelope, a recipient, no group.",
      fc("introduction", "di", recipient=BOB, envelope=env), accept())
    m("deposit-grant-valid", "The grant answering it travels back the same way.", fc("grant", "dg", recipient=ALICE, envelope=env), accept())
    m("deposit-introduction-with-group-refused", "A first-contact deposit names no group.",
      fc("introduction", "dig", recipient=BOB, envelope=env, group=GROUP), reject("schema-invalid"))
    m("deposit-introduction-without-recipient-refused", "A first-contact deposit names its recipient.",
      fc("introduction", "dir", envelope=env), reject("schema-invalid"))
    m("deposit-introduction-over-cap-refused", "The carried introduction is still capped at 4,096 bytes (§19.4).",
      fc("introduction", "dic", recipient=BOB, envelope="e" * 4097), reject("introduction-too-large", "transport.envelope-too-large"))
    m("deposit-introduction-at-cap-accepted", "Exactly 4,096 bytes is allowed.",
      fc("introduction", "dia", recipient=BOB, envelope="e" * 4096), accept())

    # mailbox rules (spec-gap 54, §19.4 carried to mailboxes)
    T = "mailbox-trace"
    ctx = mbx_ctx(intro_limit=2, intro_window=3600, inbox_cap=3)
    def intro_ev(label, sender=ALICE, device=APH, recipient=BOB, kind="introduction", exp=NOW + 604800):
        return {"first_contact": {"id": uid(label), "from": device, "sender_identity": sender, "recipient": recipient,
                                  "kind": kind, "expires_at": exp}}
    acc_c = lambda to, label, n: macc(to, label, c(n))
    out.append(trace("mailbox-introduction-stored-for-owner",
                     "An introduction for the owner is stored as a request item and pushed to bound devices; it is never a message.",
                     ["M§14.1", "§19.4"], T, ctx, [
                         ({"sync": {"id": uid("s1"), "device": BPH, "since": None, "live": True}},
                          [{"items": {"to": BPH, "in_reply_to": uid("s1"), "cursors": [], "next": None}}], ms()),
                         (intro_ev("i1"), [acc_c(APH, "i1", 1), {"push": {"to": BPH, "cursor": c(1)}}], ms([c(1)])),
                     ]))
    out.append(trace("mailbox-introduction-unknown-recipient-indistinguishable",
                     "An introduction for an identity the mailbox does not serve is accepted and dropped: a sender cannot tell it from delivery.",
                     ["§19.4", "M§15.5"], T, ctx, [
                         (intro_ev("i1", recipient="did:web:nobody.example"), [macc(APH, "i1")], ms()),
                     ]))
    out.append(trace("mailbox-introduction-rate-limited-per-sender",
                     "Introductions are rate-limited per sender identity: over the limit is policy.rate-limited with retry_after.",
                     ["§19.4", "M§14.3"], T, ctx, [
                         (intro_ev("i1"), [acc_c(APH, "i1", 1)], ms([c(1)])),
                         ({"advance": 100}, [], ms([c(1)])),
                         (intro_ev("i2", recipient="did:web:nobody.example"), [macc(APH, "i2")], ms([c(1)])),
                         (intro_ev("i3"), [{"error": {"to": APH, "in_reply_to": uid("i3"), "reason": "policy.rate-limited", "retry_after": 3500}}],
                          ms([c(1)])),
                         ({"advance": 3500}, [], ms([c(1)])),
                         (intro_ev("i4"), [acc_c(APH, "i4", 2)], ms([c(1), c(2)])),
                     ]))
    out.append(trace("mailbox-introduction-rate-limited-per-inbox",
                     "And per recipient inbox, whoever sends them.", ["§19.4", "M§14.3"], T, ctx, [
                         (intro_ev("i1", sender=CAROL, device=CPH), [acc_c(CPH, "i1", 1)], ms([c(1)])),
                         (intro_ev("i2", sender=MALLORY, device=MPH), [acc_c(MPH, "i2", 2)], ms([c(1), c(2)])),
                         (intro_ev("i3"), [{"error": {"to": APH, "in_reply_to": uid("i3"), "reason": "policy.rate-limited", "retry_after": 3600}}],
                          ms([c(1), c(2)])),
                     ]))
    # --- grants: solicited ones are not metered (spec-gap 81)
    SENT = uid("intro-out")

    def grant_ev(label, session=None, exp=NOW + 30):
        e = intro_ev(label, kind="grant", exp=exp)
        if session is not None:
            e["first_contact"]["session"] = session
        return e

    def sent_cfg(label="cfg-is", ids=(SENT,)):
        return {"config": {"id": uid(label), "device": BPH, "introductions_sent": list(ids)}}

    limited = lambda label: [{"error": {"to": APH, "in_reply_to": uid(label), "reason": "policy.rate-limited", "retry_after": 3600}}]
    grefs = ["§19.4", "M§14.1", "M§14.3"]
    out.append(trace("mailbox-unsolicited-grant-takes-the-introduction-budget",
                     "A grant that answers nothing the owner sent is an unsolicited write into the mailbox: it counts, and is limited, "
                     "like an introduction — naming a session the owner never sent changes nothing.", grefs, T, ctx, [
                         (intro_ev("i1"), [acc_c(APH, "i1", 1)], ms([c(1)])),
                         (grant_ev("g1"), [acc_c(APH, "g1", 2)], ms([c(1), c(2)])),
                         (grant_ev("g2", session=SENT), limited("g2"), ms([c(1), c(2)])),
                     ]))
    out.append(trace("mailbox-solicited-grant-bypasses-the-rate-limit",
                     "The owner's device tells its mailbox which introductions it sent (mailbox-config introductions_sent). A grant "
                     "answering one is the reply the owner asked for: stored though the sender is over its budget, and not counted.",
                     grefs + ["M§5.7"], T, ctx, [
                         (sent_cfg(), [macc(BPH, "cfg-is")], ms()),
                         (intro_ev("i1"), [acc_c(APH, "i1", 1)], ms([c(1)])),
                         (intro_ev("i2"), [acc_c(APH, "i2", 2)], ms([c(1), c(2)])),
                         (intro_ev("i3"), limited("i3"), ms([c(1), c(2)])),
                         (grant_ev("g1", session=SENT), [acc_c(APH, "g1", 3)], ms([c(1), c(2), c(3)])),
                     ]))
    out.append(trace("mailbox-solicited-grant-bypass-is-single-use",
                     "One introduction, one answer: the entry is consumed, so a second grant naming it is unsolicited again.",
                     grefs + ["M§5.7"], T, ctx, [
                         (sent_cfg(), [macc(BPH, "cfg-is")], ms()),
                         (grant_ev("g1", session=SENT), [acc_c(APH, "g1", 1)], ms([c(1)])),
                         (grant_ev("g2", session=SENT), [acc_c(APH, "g2", 2)], ms([c(1), c(2)])),
                         (grant_ev("g3", session=SENT), [acc_c(APH, "g3", 3)], ms([c(1), c(2), c(3)])),
                         (grant_ev("g4", session=SENT), limited("g4"), ms([c(1), c(2), c(3)])),
                     ]))
    out.append(trace("mailbox-introductions-sent-survives-restart",
                     "What a mailbox answers from is durable (spec-gap 59): the introductions its owner sent are, too.",
                     grefs + ["M§6.6"], T, ctx, [
                         (sent_cfg(), [macc(BPH, "cfg-is")], ms()),
                         (intro_ev("i1"), [acc_c(APH, "i1", 1)], ms([c(1)])),
                         (intro_ev("i2"), [acc_c(APH, "i2", 2)], ms([c(1), c(2)])),
                         ({"restart": {}}, [], ms([c(1), c(2)])),
                         (grant_ev("g1", session=SENT), [acc_c(APH, "g1", 3)], ms([c(1), c(2), c(3)])),
                     ]))
    out.append(trace("mailbox-introduction-inbox-bound-silent",
                     "Past the bounded inbox an introduction is accepted and not held, silently (§19.4 RECOMMENDED 16).",
                     ["§19.4"], T, mbx_ctx(intro_limit=10, inbox_cap=2), [
                         (intro_ev("i1", sender=CAROL, device=CPH), [acc_c(CPH, "i1", 1)], ms([c(1)])),
                         (intro_ev("i2", sender=MALLORY, device=MPH), [acc_c(MPH, "i2", 2)], ms([c(1), c(2)])),
                         (intro_ev("i3"), [macc(APH, "i3")], ms([c(1), c(2)])),
                     ]))
    out.append(trace("mailbox-introduction-dropped-at-expiry",
                     "A held introduction is kept only until its envelope expires: kept a second before its expires_at, "
                     "dropped at it (§12.9, spec-gap 141).", ["§19.4", "§12.9"], T, ctx, [
                         (intro_ev("i1", exp=NOW + 600), [acc_c(APH, "i1", 1)], ms([c(1)])),
                         ({"advance": 599}, [], ms([c(1)])),
                         ({"advance": 1}, [], ms()),
                     ]))
    out.append(trace("mailbox-grant-stored-for-owner",
                     "A grant answering the owner's introduction is stored for the owner the same way.", ["M§14.1", "§19.4"], T,
                     mbx_ctx(owner=ALICE, serves=[ALICE], devices=[APH], intro_limit=2, intro_window=3600, inbox_cap=3), [
                         (intro_ev("g1", sender=BOB, device=BPH, recipient=ALICE, kind="grant", exp=NOW + 30), [acc_c(BPH, "g1", 1)], ms([c(1)])),
                     ]))
    return out


# ---------------------------------------------------------------- revoking a device delegation (M§12.4, §7.4; spec-gap 57)

def revocation_vectors():
    from .. import envelope as E
    from .common import default_context
    out = []
    bob_key = F.KEYS["bob"]
    msg_caps = ("dsip.signaling", "dsip.messaging")
    deleg = lambda device, ia=NOW - 86400: F.make_delegation(bob_key, F.BOB_WEB, device, capabilities=msg_caps, issued_at=ia,
                                                              signer_kid=F.web_kid(F.BOB_WEB))

    def revocation(device=BLA, revoked_at=NOW - 60, signer=None, kid=None, subject=F.BOB_WEB, frm=None, label="rev"):
        p = {"dsip": {**VERSION, "profiles": ["messaging/1.0"]}, "type": "delegation-revocation", "id": uid(label, revoked_at),
             "from": frm or subject, "subject": subject, "device": device, "revoked_at": revoked_at, "reason": "lost",
             "issued_at": revoked_at, "expires_at": revoked_at + 300}
        return E.sign(p, signer or bob_key, kid or F.web_kid(F.BOB_WEB))

    # The record, its verification stage and the binding it affects are core v0.8 (§7.4): envelope/delegation-revoked-*,
    # payload/delegation-revocation-*, semantic/delegation-revocation-*. What stays here is the mailbox's reaction.
    R = ["§7.4", "M§12.4", "M§4.3"]
    T = "mailbox-trace"
    out.append(trace("mailbox-revoked-device-closed-and-forgotten",
                     "An owner device's mailbox-config carrying a revocation closes the revoked device's live binding now, drops it "
                     "from the registered devices and discards its KeyPackages.", R + ["M§5.7", "M§5.5"], T,
                     mbx_ctx(key_packages={BLA: {"one_time": 2, "last_resort": True}, BPH: {"one_time": 1}}), [
                         ({"sync": {"id": uid("s1"), "device": BLA, "since": None, "live": True}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s1"), "cursors": [], "next": None}}],
                          ms(kps={BLA: {"one_time": 2, "last_resort": True}, BPH: {"one_time": 1, "last_resort": False}})),
                         ({"config": {"id": uid("cfg"), "device": BPH, "revoked_devices": [BLA]}},
                          [macc(BPH, "cfg"), {"close": {"device": BLA, "reason": "delegation-revoked"}}],
                          ms(kps={BPH: {"one_time": 1, "last_resort": False}})),
                         ({"kp_fetch": {"id": uid("f1"), "from": CPH, "from_identity": BOB, "target": BOB, "grant": None}},
                          [{"key_packages": {"to": CPH, "in_reply_to": uid("f1"), "devices": {BPH: "one-time"}}}],
                          ms(kps={BPH: {"one_time": 0, "last_resort": False}})),
                     ]))
    return out


# ---------------------------------------------------------------- a committing device and the hub's answer (M§6.5, spec-gap 58)

def commit_retry_vectors():
    out = []
    T = "commit-retry-trace"
    ctx = {"component": "commit-retry", "max_attempts": 3}
    refs = ["M§6.5", "§15.3"]
    ans = lambda reason=None: {"answer": {"reason": reason} if reason else {}}
    synced = lambda needed=True: {"synced": {"still_needed": needed}}
    st = lambda attempt, state: {"attempt": attempt, "state": state}
    retry = [{"discard": {}}, {"sync": {}}]
    out.append(trace("commit-retry-accepted", "A commit the hub accepts is merged; nothing else happens.", refs, T, ctx, [
        (ans(), [{"merge": {}}], st(1, "merged")),
    ]))
    out.append(trace("commit-retry-conflict-reproposed",
                     "On mailbox.commit-conflict the device discards its pending commit, syncs until the winning commit is processed, "
                     "and re-proposes at the new epoch.", refs, T, ctx, [
                         (ans("mailbox.commit-conflict"), retry, st(1, "syncing")),
                         (synced(), [{"repropose": {"attempt": 2}}], st(2, "pending")),
                         (ans(), [{"merge": {}}], st(2, "merged")),
                     ]))
    out.append(trace("commit-retry-conflict-no-longer-needed",
                     "If the winning commit already did what this one meant to (the identity is already added), nothing is re-proposed.",
                     refs, T, ctx, [
                         (ans("mailbox.commit-conflict"), retry, st(1, "syncing")),
                         (synced(False), [{"done": "no-longer-needed"}], st(1, "done")),
                     ]))
    out.append(trace("commit-retry-stale-epoch-like-conflict",
                     "mailbox.stale-epoch means the device was further behind; it is handled the same way.", refs, T, ctx, [
                         (ans("mailbox.stale-epoch"), retry, st(1, "syncing")),
                         (synced(), [{"repropose": {"attempt": 2}}], st(2, "pending")),
                         (ans(), [{"merge": {}}], st(2, "merged")),
                     ]))
    out.append(trace("commit-retry-bounded",
                     "At most three proposals in all: a third conflict is surfaced, so contention cannot loop forever.", refs, T, ctx, [
                         (ans("mailbox.commit-conflict"), retry, st(1, "syncing")),
                         (synced(), [{"repropose": {"attempt": 2}}], st(2, "pending")),
                         (ans("mailbox.stale-epoch"), retry, st(2, "syncing")),
                         (synced(), [{"repropose": {"attempt": 3}}], st(3, "pending")),
                         (ans("mailbox.commit-conflict"), [{"discard": {}}, {"surface": "mailbox.commit-conflict"}], st(3, "surfaced")),
                     ]))
    out.append(trace("commit-retry-blocked-surfaces",
                     "policy.blocked (the commit broke M§7.3 or failed validation) is discarded and surfaced, never retried.", refs, T, ctx, [
                         (ans("policy.blocked"), [{"discard": {}}, {"surface": "policy.blocked"}], st(1, "surfaced")),
                     ]))
    out.append(trace("commit-retry-registered-mailbox-condition-surfaces",
                     "A registered mailbox condition that is not about ordering (quota) is surfaced without retry.", refs, T, ctx, [
                         (ans("mailbox.quota-exceeded"), [{"discard": {}}, {"surface": "mailbox.quota-exceeded"}], st(1, "surfaced")),
                     ]))
    out.append(trace("commit-retry-unknown-mailbox-condition-retries-once",
                     "An unregistered mailbox condition takes the category fallback: re-sync, retry once, then surface.", refs, T, ctx, [
                         (ans("mailbox.hub-draining"), retry, st(1, "syncing")),
                         (synced(), [{"repropose": {"attempt": 2}}], st(2, "pending")),
                         (ans("mailbox.hub-draining"), [{"discard": {}}, {"surface": "mailbox.hub-draining"}], st(2, "surfaced")),
                     ]))
    out.append(trace("commit-retry-unknown-mailbox-condition-after-a-conflict",
                     "The category fallback's one retry is its own: an unregistered mailbox condition met after a conflict's "
                     "re-proposal is still retried once, inside the bound of three proposals.", refs, T, ctx, [
                         (ans("mailbox.commit-conflict"), retry, st(1, "syncing")),
                         (synced(), [{"repropose": {"attempt": 2}}], st(2, "pending")),
                         (ans("mailbox.hub-draining"), retry, st(2, "syncing")),
                         (synced(), [{"repropose": {"attempt": 3}}], st(3, "pending")),
                         (ans("mailbox.hub-draining"), [{"discard": {}}, {"surface": "mailbox.hub-draining"}], st(3, "surfaced")),
                     ]))
    out.append(trace("commit-retry-fallback-retry-stays-inside-the-bound",
                     "At most three proposals for one operation, whatever the refusals were: after two conflicts the third "
                     "proposal is the last, so an unregistered mailbox condition is surfaced, not retried (found by fuzz.py: "
                     "the fallback's retry escaped the bound in two implementations).", refs, T, ctx, [
                         (ans("mailbox.commit-conflict"), retry, st(1, "syncing")),
                         (synced(), [{"repropose": {"attempt": 2}}], st(2, "pending")),
                         (ans("mailbox.stale-epoch"), retry, st(2, "syncing")),
                         (synced(), [{"repropose": {"attempt": 3}}], st(3, "pending")),
                         (ans("mailbox.hub-draining"), [{"discard": {}}, {"surface": "mailbox.hub-draining"}], st(3, "surfaced")),
                     ]))
    out.append(trace("commit-retry-unknown-category-surfaces",
                     "An unrecognized category is session.failed to this device: surfaced without retry.", refs, T, ctx, [
                         (ans("x-hubs.overloaded"), [{"discard": {}}, {"surface": "x-hubs.overloaded"}], st(1, "surfaced")),
                     ]))
    return out


# ---------------------------------------------------------------- a service restart and hub redelivery (M§5, M§6.5; spec-gap 59)

def restart_vectors():
    out = []
    RESTART = {"restart": {}}
    J = {GROUP: "joined"}
    QJ = {GROUP: {"hub": HUB_A, "state": "joined"}}
    T = "mailbox-trace"
    R = ["M§5.4", "M§6.6"]

    def sync_ev(label, device, since=None, **kw):
        return {"sync": {"id": uid(label), "device": device, "since": since, **kw}}

    def items(device, label, cursors, nxt=None):
        return {"items": {"to": device, "in_reply_to": uid(label), "cursors": list(cursors), "next": nxt}}

    push = lambda device, cur: {"push": {"to": device, "cursor": cur}}

    out.append(trace("mailbox-restart-keeps-items-cursors-acks-registrations",
                     "A mailbox restart keeps its items, cursor counter, per-device acknowledgements and group registrations: "
                     "queue-mode deletion still waits for the device that acknowledged before the restart, and new items continue "
                     "the cursor sequence.", R + ["M§4.4"], T, mbx_ctx(mode="queue", groups=QJ), [
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (hubdep("h2", 2), [macc(HUB_A, "h2", c(2))], ms([c(1), c(2)], J)),
                         (sync_ev("s1", BPH, c(2), ack_through=c(2)), [items(BPH, "s1", [])], ms([c(1), c(2)], J)),
                         (RESTART, [], ms([c(1), c(2)], J)),
                         (sync_ev("s2", BLA, c(1), ack_through=c(1)), [items(BLA, "s2", [c(2)])], ms([c(2)], J)),
                         (hubdep("h3", 3), [macc(HUB_A, "h3", c(3))], ms([c(2), c(3)], J)),
                     ]))
    out.append(trace("mailbox-restart-drops-live-bindings",
                     "Live bindings are connections and do not survive a restart: nothing is pushed until the device syncs live again, "
                     "and what arrived meanwhile is returned by that sync.", R + ["M§9.1"], T, mbx_ctx(groups=QJ), [
                         (sync_ev("s1", BPH, live=True), [items(BPH, "s1", [])], ms([], J)),
                         (RESTART, [], ms([], J)),
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (sync_ev("s2", BPH, live=True), [items(BPH, "s2", [c(1)])], ms([c(1)], J)),
                         (hubdep("h2", 2), [macc(HUB_A, "h2", c(2)), push(BPH, c(2))], ms([c(1), c(2)], J)),
                     ]))
    out.append(trace("mailbox-restart-pending-ttl-continues",
                     "A pending group's age is kept across a restart: pending_group_ttl counts from the welcome, not from the restart.",
                     R, T, mbx_ctx(), [
                         (welcome(grant_=grant()), [macc(CPH, "w1", c(1))], ms([c(1)], {GROUP: "pending"})),
                         ({"advance": 604000}, [], ms([c(1)], {GROUP: "pending"})),
                         (RESTART, [], ms([c(1)], {GROUP: "pending"})),
                         ({"advance": 800}, [], ms([c(1)], {GROUP: "pending"})),
                         ({"advance": 1}, [], ms()),
                     ]))
    KP = {BPH: {"one_time": 1, "last_resort": True}}
    out.append(trace("mailbox-restart-keeps-key-packages-revoked-grants-archive-index",
                     "KeyPackages, revoked grants and the archive index survive a restart: a revoked grant stays revoked, a KeyPackage "
                     "served once is not served again, and a second archive for the same (group, seq) is still a duplicate.",
                     R + ["M§5.5", "M§5.7", "M§12.2"], T, mbx_ctx(key_packages=KP), [
                         ({"config": {"id": uid("cfg"), "device": BPH, "revoked_grants": [uid("g1")]}}, [macc(BPH, "cfg")],
                          ms(kps={BPH: {"one_time": 1, "last_resort": True}})),
                         ({"kp_fetch": {"id": uid("f1"), "from": CPH, "from_identity": BOB, "target": BOB, "grant": None}},
                          [{"key_packages": {"to": CPH, "in_reply_to": uid("f1"), "devices": {BPH: "one-time"}}}],
                          ms(kps={BPH: {"one_time": 0, "last_resort": True}})),
                         ({"archive": {"id": uid("ar1"), "device": BPH, "ref_group": GROUP, "ref_seq": 42}}, [macc(BPH, "ar1", c(1))],
                          ms([c(1)], kps={BPH: {"one_time": 0, "last_resort": True}})),
                         (RESTART, [], ms([c(1)], kps={BPH: {"one_time": 0, "last_resort": True}})),
                         (welcome(grant_=grant()), [err(CPH, "w1", "policy.first-contact-required")],
                          ms([c(1)], kps={BPH: {"one_time": 0, "last_resort": True}})),
                         ({"kp_fetch": {"id": uid("f2"), "from": CPH, "from_identity": BOB, "target": BOB, "grant": None}},
                          [{"key_packages": {"to": CPH, "in_reply_to": uid("f2"), "devices": {BPH: "last-resort"}}}],
                          ms([c(1)], kps={BPH: {"one_time": 0, "last_resort": True}})),
                         ({"archive": {"id": uid("ar2"), "device": BLA, "ref_group": GROUP, "ref_seq": 42}}, [macc(BLA, "ar2", c(1), dup=True)],
                          ms([c(1)], kps={BPH: {"one_time": 0, "last_resort": True}})),
                     ]))
    ictx = mbx_ctx(intro_limit=1, intro_window=3600, inbox_cap=16)
    intro = lambda label: {"first_contact": {"id": uid(label), "from": APH, "sender_identity": ALICE, "recipient": BOB,
                                             "kind": "introduction", "expires_at": NOW + 604800}}
    out.append(trace("mailbox-restart-keeps-introduction-rate-window",
                     "The first-contact rate window survives a restart, so restarting a mailbox does not reset a sender's allowance.",
                     R + ["§19.4", "M§14.3"], T, ictx, [
                         (intro("i1"), [macc(APH, "i1", c(1))], ms([c(1)])),
                         (RESTART, [], ms([c(1)])),
                         ({"advance": 600}, [], ms([c(1)])),
                         (intro("i2"), [{"error": {"to": APH, "in_reply_to": uid("i2"), "reason": "policy.rate-limited", "retry_after": 3000}}],
                          ms([c(1)])),
                     ]))
    G59 = ["M§6.5", "M§6.6", "M§9.3"]
    out.append(trace("mailbox-hub-deposit-redelivered-idempotent",
                     "A hub retries a fan-out it saw no acknowledgement for, so the same (group, seq) can arrive twice: the second is "
                     "accepted with the original cursor and duplicate, and is neither stored nor pushed again.", G59, T,
                     mbx_ctx(groups=QJ), [
                         (sync_ev("s1", BLA, live=True), [items(BLA, "s1", [])], ms([], J)),
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(1)), push(BLA, c(1))], ms([c(1)], J)),
                         (hubdep("h1-retry", 1), [macc(HUB_A, "h1-retry", c(1), dup=True)], ms([c(1)], J)),
                         (hubdep("h2", 2), [macc(HUB_A, "h2", c(2)), push(BLA, c(2))], ms([c(1), c(2)], J)),
                     ]))
    out.append(trace("mailbox-hub-deposit-redelivered-after-deletion",
                     "A redelivery of an item already deleted in queue mode is still a duplicate (the hub delivers in seq order, so a "
                     "seq at or below the group's highest is not new); it carries no cursor and nothing is stored.", G59 + ["M§4.4"], T,
                     mbx_ctx(mode="queue", groups=QJ), [
                         (hubdep("h1", 1), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (sync_ev("s1", BPH, c(1), ack_through=c(1)), [items(BPH, "s1", [])], ms([c(1)], J)),
                         (sync_ev("s2", BLA, c(1), ack_through=c(1)), [items(BLA, "s2", [])], ms([], J)),
                         (hubdep("h1-retry", 1), [macc(HUB_A, "h1-retry", dup=True)], ms([], J)),
                     ]))

    H = "hub-trace"
    RR = {ALICE: [ALA, APH], BOB: [BPH]}
    out.append(trace("hub-restart-resends-unacknowledged-heads",
                     "A hub restart keeps every fan-out queue and re-sends the head of each unacknowledged one (retry before later "
                     "items); acknowledged items are not re-sent.", ["M§6.5"], H, hub_ctx(), [
                         (dep("a1", APH, ALICE, "application", 1), [acc(APH, "a1", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, RR, {ALICE: [1], BOB: [1]})),
                         ({"ack": {"identity": ALICE, "seq": 1}}, [], hs(1, 2, RR, {BOB: [1]})),
                         (dep("a2", APH, ALICE, "application", 1), [acc(APH, "a2", 2), fan(ALICE, 2)],
                          hs(1, 3, RR, {ALICE: [2], BOB: [1, 2]})),
                         (RESTART, [fan(ALICE, 2), fan(BOB, 1)], hs(1, 3, RR, {ALICE: [2], BOB: [1, 2]})),
                         ({"ack": {"identity": BOB, "seq": 1}}, [fan(BOB, 2)], hs(1, 3, RR, {ALICE: [2], BOB: [2]})),
                     ]))
    out.append(trace("hub-restart-keeps-epoch-and-digests",
                     "A hub restart keeps the epoch, the sequence counter and the deposit digests: a retried deposit is still a "
                     "duplicate, a commit for the old epoch still conflicts, and new items continue the sequence.",
                     ["M§6.5", "M§9.3"], H, hub_ctx(), [
                         (dep("k1", APH, ALICE, "handshake", 1, commit={"adds": [], "removes": []}),
                          [acc(APH, "k1", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")], hs(2, 2, RR, {ALICE: [1], BOB: [1]})),
                         ({"ack": {"identity": ALICE, "seq": 1}}, [], hs(2, 2, RR, {BOB: [1]})),
                         ({"ack": {"identity": BOB, "seq": 1}}, [], hs(2, 2, RR)),
                         (RESTART, [], hs(2, 2, RR)),
                         (dep("k1-retry", APH, ALICE, "handshake", 1, digest="k1", commit={"adds": [], "removes": []}),
                          [acc(APH, "k1-retry", 1, dup=True)], hs(2, 2, RR)),
                         (dep("k2", BPH, BOB, "handshake", 1, commit={"adds": [], "removes": []}),
                          [err(BPH, "k2", "mailbox.commit-conflict")], hs(2, 2, RR)),
                         (dep("a1", BPH, BOB, "application", 2), [acc(BPH, "a1", 2), fan(ALICE, 2), fan(BOB, 2)],
                          hs(2, 3, RR, {ALICE: [2], BOB: [2]})),
                     ]))
    return out


# ---------------------------------------------------------------- moving a group to another hub (M§7.4; spec-gap 60)

# ---------------------------------------------------------------- the hub cannot be reached (M§9.4; spec-gap 72)

def hub_outage_vectors():
    out = []
    T = "hub-outage-trace"
    refs = ["M§9.4", "M§9.3", "§13.2"]
    ctx = {"component": "hub-outage", "now": NOW}

    def snap(state, pending=(), attempt=0, down_for=None, handover_attempt=0):
        return {"state": state, "pending": list(pending), "attempt": attempt, "down_for": down_for,
                "handover_attempt": handover_attempt}

    def dep(i):
        return {"deposit": {"id": uid(i)}}

    def unreachable(i):
        return {"answer": {"id": uid(i), "reason": "mailbox.hub-unreachable"}}

    def accepted(i):
        return {"answer": {"id": uid(i)}}

    a, b, c = uid("o-a"), uid("o-b"), uid("o-c")
    out.append(trace("hub-outage-pending-and-backoff",
                     "A deposit the mailbox could not hand to the hub stays pending and is re-deposited as the same bytes with the "
                     "§13.2 backoff: 1 s, doubling, 60 s ceiling; the attempt count and the outage's age are visible.", refs, T, ctx, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (unreachable("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         ({"advance": 1}, [{"forward": a}], snap("down", [a], 1, 1)),
                         (unreachable("o-a"), [{"retry_in": 2}], snap("down", [a], 2, 1)),
                         ({"advance": 1}, [], snap("down", [a], 2, 2)),
                         ({"advance": 1}, [{"forward": a}], snap("down", [a], 2, 3)),
                         (unreachable("o-a"), [{"retry_in": 4}], snap("down", [a], 3, 3)),
                         ({"advance": 4}, [{"forward": a}], snap("down", [a], 3, 7)),
                         (unreachable("o-a"), [{"retry_in": 8}], snap("down", [a], 4, 7)),
                         ({"advance": 8}, [{"forward": a}], snap("down", [a], 4, 15)),
                         (unreachable("o-a"), [{"retry_in": 16}], snap("down", [a], 5, 15)),
                         ({"advance": 16}, [{"forward": a}], snap("down", [a], 5, 31)),
                         (unreachable("o-a"), [{"retry_in": 32}], snap("down", [a], 6, 31)),
                         ({"advance": 32}, [{"forward": a}], snap("down", [a], 6, 63)),
                         (unreachable("o-a"), [{"retry_in": 60}], snap("down", [a], 7, 63)),
                         ({"advance": 60}, [{"forward": a}], snap("down", [a], 7, 123)),
                         (unreachable("o-a"), [{"retry_in": 60}], snap("down", [a], 8, 123)),
                     ]))
    out.append(trace("hub-outage-queues-then-flushes-in-order",
                     "While the hub is down, later deposits queue behind the pending one; the first accepted answer ends the "
                     "outage, flushes the queue in order and resets the backoff.", refs + ["M§9.2"], T, ctx, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (unreachable("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         (dep("o-b"), [{"queued": b}], snap("down", [a, b], 1, 0)),
                         (dep("o-c"), [{"queued": c}], snap("down", [a, b, c], 1, 0)),
                         ({"advance": 1}, [{"forward": a}], snap("down", [a, b, c], 1, 1)),
                         (accepted("o-a"), [{"sent": a}, {"forward": b}, {"forward": c}], snap("up", [b, c])),
                         (accepted("o-b"), [{"sent": b}], snap("up", [c])),
                         (accepted("o-c"), [{"sent": c}], snap("up")),
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (unreachable("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                     ]))
    out.append(trace("hub-outage-no-answer-is-an-outage",
                     "Silence is an outage too: a deposit with no answer at all is retried like one refused hub-unreachable.",
                     refs, T, ctx, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         ({"no_answer": {"id": a}}, [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         ({"advance": 1}, [{"forward": a}], snap("down", [a], 1, 1)),
                         (accepted("o-a"), [{"sent": a}], snap("up")),
                     ]))
    full = lambda i: {"answer": {"id": uid(i), "reason": "mailbox.quota-exceeded"}}
    out.append(trace("hub-outage-storage-refusal-is-an-outage",
                     "A hub that cannot store the deposit (M§9.3, spec-gap 99) is unavailable to the sender: the item stays "
                     "pending with the same backoff, later content queues behind it, and an accepted ends it and flushes.",
                     refs, T, ctx, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (full("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         (dep("o-b"), [{"queued": b}], snap("down", [a, b], 1, 0)),
                         ({"advance": 1}, [{"forward": a}], snap("down", [a, b], 1, 1)),
                         (full("o-a"), [{"retry_in": 2}], snap("down", [a, b], 2, 1)),
                         ({"advance": 2}, [{"forward": a}], snap("down", [a, b], 2, 3)),
                         (accepted("o-a"), [{"sent": a}, {"forward": b}], snap("up", [b])),
                         (accepted("o-b"), [{"sent": b}], snap("up")),
                     ]))
    out.append(trace("hub-outage-storage-refusal-reaches-the-threshold",
                     "A hub that stays unable to store for hub_timeout is the successor trigger, as an unreachable one is.",
                     refs + ["M§7.5"], T, {**ctx, "hub_timeout": 3600}, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (full("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         ({"advance": 1}, [{"forward": a}], snap("down", [a], 1, 1)),
                         (full("o-a"), [{"retry_in": 2}], snap("down", [a], 2, 1)),
                         ({"advance": 3598}, [{"forward": a}], snap("down", [a], 2, 3599)),
                         (full("o-a"), [{"retry_in": 4}], snap("down", [a], 3, 3599)),
                         ({"advance": 1}, [{"successor": {"pending": [a]}}], snap("abandoned", [], 3, 3600)),
                     ]))
    out.append(trace("hub-outage-other-refusal-is-not-an-outage",
                     "A refusal for any other reason takes the item out of the outbox for its own handling (M§6.5 for a commit); "
                     "the hub is not down.", refs + ["M§6.5"], T, ctx, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         ({"answer": {"id": a, "reason": "policy.blocked"}}, [{"refused": {"id": a, "reason": "policy.blocked"}}], snap("up")),
                         (dep("o-b"), [{"forward": b}], snap("up", [b])),
                         (accepted("o-b"), [{"sent": b}], snap("up")),
                         ({"answer": {"id": b}}, [], snap("up")),
                     ]))
    out.append(trace("hub-outage-refused-while-down-leaves-nothing-to-retry",
                     "During an outage the pending item is refused for a reason of its own: it leaves the outbox, and the retry that "
                     "was due finds nothing to send. The outage itself ends only with an accepted.", refs, T, ctx, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (unreachable("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         ({"answer": {"id": a, "reason": "policy.blocked"}}, [{"refused": {"id": a, "reason": "policy.blocked"}}],
                          snap("down", [], 1, 0)),
                         ({"advance": 1}, [], snap("down", [], 1, 1)),
                     ]))
    out.append(trace("hub-outage-successor-after-threshold",
                     "A hub down for hub_timeout is the M§7.5 trigger: the device creates the successor group and hands it the "
                     "pending items to re-encrypt; the dead group's outbox is abandoned and takes no more deposits.",
                     refs + ["M§7.5"], T, {**ctx, "hub_timeout": 3600}, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (unreachable("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         (dep("o-b"), [{"queued": b}], snap("down", [a, b], 1, 0)),
                         ({"advance": 1}, [{"forward": a}], snap("down", [a, b], 1, 1)),
                         (unreachable("o-a"), [{"retry_in": 2}], snap("down", [a, b], 2, 1)),
                         ({"advance": 3598}, [{"forward": a}], snap("down", [a, b], 2, 3599)),
                         (unreachable("o-a"), [{"retry_in": 4}], snap("down", [a, b], 3, 3599)),
                         ({"advance": 1}, [{"successor": {"pending": [a, b]}}], snap("abandoned", [], 3, 3600)),
                         ({"advance": 100}, [], snap("abandoned", [], 3, 3700)),
                         (dep("o-c"), [{"refuse": "group-abandoned"}], snap("abandoned", [], 3, 3700)),
                     ]))
    out.append(trace("hub-outage-threshold-counts-from-the-current-outage",
                     "An accepted answer ends an outage; the threshold counts from the start of the next one, not the first.",
                     refs + ["M§7.5"], T, {**ctx, "hub_timeout": 3600}, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (unreachable("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         ({"advance": 3000}, [{"forward": a}], snap("down", [a], 1, 3000)),
                         (accepted("o-a"), [{"sent": a}], snap("up")),
                         (dep("o-b"), [{"forward": b}], snap("up", [b])),
                         (unreachable("o-b"), [{"retry_in": 1}], snap("down", [b], 1, 0)),
                         ({"advance": 3599}, [{"forward": b}], snap("down", [b], 1, 3599)),
                         (unreachable("o-b"), [{"retry_in": 2}], snap("down", [b], 2, 3599)),
                         ({"advance": 1}, [{"successor": {"pending": [b]}}], snap("abandoned", [], 2, 3600)),
                     ]))
    failed, retry = {"handover_failed": {}}, [{"handover": "retry"}]
    out.append(trace("hub-outage-handover-failure-retried-with-backoff",
                     "The hand-over to the successor can fail (no successor could be created, or an item could not be moved): "
                     "the abandoned outbox retries it with the §13.2 backoff started afresh — 1 s, doubling, 60 s ceiling — "
                     "one retry per schedule, and still takes no deposits.",
                     refs + ["M§7.5"], T, {**ctx, "hub_timeout": 10}, [
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (unreachable("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         ({"advance": 10}, [{"successor": {"pending": [a]}}], snap("abandoned", [], 1, 10)),
                         (failed, [{"handover_retry_in": 1}], snap("abandoned", [], 1, 10, 1)),
                         ({"advance": 1}, retry, snap("abandoned", [], 1, 11, 1)),
                         ({"advance": 5}, [], snap("abandoned", [], 1, 16, 1)),
                         (failed, [{"handover_retry_in": 2}], snap("abandoned", [], 1, 16, 2)),
                         ({"advance": 1}, [], snap("abandoned", [], 1, 17, 2)),
                         (dep("o-b"), [{"refuse": "group-abandoned"}], snap("abandoned", [], 1, 17, 2)),
                         ({"advance": 1}, retry, snap("abandoned", [], 1, 18, 2)),
                         (failed, [{"handover_retry_in": 4}], snap("abandoned", [], 1, 18, 3)),
                         ({"advance": 4}, retry, snap("abandoned", [], 1, 22, 3)),
                         (failed, [{"handover_retry_in": 8}], snap("abandoned", [], 1, 22, 4)),
                         ({"advance": 8}, retry, snap("abandoned", [], 1, 30, 4)),
                         (failed, [{"handover_retry_in": 16}], snap("abandoned", [], 1, 30, 5)),
                         ({"advance": 16}, retry, snap("abandoned", [], 1, 46, 5)),
                         (failed, [{"handover_retry_in": 32}], snap("abandoned", [], 1, 46, 6)),
                         ({"advance": 32}, retry, snap("abandoned", [], 1, 78, 6)),
                         (failed, [{"handover_retry_in": 60}], snap("abandoned", [], 1, 78, 7)),
                         ({"advance": 59}, [], snap("abandoned", [], 1, 137, 7)),
                         ({"advance": 1}, retry, snap("abandoned", [], 1, 138, 7)),
                         (failed, [{"handover_retry_in": 60}], snap("abandoned", [], 1, 138, 8)),
                     ]))
    out.append(trace("hub-outage-handover-failed-outside-abandonment-is-nothing",
                     "handover_failed means something only once the outbox is abandoned: with the hub up or down it emits "
                     "nothing and changes nothing, and the ordinary retry goes on; two failures before the retry both count, "
                     "and the later schedule replaces the earlier.",
                     refs + ["M§7.5"], T, {**ctx, "hub_timeout": 10}, [
                         (failed, [], snap("up")),
                         (dep("o-a"), [{"forward": a}], snap("up", [a])),
                         (unreachable("o-a"), [{"retry_in": 1}], snap("down", [a], 1, 0)),
                         (failed, [], snap("down", [a], 1, 0)),
                         ({"advance": 1}, [{"forward": a}], snap("down", [a], 1, 1)),
                         ({"advance": 9}, [{"successor": {"pending": [a]}}], snap("abandoned", [], 1, 10)),
                         (failed, [{"handover_retry_in": 1}], snap("abandoned", [], 1, 10, 1)),
                         (failed, [{"handover_retry_in": 2}], snap("abandoned", [], 1, 10, 2)),
                         ({"advance": 1}, [], snap("abandoned", [], 1, 11, 2)),
                         ({"advance": 1}, retry, snap("abandoned", [], 1, 12, 2)),
                     ]))
    # the mailbox's side of it
    out.append(trace("mailbox-forward-hub-unreachable-answered",
                     "A forwarded deposit the mailbox could not hand to the group's hub (connection refused, or lost with the "
                     "deposit in flight) is answered mailbox.hub-unreachable, so the device keeps it pending (M§9.4).",
                     ["M§9.4", "M§5.2", "M§16"], "mailbox-trace", mbx_ctx(groups={GROUP: {"hub": HUB_A, "state": "joined"}}), [
                         ({"forward": {"id": uid("fw-1"), "device": BPH, "identity": BOB, "group": GROUP, "to": HUB_A}},
                          [{"forward": {"to": HUB_A, "id": uid("fw-1")}}], ms([], {GROUP: "joined"})),
                         ({"forward_failed": {"id": uid("fw-1"), "device": BPH, "to": HUB_A}},
                          [err(BPH, "fw-1", "mailbox.hub-unreachable")], ms([], {GROUP: "joined"})),
                     ]))
    return out


def hub_change_vectors():
    out = []
    HUB_B = "did:web:mbx.bob.example"
    R = {ALICE: [ALA, APH], BOB: [BPH]}
    refs = ["M§7.4", "M§6.5"]
    move = {"adds": [], "removes": [], "moves_to": HUB_B}

    out.append(trace("hub-move-ordered-then-refuses",
                     "The commit moving the group is ordered and fanned out like any other; afterwards the old hub refuses every "
                     "deposit for the group with mailbox.unknown-group.", refs, "hub-trace", hub_ctx(), [
                         (dep("mv", BPH, BOB, "handshake", 1, commit=move),
                          [acc(BPH, "mv", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                         (dep("a1", APH, ALICE, "application", 1), [err(APH, "a1", "mailbox.unknown-group")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                         (dep("k2", APH, ALICE, "handshake", 2, commit={"adds": [], "removes": []}), [err(APH, "k2", "mailbox.unknown-group")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                         (dep("gi", APH, ALICE, "group-info"), [err(APH, "gi", "mailbox.unknown-group")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                         (dep("ty", APH, ALICE, "ephemeral", expires_at=NOW + 10), [err(APH, "ty", "mailbox.unknown-group")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                     ]))
    out.append(trace("hub-move-drains-queues",
                     "What the old hub ordered before and including the move is still delivered, in order, as mailboxes acknowledge.",
                     refs, "hub-trace", hub_ctx(), [
                         (dep("a1", APH, ALICE, "application", 1), [acc(APH, "a1", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                         (dep("mv", BPH, BOB, "handshake", 1, commit=move), [acc(BPH, "mv", 2)],
                          hs(2, 3, R, {ALICE: [1, 2], BOB: [1, 2]}, moved_to=HUB_B)),
                         ({"ack": {"identity": ALICE, "seq": 1}}, [fan(ALICE, 2, "handshake")], hs(2, 3, R, {ALICE: [2], BOB: [1, 2]}, moved_to=HUB_B)),
                         ({"ack": {"identity": BOB, "seq": 1}}, [fan(BOB, 2, "handshake")], hs(2, 3, R, {ALICE: [2], BOB: [2]}, moved_to=HUB_B)),
                     ]))
    out.append(trace("hub-move-new-hub-continues-numbering",
                     "The new hub starts after the seq the old hub gave the moving commit (handover_seq), so (group, seq) stays "
                     "unique for the conversation's life — archive records are bound to it (M§12.2).", refs + ["M§12.2"], "hub-trace",
                     {**hub_ctx(epoch=2), "hub": HUB_B, "next_seq": 3}, [
                         (dep("a2", APH, ALICE, "application", 2), [acc(APH, "a2", 3), fan(ALICE, 3), fan(BOB, 3)],
                          hs(2, 4, R, {ALICE: [3], BOB: [3]})),
                     ]))

    # spec-gap 128: the group comes back to a hub it left. The daemon has read the GroupInfo (it names this hub) and
    # hands the machine its epoch and roster as `view`, with the `handover_seq` the other hub gave the moving commit.
    gi_fan = [{"fanout": {"to": ALICE, "class": "group-info"}}, {"fanout": {"to": BOB, "class": "group-info"}}]
    back = {"epoch": 4, "roster": R}
    out.append(trace("hub-move-back-returns-the-group",
                     "A group that moved away comes back: the committer's group-info deposit carries handover_seq and names this "
                     "hub again, so the hub hosts it from the GroupInfo's epoch and roster and numbers on from handover_seq + 1. "
                     "What it ordered before the group left still drains first, in order (spec-gap 128).",
                     refs + ["M§6.5"], "hub-trace", hub_ctx(), [
                         (dep("a1", APH, ALICE, "application", 1), [acc(APH, "a1", 1), fan(ALICE, 1), fan(BOB, 1)],
                          hs(1, 2, R, {ALICE: [1], BOB: [1]})),
                         (dep("mv", BPH, BOB, "handshake", 1, commit=move), [acc(BPH, "mv", 2)],
                          hs(2, 3, R, {ALICE: [1, 2], BOB: [1, 2]}, moved_to=HUB_B)),
                         ({"ack": {"identity": BOB, "seq": 1}}, [fan(BOB, 2, "handshake")], hs(2, 3, R, {ALICE: [1, 2], BOB: [2]}, moved_to=HUB_B)),
                         (dep("gi", APH, ALICE, "group-info", handover_seq=5, view=back), [acc_nc(APH, "gi")] + gi_fan,
                          hs(4, 6, R, {ALICE: [1, 2], BOB: [2]}, group_info=True)),
                         (dep("a6", APH, ALICE, "application", 4), [acc(APH, "a6", 6)],
                          hs(4, 7, R, {ALICE: [1, 2, 6], BOB: [2, 6]}, group_info=True)),
                         ({"ack": {"identity": BOB, "seq": 2}}, [fan(BOB, 6)], hs(4, 7, R, {ALICE: [1, 2, 6], BOB: [6]}, group_info=True)),
                         ({"ack": {"identity": ALICE, "seq": 1}}, [fan(ALICE, 2, "handshake")], hs(4, 7, R, {ALICE: [2, 6], BOB: [6]}, group_info=True)),
                     ]))
    out.append(trace("hub-move-back-renumbering-refused",
                     "A return whose handover_seq is below the hub's next seq would give a seq twice for the group, so it is "
                     "refused policy.blocked and the group stays moved; a group-info with no handover_seq is still answered "
                     "mailbox.unknown-group (spec-gap 128, M§12.2: (group, seq) is unique).",
                     refs + ["M§12.2"], "hub-trace", hub_ctx(), [
                         (dep("mv", BPH, BOB, "handshake", 1, commit=move), [acc(BPH, "mv", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                         (dep("g1", APH, ALICE, "group-info", handover_seq=1, view=back), [err(APH, "g1", "policy.blocked")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                         (dep("g2", APH, ALICE, "group-info"), [err(APH, "g2", "mailbox.unknown-group")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                         (dep("g3", APH, ALICE, "group-info", handover_seq=2, view=back), [acc_nc(APH, "g3")] + gi_fan,
                          hs(4, 3, R, {ALICE: [1], BOB: [1]}, group_info=True)),
                     ]))
    out.append(trace("hub-move-back-by-a-non-member-refused",
                     "Only a member of the returning group may bring it back: a depositor whose identity is not in the "
                     "GroupInfo's roster is refused policy.blocked, as any non-member's group-info is (spec-gap 128).",
                     refs, "hub-trace", hub_ctx(), [
                         (dep("mv", BPH, BOB, "handshake", 1, commit=move), [acc(BPH, "mv", 1), fan(ALICE, 1, "handshake"), fan(BOB, 1, "handshake")],
                          hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                         (dep("gi", BPH, BOB, "group-info", handover_seq=3, view={"epoch": 4, "roster": {ALICE: [ALA, APH]}}),
                          [err(BPH, "gi", "policy.blocked")], hs(2, 2, R, {ALICE: [1], BOB: [1]}, moved_to=HUB_B)),
                     ]))

    # --- member mailboxes
    T = "mailbox-trace"
    J = {GROUP: "joined"}
    JA = {GROUP: {"hub": HUB_A, "state": "joined"}}
    mrefs = ["M§7.4", "M§6.6"]

    def hd(label, seq, frm, cls="application"):
        return hubdep(label, seq, cls=cls, frm=frm)

    def cfg(label="cfg", handover=2, hub=HUB_B):
        g = {"group": GROUP, "state": "joined", "hub": hub}
        if handover is not None:
            g["handover_seq"] = handover
        return {"config": {"id": uid(label), "device": BPH, "groups": [g]}}

    def fwd(label, to):
        return {"forward": {"id": uid(label), "device": BPH, "identity": BOB, "group": GROUP, "to": to}}

    out.append(trace("mailbox-hub-move-switches-registration",
                     "An owner device that processed the moving commit names the new hub and that commit's seq: fan-out and "
                     "forwarding now go by the new hub, and the old hub's later deposits are refused.", mrefs + ["M§5.2"], T,
                     mbx_ctx(groups=JA), [
                         (hd("h1", 1, HUB_A), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (hd("h2", 2, HUB_A, "handshake"), [macc(HUB_A, "h2", c(2))], ms([c(1), c(2)], J)),
                         (cfg(), [macc(BPH, "cfg")], ms([c(1), c(2)], J)),
                         (hd("b3", 3, HUB_B), [macc(HUB_B, "b3", c(3))], ms([c(1), c(2), c(3)], J)),
                         (hd("a3", 3, HUB_A), [err(HUB_A, "a3", "mailbox.unknown-group")], ms([c(1), c(2), c(3)], J)),
                         (fwd("f1", HUB_B), [{"forward": {"to": HUB_B, "id": uid("f1")}}], ms([c(1), c(2), c(3)], J)),
                         (fwd("f2", HUB_A), [err(BPH, "f2", "mailbox.unknown-group")], ms([c(1), c(2), c(3)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-previous-hub-redelivery",
                     "The old hub retrying an item it ordered before the move (its acknowledgement was lost) gets a duplicate "
                     "acknowledgement, so its queue drains.", mrefs + ["M§6.5"], T, mbx_ctx(groups=JA), [
                         (hd("h1", 1, HUB_A), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (hd("h2", 2, HUB_A, "handshake"), [macc(HUB_A, "h2", c(2))], ms([c(1), c(2)], J)),
                         (cfg(), [macc(BPH, "cfg")], ms([c(1), c(2)], J)),
                         (hd("h2-retry", 2, HUB_A, "handshake"), [macc(HUB_A, "h2-retry", c(2), dup=True)], ms([c(1), c(2)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-new-hub-waits-for-handover",
                     "The committing device can name the new hub before the old hub's fan-out of the move reaches its own mailbox: "
                     "the new hub is refused (and retries) until the old hub's items through handover_seq are stored, so the "
                     "mailbox keeps seq order.", mrefs + ["M§6.5"], T, mbx_ctx(groups=JA), [
                         (hd("h1", 1, HUB_A), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (cfg(), [macc(BPH, "cfg")], ms([c(1)], J)),
                         (hd("b3", 3, HUB_B), [err(HUB_B, "b3", "mailbox.unknown-group")], ms([c(1)], J)),
                         (hd("h2", 2, HUB_A, "handshake"), [macc(HUB_A, "h2", c(2))], ms([c(1), c(2)], J)),
                         (hd("b3-retry", 3, HUB_B), [macc(HUB_B, "b3-retry", c(3))], ms([c(1), c(2), c(3)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-wait-covers-everything-from-the-new-hub",
                     "While the old hub's items are still missing, the new hub is held off whatever it sends: a GroupInfo too, and a "
                     "wrongly numbered item is told to retry (mailbox.unknown-group) before its numbering is judged (policy.blocked).",
                     mrefs + ["M§6.5"], T, mbx_ctx(groups=JA), [
                         (hd("h1", 1, HUB_A), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (cfg(), [macc(BPH, "cfg")], ms([c(1)], J)),
                         (hubdep("b-gi", None, cls="group-info", frm=HUB_B), [err(HUB_B, "b-gi", "mailbox.unknown-group")], ms([c(1)], J)),
                         (hd("b1", 1, HUB_B), [err(HUB_B, "b1", "mailbox.unknown-group")], ms([c(1)], J)),
                         (hd("h2", 2, HUB_A, "handshake"), [macc(HUB_A, "h2", c(2))], ms([c(1), c(2)], J)),
                         (hd("b1-retry", 1, HUB_B), [err(HUB_B, "b1-retry", "policy.blocked")], ms([c(1), c(2)], J)),
                         (hubdep("b-gi-retry", None, cls="group-info", frm=HUB_B), [macc(HUB_B, "b-gi-retry", c(3))], ms([c(1), c(2), c(3)], J)),
                     ]))
    out.append(trace("mailbox-push-in-device-order",
                     "A stored item is pushed to the bound devices in device order, not in the order they bound.",
                     ["M§5.4"], T, mbx_ctx(groups=JA), [
                         ({"sync": {"id": uid("s1"), "device": BPH, "since": None, "live": True}},
                          [{"items": {"to": BPH, "in_reply_to": uid("s1"), "cursors": [], "next": None}}], ms([], J)),
                         ({"sync": {"id": uid("s2"), "device": BLA, "since": None, "live": True}},
                          [{"items": {"to": BLA, "in_reply_to": uid("s2"), "cursors": [], "next": None}}], ms([], J)),
                         (hd("h1", 1, HUB_A), [macc(HUB_A, "h1", c(1)), {"push": {"to": BLA, "cursor": c(1)}}, {"push": {"to": BPH, "cursor": c(1)}}],
                          ms([c(1)], J)),
                     ]))
    def expired(missing, hub=HUB_A):
        return {"handover_expired": {"group": GROUP, "hub": hub, "missing": missing}}

    xrefs = mrefs + ["M§6.5"]
    out.append(trace("mailbox-hub-move-handover-wait-expires",
                     "The old hub never delivers the moving commit (it died after ordering it; spec-gap 71): the new hub is held "
                     "off for handover_wait after the owner's device named it, then admitted, and the seqs never stored are left "
                     "to the owner's devices as a gap (M§6.5). The numbering rule still holds afterwards.", xrefs, T,
                     mbx_ctx(groups=JA), [
                         (hd("h1", 1, HUB_A), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (cfg(), [macc(BPH, "cfg")], ms([c(1)], J)),
                         (hd("b3", 3, HUB_B), [err(HUB_B, "b3", "mailbox.unknown-group")], ms([c(1)], J)),
                         ({"advance": 299}, [], ms([c(1)], J)),
                         (hd("b3-r1", 3, HUB_B), [err(HUB_B, "b3-r1", "mailbox.unknown-group")], ms([c(1)], J)),
                         ({"advance": 1}, [], ms([c(1)], J)),
                         (hd("b3-r2", 3, HUB_B), [expired([2]), macc(HUB_B, "b3-r2", c(2))], ms([c(1), c(2)], J)),
                         (hd("b4", 4, HUB_B), [macc(HUB_B, "b4", c(3))], ms([c(1), c(2), c(3)], J)),
                         (hd("b2", 2, HUB_B), [err(HUB_B, "b2", "policy.blocked")], ms([c(1), c(2), c(3)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-handover-wait-expiry-announced-on-a-refused-deposit",
                     "The wait ran out and the first thing the new hub sends is a seq at or below handover_seq: the expiry is announced "
                     "then, once, and that deposit is still refused policy.blocked; what follows above handover_seq is stored with no "
                     "second announcement (spec-gap 88).", xrefs, T, mbx_ctx(groups=JA), [
                         (cfg(handover=3), [macc(BPH, "cfg")], ms([], J)),
                         ({"advance": 300}, [], ms([], J)),
                         (hd("b1", 1, HUB_B), [expired([1, 2, 3]), err(HUB_B, "b1", "policy.blocked")], ms([], J)),
                         (hd("b4", 4, HUB_B), [macc(HUB_B, "b4", c(1))], ms([c(1)], J)),
                     ]))
    out.append(trace("mailbox-hub-deposit-redelivered-after-re-registration-carries-the-retained-cursor",
                     "A group left and registered again, at another hub, is the same group with the same numbering: a redelivery of "
                     "a seq the mailbox still retains from before is a duplicate with that item's cursor (spec-gap 92).",
                     mrefs + ["M§6.6", "M§5.4"], T, mbx_ctx(groups=JA), [
                         (hd("h2", 2, HUB_A), [macc(HUB_A, "h2", c(1))], ms([c(1)], J)),
                         ({"config": {"id": uid("left"), "device": BPH, "groups": [{"group": GROUP, "state": "left"}]}},
                          [macc(BPH, "left")], ms([c(1)])),
                         (cfg("rejoin", handover=None), [macc(BPH, "rejoin")], ms([c(1)], J)),
                         (hd("b3", 3, HUB_B), [macc(HUB_B, "b3", c(2))], ms([c(1), c(2)], J)),
                         (hd("b2", 2, HUB_B), [macc(HUB_B, "b2", c(1), dup=True)], ms([c(1), c(2)], J)),
                     ]))
    out.append(trace("mailbox-hub-deposit-redelivery-cursor-is-never-an-archive-records",
                     "An archive record shares the group's seq space (its ref_seq) but is not the hub's item: a redelivery's cursor "
                     "is the stored hub item's, whatever was stored first (spec-gap 92).", mrefs + ["M§6.6", "M§12.2"], T,
                     mbx_ctx(groups=JA), [
                         ({"archive": {"id": uid("ar2"), "device": BPH, "ref_group": GROUP, "ref_seq": 2}}, [macc(BPH, "ar2", c(1))],
                          ms([c(1)], J)),
                         (hd("h2", 2, HUB_A), [macc(HUB_A, "h2", c(2))], ms([c(1), c(2)], J)),
                         (hd("h2-r", 2, HUB_A), [macc(HUB_A, "h2-r", c(2), dup=True)], ms([c(1), c(2)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-old-hub-item-below-the-highest-stored-is-a-redelivery",
                     "The move was named with nothing missing (the highest stored is past handover_seq), so the new hub is admitted "
                     "at once and nothing was given up on: what the old hub then delivers at or below the highest stored is a "
                     "redelivery like any other (spec-gap 59) — only an expired wait makes such an item a fill to store (spec-gap 71, "
                     "spec-gap 93).", xrefs, T, mbx_ctx(groups=JA), [
                         (hd("h5", 5, HUB_A), [macc(HUB_A, "h5", c(1))], ms([c(1)], J)),
                         (cfg(handover=3), [macc(BPH, "cfg")], ms([c(1)], J)),
                         (hd("b2", 2, HUB_B), [err(HUB_B, "b2", "policy.blocked")], ms([c(1)], J)),
                         (hd("h3", 3, HUB_A), [macc(HUB_A, "h3", dup=True)], ms([c(1)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-nothing-missing-once-the-highest-stored-reaches-handover-seq",
                     "What the old hub still owes is judged by the highest seq stored — it delivers in order (M§6.5 rule 5), so a "
                     "stored seq says every lower one came before it. Once the highest stored reaches handover_seq the new hub is "
                     "admitted at once, its GroupInfo included (spec-gap 95).", xrefs, T, mbx_ctx(groups=JA), [
                         (hd("h1", 1, HUB_A), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (cfg(handover=3), [macc(BPH, "cfg")], ms([c(1)], J)),
                         (hd("h3", 3, HUB_A), [macc(HUB_A, "h3", c(2))], ms([c(1), c(2)], J)),
                         (hd("gi", None, HUB_B, cls="group-info"), [macc(HUB_B, "gi", c(3))], ms([c(1), c(2), c(3)], J)),
                         (hd("b4", 4, HUB_B), [macc(HUB_B, "b4", c(4))], ms([c(1), c(2), c(3), c(4)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-handover-wait-configurable",
                     "handover_wait is the mailbox's own choice (300 s RECOMMENDED); the wait starts at the config naming the new hub.",
                     xrefs, T, mbx_ctx(groups=JA, handover_wait=30), [
                         (cfg(handover=1), [macc(BPH, "cfg")], ms([], J)),
                         (hd("b2", 2, HUB_B), [err(HUB_B, "b2", "mailbox.unknown-group")], ms([], J)),
                         ({"advance": 30}, [], ms([], J)),
                         (hd("b2-r", 2, HUB_B), [expired([1]), macc(HUB_B, "b2-r", c(1))], ms([c(1)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-late-previous-items-stored",
                     "What the old hub still delivers after the wait, at or below handover_seq, is stored rather than taken for "
                     "a redelivery (the owner's devices fill their gap with it); what was stored before is a duplicate, and above "
                     "handover_seq the old hub is refused as before.", xrefs, T, mbx_ctx(groups=JA), [
                         (hd("h1", 1, HUB_A), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (cfg(handover=3), [macc(BPH, "cfg")], ms([c(1)], J)),
                         ({"advance": 300}, [], ms([c(1)], J)),
                         (hd("b4", 4, HUB_B), [expired([2, 3]), macc(HUB_B, "b4", c(2))], ms([c(1), c(2)], J)),
                         (hd("h2", 2, HUB_A), [macc(HUB_A, "h2", c(3))], ms([c(1), c(2), c(3)], J)),
                         (hd("h2-retry", 2, HUB_A), [macc(HUB_A, "h2-retry", c(3), dup=True)], ms([c(1), c(2), c(3)], J)),
                         (hd("h1-retry", 1, HUB_A), [macc(HUB_A, "h1-retry", c(1), dup=True)], ms([c(1), c(2), c(3)], J)),
                         (hd("h3", 3, HUB_A, "handshake"), [macc(HUB_A, "h3", c(4))], ms([c(1), c(2), c(3), c(4)], J)),
                         (hd("h4", 4, HUB_A), [err(HUB_A, "h4", "mailbox.unknown-group")], ms([c(1), c(2), c(3), c(4)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-handover-wait-survives-restart",
                     "The wait is measured from the config that named the new hub and is durable: a restart (spec-gap 59) "
                     "neither resets nor ends it.", xrefs + ["M§6.6"], T, mbx_ctx(groups=JA), [
                         (cfg(handover=1), [macc(BPH, "cfg")], ms([], J)),
                         ({"advance": 100}, [], ms([], J)),
                         ({"restart": {}}, [], ms([], J)),
                         (hd("b2", 2, HUB_B), [err(HUB_B, "b2", "mailbox.unknown-group")], ms([], J)),
                         ({"advance": 200}, [], ms([], J)),
                         (hd("b2-r", 2, HUB_B), [expired([1]), macc(HUB_B, "b2-r", c(1))], ms([c(1)], J)),
                     ]))
    out.append(trace("mailbox-hub-move-new-hub-renumbering-refused",
                     "A new hub whose numbering does not continue past handover_seq (a wrong handover) is refused policy.blocked "
                     "rather than having its items taken for redeliveries and silently dropped.", mrefs + ["M§6.5"], T,
                     mbx_ctx(groups=JA), [
                         (hd("h1", 1, HUB_A), [macc(HUB_A, "h1", c(1))], ms([c(1)], J)),
                         (hd("h2", 2, HUB_A, "handshake"), [macc(HUB_A, "h2", c(2))], ms([c(1), c(2)], J)),
                         (cfg(), [macc(BPH, "cfg")], ms([c(1), c(2)], J)),
                         (hd("b1", 1, HUB_B), [err(HUB_B, "b1", "policy.blocked")], ms([c(1), c(2)], J)),
                         (hd("b2", 2, HUB_B), [err(HUB_B, "b2", "policy.blocked")], ms([c(1), c(2)], J)),
                     ]))

    # --- a device whose deposit reaches the old hub
    ctx = {"component": "commit-retry", "max_attempts": 3}
    retry = [{"discard": {}}, {"sync": {}}]
    out.append(trace("commit-retry-unknown-group-hub-moved",
                     "A deposit refused mailbox.unknown-group by a hub the group has left: the device syncs, processes the move, "
                     "and re-proposes to the new hub.", ["M§7.4", "M§6.5"], "commit-retry-trace", ctx, [
                         ({"answer": {"reason": "mailbox.unknown-group"}}, retry, {"attempt": 1, "state": "syncing"}),
                         ({"synced": {"still_needed": True, "hub_moved": True}}, [{"repropose": {"attempt": 2}}], {"attempt": 2, "state": "pending"}),
                         ({"answer": {}}, [{"merge": {}}], {"attempt": 2, "state": "merged"}),
                     ]))
    out.append(trace("commit-retry-unknown-group-not-moved-surfaces",
                     "If the sync shows no move, mailbox.unknown-group is final and surfaced.", ["M§7.4", "M§6.6"],
                     "commit-retry-trace", ctx, [
                         ({"answer": {"reason": "mailbox.unknown-group"}}, retry, {"attempt": 1, "state": "syncing"}),
                         ({"synced": {"still_needed": True, "hub_moved": False}}, [{"surface": "mailbox.unknown-group"}],
                          {"attempt": 1, "state": "surfaced"}),
                     ]))

    # --- what the moving commit may change
    before = {"conversation": CONV, "kind": "group", "hub": {"did": HUB_A, "uri": "wss://mbx.alice.example/dsip"}, "successor_of": None}
    newhub = {"did": HUB_B, "uri": "wss://mbx.bob.example/dsip"}

    def cu(vid, desc, after, expect):
        out.append(mv(vid, desc, ["M§6.3", "M§7.4"], {"check": "conversation-update", "before": before, "after": after}, expect))
    cu("conversation-update-hub-move", "A GroupContextExtensions commit replacing the hub moves the group.",
       {**before, "hub": newhub}, accept(effective={"moves_to": HUB_B, "hub": newhub}))
    cu("conversation-update-hub-endpoint-only", "The same hub at a new endpoint is not a move; members use the new uri.",
       {**before, "hub": {"did": HUB_A, "uri": "wss://mbx2.alice.example/dsip"}},
       accept(effective={"moves_to": None, "hub": {"did": HUB_A, "uri": "wss://mbx2.alice.example/dsip"}}))
    cu("conversation-update-conversation-change-refused", "The conversation ULID is stable for the conversation's life (M§6.3).",
       {**before, "hub": newhub, "conversation": uid("other-conversation")}, reject("conversation-immutable"))
    cu("conversation-update-kind-change-refused", "A group does not change kind: a direct conversation stays direct.",
       {**before, "kind": "direct"}, reject("conversation-immutable"))
    cu("conversation-update-successor-change-refused", "successor_of is fixed when a group is created (M§7.5).",
       {**before, "successor_of": GROUP2}, reject("conversation-immutable"))

    # --- the wire fields
    def m(vid, desc, payload, expect):
        out.append(mv(vid, desc, ["M§7.4", "M§5.2"], {"check": "message", "payload": payload}, expect))
    m("deposit-group-info-handover-seq-valid", "The committer bootstraps the new hub with the latest GroupInfo and the moving commit's seq.",
      deposit(cls="group-info", handover_seq=7), accept())
    m("deposit-application-handover-seq-refused", "handover_seq belongs to a group-info deposit only.",
      deposit(handover_seq=7), reject("deposit-fields"))
    m("mailbox-config-hub-move-valid", "An owner device names the group's new hub, its endpoint and the moving commit's seq.",
      msg("mailbox-config", "cfgm", BPH, MBX_B, subject=BOB,
          groups=[{"group": GROUP, "hub": HUB_B, "hub_uri": "wss://mbx.bob.example/dsip", "handover_seq": 7, "state": "joined"}]), accept())
    m("mailbox-config-handover-seq-zero-refused", "A seq starts at 1.",
      msg("mailbox-config", "cfgz", BPH, MBX_B, subject=BOB,
          groups=[{"group": GROUP, "hub": HUB_B, "handover_seq": 0, "state": "joined"}]), reject("schema-invalid"))
    return out


# ---------------------------------------------------------------- a member arriving at the new hub first (M§7.4; spec-gap 129)

def move_arrival_vectors():
    out = []
    T = "move-arrival-trace"
    refs = ["M§7.4", "§13.2"]
    ctx = {"component": "move-arrival", "now": NOW}
    HUB_B, HUB_C = "did:web:mbx.bob.example", "did:web:mbx.carol.example"

    def snap(state, hub=None, attempt=0, waited=None):
        return {"state": state, "hub": hub, "attempt": attempt, "waited": waited}

    def moved(hub):
        return {"moved": {"hub": hub}}

    def unknown(hub):
        return {"answer": {"hub": hub, "reason": "mailbox.unknown-group"}}

    def accepted(hub):
        return {"answer": {"hub": hub}}

    out.append(trace("move-arrival-new-hub-retried-until-it-hosts",
                     "A member that processed the move can reach the new hub before the committer's group-info has set it up: "
                     "the new hub's mailbox.unknown-group is then not final. The same deposit is retried with the §13.2 backoff "
                     "until the hub accepts one. From then on the hub hosts the group, and a later mailbox.unknown-group from it "
                     "is handled as M§7.4 says (sync; final unless the group moved). A move back to a hub the group left "
                     "(spec-gap 128) is an arrival like any other.", refs + ["M§9.3"], T, ctx, [
                         (moved(HUB_B), [], snap("arriving", HUB_B, 0, 0)),
                         (unknown(HUB_B), [{"retry_in": 1}], snap("arriving", HUB_B, 1, 0)),
                         ({"advance": 1}, [], snap("arriving", HUB_B, 1, 1)),
                         (unknown(HUB_B), [{"retry_in": 2}], snap("arriving", HUB_B, 2, 1)),
                         ({"advance": 2}, [], snap("arriving", HUB_B, 2, 3)),
                         (accepted(HUB_B), [], snap("hosted", HUB_B, 2, 3)),
                         (unknown(HUB_B), [], snap("hosted", HUB_B, 2, 3)),
                         (moved(HUB_A), [], snap("arriving", HUB_A, 0, 0)),
                         (unknown(HUB_A), [{"retry_in": 1}], snap("arriving", HUB_A, 1, 0)),
                     ]))
    out.append(trace("move-arrival-wait-expires",
                     "The new hub is waited for at most arrival_wait from the move (300 s, as handover_wait). A retry scheduled "
                     "inside the wait still goes; the first mailbox.unknown-group at or past the bound ends the wait, once, and "
                     "the refusal is handled as M§7.4 says. A committer that never set the hub up leaves the group to M§7.5.",
                     refs + ["M§7.5"], T, {**ctx, "arrival_wait": 10}, [
                         (moved(HUB_B), [], snap("arriving", HUB_B, 0, 0)),
                         (unknown(HUB_B), [{"retry_in": 1}], snap("arriving", HUB_B, 1, 0)),
                         ({"advance": 1}, [], snap("arriving", HUB_B, 1, 1)),
                         (unknown(HUB_B), [{"retry_in": 2}], snap("arriving", HUB_B, 2, 1)),
                         ({"advance": 2}, [], snap("arriving", HUB_B, 2, 3)),
                         (unknown(HUB_B), [{"retry_in": 4}], snap("arriving", HUB_B, 3, 3)),
                         ({"advance": 4}, [], snap("arriving", HUB_B, 3, 7)),
                         (unknown(HUB_B), [{"retry_in": 8}], snap("arriving", HUB_B, 4, 7)),
                         ({"advance": 2}, [], snap("arriving", HUB_B, 4, 9)),
                         (unknown(HUB_B), [{"retry_in": 16}], snap("arriving", HUB_B, 5, 9)),
                         ({"advance": 16}, [], snap("arriving", HUB_B, 5, 25)),
                         (unknown(HUB_B), [{"expired": {}}], snap("expired", HUB_B, 5, 25)),
                         ({"advance": 5}, [], snap("expired", HUB_B, 5, 30)),
                         (unknown(HUB_B), [], snap("expired", HUB_B, 5, 30)),
                         (accepted(HUB_B), [], snap("expired", HUB_B, 5, 30)),
                     ]))
    out.append(trace("move-arrival-backoff-ceiling-and-default-wait",
                     "The backoff doubles to the 60 s ceiling; with the default wait of 300 s, the retry that lands at 303 s "
                     "ends it.", refs, T, ctx, [
                         (moved(HUB_B), [], snap("arriving", HUB_B, 0, 0)),
                         *[step for n, (d, w) in enumerate([(1, 0), (2, 1), (4, 3), (8, 7), (16, 15), (32, 31), (60, 63),
                                                            (60, 123), (60, 183), (60, 243)], start=1)
                           for step in ((unknown(HUB_B), [{"retry_in": d}], snap("arriving", HUB_B, n, w)),
                                        ({"advance": d}, [], snap("arriving", HUB_B, n, w + d)))],
                         (unknown(HUB_B), [{"expired": {}}], snap("expired", HUB_B, 10, 303)),
                     ]))
    out.append(trace("move-arrival-old-hub-is-not-an-arrival",
                     "mailbox.unknown-group from any hub but the one the group moved to is the ordinary M§7.4 case (a member "
                     "that missed the move): nothing to wait for. Its answers leave the wait as it was.", refs, T, ctx, [
                         (moved(HUB_B), [], snap("arriving", HUB_B, 0, 0)),
                         (unknown(HUB_A), [], snap("arriving", HUB_B, 0, 0)),
                         (accepted(HUB_A), [], snap("arriving", HUB_B, 0, 0)),
                         (unknown(HUB_B), [{"retry_in": 1}], snap("arriving", HUB_B, 1, 0)),
                     ]))
    out.append(trace("move-arrival-other-answers-keep-waiting",
                     "Only an accepted shows the new hub hosts the group. Its other refusals are handled as usual (an outage as "
                     "M§9.4, a refusal of the item as M§6.5) and leave the wait open.", refs + ["M§9.4"], T, ctx, [
                         (moved(HUB_B), [], snap("arriving", HUB_B, 0, 0)),
                         ({"answer": {"hub": HUB_B, "reason": "policy.blocked"}}, [], snap("arriving", HUB_B, 0, 0)),
                         ({"answer": {"hub": HUB_B, "reason": "mailbox.hub-unreachable"}}, [], snap("arriving", HUB_B, 0, 0)),
                         (unknown(HUB_B), [{"retry_in": 1}], snap("arriving", HUB_B, 1, 0)),
                     ]))
    out.append(trace("move-arrival-another-move-restarts",
                     "A later move replaces the wait: the hub the group moved on from is no longer waited for, and the backoff "
                     "and the bound start afresh for the new one.", refs, T, ctx, [
                         (moved(HUB_B), [], snap("arriving", HUB_B, 0, 0)),
                         (unknown(HUB_B), [{"retry_in": 1}], snap("arriving", HUB_B, 1, 0)),
                         ({"advance": 5}, [], snap("arriving", HUB_B, 1, 5)),
                         (moved(HUB_C), [], snap("arriving", HUB_C, 0, 0)),
                         (unknown(HUB_B), [], snap("arriving", HUB_C, 0, 0)),
                         (unknown(HUB_C), [{"retry_in": 1}], snap("arriving", HUB_C, 1, 0)),
                     ]))
    out.append(trace("move-arrival-no-move-no-wait",
                     "Before any move there is nothing to wait for: mailbox.unknown-group is handled as M§7.4 says.", refs, T, ctx, [
                         (unknown(HUB_A), [], snap("none")),
                         ({"advance": 10}, [], snap("none")),
                         (accepted(HUB_A), [], snap("none")),
                     ]))
    return out


# ---------------------------------------------------------------- whom a mailbox serves, and when that ends (M§4.1; spec-gap 130)

def enrolment_vectors():
    out = []
    T = "enrolment-trace"
    refs = ["M§4.1"]
    ctx = {"component": "enrolment", "now": NOW, "configured": [ALICE], "serve_any": 2}

    def snap(*enrolled, free):
        return {"enrolled": list(enrolled), "free": free}

    def op(identity, device, label):
        return {"owner_op": {"identity": identity, "device": device, "id": uid(label)}}

    def release(identity, device, label):
        return {"release": {"identity": identity, "device": device, "id": uid(label)}}

    def refused(device, label, reason):
        return [{"error": {"to": device, "in_reply_to": uid(label), "reason": reason}}]

    def enrolled(identity):
        return [{"enrolled": {"identity": identity}}]

    def released(identity, cause):
        return {"released": {"identity": identity, "cause": cause}}

    # --- the bound (spec-gap 115) and the refusal at it (spec-gap 130)
    out.append(trace("enrolment-within-bound-then-not-served",
                     "A configured identity is served and does not count against the bound. Others enrol with their first "
                     "owner operation while the bound has room; once it is reached, an owner operation from an identity the "
                     "mailbox does not serve is refused mailbox.not-served (v0.16). A verified hello alone enrols nothing.",
                     refs + ["M§16"], T, ctx, [
                         (op(ALICE, APH, "e1"), [], snap(free=2)),
                         (op(BOB, BPH, "e2"), enrolled(BOB), snap(BOB, free=1)),
                         (op(BOB, BLA, "e3"), [], snap(BOB, free=1)),
                         (op(CAROL, CPH, "e4"), enrolled(CAROL), snap(BOB, CAROL, free=0)),
                         (op(MALLORY, MPH, "e5"), refused(MPH, "e5", "mailbox.not-served"), snap(BOB, CAROL, free=0)),
                         ({"hello": {"identity": MALLORY}}, [], snap(BOB, CAROL, free=0)),
                         (op(ALICE, ALA, "e6"), [], snap(BOB, CAROL, free=0)),
                     ]))
    out.append(trace("enrolment-closed-refuses",
                     "A mailbox that enrols no one (no bound) serves its configured identities only: any other identity's "
                     "owner operation is refused mailbox.not-served.", refs + ["M§16"], T,
                     {"component": "enrolment", "now": NOW, "configured": [ALICE]}, [
                         (op(BOB, BPH, "c1"), refused(BPH, "c1", "mailbox.not-served"), snap(free=0)),
                         (op(ALICE, APH, "c2"), [], snap(free=0)),
                     ]))

    # --- release
    out.append(trace("enrolment-release-frees-the-place",
                     "mailbox-config release: true is answered accepted, then the enrolment ends: everything held for the "
                     "identity is deleted (released) and its place is free for the next identity. A released identity is "
                     "not served; it enrols afresh, with nothing kept, only while the bound has room.",
                     refs + ["M§5.7"], T, {**ctx, "serve_any": 1}, [
                         (op(BOB, BPH, "r1"), enrolled(BOB), snap(BOB, free=0)),
                         (op(CAROL, CPH, "r2"), refused(CPH, "r2", "mailbox.not-served"), snap(BOB, free=0)),
                         (release(BOB, BPH, "r3"), [{"accepted": {"to": BPH, "in_reply_to": uid("r3")}}, released(BOB, "owner")],
                          snap(free=1)),
                         (op(CAROL, CPH, "r4"), enrolled(CAROL), snap(CAROL, free=0)),
                         (op(BOB, BPH, "r5"), refused(BPH, "r5", "mailbox.not-served"), snap(CAROL, free=0)),
                         (release(CAROL, CPH, "r6"), [{"accepted": {"to": CPH, "in_reply_to": uid("r6")}}, released(CAROL, "owner")],
                          snap(free=1)),
                         (op(BOB, BLA, "r7"), enrolled(BOB), snap(BOB, free=0)),
                     ]))
    out.append(trace("enrolment-release-configured-refused",
                     "A configured identity cannot release itself: refused mailbox.not-enrolled, nothing changes, and it "
                     "is still served. Its operator ends it.", refs + ["M§5.7", "M§16"], T, ctx, [
                         (op(BOB, BPH, "k1"), enrolled(BOB), snap(BOB, free=1)),
                         (release(ALICE, APH, "k2"), refused(APH, "k2", "mailbox.not-enrolled"), snap(BOB, free=1)),
                         (op(ALICE, APH, "k3"), [], snap(BOB, free=1)),
                     ]))
    out.append(trace("enrolment-release-unserved-refused",
                     "A release from an identity the mailbox does not serve is refused mailbox.not-served, even with room in "
                     "the bound: a release never enrols.", refs + ["M§5.7", "M§16"], T, ctx, [
                         (release(BOB, BPH, "u1"), refused(BPH, "u1", "mailbox.not-served"), snap(free=2)),
                         (op(BOB, BPH, "u2"), enrolled(BOB), snap(BOB, free=1)),
                     ]))

    # --- by its operator (spec-gap 164)
    def ended(identity):
        return {"operator_release": {"identity": identity}}

    out.append(trace("enrolment-operator-ends-an-enrolment",
                     "The operator MAY end an enrolment (1.0, spec-gap 164), with the same effects as a release: everything "
                     "held for the identity is deleted and its place freed (released, cause operator). No message is sent: "
                     "its devices see their bindings close. A later owner operation enrols afresh while the bound has room.",
                     refs, T, {**ctx, "serve_any": 1}, [
                         (op(BOB, BPH, "x1"), enrolled(BOB), snap(BOB, free=0)),
                         (op(CAROL, CPH, "x2"), refused(CPH, "x2", "mailbox.not-served"), snap(BOB, free=0)),
                         (ended(BOB), [released(BOB, "operator")], snap(free=1)),
                         (op(CAROL, CPH, "x3"), enrolled(CAROL), snap(CAROL, free=0)),
                         (op(BOB, BLA, "x4"), refused(BLA, "x4", "mailbox.not-served"), snap(CAROL, free=0)),
                     ]))
    out.append(trace("enrolment-operator-end-spares-configured-and-unserved",
                     "Only an enrolment is ended by the operator (spec-gap 164): for a configured identity (the operator "
                     "removes it from the configuration instead) or one the mailbox does not serve, nothing is emitted and "
                     "nothing changes. Ending an enrolment twice ends it once.",
                     refs, T, ctx, [
                         (op(BOB, BPH, "y1"), enrolled(BOB), snap(BOB, free=1)),
                         (ended(ALICE), [], snap(BOB, free=1)),
                         (op(ALICE, APH, "y2"), [], snap(BOB, free=1)),
                         (ended(CAROL), [], snap(BOB, free=1)),
                         (ended(BOB), [released(BOB, "operator")], snap(free=2)),
                         (ended(BOB), [], snap(free=2)),
                     ]))

    # --- idle expiry (MAY: context.expire_idle)
    idle = {**ctx, "expire_idle": True, "mls_retention_s": 100}
    out.append(trace("enrolment-idle-expiry-at-the-bound",
                     "With idle expiry on, an enrolled identity whose last verified hello (its enrolment counts as one) is "
                     "more than mls_retention_s old has no registered device (M§4.4), and its enrolment ends. At exactly "
                     "mls_retention_s the device is still registered. The identity enrols afresh on its next owner operation.",
                     refs + ["M§4.4"], T, idle, [
                         (op(BOB, BPH, "i1"), enrolled(BOB), snap(BOB, free=1)),
                         ({"advance": 100}, [], snap(BOB, free=1)),
                         ({"advance": 1}, [released(BOB, "idle")], snap(free=2)),
                         (op(BOB, BPH, "i2"), enrolled(BOB), snap(BOB, free=1)),
                     ]))
    out.append(trace("enrolment-hello-keeps-the-enrolment",
                     "Each verified hello of a device of the identity restarts its registration (M§4.4). Two identities that "
                     "enrolled together expire apart: the one with a later hello later. Expiries at one advance are emitted "
                     "in enrolment order.",
                     refs + ["M§4.4"], T, {**idle, "serve_any": 3}, [
                         (op(BOB, BPH, "h1"), enrolled(BOB), snap(BOB, free=2)),
                         (op(CAROL, CPH, "h2"), enrolled(CAROL), snap(BOB, CAROL, free=1)),
                         (op(MALLORY, MPH, "h3"), enrolled(MALLORY), snap(BOB, CAROL, MALLORY, free=0)),
                         ({"advance": 60}, [], snap(BOB, CAROL, MALLORY, free=0)),
                         ({"hello": {"identity": BOB}}, [], snap(BOB, CAROL, MALLORY, free=0)),
                         ({"advance": 41}, [released(CAROL, "idle"), released(MALLORY, "idle")], snap(BOB, free=2)),
                         ({"advance": 59}, [], snap(BOB, free=2)),
                         ({"advance": 1}, [released(BOB, "idle")], snap(free=3)),
                     ]))
    out.append(trace("enrolment-owner-operation-is-not-a-hello",
                     "Only a verified hello registers a device again (M§4.4). An owner operation of an enrolled identity is "
                     "made on a binding whose hello already counted; on its own it does not keep the enrolment alive.",
                     refs + ["M§4.4"], T, idle, [
                         (op(BOB, BPH, "n1"), enrolled(BOB), snap(BOB, free=1)),
                         ({"advance": 90}, [], snap(BOB, free=1)),
                         (op(BOB, BPH, "n2"), [], snap(BOB, free=1)),
                         ({"advance": 11}, [released(BOB, "idle")], snap(free=2)),
                     ]))
    out.append(trace("enrolment-idle-expiry-is-the-operators-choice",
                     "Idle expiry is a MAY (context.expire_idle, default false): without it an enrolment lasts until it is "
                     "released, however long its devices stay away.", refs + ["M§4.4"], T,
                     {**ctx, "mls_retention_s": 100}, [
                         (op(BOB, BPH, "o1"), enrolled(BOB), snap(BOB, free=1)),
                         ({"advance": 100000}, [], snap(BOB, free=1)),
                     ]))
    out.append(trace("enrolment-idle-expiry-spares-configured",
                     "A configured identity never expires: only enrolled ones are released for idleness.", refs + ["M§4.4"],
                     T, idle, [
                         (op(ALICE, APH, "s1"), [], snap(free=2)),
                         (op(BOB, BPH, "s2"), enrolled(BOB), snap(BOB, free=1)),
                         ({"hello": {"identity": ALICE}}, [], snap(BOB, free=1)),
                         ({"advance": 1000}, [released(BOB, "idle")], snap(free=2)),
                         (op(ALICE, APH, "s3"), [], snap(free=2)),
                     ]))
    out.append(trace("enrolment-idle-expiry-default-retention",
                     "mls_retention_s defaults to 2,592,000 s (30 days, M§4.4 RECOMMENDED).", refs + ["M§4.4"], T,
                     {**ctx, "expire_idle": True}, [
                         (op(BOB, BPH, "d1"), enrolled(BOB), snap(BOB, free=1)),
                         ({"advance": 2592000}, [], snap(BOB, free=1)),
                         ({"advance": 1}, [released(BOB, "idle")], snap(free=2)),
                     ]))

    # --- the wire field (M§5.7)
    def m(vid, desc, payload, expect):
        out.append(mv(vid, desc, ["M§5.7", "M§4.1"], {"check": "message", "payload": payload}, expect))
    m("mailbox-config-release-valid", "An owner device releases its identity's enrolment (v0.16, spec-gap 130).",
      msg("mailbox-config", "cfgrel", BPH, MBX_B, subject=BOB, release=True), accept())
    m("mailbox-config-release-not-boolean-refused", "release is a boolean.",
      msg("mailbox-config", "cfgrel2", BPH, MBX_B, subject=BOB, release="yes"), reject("schema-invalid"))
    return out


# ---------------------------------------------------------------- successor groups when the hub is gone (M§7.5; spec-gap 61)

def successor_vectors():
    out = []
    T = "successor-trace"
    refs = ["M§7.5"]
    EARLY = b64url_encode(uid("successor-early", NOW).encode())
    LATE = b64url_encode(uid("successor-late", NOW + 5).encode())
    LATER = b64url_encode(uid("successor-later", NOW + 9).encode())
    ROSTER = [ALICE, BOB, CAROL]
    ctx = {"component": "successor", "groups": {GROUP: ROSTER}}
    wel = lambda g, creator=BOB, roster=ROSTER, pred=GROUP: {"welcome": {"group": g, "successor_of": pred, "creator": creator, "roster": roster}}
    st = lambda succ, cands: {GROUP: {"successor": succ, "candidates": sorted(cands)}}

    out.append(trace("successor-valid-joined", "A predecessor member's successor re-adding predecessor members is joined.", refs, T, ctx, [
        (wel(LATE), [{"join": LATE}], st(LATE, [LATE])),
    ]))
    out.append(trace("successor-invalid-is-first-contact",
                     "A successor adding an outsider, or created by one, is a new conversation under first contact, not a successor.",
                     refs + ["M§14"], T, ctx, [
                         (wel(LATE, roster=[ALICE, BOB, MALLORY]), [{"first_contact": LATE}], {}),
                         (wel(EARLY, creator=MALLORY, roster=[ALICE, MALLORY]), [{"first_contact": EARLY}], {}),
                     ]))
    out.append(trace("successor-of-unknown-group-is-first-contact",
                     "A device that was never in the named predecessor cannot check the successor: first contact.", refs + ["M§14"], T,
                     {"component": "successor", "groups": {}}, [
                         (wel(LATE), [{"first_contact": LATE}], {}),
                     ]))
    out.append(trace("successor-lower-arrives-later-switches",
                     "Concurrent successors: a lower group_id arriving after the device joined a higher one wins; the device joins it "
                     "and leaves the other.", refs, T, ctx, [
                         (wel(LATE, creator=CAROL), [{"join": LATE}], st(LATE, [LATE])),
                         (wel(EARLY), [{"join": EARLY}, {"leave": LATE}], st(EARLY, [EARLY, LATE])),
                     ]))
    out.append(trace("successor-higher-arrives-later-declined",
                     "A higher group_id arriving after the winner is declined: never joined.", refs, T, ctx, [
                         (wel(EARLY), [{"join": EARLY}], st(EARLY, [EARLY])),
                         (wel(LATER, creator=CAROL), [{"decline": LATER}], st(EARLY, [EARLY, LATER])),
                     ]))
    out.append(trace("successor-create-when-one-exists-uses-it",
                     "Asked to create a successor for a group that already has one, the device uses the existing one.", refs, T, ctx, [
                         (wel(LATE), [{"join": LATE}], st(LATE, [LATE])),
                         ({"create": {"predecessor": GROUP}}, [{"use": LATE}], st(LATE, [LATE])),
                     ]))
    out.append(trace("successor-own-loses-to-concurrent",
                     "Two members create successors at once: the creator whose group_id is higher leaves its own group for the lower.",
                     refs, T, ctx, [
                         ({"create": {"predecessor": GROUP}}, [{"create": {"successor_of": GROUP, "roster": sorted(ROSTER)}}], {}),
                         ({"created": {"group": LATE, "successor_of": GROUP}}, [], st(LATE, [LATE])),
                         (wel(EARLY), [{"join": EARLY}, {"leave": LATE}], st(EARLY, [EARLY, LATE])),
                     ]))
    out.append(trace("successor-own-created-after-joining-a-lower-one-is-left",
                     "A device that created a successor while a lower one it had already joined exists leaves its own: it stays in "
                     "only the lowest, created or not.", refs, T, ctx, [
                         (wel(EARLY), [{"join": EARLY}], st(EARLY, [EARLY])),
                         ({"created": {"group": LATE, "successor_of": GROUP}}, [{"leave": LATE}], st(EARLY, [EARLY, LATE])),
                     ]))
    out.append(trace("successor-own-wins-over-concurrent",
                     "...and the creator whose group_id is lower keeps its group and declines the other.", refs, T, ctx, [
                         ({"create": {"predecessor": GROUP}}, [{"create": {"successor_of": GROUP, "roster": sorted(ROSTER)}}], {}),
                         ({"created": {"group": EARLY, "successor_of": GROUP}}, [], st(EARLY, [EARLY])),
                         (wel(LATE, creator=CAROL), [{"decline": LATE}], st(EARLY, [EARLY, LATE])),
                     ]))
    out.append(trace("successor-create-not-a-member-refused", "Only a member of the predecessor creates its successor.", refs, T,
                     {"component": "successor", "groups": {}}, [
                         ({"create": {"predecessor": GROUP}}, [{"refuse": "not-a-member"}], {}),
                     ]))

    # the fetch that lets a creator re-add members it holds no grant from
    M = "mailbox-trace"
    fetch = lambda label, succ=None, grant_=None: {"kp_fetch": {"id": uid(label), "from": CPH, "from_identity": CAROL, "target": BOB,
                                                              "grant": grant_, **({"successor_of": succ} if succ else {})}}
    KP = {BPH: {"one_time": 2, "last_resort": False}}
    out.append(trace("mailbox-key-packages-for-successor",
                     "A KeyPackage fetch naming a group registered for the owner as successor_of is served without a grant (spec-gap 61), "
                     "as the successor's welcome will be admitted; an unregistered one is not.", refs + ["M§5.5", "M§14.2"], M,
                     mbx_ctx(key_packages=KP, groups={GROUP: {"hub": HUB_A, "state": "joined"}}), [
                         (fetch("f1"), [err(CPH, "f1", "policy.first-contact-required")],
                          ms(groups={GROUP: "joined"}, kps={BPH: {"one_time": 2, "last_resort": False}})),
                         (fetch("f2", succ=GROUP2), [err(CPH, "f2", "policy.first-contact-required")],
                          ms(groups={GROUP: "joined"}, kps={BPH: {"one_time": 2, "last_resort": False}})),
                         (fetch("f3", succ=GROUP), [{"key_packages": {"to": CPH, "in_reply_to": uid("f3"), "devices": {BPH: "one-time"}}}],
                          ms(groups={GROUP: "joined"}, kps={BPH: {"one_time": 1, "last_resort": False}})),
                     ]))
    out.append(mv("key-package-fetch-successor-valid", "A fetch for a successor names the dead group.", refs + ["M§5.5"],
                  {"check": "message", "payload": msg("key-package-fetch", "kps", CPH, MBX_B, target=BOB, successor_of=GROUP)}, accept()))
    return out


# ---------------------------------------------------------------- external joins (M§6.8; spec-gap 62)

def external_join_vectors():
    out = []
    refs = ["M§6.8"]
    BTAB2 = "did:key:z6MkBobTabletTwoTwoTwoTwoTwoTwoTwoTwoTwoTwoTwo"
    base = {"kind": "direct", "roster": [ALICE, BOB]}

    def xj(vid, desc, inp, expect, extra=()):
        out.append(mv(vid, desc, refs + list(extra), {"check": "external-join", **inp}, expect))
    xj("external-join-new-device-of-member", "A new device of a member identity joins with no removal (its siblings may be alive).",
       {**base, "joiner": {"identity": BOB, "device": BTAB}, "adds": [{"identity": BOB, "device": BTAB}], "removes": []}, accept())
    xj("external-join-returning-device-replaces-own-leaf",
       "A device that lost its group state rejoins and removes its own stale leaf (same device, MLS resync).",
       {**base, "joiner": {"identity": BOB, "device": BPH}, "adds": [{"identity": BOB, "device": BPH}],
        "removes": [{"identity": BOB, "device": BPH}]}, accept())
    xj("external-join-removes-own-identity-stale-device", "It may remove another stale leaf of its own identity.",
       {**base, "joiner": {"identity": BOB, "device": BTAB}, "adds": [{"identity": BOB, "device": BTAB}],
        "removes": [{"identity": BOB, "device": BPH}]}, accept())
    xj("external-join-stranger-refused", "An identity with no leaf in the group may not join by external commit.",
       {**base, "joiner": {"identity": CAROL, "device": CPH}, "adds": [{"identity": CAROL, "device": CPH}], "removes": []},
       reject("external-join-not-member"))
    xj("external-join-removes-other-identity-refused", "An external joiner may not remove another identity's leaf.",
       {**base, "joiner": {"identity": BOB, "device": BTAB}, "adds": [{"identity": BOB, "device": BTAB}],
        "removes": [{"identity": ALICE, "device": APH}]}, reject("external-join-removes-other"), ["M§7.3"])
    xj("external-join-adds-another-device-refused", "An external commit adds exactly the joiner's own device.",
       {**base, "joiner": {"identity": BOB, "device": BTAB}, "adds": [{"identity": BOB, "device": BTAB}, {"identity": BOB, "device": BTAB2}],
        "removes": []}, reject("external-join-adds"))
    xj("external-join-leaf-other-than-sender-refused", "The added leaf must be the joiner's: a device cannot join another in.",
       {**base, "joiner": {"identity": BOB, "device": BTAB}, "adds": [{"identity": ALICE, "device": ALA}], "removes": []},
       reject("external-join-adds"))
    xj("external-join-personal-group-owner", "The owner re-joins its own personal group even with no surviving leaf.",
       {"kind": "personal", "owner": BOB, "roster": [], "joiner": {"identity": BOB, "device": BTAB},
        "adds": [{"identity": BOB, "device": BTAB}], "removes": []}, accept(), ["M§7.1"])
    xj("external-join-personal-group-other-identity-refused", "No one else joins a personal group.",
       {"kind": "personal", "owner": BOB, "roster": [], "joiner": {"identity": ALICE, "device": APH},
        "adds": [{"identity": ALICE, "device": APH}], "removes": []}, reject("external-join-not-member"), ["M§7.1"])

    R = {ALICE: [ALA, APH], BOB: [BPH]}
    out.append(trace("hub-external-commit-removing-other-identity-refused",
                     "The hub refuses an external commit that removes another identity's leaf.", refs + ["M§7.3"], "hub-trace", hub_ctx(), [
                         (dep("ext-rm", BTAB, BOB, "handshake", 1,
                              commit={"external": True, "adds": [{"identity": BOB, "device": BTAB}],
                                      "removes": [{"identity": ALICE, "device": APH}]}),
                          [err(BTAB, "ext-rm", "policy.blocked")], hs(1, 1, R)),
                     ]))
    out.append(trace("hub-external-commit-new-identity-leaf-refused",
                     "A member's device cannot use an external commit to bring in a leaf of an identity outside the group.",
                     refs + ["M§7.3"], "hub-trace", hub_ctx(), [
                         (dep("ext-add", BTAB, BOB, "handshake", 1,
                              commit={"external": True, "adds": [{"identity": CAROL, "device": CPH}], "removes": []}),
                          [err(BTAB, "ext-add", "policy.blocked")], hs(1, 1, R)),
                     ]))
    return out


# ---------------------------------------------------------------- call history and receipt archiving (M§13.3, M§12.2; spec-gaps 63, 64)

def call_history_vectors():
    out = []
    refs = ["M§13.3"]

    def ce(vid, desc, inp, expect, extra=()):
        out.append(mv(vid, desc, refs + list(extra), {"check": "call-event", **inp}, expect))
    ce("call-event-missed-after-caller-cancel", "An alerted leg the caller cancelled (gave up) is a missed call.",
       {"alerted": True, "answered_here": False, "ended_by": "remote", "reason": "session.cancelled"}, {"send": True, "outcome": "missed"})
    ce("call-event-missed-after-ring-timeout", "An alerted leg that rang out is a missed call.",
       {"alerted": True, "answered_here": False, "ended_by": "local", "reason": "session.timeout"}, {"send": True, "outcome": "missed"}, ["§12.10"])
    ce("call-event-answered-elsewhere-none", "A leg cancelled because another device answered sends nothing.",
       {"alerted": True, "answered_here": False, "ended_by": "remote", "reason": "session.answered-elsewhere"}, {"send": False}, ["§12.7"])
    ce("call-event-answered-here-none", "A call answered on this device is not missed.",
       {"alerted": True, "answered_here": True, "ended_by": "remote", "reason": "session.ended"}, {"send": False})
    ce("call-event-not-alerted-none", "A leg that never alerted (refused before ringing) is not shown as a call.",
       {"alerted": False, "answered_here": False, "ended_by": "local", "reason": "endpoint.busy"}, {"send": False})
    ce("call-event-declined-here", "A leg the user declined on this device is recorded as declined, not missed.",
       {"alerted": True, "answered_here": False, "ended_by": "local", "reason": "user.declined"}, {"send": True, "outcome": "declined"})
    ce("call-event-declined-elsewhere-missed", "A decline that arrives from elsewhere (another leg, the caller's cancel carrying it) is missed here.",
       {"alerted": True, "answered_here": False, "ended_by": "remote", "reason": "user.declined"}, {"send": True, "outcome": "missed"})

    S1, S2, S3 = uid("call-1"), uid("call-2"), uid("call-3")

    def pt(vid, desc, inp, expect):
        out.append(mv(vid, desc, refs + ["M§8.5"], {"check": "peer-timeline", **inp}, expect))
    pt("peer-timeline-collapses-call-events-per-session",
       "Each alerted device of the identity may report the same missed call; the timeline shows it once.",
       {"content": [], "calls": [{"session": S1, "at": NOW, "outcome": "missed"}, {"session": S1, "at": NOW + 1, "outcome": "missed"}]},
       {"timeline": ["call:" + S1], "collapsed": [S1]})
    pt("peer-timeline-interleaves-by-time",
       "Calls are placed among the peer's messages by time.",
       {"content": [{"id": "m1", "at": NOW}, {"id": "m2", "at": NOW + 100}],
        "calls": [{"session": S1, "at": NOW + 50, "outcome": "missed"}, {"session": S2, "at": NOW + 200, "outcome": "declined"}]},
       {"timeline": ["content:m1", "call:" + S1, "content:m2", "call:" + S2], "collapsed": []})
    pt("peer-timeline-content-order-is-seq-order",
       "A backdated message does not move before earlier messages; only calls are placed by time around it.",
       {"content": [{"id": "m1", "at": NOW + 100}, {"id": "m2", "at": NOW}],
        "calls": [{"session": S3, "at": NOW + 50, "outcome": "missed"}]},
       {"timeline": ["call:" + S3, "content:m1", "content:m2"], "collapsed": []})

    # receipts that change rendering are archived; archived receipts restore rendering
    T = "client-trace"
    m1, m2 = uid("m1"), uid("m2")
    out.append(trace("client-receipt-archived-when-rendering-changes",
                     "A receipt that changes what is rendered is archived (spec-gap 64); one that changes nothing — a repeat, an "
                     "older watermark, a receipt about unknown content — is not.", ["M§12.2", "M§10"], T, cl_ctx(me=ALICE, delivered=False), [
                         (sync(item(1, ct("m1")), item(2, ct("m2")), item(3, rc("delivered", BOB, targets=[m1, m2])),
                               item(4, rc("read", BOB, through=m2))),
                          [{"archive": {"seq": 3}}, {"archive": {"seq": 4}}],
                          cs([m1, m2], delivered={m1: {BOB: NOW}, m2: {BOB: NOW}}, read_through={BOB: m2})),
                         (sync(item(5, rc("delivered", BOB, targets=[m1])), item(6, rc("read", BOB, through=m1)),
                               item(7, rc("delivered", BOB, targets=[uid("unknown")]))),
                          [], cs([m1, m2], delivered={m1: {BOB: NOW}, m2: {BOB: NOW}}, read_through={BOB: m2})),
                     ]))
    out.append(trace("client-restore-from-archive-sends-nothing",
                     "A device restoring history from archive applies content and receipts to its rendering state without sending "
                     "delivered receipts or archiving again; live items afterwards behave as usual.", ["M§12.2", "M§12.3", "M§10.2"], T,
                     cl_ctx(me=ALICE), [
                         ({"restore": {"items": [item(1, ct("m1", sender=BOB)), item(2, rc("delivered", ALICE, targets=[m1])),
                                                 item(3, rc("read", CAROL, through=m1))]}},
                          [], cs([m1], delivered={m1: {ALICE: NOW}}, read_through={CAROL: m1})),
                         (sync(item(4, ct("m2", sender=BOB))), [send("conversation", "delivered", targets=[m2])],
                          cs([m1, m2], delivered={m1: {ALICE: NOW}}, read_through={CAROL: m1})),
                     ]))
    H = "history-trace"
    K1 = uid("akid-1")
    hst = lambda timeline=(), held=(), current=None: {"timeline": list(timeline), "held": [c(n) for n in held], "current_akid": current}
    out.append(trace("history-archived-receipt-applied-not-shown",
                     "A restored device applies an archived receipt to its receipt state; it is not a timeline entry, and a second "
                     "copy is a duplicate.", ["M§12.2", "M§12.3"], H, {"component": "history", "keys": [], "joined": {}}, [
                         ({"archive": {"cursor": c(1), "akid": K1, "group": GROUP, "seq": 1, "id": "m1"}}, [{"hold": c(1)}], hst(held=[1])),
                         ({"archive": {"cursor": c(2), "akid": K1, "group": GROUP, "seq": 2, "id": "r2", "object": "receipt"}},
                          [{"hold": c(2)}], hst(held=[1, 2])),
                         ({"archive_key": {"akid": K1, "created_at": NOW}}, [{"show": "m1"}, {"apply": c(2)}], hst(["m1"], current=K1)),
                         ({"archive": {"cursor": c(3), "akid": K1, "group": GROUP, "seq": 2, "id": "r2", "object": "receipt"}},
                          [{"duplicate": "r2"}], hst(["m1"], current=K1)),
                     ]))
    out.append(trace("history-own-read-receipt-archived",
                     "A device archives the read watermark it sends (spec-gap 68), so a device added later knows where its user "
                     "had read; it is state, not a timeline entry, and it is archived once.", ["M§12.2", "M§10.5", "M§10.3"], H,
                     {"component": "history", "keys": [{"akid": K1, "created_at": NOW}], "joined": {}}, [
                         ({"sent": {"group": GROUP, "seq": 7, "id": "r7", "object": "receipt"}},
                          [{"archive": {"group": GROUP, "seq": 7, "akid": K1}}], hst(current=K1)),
                         ({"sent": {"group": GROUP, "seq": 7, "id": "r7", "object": "receipt"}}, [{"duplicate": "r7"}], hst(current=K1)),
                         ({"sent": {"group": GROUP, "seq": 8, "id": "m8"}},
                          [{"show": "m8"}, {"archive": {"group": GROUP, "seq": 8, "akid": K1}}], hst(["m8"], current=K1)),
                     ]))
    out.append(trace("history-archived-call-event-applied",
                     "Call events are archived too (spec-gap 63), so a device added later has the identity's call history; like a "
                     "receipt, a restored call event goes to the call log, once.", ["M§13.3", "M§12.2", "M§12.3"], H,
                     {"component": "history", "keys": [{"akid": K1, "created_at": NOW}], "joined": {}}, [
                         ({"archive": {"cursor": c(1), "akid": K1, "group": GROUP, "seq": 4, "id": "call|s1", "object": "call-event"}},
                          [{"apply": c(1)}], hst(current=K1)),
                         ({"archive": {"cursor": c(2), "akid": K1, "group": GROUP, "seq": 4, "id": "call|s1", "object": "call-event"}},
                          [{"duplicate": "call|s1"}], hst(current=K1)),
                     ]))
    out.append(trace("history-received-call-event-state",
                     "A call event received from MLS is state, as a sent or archived one is (spec-gap 63): archived once, never a "
                     "timeline entry; a sibling's report of the same session and its archived copy are duplicates, and one from "
                     "before this device joined is not its own.", ["M§13.3", "M§12.2", "M§12.3", "M§8.5"], H,
                     {"component": "history", "keys": [{"akid": K1, "created_at": NOW}], "joined": {GROUP: 1}}, [
                         ({"mls": {"group": GROUP, "seq": 4, "epoch": 1, "id": "call|s1", "object": "call-event"}},
                          [{"archive": {"group": GROUP, "seq": 4, "akid": K1}}], hst(current=K1)),
                         ({"mls": {"group": GROUP, "seq": 5, "epoch": 1, "id": "call|s1", "object": "call-event"}},
                          [{"duplicate": "call|s1"}], hst(current=K1)),
                         ({"archive": {"cursor": c(1), "akid": K1, "group": GROUP, "seq": 4, "id": "call|s1", "object": "call-event"}},
                          [{"duplicate": "call|s1"}], hst(current=K1)),
                         ({"mls": {"group": GROUP, "seq": 2, "epoch": 0, "id": "call|s0", "object": "call-event"}},
                          [{"prejoin": 2}], hst(current=K1)),
                     ]))
    out.append(trace("history-content-object-is-timeline",
                     "`object` names what was shown; `content`, like no `object` at all, is a timeline entry whether it was "
                     "received, sent or opened from the archive.", ["M§12.2", "M§12.3"], H,
                     {"component": "history", "keys": [{"akid": K1, "created_at": NOW}], "joined": {}}, [
                         ({"mls": {"group": GROUP, "seq": 1, "epoch": 1, "id": "m1", "object": "content"}},
                          [{"show": "m1"}, {"archive": {"group": GROUP, "seq": 1, "akid": K1}}], hst(["m1"], current=K1)),
                         ({"sent": {"group": GROUP, "seq": 2, "id": "m2", "object": "content"}},
                          [{"show": "m2"}, {"archive": {"group": GROUP, "seq": 2, "akid": K1}}], hst(["m1", "m2"], current=K1)),
                         ({"archive": {"cursor": c(1), "akid": K1, "group": GROUP, "seq": 3, "id": "m3", "object": "content"}},
                          [{"show": "m3"}], hst(["m1", "m2", "m3"], current=K1)),
                     ]))
    return out


# ---------------------------------------------------------------- blob replication (M§8.4 rule 6; spec-gap 65)

def blob_replication_vectors():
    out = []
    refs = ["M§8.4"]
    ORIGIN = f"https://mbx.alice.example/blobs/{SHA}"
    OWN = "https://mbx.bob.example/blobs"
    entry = {"uri": ORIGIN, "sha256": SHA, "size": 482220}
    base = {"mode": "sync", "max_blob_bytes": 16777216, "stored": [], "entry": entry}

    def br(vid, desc, over, expect, extra=()):
        out.append(mv(vid, desc, refs + list(extra), {"check": "blob-replicate", **base, **over}, expect))
    br("blob-replicate-fetch", "A sync-mode member mailbox fetches a manifest blob it does not hold.", {}, {"action": "fetch"})
    br("blob-replicate-queue-mode-skips", "Replication is for sync-mode owners only (M§4.4: queue mode keeps no history).",
       {"mode": "queue"}, {"action": "skip", "reason": "mode"}, ["M§4.4"])
    br("blob-replicate-already-stored", "A blob already held (the sender's own mailbox, or an earlier copy) is not fetched.",
       {"stored": [SHA]}, {"action": "skip", "reason": "stored"})
    br("blob-replicate-too-large-skips", "A blob over this mailbox's max_blob_bytes is not replicated; devices use the original.",
       {"max_blob_bytes": 482219}, {"action": "skip", "reason": "too-large"}, ["M§4.3"])
    br("blob-replicate-non-https-skips", "Only an https capability URL is fetched.",
       {"entry": {**entry, "uri": f"http://mbx.alice.example/blobs/{SHA}"}}, {"action": "skip", "reason": "not-https"}, ["M§5.6"])
    br("blob-replicate-store-verified", "A 200 whose body matches the manifest hash and size is stored.",
       {"fetched": {"status": 200, "sha256": SHA, "size": 482220}}, {"action": "store"})
    br("blob-replicate-mismatch-discarded",
       "A body that does not match the manifest is discarded and not tried again: the origin would serve the same bytes (spec-gap 67).",
       {"fetched": {"status": 200, "sha256": "0" * 64, "size": 482220}}, {"action": "discard", "reason": "mismatch", "retry": False})
    br("blob-replicate-size-mismatch-discarded", "The size must match too.",
       {"fetched": {"status": 200, "sha256": SHA, "size": 482221}}, {"action": "discard", "reason": "mismatch", "retry": False})
    # spec-gap 106: the device's side — what it does after trying the sources in order
    OWN, ORIG = "https://mbx-b.example/blobs/" + SHA, "https://mbx-a.example/blobs/" + SHA
    BLOB = {"sha256": SHA, "size": 482220}

    def bf(vid, desc, tried, expect, **kw):
        out.append(mv(vid, desc, refs, {"check": "blob-fetch", "blob": BLOB, "tried": tried, **kw}, expect))
    bf("blob-fetch-own-copy-plays", "The device's own mailbox's copy matches: played from it.",
       [{"uri": OWN, "status": 200, "sha256": SHA, "size": 482220}], {"action": "play", "source": OWN})
    bf("blob-fetch-falls-back-to-origin", "The own copy is damaged, the origin's matches: played from the origin.",
       [{"uri": OWN, "status": 200, "sha256": "00" * 32, "size": 482220}, {"uri": ORIG, "status": 200, "sha256": SHA, "size": 482220}],
       {"action": "play", "source": ORIG})
    bf("blob-fetch-nothing-served-retried", "No source had it yet (the replication not done, the origin down): tried again.",
       [{"uri": OWN, "status": 404}, {"uri": ORIG, "status": 0}], {"action": "retry", "reason": "unavailable"})
    bf("blob-fetch-unavailable-bounded", "On the last attempt a fetch that found nothing is given up.",
       [{"uri": ORIG, "status": 404}], {"action": "give-up", "reason": "unavailable"}, attempt=5)
    bf("blob-fetch-mismatch-and-unavailable-retried", "One source served the wrong bytes, another had nothing yet: the second may "
       "still have it, so it is tried again.",
       [{"uri": OWN, "status": 200, "sha256": "00" * 32, "size": 482220}, {"uri": ORIG, "status": 503}], {"action": "retry", "reason": "unavailable"})
    bf("blob-fetch-all-mismatch-given-up", "Every source served the wrong bytes: given up at once, they would serve them again.",
       [{"uri": OWN, "status": 200, "sha256": "00" * 32, "size": 482220}, {"uri": ORIG, "status": 200, "sha256": SHA, "size": 1}],
       {"action": "give-up", "reason": "mismatch"})
    bf("blob-fetch-no-source-tried", "No source could be tried at all: counts as nothing served.", [], {"action": "retry", "reason": "unavailable"})
    br("blob-replicate-unavailable-retried",
       "A fetch that found nothing to serve — the origin mailbox down at that moment — stores nothing and is tried again "
       "(spec-gap 67); until it succeeds the item keeps the original uri.",
       {"fetched": {"status": 404}}, {"action": "discard", "reason": "unavailable", "retry": True})
    br("blob-replicate-unavailable-bounded", "Attempts are bounded: after the last one the blob stays at its origin.",
       {"fetched": {"status": 0}, "attempt": 5}, {"action": "discard", "reason": "unavailable", "retry": False})
    br("blob-replicate-unavailable-attempt-below-bound", "Before the last attempt it is still retried.",
       {"fetched": {"status": 0}, "attempt": 4}, {"action": "discard", "reason": "unavailable", "retry": True})

    other = {"uri": "https://mbx.alice.example/blobs/" + "1" * 64, "sha256": "1" * 64, "size": 10}
    out.append(mv("items-blobs-rewrites-held-blobs",
                  "In items, a blob the mailbox holds is named at its own blob endpoint; one it does not hold keeps its uri.",
                  refs + ["M§5.4"], {"check": "items-blobs", "blob_endpoint": OWN, "stored": [SHA], "manifest": [entry, other]},
                  {"blobs": [{**entry, "uri": f"{OWN}/{SHA}"}, other]}))

    blob = {"uri": ORIGIN, "sha256": SHA, "size": 482220, "key": "k" * 43, "alg": "A256GCM", "content_type": "audio/ogg"}

    def bs(vid, desc, manifest, expect):
        out.append(mv(vid, desc, refs, {"check": "blob-sources", "blob": blob, "manifest": manifest}, {"sources": expect}))
    bs("blob-sources-own-mailbox-first", "The device tries its own mailbox's copy first, then the original.",
       [{"uri": f"{OWN}/{SHA}", "sha256": SHA, "size": 482220}], [f"{OWN}/{SHA}", ORIGIN])
    bs("blob-sources-not-replicated", "Without a rewritten manifest entry, only the original.", [entry], [ORIGIN])
    bs("blob-sources-manifest-other-hash-ignored",
       "A manifest entry for a different hash or size is not a source for this blob (the manifest is not encrypted; the content is).",
       [{"uri": f"{OWN}/{'2' * 64}", "sha256": "2" * 64, "size": 482220}, {"uri": f"{OWN}/{SHA}", "sha256": SHA, "size": 1}], [ORIGIN])
    bs("blob-sources-no-manifest", "An item with no manifest: the original.", None, [ORIGIN])
    return out


# ---------------------------------------------------------------- leaving (M§7.3; spec-gap 125)

def leave_vectors():
    """M§7.3 "Leaving": what a member's device does with an identity's pending Remove proposals. By hand."""
    out = []
    A1, A2 = "did:key:z6MkAlicePhoneLeaveLeaveLeaveLeaveLeave1", "did:key:z6MkAliceLaptopLeaveLeaveLeaveLeaveLeave2"
    B1, C1 = "did:key:z6MkBobPhoneLeaveLeaveLeaveLeaveLeaveLeave", "did:key:z6MkCarolPhoneLeaveLeaveLeaveLeaveLeave"
    roster = [{"identity": ALICE, "device": A1}, {"identity": ALICE, "device": A2}, {"identity": BOB, "device": B1},
              {"identity": CAROL, "device": C1}]

    def lv(vid, desc, want, me=BOB, proposer=(ALICE, A1), removes=((ALICE, A1), (ALICE, A2)), others=0):
        out.append(mv(f"leave-{vid}", desc, ["M§7.3"], {"check": "leave-proposals", "me": me,
                      "proposer": {"identity": proposer[0], "device": proposer[1]},
                      "removes": [{"identity": i, "device": d} for i, d in removes], "others": others, "roster": roster}, want))
    lv("commit-all-leaves", "Every leaf of the proposer's identity is proposed for removal: another member commits.", {"action": "commit"})
    lv("commit-single-device", "An identity with one device leaves with one proposal.", {"action": "commit"},
       proposer=(CAROL, C1), removes=((CAROL, C1),))
    lv("commit-proposed-by-the-other-device", "Any device of the identity may propose all of its leaves.", {"action": "commit"},
       proposer=(ALICE, A2))
    lv("commit-duplicate-proposal", "A leaf proposed twice is still one leaf: all are covered.", {"action": "commit"},
       removes=((ALICE, A1), (ALICE, A1), (ALICE, A2)))
    lv("wait-first-of-two", "One proposal of two has arrived: wait for the rest.", {"action": "wait"}, removes=((ALICE, A1),))
    lv("wait-other-first", "The other leaf's proposal arrived first: wait.", {"action": "wait"}, removes=((ALICE, A2),))
    lv("left-sibling", "A device of the leaving identity itself: the conversation is left, nothing is committed.", {"action": "left"},
       me=ALICE, proposer=(ALICE, A2))
    lv("wait-before-left", "A sibling waits for all the proposals too.", {"action": "wait"}, me=ALICE, removes=((ALICE, A1),))
    lv("not-own-leaves-other-identity", "Proposing another identity's removal is not leaving.", {"action": "ignore", "reason": "not-own-leaves"},
       removes=((BOB, B1),))
    lv("not-own-leaves-mixed", "A leave that also removes another identity's leaf is not a leave.",
       {"action": "ignore", "reason": "not-own-leaves"}, me=CAROL, removes=((ALICE, A1), (ALICE, A2), (BOB, B1)))
    lv("not-own-leaves-unknown-device", "A removal naming a device that is not a leaf of the identity.",
       {"action": "ignore", "reason": "not-own-leaves"}, removes=((ALICE, A1), (ALICE, "did:key:z6MkAliceOldLeaveLeaveLeaveLeaveLeave")))
    lv("not-own-leaves-before-left", "Not own leaves is checked before a sibling would treat it as left.",
       {"action": "ignore", "reason": "not-own-leaves"}, me=ALICE, removes=((BOB, B1),))
    lv("not-a-leave", "A proposal of another kind pending beside the removals: not a leave.", {"action": "ignore", "reason": "not-a-leave"},
       others=1)
    lv("not-a-leave-first", "Another kind of proposal is checked first.", {"action": "ignore", "reason": "not-a-leave"}, others=2,
       removes=((BOB, B1),))
    return out


# ---------------------------------------------------------------- member enforcement of M§7.3 (spec-gap 126)

def roster_change_vectors():
    """M§7.3: the roster rules every member checks on a commit the hub ordered, as the hub does. By hand."""
    out = []
    A1, A2 = "did:key:z6MkAlicePhoneRosterRosterRosterRosterRo1", "did:key:z6MkAliceLaptopRosterRosterRosterRoster2"
    B1, B2 = "did:key:z6MkBobPhoneRosterRosterRosterRosterRost1", "did:key:z6MkBobTabletRosterRosterRosterRosterRo2"
    C1, C2 = "did:key:z6MkCarolPhoneRosterRosterRosterRosterR1", "did:key:z6MkCarolLaptopRosterRosterRosterRoste2"
    B3 = "did:key:z6MkBobDeskRosterRosterRosterRosterRoste3"
    DAVE = "did:web:dave.example"
    roster = [(ALICE, A1), (ALICE, A2), (BOB, B1), (BOB, B2), (CAROL, C1)]

    def leaf(i, d, lapsed=False):
        return {"identity": i, "device": d, **({"delegation_valid": False} if lapsed else {})}

    def rc(vid, desc, want, adds=(), removes=(), committer=ALICE, ros=roster):
        out.append(mv(f"roster-change-{vid}", desc, ["M§7.3"], {"check": "roster-change", "committer": committer,
                      "roster": [leaf(i, d) for i, d in ros], "adds": [leaf(i, d) for i, d in adds],
                      "removes": [leaf(*r) for r in removes]}, want))
    blocked = lambda code: reject(code)
    rc("add-new-identity", "Any member identity may add another identity, all of its devices.", accept(),
       adds=[(DAVE, "did:key:z6MkDavePhoneRosterRosterRosterRosterRost1")], ros=roster[:4])
    rc("add-own-device", "A member adds a new device of its own identity.", accept(),
       adds=[(ALICE, "did:key:z6MkAliceDeskRosterRosterRosterRosterRos3")])
    rc("add-other-identitys-device-refused", "Adding a device of another member identity is that identity's own business.",
       blocked("roster-adds-other-devices"), adds=[(BOB, B3)])
    rc("add-other-identitys-device-refused-beside-new", "One device of another member identity among new ones is refused too.",
       blocked("roster-adds-other-devices"), adds=[(DAVE, "did:key:z6MkDavePhoneRosterRosterRosterRosterRost1"), (CAROL, C2)])
    rc("remove-whole-identity", "Any member identity may remove another identity: every leaf of it.", accept(),
       removes=[(BOB, B1), (BOB, B2)])
    rc("remove-single-device-identity", "Removing an identity with one device is removing all of it.", accept(),
       removes=[(CAROL, C1)])
    rc("remove-part-of-identity-refused", "Removing some devices of another identity is refused while their delegations verify.",
       blocked("roster-removes-part-of-identity"), removes=[(BOB, B1)])
    rc("remove-part-duplicate-refused", "A leaf named twice is still one leaf: the identity's other device stays, refused.",
       blocked("roster-removes-part-of-identity"), removes=[(BOB, B1), (BOB, B1)])
    rc("remove-lapsed-leaf", "Any member may remove a leaf whose delegation no longer verifies (M§6.2).", accept(),
       removes=[(BOB, B2, True)])
    rc("remove-lapsed-and-valid-part-refused", "A lapsed leaf removed beside a valid one of the same identity, the identity not whole: refused.",
       blocked("roster-removes-part-of-identity"), ros=roster + [(BOB, B3)], removes=[(BOB, B2, True), (BOB, B1)])
    rc("remove-own-device", "A member removes a device of its own identity.", accept(), removes=[(ALICE, A2)])
    rc("commit-anothers-leave", "Committing a leaver's proposals removes its whole identity.", accept(), committer=CAROL,
       removes=[(ALICE, A1), (ALICE, A2)])
    rc("add-and-remove", "Adding an identity and removing another whole one in one commit.", accept(),
       adds=[(DAVE, "did:key:z6MkDavePhoneRosterRosterRosterRosterRost1")], removes=[(CAROL, C1)])
    rc("adds-checked-before-removes", "An add of another identity's device is reported before a partial removal.",
       blocked("roster-adds-other-devices"), adds=[(CAROL, C2)], removes=[(BOB, B1)])
    rc("unauthenticated-committer-adds-refused", "A committer whose leaf no longer authenticates has no identity: adding a member's device is refused.",
       blocked("roster-adds-other-devices"), committer="", adds=[(ALICE, "did:key:z6MkAliceDeskRosterRosterRosterRosterRos3")])
    rc("no-change", "A commit that adds and removes nothing (a path update) changes no roster.", accept())
    return out
