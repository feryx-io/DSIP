"""`wake/` vectors — Wake Profile draft (W§3–W§6; spec-gaps 169–176, 178). Expectations are written out by hand."""
from __future__ import annotations

import copy

from .. import envelope as E
from .. import fixtures as F
from ..crypto import b64url_encode, keypair_from_seed_name
from ..messaging import hpke_seal, x25519_public
from .common import NOW, uid, vector

PROFILE_VERSION = {"core": "1.0", "min_core": "1.0", "profiles": ["wake/0.1"], "extensions": [], "critical": []}
RELAY = F.RELAY_WEB
MAILBOX = "did:web:mbx.example.com"
GW = "did:web:push.dsip.example"
GW2 = "did:web:push.other.example"
BOB = F.BOB_WEB
PHONE, LAPTOP, TABLET = F.did("bob-phone"), F.did("bob-laptop"), "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"
CALLER = F.did("alice-phone")

WK = keypair_from_seed_name("wake-key-bob-phone")       # the phone's wake key (W§3)
WK2 = keypair_from_seed_name("wake-key-bob-laptop")
WK3 = keypair_from_seed_name("wake-key-bob-phone-alert")  # the phone's alert token, its own enrolment (spec-gap 178)
HANDLE, HANDLE2 = "h-apns-bob-phone-0001", "h-fcm-bob-laptop-0001"
APNS_TOKEN = "7d1f" * 16
APNS_ALERT_TOKEN = "c0de" * 16
FCM_TOKEN = "fcm:APA91bH-bob-laptop-" + "x" * 120
SEAL_SECRET = bytes(range(1, 33))                         # the device's X25519 secret for hints (W§6)
SEAL_KEY = b64url_encode(x25519_public(SEAL_SECRET))
EPHEMERAL = bytes(range(101, 133))
SESSION = uid("wake-invite")
REFS = {"enrol": ["W§3"], "register": ["W§4.1", "W§4.2"], "gateway": ["W§5.2", "W§5.3"], "hint": ["W§6"],
        "trace": ["W§4.3", "W§5.1"]}


def wv(vid, desc, refs, inp, expect, ctx=None):
    return vector(f"wake/{vid}", "wake", desc, refs, ctx or {}, inp, expect)


def acc(**extra):
    return {"verdict": "accept", **extra}


def rej(code, reason=None):
    out = {"verdict": "reject", "code": code}
    if reason:
        out["reason"] = reason
    return out


def refused(token):
    return rej(token.split(".", 1)[1], token)


def msg(msg_type, label, frm, to, at=NOW, ttl=30, **fields):
    p = {"dsip": copy.deepcopy(PROFILE_VERSION), "type": msg_type, "id": uid(label, at), "from": frm, "to": to}
    p.update(fields)
    p["issued_at"] = at
    p["expires_at"] = at + ttl
    return p


def registration_payload(key=WK, waker=RELAY, gateway=GW, handle=HANDLE, issued_at=NOW - 60, life=2_592_000, **over):
    p = {"type": "WakeRegistration", "key": key.did, "waker": waker, "gateway": gateway, "handle": handle,
         "issued_at": issued_at, "expires_at": issued_at + life}
    p.update(over)
    return p


def registration(signer=WK, **kw):
    return E.sign(registration_payload(**kw), signer, signer.kid)


# ---------------------------------------------------------------- schema

def schema_vectors() -> list[dict]:
    out = []

    def sv(vid, desc, schema, value, ok, refs):
        out.append(wv(f"schema-{vid}", desc, refs, {"check": "schema", "schema": schema, "value": value},
                      acc() if ok else rej("schema-invalid")))

    enrol = msg("wake-enrol", "enrol", WK.did, GW, provider="apns", app="org.dsip.app.voip", environment="production",
                token=APNS_TOKEN)
    sv("enrol-valid", "A wake-enrol signed by its wake key's did:key.", "wake-enrol", enrol, True, REFS["enrol"])
    sv("enrol-from-not-did-key", "A wake-enrol's `from` must be a did:key: the gateway never learns a device's DID.",
       "wake-enrol", {**enrol, "from": BOB}, False, REFS["enrol"])
    sv("enrol-token-too-long", "A platform token longer than 4,096 characters.", "wake-enrol",
       {**enrol, "token": "a" * 4097}, False, REFS["enrol"])
    sv("enrol-environment-unknown", "`environment` is `production` or `sandbox`.", "wake-enrol",
       {**enrol, "environment": "staging"}, False, REFS["enrol"])
    sv("enrol-provider-shape", "A provider is a registry token: shape only, membership is the gateway's.", "wake-enrol",
       {**enrol, "provider": "Apple Push"}, False, REFS["enrol"])
    accepted = msg("wake-accepted", "accepted", GW, WK.did, in_reply_to=enrol["id"], handle=HANDLE)
    sv("accepted-valid", "A gateway's wake-accepted with a handle.", "wake-accepted", accepted, True, REFS["enrol"])
    sv("accepted-handle-too-long", "A handle is at most 512 characters.", "wake-accepted",
       {**accepted, "handle": "h" * 513}, False, REFS["enrol"])
    reg = msg("wake-register", "register", PHONE, RELAY, registration=registration(), seal_key=SEAL_KEY,
              kinds=["call", "call-ended"])
    sv("register-valid", "A wake-register with a registration, a seal key and kinds.", "wake-register", reg, True,
       ["W§4.2"])
    sv("register-remove-valid", "`remove: true` alone ends a registration.", "wake-register",
       msg("wake-register", "remove", PHONE, RELAY, remove=True), True, ["W§4.2"])
    sv("register-remove-with-registration", "`remove` stands in place of the registration, never beside it.",
       "wake-register", {**reg, "remove": True}, False, ["W§4.2"])
    sv("register-remove-with-kinds", "`remove` carries no kinds.", "wake-register",
       msg("wake-register", "remove-kinds", PHONE, RELAY, remove=True, kinds=["call"]), False, ["W§4.2"])
    sv("register-neither", "A wake-register with neither a registration nor `remove`.", "wake-register",
       msg("wake-register", "neither", PHONE, RELAY, kinds=["call"]), False, ["W§4.2"])
    sv("register-remove-false", "`remove` is `true` or absent.", "wake-register",
       {**reg, "remove": False}, False, ["W§4.2"])
    sv("register-seal-key-short", "A seal key is exactly 32 bytes: 31 is refused.", "wake-register",
       {**reg, "seal_key": b64url_encode(bytes(31))}, False, ["W§4.2"])
    sv("register-seal-key-noncanonical", "A seal key's last character carries no stray bits.", "wake-register",
       {**reg, "seal_key": SEAL_KEY[:42] + ("B" if SEAL_KEY[42] != "B" else "C")}, False, ["W§4.2"])
    wake = msg("wake", "wake", RELAY, GW, registration=registration(), kind="call", session=SESSION,
               deliver_by=NOW + 30)
    sv("wake-call-valid", "A call wake with its session.", "wake", wake, True, ["W§5.2"])
    sv("wake-call-without-session", "`call` requires `session`.", "wake",
       {k: x for k, x in wake.items() if k != "session"}, False, ["W§5.2"])
    sv("wake-call-ended-without-session", "`call-ended` requires `session`.", "wake",
       {**{k: x for k, x in wake.items() if k != "session"}, "kind": "call-ended"}, False, ["W§5.2"])
    sv("wake-message-without-session", "`message` needs no session.", "wake",
       {**{k: x for k, x in wake.items() if k != "session"}, "kind": "message"}, True, ["W§5.2"])
    sv("wake-unknown-kind-valid", "An unknown kind is a valid token: the schema checks shape only.", "wake",
       {**{k: x for k, x in wake.items() if k != "session"}, "kind": "typing"}, True, ["W§5.2", "W§8.2"])
    sv("wake-without-deliver-by", "`deliver_by` is required.", "wake",
       {k: x for k, x in wake.items() if k != "deliver_by"}, False, ["W§5.2"])
    sv("wake-registration-not-envelope", "The registration rides as a DSIP-JOSE envelope, nothing else.", "wake",
       {**wake, "registration": {**wake["registration"], "header": {}}}, False, ["W§5.2", "W§4.1"])
    rp = registration_payload()
    sv("registration-valid", "A WakeRegistration payload.", "wake-registration", rp, True, ["W§4.1"])
    sv("registration-extra-field", "A WakeRegistration has no other fields.", "wake-registration",
       {**rp, "identity": BOB}, False, ["W§4.1"])
    sv("registration-key-not-did-key", "A registration's key is a did:key.", "wake-registration",
       {**rp, "key": BOB}, False, ["W§4.1"])
    sv("hint-valid", "An opened hint with on_behalf_of.", "wake-hint", {"from": CALLER, "on_behalf_of": F.did("alice")},
       True, ["W§6"])
    sv("hint-extra-field", "An opened hint carries only `from` and `on_behalf_of`.", "wake-hint",
       {"from": CALLER, "display_name": "Alice"}, False, ["W§6"])
    return out


# ---------------------------------------------------------------- enrolment at the gateway

# An iOS app's two APNs topics: PushKit's VoIP token for calls, the alert token for messages (spec-gap 178).
APPS = [{"provider": "apns", "app": "org.dsip.app.voip"}, {"provider": "apns", "app": "org.dsip.app"},
        {"provider": "fcm", "app": "dsip-app-prod"}]


def enrol_vectors() -> list[dict]:
    ctx = {"apps": APPS}
    out = []

    def ev(vid, desc, p, expect):
        out.append(wv(f"enrol-{vid}", desc, REFS["enrol"], {"check": "enrol", "enrol": p}, expect, ctx))

    apns = msg("wake-enrol", "enrol-apns", WK.did, GW, provider="apns", app="org.dsip.app.voip", token=APNS_TOKEN)
    ev("apns-default-production", "An APNs enrolment without `environment` is for production.", apns,
       acc(enrolment={"key": WK.did, "provider": "apns", "app": "org.dsip.app.voip", "token": APNS_TOKEN,
                      "environment": "production"}))
    ev("apns-sandbox", "An APNs enrolment for the sandbox.", {**apns, "environment": "sandbox"},
       acc(enrolment={"key": WK.did, "provider": "apns", "app": "org.dsip.app.voip", "token": APNS_TOKEN,
                      "environment": "sandbox"}))
    ev("apns-alert-token", "An iOS device's alert token is enrolled on its own, on the bundle ID's topic (spec-gap 178).",
       {**msg("wake-enrol", "enrol-apns-alert", WK3.did, GW, provider="apns", app="org.dsip.app",
              token=APNS_ALERT_TOKEN)},
       acc(enrolment={"key": WK3.did, "provider": "apns", "app": "org.dsip.app", "token": APNS_ALERT_TOKEN,
                      "environment": "production"}))
    fcm = msg("wake-enrol", "enrol-fcm", WK2.did, GW, provider="fcm", app="dsip-app-prod", token=FCM_TOKEN,
              environment="sandbox")
    ev("fcm-ignores-environment", "`environment` is APNs only: an FCM enrolment ignores it.", fcm,
       acc(enrolment={"key": WK2.did, "provider": "fcm", "app": "dsip-app-prod", "token": FCM_TOKEN}))
    ev("unsupported-app", "The gateway does not push for this APNs topic.", {**apns, "app": "com.other.voip"},
       refused("wake.unsupported-app"))
    ev("unsupported-provider", "An unregistered provider is refused as an app the gateway does not push for.",
       {**apns, "provider": "hms"}, refused("wake.unsupported-app"))
    ev("provider-app-pair", "The provider and app are matched together: an FCM project under APNs is refused.",
       {**apns, "app": "dsip-app-prod"}, refused("wake.unsupported-app"))
    ev("from-not-did-key", "A wake-enrol from a device DID fails the schema before anything else.",
       {**apns, "from": BOB, "app": "com.other.voip"}, rej("schema-invalid"))
    return out


# ---------------------------------------------------------------- registration at a waker

def register_vectors() -> list[dict]:
    out = []
    ctx = {"waker": RELAY, "now": NOW, "gateways": [GW]}

    def rv(vid, desc, p, expect, c=None, refs=None):
        out.append(wv(f"register-{vid}", desc, refs or REFS["register"],
                      {"check": "register", "register": p, "device": PHONE}, expect, c or ctx))

    def reg_msg(label="r", **fields):
        fields.setdefault("registration", registration())
        return msg("wake-register", f"register-{label}", PHONE, RELAY, **fields)

    def held(**extra):
        return {"device": PHONE, "key": WK.did, "gateway": GW, "handle": HANDLE, "expires_at": NOW - 60 + 2_592_000,
                **extra}

    rv("accepted", "A registration naming this relay; kinds deduplicated and sorted, the seal key kept.",
       reg_msg(seal_key=SEAL_KEY, kinds=["call-ended", "call", "call"]),
       acc(registration=held(kinds=["call", "call-ended"], seal_key=SEAL_KEY)))
    rv("accepted-plain", "No kinds and no seal key: every kind, and no hint.", reg_msg("plain"), acc(registration=held()))
    rv("accepted-unknown-kind-kept", "An unknown kind is kept: the waker never sends it, and it harms nothing.",
       reg_msg("unknown-kind", kinds=["typing"]), acc(registration=held(kinds=["typing"])))
    rv("accepted-any-gateway", "A waker with no gateway policy admits any gateway.",
       reg_msg("any-gw", registration=registration(gateway=GW2)),
       acc(registration={**held(), "gateway": GW2}), {"waker": RELAY, "now": NOW})
    rv("remove", "`remove: true` ends the registration; nothing else is read.",
       msg("wake-register", "register-remove", PHONE, RELAY, remove=True), acc(removed=True))
    rv("schema-invalid", "Neither a registration nor `remove`.", msg("wake-register", "register-none", PHONE, RELAY),
       rej("schema-invalid"))
    other = keypair_from_seed_name("wake-key-mallory")
    forged = registration()
    forged = {**forged, "signature": E.sign(registration_payload(), other, other.kid)["signature"]}
    rv("bad-signature", "A registration whose signature does not verify under its kid.",
       reg_msg("badsig", registration=forged), refused("wake.registration-invalid"))
    rv("signer-not-key", "A registration signed by a key other than the one it names.",
       reg_msg("signer", registration=registration(signer=other)), refused("wake.registration-invalid"))
    rv("payload-extra-field", "A registration payload outside the WakeRegistration schema.",
       reg_msg("extra", registration=E.sign({**registration_payload(), "identity": BOB}, WK, WK.kid)),
       refused("wake.registration-invalid"))
    rv("payload-wrong-type", "A delegation is not a registration.",
       reg_msg("deleg", registration=E.sign({**registration_payload(), "type": "DeviceDelegation"}, WK, WK.kid)),
       refused("wake.registration-invalid"))
    rv("payload-float", "A registration payload with a float fails the §10.3 rules.",
       reg_msg("float", registration=E.sign_bytes(E.encode_payload(registration_payload()).replace(
           b'"issued_at":' + str(NOW - 60).encode(), b'"issued_at":' + str(NOW - 60).encode() + b".0"), WK, WK.kid)),
       refused("wake.registration-invalid"))
    rv("waker-mismatch", "A registration naming the mailbox, sent to the relay.",
       reg_msg("mbx", registration=registration(waker=MAILBOX)), refused("wake.waker-mismatch"))
    rv("waker-before-lifetime", "The waker is checked before the lifetime: both wrong is a waker mismatch.",
       reg_msg("mbx-long", registration=registration(waker=MAILBOX, life=2_592_001)), refused("wake.waker-mismatch"))
    rv("signature-before-waker", "The signature is checked before the waker.",
       reg_msg("mbx-signer", registration=registration(signer=other, waker=MAILBOX)), refused("wake.registration-invalid"))
    rv("lifetime-at-cap", "A registration of exactly W-Registration (30 days).", reg_msg("cap"), acc(registration=held()))
    rv("lifetime-over-cap", "One second over W-Registration.",
       reg_msg("over", registration=registration(life=2_592_001)), refused("wake.registration-invalid"))
    rv("expires-not-after-issued", "`expires_at` must be after `issued_at`.",
       reg_msg("order", registration=registration(life=0)), refused("wake.registration-invalid"))
    rv("expired", "A registration whose `expires_at` is now has expired (§12.9).",
       reg_msg("expired", registration=registration(issued_at=NOW - 3600, life=3600)), refused("wake.registration-invalid"))
    rv("not-yet-expired", "One second before `expires_at` it is live.",
       reg_msg("live", registration=registration(issued_at=NOW - 3600, life=3601)),
       acc(registration={**held(), "expires_at": NOW + 1}))
    rv("issued-in-future-bound", "`issued_at` up to 300 s ahead is accepted.",
       reg_msg("future-ok", registration=registration(issued_at=NOW + 300, life=3600)),
       acc(registration={**held(), "expires_at": NOW + 3900}))
    rv("issued-in-future", "`issued_at` more than 300 s ahead is refused.",
       reg_msg("future", registration=registration(issued_at=NOW + 301, life=3600)), refused("wake.registration-invalid"))
    rv("gateway-unknown", "A gateway the relay will not use.",
       reg_msg("gw2", registration=registration(gateway=GW2)), refused("wake.gateway-unknown"))
    rv("lifetime-before-gateway", "The lifetime is checked before the gateway policy.",
       reg_msg("gw2-long", registration=registration(gateway=GW2, life=2_592_001)), refused("wake.registration-invalid"))
    mctx = {"waker": MAILBOX, "now": NOW, "gateways": [GW]}
    rv("mailbox-accepted", "The same checks at a mailbox, for a registration naming it.",
       msg("wake-register", "register-mbx", PHONE, MAILBOX, registration=registration(waker=MAILBOX), kinds=["message"]),
       acc(registration=held(kinds=["message"])), mctx)
    return out


# ---------------------------------------------------------------- the gateway

HANDLES = {
    HANDLE: {"key": WK.did, "provider": "apns", "app": "org.dsip.app.voip", "token": APNS_TOKEN},
    "h-apns-bob-phone-alert": {"key": WK3.did, "provider": "apns", "app": "org.dsip.app", "token": APNS_ALERT_TOKEN},
    HANDLE2: {"key": WK2.did, "provider": "fcm", "app": "dsip-app-prod", "token": FCM_TOKEN},
    "h-apns-bob-tablet-sandbox": {"key": WK.did, "provider": "apns", "app": "org.dsip.app.voip", "token": "ab" * 32,
                                  "environment": "sandbox"},
}


def seal(session: str, hint: dict, secret_pub=None, pad=256, eph=EPHEMERAL, info=b"dsip wake hint v1", raw=None):
    pt = raw if raw is not None else E.encode_payload(hint)
    if raw is None:
        pt = pt + b" " * (pad - len(pt))
    enc, ct = hpke_seal(secret_pub or x25519_public(SEAL_SECRET), info, session.encode("utf-8"), pt, eph)
    return {"alg": "hpke-base-x25519-sha256-aes128gcm", "enc": b64url_encode(enc), "ct": b64url_encode(ct)}


def gateway_vectors() -> list[dict]:
    out = []
    ctx = {"gateway": GW, "now": NOW, "handles": HANDLES}

    def gv(vid, desc, p, expect, signer=RELAY, refs=None):
        out.append(wv(f"gateway-{vid}", desc, refs or REFS["gateway"], {"check": "gateway", "wake": p, "signer": signer},
                      expect, ctx))

    sealed = seal(SESSION, {"from": CALLER, "on_behalf_of": F.did("alice")})
    call = msg("wake", "gw-call", RELAY, GW, registration=registration(), kind="call", session=SESSION, sealed=sealed,
               deliver_by=NOW + 30)

    def fwd(cls, data, h=HANDLE, deliver_by=NOW + 30):
        hh = HANDLES[h]
        f = {"provider": hh["provider"], "app": hh["app"], "token": hh["token"], "class": cls, "deliver_by": deliver_by,
             "data": {"dsip-wake": data}}
        if hh["provider"] == "apns":
            f["environment"] = hh.get("environment", "production")
        return acc(forward=f)

    gv("call", "A call wake: the call class, the session and the sealed hint passed through, the waker named.", call,
       fwd("call", {"kind": "call", "waker": RELAY, "session": SESSION, "sealed": sealed}))
    nos = {k: x for k, x in call.items() if k != "sealed"}
    gv("call-ended", "A call-ended wake is of the call class.", {**nos, "kind": "call-ended"},
       fwd("call", {"kind": "call-ended", "waker": RELAY, "session": SESSION}))
    m = msg("wake", "gw-msg", MAILBOX, GW, registration=registration(key=WK2, signer=WK2, waker=MAILBOX, handle=HANDLE2),
            kind="message", deliver_by=NOW + 60)
    gv("message-fcm", "A message wake through FCM: the message class, no environment.", m,
       fwd("message", {"kind": "message", "waker": MAILBOX}, HANDLE2, NOW + 60), MAILBOX)
    ma = msg("wake", "gw-msg-apns", MAILBOX, GW,
             registration=registration(key=WK3, signer=WK3, waker=MAILBOX, handle="h-apns-bob-phone-alert"), kind="message",
             deliver_by=NOW + 60)
    gv("message-apns-alert-token", "A message wake to an iOS device goes to the handle of its alert token, the "
       "handle's `app` as given (spec-gap 178).", ma,
       fwd("message", {"kind": "message", "waker": MAILBOX}, "h-apns-bob-phone-alert", NOW + 60), MAILBOX,
       ["W§3", "W§5.3"])
    gv("unknown-kind-is-message", "An unknown kind is forwarded as raw, in the message class (W§8.2 fallback).",
       {**m, "kind": "typing"}, fwd("message", {"kind": "typing", "waker": MAILBOX}, HANDLE2, NOW + 60), MAILBOX,
       ["W§5.3", "W§8.2"])
    sb = msg("wake", "gw-sandbox", RELAY, GW, registration=registration(handle="h-apns-bob-tablet-sandbox"), kind="call",
             session=SESSION, deliver_by=NOW + 30)
    gv("apns-sandbox", "The handle's environment is the push's.", sb,
       fwd("call", {"kind": "call", "waker": RELAY, "session": SESSION}, "h-apns-bob-tablet-sandbox"))
    gv("unknown-handle", "A handle the gateway did not issue.",
       {**nos, "registration": registration(handle="h-forged-0001")}, refused("wake.not-authorized"))
    gv("key-not-handle-key", "A registration signed by a wake key other than the handle's.",
       {**nos, "registration": registration(key=WK2, signer=WK2)}, refused("wake.not-authorized"))
    gv("waker-not-signer", "A registration naming the relay, presented by the mailbox.", nos,
       refused("wake.not-authorized"), MAILBOX)
    gv("other-gateway", "A registration for another gateway.", {**nos, "registration": registration(gateway=GW2)},
       refused("wake.not-authorized"))
    gv("registration-expired", "A registration whose `expires_at` is now.",
       {**nos, "registration": registration(issued_at=NOW - 3600, life=3600)}, refused("wake.not-authorized"))
    gv("registration-bad-signature", "A registration whose signature does not verify.",
       {**nos, "registration": {**registration(), "signature": registration(issued_at=NOW - 61)["signature"]}},
       refused("wake.not-authorized"))
    gv("lifetime-cap-not-checked", "The gateway checks expiry only; the lifetime cap is the waker's (W§4.2).",
       {**nos, "registration": registration(life=2_592_001 * 2)},
       fwd("call", {"kind": "call", "waker": RELAY, "session": SESSION}))
    gv("deliver-by-passed", "`deliver_by` is now: the wake is useless.", {**nos, "deliver_by": NOW},
       refused("wake.expired"))
    gv("not-authorized-before-expired", "Authorization is checked before `deliver_by`.",
       {**nos, "deliver_by": NOW}, refused("wake.not-authorized"), MAILBOX)
    gv("schema-invalid", "A call wake without its session.", {k: x for k, x in nos.items() if k != "session"},
       rej("schema-invalid"))
    return out


# ---------------------------------------------------------------- the sealed hint

def hint_vectors() -> list[dict]:
    out = []

    def hv(vid, desc, sealed, expect, session=SESSION, secret=SEAL_SECRET):
        out.append(wv(f"hint-{vid}", desc, REFS["hint"],
                      {"check": "open-hint", "sealed": sealed, "session": session, "secret_hex": secret.hex()}, expect))

    full = {"from": CALLER, "on_behalf_of": F.did("alice")}
    hv("opens", "A hint with the caller's device and identity, padded to 256 bytes.", seal(SESSION, full),
       acc(hint=full))
    hv("opens-without-on-behalf-of", "A hint from a caller that is its own identity.", seal(SESSION, {"from": CALLER}),
       acc(hint={"from": CALLER}))
    hv("wrong-key", "Opened with another device's secret.", seal(SESSION, full), rej("sealed-open-failed"),
       secret=bytes(range(2, 34)))
    hv("wrong-session", "The AAD is the session: a hint moved to another wake does not open.", seal(SESSION, full),
       rej("sealed-open-failed"), session=uid("wake-other"))
    hv("wrong-info", "Sealed under another info string.", seal(SESSION, full, info=b"dsip sealed introduction v1"),
       rej("sealed-open-failed"))
    hv("alg-unsupported", "Only the M§6.9 suite.", {**seal(SESSION, full), "alg": "hpke-base-p256-sha256-aes128gcm"},
       rej("sealed-alg-unsupported"))
    hv("enc-not-base64url", "An `enc` that does not decode does not open.", {**seal(SESSION, full), "enc": "!!"},
       rej("sealed-open-failed"))
    hv("short-padding", "A hint padded to 255 bytes.", seal(SESSION, full, pad=255), rej("sealed-plaintext-invalid"))
    hv("long-padding", "A hint padded to 257 bytes.", seal(SESSION, full, pad=257), rej("sealed-plaintext-invalid"))
    hv("extra-field", "A hint with a display name, which the hint never carries.",
       seal(SESSION, {"from": CALLER, "display_name": "Alice"}), rej("sealed-plaintext-invalid"))
    hv("not-json", "256 bytes that are not JSON.", seal(SESSION, {}, raw=b"x" * 256), rej("sealed-plaintext-invalid"))
    hv("not-utf8", "256 bytes that are not UTF-8.", seal(SESSION, {}, raw=b'{"from":"\xff"}' + b" " * 242),
       rej("sealed-plaintext-invalid"))
    hv("leading-spaces", "Leading spaces are JSON whitespace: the hint opens.",
       seal(SESSION, {}, raw=(b"  " + E.encode_payload(full)).ljust(256, b" ")), acc(hint=full))
    hv("float", "A number in a hint is refused by §10.3 before the schema.",
       seal(SESSION, {}, raw=(b'{"from":"' + CALLER.encode() + b'","n":1.5}').ljust(256, b" ")),
       rej("sealed-plaintext-invalid"))
    return out


# ---------------------------------------------------------------- the waker's trace

def wake(device, kind, deliver_by, session=None):
    w = {"device": device, "kind": kind}
    if session is not None:
        w["session"] = session
    w["deliver_by"] = deliver_by
    return {"wake": w}


def ended(device, cause):
    return {"ended": {"device": device, "cause": cause}}


def reg_ev(device, identity=BOB, expires_at=NOW + 86400, kinds=None):
    r = {"device": device, "identity": identity, "expires_at": expires_at}
    if kinds is not None:
        r["kinds"] = kinds
    return {"register": r}


def trace(vid, desc, component, steps, refs=None):
    """steps: (at, event, emit, registrations)."""
    evs = [{"event": {"at": at, **ev}} for at, ev, _, _ in steps]
    exp = [{"emit": emit, "registrations": regs} for _, _, emit, regs in steps]
    return wv(f"trace-{vid}", desc, refs or REFS["trace"], {"steps": evs}, exp, {"component": component})


def trace_vectors() -> list[dict]:
    S1, S2 = uid("trace-invite-1"), uid("trace-invite-2")
    P, L = [PHONE], [LAPTOP]
    PL = sorted([PHONE, LAPTOP])
    t = NOW
    out = [
        trace("call-held-wakes", "An invite held for a registered, unbound device wakes it once, until the invite's "
              "expiry.", "relay", [
                  (t, reg_ev(PHONE), [], P),
                  (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 31}},
                   [wake(PHONE, "call", t + 31, S1)], P),
                  (t + 2, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 31}}, [], P),
              ]),
        trace("call-bound-no-wake", "A bound device is delivered to, never woken.", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"bind": PHONE}, [], P),
            (t + 2, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 31}}, [], P),
        ]),
        trace("call-unregistered-no-wake", "A device with no registration is held for and not woken.", "relay", [
            (t, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}}, [], []),
            (t + 1, {"drop": S1}, [], []),
        ]),
        trace("identity-invite-wakes-each-offline-device", "An identity-addressed invite held for two legs wakes each, in "
              "DID order; a bound third leg is not.", "relay", [
                  (t, reg_ev(PHONE), [], P),
                  (t, reg_ev(LAPTOP), [], PL),
                  (t, reg_ev(TABLET), [], sorted(PL + [TABLET])),
                  (t + 1, {"bind": TABLET}, [], sorted(PL + [TABLET])),
                  (t + 2, {"hold": {"session": S1, "devices": [PHONE, TABLET, LAPTOP], "expires_at": t + 32}},
                   [wake(d, "call", t + 32, S1) for d in PL], sorted(PL + [TABLET])),
              ]),
        trace("leg-added-later-wakes", "A leg held later for the same invite is woken then.", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t, reg_ev(LAPTOP), [], PL),
            (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}}, [wake(PHONE, "call", t + 30, S1)], PL),
            (t + 2, {"hold": {"session": S1, "devices": [PHONE, LAPTOP], "expires_at": t + 30}},
             [wake(LAPTOP, "call", t + 30, S1)], PL),
        ]),
        trace("cancel-before-bind-call-ended", "The initiator's cancel drops the held invite: the woken device gets "
              "call-ended.", "relay", [
                  (t, reg_ev(PHONE), [], P),
                  (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}},
                   [wake(PHONE, "call", t + 30, S1)], P),
                  (t + 5, {"drop": S1}, [wake(PHONE, "call-ended", t + 65, S1)], P),
                  (t + 6, {"drop": S1}, [], P),
              ]),
        trace("expiry-before-bind-call-ended", "The held invite expires unbound: call-ended at its expiry, settled at the "
              "next event.", "relay", [
                  (t, reg_ev(PHONE), [], P),
                  (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}},
                   [wake(PHONE, "call", t + 30, S1)], P),
                  (t + 29, {"tick": True}, [], P),
                  (t + 30, {"tick": True}, [wake(PHONE, "call-ended", t + 90, S1)], P),
              ]),
        trace("bind-then-cancel-no-call-ended", "Once the device binds the invite is flushed: a cancel is delivered "
              "through DSIP, not as a wake.", "relay", [
                  (t, reg_ev(PHONE), [], P),
                  (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}},
                   [wake(PHONE, "call", t + 30, S1)], P),
                  (t + 3, {"bind": PHONE}, [], P),
                  (t + 4, {"unbind": PHONE}, [], P),
                  (t + 5, {"drop": S1}, [], P),
              ]),
        trace("call-ended-only-to-woken", "call-ended goes only to the legs that were woken.", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"hold": {"session": S1, "devices": [PHONE, LAPTOP], "expires_at": t + 30}},
             [wake(PHONE, "call", t + 30, S1)], P),
            (t + 2, reg_ev(LAPTOP), [], PL),
            (t + 3, {"drop": S1}, [wake(PHONE, "call-ended", t + 63, S1)], PL),
        ]),
        trace("two-invites-two-wakes", "Each held invite wakes the device; each ends separately.", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}}, [wake(PHONE, "call", t + 30, S1)], P),
            (t + 2, {"hold": {"session": S2, "devices": [PHONE], "expires_at": t + 40}}, [wake(PHONE, "call", t + 40, S2)], P),
            (t + 35, {"drop": S2}, [wake(PHONE, "call-ended", t + 90, S1), wake(PHONE, "call-ended", t + 95, S2)], P),
        ]),
        trace("expired-invite-no-wake", "An invite already expired when held wakes nothing.", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t + 30, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}}, [], P),
        ]),
        trace("kinds-filter", "A device that asked for calls only gets no call-ended.", "relay", [
            (t, reg_ev(PHONE, kinds=["call"]), [], P),
            (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}}, [wake(PHONE, "call", t + 30, S1)], P),
            (t + 2, {"drop": S1}, [], P),
        ]),
        trace("kinds-filter-no-call", "A device that asked for messages only is never woken for a call.", "relay", [
            (t, reg_ev(PHONE, kinds=["message"]), [], P),
            (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}}, [], P),
        ]),
        trace("register-replaces", "A new registration replaces the old: its kinds now apply.", "relay", [
            (t, reg_ev(PHONE, kinds=["message"]), [], P),
            (t + 1, reg_ev(PHONE), [], P),
            (t + 2, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}}, [wake(PHONE, "call", t + 30, S1)], P),
        ]),
        trace("remove-ends", "`remove` ends the registration; a held invite then wakes nothing.", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"remove": PHONE}, [ended(PHONE, "removed")], []),
            (t + 2, {"remove": PHONE}, [], []),
            (t + 3, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}}, [], []),
        ]),
        trace("expires-ends", "A registration ends at its `expires_at` (§12.9), before the event at that instant.", "relay", [
            (t, reg_ev(PHONE, expires_at=t + 10), [], P),
            (t + 9, {"tick": True}, [], P),
            (t + 10, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 40}}, [ended(PHONE, "expired")], []),
        ]),
        trace("expiry-same-instant-no-call-ended", "The invite and the registration expire together: the registration is "
              "not live, so no call-ended.", "relay", [
                  (t, reg_ev(PHONE, expires_at=t + 30), [], P),
                  (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}},
                   [wake(PHONE, "call", t + 30, S1)], P),
                  (t + 30, {"tick": True}, [ended(PHONE, "expired")], []),
              ]),
        trace("revoked-ends", "A revoked delegation ends the device's registration (§7.4).", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t, reg_ev(LAPTOP), [], PL),
            (t + 1, {"revoke": PHONE}, [ended(PHONE, "revoked")], L),
        ]),
        trace("forgotten-ends", "A device the relay forgets (§13.3 retention) loses its registration.", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"forget": PHONE}, [ended(PHONE, "forgotten")], []),
        ]),
        trace("gateway-registration-ended-ends", "`wake.registration-ended` from the gateway ends it.", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"hold": {"session": S1, "devices": [PHONE], "expires_at": t + 30}}, [wake(PHONE, "call", t + 30, S1)], P),
            (t + 2, {"answer": {"device": PHONE, "reason": "wake.registration-ended"}}, [ended(PHONE, "gateway")], []),
            (t + 3, {"drop": S1}, [], []),
        ]),
        trace("gateway-unknown-wake-token-ends", "An unknown `wake.*` answer ends it too (W§8.1 fallback).", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"answer": {"device": PHONE, "reason": "wake.token-revoked"}}, [ended(PHONE, "gateway")], []),
        ], ["W§4.3", "W§8.1"]),
        trace("gateway-rate-limited-keeps", "`transport.rate-limited` keeps the registration.", "relay", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"answer": {"device": PHONE, "reason": "transport.rate-limited"}}, [], P),
        ]),
        trace("message-wakes", "An item stored for the identity wakes each registered, unbound device.", "mailbox", [
            (t, reg_ev(PHONE), [], P),
            (t, reg_ev(LAPTOP), [], PL),
            (t + 1, {"bind": LAPTOP}, [], PL),
            (t + 2, {"store": {"identity": BOB, "class": "application"}}, [wake(PHONE, "message", t + 62)], PL),
        ]),
        trace("message-coalesced", "One message wake per W-Coalesce (60 s) per device.", "mailbox", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"store": {"identity": BOB, "class": "application"}}, [wake(PHONE, "message", t + 61)], P),
            (t + 30, {"store": {"identity": BOB, "class": "welcome"}}, [], P),
            (t + 60, {"store": {"identity": BOB, "class": "application"}}, [], P),
            (t + 61, {"store": {"identity": BOB, "class": "application"}}, [wake(PHONE, "message", t + 121)], P),
        ]),
        trace("message-after-bind-wakes-again", "A binding starts the count afresh.", "mailbox", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"store": {"identity": BOB, "class": "application"}}, [wake(PHONE, "message", t + 61)], P),
            (t + 5, {"bind": PHONE}, [], P),
            (t + 6, {"store": {"identity": BOB, "class": "application"}}, [], P),
            (t + 7, {"unbind": PHONE}, [], P),
            (t + 8, {"store": {"identity": BOB, "class": "application"}}, [wake(PHONE, "message", t + 68)], P),
        ]),
        trace("ephemeral-no-wake", "An ephemeral deposit is never stored, so it wakes nothing.", "mailbox", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"store": {"identity": BOB, "class": "ephemeral"}}, [], P),
        ]),
        trace("message-other-identity", "An item for another identity wakes none of Bob's devices.", "mailbox", [
            (t, reg_ev(PHONE), [], P),
            (t + 1, {"store": {"identity": F.did("carol"), "class": "application"}}, [], P),
        ]),
        trace("message-kinds-filter", "A device that asked for calls only is not woken for messages.", "mailbox", [
            (t, reg_ev(PHONE, kinds=["call", "call-ended"]), [], P),
            (t + 1, {"store": {"identity": BOB, "class": "application"}}, [], P),
        ]),
        trace("message-expired-registration", "A registration expired before the item wakes nothing.", "mailbox", [
            (t, reg_ev(PHONE, expires_at=t + 5), [], P),
            (t + 5, {"store": {"identity": BOB, "class": "application"}}, [ended(PHONE, "expired")], []),
        ]),
    ]
    return out


def vectors() -> list[dict]:
    return schema_vectors() + enrol_vectors() + register_vectors() + gateway_vectors() + hint_vectors() + trace_vectors()
