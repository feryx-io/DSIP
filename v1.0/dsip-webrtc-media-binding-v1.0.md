# DSIP WebRTC Media Binding — `transport:webrtc` 1.0

**Status:** companion document to DSIP 1.0 — normative for `transport:webrtc` 1.0, unchanged from its v0.7
text. Conformance: the `media-binding/` category of the vector suite (`impl/vectors/media-binding/`, 42 vectors, Rust/Python
parity) pins B§2–B§6; resolves spec-gap 16 (`impl/docs/spec-gaps.md`).
**Editor's note:** written from the behaviour of the v0.6 reference implementation
(`impl/crates/dsip-endpoint`, `dsip-media` on webrtc-rs, `impl/demos/browser`) and intended to be
the contract a second media backend (forge-media) implements. Where this document and the
implementation differ, this document wins and the implementation changes.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY are to be interpreted as in
RFC 2119 / RFC 8174.

---

## 1. Scope

DSIP Core defines *what* is negotiated — media descriptors, direction, purpose, policy — and the
messages that carry the negotiation (`invite`, `answer`, `update`, `info`; Core §14, §16). A
**media transport binding** defines how a selected transport actually moves media. This
document is the binding for WebRTC: RTP/SRTP keyed by DTLS, candidate discovery by ICE, described
in SDP.

This binding defines:

1. the shape of the `transport:webrtc` transport descriptor and where SDP rides (§2);
2. the mapping between DSIP roles and SDP offer/answer roles, including DTLS role (§3);
3. ICE candidate exchange through signed `info` envelopes (§4);
4. renegotiation through `update` (§5);
5. behaviour under forking and screening (§6);
6. the identity-to-media binding that makes DTLS-SRTP *verified* media (§7);
7. failure handling and reason tokens (§8);
8. rate expectations (§9), registry entries (§10), and conformance (§11).

Out of scope for binding version 1.0 and explicitly **unsupported**: ICE restart (§5.4), data
channels, simulcast/SVC, SFrame end-to-end encryption (Core §6.2 reserves it), and any media
before `answer` (Core §14.1 forbids it).

## 2. The transport descriptor

A `transport:webrtc` descriptor is a member of `transports[]` on `invite`, `update` (offers) and
`answer` (selection). Its shape:

```json
{
  "id": "transport:webrtc",
  "ice": "trickle",
  "sdp": "v=0\r\no=- 4611731400430051336 2 IN IP4 127.0.0.1\r\n..."
}
```

- `id` (required): the registered transport identifier `transport:webrtc` (Core §16, registry
  `dsip-transport`).
- `ice` (required on offers, optional on answers): the candidate-exchange mode. Binding 1.0
  defines exactly one value, `trickle`. An offer with any other value MUST be rejected with
  `media.unsupported`. When present on an answer it MUST be `trickle`.
- `sdp` (required): the complete SDP offer (on `invite`/`update`) or SDP answer (on `answer`) as
  a single string with CRLF line endings, exactly as produced by the endpoint's WebRTC stack. An
  `invite` or `update` selecting this transport without `sdp` MUST be rejected with
  `media.offer-required`; an `answer` without it is not a valid selection and the initiator MUST
  treat the session as failed (§8).

### 2.1 Authority between descriptors and SDP

Core §16.3 requires the binding to say which of the structured descriptors and the SDP is
authoritative when both are present. The rule:

- **Media descriptors** (`media[]`) are authoritative for **what was negotiated**: the set of
  media, each one's `type`, `direction`, `purpose`, selected `codecs[].id`, and the session
  `policy`. These are what the DSIP state machine, the screening pattern, and the UI act on.
- **SDP** is authoritative for **transport parameters**: ICE credentials and candidates, DTLS
  fingerprint and `a=setup` role, RTP payload-type numbers and codec parameters, `a=mid`,
  BUNDLE, rtcp-mux, extmap and RTCP feedback. These are what the media stack acts on.

The two MUST be consistent:

- `media[i]` corresponds to the *i*-th non-rejected `m=` section of the SDP, in order. Binding
  1.0 permits no other `m=` sections (no `m=application`); an offer containing one MUST be
  rejected with `media.unsupported`.
- The `m=` section's kind MUST equal `media[i].type`; its direction attribute MUST equal
  `media[i].direction`; for each `codecs[j].id` in the descriptor there MUST be an `a=rtpmap`
  for the mapped codec (§3.4) — the descriptor lists what is offered/selected, the SDP MAY carry
  additional payload types (e.g. RTX, RED, telephone-event) that DSIP does not describe.
- A receiver that detects an inconsistency in an offer MUST reject it with `media.unsupported`
  and SHOULD say which `m=` section in `detail`. An inconsistency in an answer is a failure of
  the accepted leg: the initiator MUST send `bye` with `media.failed`.

### 2.2 SDP profile

Offers and answers MUST use: `a=group:BUNDLE` over all `m=` sections, `a=rtcp-mux`,
`a=fingerprint:sha-256`, `a=setup` per §3.3, and ICE attributes per §4. `a=ice-lite` MUST NOT be
used by endpoints. These are the defaults of every WebRTC stack and are stated only so that a
non-browser backend cannot quietly diverge.

## 3. Roles and offer/answer

### 3.1 Role mapping

| DSIP role | SDP role | DTLS role |
|---|---|---|
| initiator (`invite`) | offerer | `actpass` |
| responder (`answer`) | answerer | `active` |
| `update` sender | offerer for that renegotiation | `actpass` |
| `update` answerer | answerer for that renegotiation | `active` |

Core §14.2's rule — an answer is a selection, never a counter-offer — is inherited verbatim: the
SDP in an `answer` MUST be an SDP *answer* to the SDP in the referenced offer (RFC 3264). A
responder that needs different media sends an `answer` selecting what it will do now and then
sends `update` (§5); it MUST NOT put a second offer in `answer`.

### 3.2 Offer construction

The offerer MUST create its SDP from the same peer connection it will use for media, set it as
its local description, and place it in the descriptor. The SDP MAY contain candidates already
gathered (`a=candidate`) and MAY be produced before gathering completes (§4.1); an offer with no
inline candidates is valid.

### 3.3 DTLS role

The offer MUST carry `a=setup:actpass`. The answer MUST carry `a=setup:active`; the answerer
therefore initiates the DTLS handshake as soon as ICE has a usable pair. `a=setup:passive` in
an answer is permitted only if the offer was `actpass` and the answerer cannot act as client;
`a=setup:holdconn` MUST NOT be used. (RFC 8842 §5.3 makes `active` a SHOULD; binding 1.0 makes
it a MUST so that a single-leg endpoint never needs the server-side DTLS path.)

### 3.4 Codec identifier mapping

DSIP codec identifiers (Core §16.2) map to SDP as follows. Only Opus is mandatory for every endpoint
(Core §17.1 "at least one audio codec", §17.2). An endpoint that offers or accepts video MUST
support `codec:video/h264` in the constrained baseline profile (`profile-level-id=42e01f`,
`packetization-mode=1`), and SHOULD support `codec:video/vp8`, so that any two endpoints doing
video share a codec (spec-gap 181). The other codecs are optional.

| DSIP `codecs[].id` | `a=rtpmap` | parameters |
|---|---|---|
| `codec:audio/opus` (REQUIRED) | `opus/48000/2` | `sample_rates` ⊆ {8000…48000} is advisory; `channels` → `stereo`/`sprop-stereo` fmtp; `ptime` 20 ms default |
| `codec:audio/pcmu` | `PCMU/8000` | — |
| `codec:audio/pcma` | `PCMA/8000` | — |
| `codec:audio/g722` | `G722/8000` | the clock rate is 8000 although the audio is 16 kHz (RFC 3551 §4.5.2) |
| `codec:video/h264` (REQUIRED for video) | `H264/90000` | `profiles[]` → `profile-level-id` (`baseline` = `42e01f`), `packetization-mode=1` |
| `codec:video/vp8` (RECOMMENDED for video) | `VP8/90000` | — |
| `codec:video/vp9` | `VP9/90000` | — |
| `codec:video/av1` | `AV1/90000` | — |

Every row is a mapping that §2.1's consistency rule applies to: a descriptor listing one of these
codecs needs the row's `a=rtpmap` in the same `m=` section (spec-gap 182). A codec with no row has
no mapping in binding 1.0, and §2.1 does not check it.

Payload-type numbers are SDP-local and never appear in DSIP descriptors.

## 4. ICE candidate exchange

### 4.1 Trickle is the only mode

**ICE servers and TURN credentials** (v0.12, spec-gap 114). STUN and TURN servers reach an endpoint as
configuration; nothing in DSIP signaling carries them, and a relay's `hello` does not (§13.2). Short-lived TURN
credentials are expected to reach a client by the TURN REST API convention (username `<expiry>:<name>`, password
`HMAC-SHA1(secret, username)`), minted by the origin that serves the client or by its operator's own means.

Binding 1.0 requires full ICE (RFC 8445) with trickle (RFC 8838). An endpoint MAY inline
candidates it has already gathered into the SDP; every candidate gathered afterwards, and the
end-of-candidates indication, ride in `info` as defined below. An endpoint that has finished
gathering before it sends its SDP still sends one `info` with `end_of_candidates: true`.

### 4.2 Carriage: `info` with `about: "transport:webrtc"`

Candidates MUST be sent only inside signed, session-scoped `info` envelopes (Core §12.12, §16.3).
The `data` object for this binding (schema in Appendix A):

```json
{
  "about": "transport:webrtc",
  "data": {
    "candidates": [
      {
        "candidate": "candidate:842163049 1 udp 1677729535 203.0.113.7 61481 typ srflx raddr 10.0.0.5 rport 61481",
        "sdp_mid": "0",
        "sdp_m_line_index": 0
      }
    ],
    "end_of_candidates": false
  }
}
```

- `candidates` (required, array, MAY be empty): each entry carries the `candidate` attribute
  value (the text after `a=`, including the `candidate:` prefix), the `sdp_mid` of the `m=`
  section it belongs to (required — BUNDLE means one section carries the transport but the mid
  still disambiguates), and `sdp_m_line_index` (optional, integer ≥ 0).
- `end_of_candidates` (required, boolean): `true` on the batch that completes gathering for the
  current offer/answer. A sender MUST send `true` exactly once per local description; a receiver
  MUST tolerate a repeated `true` and MUST ignore candidates that arrive after it.
- Entries MUST NOT carry a `username_fragment`: binding 1.0 has no ICE restart, so the ufrag is
  always the one in the current SDP.

### 4.3 Timing: ACTIVE-only and buffering

`info` is valid only in ACTIVE (Core §12.12). Consequences both endpoints MUST implement:

1. **Initiator.** Candidates gathered between sending `invite` and receiving `answer` are
   buffered locally and sent in the first `info` after the transition to ACTIVE, coalesced into
   as few envelopes as possible. They MUST NOT be sent in `update` or any other message.
2. **Responder.** Candidates gathered while constructing the answer are likewise buffered until
   the responder's own ACTIVE transition (which is when it *sends* `answer`) and sent
   immediately after the `answer` envelope, in order.
3. **Receiving before the remote description is applied.** An endpoint MUST buffer remote
   candidates that arrive before the SDP they belong to has been applied (possible at the
   initiator when `info` overtakes the host's processing of `answer`) and apply them in arrival
   order once it is. Buffered candidates MUST be dropped, not applied, if the session ends or the
   offer they belong to is superseded.
4. Candidates MUST be applied in the order received from a given sender; the relay's ordered
   per-sender delivery (Core §13.2) is relied upon here.

### 4.4 Attribution

A receiver MUST apply candidates only from the device that is party to the media session: the
signer of the accepted `answer` (at the initiator) or the signer of the `invite`/current offer
(at the responder). `info` from any other device for the same `session` — e.g. a leg whose answer
was not accepted (§6.1) — MUST be ignored silently. Because `info` is signed and session-scoped,
candidate injection requires a device-key compromise, which is the property Core §12.12 asks
this binding to preserve; an implementation MUST NOT accept candidates from any unsigned side
channel.

## 5. Renegotiation

### 5.1 `update` carries a full re-offer

An `update` MUST carry a complete SDP offer generated from the **same** peer connection, with
the same ICE credentials (§5.4) and, unless the certificate changed, the same DTLS fingerprint.
Its `media[]` describes the full desired state, not a delta (Core §12.8 rule 1: "MUST carry a
media offer"). The answer to an `update` is an `answer` with `in_reply_to` carrying a full SDP
answer; the state machine rules of Core §12.8 (one outstanding, glare by smaller `id`, `bye`
wins) apply unchanged.

### 5.2 Applying and rejecting

The `update` sender MUST set the new offer as its local description before sending, and MUST
apply the answer's SDP on receipt of `answer`. On `reject` (or `session.glare`), the sender MUST
**roll back** its local description to the pre-update state so that the media path is exactly
the last negotiated one (Core §12.8 rule 5). Stacks without native rollback MUST achieve the same
by re-applying the prior local description.

The `update` receiver MUST NOT apply the offer's SDP to its peer connection until it has decided
to answer; a rejected update leaves its peer connection untouched.

### 5.3 Adding media

Escalation — adding video, or a screener moving from `recvonly` to `sendrecv` (§6.2) — is an
`update` whose offer adds tracks / changes direction on existing `m=` sections. New media
appends `m=` sections; `media[]` order in the descriptor MUST follow `m=` order (§2.1), so
already-negotiated media keep their index and `sdp_mid`.

### 5.4 ICE restart: unsupported in 1.0

An `update` whose SDP changes `ice-ufrag`/`ice-pwd` on any `m=` section is an ICE restart.
Binding 1.0 does not support it: the receiver MUST reject the update with `media.unsupported`
(`detail: "ice-restart"`), and the session continues on the existing candidate pair. An endpoint
that loses connectivity and cannot recover without restart ends the session with `bye`
`media.failed`. A later binding version will define restart together with a `username_fragment`
on candidates; implementations MUST NOT half-implement it.

## 6. Forking and screening

### 6.1 One answer per offer

Under relay forking (Core §12.7) every leg receives the same SDP offer and each answering leg
returns its own SDP answer with its own ICE credentials and DTLS fingerprint. The initiator MUST
apply exactly one answer — the first valid one — and release every later leg with `bye`
`session.already-answered` (Core §12.7, spec-gap 5/12). Candidates from released legs are
ignored per §4.4. Because media keys are derived by DTLS per leg and only one answer is ever
applied, forked media cannot occur (Core §14.1).

### 6.2 Screening (Core §14.4)

A screening `answer` (`answered_by: "screening"`) selects `recvonly` audio in `media[]` and its
SDP answer carries `a=recvonly` on that section (the caller therefore sends, the screener does
not). The screener's peer connection MUST NOT have a sending track at that point. Escalation is
an `update` from the screener re-offering `sendrecv` (and any added video) with
`answered_by: "user"` permitted on the update; the caller answers it as in §5. Declining is
`bye` `user.declined`.

## 7. Identity-bound media

The SDP — and therefore the DTLS certificate fingerprint inside it — is part of a payload signed
by a delegated device key (Core §10.2, §7.4). This is what turns DTLS-SRTP into *verified* media:

- An endpoint MUST verify that the certificate presented in the DTLS handshake matches the
  `a=fingerprint` in the peer's signed SDP (offer or answer as appropriate) and MUST abort the
  handshake and the session (`bye` `media.failed`) on mismatch.
- An endpoint MUST NOT begin ICE connectivity checks or DTLS toward a peer until it is in ACTIVE
  (initiator: valid `answer` applied; responder: `answer` sent) — Core §14.1 has no exceptions.
- DTLS-SRTP with AES-GCM or AES-CM-128-HMAC-SHA1-80 is REQUIRED (Core §17.2 encryption floor);
  plain RTP MUST NOT be offered or accepted (`media.encryption-required` on an offer that tries).
- Media policy (`policy`, Core §16.4) is negotiated in the descriptors; this binding does not
  change it, but a `derivative-bound` or `recording: denied` policy is a claim enforced by the
  endpoints, not by the transport.

## 8. Failure handling

| condition | where | action |
|---|---|---|
| offer without `sdp` | PROCEEDING / update | `reject` `media.offer-required` |
| `ice` ≠ `trickle`, extra `m=` sections, descriptor/SDP inconsistency, ICE restart | offer / update | `reject` `media.unsupported` (+ `detail`) |
| plain RTP offered | offer | `reject` `media.encryption-required` |
| answer SDP missing or inconsistent, fingerprint mismatch | ACTIVE | `bye` `media.failed` |
| ICE fails to connect / DTLS fails | ACTIVE | `bye` `media.failed` after the endpoint's own connectivity timeout (SHOULD be ≥ 30 s, ≤ T-Answer) |
| candidate flood | ACTIVE | `error` `policy.rate-limited` (§9), then `bye` `media.failed` if it persists |

Rejecting an `update` for any of these reasons MUST NOT end the session (Core §12.8 rule 5).

## 9. Rate expectations

Core §12.12 asks bindings to define rate expectations. Binding 1.0:

- Senders SHOULD coalesce candidates gathered within 50 ms into one `info` and SHOULD NOT send
  more than 10 `info` per second per session.
- Receivers MUST accept at least 32 `info` envelopes and 128 candidates per session per local
  description without rate-limiting; beyond that they MAY respond with `error`
  `policy.rate-limited` and drop the excess. The limit resets on each accepted `update`.
- Relays apply their own transport-level limits (`transport.rate-limited`, Core §13.2) and MUST
  NOT inspect `data`.

## 10. Registry entries

- `dsip-transport`: `transport:webrtc` — this document.
- `dsip-info-about`: `transport:webrtc` — `data` per Appendix A.
- `dsip-ice-mode` (new, governed by this binding): `trickle`.
- No new reason tokens; the `media.*` tokens of Core §15.4 cover every condition in §8.

## 11. Conformance and the Core edits this document implies

An endpoint claiming `transport:webrtc` 1.0 MUST implement §2–§7 as offerer **and** answerer
(an answer-only or offer-only endpoint is not conformant — it cannot renegotiate), MUST document
how it enforces Core §14.1, and MUST pass the `media-binding/` vectors of the conformance suite (their
`info.data` schema is Appendix A, published as `webrtc-info-data.schema.json` in the v0.7 schema set).

Edits to Core for v0.7 carried by this binding (spec-gap 16):

1. §12.12 — "normative in the WebRTC Media Binding document" → cite this document.
2. §16.3 — replace the `transport_binding: {type, sdp}` example with the §2 descriptor form and
   the §2.1 authority rule.
3. §26 step 8 — "ICE candidates ride in signed `update` envelopes" → `info`.
4. §17.2 — name `transport:webrtc` 1.0 as the recommended browser binding.
5. §12.7 — add the one-answer-per-offer sentence of §6.1.

---

## Appendix A. Schema for `info.data` when `about` is `transport:webrtc`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://dsip.org/schema/1.0/binding/webrtc/info-data.schema.json",
  "title": "transport:webrtc info.data",
  "type": "object",
  "properties": {
    "candidates": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "candidate": {"type": "string", "pattern": "^candidate:", "maxLength": 512},
          "sdp_mid": {"type": "string", "maxLength": 64},
          "sdp_m_line_index": {"type": "integer", "minimum": 0}
        },
        "required": ["candidate", "sdp_mid"],
        "additionalProperties": false
      },
      "maxItems": 64
    },
    "end_of_candidates": {"type": "boolean"}
  },
  "required": ["candidates", "end_of_candidates"],
  "additionalProperties": false
}
```

Note for the v0.7 suite: the v0.6 reference implementation emits `sdp_mid` as optional
(webrtc-rs `to_json()` can yield `null`); the binding makes it required. That is a vector-first
change: `payload/info-valid-ice` keeps passing, a new `payload/info-webrtc-missing-mid` vector
rejects, and `dsip-media` fills `sdp_mid` from the transceiver before emitting.

## Appendix B. Example: browser calls native, screened, escalated

```
browser (alice-phone)                relay                 native (bob-laptop)
  pc.createOffer → SDP_O
  invite{media:[audio sendrecv opus],
         transports:[{id, ice:trickle, sdp:SDP_O}]}  ───▶  fork ───▶ verify, ring
  (candidates gathered → buffered)                         progress{ringing} ◀───
                                                           screening policy: accept_offer(SDP_O)
                                                           → SDP_A (a=recvonly, setup:active)
  ◀─── answer{answered_by:screening,
              media:[audio recvonly opus],
              transports:[{id, sdp:SDP_A}]}
  ACTIVE: setRemoteDescription(SDP_A)
  info{about:transport:webrtc, data:{candidates:[…], end_of_candidates:true}} ───▶  applied
                                                           ◀─── info{… bob-laptop's candidates …}
  ICE → DTLS (bob active) → SRTP; alice sends, bob listens (screening indicated to alice)
                                                           human accepts: add track, create_offer → SDP_O2
  ◀─── update{answered_by:user, media:[audio sendrecv], transports:[{id, ice:trickle, sdp:SDP_O2}]}
  setRemoteDescription(SDP_O2); createAnswer → SDP_A2
  answer{in_reply_to:update.id, media:[audio sendrecv], transports:[{id, sdp:SDP_A2}]} ───▶ set_answer
  (same ICE ufrag: no restart; same DTLS association; bob now sends)
  bye{user.hangup} ───▶
```

## Appendix C. Implementation notes (informative)

**What the v0.6 reference does (webrtc-rs 0.13 + browsers).** Offers are `actpass`, answers
`active`; `on_ice_candidate(None)` is the end-of-candidates signal and maps to
`end_of_candidates: true`; a re-offer for escalation is `add_track` + `create_offer` on the same
`RTCPeerConnection`; the browser glue buffers local candidates until ACTIVE and remote
candidates until `setRemoteDescription`; the native CLI sends all buffered candidates in one
`info` on the ACTIVE transition. The first answer to a forked invite is applied; later ones get
`bye session.already-answered` (`dsip-session/src/endpoint.rs`).

**What a second backend must provide (forge-media round one)** — the four additions in
`impl/docs/forge-media-plan.md`, mapped to this binding:

| requirement | binding section |
|---|---|
| answerer role: `set_remote_offer` + `create_answer`, DTLS role from `a=setup` (answer = `active`) | §3.1, §3.3 |
| trickle-out: local-candidate stream with an end marker; SDP producible before gathering ends | §4.1, §4.2 |
| single-leg media: one peer connection, Opus in/out, SRTP from exported DTLS keys, no engine session | §2.2, §3.4, §7 |
| post-establishment re-offer on the same connection **without** changing ICE credentials; rollback on reject | §5.1, §5.2, §5.4 |
| DTLS certificate verified against the peer's signed `a=fingerprint` | §7 |

Not required for round one: ICE restart, ICE-lite, data channels, simulcast, video codecs beyond
what the demo needs. Build-target caution for endpoints: forge's vendored OpenSSL and the
cmake/Opus dependency must not leak into `dsip-wasm` or the browser demo, which use the
browser's stack and never link a media backend.
