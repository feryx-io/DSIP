# DSIP Wake Profile (`wake/0.1`)

**Status:** DRAFT, companion profile to DSIP 1.0. Cite as `W§n`. It collects spec-gaps 169–175, decided 2026-10-31
("all (a)") on the outline (`impl/docs/wake-profile-outline.md`); erratum 2026-10-31 (W§5.2 `session`, W§6
`on_behalf_of`: an invite carries neither field), found implementing the relay; spec-gap 176 (W§4.2, a mailbox's
owner operation) decided 2026-11-01, found implementing the mailbox; spec-gap 178 (W§3, W§5.3: an iOS device's two
APNs tokens) decided 2026-11-06, found implementing the iOS app. It adds message types, a credential
and a capability member, which §11.4 allows in 1.x (spec-gap 163 (a)). Schemas: `v1.0/dsip-wake-schemas-draft/`.
Conformance: the `wake/` vectors.

The core already assigns the job: reaching a device that is asleep "is the responsibility of the relay
store-and-forward layer", mobile wake-up "requires platform push services, which are centralized", and "the push
payload need carry nothing but a wake signal" (§13.3). This profile says how a device asks to be woken, who may wake
it, and what a wake carries. iOS and Android end a background app's sockets; without a wake, a phone rings only while
its app is open.

## W§1 Scope

This profile defines:

- the **push gateway**, a service identity that holds an app publisher's push credentials and forwards wakes (W§2);
- **enrolment**: a device gives a gateway its platform push token and receives an opaque **handle** (W§3);
- **registration**: a device permits each of its **wakers**, its relay and its mailbox, to wake it (W§4);
- **waking**: when a waker wakes a device, and what a wake carries (W§5, W§6);
- the profile's timers (W§7), reason tokens (W§8) and security considerations (W§9).

Out of scope: Web Push (RFC 8030), which needs no gateway; notifications shown to the person (a wake is not a
notification; the woken app decides what to show); how an app reports a call to the platform's call screen.
Reachability never depends on a wake: a waker that does not implement this profile delivers as §13.3 says.

## W§2 Roles

- **Device**: one app install, a delegated device (§7.4). It holds a platform push token: an FCM registration token on
  Android; on iOS two, a PushKit VoIP token for calls and an APNs alert token for messages, as APNs takes each for
  its own topic only (spec-gap 178).
- **Push gateway**: a `service`-class identity (§7.1) run by the app's publisher, the only party holding the APNs key
  and FCM account the app's pushes need. Its DID document names a service entry of type `DSIPWake` whose
  `serviceEndpoint` is an `https` URI.
- **Waker**: a relay (§13.6) for calls, or a mailbox (M§4) for messages, that serves the device's identity.

```
device ──wake-enrol (platform token)───────────────────────► gateway
device ◄────────────────────────────── wake-accepted (handle) gateway
device ──wake-register (registration naming the waker)─────► relay / mailbox
         … the device sleeps; an invite for it is held (§13.3) …
relay ───wake (registration, kind, session, sealed hint)───► gateway ──► APNs / FCM ──► device
device ──hello (§13.2)─────────────────────────────────────► relay, which flushes the held invite as usual
```

A wake never carries the traffic: the woken device binds and receives it through DSIP, signed end to end.

Every message of this profile names `wake/0.1` in `dsip.profiles`.

### W§2.1 Reaching the gateway (spec-gap 173)

A device or a waker sends the gateway one signed envelope (§10.2) as the body of an HTTPS `POST` to its `DSIPWake`
endpoint, `Content-Type: application/dsip+json`. The gateway answers `200` with one signed envelope: `wake-accepted`,
or a core `error` whose `in_reply_to` names the request and whose `reason` is a W§8 token. Every other HTTP status is
a transport failure. The gateway verifies the request as any receiver does (§10.2, §12.9, the 300 s replay window,
its own `seen_ids`); `to` is the gateway's DID.

## W§3 Enrolment at the gateway (spec-gaps 173, 175, 178)

A device makes a **wake key**: an Ed25519 key pair for this enrolment, never used for anything else. It sends:

```json
{
  "dsip": {"core": "1.0", "min_core": "1.0", "profiles": ["wake/0.1"], "extensions": [], "critical": []},
  "type": "wake-enrol",
  "id": "01K8S0E8M0000000000ENROL001",
  "from": "did:key:z6MkWakeKey",
  "to": "did:web:push.dsip.example",
  "provider": "apns",
  "app": "org.dsip.app.voip",
  "environment": "production",
  "token": "<the platform token>",
  "issued_at": 1790000000,
  "expires_at": 1790000030
}
```

- `from` is the `did:key` of the wake key, which signs the envelope. It has no delegation and names no identity: the
  gateway never learns the device's DID (spec-gap 175).
- `provider`: registry `dsip-wake-provider` (W§8.2), `apns` or `fcm`.
- `app`: the APNs topic of the token, the bundle ID with `.voip` for a PushKit VoIP token or the bundle ID for an
  alert token, or the FCM project ID.
- `environment`: APNs only, `production` (the default) or `sandbox`. Ignored for `fcm`.
- `token`: the platform token, at most 4,096 characters.

The gateway refuses an app or provider it does not push for with `wake.unsupported-app`, and otherwise answers
`wake-accepted` with `handle`: an opaque string of at most 512 base64url characters that only it can read, standing
for the provider, the app, the environment, the token and the wake key. How it makes one is its own choice (an AEAD
of those values under a key of its own keeps it stateless). A new platform token means a new enrolment. An enrolment
is one token: an iOS device enrols its VoIP token and its alert token apart, each under its own wake key, and has a
handle for each (spec-gap 178).

```json
{
  "dsip": {"core": "1.0", "min_core": "1.0", "profiles": ["wake/0.1"], "extensions": [], "critical": []},
  "type": "wake-accepted",
  "id": "01K8S0E8M1000000000ACCEPT01",
  "from": "did:web:push.dsip.example",
  "to": "did:key:z6MkWakeKey",
  "in_reply_to": "01K8S0E8M0000000000ENROL001",
  "handle": "<opaque>",
  "issued_at": 1790000001,
  "expires_at": 1790000031
}
```

## W§4 Registration with a waker (spec-gaps 169, 170, 174)

### W§4.1 The registration

A **registration** is a credential in the delegation's form (§7.4): a DSIP-JOSE envelope whose payload is

```json
{
  "type": "WakeRegistration",
  "key": "did:key:z6MkWakeKey",
  "waker": "did:web:relay.example.com",
  "gateway": "did:web:push.dsip.example",
  "handle": "<opaque>",
  "issued_at": 1790000002,
  "expires_at": 1792592002
}
```

signed by the wake key, `kid` a key of `key`. It is the named waker's permission to ask the named gateway to wake
the handle, and no one else's (spec-gap 169). Like a delegation it is verified by its signature and its fields, with
no replay window: it is presented for its whole lifetime. `expires_at` − `issued_at` is at most W-Registration
(W§7).

### W§4.2 `wake-register` (spec-gaps 170, 176)

A device sends its registration to a waker over its binding (§13.2):

```json
{
  "dsip": {"core": "1.0", "min_core": "1.0", "profiles": ["wake/0.1"], "extensions": [], "critical": []},
  "type": "wake-register",
  "id": "01K8S0E8M2000000000REGIST01",
  "from": "did:key:z6MkBobPhone",
  "to": "did:web:relay.example.com",
  "registration": {"protected": "…", "payload": "…", "signature": "…"},
  "seal_key": "<base64url X25519 public key>",
  "kinds": ["call", "call-ended"],
  "issued_at": 1790000002,
  "expires_at": 1790000032
}
```

- `seal_key` (optional): the X25519 public key a relay seals W§6's hint to. Without it no hint is sent.
- `kinds` (optional): the W§5 kinds the device wants; absent, every kind the waker sends.
- `remove: true` in place of `registration`, `seal_key` and `kinds` ends the device's registration at this waker.

The waker verifies the envelope as any message on the binding, then, in this order, refusing with a core `error`:

1. the registration verifies: its signature by a key of `key` (a `did:key`, resolved as §7.2), its payload of the
   `WakeRegistration` schema; otherwise `wake.registration-invalid`;
2. `waker` is this waker's DID; otherwise `wake.waker-mismatch`;
3. `issued_at` < `expires_at` ≤ `issued_at` + W-Registration, `expires_at` > now, `issued_at` ≤ now + 300 s;
   otherwise `wake.registration-invalid`;
4. the waker will use `gateway`: its own policy, which MAY admit any; otherwise `wake.gateway-unknown`.

It answers `wake-accepted` and keeps one registration per device: the `wake-register` signer's device DID. A new one
replaces it. A device registers the handle whose push suits the waker's kinds: with a relay (`call`, `call-ended`) an
iOS device's VoIP handle, with a mailbox (`message`) its alert handle (spec-gap 178). No capability is needed beyond binding's (§13.2; M§4.3 for a mailbox). A mailbox treats `wake-register`
as an owner operation (M§4.1) before these checks: an identity it does not serve enrols by it, or is refused
`mailbox.not-served` (spec-gap 176).

### W§4.3 When a registration ends (spec-gap 174)

A waker forgets a device's registration:

- at its `expires_at`;
- when the device sends another (replaced) or `remove: true`;
- when the gateway answers a `wake` with `wake.registration-ended`, `wake.not-authorized`, or any `wake.*` token it
  does not know (W§8);
- when the device's delegation is revoked or expires (§7.4);
- when the waker forgets the device: a relay at the end of §13.3's retention window, a mailbox when the device stops
  being a registered device (M§4.4).

A device registers again on every binding at which its registration has less than half its lifetime left, and at
once when its platform token changes.

### W§4.4 Advertising

A waker that implements this profile says so in its `hello` capabilities (§13.2, §11.4):

```json
"wake": {"profiles": ["wake/0.1"], "kinds": ["call", "call-ended"]}
```

`kinds` lists the W§5 kinds it sends. A device does not send `wake-register` to a waker that does not advertise the
profile. The core's informative `push_wake` capability is not read by this profile.

## W§5 Waking (spec-gaps 172, 173)

### W§5.1 When

A waker wakes a device that has a registration, is not bound, and whose registration's `kinds` (if any) include the
kind:

- **`call`** (a relay): when it holds an `invite` for the device (§13.3): addressed to the device, or to its identity
  and held for the device as one of the attempt's legs (§12.7). One per held invite per device.
- **`call-ended`** (a relay): when an `invite` it woke the device for stops being held before the device bound: the
  initiator's `cancel` dropped it, or it expired. Apple requires a woken app to report a call at once; this ends that
  call on the screen. Once the device binds, the held invite is flushed and the call proceeds, or ends, through DSIP.
- **`message`** (a mailbox): when it stores an item for the device's identity (M§5.2), other than an `ephemeral`
  deposit (M§11.2), which is never stored. At most one per W-Coalesce per device; the device's binding starts the
  count afresh.

Nothing about a wake changes call signaling. A device that binds in time receives the held invite as §13.3 says; one
that does not is unreachable like any other, and the initiator's T-Establish (§12.10) ends the attempt.

### W§5.2 `wake`

```json
{
  "dsip": {"core": "1.0", "min_core": "1.0", "profiles": ["wake/0.1"], "extensions": [], "critical": []},
  "type": "wake",
  "id": "01K8S0E8M3000000000WAKE0001",
  "from": "did:web:relay.example.com",
  "to": "did:web:push.dsip.example",
  "registration": {"protected": "…", "payload": "…", "signature": "…"},
  "kind": "call",
  "session": "01K8S0E8M3000000000INVITE01",
  "sealed": {"alg": "hpke-base-x25519-sha256-aes128gcm", "enc": "…", "ct": "…"},
  "deliver_by": 1790000060,
  "issued_at": 1790000030,
  "expires_at": 1790000060
}
```

- `registration`: the device's, exactly as received.
- `kind`: registry `dsip-wake-kind` (W§8.2). An unknown kind is treated as `message`.
- `session`: the session id, which is the invite's `id` (§12.2), required for `call` and `call-ended`, absent
  otherwise.
- `sealed`: W§6, `call` only, optional.
- `deliver_by`: after it the wake is useless. For `call` the held invite's `expires_at`; for `call-ended` the time
  of the drop plus W-Call-Ended; for `message` the time of the item plus W-Coalesce.

A waker MAY retry a `wake` that failed in transport (W§2.1) once, before `deliver_by`. It never resends one that was
answered.

### W§5.3 At the gateway

The gateway verifies the envelope (W§2.1), then refuses in this order:

1. `wake.not-authorized` unless every one holds: `handle` is one it issued; the registration verifies (W§4.2 step 1)
   and its `key` is the handle's wake key; its `waker` is the `wake`'s `from`; its `gateway` is the gateway's own
   DID; its `expires_at` is after now;
2. `wake.expired` when `deliver_by` ≤ now.

Otherwise it forwards to the handle's provider and answers `wake-accepted` with no `handle`. "Accepted" means
handed to the provider, never delivered: neither APNs nor FCM reports delivery. The push's **class** is `call` for
`call` and `call-ended`, `message` otherwise:

| class | APNs | FCM |
|---|---|---|
| `call` | `apns-push-type: voip`, priority 10, topic the handle's `app` | `priority: high` data message |
| `message` | `apns-push-type: alert` with `mutable-content: 1`, priority 10, topic the handle's `app` | `priority: high` data message |

The expiry is `deliver_by` (APNs `apns-expiration`, FCM `ttl`, at least 0). The data the app receives is, as compact
JSON (APNs: a top-level key beside `aps`; FCM: one data field, `dsip-wake`, holding it as a string):

```json
{"dsip-wake": {"kind": "call", "waker": "did:web:relay.example.com", "session": "01K8S0E8M3000000000INVITE01", "sealed": {"alg": "…", "enc": "…", "ct": "…"}}}
```

with `session` and `sealed` only when the `wake` had them. When the provider reports the token unknown (APNs 410,
FCM `UNREGISTERED`), the gateway answers that and every later wake for the handle `wake.registration-ended`. It
bounds wakes per handle and per waker, answering `transport.rate-limited` with `retry_after`.

### W§5.4 At the device

The woken app binds to the waker named in the data (and its other relays, as usual). On iOS a `call` is reported to
CallKit at once, a `call-ended` reports the call it names ended (or a call ended at once, if none is shown), and a
`message` is handled by a notification service extension that may sync before showing anything. A call shown from
a wake whose invite has not arrived within T-Establish's maximum (60 s, §12.10) is ended. A wake proves nothing: the
app trusts only what arrives through DSIP and verifies (§8.1).

## W§6 What a wake shows (spec-gap 171)

The gateway and the provider see every wake, so a `call`'s caller travels sealed. `sealed` is HPKE base mode with the
suite of M§6.9 (`hpke-base-x25519-sha256-aes128gcm`) to the registration's `seal_key`, `info`
`"dsip wake hint v1"`, AAD the UTF-8 of the `session`. The plaintext is the compact JSON
`{"from":"<the invite's from>","on_behalf_of":"<the identity its signer acts for>"}`, followed by spaces to exactly
256 bytes; a hint that would be longer is not sent. An invite carries no `on_behalf_of`: the identity is the subject of
the delegation binding its signer (§7.4), which the relay knows from the caller's binding (§13.2); it is left out
when it is the `from` itself.

The app opens it, shows the contact it already holds for the DID (or "unknown"), and replaces that with what the
verified invite says once it arrives. The hint is the relay's claim: the app MUST NOT treat it as the caller's
identity, and MUST show a call from a DID it does not know as from an unknown caller.

## W§7 Timers

| timer | value | meaning |
|---|---|---|
| W-Registration | 2,592,000 s (30 days) | the longest registration, `expires_at` − `issued_at` |
| W-Coalesce | 60 s | a mailbox's minimum gap between `message` wakes to one device |
| W-Call-Ended | 60 s | how long a `call-ended` wake is worth delivering |

## W§8 Registries

### W§8.1 Reason tokens

Category **`wake`** (new in §15.1). Fallback for an unknown `wake.*` condition: the registration is ended (W§4.3);
the device registers again on its next binding.

| token | meaning | valid on |
|---|---|---|
| `wake.registration-invalid` | the registration does not verify, or its lifetime is outside W§4.2 | error |
| `wake.waker-mismatch` | the registration names another waker | error |
| `wake.gateway-unknown` | the waker will not use this gateway | error |
| `wake.unsupported-app` | the gateway does not push for this provider and app | error |
| `wake.not-authorized` | the registration does not authorize this waker at this gateway | error |
| `wake.expired` | `deliver_by` has passed | error |
| `wake.registration-ended` | the provider no longer knows the platform token | error |

### W§8.2 Registries requested

- `dsip-wake-provider`: shape `[a-z][a-z0-9-]*`; `apns`, `fcm`. A gateway refuses one it does not push through
  (`wake.unsupported-app`).
- `dsip-wake-kind`: shape `[a-z][a-z0-9-]*`; `call`, `call-ended`, `message`; fallback `message`.
- `dsip-message-type`: `wake-enrol`, `wake-accepted`, `wake-register`, `wake`.
- `dsip-profile`: `wake/0.1`.
- DID service type `DSIPWake`.

## W§9 Security and privacy considerations

- **The gateway learns** the platform tokens, which wakers wake which handles, and when: when a person is called or
  messaged, and through which relay and mailbox. It does not learn the device's DID or identity (W§3), the caller
  (W§6), or any content. This is the platform dependency §13.3 states, for delivery latency and not for trust.
- **The waker learns** the gateway, so which app the device runs; it already holds the traffic.
- **A handle alone wakes nothing**: the gateway needs a registration, signed by the handle's wake key, naming the
  waker that signed the wake. A waker that misuses its registration is bounded by the gateway's rate limits and
  ended by the device's `remove`.
- **A false wake** (one with nothing held) costs battery and, on iOS, a call shown and ended. Rate limits bound it.
- **No authority** (§8.1): a wake and its hint prove nothing; only verified DSIP traffic does.

## W§10 Spec-gaps

| gap | section | decision |
|---|---|---|
| 169 | W§4.1 | a device-signed registration naming the waker, shown with each wake |
| 170 | W§4.2 | a `wake-register` message, held beyond the binding |
| 171 | W§6 | kind and session, plus the caller's DID sealed to the device |
| 172 | W§5.1 | `call` per held invite, `call-ended`, `message` coalesced, one transport retry |
| 173 | W§2.1 | an HTTPS `POST` of a signed envelope to `DSIPWake` |
| 174 | W§4.3 | `expires_at` (W-Registration), replacement, `remove`, gateway answers, revocation, retention |
| 175 | W§3 | a per-enrolment wake key, not the device DID |
| 176 | W§4.2 | at a mailbox, `wake-register` is an owner operation (M§4.1) |
| 178 | W§3, W§4.2, W§5.3 | one APNs token per enrolment: an iOS device enrols its VoIP and alert tokens apart, registering each with the waker whose kinds it suits |
