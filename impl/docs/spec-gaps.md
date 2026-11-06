# Spec-gap issue drafts (v0.6 → v0.7 worklist)

Each entry is the text of a `spec-gap` issue, per plan §11 and the CLAUDE.md
documentation standard. Numbers match the `Impl (spec-gap N)` comments in
`impl/tools/dsipvec/` and the Rust crates, and the list in
`impl/vectors/README.md`. Vectors named here pin the PoC's choice; if the spec
resolves differently, the vector changes first, then the code.

## v0.7 worklist (dispositions)

**Status (2026-08-21):** every disposition below is transcribed into `v0.7/dsip_v_0_7_decentralized_session_initiation_protocol.md` (changelog Appendix A.4) and pinned by the 298-vector v0.7 suite.

Status of every gap as input to the v0.7 assembly. *Disposition* is what v0.7 should say;
for gaps 1–13 it is the **Suggested fix** already recorded under each entry. Gaps 14–22
carry an explicit **v0.7 disposition** paragraph (added 2026-08-21). "adopt" = make the PoC
choice normative as written; "adopt-with-change" = normative text differs from the PoC and the
vectors change first. No gap is awaiting a decision.

| # | sections | disposition | pinned by |
|---|---|---|---|
| 1 | §12.4, §12.5 | adopt (crossed vs late cancel) | `state/race-responder-*` |
| 2 | §12.6 | adopt (suggested fix) | `state/glare-*` |
| 3 | §12.8 r4 | adopt (suggested fix) | `state/update-second-outstanding` |
| 4 | §12.9 | adopt (suggested fix) | `state/t-ring-*` |
| 5 | §12.7 r3, §12.4 | adopt (suggested fix) | `state/fork-*` |
| 6 | §20.6 | adopt (300 s, reject) | `envelope/ulid-*` |
| 7 | §12.9 | adopt (symmetric window) | `envelope/replay-future` |
| 8 | §7.4 | adopt (header `delegations`) | `envelope/delegation-in-header` |
| 9 | §14.2 | adopt (suggested fix) | `semantic/selection-*` |
| 10 | §15.4 | adopt (warning, not reject) | `payload/reject-*` |
| 11 | §12.10 | adopt (suggested fix) | `state/queue-*` |
| 12 | §12.4, §12.7 | adopt (`session.failed`) | `state/answer-after-reject` |
| 13 | §12.4 | adopt (drop ENDING) | all state traces |
| 14 | §19.4, §13.2 | adopt | `state/relay-introduction-anti-enumeration` |
| 15 | §19.4 | adopt | `state/first-contact-*` |
| 16 | §12.12, §16.3, §26 | adopt → **WebRTC Media Binding** (`v0.7/dsip-webrtc-media-binding-v0.7.md`) | `payload/info-*` incl. `info-webrtc-missing-mid` (binding schema, v0.7), `state/info-active-only` |
| 17 | §13.2, §13.3, §12.7 | adopt | `state/relay-store-and-forward-*`, `state/relay-*-queued-*` |
| 18 | §22.1 | adopt | `broadcast/publication-*` |
| 19 | §9.3, §9.4 | adopt (refuse over-cap with `error policy.subscription-lifetime`; authority-asserted presence) | `state/broadcast-authority-presence`, `semantic/subscribe-presence-over-cap` (carries the token since v0.7) |
| 20 | §22.2 | **adopt-with-change** (record-level `integrity`) — done in v0.7 vectors | `broadcast/publication-integrity-*` (3, v0.7), `broadcast/publication-valid-metadata-only`, `broadcast/provenance-derivative-bound` |
| 21 | §22.3 | adopt; `provenance` is a core message with a spec schema — done in v0.7 vectors | `broadcast/provenance-*`, `payload/provenance-*` (v0.7) |
| 22 | §7.5 | adopt (c): DID document authoritative + `key-rotation` record defined — schema + checks in v0.7 | `envelope/rotated-did-web-*`, `envelope/key-rotation-signed-by-previous-key`, `payload/key-rotation-*`, `semantic/key-rotation-*` (v0.7) |
| 23 | §15.5, §6.3 | adopt → **Gateway Profile 1.0** (`v0.8/dsip-gateway-profile-v0.8.md`) | `gateway/*` (53) |
| 24 | §15.5 | adopt (`Reason: DSIP;text=`) | `gateway/reason-outbound-*`, `gateway/trace-*` |
| 25 | §18.1, §24.2 | adopt; register `tel` claim type | `gateway/claims-*` |
| 26 | §12.12 | adopt → `media:dtmf` in `dsip-info-about` with `dtmf-info-data` (spec-gap 70; core v0.8 §12.12 + G§9 errata, 2026-09-17) | `payload/info-dtmf-*` (7), `gateway/trace-dtmf-*` (3) |
| 27 | §6.3 | adopt (named downgrade losses) | `gateway/downgrade-*` |
| 28 | §15.5, App. C | adopt (per-trunk early-media policy) | `gateway/trace-outbound-early-media*` |
| 29 | §12.7 | adopt (single contact; no SIP→DSIP forking in v1) | `gateway/trace-*` |
| 30 | §17.2, §24.4 | adopt → **RTP/SRTP Media Binding 1.0** (`v0.8/dsip-rtp-srtp-media-binding-v0.8-draft.md`) | G§6 (`gateway/sdp-*`) |

---

## 1. §12.4 vs §12.5 — responder in ACTIVE receiving `cancel`

**Conflict.** The §12.4 responder table says `ACTIVE` + `Recv cancel` → send
`error` (`session.invalid-state`), session continues. §12.5 rule 2 says a
responder that has already sent `answer` when `cancel` arrives MUST treat the
session as ended and MUST NOT treat the crossed cancel as an error. Both rows
fire on the same input.

**Choices considered.** (a) Always error (table wins) — breaks the race rule.
(b) Always tear down (rule wins) — lets a stale/forged-path cancel kill an
established call. (c) Distinguish "crossed" from "late" by whether the
initiator has been observed post-answer.

**PoC choice.** (c): a cancel received in ACTIVE before any initiator message
has arrived since our answer is treated as crossed (teardown, no error); after
the initiator has spoken post-answer (`info`, `update`, `bye`, an update
reply), cancel is `session.invalid-state`. Vectors:
`state/race-responder-crossed-cancel`,
`state/race-responder-cancel-after-post-answer-traffic`.

**Suggested fix.** Add the distinguishing condition to both §12.4 and §12.5,
or define that the initiator MUST NOT send `cancel` after accepting an answer
except `session.answered-elsewhere` addressed to the identity, and that
responders in ACTIVE MUST ignore `session.answered-elsewhere` silently.

## 2. §12.6 — who sends `reject session.glare`, and with which message

**Ambiguity.** "The endpoint whose invite lost MUST send `reject` with reason
`session.glare` for the losing invite." The loser cannot `reject` its own
invite (`reject` is a responder message); the winner "ignores the glare
condition", so nobody withdraws the losing invite at the winner's side.

**PoC choice.** The loser withdraws its own invite with `cancel
session.glare` (the initiator's withdrawal verb; §15.4 lists `session.glare`
as valid on `cancel`) and proceeds as responder. The winner rejects the
inbound losing invite with `reject session.glare`. Both legs of the losing
invite therefore end deterministically whichever message arrives first.
Vectors: `state/glare-we-win`, `state/glare-we-lose`, `state/glare-equal-ids`.

## 3. §12.8 rule 4 — "processes neither"

**Ambiguity.** A second `update` from the same sender while its first is
outstanding yields `error session.update-pending` "and processes neither".
Does the first update remain outstanding?

**PoC choice.** Literal reading: both are discarded; the session has no
outstanding update afterwards. Vector:
`state/renegotiation-second-update-same-direction`.

## 4. §12.9 — T-Ring restart semantics; what bounds PROCEEDING after `trying`

**Gaps.** (a) T-Ring is "started on first `progress` with status `ringing`";
the PROCEEDING row says later `progress` "adjusts timers per §12.9" without
saying how. (b) T-Establish is "stopped by first `progress`" of any status,
but nothing starts on `trying`/`forwarded`, so PROCEEDING is unbounded until
the relay signals an outcome.

**PoC choice.** A `ringing` progress carrying `ring_timeout` (re)starts T-Ring
at `clamp(ring_timeout, 30, 300)`; a `ringing` without it starts T-Ring only
if none is running. A non-ringing, non-queued progress starts T-Ring (default)
as a backstop when neither T-Ring nor T-Queue runs. Vectors:
`state/timer-t-ring-extension-honored`, `state/timer-repeat-ringing-no-restart`,
`state/timer-trying-backstop`.

## 5. §12.7 rule 3 / §12.4 — when does the initiator know an invite was forked?

**Gap.** §12.4 says "if forked, send `cancel`"; §12.7 rule 3 says the
initiator MUST send it unconditionally. The initiator cannot observe forking.

**PoC choice.** Send `cancel session.answered-elsewhere` to the invite's `to`
when the accepted answer's `from` differs from `to` (identity-addressed
delivery may have forked); do not send it when the invite addressed the
answering device directly. Vectors: `state/fork-first-answer-wins`,
`state/direct-device-call-no-fork-cancel`.

## 6. §20.6 — ULID/`issued_at` consistency tolerance

**Gap.** "SHOULD verify … MAY reject on gross mismatch" defines neither the
tolerance nor the verdict. **PoC choice.** Reject when the ULID timestamp
component differs from `issued_at` by more than the 300 s replay window.
Vectors: `envelope/ulid-backdated`, `envelope/ulid-within-tolerance`.

## 7. §12.9 — future-dated `issued_at`

**Gap.** Replay window text rejects envelopes "older than the window" only.
**PoC choice.** Symmetric window: `issued_at` more than 300 s in the future
is also rejected. Vector: `envelope/replay-window-future`.

## 8. §7.4 — conveying delegation credentials to a verifier

**Gap.** §7.4 shows the DeviceDelegation object but not how a verifier
obtains it for a `did:key` identity (which has no DID document to host it).
**PoC choice.** A delegation is a DSIP-JOSE envelope over the DeviceDelegation
object, signed directly by a key of the subject (no chains). Verifiers accept
delegations from a local store and from an optional `delegations` array in
the envelope's protected header. Vectors: `envelope/delegation-*`.

## 9. §14.2 / schema README check 9 — subset semantics

**Gap.** "Selections are subsets of the referenced offer" is not defined per
field. **PoC choice.** Match descriptors on `type`+`purpose`; codecs by `id`
⊆ offered; SDP-style direction answers; the single transport `id` ∈ offered.
Vectors: `semantic/selection-*`.

## 10. §15.4 — registered token on a message type it is not listed as valid on

**PoC choice.** Accept with a `reason-not-valid-on-type` warning rather than
reject; the registry column reads as guidance for senders. Vector:
`semantic/reason-not-valid-on-type`.

## 11. §12.10 — re-queue limit exceeded

**PoC choice.** The fourth consecutive `queued` is treated as T-Queue expiry
(`cancel session.timeout`). Vector: `state/timer-t-queue-requeue-limit`.

## 12. §12.4/§12.7 — `bye` reason for an answer after a terminal `reject`

**Gap.** `session.cancelled` covers answers crossing a cancel;
`session.already-answered` covers late legs of an established session. No
token covers an answer arriving after the attempt ended by `reject`.
**PoC choice.** `bye session.failed`. Vector:
`state/initiator-rejected-while-proceeding`. The third case — an answer arriving after a session that *was* established
has ended — is spec-gap 85.

## 13. §12.4 — ENDING

**PoC choice.** ENDING is collapsed into ENDED; the reference engine's local
teardown is synchronous. A future media-bound implementation may surface
ENDING as an observable state without changing any emission.

## 14. §19.4 vs §13.2 — relay handling of introductions to unknown recipients

**Conflict.** §13.2: "A relay MUST NOT silently drop envelopes on a live connection … it MUST
respond with a signed `error` (`transport.unknown-recipient` …)". §19.4: "an introduction to a
nonexistent identity and an ignored introduction are indistinguishable to the sender." A relay
that answers `transport.unknown-recipient` to an introduction is an enumeration oracle.

**PoC choice.** For `introduction` only, the relay queues the envelope for the addressed identity
whether or not it knows it (bounded per-inbox, until the introduction's `expires_at`) and returns
nothing; bound devices receive it immediately; a later `hello` binding flushes the queue. All
other message types keep the §13.2 error. Vector: `state/relay-introduction-anti-enumeration`.

**Suggested fix.** Add to §13.2: "except for `introduction`, where §19.4 anti-enumeration
governs: the relay MUST accept without a routing error regardless of recipient existence."

**v0.7 disposition.** Adopt. §13.2: append to the MUST-NOT-silently-drop rule — "except
`introduction`, which §19.4 governs: a relay MUST accept an introduction for any recipient
without a routing response, MAY hold it (bounded per recipient) until its `expires_at`, and
MUST deliver it on the recipient's next binding." §19.4: state the bound (PoC: 16 per inbox)
as a SHOULD with a registry-free deployment knob. No vector change.

## 15. §19.4 — grant matching, scope, and contact-token semantics

**Gaps.** (a) Whether the optional `grant` field in an invite is required for a relay/endpoint to
honor a grant, or whether holding a grant for the inviting identity suffices. (b) Whether a grant
whose `scope` lacks `dsip.invite` admits invites. (c) Whether a contact token is single-use.

**PoC choice.** A live grant admits an invite when matched by `grant` id **or** by grantee
identity; `scope` MUST contain `dsip.invite`; a token auto-grants once and is then consumed.
Vectors: `state/first-contact-responder-grant`, `state/first-contact-grant-scope`,
`state/first-contact-contact-token`.

**v0.7 disposition.** Adopt all three. §19.4 text: (a) "A live grant admits an invite when
the invite's `grant` names it **or** the inviting identity is the grantee; the `grant` field is
an optimisation for stateless relays, never a requirement." (b) "A grant admits only the
operations in `scope`; an invite requires `dsip.invite`." (c) "A contact token is single-use:
the first invite carrying it is auto-granted and the token is consumed; multi-use tokens are a
deployment extension." No vector change.

## 16. §12.12 / §16.3 — the WebRTC Media Binding document does not exist

**Gap.** §12.12 says the `info.data` structure for `transport:webrtc` "is normative in the
WebRTC Media Binding document" and §16.3 says SDP may ride as a transport binding object; no
such document is in the repository, and §26 step 8 still says candidates ride in `update`.

**PoC choice.** `transports[].sdp` on `invite`/`update`/`answer` carries the SDP offer/answer
(the descriptor keeps `id: transport:webrtc`, `ice: trickle`); trickle candidates ride in
`info.data.candidates[{candidate, sdp_mid, sdp_m_line_index}]` + `end_of_candidates`, exactly
the §12.12 example shape; `info` is ACTIVE-only so candidates gathered before the answer are
buffered by the endpoint. Implemented in `dsip-endpoint` and the browser client (`web/app.js`).

**Suggested fix.** Publish the binding document (or an appendix) with these shapes, fix §26
step 8 to say `info`, and state whether a forked invite's single SDP offer may be answered by
more than one leg (the PoC accepts only the first answer; later legs get `bye`).

**v0.7 disposition.** Adopt the PoC shapes and publish them as the **WebRTC Media Binding**
companion document — drafted at `v0.7/dsip-webrtc-media-binding-v0.7.md` (binding id
`transport:webrtc`, version 1.0). Spec edits: §12.12 "normative in the WebRTC Media Binding"
→ cite the document by id; §16.3 replace the `transport_binding: {type, sdp}` example with the
`transports[].sdp` descriptor form and the authority rule (descriptors govern *what* is
negotiated, SDP governs transport parameters); §26 step 8 `update` → `info`; §17.2 name the
binding. Forking: "exactly one answer is applied per invite; a later answer is released with
`bye session.already-answered`" moves into §12.7. ICE restart is explicitly out of scope for
binding 1.0. Vectors: the binding's `info.data` schema (Appendix A of the draft) becomes a
payload vector set in the v0.7 suite.

## 17. §13.2 / §13.3 — what a store-and-forward relay may call an unknown recipient

**Gap.** §13.2 requires `transport.unknown-recipient` when the relay "has no route"; §13.3
makes reaching offline devices the relay's job. A relay with store-and-forward therefore needs
a rule for *offline* versus *unknown*, and for what happens when a held envelope expires.

**PoC choice.** A recipient is *known* if any device has bound (`hello`) for it on this relay;
known-but-offline envelopes are queued until `min(expires_at, offline_retention_s)` and flushed
in order on the next binding (queued invites become tracked legs; a device binding while an
attempt is live becomes a leg mid-attempt, §12.7 rule 3). Expiry dequeues silently — the
initiator's §12.9 timers are the backstop — and an initiator `cancel` drops a still-queued
invite. Never-seen recipients still get `transport.unknown-recipient` (introductions excepted,
gap 14). Vectors: `state/relay-store-and-forward-known-offline`,
`state/relay-queued-invite-expires`, `state/relay-cancel-drops-queued-invite`,
`state/relay-leg-added-mid-attempt`, `state/relay-bye-queued-for-reconnecting-device`,
`state/relay-retention-cap`.

**Suggested fix.** Define "known" in §13.3, state that expiry of a held envelope is not
signaled (or define an `error` for it), and add the mid-attempt leg case to §12.7 explicitly.

**v0.7 disposition.** Adopt. §13.3 defines *known*: "an identity for which a device has
completed a verified `hello` at this relay within the relay's retention window"; store-and-
forward applies only to known identities, `transport.unknown-recipient` to all others (gap 14
excepted). Expiry of a held envelope is **not** signalled — the initiator's §12.9 timers are the
backstop; a held `invite` whose `cancel` arrives is dropped with no leg ever created. §12.7 rule
3 gains the mid-attempt leg sentence: "a device that binds while an attempt is live becomes a
leg of that attempt if the invite is still unexpired." Retention cap is a SHOULD with the PoC
default (24 h). No vector change.

## 18. §22.1 — who may publish a stream, and stream_id ownership

**Gap.** The record carries `from` and `publisher`; nothing says they must agree with the
signature, nor who may update or withdraw a stream, nor how `stream_id` relates to the publisher.

**PoC choice.** `publisher` MUST equal the verified identity (signer or its delegator); `stream_id`
MUST be the publisher DID or a colon-suffixed extension of it; a record with a lower ULID than the
held one is stale; `unpublish` MUST be signed by the same identity and name the held
`publication`. Vectors: `broadcast/publication-publisher-mismatch`,
`broadcast/publication-stream-outside-namespace`, `state/broadcast-authority-publisher-binding`.

**v0.7 disposition.** Adopt as §22.1 normative text: "`publisher` MUST equal the verified
signing identity (the signer, or the delegator of a delegated device); `stream_id` MUST be the
publisher DID or a colon-suffixed extension of it; a `publish` whose `id` is ULID-older than
the held record for the same `stream_id` is stale and ignored; `unpublish` MUST be signed by
the same identity and MUST name the held `publication`." No vector change.

## 19. §9.3 — presence subscriptions: what the authority knows

**Gap.** §9.4 defines signed presence records but not how an authority learns presence.
**PoC choice.** Presence for an identity derives from whether any of its devices is bound at the
authority (`available` / `offline`); presence bodies are authority-asserted, not subject-signed;
targets the authority has never seen get the uniform `policy.blocked`. Vectors:
`state/broadcast-authority-presence`, `state/broadcast-authority-caps-renewal-terminate`.

Also: §9.3 calls the per-event lifetimes "hard caps" without saying whether an over-cap
`expires_in` is refused or clamped. The PoC refuses it at the stateless boundary
(`subscription-lifetime-exceeded`, vector `semantic/subscribe-presence-over-cap`) and the
authority additionally clamps as defense in depth.

**v0.7 disposition.** Adopt, with the two models named. §9.4 keeps subject-signed presence
records as the privacy-preserving form; §9.3 adds: "An authority that has no subject-signed
record MAY assert presence from its own device bindings (`available` when any device of the
target is bound, else `offline`); such bodies are authority-asserted and clients MUST render them
as the authority's claim." Over-cap `expires_in` is **refused** at the stateless boundary with
`error policy.subscription-lifetime` — v0.7 registers that token (PoC verdict code
`subscription-lifetime-exceeded`); clamping is not permitted because it makes the caller's view
of its own subscription wrong. Vector change: none for the refusal; the new token lands in the
`dsip-reason` registry and `semantic/subscribe-presence-over-cap` gains the `reason` field.

## 20. §22.2 — where the integrity mode is stated

**Gap.** §22.2 defines `metadata-only` / `derivative-bound` but the `publish` schema is closed and
has no field for it. **PoC choice.** Variants carry `integrity` (variants allow extra
properties); a verified transcode statement makes the receiver display `derivative-bound`.

**v0.7 disposition.** Adopt-with-change. The PoC's per-variant `integrity` is a workaround
for a closed schema; v0.7 adds a **record-level** `integrity` field to `publish` (string,
registry `dsip-integrity-mode`, initial values `metadata-only`, `derivative-bound`) with an
optional per-variant override. Vectors change first: `broadcast/publication-valid-metadata-only`
and `broadcast/provenance-derivative-bound` move the field up a level; `generate_schemas.py`
gains the property; receivers treat an absent field as `metadata-only`.

## 21. §22.3 — how provenance statements reach receivers

**Gap.** §22.3 shows the statement but not its carriage. **PoC choice.** Processors send the
statement (type `broadcast.provenance`, extension `broadcast-provenance/1.0`, impl-local schema)
to the publisher's authority, which attaches processors to the record and lists them in
`notify.body.provenance`; the CLI receiver fetches statements alongside the record. Vectors:
`broadcast/provenance-*`, `state/broadcast-authority-provenance`.

---

**v0.7 disposition.** Adopt the carriage (processor → authority → `notify.body.provenance`)
and promote the statement to a spec message: `provenance` joins §22.3 with the PoC's impl-local
schema as its normative schema (`broadcast-provenance/1.0` stops being an extension id). Direct
receiver ↔ processor fetch remains permitted as an alternative path; either way the statement is
verified against the processor's identity and the publication's `policy` (§16.4). Vector change:
the `broadcast/provenance-*` vectors drop the extension declaration from `dsip.extensions`.

## 22. §7.5 — key rotation has requirements but no wire format

**Gap.** §7.5 says the protocol "defines, at minimum" a previous key, new key, rotation
timestamp, signature by the previous key (or a recovery signature), revocation reason, device
list update, and replay protection — but no message, record, or schema carries these, and no
section says how a verifier learns of a rotation. §7.6 (recovery models) is explicitly
deployment-specific and §7.7 (transparency) is optional, so nothing else fills the hole.

**Choices considered.** (a) Define a DSIP `KeyRotation` record (DSIP-JOSE envelope signed by
the previous key when available, else by a recovery key; carries the fields §7.5 lists; ULID +
`issued_at` give replay protection) and have DID methods / transparency logs publish it.
(b) Delegate rotation entirely to the DID method: the DID document *is* the rotation state
(§8.1 rule 4), and §7.5's list becomes guidance for what a method's update must capture.
(c) Both: the DID document is authoritative for verification (as today), and the record is the
audit artifact that §7.7 logs and that clients display as trust metadata.

**PoC choice.** The verifier-observable consequences only, derived from §8.1 + §7.4: after a
`did:web` document replaces `#key-1` with `#key-2`, signatures under the new kid verify, the
retired kid is `kid-unresolvable`, a delegation re-issued by the new key admits the device, and
a delegation signed by the retired key is `delegation-invalid`. No rotation record exists in
the PoC. Vectors: `envelope/rotated-did-web-new-key-signs`,
`envelope/rotated-did-web-retired-kid-rejected`, `envelope/rotated-did-web-new-key-delegation`,
`envelope/rotated-did-web-old-key-delegation-rejected`.

**Suggested fix.** (c). Keep the DID document authoritative — the vectors above then stand
unchanged — and define the record as the §7.5 artifact with a schema, so §7.7 has something to
log and clients have something to show. State explicitly that `did:key` identities cannot rotate
(the DID is the key) and that rotation for them means a new identity plus a signed
`identity.moved` pointer.

**v0.7 disposition.** **(c), decided 2026-08-21.** The DID document stays authoritative for
verification (§8.1; the vectors above stand unchanged) and v0.7 defines the `KeyRotation` record
with a schema as the §7.5 artifact — what §7.7 logs and clients show as trust metadata. `did:key`
identities cannot rotate; v0.7 says so and points to `identity.moved`.

## 23. §15.5 / §6.3 — the Gateway Profile does not exist

**Gap.** §15.5 gives an "informative initial mapping" and says "the normative table belongs to the
gateway profile"; §6.3 states the trust-downgrade principle but no mechanism. No Gateway Profile
document exists.

**PoC choice.** `impl/crates/dsip-gateway` implements the full B2BUA rule set — reason mapping both
directions, PSTN caller claims, SDP↔descriptor mapping, the downgrade rule, early media, the
controller state machine — all pinned by the 53 `gateway/` vectors. Written up as
**DSIP Gateway Profile 1.0** (`v0.8/dsip-gateway-profile-v0.8.md`).

**Suggested fix.** Adopt the profile draft as a named conformance piece (§24.4); make §15.5's table
normative there and leave §15.5 in core as the pointer.

## 24. §15.5 — the DSIP reason should stay visible across a SIP crossing

**Gap.** §15.5 says map foreign codes to DSIP reasons; it does not say the DSIP reason should be
preserved *on* the SIP message so a capture or downstream element can see the original token.

**PoC choice.** Every SIP crossing carries `Reason: DSIP;text="<token>"` (RFC 3326) in addition to
any `Q.850;cause=`. Vectors: `gateway/reason-outbound-*`, `gateway/trace-*`.

**Suggested fix.** State the `Reason: DSIP` convention in the Gateway Profile (G§3).

## 25. §18.1 — no claim type for a PSTN caller identity

**Gap.** §18.1 requires clients to display a verification *basis*; a gateway presenting a PSTN
caller has no registered claim shape to carry the number, STIR attestation, and verification
outcome.

**PoC choice.** A `tel` claim `{type, number, attestation, verified, verifier, cnam?}` in the
invite's `identity.claims`, rendered as "Gateway attested by <did> · STIR attestation <A|B|C>
(verified|unverified)" or "· no attestation"; a PASSporT whose `orig` ≠ `From` is discarded.
Vectors: `gateway/claims-*`.

**Suggested fix.** Register `tel` in a DSIP claim-types registry (§24.2) with this shape.

## 26. §12.12 — DTMF has no DSIP carriage

**Gap.** DSIP Core v1.0 has no DTMF semantics; a gateway bridging RFC 2833 telephone-event has
nowhere to put digits on the DSIP side.

**PoC choice.** Round one did not forward DTMF across the gateway. The natural vehicle is a signed
`info` (§12.12) with a registered `about`.

**Resolved by spec-gap 70:** `media:dtmf` is now a registered `dsip-info-about` value with its own
`data` schema, and G§9 maps it to and from SIP `INFO`.

## 27. §6.3 — `gateway.downgraded` trigger conditions are undefined

**Gap.** `gateway.downgraded` is a registered reason (§15.4) but §6.3 does not say when a gateway
emits it.

**PoC choice.** One informational `error` per crossing that loses a guarantee, naming each loss:
`no-srtp-on-trunk`, `identity-not-assertable`, `no-attestation`, `policy-unenforceable`. Vectors:
`gateway/downgrade-*`.

**Suggested fix.** State the trigger set in the Gateway Profile (G§7).

## 28. §15.5 / Appendix C — early-media handling needs a rule

**Gap.** §15.5 and Appendix C describe early media in prose ("classify announcements … otherwise
answer the DSIP leg and pass audio through") without a rule.

**PoC choice.** Per-trunk `pass-early-media` ∈ {auto, always, never}, default auto (classify to a
reason if possible, else answer `answered_by: gateway` and bridge). Vectors:
`gateway/trace-outbound-early-media*`.

**Suggested fix.** Adopt the rule in the Gateway Profile (G§8).

## 29. §12.7 — may a gateway forward SIP forking as DSIP forking?

**Gap.** SIP 3xx and parallel forking have no stated mapping to DSIP forking (§12.7 is a
relay-side, identity-addressed mechanism).

**PoC choice.** A gateway follows a single SIP contact and does **not** forward SIP 3xx as DSIP
forking in round one; glare (§12.6) cannot cross (the two sides are distinct sessions).

**Suggested fix.** State single-contact behaviour in the Gateway Profile; leave multi-contact
follow as a later extension.

## 30. §17.2 / §24.4 — the RTP/SRTP Media Binding does not exist

**Gap.** §17.2 names "RTP/SRTP binding for SIP and telecom gateways" and §24.4 lists
`DSIP RTP/SRTP Media Binding 1.0` as a conformance piece; no document defined it.

**PoC choice.** `transport:rtp` with SDES/DTLS keying, the §17.2 encryption floor plus a
plain-RTP exception behind an operator-vouched trunk (with `gateway.downgraded`), and the PSTN
codec set. Written up as `v0.8/dsip-rtp-srtp-media-binding-v0.8-draft.md`.

**Suggested fix.** Adopt the binding draft; align it with the WebRTC binding's descriptor/SDP
authority rule.

## v0.8 messaging worklist (gaps 31–58)

**Status (2026-09-17): every gap in this worklist and in the gateway worklist (23–30) is disposed in the v0.8
core (`v0.8/dsip_v_0_8_decentralized_session_initiation_protocol.md`, Appendix A.5) or in its companion profiles.
Spec-gap 26 (DTMF carriage), open until 2026-09-17, is closed by spec-gap 70. Gaps 58–72 are profile 1.0 errata
found by running the profile; each is carried into the profile text as it lands.**

**Status (2026-09-15):** filed with the **DSIP Messaging Profile 1.0** draft
(`v0.8/dsip-messaging-profile-v0.8.md`, cited M§n). Unlike gaps 1–30, these were not found
by implementing. They are the choices the profile draft makes before implementation, per the
decisions taken 2026-09-15: companion profile, MLS plus HPKE, SYNC history by default, groups in
1.0. Every row is **open** until the profile text and its vectors agree; "draft choice" is what the profile
text says today. Tranche 1 of `messaging/` (101 vectors, 2026-09-15: message/object rules, hub
and mailbox traces) pins gaps 34–36, 38, 40 and 43 at Rust/Python parity. Tranche 2 (46 vectors: voicemail offer, conversation and successor
convergence, client receipts/watermarks/activity, seq gaps) pins 41 and 42. Tranche 3 (38 vectors: MLS extension encoding, leaf authentication, `dsip_conversation`
bytes, AES-GCM formats) pins 33 and 39, and `impl/crates/dsip-mls` runs the profile on OpenMLS end to end. Gap 31 is a v0.7 defect in its own right and does not depend on messaging.

| # | sections | draft choice | pinned by |
|---|---|---|---|
| 31 | §12.9, §13.3, §19.4 | **adopted in the PoC** (2026-09-15): type-scoped validity for held introductions + enforced 7-day cap (**v0.7 defect**) | `envelope/introduction-held-*` (3), `envelope/introduction-future-rejected`, `envelope/introduction-validity-over-cap` |
| 32 | §3.2, §6.1, §12.1, §24.4 | adopt → **Messaging Profile 1.0** + **Mailbox 1.0** conformance pieces | `messaging/*` (101, tranche 1) |
| 33 | §6.2, §20.7 | MLS for conversations, HPKE for sealed introductions; non-repudiation stated | `messaging/mls-credential-*` (13), `dsip-mls` e2e (OpenMLS) |
| 34 | (new; M§6.5) | per-group hub orders MLS commits | `messaging/hub-*` (19) |
| 35 | (new; M§12) | archive key in the personal group; `sync` default, `queue` opt-out | `messaging/mailbox-archive-*`, `messaging/mailbox-sync-mode-retains-after-ack`, `messaging/mailbox-queue-mode-*` |
| 36 | §19.4 | `dsip.message` scope; `sealed` introductions; grant-gated group adds; invite-grantee voicemail | `messaging/mailbox-welcome-*` (11), `messaging/mailbox-key-package-fetch-unauthorized` |
| 37 | §8.1, §13.2, DHT Hints | `DSIPMailbox` service type; hint `service`; priority-ordered multiple mailboxes | `messaging/mailbox-select-*` (11), `messaging/mailbox-switch-*` (3), `messaging/mailbox-service-*` (3) |
| 38 | §15.1 | new reason category `mailbox` | `messaging/deposit-unknown-class-refused`, `messaging/mailbox-*` error tokens |
| 39 | §7.4, §24.2 | delegation capability `dsip.messaging` + a delegation-capability registry | `messaging/mls-credential-signaling-only-delegation`, `dsip-mls` e2e |
| 40 | §13.2 | `MAX_MLS_BYTES` = 24,576; blobs over HTTPS | `messaging/deposit-mls-at-cap-accepted`, `messaging/deposit-mls-over-cap-refused` |
| 41 | §12, §14 | caller-recorded voicemail; trigger set; no core field | `messaging/voicemail-offer-*` (16) |
| 42 | §12.6, §20.6 | duplicate direct conversations / successor groups: lower ULID wins | `messaging/direct-select-*`, `messaging/successor-*` |
| 43 | (new; M§11) | activity keyed by the MLS exporter, not the secret tree | `messaging/deposit-ephemeral-*`, `messaging/hub-ephemeral-*`, `messaging/mailbox-ephemeral-pushed-never-stored` |
| 44 | M§5.4, M§8.5 | **pinned** (2026-09-16): MLS state and delivery state (ack cursor, per-group seq positions) commit atomically per item; redelivered sequenced items collapse by seq, not content id | `messaging/resume-*` (9), `dsip-mls` `tests/persist.rs`, `demos/messaging-demo.sh` (restart + crash-before-commit) |
| 45 | M§5.2, M§6.6 | **pinned** (2026-09-16): a mailbox forwards only its owner's devices' deposits, only to the hub registered for the group (from the welcome's `hub`); hub identity from the header delegation | `messaging/mailbox-forward-*` (5), `demos/group-demo.sh` |
| 46 | M§14.2, §19.4 | **pinned** (2026-09-16): a hub-forwarded welcome's adder is proven only by `origin` (a `handshake` deposit, same group, ≤ 300 s); `policy.blocked` for a bad origin | `messaging/mailbox-welcome-hub-forwarded-*` (6), `demos/group-demo.sh` |
| 47 | M§6.5 | **pinned** (2026-09-16): a device's own fanned-back items are processed by the `accepted` seq (or recognised by their bytes), never decrypted | `messaging/resume-own-item-by-accepted-seq`, `demos/group-demo.sh` |
| 48 | M§5.6, M§16 | **pinned** (2026-09-16): blob endpoint statuses 401/403/400/413 in check order, idempotent 200 re-upload, 404 GET; new token `mailbox.blob-mismatch` | `messaging/blob-put-*` (10), `messaging/blob-get-*` (2), `demos/messaging-demo.sh` (voicemail) |
| 49 | M§5.4, M§11.2 | **pinned** (2026-09-16): pushed ephemeral item `{class, group, source, sealed, expires_at}` without cursor; originating `expires_at` carried unchanged and enforced by every hop; receivers clear at it | `messaging/items-ephemeral-*` (3), `messaging/items-stored-class-ephemeral-refused`, `messaging/mailbox-ephemeral-expired-dropped`, `messaging/client-activity-*` (4 receiver traces), `demos/receipts-demo.sh` |
| 50 | M§6.5, M§6.7 | **pinned** (2026-09-16): the hub sends a welcome to every identity that gains a device, including a member adding its own | `messaging/hub-commit-adds-own-device-sends-welcome`, `messaging/hub-commit-readds-existing-device-no-welcome`, `demos/multidevice-demo.sh` |
| 51 | M§12.1–M§12.3, M§8.5 | **pinned** (2026-09-16): held archive until its key; pre-join and unjoined-group MLS skipped; sibling welcome acknowledged, not a join; own sent content archived; current key = greatest created_at; archive items carry ref_group/ref_seq as group/seq | `messaging/history-*` (8), `messaging/resume-sibling-welcome-is-not-a-join`, `demos/multidevice-demo.sh` |
| 52 | M§10.5, M§8.1 | **pinned** (2026-09-16): a private read watermark in the personal group names the conversation it describes (exempt from the conversation match) | `messaging/receipt-read-in-personal-group-*`, `messaging/receipt-*-other-conversation-refused` (2), `demos/multidevice-demo.sh` |
| 53 | M§5.7, M§6.6, M§12.4 | **pinned** (2026-09-16): a removed device sends `left` only when no leaf of its identity remains | `messaging/registration-on-removal-*` (2), `demos/multidevice-demo.sh` |
| 54 | M§14.1, §19.4, M§5.2 | **pinned** (2026-09-17): introductions and grants as mailbox deposits (`envelope`, `recipient`, no group); §19.4 relay rules at the mailbox | `messaging/deposit-introduction-*`, `messaging/deposit-grant-valid`, `messaging/mailbox-introduction-*` (5), `messaging/mailbox-grant-stored-for-owner`, `demos/messaging-first-contact-demo.sh` |
| 55 | M§6.9, §7 | **pinned** (2026-09-17): did:key-style derivation of the X25519 key agreement key; did:web provisioning is deployment-defined | `messaging/x25519-key-agreement-from-ed25519`, `messaging/sealed-introduction-*` (10), `messaging/hpke-*` (4) |
| 56 | §7.4, §24.2 | **adopted in core v0.8** (2026-09-17), disposition (b): binding stays `dsip.signaling` for every envelope; messaging devices carry `dsip.signaling` and `dsip.messaging` | `envelope/hello-messaging-only-delegation-rejected`, `dsip-mailbox` `verify::tests` |
| 57 | §7.4, §8.1, M§4.3, M§5.7, M§12.4 | **adopted in core v0.8** (2026-09-17): `delegation-revocation` record (subject-signed, covers delegations issued ≤ `revoked_at`), found in the DID document or any verifier store; `delegation-revoked`; mailbox closes the binding | `envelope/delegation-revoked-*`, `envelope/delegation-revocation-*`, `envelope/hello-revoked-device-rejected`, `payload/delegation-revocation-*`, `semantic/delegation-revocation-*`, `messaging/mailbox-revoked-device-closed-and-forgotten`, `demos/revocation-demo.sh` |
| 58 | M§6.5, §15.3 | **pinned** (2026-09-17, profile 1.0 erratum): on commit-conflict or stale-epoch discard, sync past the winning commit, re-propose while still needed, at most 3 proposals; unknown `mailbox.*` retried once; other refusals surfaced | `messaging/commit-retry-*` (9), `demos/commit-conflict-demo.sh` |

## 31. §12.9 vs §13.3 / §19.4 — the replay window rejects held envelopes

**Gap.** §12.9 requires rejecting any envelope whose `issued_at` is more than 300 s old. §19.4
gives introductions up to 7 days of validity "because the recipient may be offline for days", and
§13.2/§13.3 have relays hold them until the recipient's next binding. A held introduction delivered
more than 300 s after signing therefore fails the recipient's replay check. The PoC confirms it:
`dsip-core::envelope::verify` applies `REPLAY_WINDOW_S` to every envelope with no type exemption.
No vector exercises recipient-side verification of a held introduction, which is why the suite is
green. Held `invite`s are unaffected in practice (their validity is 30 s).

**Choices considered.** (a) Type-scoped validity: for `introduction`, replace the age bound with
`now < expires_at` (keeping the future bound) and deduplicate its `id` until `expires_at`. Memory
stays bounded by the 7-day cap and the per-recipient inbox bound of 16. (b) The relay re-wraps held
envelopes in a fresh relay-signed envelope, which changes what the recipient verifies and makes the
relay a signer of third-party content. (c) Shorten introduction validity to 300 s, which defeats
store-and-forward.

**Draft choice.** (a). The Messaging Profile sidesteps the issue by construction: mailboxes deliver
stored bytes inside fresh `items` envelopes (M§5.1) and authenticate content with MLS. It does not
fix core.

**PoC choice (2026-09-15).** (a), plus enforcing the §19.4 cap, which nothing enforced before.
Without the cap the relaxed age bound would let an introduction claiming a year of validity stay
replayable, with its id tracked, for a year. Envelope stage 9 for `introduction`:
`expires_at − issued_at > 604,800` → `introduction-validity`; `issued_at > now + 300` →
`replay-window`; `expires_at < now` → `expired`. Receivers track the id until `expires_at`
(`dsip-endpoint::verify::SeenIds`). Every other type keeps the symmetric 300 s window. Vectors:
`envelope/introduction-held-accepted` (delivered at +2 days), `introduction-held-replayed`,
`introduction-held-expired`, `introduction-future-rejected`, `introduction-validity-over-cap`.
The existing `introduction-valid-7-day` pins the cap edge and `replay-window-too-old` pins that
invites are unaffected.

**Suggested fix.** State (a) and the enforced cap in §12.9 and §19.4 for v0.8.

## 32. §3.2 / §6.1 / §12.1 / §24.4 — no Messaging Profile exists

**Gap.** §6.1 defers messaging to "a future DSIP Messaging Profile, or reuse MIMI/MLS concepts";
§3.2 lists full messaging interoperability as out of scope for Core v1.0. No profile, message
types, or conformance piece exists.

**Choices considered.** (a) A companion profile with its own message types and conformance pieces,
like the Gateway Profile. (b) Fold a mailbox into core as a fourth core service. That reverses the
v0.5 scope correction (Appendix A.1) and §5.1.

**Draft choice.** (a): `messaging/1.0`, message types `deposit`, `accepted`, `sync`, `items`,
`key-packages`, `key-package-fetch`, `blob-put`, `mailbox-config` (outside the §12.1 session set,
as `reachability-hint` is), and conformance pieces `DSIP Messaging Profile 1.0` and
`DSIP Mailbox 1.0`.

**Suggested fix.** Add both pieces to §24.4. Add a §12.1 sentence naming profile message types
alongside `reachability-hint`. Replace §6.1's deferral with a pointer to the profile.

## 33. §6.2 / §20.7 — asynchronous traffic needs end-to-end encryption

**Gap.** §20.7: payloads are signed, not encrypted; a relay can read them. That is tolerable for
call signaling but not for stored messages. §6.2 says to consider MLS before inventing group key
management.

**Choices considered.** (a) MLS (RFC 9420): devices as leaves, groups, FS/PCS, IETF standard,
permissively licensed Rust implementations (OpenMLS, mls-rs), and the choice of MIMI and RCS
Universal Profile 3.0. It needs an ordering authority (gap 34). (b) The Signal Protocol
(PQXDH + Double Ratchet, sender keys for groups): excellent pairwise and deniable, but it is
implementation-defined rather than a standard (libsignal is AGPL-3.0), and multi-device and group
membership lean on central servers. (c) HPKE to each device: simple, but no FS and no group
machinery.

**Draft choice.** (a) for all conversations (M§6), with credentials bound to §7.4 delegations and
leaf signature key = device Ed25519 key. (c) only to seal introduction text (M§6.9). Messages are
non-repudiable, and the profile says so (M§6.10).

**Suggested fix.** In §20.7, keep the signaling limitation and add that the Messaging Profile's
content is end-to-end encrypted. In §6.2, record the MLS adoption.

## 34. MLS commit ordering needs an authority

**Gap.** MLS members must apply one commit per epoch. Concurrent commits fork a group, and forks
cannot be merged. RFC 9420 leaves ordering to a Delivery Service, which DSIP does not define.

**Choices considered.** (a) One hub per group, named in an authenticated GroupContext extension,
accepting the first valid commit per epoch (MIMI's hub model). (b) Leaderless: members pick among
conflicting commits deterministically (e.g. lowest hash), which needs fork detection and rollback
and still loses messages sent on the losing branch. (c) Consensus among member mailboxes, which is
too heavy for a profile and introduces Sybil questions.

**Draft choice.** (a) (M§6.5). The creator's primary mailbox is hub by default. The hub can be moved
by commit (M§7.4). If it dies, a successor group takes over (M§7.5). Hub powers and limits are
stated in M§15.3.

**Suggested fix.** Adopt in the profile; nothing in core.

## 35. New-device history versus forward secrecy

**Gap.** With MLS a device added today cannot decrypt earlier messages. The user requirement
(2026-09-15) is SYNC: history on new devices.

**Choices considered.** (a) An identity-level archive key, distributed in a personal MLS group, used
by devices to re-encrypt decrypted content into mailbox-stored archive records. This gives up
forward secrecy of stored history. (b) Device-to-device history transfer at add time, which needs a
surviving device online and holding the full history. (c) No history (`queue`). (d) Mailbox-side
plaintext (rejected: violates the untrusted-mailbox principle).

**Draft choice.** (a) as default `sync` mode, with (c) as opt-in `queue` mode (M§4.4, M§12). The
first archive per (group, seq) wins at the mailbox. The archive key is rotated on device removal.
The trade is stated normatively (M§15.2).

**Suggested fix.** Adopt in the profile; recovery-escrow of the archive key goes into §7.6
deployment guidance.

## 36. §19.4 — first contact for messaging

**Gap.** §19.4's grant scopes are `dsip.invite` and `dsip.subscribe`; nothing authorizes messaging.
Introduction `purpose` is plaintext to relays. Nothing says who may add an identity to a group.

**Choices considered.** For authorization: (a) new scope `dsip.message`; (b) reuse `dsip.invite`
for everything. For sealing: (a) optional HPKE `sealed` replacing `purpose`, keyed to the DID
`keyAgreement` key; (b) leave introductions plaintext. For group adds: (a) the adder must hold a
`dsip.message` grant from the added identity, or the added identity's mailbox admits `open`;
(b) any member may add anyone (spam vector).

**Draft choice.** (a) in each case (M§14). A `dsip.invite`-only grantee may create a conversation
so it can leave voicemail, and the recipient client restricts rendering to `voicemail` and
`callback-request` until `dsip.message` is granted. Grants are carried in full so mailboxes verify
them statelessly, and revocation is propagated by `mailbox-config.revoked_grants`.

**Suggested fix.** Register `dsip.message` in `dsip-grant-scope`. Add optional `sealed` to
`introduction.schema.json` (mutually exclusive with `purpose`). Add a §19.4 sentence pointing to
the profile.

## 37. §8.1 / §13.2 / DHT Hints — mailbox discovery

**Gap.** Only `DSIPSignaling` service entries exist (§13.2). The hint schema's `endpoints[]` have
no service discriminator. Nothing defines several mailboxes for one identity.

**Choices considered.** Discovery: (a) a `DSIPMailbox` DID service entry (authoritative) plus a
hint `service` field for `did:key`; (b) mailbox fields on the relay's `hello` capabilities, which
are not authoritative and are only visible after connecting. Multiple mailboxes: (a) `priority`
order for deposit, owner devices sync all and archive to all; (b) exactly one mailbox;
(c) mailbox-to-mailbox replication, a new trust relationship between operators.

**Draft choice.** (a) and (a) (M§4.2). Hint-sourced mailboxes never replace an established
conversation's mailbox on their own (M§15.4). Vectors (2026-09-15) settle what the prose left open: an
entry is usable only if it satisfies the `mailbox-service` shape and advertises `messaging/1.0`;
`priority` defaults to 0 and equal priorities keep document order; the selection is the first usable
entry that accepts a connection while devices sync every usable one; and a document that lists only
unusable entries yields **no** mailbox rather than falling back to a hint.

**Suggested fix.** Register the `DSIPMailbox` service type. Add optional `endpoints[].service` to
the DHT Hints Profile (default `DSIPSignaling`).

## 38. §15.1 — no reason category fits mailbox conditions

**Gap.** The §15.1 category set is closed in the grammar. Commit conflicts, stale epochs, cursors,
and KeyPackage exhaustion are neither `session` (no session exists) nor `transport`.

**Choices considered.** (a) New core category `mailbox`, with fallback "re-sync, retry once, then
surface". (b) Extension-prefixed `x-messaging.*` (§15.6), which receivers without the profile map
to `session.failed`, and whose `x-` wrongly suggests an unofficial extension. (c) Overload
`session.*` and `policy.*`.

**Draft choice.** (a), with eight tokens (M§16).

**Suggested fix.** Add `mailbox` to the §15.1 grammar and §15.3 table; register the M§16 tokens.

## 39. §7.4 / §24.2 — delegation capabilities have no registry

**Gap.** §7.4's example uses `dsip.signaling` and `dsip.media.interactive`, and verifiers require
`dsip.signaling`, but §24.2 lists no registry for delegation capabilities. Messaging needs a
capability so that an identity can delegate a device for calls but not messages, or the reverse.

**Choices considered.** (a) Create `dsip-delegation-capability` with the two existing values plus
`dsip.messaging`, and require `dsip.messaging` for messaging leaves and mailbox operations. (b)
Treat `dsip.signaling` as covering messaging, which gives no separation.

**Draft choice.** (a) (M§6.2, M§4.3).

**Suggested fix.** Add the registry to §24.2 and cite it from §7.4.

## 40. §13.2 — 64 KiB cap versus media messages

**Gap.** Voicemail, images, and files exceed the fixed 65,536-byte `ws/1.0` envelope cap, and
payload bytes are base64url-encoded twice (inside the payload and then as the payload).

**Choices considered.** (a) Cap every MLS value at 24,576 bytes so any envelope carrying one value
plus a header delegation fits, and move larger payloads to client-encrypted blobs over HTTPS with
signed `blob-put` upload and capability-URL fetch. (b) Chunk over `ws/1.0`, adding a reassembly
layer to a binding defined as one envelope per message. (c) A new binding version with a larger cap
(§13.2 forbids negotiating the constant).

**Draft choice.** (a) (M§5.1, M§8.4). Recipient mailboxes replicate blobs so devices never contact
the sender's mailbox.

**Suggested fix.** Adopt in the profile. Add a §13.2 note that profiles carry bulk data outside the
signaling binding.

## 41. §12 / §14 — voicemail

**Gap.** Core has `answered_by: service` for voicemail systems (§14.3), but no end-to-end model, and
no rule for when a caller may leave a message.

**Choices considered.** (a) The caller records locally and sends an E2EE `voicemail` content object.
The offer is gated on the callee's `DSIPMailbox.voicemail` advertisement and a fixed set of attempt
outcomes. (b) A mailbox service answers the call (`answered_by: service`) and records, which gives
the service plaintext audio. (c) (a) plus a new `reject` field to suppress or permit voicemail per
attempt, a core schema change.

**Draft choice.** (a) (M§13). (b) remains permitted outside the profile's guarantee. (c) is not
adopted in 1.0. Vectors (2026-09-15) added the unregistered-token rule the list left open: an
unregistered `endpoint.*` rejection offers by category fallback; an unregistered condition in any other
category does not, and registered tokens outside the list (e.g. `endpoint.capability`) never do.

**Suggested fix.** Adopt in the profile; no core change.

## 42. §12.6 / §20.6 — concurrent conversation creation

**Gap.** Two identities can create a direct conversation simultaneously, and two members can create
successor groups for a dead hub simultaneously. Both are glare in a new place.

**Choices considered.** (a) Lower ULID wins (conversation ULID for direct conversations, `group_id`
ULID for successors), mirroring §12.6, with clients merging histories into one thread. (b) Both
survive and the UI merges them. That leaves two hubs and doubles metadata exposure. (c) The
lexicographically lower identity DID wins, which is deterministic but permanently favors some
identities.

**Draft choice.** (a) (M§7.2, M§7.5). Backdating wins only hub hosting (metadata visibility), and
the §20.6 tripwire is restated for any future hosting privilege. Vectors (2026-09-15) pin two details:
a candidate failing the ULID/`issued_at` check cannot win, and successor `group_id`s compare as
decoded ULIDs, because base64url text does not sort like the ULID it encodes.

**Suggested fix.** Adopt in the profile; cite §20.6.

## 43. Ephemeral activity and the MLS secret tree

**Gap.** Sending typing refreshes as MLS application messages consumes sender ratchet generations.
A long-offline member then faces generation gaps that can exceed an implementation's maximum
forward distance, breaking decryption of real content.

**Choices considered.** (a) Seal activity with a per-epoch `MLS-Exporter("dsip activity", …)` key
and a device signature: no ratchet consumption, not forward-secret within an epoch, acceptable for
content-free indicators. (b) MLS application messages with a rate cap, which mitigates but does not
eliminate the problem. (c) Unencrypted activity, which leaks conversation activity to hubs and
mailboxes.

**Draft choice.** (a) (M§11.1), never stored, ≤ 10 s envelope lifetime.

**Suggested fix.** Adopt in the profile.

## 44. M§5.4 / M§8.5 — durable processing and redelivery of MLS items

**Gap.** M§5.4 lets a device acknowledge items it has "durably processed" but does not say what must
be durable. Processing an MLS item changes two things in different places: the MLS group state
(which deletes the secret it used) and the device's ack cursor. A crash between them either (a)
acknowledges an item whose MLS state change is lost — in `queue` mode the mailbox then deletes a
message the device never kept — or (b) keeps the MLS state change but not the cursor, so the item is
redelivered and can no longer be decrypted. M§8.5 deduplicates by content id, which needs a
decryption, so (b) surfaces as an undecryptable message rather than a silent duplicate. The same
redelivery happens with no crash at all after `mailbox.cursor-invalid` (re-sync from `null`) and when
a device syncs several mailboxes.

**Choices considered.** (a) Commit MLS state and delivery state (ack cursor, per-group seq positions,
joined groups) atomically per item, and recognise redelivered sequenced items by hub `seq`, welcomes
by joined group. (b) Acknowledge only after MLS state is flushed, and treat undecryptable items as
probable duplicates: silent loss of genuinely undecryptable content is indistinguishable from a
duplicate. (c) Leave it to implementations: interop is unaffected, but the queue-mode loss in (a)
above is a protocol-visible failure.

**Draft choice.** (a) — MUST NOT acknowledge ahead of durable MLS state; SHOULD commit atomically;
MUST keep per-group seq positions durably and collapse redelivery by seq. Vectors (2026-09-16,
`messaging/resume-*`) pin: the post-restart `since`/`ack_through` equal the last committed item;
an uncommitted item is redelivered and processed; duplicates are acknowledged; seq positions are per
group and include seqs processed beyond a gap; a welcome for a joined group is a duplicate;
`group-info` is re-applied. `impl/crates/dsip-mls` (`sqlite` feature) shows (a) is directly
implementable on OpenMLS: its SQLite storage provider opens no transactions of its own, so one
transaction spans the MLS writes and the delivery state. `tests/persist.rs` and the messaging demo
(a device killed after processing but before commit) exercise it, and both fail when the transaction
is removed.

**Not yet pinned.** How a device's durable state interacts with items held across a seq gap (M§6.5):
a held item is not processed, so the ack position must stop before it, while later items for other
groups may still be processed.

**Suggested fix.** Adopt the M§5.4 and M§8.5 text now in the draft.

## 45. M§5.2 / M§6.6 — mailbox-to-hub forwarding has no rules

**Gap.** M§5.2 says a device sends every deposit to its own mailbox, "which forwards it unchanged to
`to` when `to` names another service". It does not say how the mailbox reaches that service (a hub is
named by a DID, which for a service need not resolve to an endpoint), which deposits it may forward
(otherwise any client can use a mailbox as an open relay), or how the hub learns who deposited: the
connection it arrives on is the mailbox's `hello`, so the §13.2 binding names the mailbox, not the
member. The first group over the wire needed all three; a direct conversation never did, because only
its creator's device deposits and that device is bound at the hub.

**Choices considered.** (a) Forward only an owner device's deposit and only to the hub registered for
its group, at the `hub.uri` the registering `welcome` carried; the device carries its delegation in the
header and the hub takes identity from it. (b) Resolve `to` as a DID and forward anywhere it leads: an
open relay, and a service `did:key` has no endpoint. (c) Devices always connect to hubs directly (the
MAY): exposes device addresses to every hub and multiplies connections, which M§5.2 set out to avoid.

**Draft choice.** (a), with `policy.blocked` for another identity's device and `mailbox.unknown-group`
for an unregistered group or another service. Vectors pin the mailbox decisions; the group demo shows
the hub taking identity from the header (mutation: taking it from the connection makes the hub refuse
Bob's deposit with `policy.blocked`).

**Suggested fix.** Adopt the M§5.2 text now in the draft. Hub changes (M§7.4) will need the device to
update the registration's hub when it processes the GroupContextExtensions commit.

## 46. M§14.2 — `origin` on hub-forwarded welcomes

**Gap.** M§14.2 requires a mailbox to verify a hub-forwarded welcome's `origin` but does not say that
the adder identity is *taken from* it (rather than from the hub's connection or any other field), what
kind of deposit it must be, whether it must name the same group, whether its own replay window applies
(it cannot: it is presented after delivery), or what to answer when it fails.

**Choices considered.** (a) `origin` is verified as a credential, must be a `handshake` deposit for the
same group within 300 s of the hub deposit, and alone names the adder; failures are `policy.blocked`,
while a proven adder without authorization stays `policy.first-contact-required`. (b) Trust the hub to
name the adder: gives every hub the power to impersonate adders to first-contact controls. (c) Reuse
`policy.first-contact-required` for everything: conflates "who added you is unknown" with "they may
not add you".

**Draft choice.** (a). Vectors pin the 300 s bound as inclusive, a mismatched group, a missing origin,
and that a claim beside the origin cannot override it.

**Suggested fix.** Adopt the M§14.2 text now in the draft.

## 47. M§6.5 rule 5 — a device's own items come back to it

**Gap.** The hub fans every item out to the sender's own identity "which is how a user's other devices
see sent messages". The sending device receives that copy too, and MLS does not let a member decrypt
its own messages, so a device that simply processes its mailbox fails on everything it sent. The
profile does not say how the copy is recognised; content-id deduplication (M§8.5) needs a decryption.

**Choices considered.** (a) The `seq` in the hub's `accepted` marks the item processed (it joins the
device's durable seq positions, spec-gap 44), and a copy that arrives before the `accepted` is
recognised by its MLS bytes. (b) Recognise copies only by bytes: lost on restart, so a copy redelivered
after a restart fails. (c) Hubs skip the sending device: the hub knows identities, not which device's
mailbox copy serves which device, and the identity's other devices need the copy.

**Draft choice.** (a). The demo exercises both paths: the hub owner's `accepted` arrives before its copy
(`DUP`), and a forwarded deposit's copy can beat its `accepted` (`SELF`); removing both fails the demo.

**Suggested fix.** Adopt the M§6.5 text now in the draft.

## 48. M§5.6 — the blob endpoint has no refusals

**Gap.** M§5.6 defines the success of `PUT {blob_endpoint}/{sha256}` (`201` with a signed `accepted`)
and what the mailbox must verify, but no HTTP status or reason for any failure, no answer for a hash
already stored, and nothing for `GET`. No registered token fits a body that does not match its
authorization (`mailbox.object-too-large` is about size limits, `policy.blocked` about who may act).
It also leaves open whether the URL's hash must equal the envelope's, and whether an authorization
minted for one mailbox can be replayed at another.

**Choices considered.** (a) Statuses in the order a server can decide them — `401` credential, `403`
addressee and served identity, `400` URL/authorization mismatch, `413` declared size before reading the
body, `400` body mismatch with a new `mailbox.blob-mismatch` — with a signed `error` body, idempotent
`200 duplicate` for a stored hash, `404` for an unknown `GET`. (b) One `400` for everything: clients
cannot tell a retryable upload from a forbidden one. (c) Silent `201` for a stored hash: hides that
nothing new was stored, which quota accounting will need.

**Draft choice.** (a). Vectors pin the order and each status; the PoC serves blobs on the mailbox's own
TLS port beside `ws/1.0`, and its demo checks `401` for an unauthorized `PUT`, `404` for an unknown hash
and the stored ciphertext for a known one (mutation: accepting an unauthorized upload fails it).

**Suggested fix.** Adopt the M§5.6 table and the `mailbox.blob-mismatch` registry entry now in the draft.

## 49. M§5.4 / M§11.2 — ephemeral activity cannot reach a device

**Gap.** M§11.2 says hubs and mailboxes push `ephemeral` deposits to bound devices, never store them,
drop them at `expires_at`, and that a receiver clears an indicator at the last refresh's `expires_at`.
But the only message a mailbox pushes with is `items`, whose items require `cursor` and `stored_at` and
have no `sealed` field, so a pushed activity cannot be expressed. And because carriage is fresh on every
hop (M§5.1), each hop signs a new envelope with its own `expires_at`: nothing says whose expiry the
receiver clears at, and a hop that issues a fresh 10 s lifetime extends the activity at every hop.

**Choices considered.** (a) A second item form for pushes — `{class: ephemeral, group, source, sealed,
expires_at}`, no cursor — where `expires_at` is the originating deposit's, carried unchanged, never
extended by any hop (forwarded envelopes expire no later), enforced by each hop and by the receiver.
(b) Deliver activity in a separate message type: one more type for the same carriage. (c) Receivers clear
after a fixed 10 s from arrival: stale indicators after queueing delays, and hops can still extend.

**Draft choice.** (a). The item schema is a `oneOf` of the stored and pushed forms; vectors pin the
schema, a mailbox dropping an expired push, and the receiver's indicator (shown until the refresh's
expiry, extended by a refresh, cleared by `stopped`, ignored when already expired). The receipts demo
shows typing clearing at expiry; a hub that extends the lifetime gets its forward refused downstream by
the 10 s rule and fails the demo.

**Suggested fix.** Adopt the M§5.4 and M§11.2 text now in the draft.

## 50. M§6.5 rule 5 — a new device of an existing member never gets a welcome

**Gap.** Rule 5 sends a `welcome` "to each added identity". When a member adds its own new device
(M§6.7, M§12.3 step 4), the identity is already in the roster, so a literal reading sends no welcome —
and the device, which is not in the group yet, has no other way to join.

**Choices considered.** (a) Welcome every identity that gains a device the group did not have. (b) The
adding device delivers the welcome to its own mailbox directly: a second path for one thing, and it
bypasses the hub's ordering of the welcome after its commit. (c) The new device external-joins (M§6.8):
defeats "an existing device adds it", which is what carries the archive keys.

**Draft choice.** (a). Vectors pin it, and that a commit adding no new device sends none; the
multidevice demo fails without it.

**Suggested fix.** Adopt the M§6.5 text now in the draft.

## 51. M§12.3 — what a new device meets when it syncs from null

**Gap.** "The new device syncs from `null`. It decrypts archive records for history and MLS items from its
join epoch onward" leaves out what happens on the way. Items arrive in cursor order, so the device meets
archive records before the personal-group welcome that brings their key, MLS items of groups it has not
joined yet and of epochs before its join, and its sibling's welcomes, which hold none of its KeyPackages.
Read literally, it acknowledges and loses the archive, fails on the MLS items, and — because a committed
welcome counts as a join (spec-gap 44) — drops its own later welcome for the same group as a duplicate.
M§12.2 also archives only what a device "decrypts", so no device ever archives its own sent messages, and
"newest `akid`" does not say newest by what. Archive `items` carry neither `ref_group` nor `ref_seq`, which
the AAD needs.

**Choices considered.** (a) Hold unknown-key archive durably and open it on the key; skip unjoined-group and
pre-join MLS items; acknowledge a sibling welcome without joining; archive own sent content with the
`accepted` seq; current key by `created_at` then `akid`; file archive items under `ref_group` with `seq` =
`ref_seq`. (b) Delay acknowledgement of anything unreadable: a mailbox in `queue` mode then retains
items forever for a device that can never read them. (c) Put archive keys in the new device's welcome
(group context or a custom extension): mixes identity-level secrets into every group's state.

**Draft choice.** (a). `messaging/history-*` pins hold/release, per-key release, archive/MLS collapse,
seq-order display, pre-join skip, no-key no-archive, newest-key archiving and own-content archiving;
`resume-sibling-welcome-is-not-a-join` pins the welcome rule. The multidevice demo exercises hold, release,
sibling welcomes, pre-join skipping and history in seq order; removing the archive-key re-send, counting a
sibling welcome as a join, or skipping nothing before the join each fail it. The epoch-race variant of the
pre-join rule (an old-epoch message sequenced after the add) is pinned by vector only.

**Suggested fix.** Adopt the M§12.1–M§12.3 text now in the draft.

## 52. M§10.5 vs M§8.1 — a private read watermark cannot name its conversation

**Gap.** M§10.5 sends an undisclosed `read` watermark to the personal group. A `read` names its
conversation, but M§8.1 requires every receipt's `conversation` to equal the carrying group's, so a
sibling device must reject it — or the watermark cannot say which conversation was read.

**Choices considered.** (a) Exempt `read` receipts in the personal group from the conversation match; they
name the conversation they describe. (b) A new object type for synced watermarks: one more type for the same
content. (c) Per-conversation personal subgroups: multiplies groups.

**Draft choice.** (a), only for `read` in `kind: personal`; other objects there still must match. Vectors
pin both sides; the demo shows the laptop's private read reaching the phone, which then sends nothing.

**Suggested fix.** Adopt the M§10.5 text now in the draft.

## 53. M§5.7 / M§12.4 — a removed device unregisters the group for its whole identity

**Gap.** A device that learns it was removed from a group naturally tells its mailbox `left` (M§5.7). But
the registration is the identity's (M§6.6), so when one device is removed while a sibling stays (M§12.4),
that `left` makes the mailbox refuse the hub's fan-out for the sibling (`mailbox.unknown-group`). The first
multidevice run lost the phone's next message exactly this way.

**Choices considered.** (a) A removed device sends `left` only when no leaf of its identity remains (it can
see the remaining roster in the removing commit). (b) Per-device registrations: mailboxes would track
device membership they cannot verify. (c) Never send `left` on removal: registrations linger after an
identity is removed.

**Draft choice.** (a). Vectors pin both cases; sending `left` unconditionally fails the demo.

**Suggested fix.** Adopt the M§5.7 text now in the draft.

## 54. M§14.1 / §19.4 — where a messaging introduction goes

**Gap.** M§14.1 says messaging "reuses §19.4 unchanged in structure", but §19.4 delivers introductions
through relays, and a messaging identity's DID document may list only a `DSIPMailbox`. Nothing says how an
introduction reaches such an identity, how the grant comes back, or whether the relay rules (mandatory rate
limits, anti-enumeration, a bounded inbox, holding until expiry) apply to a mailbox. The PoC's messaging demos
passed grants between identities as files until now.

**Choices considered.** (a) Two deposit classes, `introduction` and `grant`, carrying the signed envelope
(no group), with §19.4's relay rules applied by the mailbox. (b) Require messaging identities to also run a
relay binding: every messaging device would need a second connection for requests. (c) A new profile message
type: the same carriage with another type.

**Draft choice.** (a). The mailbox verifies the envelope fresh at deposit (pipeline, delegation, 4,096-byte
cap, profile introduction rules); it rate-limits per sender identity and per recipient inbox
(`policy.rate-limited`, `retry_after`); an introduction for an unserved identity or past the bounded inbox
is accepted and not held (indistinguishable from delivery); held items leave at `expires_at`. Devices
render introductions as requests and verify delivered grants as credentials (signature and signer binding),
because a grant's delivery window has passed by the time it is read. Vectors pin the deposit shapes and the
mailbox rules; `demos/messaging-first-contact-demo.sh` exercises them end to end and fails without sealing,
without anti-enumeration, or without rate limiting.

**Found alongside.** The PoC mailbox accepted a presented grant after checking only its signature, not that
its signer was delegated by the grant's `from`, so any device could forge consent. Fixed
(`dsip_mailbox::verify::grant_credential`, unit-tested with an honest, a bare and a forged grant).

**Suggested fix.** Adopt the M§5.2 rows and the M§14.1 "Carriage" text now in the draft; §19.4 in the v0.8
core should say its relay rules apply to any service that holds introductions.

## 55. M§6.9 — the key agreement key of a delegated identity

**Gap.** M§6.9 seals introductions to the identity's X25519 `keyAgreement` key. For `did:key` it is derived
from the Ed25519 key. For a `did:web` identity whose messaging is done by delegated devices, nothing says how
those devices hold the private half, and the DID document shape for it is not given.

**Choices considered.** (a) Leave provisioning deployment-defined (like the controller key), publish an
embedded `Multikey` X25519 method under `keyAgreement`, and allow the `did:key`-style derivation as one
arrangement. (b) Seal to each device key: the sender does not know the device set, and every device would
see the others' requests anyway. (c) Seal to the mailbox: the mailbox would read requests.

**Draft choice.** (a). The PoC derives the key from the identity key and publishes it; vectors pin the
derivation (`x25519-key-agreement-from-ed25519`) and HPKE itself against RFC 9180 A.1.1, and `dsip-mls`
cross-checks the profile's HPKE against `hpke-rs` in both directions.

**Suggested fix.** Adopt the M§6.9 text now in the draft.

## 56. §7.4 — a messaging-only device cannot introduce or grant

**Gap.** Core §7.4 binds a device-signed envelope to its `from` identity through a delegation carrying
`dsip.signaling`. The Messaging Profile delegates devices with `dsip.messaging` (spec-gap 39), and M§14.1
has devices sign core `introduction` and `grant` envelopes. A device delegated for messaging only is
therefore refused when it introduces or grants, by every verifier following core. The PoC's devices carry
both capabilities, which hides the problem; `dsip-mailbox`'s grant test pins today's refusal.

**Choices considered.** (a) Core §7.4 names the capability per message type, with `introduction` and `grant`
accepting `dsip.messaging` as well as `dsip.signaling`. (b) Messaging devices always also carry
`dsip.signaling`: over-grants signaling authority to devices that do not call. (c) The identity key signs
first-contact messages: puts the controller key on every device.

**Disposition (v0.8 core, 2026-09-17).** (b), decided by the editor: binding every envelope keeps requiring
`dsip.signaling`, profile capabilities are added beside it, and a Messaging Profile device carries both. §7.4
states it with the `dsip-delegation-capability` registry (spec-gap 39); `envelope/hello-messaging-only-delegation-rejected`
pins it.

## 57. §7.4 — a device delegation cannot be revoked

**Gap.** Core §7.4 verifies a delegation by signature, subject key, capability and its own
`issued_at ≤ now < expires_at`. Nothing revokes one before it expires, and a device presents its own delegation
in every envelope header. Key rotation (§7.5) invalidates delegations only by retiring the identity key that
signed them, which takes every device down with it. The Messaging Profile's M§4.3 and M§12.4 assumed that a
lost device "stops being served at its next hello because its delegation no longer verifies" — it keeps
verifying for its full lifetime (a year in the PoC). The multidevice demo showed it: a removed laptop still
connected to its identity's mailbox.

**Choices considered.** (a) A `delegation-revocation` record signed directly by a key of the subject, covering
the device's delegations issued at or before `revoked_at` (so the device can be re-enrolled with a later one),
published in the subject's DID document (authoritative, §8.1) and honored from any other source too, because
it can only remove authority. (b) Short-lived delegations renewed continually: puts the identity key online for
every renewal and still leaves a window. (c) Delegations valid only while listed in the DID document: every
verifier needs a fresh document for every device, and `did:key` identities cannot list anything. (d) Rotate the
identity key: revokes all devices at once.

**Draft choice.** (a). Verification adds `delegation-revoked` after capability and expiry. A mailbox accepts
revocations from its owner in `mailbox-config.revoked_delegations`, keeps them for every later verification,
closes the device's live binding, and forgets its registration and KeyPackages. Vectors pin revocation in the
document and in a store, the `revoked_at` boundary, re-enrollment, other devices unaffected, revocations signed
by anyone other than the subject (including the device itself) ignored, the binding every envelope passes, the
record shape, and the mailbox's reaction. The revocation demo: the laptop is disconnected at once, refused by
its own and by Alice's mailbox (which reads Bob's document), removable by Alice only after revocation (M§7.3),
and removed by Bob's phone with the archive key rotated; it fails if verifiers ignore revocations, if the mailbox
keeps the binding, or if a member may remove a leaf that still verifies.

**`did:key` identities** have no document: their revocations reach verifiers only by distribution (their own
mailbox in the PoC). The v0.8 core should say where else they are carried.

**Suggested fix.** Add `delegation-revocation` as a core message type and verification stage in the v0.8 core
(§7.4), with the `dsipDelegationRevocations` document property; adopt the M§4.3, M§5.7 and M§12.4 text now in
the draft. The record schema is staged in `v0.8/dsip-messaging-schemas-draft/` until the core schema set moves.

## 58. M§6.5 — what a member does when the hub refuses its commit

**Gap.** M§6.5 says a member that gets `mailbox.commit-conflict` "syncs, processes the winning commit, and
re-proposes if still needed". It does not say whether `mailbox.stale-epoch` (the member was more than one
epoch behind) is handled the same way, how many times a member re-proposes under contention, what "still
needed" means, or how the new core `mailbox` category fallback (§15.3: re-sync, retry once, then surface)
applies to refusals the profile does not name. A device that retries without bound can loop against a busy
hub; one that merges a refused commit forks the group.

**Choices considered.** (a) Conflict and stale epoch alike: discard, sync past the epoch committed from,
re-propose while still needed, at most three proposals; unregistered `mailbox.*` retried once per the core
fallback; everything else surfaced without retry. (b) Retry until accepted: unbounded under contention.
(c) Never re-propose automatically: every conflict becomes a user-visible failure for what is routine
concurrency.

**Draft choice.** (a), stated in M§6.5 as a 1.0 erratum (the profile was published in v0.8). The
`commit-retry-trace` vectors pin the outcomes; the reference device runs every commit (add, remove, device
changes, rekey) through the pinned machine. `demos/commit-conflict-demo.sh` makes a member commit from a stale
epoch twice — one epoch behind (`commit-conflict`) and two behind (`stale-epoch`) — and shows the hub refuse,
the member sync and re-propose, and both members still reading each other; merging regardless of the answer
or re-proposing without syncing fails it.

**Suggested fix.** Carry the M§6.5 text into the next profile revision.

## 59. M§6.5 / M§6.6 — a restarted hub or mailbox, and redelivered fan-out

**Gap.** Rule 5 of M§6.5 makes the hub retry an unacknowledged fan-out, so a member mailbox receives the
same `(group, seq)` again whenever an acknowledgement is lost — on a dropped connection, or when the hub
restarts between the mailbox storing an item and the hub hearing so. M§6.6 does not say what the mailbox
answers: storing it again gives the owner's devices a second item for one `seq` (a duplicate they must
catch), and refusing it leaves the hub's queue stuck. Nothing says which hub or mailbox state must survive a
restart, either. A hub that forgot its epoch or `seq` counter would re-number items or accept a second
commit for an epoch — a fork; one that forgot its queues would silently lose fan-out. A mailbox that forgot
its counter would re-issue cursors devices already hold; one that forgot `ack_through` would delete in
`queue` mode too early or never; one that forgot its rate window or seen ids would reset §19.4 limits or
accept a replay.

**Choices considered.** (a) A `seq` at or below the highest stored for the group is a redelivery: `accepted`
with `duplicate` (and the original `cursor` while the item is held), not stored or pushed; all ordering,
queue and answer state durable; live bindings not state; a restarted hub re-sends every queue head at once.
(b) Deduplicate only against items still held: a redelivery after `queue`-mode deletion would be stored as
new. (c) Leave duplicates to devices (M§8.5 already makes them idempotent): correct for content, but the
mailbox grows and pushes the item again, and every restart re-delivers every in-flight item to every device.

**Draft choice.** (a), stated in M§6.5 and M§6.6 as a 1.0 erratum. The `mailbox-trace` and `hub-trace`
vectors gain a `restart` event (the machine's full state round-trips through JSON; bindings are dropped):
`mailbox-restart-*` (items, cursors, acknowledgements, registrations, pending age, KeyPackages, revoked grants,
archive index, rate window), `mailbox-hub-deposit-redelivered-*` (held and deleted), `hub-restart-*` (queue
heads re-sent; epoch, digests and `seq` kept). The service saves its full state after every change —
machines, the hub's public MLS view, payloads, fan-out still queued, revocations, seen ids — and reloads it;
queue heads left unacknowledged are re-sent at start and then with doubling delay (4 s up to 60 s).
`demos/mailbox-restart-demo.sh` kills a mailbox with a message waiting and the hub with fan-out to a mailbox
that is down, and shows nothing lost, replayed or reordered and the reloaded hub validating the next commit;
skipping the reload, the retries, or the public view's reload each fail it.

**Open.** A welcome is fanned out once, outside the queues (M§6.5 rule 5 queues only sequenced items): an added
member whose mailbox is down misses it until a later welcome or an external join. Queuing welcomes is left to
the next profile revision.

**Suggested fix.** Carry the M§6.5 and M§6.6 text into the next profile revision; consider queuing welcomes.

## 60. M§7.4 — moving a group to another hub

**Gap.** M§7.4 gives the move in four sentences: a GroupContextExtensions commit changes the hub, the old hub
orders it and then refuses the group, members deposit to the new hub, which initializes from the latest
GroupInfo. Running it needs answers the text does not give. (1) Numbering: devices track per-group `seq`
(M§6.5, M§8.5) and archive records are sealed to `(group_id, seq)` (M§12.2), so a new hub starting at 1 would
make new items look like redeliveries and collide archive records — but nothing tells the new hub where the
old one stopped. (2) Member mailboxes admit fan-out only from the registered hub (M§6.6) and forward only to it
(spec-gap 45): who changes the registration, and when, without letting the new hub's items overtake the old
hub's last ones? (3) What a member that missed the move does with the old hub's `mailbox.unknown-group`.
(4) Whether a GroupContextExtensions commit may change anything else in `dsip_conversation`.

**Choices considered.** Numbering: (a) continue — the committer carries the moving commit's `seq`
(`handover_seq`) to the new hub; (b) restart per hub — breaks the archive AAD and every device's
duplicate test; (c) the old hub hands over directly — nothing binds the old hub's identity for the new
hub to check, and a dying old hub strands the move. Registration: (a) the owner's device, after processing
the MLS-verified commit, names the new hub and `handover_seq` in `mailbox-config`; (b) the mailbox follows
the old hub's word — lets a hub redirect a group it no longer orders. Missed move: (a) sync, re-send if the
sync shows a move, else final; (b) surface every `unknown-group` — a routine move becomes a user error.

**Draft choice.** (a) throughout, in M§7.4 as a 1.0 erratum: only the hub may change; the old hub orders
the move then refuses the group while its queues drain; the new hub starts at `handover_seq + 1` and hosts
a group only if `dsip_conversation` names it; a mailbox switches on its owner's `mailbox-config` (new
fields `hub_uri`, `handover_seq`), keeps admitting the old hub through `handover_seq`, holds the new hub off
(`mailbox.unknown-group`, retried) until those items are stored, and refuses the new hub's items at or below
it (`policy.blocked`, so a wrong handover fails loudly instead of being dropped as duplicates); a device that
gets `unknown-group` syncs and re-sends only if the group moved. A wrong `handover_seq` from a member is
detected, not prevented: too low is refused by every mailbox, too high is a gap (M§6.5 rejoin).

Vectors: `hub-move-*` (ordered then refused, queues drain, numbering continues), `mailbox-hub-move-*`
(switch, old-hub redelivery, waiting for the handover, renumbering refused), `commit-retry-unknown-group-*`,
`conversation-update-*` (only the hub changes), and the new wire fields. Real MLS (`dsip-mls` e2e): the
public view recognises the move and refuses a commit changing `kind`. `demos/hub-change-demo.sh` moves a
three-member group from Alice's mailbox to Bob's while Carol's device is offline; Carol posts before syncing,
is refused by the old hub, syncs and re-sends. A mailbox ignoring the switch, a new hub restarting at 1, a
device not re-sending, and an old hub that keeps ordering each fail it.

**Open.** None; an old hub that dies before delivering the move to some mailbox is spec-gap 71.

**Suggested fix.** Carry the M§7.4 text into the next profile revision; register `hub_uri` and `handover_seq`.

## 61. M§7.5 — successor groups: re-adding members, checking, converging

**Gap.** M§7.5 lets any member recreate a group whose hub is gone, and says mailboxes admit the successor's
welcome without a grant, clients check creator and roster, and concurrent successors converge on the lowest
`group_id`. Building one over the wire needs more. (1) The creator must fetch every member's KeyPackages, and
M§5.5/M§14.2 demand a grant it may not hold (in a group, members hold grants only from whoever added them).
(2) Hubs fan welcomes out; nothing says the fanned-out welcome carries `successor_of`, which is what the
mailbox admits it by. (3) "The successor's creator": MLS has no creator field. (4) What "converge" does to a
device already in a higher successor, or that created one; and whether a member should create a successor when
one exists. (5) What a device does with an invalid one its mailbox admitted only as a successor.

**Choices considered.** (1) (a) a registered predecessor authorizes the fetch, mirroring the welcome; (b)
require grants — successors fail in exactly the groups that need them; (c) re-add only identities the creator
holds grants from — silently drops members. (3) (a) leaf 0, the creating leaf; (b) the committer of the
first Add — needs the commit history, which a joiner does not have. (4) (a) keep candidates, stay only in the
lowest, leave a higher one joined or created; (b) first successor wins — not convergent under concurrency.

**Draft choice.** (a) throughout, in M§7.5 as a 1.0 erratum: `key-package-fetch.successor_of`; the hub
carries `successor_of` on successor welcomes; creator = leaf 0; candidates per predecessor, lowest kept, a
device leaving the others with `mailbox-config left`; a member already converged uses that successor instead of
creating one; the reference device leaves an invalid successor (its mailbox admitted it only as one), which is
"new conversation under first contact" with no grant behind it. When a hub counts as dead stays the member's
call (the reference device acts on an explicit `successor` command).

Vectors: `successor-trace` (valid joined, invalid and unknown-predecessor as first contact, a lower successor
arriving later switches, a higher one declined, create when one exists, own successor losing or winning against
a concurrent one, non-member refused), `mailbox-key-packages-for-successor`, `key-package-fetch-successor-valid`.
`demos/successor-demo.sh` moves a three-member group to a dedicated hub service, kills it and deletes its state;
Bob and Carol create successors at the same moment; all three devices converge on the lower `group_id` and the
conversation continues there. A device keeping a superseded successor, a mailbox refusing successor KeyPackage
fetches, welcomes fanned out without `successor_of`, and joining every successor each fail it.

**Open.** A device that left a losing successor is still a leaf in it; its members can remove it once they
converge too (nobody is left to order anything there in practice). A dead hub that comes back finds its group
superseded; members ignore it (M§7.5 says nothing about the predecessor's future).

**Suggested fix.** Carry the M§7.5 text into the next profile revision; register `key-package-fetch.successor_of`.

## 62. M§6.8 — what an external commit may do, and who the joiner is

**Gap.** M§6.8 allows an external join when "its identity already has a leaf in the group" or the group is the
identity's personal group, with the commit removing "that identity's stale leaves it replaces", and requires hub
and members to check the same condition. Checking it needs definitions the text does not give. (1) Which leaf is
"its identity"? An external commit carries no Add proposal for the joiner (MLS installs the joiner's leaf through
the update path), so a hub looking at Add proposals sees nobody and cannot apply M§7.3 at all. (2) May the commit
add anyone else, or remove another identity's leaf? (3) What "stale leaves" means given MLS permits exactly one
Remove in an external commit — the resync of the joiner's own signature key — and that a returning device's old
leaf may no longer authenticate. (4) What a member does with an external commit that fails the check, and where
a device gets "the latest group-info" for a group it is not in. (5) The hub checks "the identity's own personal
group", but a hub machine built from a GroupInfo has no owner.

**Choices considered.** (1) (a) the path leaf, authenticated like any leaf (M§6.2); (b) the envelope's delegation
alone — a device could commit a leaf for another device. (2) (a) exactly the joiner's device, removals only of the
joiner's identity; (b) the M§7.3 member rules (whole-identity or lapsed removals) — an external joiner is not yet a
member and has no business removing anyone else. (3) (a) a removed leaf naming the joiner's device counts as the
joiner's even unauthenticated; (b) require it to authenticate — a device returning after its delegation lapsed
could never replace its leaf. (4) (a) not merged, surfaced; the latest group-info item the mailbox delivered is kept
per group. (5) (a) the mailbox hosting a personal group is its owner's (M§7.1).

**Draft choice.** (a) throughout, in M§6.8 as a 1.0 erratum. Vectors: `external-join-*` (new device of a member,
returning device replacing its own leaf, removing another own stale leaf, stranger, removing another identity,
adding another device, a leaf other than the sender's, personal-group owner and non-owner) and
`hub-external-commit-*` (removing another identity, bringing in another identity's leaf); the hub uses the same
check. Real MLS (`dsip-mls` e2e): a new device joins from a GroupInfo and the public view names it; a device with a
fresh store and the same key rejoins and the commit removes its old leaf; a stranger's external commit is refused.
`demos/external-join-demo.sh`: Bob's tablet joins his personal group and his conversation with Alice while his phone
is offline; then the phone loses its MLS state and rejoins, replacing its leaf; Alice and the tablet render both.
A hub view that misses the path-leaf joiner, a device that keeps no GroupInfo, members refusing valid joins, and a
check refusing any removal each fail it.

**Open.** None; rejoining on a gap that does not fill is spec-gap 69.

**Suggested fix.** Carry the M§6.8 text into the next profile revision.

## 63. M§13.3 — which devices send call events, and what the timeline does with them

**Gap.** M§13.3 has "a callee device that alerted and was not answered" send a `call-event` so "every device of
the identity shows one missed call", never for `session.answered-elsewhere`, and asks clients to interleave calls
with content by peer. Left open: whether every alerted device sends (then several events describe one call) or
only one does (which one, if the others are offline); what `outcome` a leg the user declined on this device gets;
how duplicates collapse, given `call-event` has no `id`; whether call events reach a device added later (M§12.2
archives only content and receipts); and how calls are placed among messages when M§8.5 forbids time from
reordering history.

**Choices considered.** Senders: (a) every alerted, unanswered device, collapsed by `session`; (b) one designated
device — none exists in DSIP, and it may be the one offline. Outcome: (a) `declined` for a local `user.declined`,
`missed` otherwise; (b) always `missed` — loses the difference the user sees. History: (a) archive call events;
(b) not — a new device has no call log. Placement: (a) content in `seq` order, each call before the first content
later than it; (b) sort everything by time — lets a backdated `sent_at` reorder content.

**Draft choice.** (a) throughout, in M§13.3 as a 1.0 erratum. Vectors: `call-event-*` (7 decisions),
`peer-timeline-*` (collapse, interleave, content order kept), `history-archived-call-event-applied`.
`demos/call-history-demo.sh`: a missed call on Bob's phone reaches a laptop added later via archive; with both
devices ringing, a call answered on the laptop leaves no event anywhere, a call both miss is reported by both and
recorded once on each, a call declined on the phone is `declined` on the laptop; the laptop's timeline with Alice
interleaves calls and messages. The reference device takes leg outcomes from a `call-ended` command (its messaging
process has no signaling leg); the decision is the pinned function.

**Suggested fix.** Carry the M§13.3 text into the next profile revision; register `outcome` values (`missed`,
`declined`) in a `dsip-call-outcome` registry.

## 64. M§12.2 — which receipts are archived, and what restoring them does

**Gap.** M§12.2 archives "a `receipt` that changes rendering" without defining the phrase, and says nothing
about what a device does when it opens archived receipts (or content) while restoring history: a device that
treats them as new items sends delivered receipts for weeks-old messages and archives everything again.

**Choices considered.** (a) Changes rendering = adds a delivered/played entry not held for that content and
identity, or advances that identity's read watermark; restored items update rendering state silently (no receipts,
no re-archiving). (b) Archive every receipt — duplicates and stale watermarks fill the archive. (c) Restore by
replaying records as live items — sends receipts for history.

**Draft choice.** (a), in M§12.2 as a 1.0 erratum. The receipt machine (`client-trace`) emits `archive {seq}`
exactly when a receipt changes its state (five existing vectors gain that emission where their receipts did; new
`client-receipt-archived-when-rendering-changes`), and gains a `restore` event that applies content and receipts
without emissions (`client-restore-from-archive-sends-nothing`); `history-trace` applies an archived receipt
instead of showing it (`history-archived-receipt-applied-not-shown`). In `demos/call-history-demo.sh` Bob's phone
archives Alice's delivered and read receipts; a laptop added later restores them (its receipt state shows Alice's
watermark) and sends no receipts for history. Mutation-checked: restoring like a live sync, never archiving
receipts.

**Open.** None; a device's own read watermark is archived under spec-gap 68.

**Suggested fix.** Carry the M§12.2 text into the next profile revision.

## 65. M§8.4 rule 6 — replicating blobs to member mailboxes

**Gap.** Rule 6 has a sync-mode member mailbox replicate "every manifest blob on receipt, verifying `sha256`, and
rewrite `uri` in `items`", with devices fetching from their own mailbox and "falling back to the original `uri`".
Unstated: whether size is verified too (the manifest carries it); what happens to a blob larger than the replicating
mailbox's own `max_blob_bytes`; whether a failed or mismatching fetch changes anything; which `uri` in `items` is
rewritten, given the content object's `uri` is inside MLS and cannot be; and how a device relates the unencrypted
manifest to the encrypted content — a manifest entry must not be able to point a device at a different blob.

**Choices considered.** (a) Replicate application items' manifest blobs in sync mode unless already held,
over the local limit, or not https; store only a 200 matching both hash and size; rewrite only held entries in
`items`; devices take a manifest entry as a source only for the exact `sha256` and `size` of the content's blob, try
it first, verify every source and fall through on mismatch. (b) Verify the hash only — sufficient on its own, but the
device checks both (rule 7), and one rule for mailbox and device is simpler to state and test. (c) Trust the rewritten `uri` alone — a damaged or malicious copy would make the
blob unplayable instead of falling back.

**Draft choice.** (a), in M§8.4 as a 1.0 erratum. Vectors: `blob-replicate-*` (9: fetch, queue mode, already
stored, too large, non-https, store verified, hash mismatch, size mismatch, unavailable), `items-blobs-rewrites-
held-blobs`, `blob-sources-*` (4). `demos/blob-replication-demo.sh`: Bob's mailbox replicates a voice message while
Bob is offline; Alice's mailbox crashes and Bob plays from his own mailbox; a damaged replicated copy fails Bob's
device's check and the original serves it; a message larger than Bob's mailbox's limit is not replicated and plays
from the original. A mailbox that never replicates, `items` not rewritten, a device ignoring its mailbox's copy, a
device that never falls back, and an ignored size limit each fail it.

**Open.** Replicated blobs are kept for as long as the items that reference them (no separate retention). Retrying a
failed fetch is spec-gap 67.

**Suggested fix.** Carry the M§8.4 text into the next profile revision.

## 66. M§6.5 rule 5 — a welcome is a fan-out too

**Gap.** Rule 5 queues sequenced items per member mailbox and retries an unacknowledged one before sending later
ones, but the welcome a commit sends to an added identity is not sequenced, so nothing said it is retried at all.
An identity whose mailbox is down when it is added therefore never learns of the group: the commit's `seq` goes to
the existing members, the welcome is sent once into the void, and the added member's devices wait forever (recorded
as the open item of spec-gap 59). Two further questions follow: what the hub does with items sequenced after the
add, since the added mailbox has no registration for the group until the welcome arrives and refuses them (M§6.6);
and what a mailbox does with a welcome it has already stored, once retries make duplicates possible — it cannot
simply drop a second welcome for a registered group, since that is how an owner's new device is let in (M§6.7).

**Choices considered.** (a) The welcome is queued in the added identity's own queue at the commit's `seq` and
retried like any fan-out; its items wait behind it; a mailbox answers a welcome whose MLS bytes it already holds
`accepted` with `duplicate` and that welcome's cursor. (b) Queue the welcome in the same queue as sequenced items — a
member adding its own device needs both the commit and the welcome for one `seq`, so one queue entry cannot carry
both. (c) Leave the welcome unretried and let the added member discover the group by external join (M§6.8) — it
cannot: an external join needs a `group-info` its mailbox would also have refused.

**Draft choice.** (a), in M§6.5 as a 1.0 erratum. A welcome has no `seq` on the wire (M§5.2), so its
acknowledgement is matched by the deposit it answers. Vectors: `hub-welcome-queued-and-retried` (queued, later items
held, released on acknowledgement), `hub-welcome-resent-after-restart`, `mailbox-welcome-redelivered-duplicate` (same MLS bytes),
`mailbox-welcome-for-another-device-stored` (different bytes, a sibling's invitation),
`mailbox-welcome-after-leaving-registers-again`; the two existing welcome vectors now show the queue.
`demos/welcome-retry-demo.sh`: Alice adds Carol with Carol's mailbox down (her KeyPackage fetched beforehand — new
`prefetch`, M§5.5 allows holding one), Alice and Bob carry on, and when Carol's mailbox returns the welcome lands,
her device joins once, and the messages that waited follow in order. A hub that sends the welcome once and never
queues it fails the demo.

**Suggested fix.** Carry the M§6.5 text into the next profile revision.

## 67. M§8.4 rule 6 — a replication that could not be made

**Gap.** Rule 6 replicates "on receipt". A member mailbox that receives an item while the sending mailbox is down —
or before the blob is readable there — fetches nothing, and nothing in the profile says whether it ever tries again.
The item then keeps the origin `uri` for good, which is exactly the case rule 6 exists to avoid. Retrying
indiscriminately is no better: a body that did not match the manifest will not match on the next attempt either.

**Choices considered.** (a) Retry only `unavailable` (no 200 to work with), with rule 5's backoff, bounded and
carried across restarts; never retry `mismatch`. (b) Retry everything — a mismatching or hostile origin is refetched
forever. (c) Retry nothing (the state before this gap) — a moment's outage costs the copy permanently.

**Draft choice.** (a), in M§8.4 as a 1.0 erratum, with 5 attempts RECOMMENDED. `blob-replicate` gains `attempt` and
answers `retry` on a discard. Vectors: `blob-replicate-unavailable-retried`, `-unavailable-bounded`,
`-unavailable-attempt-below-bound`, and the mismatch vectors now show `retry: false`. The service keeps failed
replications with their attempt count and next time, persists them, and runs them from the same timer as fan-out
retries. `demos/blob-replication-demo.sh` gains a stage: the blob is made unreadable at its origin while Bob's
mailbox is down, so its first fetch finds nothing; when the blob is readable again a later attempt stores it, and
Bob plays from his own mailbox. A mailbox that never retries fails it.

**Suggested fix.** Carry the M§8.4 text into the next profile revision.

## 68. M§12.2 / M§10.5 — a device's own read watermark is history too

**Gap.** M§12.2 archives what a device "decrypts": content, and (spec-gap 64) receipts that change its rendering. A
device's own `read` watermark is neither — it does not arrive, it is sent — so nothing archived it, and a device
added later had no idea where its user had read. The gap is plain in the personal group, which exists precisely so
an identity's devices share that watermark (M§10.5): the receipt is deposited, but only devices that were in the
group at the time ever see it.

**Choices considered.** (a) A device archives the `read` receipt it sends, under the group it sent it to and the
`seq` the hub accepted, and not its own `delivered`/`played` (those describe other identities' devices, which
siblings learn from those identities directly). (b) Archive every receipt a device sends — fills the archive with
`delivered` receipts that tell a sibling nothing. (c) Leave it: a new device re-reads everything as unread until
the user reads again.

**Draft choice.** (a), in M§12.2 as a 1.0 erratum. `history-trace`'s `sent` event takes an `object`: a `receipt` or
`call-event` is archived once and is not a timeline entry (`history-own-read-receipt-archived`).
`demos/call-history-demo.sh`: Bob's phone marks the conversation read (undisclosed, so the watermark goes to his
personal group), and the laptop added later restores it — its receipt state shows Bob's own watermark as well as
Alice's, and neither device shows a receipt as a conversation entry. Not archiving the watermark, and treating it as
timeline content, each fail the demo.

**Suggested fix.** Carry the M§12.2 text into the next profile revision.

## 69. M§6.5 / M§6.8 — re-joining when a gap will not fill

**Gap.** M§6.5 tells a device to hold a handshake beyond a `seq` gap and, if the gap does not fill within
`gap_timeout`, to re-join by external commit and treat every seq it has seen as passed. The rule was pinned
(`gap-trace`) but never wired into a device, and three things it leaves open decide whether it can be: what a device
does with a held item it cannot process (the mailbox may delete an item it has acknowledged, M§5.4); whether the
device's own deposits count towards its contiguous position, since their `seq` arrives in the hub's `accepted` and
never as an item (spec-gap 47); and whether `gap_timeout` is a protocol constant or the device's own choice.

**Choices considered.** (a) A held item is kept durably by the device and MAY be acknowledged — it has taken
responsibility for it, though it has not processed it — and is dropped on re-join; own deposits advance the gap
tracker exactly as they advance the resume position; `gap_timeout` is the device's (300 s RECOMMENDED). (b) Do not
acknowledge held items: the ack cursor is a single watermark, so one held item stalls acknowledgement for every group.
(c) Leave own deposits out of the tracker: a device then sees its own items as a gap and re-joins for nothing — which
is exactly what happened when this was first wired (Alice held Bob's re-join commit). A fourth question the wiring
answered the same way: a device counts gaps from where it starts — the first sequenced item a fresh member processes,
or the position an existing one committed — since everything before its welcome is history (M§12.3 step 5), not a gap
(every group demo failed until this was right).

**Draft choice.** (a), in M§6.5 as a 1.0 erratum. `gap-trace` takes `gap_timeout` in its context
(`gap-timeout-configurable`), and `resume-trace` gains `rejoined` (`resume-rejoin-passes-every-seq-seen`): every seq
up to the highest seen is passed, so a redelivery is a duplicate. The device holds items durably, advances its
trackers on a timer, and re-joins by external commit when one times out (`--gap-timeout` for the demo's sake).
`demos/auto-rejoin-demo.sh`: Bob is away while Alice rekeys, his mailbox loses an item he never acknowledged (what
`mls_retention_s` does), and on return he holds the rekey, re-joins by himself, and carries on from the current
epoch. A tracker that never times out, a device that does not hold beyond a gap, and a re-join that does not pass the
seqs behind it each fail the demo.

**Suggested fix.** Carry the M§6.5 text into the next profile revision.

## 70. §12.12 / G§9 — the DTMF binding

**Gap.** Spec-gap 26 left DTMF with nowhere to go: core has no DTMF semantics, and the gateway profile said a future
revision would define carriage, suggesting a gateway-defined `about` such as `x-gateway:dtmf`. That is the wrong
shape — DTMF is not gateway-specific (a DSIP callee may run an IVR, with no PSTN anywhere) — and "gateway-defined"
means every gateway invents its own, which G§9 itself forbids.

**Choices considered.** (a) A core binding: `media:dtmf` in `dsip-info-about`, `data` of `{digits, duration_ms?}`,
carried by `info` (§12.12) — ACTIVE-only, never critical, no reply, changes nothing negotiated; the gateway maps it
to and from SIP `INFO`. (b) `x-gateway:dtmf` as the profile suggested: private to gateways, so two DSIP endpoints
cannot send digits to each other. (c) A new message type: `info` exists for exactly this kind of in-session,
high-frequency, nothing-negotiated data.

**Draft choice.** (a), in §12.12 and G§9 as errata. `digits` is 1–32 RFC 4733 events (`0`–`9`, `*`, `#`, `A`–`D`) in
the order pressed; `duration_ms` (40–10,000) is each digit's tone length and is optional. Vectors: `payload/info-dtmf-*`
(7, through the binding data schema the harness validates per `about`), `state/info-active-only` (a `media:dtmf` info
is delivered like any registered one), `gateway/trace-dtmf-*` (both directions, ignored outside the call, other
`about` values not carried, and a digit arriving as an RFC 4733 event — a SIP-side event with nothing to answer). Mutation-checked: a gateway carrying any `about`, carrying DTMF before answer, an
unregistered `media:dtmf`, and an unconstrained `digits` each fail vectors.

**Open.** None. Both carriages are on the wire in the reference gateway (2026-09-17). INFO: one
`application/dtmf-relay` body per digit with an increasing CSeq, 160 ms when the DSIP `info` names no `duration_ms`;
inbound dtmf-relay on a known call is answered 200 and reported, other INFO payloads 415, unknown calls 481. RFC 4733:
the gateway offers `telephone-event` (payload type 101) and, when the trunk accepts it, sends each digit as a marked
start packet, 20 ms updates and the end packet three times on one timestamp, and reports a trunk's event once, on its
end packet, as the controller event `{"sip": {"event": "dtmf", …}}` (`trace-dtmf-rtp-events`), which answers nothing
on the SIP leg. RTP events are preferred when negotiated. `tests/round_trip.rs` proves both carriages both ways
against the SIP peer. Found on the way: the host re-sent the controller's `response` emission for a request the leg
had already answered — for INFO that would have been a second 200 to the INVITE.

**Suggested fix.** Register `media:dtmf` in `dsip-info-about` and carry the §12.12 and G§9 text into the next
revision.

## 71. M§7.4 — a move whose old hub never finishes delivering

**Gap.** Spec-gap 60 has a member mailbox hold the new hub off (`mailbox.unknown-group`, retried) until the old
hub's items through `handover_seq` are stored, so that items reach the owner's devices in `seq` order. It says
nothing about an old hub that dies after ordering the move and before every mailbox has those items. The
committer's own mailbox is the usual victim: the committer processes its own commit from `accepted` (spec-gap 47)
and names the new hub at once, so if the old hub's fan-out of that commit is lost, the mailbox waits for an item
that will never come and refuses its own hub forever. The reference service had a second problem underneath: a
hub delivered its own owner's fan-out in-process and acknowledged its queue unconditionally, so a refusal there
was never retried at all. (The other members are not stranded by this: their devices learn of the move only from
the old hub's fan-out, so their mailboxes have everything through `handover_seq` by the time they switch. A hub
that dies before fanning out to anyone is the dead-hub case, spec-gap 61.)

**Choices considered.** (a) Bound the hold: the mailbox waits `handover_wait` from the `mailbox-config` that
named the new hub, then admits it and leaves the missing seqs to the owner's devices, whose gap handling
(spec-gap 69) already covers a `seq` that never arrives; what the old hub still delivers after that, at or below
`handover_seq`, is stored out of order so a merely slow old hub fills the gap. (b) The committer tells its mailbox
it holds everything through `handover_seq` (a new `mailbox-config` field): true for the committer, false for its
sibling devices, and a device asserting what its mailbox should believe. (c) The new hub carries the old hub's
tail: it has nothing before `handover_seq + 1`, and the committer's `group-info` deposit is the wrong place for
other members' content. (d) Drop the hold and let devices sort every move out by gap handling: a routine move
would then cost every sibling device a `gap_timeout` and an external re-join.

**Draft choice.** (a), in M§7.4 as a 1.0 erratum. `handover_wait` is the mailbox's own (300 s RECOMMENDED,
`handover_wait` in the `mailbox` vector context, `--handover-wait` on the service), measured from the config
naming the new hub and durable across a restart. Expiry is an internal event of the mailbox machine
(`handover_expired`, naming the seqs given up on), not a wire message. After it, the old hub's items at or below
`handover_seq` are stored unless already stored, its items above it are refused as before, and the new hub's at or
below it are still `policy.blocked`. Vectors: `mailbox-hub-move-handover-wait-expires`,
`mailbox-hub-move-handover-wait-configurable`, `mailbox-hub-move-late-previous-items-stored`,
`mailbox-hub-move-handover-wait-survives-restart`. The service delivers its own owner's fan-out through the same
queue discipline as everyone else's (acknowledged only when the mailbox stored it, retried with backoff
otherwise), which the demo depends on. `demos/handover-wait-demo.sh`: a dedicated hub orders Bob's move, delivers
it to Alice and Carol, never to Bob's mailbox (`--drop-fanout-to`, fault injection), and dies; Bob's mailbox
refuses its own hub, the wait expires, the queued fan-out is retried, and Bob receives Alice's reply. A mailbox
that never releases (`HANDOVER_WAIT=100000`) fails it, as did the service's unconditional self-acknowledgement
before it was fixed (the refused fan-out was never retried).

**Open.** A sibling device of the committer, if the missing items included a commit, pays a `gap_timeout` and an
external re-join (spec-gap 69); so does the committer itself if other members' items were lost along with its
commit (the demo lets receipts land before the move for that reason); nothing shorter is available without the
old hub. The reference service's
mailbox clock (advanced before each message and every 2 s) now drives the machine's other timers too (§19.4
held-introduction expiry, M§6.6 pending groups), which no demo exercises yet.

**Suggested fix.** Carry the M§7.4 text into the next profile revision.

## 72. M§9.4 — the hub cannot be reached

**Gap.** M§9.4 says a client keeps content pending, retries with the §13.2 backoff, never deposits into members'
mailboxes directly, and treats a hub unreachable past a client-chosen threshold (24 h RECOMMENDED) as the M§7.5
successor trigger. Nothing pinned it: the reference device sent once, waited 20 s for an answer, and reported an
error with nothing kept; the mailbox, whose dial to the hub had failed, told the device nothing at all (a forward
queued behind a failed dial was dropped, and one in flight when the connection ended was forgotten); and the only
way a successor group ever came about was a person typing `successor`. Coverage found it: M§9.4 was the one
normative section of the profile with neither a module nor a vector (`docs/coverage.md`, spec-lint since PR #29).

**Choices considered.** (a) An explicit signal: the mailbox answers `mailbox.hub-unreachable` when it cannot hand a
forward to the hub, and the device also treats silence as an outage; the device's outbox is a machine with a
pinned backoff and threshold. (b) Silence only: the device infers the outage from its own answer timeout — slow
(20 s per attempt), and a mailbox that knows the hub is down would still say nothing. (c) The mailbox retries on the
device's behalf: it would have to hold content and re-sign nothing (the envelope is the device's), and M§9.2's
"pending" state is the device's to show; a mailbox is not the place for a device's outbox. Threshold: (a) counts
from the start of the current outage, reset by any `accepted`; (b) cumulative downtime — a flapping hub would then
be abandoned for no reason.

**Draft choice.** (a) throughout, in M§9.4 as a 1.0 erratum and `mailbox.hub-unreachable` in M§16. The outbox:
new content is encrypted at once and queued behind the pending items; the head is re-deposited as the same bytes
after 1 s, doubling to 60 s (the ceiling; a host adds jitter); an `accepted` ends the outage, flushes in order and
resets the backoff; any other refusal leaves the outbox for its own handling; at `hub_timeout` the device creates
the successor, re-encrypts the pending items for it, and abandons the dead group's outbox. Pending items and the
outage's start are durable. Vectors: `hub-outage-*` (6, `hub-outage-trace`) and
`mailbox-forward-hub-unreachable-answered`. Reference: `dsip-messaging::client::HubOutage`; the mailbox service
answers every forward a failed or lost hub connection left unanswered; `dsip-msg --hub-timeout`, `PENDING` /
`OUTAGE-SUCCESSOR` / `RESENT` lines. `demos/hub-outage-demo.sh`: the hub service dies; Alice's message is pending
and retried at 1, 2, 4, 8 s; a second one queues behind it; at 12 s her device creates the successor, re-adds Bob
and Carol and re-sends both; they converge and reply. A device that never gives up (`HUB_TIMEOUT=100000`) fails it,
and exactly one successor is created.

**Open.** A member that has nothing to send never notices the dead hub and creates no successor; it converges on
one another member creates. If nobody has anything to say, the group just stays dead until someone does, which is
what M§7.5 says. Whether receipts and typing (which also go through the hub) should count as content that keeps
the outbox alive is a host choice; the reference device queues application content only.

The hand-over to the successor can itself fail, and the reference device must not lose content to that. An item
leaves the dead group's durable outbox only once the successor's outbox has it. An item whose deposit failed after it
was encrypted for the successor is treated as a deposit with no answer (it stays pending in the successor's outbox
and is retried with the backoff, the later items queueing behind it — `RESEND-PENDING`); the successor's hub being
unreachable too is the same state reached through the ordinary answer. If the successor cannot be created at all, or
an item cannot be encrypted for it, the items stay in the dead group's outbox in order and the hand-over is tried
again with the §13.2 backoff (`SUCCESSOR-RETRY`); the dead group's outage stays abandoned with its start kept, so
nothing goes to the dead hub meanwhile and a restart resumes the hand-over. Delivery into the successor is therefore
at-least-once: a crash between the successor's `accepted` and the local save re-sends that item (same content `id`).
The item-level part is host behaviour built from the pinned `no_answer` event and the restart rule above. The retry
of the hand-over itself is the outbox's, and pinned: once `abandoned`, the event `{"handover_failed": {}}` (the host
could not create or find the successor, or could not move every item into it) is counted in `handover_attempt` — a
snapshot member, 0 until the first failure — and answered `{"handover_retry_in": d}`, where d is the §13.2 series
started afresh (1 s, doubling, 60 s ceiling), independent of `attempt`; the `advance` that reaches that time emits
`{"handover": "retry"}` once, and the next failure schedules the next. Every `handover_failed` counts, whether or not
a retry is already scheduled (the later schedule replaces the earlier). In any other state `handover_failed` emits
nothing and changes nothing; deposits stay refused (`group-abandoned`) throughout. Vectors: `hub-outage-handover-*`
(2). A host that completes the hand-over simply drops the dead group's outbox.

**Suggested fix.** Carry the M§9.4 text into the next profile revision; register `mailbox.hub-unreachable`.

## 73. §9.3 / §15.1 / §15.4 — reason tokens on `notify`

**Gap.** §9.3 says a terminal `notify` SHOULD carry a `reason`, "e.g., `session.expired` for lapsed subscriptions,
`policy.terminated` for revoked authorization". §15.1 lists the reason-carrying types as `reject`, `cancel`, `bye`
and `error` — not `notify` — and the §15.4 "valid on" column gives `session.expired` to `reject` only and
`policy.terminated` to `bye` only. An implementation that applies the column as written flags the spec's own
example. Found by the second implementation (`impl-ts/`, written from the spec and the vector README alone): it
accepted `semantic/notify-terminated-reason` with `warnings: ["reason-not-valid-on-type"]`, the Python harness and the
Rust runner with none. The vector README did not say how `actual` is compared with `expect`; read as "the members
`expect` names", the extra warning passed. (The existing runners compare for deep equality; the README now says so.)

**Choices considered.** (a) The column does not apply to `notify`: any registered token is warning-free there.
(b) Apply it and extend the registry: add `notify` to the "valid on" cell of each token a terminal notify may carry
(`session.expired`, `policy.terminated`, `policy.blocked`, `identity.not-in-service`, …) — precise, but it needs a
decided list the spec does not have. (c) Apply it as written: every reasoned `notify` warns, including the spec's own
examples.

**Draft choice.** (a) now, (b) as the spec fix. `notify` is named in the README's effective-reason rule, and the
README now states the deep-equality comparison (absent `warnings` = none), which is what pins this — the existing
vector needed no change. Reference: all three implementations agree; `impl-ts/src/semantic.ts` carries the `Impl:` note.

**Suggested fix.** §15.1: add `notify` to the types that carry a `reason`. §15.4: add `notify` to the "valid on"
cells of `session.expired` and `policy.terminated` (and whichever others §9.3 means), or state that the column
governs only `reject`/`cancel`/`bye`/`error`.

**Applied to the spec (2026-09-18).** The second form, which is what the vectors pin: §15.1 names a terminal `notify`
among the reason-carrying types, and §15.4 says the "valid on" column governs the four session types and not `notify`,
where any registered token is valid. A.5 errata. No vector or code change.

## 74. §19.4 — who an introduction's outcome is addressed to

**Gap.** §19.4 gives two signed outcomes for an introduction, `grant` and `reject`, and says nothing about their `to`.
Its `grant` example is addressed to `did:key:z6MkCarolPhone` — by its name a device — for an introduction `from` the
same DID. The vectors pin an asymmetry nobody chose on the page: the endpoint sends the `grant` to the introducing
**identity** (resolved through the delegation) and the `reject` to the introducing **device** (the introduction's
`from`). Found by the second implementation, which addressed both to the identity and failed
`state/first-contact-reject-and-silence`.

**Choices considered.** (a) Both to the identity: a grant is held by an identity (any of its devices may invite
under it), and a rejection is equally the identity's to know; the relay fans out. (b) Both to the introduction's
`from`: simplest, but a grant that reaches one device leaves the identity's other devices unable to cite it.
(c) As pinned: grant to the identity, reject to the device that asked.

**Decision (2026-09-18).** (a): both outcomes are addressed to the introducing identity. Applied: §19.4 says so and
its `grant` example names the identity; `state/first-contact-reject-and-silence` changed; all three implementations.

## 75. §12.5 rule 2 / §12.7 rule 3 — `session.answered-elsewhere` at the leg that answered

**Gap.** §12.5 rule 2: a `cancel` arriving after the responder's `answer`, with no initiator message since, "crossed
the answer: the responder MUST treat the session as ended … and MUST NOT treat the crossed `cancel` as an error".
§12.7 rule 3 has the initiator send `cancel session.answered-elsewhere` to the invited identity on accepting an
answer; a conformant relay delivers it only to the legs that did not answer, but a relay without leg tracking (or a
direct fan-out) hands it to the answering leg too — where, read literally, §12.5 rule 2 tears down the call that was
just established. The vectors pin the sane outcome (`error session.invalid-state`, session stays ACTIVE); the spec
text does not. Found by the second implementation, which followed §12.5 to the letter and ended the call.

**Choices considered.** (a) `session.answered-elsewhere` is never a crossed withdrawal: at an ACTIVE responder it is
`session.invalid-state`. (b) Silently ignore it there — no error traffic for what is a relay's shortcoming.
(c) Literal §12.5: end the session.

**Draft choice.** (a), as pinned by `state/race-responder-answered-elsewhere-at-answering-leg`.

**Suggested fix.** §12.5 rule 2 and the §12.4 responder table: except reason `session.answered-elsewhere` from the
crossed-cancel rule.

**Applied to the spec (2026-09-18).** §12.5 rule 2 carries the exception and its reason (the token is sent *because*
an answer was accepted, so the answered leg receiving it is the one that answered); the §12.4 responder table has the
row. A.5 errata. No vector or code change.

## 76. §12.7 rule 6 — the attempt outcome when no leg rejected

**Gap.** Rule 6 has the relay signal attempt completion by forwarding "that leg's `reject`", choosing the most
informative reason "if legs differed". When every leg expires there is no `reject` to forward and no reason to choose.
The vectors pin `reject endpoint.unavailable`, forwarded in the name of the first leg
(`state/relay-all-legs-expired`); the spec names neither the token nor whose name it goes out in — and a `reject`
the relay composes is not a leg's signed message at all.

**Choices considered.** (a) As pinned: `endpoint.unavailable`, attributed to the first leg. (b) Signal nothing and let
the initiator's T-Ring / T-Establish run out — rule 6 already calls them the backstop. (c) A relay-signed `error`
(`transport.*` or `identity.*`), which is honest about who is speaking.

**Decision (2026-09-18).** (c), with a token of its own: the relay sends a relay-signed `error` with reason
`transport.no-response` (new in §15.4, valid on `error`) and `session` naming the invite. It keeps "no device said
anything" apart from `endpoint.unavailable`, which a device says. An initiator in INVITING or PROCEEDING ends the attempt
on it and sends no `cancel`; in any other state it is an error like any other. Applied: §12.4 (initiator table), §12.7
rule 6, §15.4; `state/relay-all-legs-expired` changed (outcome `no-response`), `state/initiator-relay-no-response-ends-attempt`
and `state/relay-no-response-after-answer-only-surfaced` added; all three implementations; `dsip-relay` signs and sends it,
also from its timer, with no inbound frame in hand. The gateway maps it like any other `transport.*` (G§4.2: 503, cause 41).

## 77. §22.2 / §22.3 — the integrity mode of a statement that is not a transcode

**Gap.** §22.3: "`transcode` makes the output `derivative-bound` …; other operations list it under 'delivered by'."
The vectors report a per-statement `integrity_mode`, and it is `derivative-bound` for every verified statement — a
plain `relay` too (`broadcast/provenance-relay-operation`, `provenance-chain-two-processors`) — while the *displayed*
mode for the same relay-only stream is `metadata-only`. Two values for one stream, and the spec defines only one notion
of integrity mode. Found by the second implementation, which reported `metadata-only` for a relay statement and
failed three vectors.

**Choices considered.** (a) The per-statement value is the mode of the *statement* — by §22.2 any processor-signed
reference to the original record is a `derivative-bound` artifact — and only the displayed mode follows the operation.
(b) The per-statement value follows the operation: `derivative-bound` for `transcode`, the record's mode otherwise;
the vectors change. (c) Drop the per-statement field: it carries nothing the operation does not.

**Decision (2026-09-18).** (c): a statement has no integrity mode of its own. Applied: §22.3 says so (and that a
receiver MUST NOT present a `relay` or `repackage` statement as `derivative-bound`); five broadcast vectors lose the
member; all three implementations. No wire change: the field was only ever in the verification result.

## 78. G§4 — which tokens are "attempt" tokens

**Gap.** G§4: "Tokens describing a failed *attempt* (busy, declined, unknown, moved, cancelled, blocked) that arrive
after the DSIP leg is ACTIVE are reported as `gateway.mapped`." Read as a list, that is six tokens. The Rust and Python
implementations also map `endpoint.unavailable` and `identity.not-in-service`; no vector said so (the only one was
`endpoint.busy`). The second implementation took the list literally and a mid-call BYE with Q.850 18 came out as
`bye endpoint.unavailable` — a token §15.4 does not even list as valid on `bye`. A real three-way divergence, found by
adding the vector; the existing implementations' set was established black-box, with probe vectors, not by reading them.

**Choices considered.** (a) The eight tokens the existing implementations use: every mapped token that says why a call
could not be *set up*. (b) The six the profile names. (c) A rule instead of a list: any token §15.4 does not list as
valid on `bye` — tidy, but it would also rewrite `gateway.unreachable`, `media.unsupported` and `session.timeout`, which
are useful mid-call and which `gateway/inbound-bye-q850-41-unreachable` already pins as kept.

**Draft choice.** (a). Vectors `inbound-active-declined-becomes-mapped`, `-unavailable-becomes-mapped`,
`-not-in-service-becomes-mapped`, `inbound-active-media-token-stays`; all three implementations agree.

**Applied to the spec (2026-09-18).** G§4 lists the eight tokens and says every other mapped token is kept mid-call.
The §15.4 point below is **not** applied: it changes which `bye` reasons warn `reason-not-valid-on-type`, so it is a
registry decision with vector changes, not wording.

**Suggested fix.** G§4: replace the parenthetical with the eight tokens. Separately, §15.4's "valid on" for
`gateway.unreachable`, `media.unsupported` and `session.timeout` should admit `bye` if a gateway may send them there.

**Decision on the §15.4 point (2026-09-20).** All three admit `bye`. Applied: the §15.4 "valid on" column
(`session.timeout`: cancel, bye; `media.unsupported`: reject, bye; `gateway.unreachable`: reject, bye, error) and the
A.5 errata list; the three registries; vectors `semantic/bye-reason-gateway-unreachable`, `-media-unsupported`,
`-session-timeout` (accepted, no `reason-not-valid-on-type`). G§4.2's BYE-cause sentence used to say "the `session.*`
tokens valid on `bye`" for the cause-16 set; it now names `session.already-answered` and `session.cancelled`, because
`session.timeout` is valid on `bye` and keeps 102 (`gateway/outbound-bye-session-timeout-keeps-its-cause`).

## 79. G§4.2 — Q.850 causes the table does not give

**Gap.** G§4.2 maps an unregistered token "by its §15.1 category (`user`→603, `endpoint`→480, …)" — statuses only — yet
G§3 requires every crossing to carry a `Q.850;cause` where one applies, and the vectors pin one
(`outbound-unknown-token-category-fallback`: 603 **with cause 21**). Likewise an ACTIVE teardown is "BYE with the
cause", but the BYE rows name only `user.hangup`/`session.*` (16) and `media.failed` (47); `outbound-bye-policy-terminated`
pins 31, taken from the token's pre-answer row.

**Choices considered.** (a) A category fallback takes the cause of the category's representative row (`user` 21,
`endpoint` 18, `identity` 1, `session` 41, `media` 65, `policy` 21, `transport` 41, `gateway` 38); a BYE takes the
token's table cause when the BYE rows do not name it, else 16. (Settled by fuzz.py, 2026-09-18: "`session.*` → 16" in the
BYE rows means `session.already-answered` and `session.cancelled` — the `session.*` tokens valid on `bye` at the time;
spec-gap 78's later decision admits `session.timeout` on `bye` without moving it into this set. Any
other registered token keeps the cause of its own row, so a BYE for `session.timeout` is cause 102, which says more than
"normal clearing"; an unregistered token has no row and is 16, category fallback being a pre-answer rule. Vectors
`outbound-bye-session-timeout-keeps-its-cause`, `outbound-bye-unregistered-token-is-cause-16`.) (b) No cause on a fallback — the `Reason: DSIP` header
already carries the literal token.

**Draft choice.** (a), as the implementations already agreed; new vector
`outbound-unknown-endpoint-token-category-fallback` (480, cause 18) pins a second category.

**Suggested fix.** G§4.2: add the cause to each category fallback, and a sentence for BYE causes.

**Applied to the spec (2026-09-18).** G§4.2 gives each category fallback its cause and has a "BYE causes" paragraph.

## 80. M§5.2 — the deposit class field table

**Gap.** M§5.1 orders a deposit's refusals "… the class (unregistered → `mailbox.unsupported-class`), the class field
table below, and the size constant", and M§5.2's table has a "carries" column: what a class is *for*. It does not say
which of the other deposit fields a class may also carry, so `deposit-fields` — a refusal every mailbox and hub must
agree on — had no complete definition outside the two existing implementations. The second implementation wrote the
table from the prose and passed every vector; a differential probe (each class × each field, 87 temporary vectors run
through all three implementations) then found **seven** disagreements no vector covered: `recipient` on `application`,
`handshake`, `archive` and `group-info` (allowed — it is addressing, not class, and a hub's fan-out to a mailbox is an
`application` deposit with `recipient` and `seq`); `ratchet_tree_blob` on `welcome` and `group-info` (allowed, M§6.4);
`blobs` on `handshake` (refused — the manifest names what *content* references).

**Choices considered.** (a) The existing implementations' table, which the prose supports on each of the seven
points once read closely. (b) A looser rule — refuse only fields that contradict the class (an `ephemeral` with `mls`)
and ignore the rest — simpler, but then two services disagree about the same deposit.

**Draft choice.** (a). The table is now written out in the vectors README; vectors `deposit-application-fanout-valid`,
`deposit-handshake-with-blobs-refused`, `deposit-welcome-ratchet-tree-blob-valid`,
`deposit-group-info-ratchet-tree-blob-valid` pin the points that had none.

**Suggested fix.** M§5.2: replace the "carries" column with MUST-carry / MAY-carry columns, and say that `recipient`
is class-independent.

**Applied to the spec (2026-09-18).** M§5.2 keeps its descriptive table and gains "The class field table" beneath the
field list — MUST-carry / MAY-carry per class, `recipient` class-independent, `welcome` with `seq` per spec-gap 83 — the
same table the vectors README carries.

## 81. M§6.5 / M§7.4 / M§14.1 — orders and scopes the traces never exercised

**Gap.** Three places where the profile gives a list of rules and the services must pick one answer. None had a vector
with two rules in play, so the second implementation passed the whole suite (867 of 867) and still disagreed with Rust
and Python once random traces were run through all three (about 3,000 generated hub and mailbox traces; Rust and Python never
disagreed with each other):

1. **A hub's refusals** (M§6.5 rules 1–3 are a list, not an order). The reference order: moved → unsupported class →
   expired ephemeral dropped → *sequenced bytes seen before are `accepted duplicate`* → membership / M§6.8 → epoch →
   commit validity. The second implementation authenticated first, as rule 1's position suggests. The notable point is
   the fourth: a re-deposit is answered before membership and epoch, so a member removed since, or a retry arriving an
   epoch late, still learns its item was ordered — and so does anyone else who holds those bytes.
2. **The handover wait** (M§7.4, spec-gap 71) says the mailbox "refuses the new hub" until the old hub's items are
   stored. The reference holds off *everything* from the new hub, a `group-info` included, and answers "retry"
   (`mailbox.unknown-group`) before judging a wrong `seq` (`policy.blocked`); the second implementation held off only
   sequenced items and judged numbering first.
3. **First-contact rate limits** (M§14.1, §19.4) are stated for introductions. The reference counts, and limits, a
   `grant` deposit the same way.

**Choices considered.** (1) (a) the reference order; (b) membership first — but then a removed member's retry is
refused `policy.blocked` though its item *was* ordered, which M§9.3's idempotence exists to prevent. (2) (a) everything
waits; (b) only sequenced items — a GroupInfo from a hub the mailbox is not yet sure of would replace the stored one.
(3) (a) both kinds; (b) introductions only — a grant answers an introduction the *owner of the other mailbox* sent, so
limiting it with the stranger's budget can delay a legitimate answer; on the other hand an unlimited `grant` class is
an unmetered way to write into someone's mailbox.

**Draft choice.** (a) in all three, as pinned now: `hub-refusal-order-*` (4), `mailbox-hub-move-wait-covers-everything-
from-the-new-hub`, `mailbox-grant-counts-toward-the-rate-limit`, `mailbox-push-in-device-order`, and
`commit-retry-unknown-mailbox-condition-after-a-conflict` (the §15.3 fallback's one retry is its own, inside the bound
of three proposals). (3) deserves a second look: a separate, more generous budget for grants would answer both worries.

**Decision on (3) (2026-09-18).** Neither (a) nor (b): a **solicited** grant bypasses the limit. The owner's device
tells its own mailbox which introductions it sent — `mailbox-config` `introductions_sent` (new schema field, ≤ 256 ids per
message, durable) — before depositing each one. A `grant` deposit whose `session` names one is the answer the owner asked
for: not counted, not limited, and it consumes the entry (one introduction, one answer). Any other grant is an
unsolicited write and takes the introduction budget. It is the core's own `grant-unknown-introduction` test (§19.4),
applied where the abuse would land. Applied: M§5.7, M§14.1, the profile schema set; `mailbox-grant-counts-toward-the-rate-
limit` became `mailbox-unsolicited-grant-takes-the-introduction-budget`, plus `mailbox-solicited-grant-bypasses-the-rate-
limit`, `-bypass-is-single-use`, `mailbox-introductions-sent-survives-restart` and two `mailbox-config-introductions-sent-*`
message vectors; all three mailbox machines; the mailbox service passes a grant's `session` through and `dsip-msg`
announces an introduction to its mailbox before sending it.

**Suggested fix.** M§6.5: state the order. M§7.4: "refuses every deposit from the new hub".

**Applied to the spec (2026-09-18).** M§6.5 has "The order of a hub's refusals" (seven steps, the duplicate answer
before membership and epoch, with why); M§7.4 says the wait covers every deposit from the new hub and that the retry
answer comes before the numbering is judged.

## 82. §12.7 / §13.3 — session traffic for a session the relay never saw

**Gap.** Found by `impl/tools/fuzz.py` (the `relay` target: the implementations differ on most random traces, all
for this one reason). A relay tracks an attempt from the invite it forked. What does it do with session traffic —
`progress`, `answer`, `reject`, `cancel`, `bye`, `info`, `update` — naming a `session` it holds no attempt for? Rust and
Python drop it (`drop unknown-attempt`). The second implementation routes it by `to`, queueing for an unbound recipient,
because the vectors README says of the relay "`{"recv": any}` to a known but unbound identity/device: queued (§13.3)".
Neither the spec nor a vector says which. It is not an edge: a relay that restarts mid-call has no attempts, and under
the first reading it then drops every `bye` of every call set up before the restart; under the second, anyone can have
a relay carry session traffic for sessions that never existed.

**Choices considered.** (a) Attempt-scoped: drop what belongs to no known attempt (as Rust and Python). (b) Routed by
`to` like any envelope — pre-answer leg traffic needs the attempt (it is forwarded to the initiator, whom only the
attempt names), but anything carrying a device `to` is store-and-forward (§13.3). (c) (b), but only while the attempt is
unknown *because the relay lost it*: indistinguishable to the relay, so not really a choice.

**Decision (2026-09-18).** (b): route by `to`. The attempt record is for three things only — forwarding a leg's
pre-answer traffic to the initiator, delivering a `cancel` per leg, and signalling the outcome; everything else is an
envelope like any other: to the bound device it names, or every device bound for the identity it names (in device
order); held for a known, offline recipient; otherwise `error` `transport.unknown-recipient` to its sender, never a
silent drop. Applying it surfaced four neighbours, settled the same way and pinned with it:

- traffic from a device that is **not a leg** of a known attempt is routed by `to`, not dropped;
- a `cancel` whose `to` is one leg's **device** cancels that leg alone (§12.11), the attempt going on with the others;
  addressed to a device that is not a leg, it is routed by `to`; and it never takes the identity's queued invite with it;
- a leg can still be added in the invite's last second (`expires_at >= now`, as §12.10 counts it);
- when several queued invites expire together, the relay reports them in recipient order.

Applied to the spec (§13.3, A.5), the vectors (`state/relay-unknown-session-*`, `state/relay-device-addressed-cancel-*`,
`state/relay-cancel-addressed-to-a-device-that-is-not-a-leg`, `state/relay-traffic-from-a-device-that-is-not-a-leg-is-routed`,
`state/relay-leg-added-at-the-invites-last-second`, `state/relay-expiry-reports-in-recipient-order`) and all three
implementations; the `relay` fuzz target is back in `--target all`.

## 83. M§6.5 / M§8.5 — where a device starts counting a group's `seq`

**Gap.** Found by `fuzz.py` (the `resume` target). Spec-gap 69 says "a device that has just joined takes the first
sequenced item it processes as its position". In the durable delivery state (`resume-trace`), Rust and Python record a
group's first item as *seen beyond a gap* (`contiguous: 0, seen: [4]`); the second implementation records it as the
position (`contiguous: 4`). Every vector starts a group at `seq` 1, where the two are the same. They differ when a lower
`seq` arrives later: the first reading processes it, the second calls it a duplicate. Lower seqs are normally pre-join
history the device cannot decrypt — but after a hub handover wait (spec-gap 71) a mailbox does store the old hub's late
items out of order, so "lower and later" can be a real item.

**Choices considered.** (a) The first item is the position (spec-gap 69's words): what came before is history.
(b) The first item is merely seen: nothing is ever wrongly called a duplicate, at the price of a `contiguous` that never
reaches the items before the join. (c) (a), except that a welcome carries the `seq` of the commit that added the device,
and the position starts there — exact, but it needs the welcome's seq in the resume state.

**Decision (2026-09-18).** (c): from the welcome's `seq`. A hub-forwarded `welcome` carries the `seq` of the commit
that added the device (M§5.2: `welcome` MAY carry `seq`; `ephemeral` still may not); the device's position for the group
starts there, so anything at or below it is a duplicate and anything above it is processed or waited for, whatever order
the mailbox delivers in. A welcome with no `seq` keeps the old rule (the first sequenced item processed is the
position). A welcome for a sibling device sets nothing; a re-join by external commit is a join, positioned at its own
`accepted`. A mailbox never sequences a welcome by that `seq` nor echoes it in the acknowledgement (M§6.5, spec-gap 66).
Applied to the profile (M§5.2, M§6.5), the vectors (`messaging/deposit-welcome-with-seq-valid` — replacing
`deposit-welcome-with-seq-refused`, a reading the decision reverses — `deposit-ephemeral-with-seq-refused`,
`resume-welcome-seq-is-the-starting-position`, `resume-late-item-after-the-join-is-processed`,
`resume-welcome-without-seq-starts-at-the-first-item`, `resume-sibling-welcome-seq-sets-no-position`,
`resume-rejoin-is-a-join`) and all three implementations; the `resume` fuzz target is back in `--target all`.

## 84. §12.6 — glare with more than one attempt of our own

**Gap.** Found by `fuzz.py` as the first disagreement between Rust and Python themselves. An endpoint may have two live
attempts to the same identity (one addressed to the identity, one to a device). §12.6 speaks of "its outbound invite",
singular. On an inbound invite from that identity each implementation picked *one* rival — Python and TypeScript the
first placed, Rust whichever its map yielded — withdrew that one, and left the other ringing.

**Decision (2026-09-18, from the text).** "The invite with the lexicographically smaller `id` wins", over *all* the
invites between the two identities: if any of ours is older than theirs, theirs is rejected and ours are left alone;
otherwise each of ours lost, and each is withdrawn, in id order. Applied in all three; vectors
`state/glare-every-losing-attempt-is-withdrawn`, `state/glare-lowest-id-of-all-decides`.

**Suggested fix.** §12.6: say "each outbound invite to that identity".

## 85. §12.4 / §12.7 rule 4 — the `bye` a late answer gets once the call has ended

**Gap.** The §12.4 initiator table gives a late answer's `bye` in two ended states: after our `cancel`
(`session.cancelled`, §12.5 rule 3) and after an attempt "ended by `reject` or timeout" (`session.failed`, spec-gap 12).
It says nothing about the third: the session reached ACTIVE, ended with a `bye` (ours or the peer's), and another leg's
answer arrives after that — with forking that is an ordinary race, not an edge. Rust and Python send
`session.already-answered`; the second implementation, reading the table's two rows as exhaustive, sent
`session.failed`. Unpinned by any vector; noticed by reading, and confirmed by the vectors below before they were fixed.

**Choices considered.** (a) `session.already-answered`: §12.7 rule 4 says "exactly one answer is ever applied per
invite; any subsequent answer from another leg" gets it — a rule about the invite, not the state, and it is the truthful
reason. (b) `session.failed`: the fallback the table names for an ended attempt. (c) `session.cancelled`: wrong — nothing
was withdrawn.

**Decision (2026-09-20).** (a). The `bye` follows what the invite was: `session.cancelled` when we withdrew it,
`session.already-answered` when an answer was applied (however the call then ended), `session.failed` when the attempt
was never answered. Applied to §12.4 (a third ENDED row) and §12.7 rule 4; vectors
`state/fork-late-answer-after-the-call-ended`, `state/fork-late-answer-after-our-hangup`; the second implementation
now tracks whether an answer was applied.

## 86. §12.7 rules 3–4 / §13.2 — the relay must not withhold an `answer`

**Gap.** A forking relay marks a leg terminated when it delivers a `cancel` to it, when the invite expires at the relay,
or when the leg rejects. All three implementations then dropped *everything* the leg sent, `answer` included
(`drop leg-terminated`, pinned by `state/relay-user-cancel-all-legs`). But an answer can cross the cancel (§12.5 rule 3
exists for exactly that), and a device alerted just before `expires_at` can answer just after it: the device is then
ACTIVE, waiting for media, and the `bye` that §12.5 rule 3 / §12.4 make the initiator send never comes, because the
initiator never saw the answer. Silent on the wire, and at odds with spec-gap 82, under which a relay that has *lost* its
attempt record forwards that same late answer (`state/relay-unknown-session-routed-by-to`): a relay that remembered
more delivered less.

**Choices considered.** (a) Forward every `answer`, whatever the leg's state; the initiator alone ends an answered leg
(`already-answered`, `cancelled` or `failed` by §12.7 rule 4, §12.5 rule 3, §12.4). (b) Route it by `to` like unknown-
session traffic: same wire effect, but it is an attempt's own leg traffic and the record should not pretend otherwise.
(c) Keep dropping, and have the relay `bye` the leg itself: the relay speaking for the initiator (§15.2 forbids composing
in another's name). (d) Forward `progress` and `reject` from terminated legs too: no — the initiator cannot see legs, so a
stale `progress` or a second `reject` would read as the attempt's own, and nobody needs them.

**Decision (2026-09-20).** (a), with the leg record moving only for a leg that was still outstanding: a cancelled,
expired or rejected leg that answers is forwarded and stays recorded as cancelled, expired or rejected, and the attempt's
outcome is unchanged. `progress` and `reject` from a terminated leg are still `drop leg-terminated` — the relay screens
them because only it can. Applied to §12.7 rule 3 and §13.3; `state/relay-user-cancel-all-legs` reversed (the crossed
answer is forwarded), `state/relay-answer-from-an-expired-leg-is-forwarded`,
`state/relay-answer-from-a-rejected-leg-is-forwarded`; all three implementations.

## 87. M§6.5 rule 5 / spec-gap 66 — whose queue the welcome holds

**Gap.** Found by `impl/tools/fuzz.py` (seed 3, the `hub` target). The M§6.5 erratum for spec-gap 66 says that until
"that mailbox" — the added identity's — acknowledges its welcome, the hub sends it nothing else for the group, "it has no
registration yet". Read literally, "the added identity" includes a member adding its own device, whose mailbox is
registered and which the same paragraph says gets the commit *and* the welcome. Rust and Python used "has an
unacknowledged welcome" as the test: at the commit they fanned it out to the member (the welcome was queued after), but
on a restart they held that member's head back, and on the welcome's acknowledgement they sent it again. The second
implementation tracked the identities with no registration and held only those. Three readings of one paragraph.

**Choices considered.** (a) Hold the queue of an identity the commit brought in, and only that: the reason the text
gives. (b) Hold any identity with an unacknowledged welcome, consistently — at the commit too: a member's other devices
would then wait for its new device's mailbox acknowledgement for no reason. (c) Hold nothing and let the mailbox refuse
and the hub retry: what spec-gap 66 rejected.

**Decision (2026-09-20).** (a). The hold is by registration, not by welcome: an identity with no registration for the
group (brought in by the commit; an external joiner joins by its own commit and has one) has its sequenced queue held
until its welcome is acknowledged — at the commit, on retry and after a restart alike; a member that gained a device is
registered and its queue moves only on its own acknowledgements. The hold covers every send: an acknowledgement from
an identity still waiting for its welcome (seed 5 found Rust and Python answering it with the next item) moves its queue
and sends nothing. Applied to M§6.5, the README, Rust and Python (a durable `unregistered` set); vectors
`messaging/hub-member-adding-its-own-device-is-not-held-behind-the-welcome`,
`messaging/hub-acknowledgement-does-not-lift-the-welcome-hold`.

## 88. M§7.4 / spec-gap 71 — announcing the handover wait's expiry on a refused deposit

**Gap.** Found by `fuzz.py` (seed 3, the `mailbox` target). The expiry of `handover_wait` is noticed lazily, at the new
hub's first deposit after it (spec-gap 71's vectors). When that deposit is itself at or below `handover_seq`, it is
refused `policy.blocked` — and Rust and Python returned the refusal alone, discarding the `handover_expired` they had
just computed while keeping the released state, so the expiry was never announced at all. The second implementation
emitted both. An implementation defect in the two, not a reading; recorded because the profile text never says the
announcement is unconditional.

**Decision (2026-09-20).** The expiry is announced once, at the first deposit from the new hub after the wait ran out,
whether that deposit is then admitted or refused. Applied to M§7.4 and the README; vector
`messaging/mailbox-hub-move-handover-wait-expiry-announced-on-a-refused-deposit`; Rust and Python fixed.

## 89. §12.7 rule 3 / §12.11 — the order a relay reaches several legs in

**Gap.** Found by `fuzz.py` (seed 3, the `relay` target): the first disagreement of Rust with Python *and* the second
implementation. Nothing in the spec orders a fan-out, and the suite's rule ("device (DID) order wherever a relay or
mailbox fans out", spec-gap 82) was applied by Python and the second implementation to routing, but not to the two
fan-outs that walk the attempt record: a `cancel` to the identity reached the live legs in the order they were
delivered, and a device binding into several live attempts got their invites in the order the attempts were made. Rust
keeps both in ordered maps and so used DID order and id order. Only visible when delivery order differs from DID order,
which the suite's fork event, listing legs in DID order, never did.

**Decision (2026-09-20).** DID order and id order everywhere, as the suite already says: a real relay forks in DID
order anyway (its binding table), so the record's insertion order is an artefact of the harness's explicit leg list.
Applied to the README, Python and the second implementation; vectors `state/relay-cancel-reaches-live-legs-in-device-order`,
`state/relay-late-binder-gets-live-invites-in-id-order`. No spec text: emission order is the suite's contract, not the
protocol's.

## 90. §12.4 / §12.9 — a local `place_call` on a session the endpoint already holds

**Gap.** Found by `fuzz.py` (seed 3, the `endpoint` target). The harness's `place_call` names its session id. All three
implementations accepted one for an id already held — a PROCEEDING session went back to INVITING with a second
`invite` on the wire and a second T-Establish, while its T-Ring ran on; they then differed on what the timers did at
expiry. §12.4 has no transition on a local call request from any session state, and §12.9 makes the id a ULID the
replay check remembers: an id is used once.

**Decision (2026-09-20).** A `place_call` naming a session this endpoint holds, live or ended, is `refused
invalid-state` and changes nothing (the timers run on). A local-API rule, so README only; vector
`state/place-call-on-a-held-session-is-refused`; all three implementations.

## 91. M§6.6 / M§12.2 — what a pending group's expiry drops

**Gap.** Found by `fuzz.py` (seed 4, the `mailbox` target). M§6.6: an unconfirmed pending group "is dropped, with its
items". An archive deposit (M§12.2) names a group by reference and needs no registration for it — history outlives
leaving, and a later welcome for the same group makes a new, pending registration. Rust and Python kept archive records
through the drop (deliberately, unpinned); the second implementation dropped every item filed under the group, archive
records included, which would erase the owner's history of a group they left and were re-invited to, if the invitation
lapsed.

**Choices considered.** (a) Drop the hub deposits the pending group admitted, keep archive records: the records are the
owner's, stored by reference whatever the registration. (b) Drop everything filed under the group: the literal reading,
and it destroys history for a registration the owner never confirmed. (c) Refuse archive deposits for a group with no
confirmed registration: a device archives what it decrypted, and its `joined` config may arrive after its first archive.

**Decision (2026-09-20).** (a). Applied to M§6.6 and the README; vector
`messaging/mailbox-pending-group-expiry-keeps-archive-records`; the second implementation fixed.

## 92. M§6.6 / spec-gap 59 — which cursor a redelivery carries

**Gap.** Found by `fuzz.py` (seed 5, the `mailbox` target). Spec-gap 59: a redelivery is acknowledged as a duplicate
"with the original cursor while the item is still retained". After the owner leaves a group and registers it again at
another hub, a redelivered `seq` the mailbox still retains from the first registration got its cursor from Rust and
Python (which look items up by group and seq) and no cursor from the second implementation (which kept the seen map per
registration and had dropped it with the `left`). Reading all three showed a shared defect underneath: the lookup by
group and seq also matches an archive record (M§12.2), whose `ref_seq` is in the same seq space, and returns its cursor
if it was stored first.

**Choices considered.** (a) By group and seq among retained hub items: the group is the same group and its numbering
is the hub's; whether the owner's registration lapsed in between is no concern of the hub retrying. (b) Per
registration: a redelivery after re-registration is a duplicate without a cursor — true but less useful, and a mailbox
would have to remember which registration stored what. (c) Treat it as new and store it again: two items for one seq.

**Decision (2026-09-20).** (a), and an archive record is never the item. Applied to M§6.6 and the README, all three
implementations; vectors `messaging/mailbox-hub-deposit-redelivered-after-re-registration-carries-the-retained-cursor`,
`messaging/mailbox-hub-deposit-redelivery-cursor-is-never-an-archive-records`.

## 93. M§7.4 / spec-gap 71 — when an old hub's item is a fill and when a redelivery

**Gap.** Found by `fuzz.py` (seed 6, the `mailbox` target). Spec-gap 71: after the handover wait expires with items
missing, what the old hub still delivers at or below `handover_seq` "is stored rather than taken for a redelivery".
The second implementation switched to that treatment as soon as the new hub was admitted — with nothing missing, no
wait and no expiry — and then stored an old-hub item below the highest stored that Rust and Python, applying spec-gap
59's redelivery rule, acknowledged as a duplicate.

**Decision (2026-09-20, from the text).** "After that" is after an expiry: only a wait that ran out with items missing
makes the old hub's later items below the highest stored fills; a move with nothing missing changes nothing about
redelivery. Applied to the README and the second implementation; vector
`messaging/mailbox-hub-move-old-hub-item-below-the-highest-stored-is-a-redelivery`.

## 94. M§6.6 / spec-gap 66 — how long a welcome is "already held"

**Gap.** Found by `fuzz.py` (seeds 9, 11 and 12, the `mailbox` target, three probes of one shape). Spec-gap 66: a
mailbox answers a welcome "whose MLS bytes it already holds" as a duplicate with the first one's cursor. The second
implementation remembered every welcome's bytes for ever, so a welcome arriving after its pending registration had
expired — and taken the stored welcome with it (M§6.6) — was still a duplicate, answered with a cursor that no longer
existed, and the group was never registered again; and it matched the bytes across groups. Rust and Python looked
among the welcomes still held, but not by group either.

**Decision (2026-09-20).** "Already holds" is literal: among the welcomes the mailbox still holds, for that group. After
an expiry the same welcome is a new invitation — stored, registered pending again, its own cursor; the same bytes for
another group are that group's welcome. Applied to M§6.5, the README and all three implementations; vectors
`messaging/mailbox-welcome-after-pending-group-expiry-is-stored-anew`,
`messaging/mailbox-welcome-same-bytes-for-another-group-is-its-own`.

## 95. M§7.4 / spec-gap 71 — what "missing" means during a hub move

**Gap.** Found by `fuzz.py` (seed 9, the `mailbox` target). During a move the new hub is held off "while the old hub's
items through `handover_seq` are missing". Rust and Python judged that by the highest `seq` stored (nothing is missing
once it reaches `handover_seq`); the second implementation kept a map of the seqs it had seen since the registration and
called every unseen one missing, so with seqs 1 and 3 stored and `handover_seq` 3 it held the new hub's GroupInfo off
while the other two admitted it. Spec-gaps 59 and 93 already reason from the high-water mark: the hub delivers in order
and retries before sending later items (M§6.5 rule 5), so a stored `seq` says every lower one was delivered before it.

**Decision (2026-09-20).** By the highest `seq` stored, as everything else about redelivery is. Applied to M§7.4, the
README and the second implementation; vector
`messaging/mailbox-hub-move-nothing-missing-once-the-highest-stored-reaches-handover-seq`. The relay probe of seed 10
was a generator artefact — the same invite id introduced twice, which the replay stage never lets through — and the
generator now introduces an id once.

## 96. §12.9 / DHT profile §2, §4 — the replay window kills reachability hints after 300 s

**Gap.** Found on the WAN testbed (2026-10-02, `impl/tools/wan/README.md` Runs 1–2), invisible on localhost and
to the suite. The DHT profile applied "envelope rules unchanged: 300 s replay window on `issued_at`", at every hop
(§4: before a node stores, forwards or returns a record), while allowing `expires_at − issued_at` up to 3,600 s and
re-signing at ⅔ of the lifetime. Read together: a hint becomes unusable 300 s after signing whatever its TTL. With
the CLI's 600 s TTL, Bob re-signs every 400 s, so he is undiscoverable for 100 s of every cycle — measured: at
`issued_at + 321 s` all three copies returned `replay-window` and `hint none verified`, ~280 s before `expires_at`,
with Bob online and bound. Replication fails the same way: a node that joins or rejoins (Run 2's restarted
bootstrap) received the record twice by Kademlia replication and rejected both copies `replay-window`, so a node
that misses a hint's first 300 s can never hold it. This is spec-gap 31 again, for the other envelope type that is
stored and forwarded by design.

**Choices considered.** (a) As gap 31: for `reachability-hint`, the age bound is the record's own `expires_at`;
the future bound stays; `expires_at − issued_at` is capped (3,600 s, the existing SHOULD made a MUST so the
relaxation stays bounded). Replay is harmless — §8.3 already discards a lower `seq` and treats identical content
as a no-op, and the record is the signer's own claim about itself — so `id` deduplication does not apply. (b) Keep
the window and require re-signing every < 300 s: 3,600 s TTLs become meaningless, publish traffic rises ~8×, and
replication to late joiners still fails. (c) Exempt hints at storage but not at read: readers would still reject
what nodes serve.

**Decision (2026-10-02, user: "option (a), gap-31 style").** (a). Written into core §12.9 (second exception and
the errata line) and DHT profile §2. New reject code `hint-validity` (vectors README). Envelope stage 9 for
`reachability-hint`: `expires_at − issued_at > 3,600` → `hint-validity`; `issued_at > now + 300` →
`replay-window`; `expires_at < now` → `expired`. `dsip --hint-ttl` refuses values over 3,600. Vectors:
`dht/hint-held-accepted`, `hint-held-expired`, `hint-future-rejected`, `hint-validity-over-cap`,
`hint-held-newer-wins`, `hint-held-duplicate`; the cap edge is `dht/valid-self-signed-did-key` (TTL exactly 3,600).

## 97. §20.7 / §10.2 / §12.7 — signaling bodies are readable by every relay that routes them

**Status: decided 2026-10-02 — (a), static key accepted, padding 256 (user).** Raised 2026-10-02 after the WAN campaign ("what stops a bad
actor's relay from stealing user data?"). §20.7 already names "payload encryption to the recipient's
key-agreement key (sealed-sender-style delivery)" as a v1.x candidate and Appendix A lists "sealed-sender signaling
confidentiality" as forward work; this entry turns that into a concrete choice.

**Gap.** Core envelopes are signed, not encrypted (§10.2, §20.7). A relay cannot forge, alter, replay or splice
them, and cannot touch media (DTLS fingerprints ride in the signed SDP) or Messaging Profile content (MLS). But
it reads every field it routes. What a hostile relay learns today, per message (schemas, v0.8):

| Field | Carried by | What it reveals | Relay needs it? |
|---|---|---|---|
| `type`, `id`, `from`, `to`, `session`, `in_reply_to`, `issued_at`, `expires_at`, `dsip` | all | who, whom, when, which call | **yes** — routing by `to` (§13.3, spec-gap 82), attempt tracking and forking (§12.7), replay window (§12.9), store-and-forward expiry |
| `reason` (registry token), `retry_after` | reject, cancel, bye | coarse outcome (`user.busy`, `user.no-answer`) | **yes** — §12.7 rule 6 picks among leg rejects by reason; the relay itself emits `transport.no-response` (spec-gap 76) |
| `status` (progress registry token) | progress | ringing / queued | no rule uses it — the relay forwards it (`dsip-session` fork tracker records it in its emissions); T-Ring/T-Queue are the endpoints' timers |
| `transports[].sdp` | invite, answer, update | every ICE candidate (host, srflx, relay addresses: **the users' IP addresses**), codecs, DTLS fingerprint | no |
| `identity` (identityInfo: display name, claims) | invite | the caller's presented name and claims | no |
| `intent`, `policy` | invite, answer, update | why the call is placed, recording/screening policy | no |
| `answered_by` | answer, update | user / screening / gateway / service | no |
| `media` | invite, answer, update | what media is offered or selected | no |
| `data`, `about` | info | DTMF digits (§12.12, spec-gap 70), WebRTC trickle candidates — **IP addresses again** | no |
| `detail` | reject, cancel, bye | free text | no |
| `grant` | invite | id of a first-contact grant (§19.4) | only a stateless relay checking first contact; otherwise no |

The bottom half is the sensitive half: IP addresses (from SDP and trickled candidates), names, DTMF digits
(PINs typed into an IVR), and policy. None of it is used by any relay rule in §12–§13.

**Not in scope — sender anonymity.** A relay binds every connection to a device DID with `hello` (§13.2), and a
caller binds to the *callee's* relay to reach them, so the relay always knows who is talking to whom. "Sealed
sender" in the Signal sense needs anonymous binding plus a delivery token, which conflicts with per-device rate
limits and with `hello` anti-splicing. This gap is about **body confidentiality**, and the name should say so
("sealed signaling bodies"), not promise metadata privacy (§20.7 stays true).

**Choices considered.**

(a) **Seal the body to the peer identity's `keyAgreement` key; keep the routing header clear; encrypt then
sign.** The payload keeps the "relay needs it" fields above in clear and replaces the rest with
`sealed: {alg, enc, ct}` — the §19.4 / M§6.9 / M§14.1 HPKE construction (X25519 `keyAgreement` key from the
recipient's DID document, §7.2), with the clear header (`type`, `id`, `from`, `to`, `session`) as HPKE `info`/AAD so
a ciphertext cannot be cut from one message into another. The outer signature covers the payload bytes including
`ct`, so §10.2 (signature over bytes, no re-serialization) is unchanged, relays still verify, and the replay
window and dedup still apply to the clear `id`/`issued_at`. Encrypted to the **identity** key, not a device key:
the caller does not know the callee's devices (the relay forks to them, §12.7), and every device acting for the
identity can open it. Responses (`answer`, `update`, `info`) are sealed to the *caller's* identity key, which the
callee already resolves to verify the invite. Schema validation of sealed fields moves after decryption at the
recipient — a new pipeline stage between signature verification and payload schema (`impl/vectors/README.md`),
with new verdicts (candidates, in the style of `introduction-purpose-and-sealed`: `body-unseal-failed`,
`body-field-and-sealed` for a field present both in clear and in the seal, `routing-field-sealed`).

(b) **Encrypt the whole payload, routing fields included.** The relay can then neither route by `to` nor run
§12.7 forking, the §13.3 queue, or spec-gaps 75/76/86 — it would degrade to a blind byte pipe plus an outer
routing envelope, i.e. a second envelope format. Rejected: it rebuilds what (a) keeps clear, at the cost of a new
layer.

(c) **Status quo: hop-by-hop TLS, "run your own relay" (§20.7).** Correct and already stated, but the callee's
relay is the *callee's* choice: a caller cannot avoid exposing its IP addresses and name to whatever relay the
callee picked.

(d) **A two-member MLS group per call** (reusing the Messaging Profile). Gives forward secrecy, but needs key
packages fetched before the first `invite` (an extra round trip and a mailbox dependency for plain calling) and
does not fit forking to devices the caller cannot see. Better as the later upgrade for long-lived sessions than as
the base mechanism.

(e) **Per-device HPKE.** Needs the device list up front — conflicts with relay forking and leaks the device
count. Rejected.

**Draft choice.** (a), as an optional extension first (`dsip.extensions`, e.g. `sealed-body/1.0`), not a core MUST:
- A sender MAY seal when the recipient's DID document carries a `keyAgreement` key; it SHOULD when the recipient
  advertises the extension. Sealing is never inferred from a hint (DHT records are not authoritative, §8.1).
- A recipient that advertises the extension MUST accept sealed and clear bodies; one that does not MUST reject a
  sealed body with a registry token (candidate: `media.unsupported`-style new `signaling.sealed-unsupported`), so the
  sender can retry in clear only if its policy allows.
- `did:key` identities: the Ed25519 → X25519 conversion gives every `did:key` a key-agreement key with no document,
  so the flagship path works unchanged.

**Costs and open questions.**
1. **No forward secrecy.** HPKE base mode to a static identity key: whoever later obtains that key reads every
   captured sealed body. Mitigation: `keyAgreement` rotation (§7.5 already rotates keys) and (d) for long sessions.
   Is a static-key mode acceptable for v1.x?
2. **Relay content screening ends** for sealed bodies (as §19.4 already accepts for sealed introductions); rate
   limits still apply. Gateways (G§) are endpoints and unseal as the identity they act for.
3. **Size leakage.** SDP size varies with candidate count; RECOMMENDED padding of `ct` to 256-byte buckets, inside the
   65,536-byte cap (§13.2).
4. **Device key custody.** Every device of the identity must hold the identity's X25519 private key (as for sealed
   introductions today). Is that acceptable, or should delegation (§7.4) carry a device-scoped key-agreement key
   that the identity key wraps?
5. **Which header fields can still move into the seal?** `reason` on `bye` and `cancel`, and `progress.status`, are
   used by no relay rule (only `reject` reasons are, §12.7 rule 6) — candidates for sealing, at the cost of relay
   vectors that record them.

**Decision (2026-10-02).** (a), with: static-key HPKE base mode accepted (no forward secrecy; rotation is the
mitigation); plaintext padded with spaces to a multiple of 256 bytes, enforced by receivers; key custody as for
sealed introductions (identity key on every device); `bye`/`cancel` reasons and `progress.status` stay clear.
Settled while implementing:
- **Extension id `sealed-body/1.0`** — identifiers are `name/major.minor` (the schema rejected `sealed-body/1`).
  Marked in `dsip.extensions` *and* `dsip.critical`, so an addressee without it rejects with the existing
  `session.unsupported-critical-extension`; no new reason token.
- **Routers route regardless** (§10.4 "Routing"): §11.2's critical rule binds the addressee. Vector context
  `router: true`.
- **Recipient key = the DID in `to`**, which on a response is the caller's *device* (`to` = the invite's `from`);
  a device `did:key` opens with its own derived key. Found wiring the CLI: sealing to the caller's identity would
  have made every sealed `answer` unopenable on the device.
- **Pipeline stage 12b** after the version check, before schema: `sealed-not-critical` → `sealed-alg-unsupported`
  → `body-unseal-failed` → `sealed-plaintext-invalid` → `sealed-field-not-sealable` → `sealed-field-in-clear`;
  stages 13–14 run on the merged payload (`effective.sealed` on accept). Schemas admit `sealed` in place of a type's
  required sealable fields (`anyOf`).
- **Three edges the second implementation found** (its author could not decide them from §10.4 and the README):
  a payload whose AAD inputs (`type`/`id`/`from`/`to`) are not strings is not opened (Python and Rust had answered
  `body-unseal-failed`, impl-ts `schema-invalid` — a real divergence no vector covered; impl-ts's reading adopted);
  a non-array `critical` lists nothing; a type with no sealable fields admits none. Each pinned by a vector.

Written into core §10.4 (new), §20.7, the errata line; schemas (`SEALABLE` in `generate_schemas.py`); vectors README
(stage 12b, six codes, `unseal_key_hex` / `router`). Python harness, Rust (`dsip-core::hpke` — moved down from
`dsip-messaging` — and `dsip-schema::sealed`), impl-ts (written from the spec and README only). 26 vectors (25 `semantic/sealed-*`, `semantic/clear-invite-without-media-rejected`) → 963, three-way parity. CLI: `dsip call|answer --seal`;
inbound sealed bodies always open. Local check through a tracing relay (`RUST_LOG=dsip_relay=trace`): a clear call
exposed 2 SDPs, 10 ICE candidates and a display name; the sealed call exposed none (invite, answer and 8 trickle
`info`s sealed) and carried media both ways.

**Test plan (as adopted).** Vectors first (envelope/: sealed body accepted, tampered `ct`, `ct` moved between
messages, sealed field also in clear, wrong recipient key, unknown `alg`; state/: forking with sealed invites and a
relay reject choice unaffected); Python harness, Rust and impl-ts to three-way parity; then a WAN check that the
relay log and a packet capture on L2 show no SDP and no IP addresses.

## 98. §13.3 — the order a binding device receives what was queued for it

**Gap.** Found by CI's differential fuzz (seed 274, the `relay` target; first seen on PR #65's run, which changed only
a comment). A relay keeps store-and-forward queues per recipient, and a recipient is either a device or its identity
(§13.3, spec-gap 82). When the device binds, both queues are flushed to it. The README said only "`bind` flushes them
in order". Python and Rust flushed the identity's queue first, then the device's (two maps, walked in turn); the
second implementation, reading the README, flushed in arrival order. They differ when a device-addressed envelope
arrived before an identity-addressed one: the probe queued a `cancel` to the device, then one to the identity.

**Choices considered.** (a) Arrival order across both queues — what a relay that keeps one log per device does, and the
plain reading of "in order". (b) Identity queue first — an artefact of keeping two maps; no rule asks for it. (c) Id
order — would reorder envelopes from different senders by their own ULID clocks.

**Decision (2026-10-03).** (a), as spec-gap 89 did for fan-outs: the suite's own wording is the contract and the
implementations that diverged from it are fixed. README states it; Python and Rust record an arrival number when
queuing; the second implementation already complied. Vector
`state/relay-bind-flushes-device-and-identity-queues-in-arrival-order` (device, identity, device queued; delivered in
that order). No spec text: emission order is the suite's contract, not the protocol's — two `cancel`s for different
sessions mean the same in either order.

## 99. M§4.3 / M§4.4 / M§5.6 / M§9 / core §13.3 — storage limits: what `accepted` promises, and how quota is counted

**Status: decided 2026-10-04 (user: "yes to all four") — written into M§4.4, M§5.6, M§9.3 and core §13.3.** Raised by the
user: "if a relay is storing users' messages until they can be sent, what happens when it runs out of space?"

**Gap.** Four places where the profile assumes storage behaviour it never states.

1. **`accepted` and durability.** Senders stop retrying on `accepted` (M§9.2–M§9.4; spec-gap 72's outbox), so a
   mailbox that acknowledges an item it has not made durable loses it at the next restart while the sender believes it
   delivered. The PoC did exactly that: `dsip-mailbox` logged `saving state failed` and carried on. Nothing in the
   profile says `accepted` means "stored durably".
2. **What `quota_bytes` counts** (M§4.3 advertises it; M§4.4 and M§14.3 say quota is `mailbox.quota-exceeded`): which
   stored things count, when the check runs relative to the other refusals, whether a redelivery can be refused, and
   whether introductions — which §19.4 requires to be indistinguishable from an ignoring recipient — are counted.
3. **Blob uploads over quota.** The M§5.6 refusal table (spec-gap 48) has no row for quota.
4. **Relay memory.** §13.3 bounds nothing globally; a per-recipient cap alone lets traffic to many recipients grow a
   relay's store-and-forward memory without bound.

**Choices made (PoC).**
1. A deposit that stored a new item is acknowledged only after the mailbox state is written; if the write fails, the
   step is rolled back and the deposit refused `mailbox.quota-exceeded` with `retry_after` (60 s), so the sender keeps it
   pending. Proposed spec text (M§9): *"A service MUST NOT answer `accepted` for an item it has not stored durably; one
   that cannot store refuses with `mailbox.quota-exceeded`."* Live check: with the mailbox's state directory unwritable
   the fan-out was refused, and after it became writable the hub's retry delivered it exactly once.
2. Quota counts the bytes of retained items (welcomes, hub fan-out, archive records) plus stored blobs. The check runs
   after the duplicate checks — a redelivery is never refused — and after every other refusal of that deposit, before
   anything is stored or registered; a `group-info` that would replace the previous one is checked with the previous one
   still counted. Introductions are never counted or refused for quota (§19.4: they stay bounded by the inbox). Vectors:
   `messaging/mailbox-quota-*` (8).
3. `507 mailbox.quota-exceeded`, decided from the authorized size before the body is read, after `413`; a hash already
   stored is never refused. Vectors: `messaging/blob-put-*quota*`, `blob-put-over-max-and-quota-413`,
   `blob-put-stored-hash-at-full-quota-200`.
4. Relays: a memory budget for queued envelopes across all recipients (`dsip-relay --queue-budget-bytes`, default 64
   MiB), refused with a signed `transport.routing-refused` like the inbox cap (§13.3 forbids silent drops);
   introductions are dropped silently at either bound (§19.4); a `cancel` for an invite still queued is never refused,
   since it only shrinks the queue.

**Hub durability (2026-10-04, closes the known non-conformance).** The reference hub saves a newly accepted item before
answering the depositor or fanning out; if the write fails it restores the group's hub state (machine, public view,
conversation, kept payload) and refuses `mailbox.quota-exceeded` with `retry_after`. To the sender a hub's storage
refusal is the hub unavailable (M§9.4): the item stays pending under the outage backoff and counts toward
`hub_timeout`. The backoff governs; `retry_after` is advisory and not an input to the outbox (a finding of the second
implementation, which asked whether it replaces or floors the backoff). Vectors
`messaging/hub-outage-storage-refusal-is-an-outage`, `-reaches-the-threshold`. Live check: the hub's state directory
unwritable → Alice's message refused and kept PENDING (retry 1, 2, 4 s), sent once after recovery, received once.

**Open (next revision).** Relay store-and-forward is in memory, so a relay restart loses queued envelopes; §13.3 does
not say whether that is acceptable. (`retry_after` was decided: SHOULD on the refusal, advisory to the sender.)

## 100. core §13 — relay service scope: may a relay serve only some identities?

**Status: decided 2026-10-04 (user: "do both, the allowlist and the spec text") — written into core §13.6.** Raised by
the user: "can someone hosting their own relay keep it private, or do we make all relays participate to grow the
network?"

**Gap.** The spec says what a relay does for the identities bound to it, but never whether a relay may choose which
identities those are. Because a sender connects to the *recipient's* relay (the one its DID document names), a relay
that simply refuses outside devices also makes its own users unreachable, and one that binds anyone becomes a free
relay between strangers. Neither is stated.

**Choice made.** §13.6 names three deployments.
- *Open*: serves every identity that binds (the PoC default).
- *Private*: serves an operator-chosen set. It still binds any verified device. It routes only to or from a served
  identity, holds envelopes only for served identities, and is authority only for them. Everything else gets a signed
  `transport.routing-refused`. Introductions are dropped silently (§19.4).
- *Closed*: also refuses `hello` from outsiders. Conformant, but unreachable from outside.

No relay is obliged to serve or forward for anyone. Participation stays voluntary: the network grows with identities,
each bringing its own relay via its DID document, not with shared relays. Rejected: mandatory participation (cost and
abuse liability on hosts, and Sybil exposure that is out of scope per §3.2).

**PoC.** `dsip-relay --serve <DID>` (repeatable) / `--serve-file`; unset = open. `demos/private-relay-demo.sh`
covers an outsider reaching a served identity live and queued, outsider-to-outsider refused, nothing held for an
outsider, and an introduction between outsiders dropped silently. No vectors: this is routing policy outside the
relay state machine (`dsip_session::Relay`), checked before it.

**Open.** A relay cannot yet *advertise* its scope; a `hello` capability (`serves: "open" | "private"`) would let a
client know before it tries. Not needed for correctness, since refusals are explicit.

## 101. §7.2 / §8.1 / §8.4 — `did:webvh` in DSIP: what a resolver must check, and rollback

**Status: decided 2026-10-04 (user: "yes to all 4"; rollback: "cache required, watchers optional") — written into
v0.9 §7.2, §8.4, A.6; pinned by `impl/vectors/did-webvh/` (67 vectors).**

**Gap.** `did:webvh` (DIF Ratified v1.0) makes a domain-hosted DID document unforgeable by its host, but a resolver
that only verifies the log as served still accepts an *older* valid log. A host can roll an identity back to a key it
rotated away from. The method leaves rollback detection to resolver caches, watchers and witnesses. DSIP must also say
which versions it supports and how strictly it reads the log, so that three implementations agree.

**Choices made.**
1. **Rollback:** a resolver MUST cache the highest verified `versionId` per DID, and reject a log that ends before it
   (`rollback`) or differs at it (`fork`). Watchers MAY be consulted. Rejected alternatives: requiring watchers (an
   extra fetch per lookup, and they must exist) and requiring witnesses (a heavy deployment burden).
2. **Fail closed:** any invalid entry rejects the whole log. The method allows a versioned query to succeed below a
   later invalid entry; DSIP resolves only the latest version.
3. **Versions:** `did:webvh:1.0` only.
4. **I-JSON:** every line, and the witness file, must be I-JSON (RFC 7493): no duplicate names, no lone surrogates,
   integers within ±(2^53−1). This was found by probing the three implementations (a third finding of the second
   implementation's notes): an integer above 2^53 hashed differently in JavaScript, a duplicate key is a
   signature-confusion risk, and a lone surrogate crashed one runner. JCS assumes I-JSON anyway.
5. **Extra entry keys** are refused (`log-malformed`). The method lists the five entry properties without saying
   "only". See spec-gap 102 for why accepting them is unsafe in practice.
6. **DID syntax:** ASCII LDH domain labels (an IDN in its `xn--` form), the port separator `%3A` in upper case only,
   percent-decoded path bytes valid UTF-8, and Unicode White_Space at either edge of a segment refused.
7. **A deactivated DID** returns no document and has no keys (the method's MUST, which its implementations diverge on).
8. **The check order and reason tokens** are the suite's contract (`impl/vectors/README.md`, kind `did-webvh`).
9. **Boundary with CLAUDE.md rule 3:** JCS is used inside the method's own hashes and proofs. No DSIP envelope is
   ever canonicalized.

**Evidence.**
- The Python reference resolves all 76 positive logs of the DIF conformance suite
  (`didwebvh-test-suite` @ `703f97f`) and rejects all its log-level negatives.
- The vector logs were also run through `didwebvh-rs` 0.8.0 (41 of 43 applicable agree) and `didwebvh-ts` 2.8.0 (37
  of 43). Every disagreement is a case where the library is laxer than the spec text (spec-gap 102).

## 102. did:webvh v1.0 (upstream) — findings to report to the DIF working group

**Status: draft, for the user to send upstream.** The texts are in `impl/docs/upstream-reports.md`, rechecked on
2026-10-05: reports 1–6. Item 2's spec half is fixed upstream (the spec now rejects unknown `method` values with its
own negative example); the library half remains. Found while implementing spec-gap 101. These are not DSIP spec
issues; DSIP's resolution is pinned either way.

1. **Unknown entry properties are dropped before hashing by both reference libraries.** An entry with an extra key
   added *after* it was hashed and signed resolves as VALID in `didwebvh-rs` 0.8.0 and `didwebvh-ts` 2.8.0, so the
   extra content is covered by no signature. The spec lists the five entry properties but never says "only these".
   Suggest: "a log entry MUST NOT contain other properties; a resolver MUST reject one that does".
2. **`didwebvh-rs` 0.8.0 accepts `method: "did:webvh:9.9"`,** contrary to §Parameters ("MUST reject any `method`
   value that is not exactly one of the acceptable values") and to the spec's own negative example `did:webvh:99.0`.
3. **`didwebvh-ts` 2.8.0 (latest on npm) predates the 2026-06-06 hardening.** It accepts:
   - an entry after deactivation;
   - a portable move without `alsoKnownAs`;
   - an empty `proof` array;
   - an omitted `nextKeyHashes` under pre-rotation;
   - unknown parameters;
   - extra entry keys.

   The repository is at 3.0.0, unpublished.
4. **I-JSON is not stated.** JCS (RFC 8785) assumes I-JSON, but the method never requires it. Large integers,
   duplicate names and lone surrogates make implementations disagree (spec-gap 101 item 4).
5. **Schema versus prose** (`schemas/v1.0/log_entry.json`):
   - `minItems: 1` on `updateKeys`, `nextKeyHashes` and `watchers`, while the prose uses `[]` to deactivate and to
     end pre-rotation;
   - `proof` may be a single object;
   - `"type": "date-time"` is not valid JSON Schema.
6. **Smaller points:**
   - "one second" monotonicity in the security section versus "strictly greater" in the normative text;
   - a legacy base32 `nextKeyHashes` example;
   - metadata `ttl` and `witness.threshold` specified as strings while implementations emit integers;
   - `portable: false` together with a move in the same entry;
   - leading zeros in the `versionId` number;
   - fractional seconds in `versionTime`.

## 103. E§3–E§6 — Device Events Profile: re-raise, the syslog table, who escalates, SNMPv3 and syslog inputs

**Status: decided 2026-10-04 (user: "yes to all 4"; "reopen the same alarm"; "default table, configurable"; "an
escalation agent member") — written into `v0.9/dsip-device-events-profile-v0.9-draft.md`; pinned by
`impl/vectors/device-events/`.**

**Gap.** The new profile had three choices with no standard to defer to:

1. When a cleared alarm is raised again:
   - **reopen** the same alarm (RFC 8632: one alarm per key, with history);
   - **or open a new incident** (PagerDuty; an OpenNMS option).
2. How syslog severities map to alarm severities. RFC 5424 has eight levels and RFC 8632 five, and no standard
   bridges them.
3. Who runs the escalation timer: the NOC's mailbox/hub, or a member.

**Choices made.**
1. **Reopen**, with `reopened: true`. The operator state returns to `none`, so the alarm gets attention again, and the
   alarm can escalate again (once per raise). A flapping link is one alarm with a count.
2. **A default table, overridable per rule:** 0–2 `critical`, 3 `major`, 4 `warning`, 5–7 no alarm. It is a
   convention, so it is an `Impl` note.
3. **A member, the escalation agent.** Mailboxes and hubs stay storage and ordering services (M§4). The trigger is
   normative; the rota and timers are local policy.

**Also fixed while implementing.** Probing the three implementations on the second implementation's notes pinned:
- strict v1 fields (generic 0–6);
- a decimal-string sysUpTime;
- varbinds carried as exactly `{oid, type, value}`;
- a missing severity or `by` as null;
- gateway-silence processing in gateway-id order, not first-heartbeat order. impl-ts had read it the other way.

**Done (2026-10-05).**
- `device-event` and `alarm-ack` are registered content kinds (M§8.2; 4 vectors).
  - The kind check tests that the body fields are present.
  - Their contents are the alarm list's to judge (E§5).
- A reference gateway: `dsip-trapd` (BER decoding of SNMPv1/v2c traps, E§3 translation, E§4 rules, heartbeats)
  feeding the gateway's `dsip-msg`.
- `dsip-msg` keeps each group's alarm list and acknowledges with `alarm-ack`. As an escalation agent
  (`--escalate-min`, `--escalate-after`, `--escalate-cmd`) it runs the escalation command.
- `demos/device-events-demo.sh`, in CI. Real traps become signed events in an MLS alarm group, and:
  - every member keeps the same alarm list;
  - a repeat pages nobody;
  - an acknowledged alarm does not escalate;
  - an unacknowledged critical alarm rings the on-call phone through `dsip call`;
  - a silent gateway raises its alarm;
  - the community never leaves the gateway.

**Informs (2026-10-05).**
- The trap receiver moved into the gateway's `dsip-msg` (`--snmp-listen`, `--snmp-rules`, `--heartbeat`), which
  sees the hub's verdict. `dsip-trapd` is retired.
- An inform is answered (RFC 3416 §4.2.7 Response-PDU, echoing request-id and varbinds) only once its event is
  `accepted`, including when the outbox delivers it after a hub outage.
- An inform tracker gives one event per inform. Pinned by `device-events/inform-*` (9 traces), with the key order
  pinned numerically after a question from the second implementation.
- The demo kills the hub mid-inform: the device's 3 retransmissions go unanswered and deposit nothing more, and the
  next one after recovery is answered. There is exactly one event.

**SNMPv3 and syslog (2026-10-05).** E§2 gains the claims an authenticated basis adds: `usm: {engine_id, user}`
and `certificate_sha256`. E§3 gains USM processing and the syslog fields; E§4 gains syslog rules. The vectors README
pins the USM pipeline (10 reason tokens, in RFC 3414 §3.2 order), BER, the RFC 5424 / RFC 3164 grammar and the
syslog mapping. That adds 86 vectors (1309 total), with three-way parity and two new fuzz targets (`syslog`,
`snmpv3`).

Choices made (Impl):
- **Refused:** `noAuthNoPriv` (it proves nothing v2c does not), DES (RFC 3414 §8), and security models other than
  USM.
- **Wildcard users:** a password user may omit its engine ID and is then localized per message.
- **Trap time cache:** a trap engine's cache entry is seeded by its first authenticated message. RFC 3414 creates it
  by discovery, which a trap receiver never does.
- **Reports:** only `unknown-engine-id` (discovery) and `not-in-time-window` (time sync) are answered; every other
  failure is silent.
- **RFC 3164** is accepted. Its tag heuristic reads Cisco's sequence number as `app_name`, and a vector pins that.
- **Unmatched syslog:** an unmatched message that the table maps to a severity raises `(source, syslog, app_name)`.

Questions the second implementation raised, now pinned by README text and vectors:
- `<00>` is malformed.
- `resource_sd` searches only the first element with its `id` (E§4's wording was aligned).
- A userName that is not UTF-8 matches no user.
- An empty OID is malformed.
- NULL must have empty content (X.690 §8.8.2).
- Integer32 is bounded to ±2^31, and Counter32, Gauge32 and TimeTicks to 2^32−1 (RFC 2578).
- A PDU's constructed bit is not checked.
- Every SEQUENCE holds exactly its listed elements.
- Encodings need not be minimal (BER, not DER).

Outside oracles:
- RFC 3414 A.3's MD5 and SHA-1 localized keys.
- pysnmp 7.1.30's RFC 7860 SHA-2 keys.
- Three traps captured from pysnmp (SHA+AES, SHA-256, MD5+AES), kept verbatim as vectors.

The gateway (`dsip-msg`):
- New flags: `--snmp-users`, `--snmp-engine-id` (a persistent ID, with boots incremented at each start),
  `--syslog-listen`, `--syslog-tls-listen` (client certificates required, RFC 5425 octet-counted frames) and
  `--syslog-table`.
- Members render the basis with its verified identity.

`demos/device-events-v3-syslog-demo.sh` (in CI) uses real senders:
- **pysnmp:**
  - an authPriv trap arrives with its engine and user;
  - a wrong password is refused with `wrong-digest`;
  - after a reboot (boots + 1), a byte-for-byte replay of the pre-reboot trap is refused with `not-in-time-window`;
  - a v3 inform runs discovery against the gateway (a Report), is answered only once stored, and is deposited once.
- **logger:** RFC 5424 matched by a rule, and RFC 3164 through the table.
- **TLS:** a client with a device certificate gets `syslog-tls` and its fingerprint; one without is refused.
- No USM password leaves the gateway.

**v0.10, decided with the user 2026-10-06 ("Delay clears").**
- **Hold-down (E§4):** optional; the gateway delays clears by `H` s (0 = off). A raise of the same alarm while its
  clear is held cancels the clear, so members count a repeat, and a fast flap stays one alarm. A second clear keeps
  the first one's time. Events, and anything from an inform (answered only once stored, E§3), pass at once. Members'
  rules are unchanged.
- **Vectors:** `device-events/holddown-*` (8 traces), three-way. The second implementation's readings pinned key
  order (code points) and that other report fields pass through (`holddown-same-due-key-order`).
- **Certificate names (E§2):** an optional `source.name`, the gateway's configured name for the verified identity.
  It is a claim, and members render it only beside that identity.
- **Gateway:** `dsip-msg --hold-down`, `--syslog-tls-names`. In `demos/device-events-v3-syslog-demo.sh`, port 7 flaps
  (down, up, down, up) and Ann sees one raise and one clear; sw1 is shown as `name="sw1-core"` beside its
  fingerprint.

**SNMPv3 over TLS (v0.10, E§3; RFC 6353 TLSTM + RFC 5591 TSM).**
- **Basis and claim:** basis `snmpv3-tls`; the claim carries `certificate_sha256` and `tsm.security_name`.
- **Transport:** TLS over TCP only (DTLS left open), with a client certificate required.
- **The name table is pinned where RFC 6353 is loose:**
  - rows are tried in ascending `id`, matching the leaf or a CA in the verified path;
  - six maps, with only the first SAN of the type tried;
  - a name of 1–32 UTF-8 bytes, otherwise the next row;
  - no name closes the connection.
- **Framing:** BER self-delimited messages of at most 65,536 bytes; an unframeable stream is closed.
- **Per message:** `malformed`, `unsupported-security-model` (USM over TLS is refused), then `not-a-notification`. Any
  `msgFlags` level is accepted.
- **RFC 5343 discovery is required:** net-snmp's `snmpinform` probes `snmpEngineID.0` in context `8000000006` and
  gives up without an answer. The answer echoes that context (RFC 3412); only the varbind carries the engine ID. The
  first draft of E§3 put the engine ID in the context, and net-snmp discarded the Response. The real client caught
  it, and a unit test now pins it.
- **Vectors:** `tsm-*`, `tls-frames-*` and `tsm-name-*` (71), three-way. Of the second implementation's fifteen
  readings, three are now pinned in the README with vectors: first SAN only, IP hex in either case, and a single
  byte waits. Three new fuzz targets (`tsm`, `tls-frames`, `tsm-name`) ran 9,000 probes with no divergence.
- **Gateway:** `dsip-msg --snmp-tls-listen/-cert/-key/-ca/-map`. The certificate's fields come from x509-parser; the
  verified path's CA is matched by issuer against the configured CAs (an `Impl:` note). Informs are remembered by
  security name.
- **Demo:** `demos/device-events-snmp-tls-demo.sh` (in CI) uses net-snmp 5.9.5.2. 5.9.4, as shipped by Debian trixie
  and Ubuntu 24.04, caps its TLS client at TLS 1.0 and cannot connect; upstream report 11 asks for the backport.

**Signed syslog (v0.10, E§3; RFC 5848). Decided with the user 2026-10-06: "Hold, then deposit once".**
- **Basis and holding:** basis `syslog-signed`, with claim `signed` {hostname, app_name, procid, rsid, sg, spri,
  message_number, key_sha256}. A configured signer's messages are held up to `H` s (default 10); unsigned in time,
  they are deposited with their transport's basis.
- **What is pinned where RFC 5848 is loose or contradicts itself:**
  - **Keys:** configured per HOSTNAME (types C and K; §5.2.2 b end-entity matching), so every block, including each
    fragment, is authenticated on arrival.
  - **Versions:** `0111` and `0121` with OpenPGP DSA; the MPI bit count is only a length.
  - **The block** is the message's only SD element, which locates the signed bytes.
  - **FRAG** is the payload text (the example, against the table).
  - **Replays:** `old-session` per (HOSTNAME, APP-NAME).
  - **RSID 0:** a different payload resets the session.
- **Vectors:** `syslog-sign-*` (51), three-way, including RFC 5848's two examples verbatim, which verify. Python
  (OpenSSL) and Rust (RustCrypto `dsa`) agreed at first run. The second implementation verifies DSA with its own
  BigInt FIPS 186 code.
- **The new `syslog-sign` fuzz target found two real divergences:**
  - an unescaped `]` inside a quoted value: Python and Rust took the first `]` as the element's end;
  - waiting hashes when a session ends: the second implementation kept them.

  Both are fixed and pinned with vectors, along with five of its other readings. Afterwards 3,000 random probes showed
  no divergence.
- **Gateway:** `dsip-msg --syslog-signers`, `--syslog-sign-hold`; the transport of a held message is remembered for
  its unsigned deposit.
- **Demo:** `demos/device-events-syslog-sign-demo.sh` (in CI). No packaged signer exists (NetBSD's syslogd is the
  one implementation), so the demo's signer is `demos/syslog_sign_send.py`.
- **Upstream reports 12 and 13** draft RFC 5848 errata: FRAG's encoding, and the example's MPI bit count.

**Gap detection from signed syslog (v0.11, E§3).**
- **Opt-in** per signer (`gaps: true`), because RFC 5848 §4.2.3 expects gaps when a signer splits its messages
  across collectors.
- **Two gap kinds, per Signature Group:**
  - numbers no verified block covered: a block's FMN past the group's `covered`;
  - numbers signed but never arrived: a waiting hash expires.
- **Reporting:** each gap is a gateway event (`syslog_gap`, E§5) raising `(<signer>, dsip-syslog-gap,
  "<app>/<sg>/<spri>")`, warning. Later gaps re-raise it, so it is one counted alarm. A session's end drops its
  `covered`, waiting hashes and numbers.
- **Vectors:** `syslog-sign-gap-*` (11), three-way. The second implementation's two open readings were pinned: a
  run's identity comes from its lowest number's block, and `covered` resets with the session. The second of these was
  a real divergence, since Python and Rust kept `covered`.
- **Fuzzing:** the `syslog-sign` target now randomizes `gaps`; 4,000 probes found no divergence.
- **Demo:** `device-events-syslog-sign-demo.sh` shows both kinds raising one alarm.

**Key blob types N, P and U (v0.11, 2026-10-09).** RFC 5848 §5.2.1's remaining types, pinned by
`device-events/syslog-sign-blob-*` (19 traces), three-way.
- **`N`**: no key information sent; the session uses the configured key, whatever its type. Exactly two payload
  fields: a third is `payload-mismatch`.
- **`P`**: the OpenPGP KeyID and certificate. The collector reads the certificate as OpenPGP packets (old and new
  format headers, definite lengths only), takes the first packet, which must be a v4 DSA Public-Key packet whose
  MPIs fill its body, and checks the KeyID against the V4 fingerprint. Nothing else in the certificate is examined:
  the collector authorizes keys by configuration (RFC 5848 §5.2.2), so User ID packets and self-signatures add
  nothing it would act on. A configured `P` key that does not read leaves the signer without a key, and its blocks
  fail `bad-signature`.
  **Choices considered** for a bad `P` key: a configuration error at load (outside the vector contract), treating
  the signer as unknown (`unknown-signer`, which would hide a misconfiguration behind the same answer as a stranger),
  or `bad-signature`. **Chosen: `bad-signature`.**
- **`U`**: `unsupported-key-blob`, a new reason. Installation-specific key exchange has no interoperable reading.
- **Retired:** v0.10's `syslog-sign-payload-other-type` pinned `N` as `payload-mismatch` under the two-type rule; it
  is replaced by `blob-n-session` and `blob-unknown-type`.
- The `syslog-sign` fuzz target now draws `P` signers (one with a wrong KeyID) and `N`/`U`/unknown payloads.
- **Demo:** `device-events-syslog-sign-demo.sh` adds a signer whose certificate is OpenPGP (`P`) and a rebooted
  signer re-establishing with `N`.

**DTLS for SNMP (v0.11, 2026-10-09; RFC 6353 over UDP).** The last leftover. The transport model is the same: the
DTLS session's client certificate names the sender through the same table, and a session with no name is closed
(RFC 6353 §5.3.2). What differs is framing: a DTLS record carries exactly one message, pinned by
`device-events/dtls-record-*` (11, stateless, defined through the `tls-frames` split: one message, nothing pending,
no close). A record that is not one message is dropped and the session continues. The basis stays `snmpv3-tls`,
RFC 6353's one model; E§2's `tsm` claim gains `transport: "tls" | "dtls"`.
- **Choices considered** for a record that is not one message: close the session (as an unframeable TLS stream is
  closed) or drop the record. **Chosen: drop.** A stream that cannot be framed loses synchronization for good; a
  datagram does not, since the next record starts clean.
- **Host:** `dsip-msg --snmp-dtls-listen`, OpenSSL's DTLS server (rustls has no DTLS) with RFC 6347's cookie
  exchange, a session per peer address. A lost handshake flight is retransmitted by OpenSSL's DTLS timer, run from
  the session thread (`DTLSv1_handle_timeout`, reached through `SSL_ctrl` since the crate does not wrap it); a
  session silent for 300 s is shut down, and the peer's next datagram starts a new one. At most 64 handshakes are
  in flight at once (each unseen source address costs a thread until the cookie exchange and the certificate check
  are done), and a handshake has 10 s; past the cap, datagrams from new addresses are dropped until one ends.
- **Demo:** `device-events-snmp-tls-demo.sh` sends sw1's trap over net-snmp's `dtlsudp:` transport, and sw3's
  nameless session is closed.

**Closed:** every item of spec-gap 103 is now disposed.

## 104. T§2–T§5 / core §8.1–§8.2 — alias transparency: what DSIP adopts of KEYTRANS, and when

**Status: decided 2026-10-04 (user: "KEYTRANS-shaped, blinded"; "stage it") — written into
`v0.9/dsip-alias-transparency-profile-v0.9-draft.md`; stage 1 pinned by `impl/vectors/alias-transparency/`.**

**Gap.** §8.2 aliases (`alice@example.com → DID`) are the one place a provider can silently substitute someone's
identity. IETF KEYTRANS solves this, but it is a working-group draft whose lookup-proof format is changing:
- the editors' copy is not wire-compatible with -05;
- open issue #51 records an interoperability failure over `PrefixProof` contents.

**Choices made.**
1. **Shape:** KEYTRANS-shaped, with VRF-blinded labels, as a DSIP profile that tracks the draft. Rejected:
   - CT-style public log: it enumerates a provider's users;
   - adopting KEYTRANS verbatim: the draft is still moving.
2. **Staged.** Stage 1 is now: the profile choices and the building blocks, which are stable. Stage 2 follows -06:
   - lookup verification;
   - owner monitoring;
   - fork detection via `DistinguishedHead` in DSIP signalling;
   - credentials, in introductions.
3. **One suite, one mode:** `KT_128_SHA256_Ed25519` only, and `contactMonitoring` only.
4. **`validate_key = TRUE`.** KEYTRANS states no choice, and RFC 9381 §5.3 requires one.
5. **Canonical point decoding** (RFC 8032 §5.1.3) everywhere, and a one-byte encode-to-curve counter. Found by the
   second implementation's notes.
6. **Alias normalization (T§3)**, which §8.1 never defined:
   - split at the last `@`;
   - a printable-ASCII local part, case kept;
   - LDH domain labels, lowercased;
   - at most 255 bytes.

   Internationalized local parts are deferred, because Unicode normalization tables differ across implementations.
7. **Discovery:** a `DSIPAliasLog` service in the provider's `did:web` document, holding the TLS-encoded
   Configuration.
   - The Configuration's signing key must be one of that DID's verification methods.
   - The Configuration is pinned on first use; a change is a log migration.
8. **KT bytes are carried raw**, never re-wrapped in DSIP envelopes, so any KEYTRANS implementation can verify them.
9. **Configuration integers above 2^53−1 are refused**, so they survive JSON in every language.

**Evidence.**
- RFC 9381 Appendix B.3 Examples 16–18 are vectors.
- katie's commitment test vector is reproduced.
- The draft's own search-tree and ladder examples are vectors.
- Every computed hash and signature was confirmed with **katie**, the KEYTRANS editor's Go implementation (commit
  `e1640671`): indexes, commitments, prefix and log roots, the Configuration and tree heads.

**Findings for the KEYTRANS working group** (the user to send). The texts are in `impl/docs/upstream-reports.md`,
rechecked on 2026-10-05 against the editors' copy at `a214b15`:
- **Fixed upstream since:** items 1 (`leaf_public_key`), 2 (vector lengths) and 7's stray `UpdateRequest`.
- **Partly settled:** item 3 (the `nonInclusionParent` depth is now defined), sent as a question on #51.
- **Still open, sent as reports 7–9:** items 4 (empty root), 5 (`Kc`) and 6 (the VRF).

The original list:
1. **Mode-1 Configuration.** -05 §11.2 gives contactMonitoring a `leaf_public_key`. The editors' copy removed it
   (commit `b97f81d`, 2026-07-28), and katie follows the editors. Implementations of -05 and of the editors' copy
   compute different `TreeHeadTBS` bytes, so their signatures don't verify across them. DSIP follows the editors'
   copy.
2. **The -05 → editors' copy change to vector-length semantics** (element counts).
3. **`PrefixProof.elements` for `nonInclusionParent`** (#51), and the change to its depth.
4. **The empty prefix-tree root** is unspecified.
5. **`Kc`** is called a "hex-encoded string" but is used as raw bytes (katie agrees with raw bytes).
6. **The VRF `validate_key` choice** is unstated, as are canonical point decoding and the counter bound.
7. **Editorial:**
   - a stray `UpdateRequest request;` in -05 §15.1;
   - [KTA] -09 §7 cites the RMW as "[PROTO] §7.1"; in -05 it is §6.1.

**`tel:` labels (v0.12, 2026-10-09; for Number Attestation route 2).** T§3 gains the `tel:` alias: a global tel
URI (RFC 3966) with no parameters, visual separators removed, E.164 digits, lowercase scheme; the label is
`tel:+<digits>`. Pinned by `alias-transparency/alias-tel-*`. **Choices considered:** admit parameters (`;ext=`,
`;phone-context=`) and local numbers, or only global numbers. **Chosen: global numbers only**, matching the
profile's E.164 scope (spec-gap 110 item E); a local number has no identity without its context.

**Open (stage 2).**
- Lookups, monitoring and fork detection.
- Anti-enumeration at the query endpoint: identical answers for "no such alias" and "not permitted", plus rate
  limits.
- Credentials in introductions.

## 105. §8.5 / DHT Hints Profile §9 — reachability hints on Pkarr (the Mainline DHT)

**Status: decided 2026-10-04 (user: "yes to all 4"; "compact root-signed record") — written into the DHT Hints Profile
§9 and core §8.5; pinned by `impl/vectors/pkarr/` (40 vectors).**

**Gap.** v0.9 adds Pkarr as a second carrier for hints, putting them on a DHT far larger than DSIP's own overlay.
Pkarr does not fit DSIP hints directly:
- a BEP 44 item can be signed only by the key it is stored under, so a device cannot publish;
- values are capped at 1000 bytes, and a DSIP-JOSE hint with delegations does not fit;
- Pkarr has no signed expiry.

**Choices considered.**
- **(a) Compact `_dsip` TXT records signed by the identity key.** Chosen.
- **(b) A pointer to device-signed hints.** Deferred: it needs a new delegation conveyance (§7.4) and a freshness
  rule, because a withholding node can keep serving a pointer that still lists a revoked device.
- **(c) The whole JOSE hint in TXT.** Rejected: only an identity-signed, single-endpoint hint fits.

**What DSIP adds over Pkarr.** The pkarr crate accepts all of the following, which DSIP refuses or rejects:
- a timestamp in the future (DSIP allows at most 300 s ahead);
- a record outside the key's zone (DSIP ignores it);
- non-canonical z-base-32 (Pkarr accepts 16 encodings per key; DSIP requires the canonical one);
- any TXT content (DSIP requires exactly one `wss://` `uri=` and at least one `b=`).

DSIP also adds:
- a signed expiry of the timestamp plus the smallest TTL, each TTL at most 3600 s;
- §8.3 conflicts in place of "larger packet wins";
- owner names compared label by label without case (the crate's lookup is case-sensitive);
- `seq` at most 2^53−1, so it is exact as a JSON number.

**Evidence.**
- BEP 44's published test vectors are vectors.
- An independent Python codec produces packets byte-identical to the pkarr crate's.
- Every vector's payload was run through the crate (`SignedPacket::from_relay_payload`, v8.1.0). It agrees on every
  value and must-agree case, and every difference is one of DSIP's additions listed above.
- Probing the second implementation's notes pinned: label-by-label name matching, framing checked before content,
  the 2^53 bound, and non-hex payloads as `malformed`.

**Network (2026-10-05).**
- `dsip answer --publish-pkarr --pkarr-relay <url>` builds and signs the `_dsip` packet
  (`dsip_core::pkarr::build_payload`, with a round-trip unit test through the reader) and re-signs at 2/3 of the
  TTL. `dsip call --pkarr-relay <url>` asks every relay, reads each answer offline and takes the highest seq (§8.3).
- Relays only (Pkarr's HTTP `PUT/GET /<z32>`), since a relay writes to the Mainline DHT itself. Direct DHT access
  (the mainline crate) is not done.
- **Interoperability:** the real `pkarr-relay` (v8.1.0 source, `--testnet`: a 10-node Mainline DHT on localhost,
  nothing public) accepted 4 successive publishes, with its own signature and packet parsing. It served them back,
  the Python reader accepted the bytes, and a call was completed through it.
- **Demo** (`demos/pkarr-demo.sh`, in CI, against local stand-ins of the HTTP API): a hostile relay's forged newer
  packet is rejected (`signature`), the call reaches the real relay, the seq rises across re-publishes, and another
  application's record in the zone survives.
- **Decided (with the user, 2026-10-05): re-encode, never drop.** The publisher used to keep only TXT, A and AAAA.
  Now every IN record outside `_dsip` is carried:
  - names inside the rdata of the RFC 1035 types that RFC 3597 §4 lets compress are expanded;
  - every other type is copied as is, since RFC 3597 forbids compression in it, so SVCB and SRV are verbatim.

  It still ignores a previous packet that does not verify under its own key, so a hostile relay cannot push its
  seq. Pinned by `pkarr/carry-*` (12 vectors).
- **Decided (with the user, 2026-10-05): previous + 1, stated.** The timestamp is max(clock, previous + 1), and the
  profile names a clock stepped back as the one case signed ahead of the clock. A result above 2^53−1 (which readers
  reject) is not signed. Pinned by `pkarr/next-ts-*` (5 vectors).
- **The second implementation's questions,** settled in the README:
  - an excluded record's rdata is not examined;
  - which bytes of a name in rdata count as "in place";
  - the pointer rule inside rdata;
  - names keep their case;
  - the `_dsip` exclusion covers any type and exactly two labels, with class exactly IN;
  - only answer records are carried;
  - `dns` that is not hex is `malformed` (a vector), and the exhaustion case above.

**Mainline directly (2026-10-05).**
- `--mainline [--mainline-bootstrap host:port,…]` on `dsip answer`, `dsip call` and `dsip resolve` runs a Mainline
  node (the mainline crate, v8.0.1). It puts the same signed bytes as a BEP 44 mutable item (`seq` = ts, `v` = the
  DNS message, no salt), and gets every item a lookup returns.
- Relays and the DHT are sources of one candidate set. Every candidate is read offline by the DSIP reader, and the
  highest valid seq wins; the crate's own checks and "most recent" choice are not relied on. The put carries no
  CAS, since the seq order settles concurrent publishers.
- **Interoperability:** Pkarr's own client (v8.1.0 source, DHT only, `ResolvePolicy::NetworkOnly`) resolved the item
  DSIP put on a local testnet and parsed the `_dsip` TXT record intact.
- **Demo** (`demos/pkarr-mainline-demo.sh`, in CI): `dsip mainline-testnet` runs 10 nodes on 127.0.0.1. Bob puts to
  the DHT with no relay in his path, and Alice gets it from the DHT while a hostile relay's forgery is rejected. The
  seq rises over 3 puts, and a fresh node finds the newest packet after Bob left.

**Option (b), multi-device identities (v0.10, decided with the user 2026-10-06).**
- **Pointer:** the identity key signs `_dsip-devices` records (`dev=<did:key>`, TTL up to 604,800 s).
- **Device zone:** each device signs its own zone: the `_dsip` endpoint records (3,600 s cap) and one
  `_dsip-delegation` record holding the compact delegation. Readers resolve pointer → devices, in order, and verify
  each delegation as §7.4 does (§9.1).
- **Revocation is bounded, not immediate,** and the profile says so: by the delegation's expiry, the hourly hint, or
  the pointer's re-signing (7 days at most).
- **Vectors:** `pkarr/devices-*` (20) and `pkarr/carry-dsip-devices-and-delegation-replaced`, three-way.
- **The second implementation's twelve readings** were checked against Python and Rust. Ten matched and are now
  pinned in the README. Two were real divergences: a `null` payload (Rust) and an unsplittable delegation record
  (Python), now fixed and vectored.
- **Code:** `dsip_core::pkarr::{build_pointer_payload, build_device_payload, read_pointer, read_device}`; `dsip
  pkarr-pointer`; `dsip answer --publish-pkarr --pkarr-device`. Discovery falls back to the pointer when the identity
  zone has no `_dsip` hint.
- **Demo:** `demos/pkarr-multidevice-demo.sh` (in CI): one identity-signed pointer; the phone reached on R1; then, with
  the phone gone, the laptop on R2. Devices publish with their own keys only.

**HTTP access (v0.11, DHT Hints Profile §10; `dsip-node` stage 1, decided with the user 2026-10-06).**
- **Browsers** still join no DHT, but any `dsip-node` now serves them hints over HTTP, which they verify offline.
- **The routes:**
  - Pkarr's relay interface (`GET`/`PUT /<z32>`);
  - the overlay's `GET /dsip/v1/hints/<did>` and `POST /dsip/v1/hints`;
  - CORS on every answer.
- **A node serves every application's packets,** so a `PUT` passes only what every Pkarr packet must pass, then
  §8.3's `ts` rule (`check: "store"`, 16 vectors, three-way). `_dsip` content is judged by readers.
- **The second implementation's three open readings were pinned:**
  - a held packet is not re-verified;
  - "the same bytes" compares decoded bytes;
  - the path key is case-sensitive.
- **Demo:** `demos/dsip-node-demo.sh` (in CI). DSIP's unchanged clients publish through node A, and a call resolves
  through node C via the Mainline DHT. A browser (curl) reads the overlay hint from C, and forged and older packets
  are refused.

**Open.** None. Browsers stay off the DHT by design; HTTP access is their path.

## 106. M§8.4 "Fetching" — a device whose blob fetch finds nothing

**Status: fixed 2026-10-05 — M§8.4 text; vectors `messaging/blob-fetch-*` (7).** Found when #82 changed the
blob-replication demo.

**Gap.** M§8.4 says how a device orders a content's blob sources and verifies what it gets (rule 7). It says nothing
about a device for which **no** source served the blob, for example when the item arrives before its own mailbox has
replicated the blob and the origin is down. The reference device sent its "delivered" receipt, printed an error and
never fetched again, so a voice message could stay unplayable for good. That is the device-side twin of spec-gap 67.

**Choices considered.**
- **(a)** Retry like a mailbox's replication: only when some source had nothing to serve, with the same backoff and
  bound, across restarts; never when every source served other bytes.
- **(b)** Retry until success: a hostile or broken origin is refetched forever.
- **(c)** Hold back the "delivered" receipt until the media plays. That conflates delivery of the message with
  downloading its attachment, which M§10.2 does not do.

**Choice made.** (a). The receipt is unchanged: the message was delivered, and its media is fetched separately.

**PoC.**
- `dsip-msg` records each source's result, decides with `client::blob_fetch`, and keeps pending fetches persisted.
- It retries them from its ticker: 4 s, doubling, at most 60 s, for 5 attempts.
- It prints `AUDIO-PENDING`, then `RECV-AUDIO` on success.
- `demos/blob-replication-demo.sh` gains a stage where the device's only source has nothing to serve, then does.

## Already-flagged (schema README / plan §11)

- §15.3 codec example uses bare strings; §16.2 defines objects (schemas follow §16.2).
- `$id` base `https://dsip.org/schema/1.0/` is a placeholder pending §24.
- Prose ids like `01HZINVITEABC` are not valid ULIDs.
- §12.7 rule 6 reject preference order lists four tokens; the relay needs a rule
  for other tokens (PoC: first-seen).
- §26 step 8 says ICE candidates ride in `update` envelopes; §12.12/§16.3 say `info`.

## 107. §16.4 / Recording Profile C§1–C§7 (draft) — compliance recording under end-to-end encryption

**Gap.** §16.4's `policy.recording` says what a party accepts, but nothing says that a party **is** recording, who
records, or what a counterparty's client must do. Under end-to-end encryption, compliance recording can only happen
at an endpoint the organisation controls (research track C). Without a disclosure, it happens unannounced.

**Prior art (2026-10-05).**
- **SIPREC** (RFC 7866, RFC 7865): the recording client declares `a=record:on|off|paused`. A participant states
  `a=recordpref`, which the recorder may ignore, and refusing means leaving. The recorder is not a participant: the
  client forks media to it, at least as secure as the recorded session.
- **Wire legal hold** (MLS): a disclosed device on the subject's account, with an indicator in every conversation.
  Users who have not consented are kept out of conversations a legal-hold device is in (per team).

**Decided (with the user, 2026-10-05).**
- **Scope:** all three — disclosure, a recorder role, and a recorder leg for calls.
- **Consent:** render plus local acceptance. A callee does not answer, and a caller holds its media, until the user
  or a standing policy accepts. Declining is `reject` or `bye` with the new reason `policy.recording-declined`.
- **Recorder devices are receive-only:** members do not render their content.

**Choices made (Impl).**
- **The declaration** is a top-level `recording` member on `invite`, `answer` and `update`, signed with the
  envelope: `{state, recorder, purpose?}`. A mid-call change is an `update`, as SIPREC uses a re-INVITE or UPDATE.
- **Acceptance** is per session and per recorder. A resume with the same recorder needs none; a new recorder needs
  it again. A `paused` declaration holds nothing.
- **An unregistered state** reads as `on`, the safe reading.
- **The messaging recorder** is a device of the recorded identity carrying `dsip.record` (the Wire model), visible
  through its leaf's delegation (M§6.2). Acceptance is per conversation and per set of recorder devices.
- **The recorder leg** is an ordinary DSIP session to the declared recorder, carrying RFC 7865-shaped
  `recording_session` metadata and `sendonly` streams. The recording party checks the recorder's identity and
  capability first.

**Spec.**
- `v0.9/dsip-recording-profile-v0.9-draft.md`.
- Core: §15.4 adds `policy.recording-declined`; §16.4 separates the preference from the declaration; §24.2 adds
  `dsip.record` and the recording registries.
- Schemas: `recording` on invite/answer/update, and `recording_session` on invite, with samples.

**Vectors.**
- `recording/` (39): consent traces, recorded conversations, recorder-leg checks.
- `semantic/` (4): the reason token, and declarations with and without a recorder.

**The second implementation's questions, decided and pinned.**
- **Returning to an accepted recorder** while a new one is pending releases the hold. C§4's intent; the README had
  said "nothing more". Vector: return-to-accepted-recorder-releases-hold.
- **A caller's local `answer`** does nothing.
- **Any message type is processed for either role.**
- **The disclosure** holds only `state`, `recorder` and `purpose`.
- **Conversation acceptance** covers every recorder present: a new one asks again, one that leaves asks nothing.
  C§5's "set of recorder devices" wording was aligned with the README's subset test.
- **The recording-session check:**
  - at least one stream, each with an integer `media`;
  - a missing `direction` is not `sendonly`;
  - an unregistered state counts as declared;
  - the six refusal tokens are local results, and the leg is ended with `bye` and `policy.blocked`.

**On the wire (2026-10-05).**
- **New flags:** `dsip call/answer --recorded-by <recorder> [--record-purpose] [--record-later]`, and
  `--recording-accept ask|always|never`.
- **New commands:** `accept-recording`, `decline-recording`, `record on|pause|off`.
- The endpoint signs the declaration into every invite, answer and update.
- The console runs `dsip_recording::Consent`. It never auto-answers before acceptance, and holds the media leg
  (`hold_sending`) while acceptance is pending.
- A local decline may now carry a reason: `state/responder-declines-with-reason` (all three implementations).
- `demos/recording-consent-demo.sh` (in CI) runs four calls:
  - a caller holds all audio (0 frames) until acceptance;
  - a callee will not answer before acceptance, and its decline is `reject policy.recording-declined`;
  - a standing `never` policy declines at once;
  - recording begun mid-call by `update` and declined ends with `bye policy.recording-declined`.

**The recorder leg (2026-10-05).**
- `dsip recorder` is a recorder service. It answers only invites carrying `recording_session` (otherwise `reject
  policy.blocked`), records each stream to Ogg/Opus, and keeps the metadata.
- The recording party's console, with `--record-device <second device>`, forks the call from that device once media
  flows:
  - one `sendonly` recording session per voice;
  - the Opus is forwarded unchanged through taps on the call leg and a `Feed` source;
  - before any media, it runs `dsip_recording::recording_session` with the recorder's verified delegation
    (`peer_has_capability`).
- Supporting changes:
  - `identity init --capability` for extra delegated capabilities;
  - an invite patch for direction and metadata;
  - the answer selection maps an offered `sendonly` to `recvonly` and vice versa (§14.2 subset rule; it used to copy
    the direction).
- **Choices made (Impl), now in C§6:**
  - one recording session per stream (C§6 now says "one or more");
  - `paused` holds the legs' media rather than renegotiating them to `inactive` (C§6 now allows either).
- `demos/recorder-leg-demo.sh` (in CI; forge and webrtc-rs both pass):
  - a call yields two files, one per voice, plus metadata;
  - a counterparty who never accepted contributes 0 frames;
  - a "recorder" without `dsip.record` is refused before any media (`bye policy.blocked`).

**Recorder devices in messaging (2026-10-05).**
- A leaf's delegated capabilities are now part of `LeafIdentity` (`is_recorder`).
- `dsip-msg --recorder` delegates `dsip.record`. It sends no content or receipts, discloses nothing, and archives
  what it receives to `recorder-archive.jsonl`.
- Members run `dsip_recording::conversation` over the authenticated leaves:
  - they render a conversation becoming recorded, or no longer recorded;
  - they refuse to send content or receipts before `accept-recording` (`decline-recording` leaves);
  - they drop anything a recorder leaf sends.
- **Choice made (Impl, now in C§5):** a recorder of a member's own identity needs no acceptance from that member.
- **Choice made (Impl, now in C§5):** a recorder device joins conversations, never its identity's personal group.
  So it gets no archive key and records only what was sent while it was disclosed. Without this, the multi-device
  path would have handed it the whole history, including messages sent before anyone was told.
- `demos/recorder-device-demo.sh` (in CI) covers all of this, including a misbehaving recorder whose message both
  members drop.

**Acceptance across devices (v0.10, 2026-10-06).**
- Acceptance is now the person's, not one device's. The device on which the user accepts sends a
  `recording-acceptance` object (`{conversation, recorders, accepted_at}`) to the identity's personal group. Every
  device of the identity applies the union with its own acceptances (C§5, M§8.1 table).
- Vectors: `messaging/recording-acceptance-*` (3), three-way.
- **The second implementation's agent found a text contradiction.** M§10.5 called the private read watermark "the
  one object exempt" from M§8.1's `conversation` rule, yet the new object names the recorded conversation too. M§10.5
  now names both, and the vectors README states that `sender-mismatch` and `conversation-mismatch` apply to `content`,
  `receipt` and `activity` only, as all three implementations already did.
- `dsip-msg`: `accept-recording` shares the acceptance, and a sibling's acceptance is applied on receipt.
- The recorder-device demo now adds a laptop for Alice. Told of the recording, the laptop can't send until Alice
  accepts on her phone; the acceptance then reaches the laptop through her personal group, and it sends.
- Whether a party's `policy.recording: forbidden` should also be enforced by its relay. It is not: a relay never
  sees media and cannot know.

## 108. M§7.2 / Recording Profile C§5 — every device of an identity in a new conversation; a recorder never stands in

**Found (2026-10-05)** by testing whether conversations created after a recorder device exists pick it up. Neither
direction did:
- **Alice creates a conversation with Bob.** Bob's mailbox happened to hand out his **recorder's** KeyPackage. The
  conversation was Alice plus Bob's recorder; Bob's phone never joined.
- **Bob creates one.** Only his phone and Alice joined, so the conversation was not recorded at all.

**Cause: an implementation bug, not the spec.** M§5.5 has a fetch return one KeyPackage per device, and M§7.2 has the
creator add "its own other devices and the peer's devices in one commit". `dsip-msg` added only the first KeyPackage
it was given, and never its own other devices. A second ordinary device, such as a laptop, missed new conversations
the same way.

**Spec gap (recording-specific).** With every device added, a recorder joins every new conversation of its identity,
as it should. But if only the recorder had KeyPackages left, a conversation could hold the person's recorder without
the person.

**Decided (with the user).** C§5 now says:
- an adder adds a recorder device only together with at least one other device of that identity, unless that
  identity is the adder's own (the person is then present through the adding device);
- otherwise the identity is not added (`recorder-only`);
- the personal group never takes a recorder.

The rule is pinned by `recording/add-devices-*` (9 vectors, three-way parity). The second implementation's agent
found an ambiguity in the first wording (the adder's own identity), and the `self_identity` input settled it.

**Implemented.**
- `CommitOp::Add` carries every selected KeyPackage in one commit.
- `create` adds the peer's devices and the creator's own other devices.
- `add` and the successor re-add take every device of the peer.
- All of these go through `dsip_recording::add_devices`.

**Demo.** `demos/recorder-device-demo.sh` now creates a conversation from each side after the recorder exists:
- both include the recorder, and Alice is told each is recorded;
- 19 messaging demos pass with every-device adds.


## 109. DHT Hints Profile §10 — when a node holding a Pkarr packet looks for a newer one

**Found (2026-10-08, `dsip-node` stage 5, on the WAN).** §10 says a node serves "the Pkarr relay payload" for
`GET /<z32>`, and that serving an older packet is its only power. It does not say when a node holding a packet
should look on Mainline again. `dsip-node` never did. After Bob re-signed, Milan and Tokyo kept serving his first
packet, and once it expired Alice's call through Milan failed with `rejected (expired)`, while Mainline held the new
one. This was conformant, and useless.

**Choices considered.**
1. Leave it to implementations. The cost is honest nodes that look like withholding ones.
2. Re-read Mainline on every `GET`. Always current, but every lookup pays a DHT query: 2.8–3.3 s on the WAN, against
   0.25 s from what is held.
3. Serve a fresh held packet at once and re-read in the background, rate-limited; re-read before serving a packet
   past its TTL (its `ts` plus its shortest record TTL — a node can compute that for any application's packet).

**Implemented: 3** (`Impl:` on `pkarr_get`, `crates/dsip-node/src/lib.rs`). The background re-read runs at most once
a minute per key. Measured (`dht-findings.md`, "dsip-node on the WAN", finding 2): with a 120 s TTL, nodes followed
each re-sign 20–60 s behind and never served an expired packet.

**Proposed text (§10, under `/<z32>`), as first drafted:** "A node holding a packet SHOULD look for a newer one on Mainline before
serving it after its TTL has passed (its `ts` plus its shortest record TTL), and MAY look again while it is fresh. A
held packet is a cache, not a store of record." No vector change: freshness is node behaviour, outside `check:
"store"`.

**Decided (with the user, 2026-10-08): adopted in v0.11.** DHT Hints Profile §10 now says, under `/<z32>`, that a
held packet is a cache: a node SHOULD look for a newer packet on Mainline before serving one past its freshness
(`ts` plus its shortest record TTL), and MAY look while it is fresh without delaying the answer. Core A.8 notes it.
`dsip-node` already does both.

## 110. N§1–N§7 (draft) / G§11 / §19.1 — number-to-DID attestation

**Found (2026-10-08).** G4 recommendation 3 (`gateway-stir-findings.md` §5) and G§11 path (c) need a way for a DSIP
identity to be entitled to a phone number. The design study `impl/docs/number-attestation-design.md` proposed a
STIR-signed binding. It is now the draft Number Attestation Profile (`N§n`), and stage 1 (N§3, the binding and its
checks) is pinned by `impl/vectors/tn-binding/`. The design left five choices open. The user decided on 2026-10-08
to adopt it and start stage 1, with E.164 numbers only. Items B–E take the design's proposals; A was decided with
stage 4 and D with it (below).

**A. G§11 / SHAKEN: may a gateway attest `A` on a carrier's binding?**
- Choices:
  - (a) yes, with the binding standing in for the subscriber relationship;
  - (b) `B`;
  - (c) only under an RFC 9060 delegate certificate for the number.
- **Decided by the user (2026-10-09): (c).** A gateway signs `A` only under a STIR certificate that covers the
  number, normally an RFC 9060 delegate certificate, and signs nothing otherwise. Pinned by `tn-binding/assert-*`
  (stage 4).
  - Not (b): after a binding verified the number against the number authority's signature and the caller's proof of
    possession, `B` ("customer known, number not verified") states something false and discards the evidence.
  - Not (a): "A on a binding alone" has the gateway sign under a certificate that does not cover the number. A
    SHAKEN SP certificate holds only an SPC, so a verifier cannot check coverage, and this profile's own `passport`
    check refuses such an `A` unless the relying party's portability data lists the number. The profile encodes (c)
    structurally.
  - What (c) leaves open is practical, not a policy question: a subscriber crosses only through a gateway that
    already holds a delegate certificate for the number. The DSIP-shaped answer stays inside SHAKEN's machinery:
    a binding, with the subscriber's signed choice of gateway, as grounds for an RFC 9447 TNAuthList authority
    token, so the gateway obtains a short-lived RFC 9060 delegate certificate for the number by ACME (RFC 9448),
    the carrier still the issuer and revocation still its own. That is the stage 5 partner conversation, and the
    argument for it: a binding is a signed, expiring, revocable statement by the number authority with proof of
    possession, where today's letter of authorization is a document.

**B. N§3 / N§7: lifetime, certificate time, conflicts.**
- **Lifetime.** Choices: a 24 h, 7 d or 30 d cap. **Chosen: 7 d**, as `exp − iat` ≤ 604800, giving
  `lifetime-too-long`.
- **Clock skew.** `iat` may be up to 300 s ahead (the §12.9 tolerance), giving `not-yet-valid`. The design had no
  future rule.
- **Certificate time.** The design said "the certificate valid at `iat`". **Changed:** every certificate on the path
  is checked at the verification time, which is RFC 5280's practice. `iat` is the signer's own claim, so checking
  the certificate at `iat` proves nothing a signer could not choose.
- **Two verified bindings for one number.** The two-way rule decides first. When both DIDs claim the number, the
  newer `iat` wins, with the N§5 warning. Not vectored yet; it lands with stage 2.
- **Vectors:**
  - `tn-binding/lifetime-*`, `verified-lifetime-exactly-7-days`;
  - `not-yet-valid`, `verified-iat-at-tolerance`;
  - `cert-leaf-expired`, `cert-anchor-expired`.

**C. N§6: whether a number is discoverable by default.**
- Choices: opt-in, opt-out, or never published keyed by the number.
- **Chosen: opt-in.** Enumeration is a stated limitation, instrumented and not solved, like Sybil resistance
  (§3.2).
- Not vectored. It lands with stage 3, discovery.

**D. §19.1: the trust tier of a verified number.**
- Choices: Tier 1, Tier 3, Tier 4, or deployment policy.
- **Decided by the user (2026-10-09): Tier 3 by default**, domain-bound; a deployment may raise it for issuers its
  trust list vouches for more. Text in N§4 and §19.1.
  - Not Tier 4, although a binding is credential-shaped (a third party's signed statement under a trust list):
    §19.1 lets credential-backed identities bypass spam screening, and that is the one privilege a number must
    never buy. Robocalling is numbers rented in bulk from carriers who attest them honestly, and SHAKEN's
    attestation `A` has not stopped it. What a binding proves is control of a rented, transferable resource, which is
    what a domain proves.
  - Not Tier 1: the number authority and the port history are traceable in a way a self-issued key is not, and a
    self-issued tier would make the profile useless for first contact.
  - Not policy alone: every tier is policy at the privilege end already; refusing to name the evidence class gains
    nothing and leaves implementers to repeat the robocall mistake. The spec names the default; the trust list may
    raise it.
  - Consistent with G§2 (a gateway is Tier 3 toward DSIP callees). A binding never changes the identity's own basis
    line (stage 2), so the tier is a first-contact input and nothing else; the binding's larger value is continuity
    (N§5), which no tier captures.
  - Not vectored: nothing implements tiers; text only.

**E. N§1: short codes and toll-free numbers.**
- **Decided by the user: E.164 only for now.** `tn` matches `^\+[1-9][0-9]{1,14}$`.
- Short codes are not E.164 and are out of scope.
- Toll-free numbers written in E.164 pass the syntax checks. Their issuers (RespOrgs) and their STIR treatment
  are open.

**Decisions the vectors pin that the design did not discuss** (`Impl:` in `crates/dsip-number`):
- **Every TNAuthList on the path must cover the number,** not only the leaf's. A delegate certificate (RFC 9060)
  therefore cannot exceed its issuer's scope. Vectors: `delegate-beyond-issuer-range`,
  `tn-intermediate-list-does-not-cover`.
- **Recognized critical extensions.** Only basicConstraints, keyUsage and TNAuthList; any other critical extension
  is `untrusted-certificate`. SHAKEN's JWTClaimConstraints (RFC 8226 §8) is therefore refused when it is critical,
  until a later stage implements it.
- **An SPC entry covers a number** only through the relying party's SPC lookup (`spc_numbers`): the number
  portability data in SHAKEN.
- **Step 8 status** is a policy switch. `status-unavailable` covers both a missing URL and no answer; that token is
  new against the design.

**F. N§3.2 / README step 2: certificate parsing.** The impl-ts implementation, written from the text alone, probed
it with 41 temporary vectors and found 16 places where the three implementations disagreed. Each was decided and is
pinned with a hand-authored vector.
- **PEM.** Marker lines are whole lines, and lines end in LF or CRLF. A block left open fails the text. Only SP, HT,
  CR and LF are removed from a body. Non-zero unused bits are accepted. Vectors: `cert-pem-*`.
- **Every block parses, even after an anchor.** That means:
  - the tbs `signature` field equals `signatureAlgorithm` (RFC 5280 §4.1.1.2);
  - no extension appears twice (§4.2);
  - there is no pathLen without cA (§4.2.1.9);
  - basicConstraints and keyUsage decode, and any TNAuthList is well-formed.

  Vectors: `cert-duplicate-*`, `cert-pathlen-without-ca`, `cert-tbs-algorithm-differs`,
  `cert-unparseable-after-anchor`.
- **Trust anchors.** An entry that is not padded base64 of a certificate is ignored. Every qualifying issuing
  anchor is tried, in list order. Vectors: `anchor-*`.
- **Status.** A required check fails closed on an answer that is neither `good` nor `revoked` (`status-unknown-answer`).
- **`attested_by`.** A value whose bytes are not UTF-8 is passed over, never shown lossily
  (`attested-by-invalid-utf8-passed-over`).
- **Left unpinned, stated in the README.** Other DER and RFC 5280 encoding faults inside a CA-signed certificate:
  - a BOOLEAN `01`;
  - an encoded DEFAULT;
  - a non-minimal BIT STRING;
  - an empty `extensions` SEQUENCE;
  - GeneralizedTime before 2050;
  - an odd serial number;
  - a PrintableString outside its character set.

  The implementations differ here: `cryptography` and impl-ts are strict, and `x509-parser` is lenient. A CA signed
  those bytes, so leniency never admits an unsigned claim. Pinning them would mean writing a full strict-DER
  validator into every implementation. Vectors and fuzz avoid them. **Proposed text (N§3.2):** "Certificates are DER
  as RFC 5280 requires; a verifier SHOULD refuse one that is not."

**G. Stage 2 (N§4, N§5): the claim and the identity-change warning.** Pinned by `tn-binding/claim-*`,
`tn-binding/contact-*` and `trust/basis-tel-binding-*`. Exact rendered lines are the suite's.
- **A latent `trust` divergence, found and fixed.** Two `tel` claims, the first with no `verifier` (a binding claim)
  and the second a gateway's, were rendered differently:
  - Rust took the first `tel` claim and fell back to the identity's own basis;
  - Python took the first claim with a `verifier`;
  - impl-ts would have printed "undefined".

  **Decided:** the basis comes from the first `tel` claim whose `verifier` is a string, and `tel-caller` needs one
  too.
- **A claim with both a string `verifier` and a `binding`** is a gateway claim. The `claim` check ignores it.
- **A failed binding claim** is shown as `<number> (unverified)` (§18.2), and only when `number` is E.164.
- **The N§5 warning** is said only when no stored contact listing the number has the attested DID. It names the first
  contact that lists it, and dates the binding by its `iat` (UTC).
- **Left open** (client-local data; impl-ts's choices stand, no parity exposure on well-formed input):
  - dates outside the years 0000–9999;
  - malformed address-book entries;
  - an `attested_by` that is neither a string nor `null`.

**H. Stage 3 (N§6 route 1, N§7): discovery.** Pinned by `tn-binding/store-*` and `select-*`.
- **What a node checks.** A node resolves no DIDs, so before it stores a binding it checks steps 1–5 and that the
  path's number is the binding's (`tn-mismatch`). Steps 6–8 are the reader's.
- **The held set.**
  - At most 4 live bindings per number, one per DID.
  - For the same DID, a newer `iat` replaces the held binding. The same text is `same`; anything else is `older`.
  - When the set is full, the smallest `iat` is evicted (on a tie, the greatest text), and only by a newer
    binding.

  **Choices considered:**
  - (a) one binding per number, the newest winning. This lets a misissued binding displace the right one at the
    node.
  - (b) unbounded. Storage is then open to any holder of valid bindings.
  - (c) a small set, which leaves the conflict to the reader, who resolves DIDs. **Chosen: (c).**
- **Reader selection.** Every binding is verified fully, against its own DID. The greatest `iat` wins, and on a
  tie the smallest binding text. `others` lists the other DIDs that verified.
- **No replication between nodes** in this draft. Publishers PUT to several nodes, as with Pkarr relays.
  Overlay replication of bindings is open.
- **Enumeration (item C)** is unchanged. Publishing is opt-in (`dsip tn-publish`), and a node's HTTP rate limit
  applies.

**J. Route 2, the serving half (N§6; v0.12, 2026-10-09).** The number's authority serves its bindings at
`https://<authority>/.well-known/dsip/tn/<tn>`, `200 {"bindings": [...]}` or `404`. A client asks the authorities it
is configured with, pools their answers with route 1's, verifies and chooses as before, and keeps `served_by`: the
authorities whose answer held the chosen binding. Pinned by `tn-binding/authority-*`; `dsip call --tn-authority`;
the discovery demo's simulated carrier (`demos/tn_authority.py`).
- **What is staged:** the log entry (T§6, after KEYTRANS -06). The auditable half of route 2 is Alias Transparency
  stage 2's lookup verification applied to the label `tel:` + `tn`; T§3 now defines that label.
- **Choices considered** for how a client finds the authority: a lookup from number to carrier (number portability
  data, not available to a client), the binding's own `x5u` host (circular: the binding is what is sought), or a
  configured list. **Chosen: a configured list.** The relying party already configures its trust list and SPC data.
- **Pooling, not precedence.** N§6's "order of preference" names the routes; a client that has both a node's and an
  authority's answer pools them and lets N§7 choose, since both are verified the same way.

**I. Stage 4 (N§4.1, N§6.1, G§5, G§7): the gateway.** Pinned by `tn-binding/assert-*`, `passport-*` and `route-*`;
the wire demo is `demos/number-gateway-demo.sh` (two gateways over SIP between a DSIP caller and a DSIP callee).
- **The daemon carries media** (closing the deferrals, 2026-10-09): a forge-webrtc peer connection per call on the
  DSIP leg, SDP in `transports[].sdp`, candidates in signed `info` (§12.12), bridged to the trunk's G.711 RTP once
  both sides are up (§14.1). The demo's calls carry tones and both ends count what they received through two
  gateways. forge creates its event stream when the SDP exchange starts, so the pump that collects candidates and
  inbound Opus is attached after the offer or answer, never before.
- **From the review of the daemon (2026-10-09):** the engine holds one pending SDP, so the gateway's offer or answer
  is given to it right before the event that consumes it (`place_call`, `accept`), never at invite time; a
  retransmitted INVITE (same Call-ID and CSeq) gets its `100` again and nothing else; a re-INVITE (hold, a
  session-timer refresh) is refused `488` with `Reason: DSIP;text="media.unsupported"` and the dialog stands, since
  no mid-call offer crosses in this round; ended calls leave the table; a DSIP `destination` must carry its `+`
  (a local number is declined, never dialled under a guessed country code); the DSIP caller's DTMF `info` reaches
  the controller (G§9).
- **Outbound (`assert`).** The first attested `tel` claim gives the `From`. The gateway signs a SHAKEN PASSporT only
  under its own certificate: chained at `now`, every TNAuthList on the path covering the number, the key the
  leaf's. **Choices considered** for a caller with an attested number the gateway cannot sign for:
  - (a) refuse the call;
  - (b) present the number unsigned and cross downgraded (G§11 path b);
  - (c) sign `B` ("customer known").

  **Chosen: (b).** (c) is what item A rules out: `A` under a covering certificate, or nothing. A caller with no
  attested claim gets the gateway's own `From`: a number nobody proved is never presented.
- **The level is `A`** under an RFC 9060 delegate certificate (item A, decided: path c).
- **The signature is not pinned**, only the signing input (header and claims as decoded objects): ECDSA signatures
  differ between implementations, and RFC 6979 nonces are not something a spec may require of a gateway. Each
  implementation's own round trip (`assert` then `passport`) is tested in its unit tests and in the demo.
- **Inbound (`passport`), RFC 8224 §6.2 made exact.** The order: absent, malformed parameters, unsupported
  `alg`/`ppt` (ignored, §6.2.3), malformed token, `orig` against the `From` (discarded whole, G§5), then with the
  level kept: `dest`, freshness (60 s, §6.2.1), `x5u` against `info`, the path, the signature, coverage.
  - **Coverage is checked for `A` only.** `B` and `C` attest no authority over the number (RFC 8588 §3); a SHAKEN SP
    certificate holds only an SPC, so checking coverage would refuse every honest `B`. For `A`, an SPC entry covers
    through the relying party's `spc_numbers`, as for bindings.
  - **Canonical numbers** (RFC 8224 §8.3): the `+` and the visual separators `-`, `.`, `(`, `)`, SP removed; 1 to 15
    digits remain or nothing matches.
  - **An unsupported `ppt` is `none`,** not a refusal: the gateway renders "no attestation", as for an absent header.
  - **No status step**: a PASSporT has no status URL, and OCSP for STI certificates is out of scope.
- **Routing (`route`).** The operator's table first, then route 1, then `identity.unknown` (404, cause 1).
  **Choices considered:** a verified binding overriding the table (the binding is cryptographic evidence) or the
  table first (the operator's statement about its own trunk). **Chosen: the table first.** An operator that wants
  bindings to win configures no table.
- **From impl-ts, written from the text alone** (second implementation, this stage): a parameter value is everything
  after the first `=`; a trailing `;` is `malformed`; values compare exactly (`alg=es256` is unsupported); an empty
  `info` URI reads and fails `x5u-mismatch`; a SEC1 `EC PRIVATE KEY` PEM is `no-certificate` (the Python reference
  would have read it: fixed). Each is a vector now.

## 111. G§3.1 / invite schema — how a DSIP caller names the PSTN number a gateway should reach

**Found (2026-10-09, Number Attestation stage 4).** G§3.1 has the gateway dial `sip:+1555…@trunk` on a DSIP invite
whose `to` is the gateway's DID, and the invite schema is closed, so nothing in the message says which number. The
round-one daemon took the number from configuration; the stage 4 demo needs the caller to name it.

- Choices:
  - (a) an optional invite member `destination`, a tel URI (`tel:` + E.164), meaningful when `to` is a gateway and
    ignored by any other callee;
  - (b) a `to` that is a gateway-minted DID per number (a DID document per dialled number: absurd at scale);
  - (c) out of band (configuration, as in round one).
- **Chosen: (a)**, as a draft member of the Number Attestation Profile (N§4.1, N§9), in the core invite schema with
  the same precedent as `recording_session` (Recording Profile draft). The core registry (§24) should list it when
  the profile leaves draft. A client asked for `tel:+…` looks the number up first (N§6) and treats only a number no
  binding resolves as a PSTN number; `dsip call --to tel:+… --gateway <did>` does exactly that.
- Pinned by `payload/invite-destination-tel` and `payload/invite-destination-not-tel`.
- **Decided (2026-10-09, closing the deferrals):**
  - `destination` is a `tel:` E.164 URI only in this draft, as the profile's scope is (item E of spec-gap 110). A
    `sip:` target is a different feature, a SIP trunk selector, and would need its own trust story; it is not
    admitted by the schema until asked for.
  - A DSIP invite to a gateway with no `destination`, or one the gateway cannot dial (`bad-destination` in the
    `assert` check), is declined `identity.unknown`: nothing was named that the gateway could reach. No token of
    its own: §15's `identity.unknown` already means "no such party", and the Gateway Profile maps it to 404 on the
    other side. Stated in the README under `assert` rule 2.

## 112. §15 / error schema vs G§7 — `error.detail` is a string, and `gateway.downgraded` carries `{losses}`

**Found (2026-10-09, by the stage 4 wire demo).** G§7 makes `gateway.downgraded` an informational `error` whose
`detail` names each lost guarantee, and the conformance suite (`gateway/downgrade-error-*`) and the clients pin
that detail as the object `{"losses": [...]}`. The core error schema typed `detail` as a string (free text, 13C.3.2),
so a relay refused the first `gateway.downgraded` ever sent on the wire as `schema-invalid`. The error had been
vector-pinned but never sent until a daemon hosted both legs.

- Choices:
  - (a) `detail` is a string or an object a profile defines;
  - (b) G§7's detail becomes a string of tokens, and the vectors and clients change.
- **Chosen: (a)**: `detail` is `anyOf` a string (≤ 1024 characters) and an object (≤ 16 members). The core prose
  should say that a profile may define an object-valued `detail` for a reason token it registers, and §24 should
  list `gateway.downgraded`'s. Pinned by `payload/error-detail-object` and `payload/error-detail-number`.

## 113. §7.4 / §13.2 — how a `did:key` identity hands its relay a revocation

**Found (2026-10-10, by the client's stage 3).** §7.4 (v0.8) says a `did:key` subject's revocations "reach verifiers
only by distribution — to the identity's own services, or presented alongside", and that a service handed one for a
device it has bound "SHOULD end that binding at once". The Messaging Profile defines the carriage to a mailbox
(`mailbox-config.revoked_delegations`, acknowledged). ws/1.0 (§13.2) defines none to a relay: `delegation-revocation`
is a registered type with a schema, but a relay routes by `to`, which the record does not carry, and its signer (a key
of the identity, never the bound device) fails the "signer is the bound device" rule every routed frame meets.

- Choices:
  - (a) the record itself is sent as a frame on a bound connection; the relay recognises the type, requires the signer
    to be the subject, holds the record for every later verification and ends the named device's binding; no
    acknowledgement (an `error` only when it is refused);
  - (b) a relay configuration message like the mailbox's, carrying revocations in an array and acknowledged;
  - (c) the record presented "alongside": a `revocations` array in the protected header of any `hello`, so every relay
    an identity binds to learns it at the next hello of any of its other devices, with no new message flow.
- **Chosen: (a)** in the PoC relay (`dsip-relay`, `State::revoke`), accepted from any bound device: a validly signed
  record can only remove authority, so its source does not matter (§7.4). The client (`impl/web`) sends it and holds it.
  (c) suits identities bound to several relays and adds no flow; the core should pick one and say whether a relay
  acknowledges. Pinned by the client's headless test (`web/test/devices.mjs`: the revoked device is dropped and its next
  hello refused `delegation-revoked`, after a relay-side hold too); no vector yet, because the relay tracker has no
  revocation event, which is the next gap once the carriage is decided.
- **Text:** in v0.12 (§7.4 and §13.2), 2026-10-11.

## 114. §13.2 / B§ — how ICE servers, TURN credentials and hints nodes reach a client

**Found (2026-10-11, by the client's stage 5).** A browser client needs three things no message carries: the ICE
servers for its calls (B§: the binding assumes ICE, and a call across two NATs needs TURN), credentials for a TURN
server (short-lived, so they cannot be static configuration), and the nodes of the hints tier it looks up and
publishes on (DHT Hints Profile §10: "pointing a client at a node is configuration"). The client plan (§12) listed
the first two as an expected gap: whether a relay may advertise ICE servers in its `hello` capabilities.

- Choices:
  - (a) the relay's `hello` capabilities carry `ice_servers` (with credentials minted per hello) and `hints_nodes`;
  - (b) the origin that serves the client carries them beside it: a `config.json` of operator defaults and a `/turn`
    that mints TURN REST API credentials (username `<expiry>:<name>`, password `HMAC-SHA1(secret, username)`, the
    convention coturn implements), both outside the protocol;
  - (c) manual configuration only.
- **Chosen: (b), with (c) as the override** in `dsip-relay` (`--client-config`, `--turn-uri --turn-secret-file`) and
  `impl/web` (Settings → Network shows what is in effect and where it came from; `none` overrides an operator
  default). `hello` is untouched: capabilities describe the relay's own protocol behaviour (§13.2), and a relay is not
  the only origin a client can be served from. (a) would tie credentials to the binding lifetime and give every relay
  an opinion about media, which the core keeps out of signaling. The core could say in §13.2 that a relay MUST NOT be
  needed for ICE configuration, and the binding could cite the TURN REST convention as the way short-lived credentials
  are expected to reach a client. Pinned by `web/test/deploy.mjs` (served defaults in effect, minted credentials verify
  under the secret, a call through the relay another operator's hint names); no vector, because nothing is a message.
- **Text:** in v0.12 (§13.2, WebRTC Media Binding §4, DHT Hints Profile §10), 2026-10-11.

## 115. M§4.1 / M§4.2 — how an identity with no document comes to be served by a mailbox

**Found (2026-10-11, by the client's stage 6).** M§4.1 says a mailbox is a service identity and M§4.2 how an
identity advertises the mailbox that serves it (a document entry, or for `did:key` a `DSIPMailbox` endpoint in its
reachability hint). Nothing says how a mailbox comes to serve an identity: the reference mailbox served one
configured owner, which a `did:key` identity made in a browser can never be ahead of time. The relay has the same
question answered in §13.6 (open, or private to listed identities; spec-gap 100).

- Choices:
  - (a) static configuration only (`--owner`, repeatable);
  - (b) enrolment at first use: an identity whose device binds with a verified `hello` under a delegation carrying
    `dsip.messaging` (M§4.3) is served from its first owner operation (`sync`, `key-packages`, `mailbox-config`),
    bounded by an operator cap; a binding alone enrols nothing (another identity's device binds to fetch
    KeyPackages or deposit a welcome);
  - (c) an operator-issued token presented in the first `mailbox-config`.
- **Chosen: (a) and (b) together** in `dsip-mailbox` (`--owner` repeatable, `--serve-any <n>`). (b) is the relay's
  open mode for mailboxes: the identity is what the delegation proves, the cap is the abuse bound, and what the
  mailbox holds for it is bounded by its quota (spec-gap 99). (c) is deployment and can be added without touching
  the profile. An enrolled identity is served exactly as a configured owner (its own machine, store and quota). The
  profile could say in M§4.1 that a mailbox MAY serve identities that enrol by binding, that enrolment is an owner
  operation and never a binding alone, and that the identity's hint, not its enrolment, says which mailbox it uses
  (see 116). Pinned by `web/test/messaging.mjs` (two browsers enrol at two mailboxes); no vector, because the
  decision is the host's policy, not a message rule.
- **Text:** in v0.12 (M§4.1), 2026-10-11.

## 116. M§4.2 / M§6.5 — which mailbox a hub delivers to for a member that enrolled here but advertises another

**Found (2026-10-11, by the client's stage 6).** A hub fans out to each member's mailbox, selected per M§4.2. The
reference hub short-cut this for identities it served itself (in-process delivery). With enrolment by binding
(115), an identity can be served by the mailbox it first bound to and advertise, in its hint, the one it moved to:
the hub delivered to itself, its own mailbox refused `mailbox.unknown-group`, and the member never received the
welcome. M§4.2 says hints never override a document and a client never moves an established conversation's mailbox
on a hint alone; it does not say what a hub does when its own view (an enrolment) and the member's hint disagree.

- Choices:
  - (a) the hub delivers to every mailbox it believes serves the member (its own and the hinted one);
  - (b) the hub delivers to the mailbox the member advertises — document, else the newest verified hint (§8.3) —
    and to itself only when that resolution names it; the hint is looked up again after a bounded reuse time and at
    once when its own mailbox does not hold the group for the member;
  - (c) enrolment is withdrawn when a newer hint names another mailbox.
- **Chosen: (b)** in `dsip-mailbox` (every fan-out is routed through the resolution, `HINT_REUSE_S` = 60 s, a local
  `mailbox.unknown-group` drops the cached hint). (a) duplicates traffic and stores for a mailbox the member no
  longer syncs; (c) makes a hint change registration state, which §8.1 rule 6 forbids. The profile could add to
  M§6.5 rule 5 that the member's mailbox is resolved per M§4.2 at each delivery attempt, never taken from where the
  member once bound. Pinned by `web/test/messaging.mjs` (Bob binds at mailbox A first, moves to B, and the welcome
  reaches B).
- **Text:** in v0.12 (M§6.5 rule 5), 2026-10-11.

## 117. §10.2 / §19.4 / M§14.2 — `from` on a grant: the identity, or the device acting for it

**Found (2026-10-11, by the client's stage 6).** The core engine (`dsip-endpoint`, the CLI and the browser) sets
`from` to the device DID on every message and the receiver learns the identity from the delegation in the header
(§13.2: a device acts for the identity it is bound as). The messaging console sets `from` to the identity and signs
under the device with the delegation inline. Both verify under §10.2 and §7.4. A mailbox checking a presented grant
(M§14.2: "a live grant from the owner whose `to` is that identity") compared `from` with the owner identity and
refused every grant the core engine had issued — the grantee held a valid grant and could not fetch KeyPackages.

- Choices:
  - (a) `from` MUST be the identity on `introduction` and `grant` (the device signs, the delegation binds);
  - (b) `from` MAY be the device; a verifier takes the granter as the identity the header delegation binds the
    signer to, as it does for `hello`'s `on_behalf_of` and for every session message;
  - (c) grants carry an explicit `granter` field.
- **Chosen: (b)** in `dsip_messaging::verify::grant_credential` (the payload's `from` is replaced by the bound
  identity when it names the signing device). (a) would make the core engine's existing grants invalid and split the
  `from` rule by type; (c) adds a field for what the delegation already proves. §10.2 could state the rule once:
  `from` names the device or the identity, and a receiver that needs the identity takes it from the delegation
  binding, whatever the type. Pinned by the `verify` unit test in `dsip-messaging` and by `web/test/messaging.mjs`
  (a grant issued by the browser's calling engine admits the KeyPackage fetch); a `messaging/` vector for the grant
  check with a device `from` is the next step.
- **Text:** in v0.12 (§10.2), 2026-10-11.

## 118. M§14.2 / M§6.5 — a hub-forwarded welcome re-sent after an outage fails the `origin` freshness bound

**Found (2026-10-11, on the WAN testbed by the client's stage 6).** M§14.2 has the member mailbox verify a
hub-forwarded `welcome` by its `origin` — the adder's signed `handshake` deposit — with `issued_at` within 300 s of
the hub deposit's `issued_at` (spec-gap 46). The hub re-signs the `welcome` deposit at every retry (M§6.5 rule 5,
spec-gap 66: a fresh envelope, since the receiver's replay window and the profile's 60 s lifetime refuse an old
one). When the first delivery fails for longer than 300 s — here a TLS trust problem between two mailboxes for five
minutes — every later retry carries an `origin` too old for the bound and is refused `policy.blocked`, forever:
the member never joins, and the hub keeps retrying. The welcome-retry and hub-outage demos pass because their
outages are shorter than the bound.

- Choices:
  - (a) the hub stops retrying a welcome after 300 s and surfaces the failure to the adder, who re-adds (a new
    commit, a new welcome): the conversation's creation depends on every member mailbox answering within five
    minutes;
  - (b) the bound compares `origin.issued_at` with the welcome's own `seq`-time as the hub recorded it, carried in
    the deposit: a new field that only the hub attests, which the member mailbox cannot verify;
  - (c) the bound is one of age, not skew: `origin.issued_at` MUST NOT be later than the hub deposit's `issued_at`
    plus 300 s (no origin from the future), and MUST be within the pending-group retention
    (`pending_group_ttl`, RECOMMENDED 604,800 s) before it — a welcome is held for that long anyway (M§6.6), so
    an `origin` of the same age proves the same thing: that this adder, under a delegation live when it signed,
    committed the add the welcome belongs to. The replay guarantee the 300 s skew gave (a stale welcome cannot be
    re-presented much later) is already given by the group's registration: a second welcome for a registered
    group is a duplicate (spec-gap 66).
- **Chosen: (c)** (2026-10-11, after PR #137): the M§14.2 text now in the draft; the three runners agree on the
  new vectors `mailbox-welcome-hub-forwarded-origin-{after-outage-accepted, older-than-retention-refused,
  at-retention-bound, at-future-bound, from-the-future-refused}` beside the kept `at-skew-bound` (300 s before:
  accepted); `origin-stale-refused` (301 s before) is gone, since that is exactly the delivery the bound broke.
  Found by `tools/wan/browser-message.mjs`; recorded in `impl/docs/dht-findings.md`.

## 119. M§6.5 rule 5 / M§6.6 — a hub's fan-out queue for a member that has gone has no bound

**Found (2026-10-11, on the WAN testbed by the client's stage 6).** M§6.5 rule 5 has the hub retry an
unacknowledged fan-out before sending later ones, and spec-gap 59 has it re-send every unacknowledged head after a
restart with backoff. Nothing bounds how long. A member whose device is gone for good and whose hint has expired
(`did:key`, no document) is retried once a minute forever: the hub keeps its queue, its welcome and its payloads,
and logs a failed resolution each time. Mailboxes have `mls_retention_s` and `pending_group_ttl` (M§4.4, M§6.6);
the hub has nothing comparable.

- Choices:
  - (a) no bound: a queue lives as long as the group (today);
  - (b) a queue whose head has been unacknowledged for `mls_retention_s` (RECOMMENDED 2,592,000 s, 30 days) is
    dropped, welcome and payloads included; a member that returns later re-joins by external commit from the
    group's GroupInfo (M§6.8), which is what the same bound already means at its mailbox;
  - (c) the hub removes the member from the group (a commit of its own): the hub is an ordering authority, never a
    member, and must not change membership (M§6.10, M§15.3).
- **Recommended: (b)**. (a) is a resource leak an operator sees in the log; (c) crosses the line the profile draws
  for hubs.
- **Implemented (2026-10-12), (b).** Vectors first: `hub-queue-dropped-at-retention`,
  `hub-queue-clock-restarts-on-acknowledgement`, `hub-welcome-dropped-at-retention-member-rejoins` (the `hub-trace`
  row of `impl/vectors/README.md` states the rule, `mls_retention_s` in the context, `dropped {identity, pending,
  welcomes}` emitted). The clock is per member identity: it runs while anything, items or welcome, is queued for it,
  and restarts at every acknowledgement of a head, so a slow mailbox that keeps acknowledging is never dropped. A
  dropped identity stays in the roster and loses its welcome hold; later items are queued for it afresh under the same
  bound. The three machines agree, and `fuzz.py`'s hub traces now advance time; the probes found that `impl-ts`
  judged ephemeral expiry against the starting clock, now the vector `hub-ephemeral-expiry-judged-at-the-hubs-clock`.
  `dsip-mailbox --mls-retention` sets the bound (2,592,000 s by default), and the service advances every hub's clock on
  its retry tick; `demos/hub-retention-demo.sh` shows it on the wire. One case the text should say: an identity whose
  welcome was dropped never joined, so it has no GroupInfo to re-join from and must be added again.
- **Text:** in v0.13 (M§6.5 "How long a queue is kept", M-B), 2026-10-13, with the dropped-welcome case.

## 120. M§6.8 / M§12.3 — when a device decides no sibling will add it

**Found (2026-10-12, by the browser client's round 2C).** M§6.8 lets a device join by external commit "a new device
with no surviving sibling online", and M§12.3 has a sibling add a new device. Neither says how the new device tells
the two apart: it cannot see whether a sibling is online, and a sibling that is online adds it within seconds, while
one that is not may never. M§7.5 settles the same question for successor groups in a sentence ("when a hub counts as
permanently unreachable is the member's decision (this profile sets no timer)"); M§6.8 has no counterpart. Nothing
on the wire depends on the answer: an external join of a device whose sibling then also adds it is two valid
commits, the later of which loses its conflict and is not re-proposed because it is no longer needed (spec-gap 58).

- Choices:
  - (a) say it is the device's decision, as M§7.5 does, with no timer;
  - (b) set a wait (say 30 s after the first sync) before a device that knows of siblings joins on its own;
  - (c) require the user to ask for it.
- **Recommended: (a)**, one sentence in M§6.8. The browser client waits 30 s after binding when it knows of a
  sibling and then joins every group its mailbox holds a GroupInfo for, personal group first (an `Impl:` note in
  `impl/web/app.js`); a device that knows of no sibling creates the personal group at once (M§7.1), as before.
- **Text:** in v0.13 (M§6.8), 2026-10-13.

## 121. C§6 / M§8 / §20.7 — an organisation's call records have no endpoint-side path, and a recording leg cannot carry metadata alone

**Found (2026-10-12, asked how an enterprise collects call detail records for compliance).** DSIP has no central
switch. The records an organisation can collect today come from infrastructure it runs: its relay sees every
session message of the devices bound to it (§10.4, §20.7), its gateway sees PSTN legs, its mailboxes see deposits.
The draft core Appendix D (then `impl/docs/v0.13-cdr-appendix-draft.md`, now in the v0.13 core) describes that. Two things it cannot cover:

- **Calls the organisation's relay never sees.** A device MAY hold connections to several relays (§13.2), a
  roaming device may bind elsewhere, and nothing in the protocol pins a delegated device to its organisation's
  relay. Those calls leave no record anywhere the organisation runs.
- **A disclosed record at the organisation's recorder without media.** The Recording Profile's recorder leg (C§6)
  carries RFC 7865-shaped metadata, but only beside media: "At least one stream is required", and an `invite`
  requires at least one media descriptor (`invite.schema.json`, `media` `minItems: 1`). A party that must log every
  call but record none has no profile path to its recorder.

Choices:

- **(a)** Records at infrastructure only (Appendix D); no change. Coverage depends on deployment policy pinning
  devices to the organisation's relay, which the protocol cannot enforce.
- **(b)** A metadata-only recording session: C§6 allows `streams: []`, and the invite schema admits an empty `media`
  for an invite carrying `recording_session`. Live: the recorder must be online at every call's start, each call
  costs a second session, and `media` loses a core invariant for one profile's sake.
- **(c)** A `call-record` object (M§8.1), sent by the recording party's device after every session it took part in,
  to a direct conversation with the organisation's recorder identity (C§1: a service identity whose devices carry
  `dsip.record`). Store-and-forward through the mailboxes, so a recorder that is down loses nothing; encrypted end to
  end; authenticated by the device's MLS leaf; covering calls on any relay. Shape, mirroring `call-event` (M§13.3) and
  RFC 7865's participants:

  ```json
  {"object": "call-record", "session": "01J…", "direction": "outbound", "peer": "did:web:carol.example",
   "device": "did:key:z6Mk…", "relay": "did:web:relay.acme.example",
   "invited_at": 1790000000, "answered_at": 1790000004, "ended_at": 1790000310,
   "outcome": "answered", "reason": "user.hangup", "ended_by": "remote", "media": ["audio"],
   "recording": {"state": "off"}, "evidence": ["<sha-256 of each signed envelope, hex>"]}
  ```

  `outcome` is `answered`, `missed`, `declined`, `rejected`, `cancelled` or `failed`; `reason` is the token that
  ended it (§15); `evidence` lets a record be checked against the signed envelopes the relay or the peer kept
  (Appendix D.4). The recorder's client verifies the object like any content and renders nothing to anyone.

Disclosure, for (b) and (c): the C§3 declaration covers the sender's **recording**, and the record holds what the
sender's own relay already sees (who, when, how it ended). The recommendation is that metadata records need no
per-call declaration, as SIP CDRs do not, and that the organisation discloses them as a standing policy (its
privacy notice); content recording keeps C§3–C§6 unchanged. A profile that wants a per-call disclosure adds a
`purpose: compliance-metadata` declaration instead.

- **Recommended: (c)**, with (a) as the baseline Appendix D describes. Like all endpoint-side compliance in the
  Recording Profile, it trusts clients the organisation controls (C intro): a modified client can omit records, which
  is why the infrastructure records stay the cross-check. (b) is the smaller text change but the worse protocol: it
  needs the recorder online at call time and weakens a core schema invariant. Not implemented; a `call-record` vector
  set (object shape, the recorder-conversation rule, `evidence` matching) comes first if adopted.
- **Text and implementation:** in v0.13, 2026-10-13, (c) with (a) as the baseline. Core Appendix D (informative) from
  the draft; Recording Profile C§9 (appended after C§8 so nothing is renumbered) defines the record-keeper, one
  record per leg, the outcome order and `evidence`; M§8.1 lists the object; `call-record.schema.json` in the messaging
  set. Vectors first: 16 `messaging/call-record-*` (`check: "object"` with `context.leaf_device`: `sender-mismatch` →
  `recorder-conversation-only` → `call-record-invalid` → kept, never rendered), 17 `recording/call-record-outcome-*`
  and 7 `recording/call-record-evidence-*` (SHA-256 of the frame's bytes as kept; a re-serialised frame does not
  match). The Python harness, `dsip-messaging`/`dsip-recording` and `impl-ts` agree (2,000 vectors); `fuzz.py` gains
  `call-record` and `call-record-outcome`. The browser client sends records (spec-gap 123).

## 122. M§4.1 / M§6.6 — what a device does when its identity moves to another mailbox

**Found (2026-10-12, by the browser client's round 2D).** M§4.1 says "which mailbox an identity uses is what it
advertises (M§4.2), never where it enrolled", so an identity may move: its operator closes, or its old mailbox is
gone for good, which is the case M§7.5 exists for. Nothing says what its devices do on arrival:

- **Registrations.** Hubs resolve a member's mailbox at each fan-out (M§6.5 rule 5, spec-gap 116), so they find the
  new one. But the new mailbox has none of the identity's groups registered, so it refuses their fan-out (M§6.6), and
  it cannot serve a successor's `key-package-fetch` or admit its `welcome` without a grant, since both rest on the
  predecessor being registered for the target (M§7.5, spec-gap 61).
- **Cursors.** A sync cursor is the old mailbox's (M§5.4); the new one does not know it.
- **Answers in flight.** A deposit sent through the old mailbox and not yet answered gets no answer.

Choices:

- **(a)** On its first binding at the new mailbox, a device registers every group it is in with one `mailbox-config`
  (`state: joined`, each group's `hub` and `hub_uri`), syncs from the start (as after `mailbox.cursor-invalid`), and
  re-deposits what it had pending (M§9.3: same bytes, so a duplicate is harmless);
- **(b)** a hand-off between the two mailboxes (an export of registrations and stored items): needs the old one alive,
  which is exactly when it matters least;
- **(c)** treat the move as a new device: re-join every group by external commit (M§6.8) from the new mailbox's
  GroupInfo, which it does not have yet.
- **Recommended: (a)**, a paragraph in M§4.1 or M§6.6. The browser client implements the registration and the fresh
  sync (an `Impl:` note in `dsip-wasm`'s messaging engine), and re-deposits everything pending under fresh
  envelopes: application items from the outbox, a GroupInfo as a new export, a commit as the same MLS bytes, an
  archive record to the new mailbox; a pending `mailbox-config` at the old one is superseded by the registration.
  Pending deposits are kept across a restart too, so a reload does the same (`impl/web/test/messaging-pending.mjs`
  loses the personal group's GroupInfo, then reloads one identity and moves the other). Its outbox for the dead hub's groups then runs M§9.4 as usual, and the
  successor's creator fetches the moved identity's KeyPackages from the new mailbox on the strength of that
  registration (`impl/web/test/messaging-successor.mjs`).
- **Text:** in v0.13 (M§4.1 "Moving to another mailbox", M§5.7 `joined` with a `hub` registers), 2026-10-13.

## 123. C§9 / C§5 — a party cannot open the conversation to its record-keeper

**Found (2026-10-13, building the browser client's call records).** C§9 makes the record-keeper "a service identity
whose devices carry `dsip.record`" and has "the party's devices keep a direct conversation with it (M§7.2)". But C§5
says a device adds a recorder only together with at least one of that identity's other devices, unless that identity
is the adder's own: "If only recorder devices are available, the identity is not added (`recorder-only`)", pinned by
`recording/add-devices-recorder-only`. Every device of a record-keeper is a recorder, so the party's attempt to open
the conversation is always refused, and C§9 does not say who else opens it.

Choices:

- **(a)** The record-keeper opens it: its device creates the direct conversation at its own mailbox and adds every
  device of the party, which C§5 allows (the targets are not recorders). It asks for the party's grant (M§14.2) like
  any first contact. The party's client sends records only to the conversation with the record-keeper its
  organisation names, and holds them until that conversation exists. No rule changes.
- **(b)** An exception in C§5's add rule for the identity the party's organisation names as record-keeper; the party
  opens the conversation. This changes a pinned rule: `add-devices` takes a new input, so new vectors and changes in
  all three implementations.
- **(c)** The record-keeper's devices do not carry `dsip.record`. The conversation is then not recorded in C§5's
  sense, and the party's client stops naming who keeps the records.
- **Decided (the user, 2026-10-13): (a).** Text in v0.13 C§9 ("Who opens the conversation") and A.10. It also says
  that a `call-record` is not content, so a party sends it without the acceptance C§5 asks before content. Two
  vectors pin both directions: `recording/add-devices-party-cannot-add-record-keeper` (refused, `recorder-only`) and
  `recording/add-devices-record-keeper-opens` (the keeper's recorder device adds every device of the party).
- **Implementation (browser client).** The browser sends a record after each leg to the record-keeper named in
  Settings, holding records while no conversation exists. A browser identity can be a record-keeper: its device is
  re-delegated with `dsip.record`, never makes a personal group (C§5), and lists the records it receives. A
  conversation with a recorder of another identity is shown as recorded and takes no content or receipt until the
  user accepts its recorders; the acceptance is sent to the personal group (C§5). Test:
  `impl/web/test/call-records.mjs`.

## 124. T§6 / §8.1 / §19.4 — alias transparency stage 2 without KEYTRANS -06: the DSIP side

**Found (2026-10-13, KEYTRANS -06 still unpublished).** T§6 staged five things for after -06. Four of them are
DSIP's own, and none needs KEYTRANS's proof bytes: how the provider's endpoint keeps aliases from being enumerated,
how an owner authenticates to monitor, how tree heads travel between peers, and what a lookup result counts as. The
draft named them but did not say how. The user chose to do this half now (2026-10-13).

Choices, and what the user decided:

- **Tree-head carriage:** (a) a claim `{"type": "alias-log-head", provider, tree_head, root}` in `identity.claims` of
  `invite` and `introduction`, as N§4's number claims ride; (b) a new optional top-level field, a core schema change;
  (c) an `info` frame, which only works inside a session. **Decided: (a).**
- **Monitor authentication:** (a) an `alias-monitor` message as `Authorization: DSIP` beside the raw KEYTRANS
  request, as `blob-put` (M§5.6); (b) a DSIP envelope whose payload carries the request, which re-wraps KEYTRANS
  bytes, against T§2. **Decided: (a).** Any identity that is or was the alias's value may monitor, so an owner whose
  alias was rebound can still see it.
- **Anti-enumeration:** (a) one `not-found` (404, empty body) for an absent alias, a hidden one and a non-owner's
  monitor request, never a proof of absence, after a rate limit that counts every query; (b) a proof of absence to
  permitted callers, which makes the provider's "permitted" part of the profile. **Decided: (a).**
- **What a lookup counts as:** T§6 already decided the rule (a pending version is not authority, `[KTA]` §7.1). It is
  written as `audited` / `unaudited` (`fork`, `unverifiable`, `pending`) / `not-found`, in that order.

**Text:** v0.14 T§7–T§10, T§6 trimmed to what still waits for -06, A.11. **Schema:** `alias-monitor` in the core set.
**Vectors:** 58 `alias-transparency/` vectors, with `check: "alias-query"`, `"alias-monitor"`, `"alias-head"` and
`"alias-lookup-result"`, plus 5 `payload/alias-monitor-*`, all hand-authored; 2,065 in all. The Python harness,
`dsip-kt` and impl-ts agree. `fuzz.py` gains `alias-query`, `alias-monitor`, `alias-head` (signed heads, then field and
byte mutations) and `alias-lookup`: 6,000 random probes, 0 divergences. A head's `tree_size` above 2^53−1 is
`malformed`, as `configuration-accept` treats durations, so every implementation can return it as a JSON number.

## 125. M§7.3 — "any identity MAY leave (commit removing all its own leaves)" is impossible in MLS

**Found (2026-10-13, adding a way to decline a recorder by leaving, C§5).** M§7.3 says an identity leaves by a
commit removing all its own leaves. RFC 9420 forbids a commit that removes its committer (§12.4), so no device can
leave that way. Nothing else in the profile says how to leave. The browser client had no leave at all; a local
"forget the group" would leave the device's leaf in the group, with every member still encrypting to it.

Choices:

- **(a)** The leaver deposits MLS Remove proposals for all its identity's leaves, and any other member's device
  that receives them commits them; first commit wins at the hub (M§6.5). The leaver re-proposes at each new epoch
  until it is removed.
- **(b)** The leaver sends an application object asking to be removed, and other members commit an ordinary removal.
  Simpler to pin, but the request is content: it can be lost or ignored, and it is not MLS's own mechanism.
- **(c)** Leave it out of 1.0; fix the text only.
- **Decided (the user, 2026-10-13): (a).** Text in v0.14 M§7.3 "Leaving", A.11, M-B. The members' decision is pinned
  by `check: "leave-proposals"` (messaging vectors): `not-a-leave`, `not-own-leaves`, `wait` (only some leaves
  proposed so far), `left` (a device of the leaving identity), `commit`. The hub needed no change of rule: it
  already sequences standalone proposals and orders removals of a whole identity. The mailbox, though, handed every
  handshake to its commit observer, which refused a proposal as an invalid commit; it now stores the proposal in its
  view of the group, so the commit that references it validates.
- **Implementation:** `dsip-messaging` `leave_proposals`, the Python harness and impl-ts agree (14 vectors; fuzz
  target `leave-proposals`). `dsip-mls`'s hub view stores a standalone proposal (`observe_commit` →
  `{proposal: true}`), and `tests/e2e.rs` `leave_on_real_mls` runs the whole path on OpenMLS: two proposals, the hub's
  view across a reload, wait then commit, a sibling's `left`, a whole-identity removal at the hub. The browser
  Messenger has `leave()`, re-proposes at each new epoch, and commits others' leaves; "Leave" and "Decline and leave"
  in the client; `impl/web/test/call-records.mjs` step 10 (Bob declines Kim's recorder by leaving).

## 126. M§7.3 — members "MUST enforce all of M§7.3 themselves", and no member did

**Found (2026-10-13, scoping group conversations in the browser).** M§7.3 makes the hub's roster check defense in
depth: "Members MUST enforce all of M§7.3 themselves." Only the hub enforced it (`dsip-messaging` `hub.rs`, the
`hub-add-*` / `hub-remove-*` vectors). The console (`dsip-msg`) and the browser merged any commit the hub ordered,
so a faulty or hostile hub could have a member add a device to another identity, or cut one of its devices out,
and every member would follow. The text also leaves two things to infer: what exactly a member checks (the hub's
rule is not written as a member check), and what a member does with an ordered commit that fails it.

Choices:

- **What is checked.** (a) The hub's rule, as one check the hub and every member make: an add of a device of
  another member identity is refused; another identity's leaves are removed all together, or each because its
  delegation no longer verifies (M§6.2); the committer's own identity is unconstrained. (b) Also M§14.2
  authorization of each added identity at the member: a member cannot see the grant the adder presented at the
  hub's mailbox, so it is not checkable there.
- **On failure.** (a) The commit is not merged and is surfaced, as an external join failing M§6.8 (spec-gap 62 (4)).
  The member then cannot follow the group past that epoch: a hub that orders a commit its members refuse has forked
  the group, and the members' later recovery is a successor (M§7.5). (b) Merge and warn: the rule would not be
  enforced.
- **Draft choice: (a) and (a).** Pinned by `check: "roster-change"` (messaging vectors, 16): `roster-adds-other-devices`
  before `roster-removes-part-of-identity`, the committer's identity empty when its leaf no longer authenticates.
  The hub now calls the same check, so the rule has one definition. A leaver's proposals committed by another
  member remove a whole identity and pass.
- **Implementation:** `dsip-messaging` `check_roster_change`, the Python harness and impl-ts agree (fuzz target
  `roster-change`). `dsip-mls` `roster_change` describes a staged commit for the check; the console and the browser
  Messenger run it on every commit before merging and drop one that fails (`commit refused: <code>`). Real MLS
  (`dsip-mls` `tests/e2e.rs` `roster_rules_enforced_by_members_on_real_mls`): removing one of Bob's two devices and
  adding a device of Bob's are refused at Alice, removing all of Bob is accepted.

**Fix, transcribed into v0.15 (Appendix A.12).** In M§7.3, after "Members MUST enforce all of M§7.3 themselves": "A member checks each
commit before merging it: no add of a device of another member identity than the committer's, and for each other
identity, the commit removes all of its leaves or only leaves whose delegation no longer verifies. A commit that
fails is not merged (as M§6.8)."

## 127. M§8.5 / M§7.3 — a removed device is never told the group is over, so adding it back fails

**Found (2026-10-13, group conversations in the browser: Alice removes Carol, then adds her back).** M§8.5 and the
pinned resume rule (spec-gap 44) make a welcome for a group the device has joined a duplicate: a redelivered welcome
must not be processed twice. Nothing says what removal does to that. A device whose identity a commit removed kept
the group as "joined" and kept its seq-gap tracking there, so a member adding it back (M§7.3: any member identity
MAY add another) got nowhere: the new welcome was dropped as a duplicate, and once that was fixed, MLS refused it
because the device still stored the old group under the same group id, and then the device held every later item
behind the seq gap of the items sent while it was out.

Choices:

- **(a)** Removal ends the join: the group is no longer joined, so a later welcome for it is a join from its own seq
  (spec-gap 83); the seq positions stay, so items already processed stay duplicates; the device deletes the group's
  MLS state and its gap tracking. **Chosen.**
- **(b)** A re-add must use a successor group (M§7.5) with a new group id. Works with no change, but turns an ordinary
  re-add into the outage machinery and loses the conversation's group id.
- **(c)** Forget the group's positions as well. A redelivery of the old items would then be processed again; MLS can no
  longer decrypt them, so they fail rather than duplicate.

**Draft choice: (a).** Pinned by a new `resume-trace` step `{removed: {group}}` (4 vectors: re-add is a join,
positions kept, survives a restart, other groups untouched); the Python harness, Rust and impl-ts agree; the
`resume` fuzz target draws `removed` steps. The browser Messenger and the console call it when a commit removes their
identity, and drop the group's MLS state and gap tracking with it. Real MLS: `dsip-mls` `tests/e2e.rs`
`readd_after_removal_on_real_mls` (Carol removed, her group state deleted, a new welcome into the same group id joined,
the adder named by the welcome's GroupInfo signer, a message after read). Browser: `impl/web/test/messaging-group.mjs`.

**Also found here (implementation, no spec change):** the mailbox daemon checked a welcome against the first grant in
the deposit's `grants` that verified, not the one from the welcome's recipient; with two identities added in one
commit, the second was refused `policy.first-contact-required`. It now picks the grant whose `from` is the recipient
(M§14.2).

**Fix, transcribed into v0.15 (Appendix A.12).** In M§8.5, after the duplicate rule: "A device whose identity a commit removes from a group
is no longer joined to it: a later welcome for the group is processed as a join. Seq positions are kept."

## 128. M§7.4 — a group cannot move back to a hub it left

**Found (2026-10-14, moving a hub from the browser: Bob hosts Alice's conversation at his mailbox, then Alice moves it
back to hers).** M§7.4 has the old hub refuse "every later deposit for the group with `mailbox.unknown-group`", and
says a hub hosts a group only if `dsip_conversation.hub.did` names it. It never says what happens when the group
names the old hub again. The hub at A still held its state for the group, marked moved, so the committer's handover
`group-info` was refused `mailbox.unknown-group`. Nobody could deposit anywhere: hub B had ordered the move back and
refused the group, and hub A refused it as gone. Moving a conversation to your own mailbox and back is an ordinary
thing for a person to do.

Choices:

- **(a)** The committer's handover `group-info` brings the group back. The GroupInfo names this hub, and its depositor
  is in the GroupInfo's roster. The hub takes the GroupInfo's epoch and roster and numbers on from `handover_seq` + 1.
  It keeps the queues it still holds for the group, which drain as before. A `handover_seq` below the hub's next seq
  would give a seq twice (M§12.2: `(group, seq)` is unique), so it is refused `policy.blocked`. **Chosen.**
- **(b)** Forget the group entirely once it moves away, so that a return is a first bootstrap. This loses the queues
  still draining, and with them the old hub's last items for a slow mailbox (spec-gap 71). It also lets a stale
  `handover_seq` restart the numbering below seqs the hub already gave.
- **(c)** Never: a group that left a hub cannot return, and a move back needs a successor group (M§7.5). This turns an
  ordinary action into the outage machinery and loses the group id.

**Draft choice: (a).** In `hub-trace`, a `group-info` deposit carrying `handover_seq` and `view {epoch, roster}`
(the GroupInfo as the daemon reads it) returns a moved group. Three vectors pin it:

- `hub-move-back-returns-the-group`: the old queues drain first, then the new seqs.
- `hub-move-back-renumbering-refused`: a `handover_seq` below `next_seq` is refused `policy.blocked`, and a group-info
  with no `handover_seq` is still `mailbox.unknown-group`.
- `hub-move-back-by-a-non-member-refused`.

The Python harness, Rust and impl-ts agree, and the `hub` fuzz target starts a third of its traces moved and draws
returns. The mailbox daemon gives the machine the view only when the GroupInfo names it. Browser:
`impl/web/test/messaging-hub-move.mjs`.

**Fix, transcribed into v0.15 (Appendix A.12).** In M§7.4, after "The old hub": "A group may come back to a hub it left. The committer's
`group-info` with `handover_seq`, whose GroupInfo names that hub, returns it: the hub takes the GroupInfo's epoch and
roster, keeps the queues it still holds, and numbers on from `handover_seq` + 1. It refuses a `handover_seq` below a
seq it has already given."

## 129. M§7.4 — a member can reach the new hub before the GroupInfo that sets it up

**Found (2026-10-14, CI on the browser hub-move test, Chromium; one run in two).** M§7.4 bootstraps the new hub from
the committer's `group-info` with `handover_seq`, which the committer sends once the old hub has accepted the move.
Every other member processes the moving commit when the old hub fans it out, and deposits to the new hub from then on.
Nothing orders those two. A member's deposit can reach the new hub first. The new hub does not host the group yet, so
it answers `mailbox.unknown-group`. M§7.4 has a member sync on that refusal and treat it as final unless the sync shows
the group moved. Here it did not move again, so the member gave up: Bob's message, re-sent to the new hub after he had
missed the move, was dropped. A re-proposed commit is lost the same way. The window is a second wide when the old hub
is on the same machine as the new one. Over a WAN, or with a committer that is slow to send its GroupInfo, it is
wider.

Choices:

- **(a)** A member waits for the new hub. From processing the move (or, for the committer, its `accepted`) until the
  new hub accepts a deposit, that hub's `mailbox.unknown-group` means "not set up yet". The member re-sends the same
  deposit with the §13.2 backoff (1 s, doubling, 60 s ceiling; the same bytes, M§9.3) for at most `arrival_wait` from
  the move: 300 s, as the mailbox's `handover_wait`. At or past the bound the refusal is handled as M§7.4 already
  says. A committer that never sets the hub up leaves the group to M§7.5. **Chosen.**
- **(b)** The new hub answers a different reason for a group it does not host yet. It cannot tell such a group from
  one that never existed, so the reason would carry no information.
- **(c)** The committer sets the new hub up before committing. The GroupInfo needs `handover_seq`, which exists only
  once the old hub has ordered the commit.

**Draft choice: (a).** A new vector-pinned machine, `move-arrival-trace` (7 vectors), with events `moved {hub}`,
`answer {hub, reason?}` and `advance`:

- `move-arrival-new-hub-retried-until-it-hosts`: the backoff, `hosted` on an accepted, and a move back (spec-gap 128).
- `move-arrival-wait-expires`: the bound, and `expired` emitted once.
- `move-arrival-backoff-ceiling-and-default-wait`: the 60 s ceiling and the 300 s default.
- `move-arrival-old-hub-is-not-an-arrival`, `move-arrival-other-answers-keep-waiting`,
  `move-arrival-another-move-restarts`, `move-arrival-no-move-no-wait`.

An answer is judged against the hub the deposit was addressed to, not the group's current hub: the old hub's refusal
can arrive after the move was processed. The Python harness, Rust and impl-ts agree, and the `move-arrival` fuzz
target draws moves, answers from three hubs, and time across the bound. `CommitRetry` is unchanged: a deposit the new
hub is waited for never reaches it. The browser Messenger re-sends on its tick (the item's bytes under a fresh
envelope; a commit's same MLS bytes), and the console (`dsip-msg`) waits in `hub_deposit`. Browser:
`impl/web/test/messaging-hub-move.mjs` step 6 holds the mover's GroupInfo, so the other member always arrives first.

**Fix, transcribed into v0.15 (Appendix A.12).** In M§7.4, after "Members then deposit to the new hub, which initializes its state from the
latest `group-info`": "A member can reach the new hub before that `group-info`. Until the new hub accepts one of its
deposits, a member treats the new hub's `mailbox.unknown-group` as not yet set up: it re-sends the same deposit with
the §13.2 backoff, for at most 300 s (RECOMMENDED) from processing the move. Past that, the refusal is handled as
below."

## 130. M§4.1 / M§5.7 / M§15.5 — an enrolled identity can never leave a mailbox, and a full mailbox says nothing

**Found (2026-10-15, while reviewing the browser welcome screen, #168).** Spec-gap 115 let a mailbox serve identities
that enrol by binding, "within a bound the operator sets". Nothing ends an enrolment. An identity cannot say it is
done with a mailbox: M§4.1 "Moving to another mailbox" changes what the identity advertises, and nothing passes to
the old mailbox. The mailbox has no rule for when to stop serving it. So each place in the bound is used once and held
for good, with whatever the mailbox stores for the identity: retained items, KeyPackages, blobs, group registrations,
grants. A browser identity made and thrown away, or one that moved, keeps its place. The testbed's mailboxes (L1, L2,
`--serve-any 32`) had used 11 of their 32 places each on 2026-10-15, almost all of them by test identities.

Once the bound is reached, the next identity's owner operations (`sync`, `key-packages`, `mailbox-config`) are not
refused. The reference mailbox hands them to its drop box, the §19.4 anti-enumeration sink. The device gets an empty
`items` or an `accepted` for something that is never kept. Then its group creation fails, and nothing says why.
M§15.5 already lets a mailbox say `transport.unknown-recipient` for an identity it does not serve. An owner operation
from the identity's own device is not a stranger probing, so there is nothing to hide from it.

Choices:

- **(a) The owner releases its enrolment.** A new `mailbox-config` field, `release: true`, sent by a device of the
  identity. The mailbox answers `accepted`, then deletes everything it holds for the identity (items, KeyPackages,
  blobs, registrations, grants, held introductions), closes the identity's bindings, and frees the place. A configured
  owner (operator-listed) cannot be released this way: the operator listed it, and `release` is refused
  `mailbox.not-enrolled`. A device sends `release` only once the identity advertises another mailbox, or no longer
  uses one. The hubs of its groups then find the new mailbox, or none, at their next delivery (M§6.5 rule 5). A
  release is final: binding again later enrols afresh, with nothing kept.
- **(b) Idle enrolments expire.** An enrolled identity with no *registered device* (M§4.4: no verified `hello` from
  any of its devices within `mls_retention_s`, RECOMMENDED 30 days) MAY be released by the mailbox, with the same
  effects as (a). The bound is the one M§4.4 already uses: past it, every device of the identity has to rejoin its
  groups by external commit (M§6.8) anyway, so the mailbox drops nothing a device could still use. Configured owners
  never expire.
- **(c) A full mailbox refuses, with a reason.** An owner operation from an identity the mailbox does not serve, and
  cannot enrol because the bound is reached, is refused `mailbox.not-served` (new token, `error`). Before the bound is
  reached, enrolment is unchanged (spec-gap 115). M§15.5 gains a line: an owner operation is answered truthfully,
  because only a device delegated by the identity can send one (M§4.3).
- **(d) Leave it to deployment.** The operator raises the bound or clears the state by hand. This is what happens
  today, and it does not scale past a test bed: the operator cannot tell a dead enrolment from a quiet one.

**Draft choice: (a), (b) and (c) together.** (a) is the polite path, (b) collects what nobody releases (a cleared
browser profile can never send (a)), and (c) makes the bound visible instead of silent. (c) uses its own token rather
than `mailbox.quota-exceeded`: no quota is involved, and retrying later only helps once places free up through (a) or
(b).

**Open points for the decision:**

1. Should (b) be MAY (operator policy) or SHOULD? MAY keeps a paid mailbox free to hold a quiet customer.
2. Should a release also send `left` for every registered group (M§5.7) so hubs stop fanning out at once? Or is M§6.5
   rule 5 at the hub's next delivery enough? The draft relies on rule 5 and sends nothing extra.
3. Should a device about to release first check that its identity's hint or document no longer names this mailbox?
   Releasing while still advertised turns every later delivery into `transport.unknown-recipient`. The draft says
   SHOULD.

**Vectors first (when decided).** The release and the expiry are mailbox state transitions, so they are pinned before
any code: `mailbox-config-release-valid` / `-configured-owner-refused` (schema and semantic), and mailbox-machine
traces for: release deletes and frees the place, release of a configured owner refused, expiry after `mls_retention_s`
without a registered device, a `hello` inside the bound keeps the enrolment, an owner operation at a full bound
refused `mailbox.not-served`, and a release freeing a place for the next identity. The bound itself and the enrolment
stay host policy (spec-gap 115). The vectors pin only what a device can observe, plus the deletion.

**Decided (2026-10-15, user: "go with your choices on all three"): (a), (b) and (c), with the three open points as
drafted** — expiry is a MAY; a release sends nothing extra to hubs; a device SHOULD release only once its identity no
longer advertises the mailbox.

**Pinned.** A new vector-pinned machine, `enrolment-trace` (11 vectors), with events `owner_op`, `release`, `hello` and
`advance`: the bound and `mailbox.not-served` at it, enrolment closed, release freeing a place, release of a configured
identity refused `mailbox.not-enrolled`, release of an identity not served refused, idle expiry strictly past
`mls_retention_s`, a `hello` keeping an enrolment alive, an owner operation not counting as a `hello` (found by
impl-ts: the text did not say), expiry being the operator's choice, configured identities never expiring, and the
default retention. Plus `mailbox-config-release-valid` / `-not-boolean-refused` and the two `reason-mailbox-not-*`
semantic vectors. Python, Rust (`dsip_messaging::enrolment`) and impl-ts (written from the spec and the README row
only) agree on all 2,124; the `enrolment` fuzz target drew 5,000 traces with no divergence. `dsip-mailbox` drives the
machine (`--release-idle`; a blob-uploader index so a release deletes the blobs only that identity had), `dsip-msg`
gains `release`, and `demos/mailbox-enrolment-demo.sh` (CI) checks it on the wire. The browser surfaces
`mailbox.not-served`.

**Proposed text, as transcribed** (M§4.1 gained a fuller paragraph, "When an enrolment ends"). M§4.1, after "Whom a mailbox serves": "An enrolled identity's device MAY release the
enrolment with `mailbox-config` `release: true` (M§5.7); the mailbox deletes everything it holds for the identity
and stops serving it. A mailbox MAY release an enrolled identity that has had no registered device (M§4.4) for
`mls_retention_s`. A configured identity is released only by its operator. An owner operation from an identity the
mailbox neither serves nor can enrol is refused `mailbox.not-served`." M§5.7 gains `release`. The M§16 registry
gains `mailbox.not-served` and `mailbox.not-enrolled`. M§15.5 gains the owner-operation line of (c).

**Fix, transcribed into v0.16 (Appendix A.13).** M§4.1 "When an enrolment ends", M§5.7 `release`, M§15.5, M§16.

## 131. §12.7 / §13.3 — a relay is never told when it may forget an attempt, or how long a recipient stays *known*

**Found (2026-10-16, while adding the relay's status page, #176).** The page counts what the relay holds, and two of
those counts only ever grow. The reference relay kept every attempt it forked (legs, outcome, the invite) and every
device and identity that had ever bound, for the life of the process. Live, that is memory proportional to every call
and every browser profile the relay has seen.

The spec half-answers both questions:

- **Attempts.** §12.7 says what the attempt record is for (pre-answer `progress`/`answer`/`reject`, per-leg `cancel`,
  the outcome) and §13.3 (spec-gap 82) says what happens to a session the relay holds no attempt for: it is routed by
  `to`, "as after a restart", and "a relay therefore loses no call signaling by restarting". Nothing says when a relay
  that did not restart may let an attempt go, or that it may at all. A relay that drops one early changes what
  happens to a late `answer`: it is delivered by `to` instead of forwarded, and stale `progress` is no longer screened.
- **Known recipients.** §13.3 (v0.7, from spec-gap 17) defines *known* as "a device has completed a verified `hello` for
  it at that relay within the relay's retention window". It does not say whether the window runs from the `hello` or
  from the end of the binding. Taken literally, a device bound for longer than `offline_retention_s` is unknown the
  moment it disconnects, and the next envelope for it is refused instead of held. The reference relay sidestepped it:
  "ever bound" (the spec-gap 17 PoC choice, never revisited after the v0.7 disposition).

Choices for attempts:

- **(a) Forget once the invite's `expires_at` is more than the replay window (300 s, §10.3) past.** Tempting, because
  an endpoint does not answer an expired invite (§12.9). But a queued call (§12.10) is answered long after its invite
  expired: the reference endpoint signs invites for 30 s and waits up to 1,800 s on a `queued` progress. Rejected.
- **(a′) Forget once more than the T-Queue hard cap (1,800 s, "a core constant", §12.10) passes with nothing for the
  attempt**: no fork, no leg added, no attempt-scoped message from a leg or the initiator. Every pre-answer wait in the
  core (T-Establish, T-Ring ≤ 300 s, T-Queue ≤ 1,800 s) ends within that of the last `progress`, so the record is gone
  only when nothing the record exists for can still come.
- **(b) Forget at the outcome.** Drops the record that screens stale `progress` and forwards a late second `answer`
  (spec-gap 86) while those are still likely.
- **(c) Leave it to the implementation.** Every relay has to make one of these up anyway, and conformance vectors cannot
  pin it.

Choices for *known*:

- **(d) The window runs from the end of the binding.** Known while bound, and for `offline_retention_s` after the last
  device of the identity (or the device itself) unbound; and while anything is held for it, so a held envelope is
  never stranded behind an unknown recipient. Past that it is never-seen again.
- **(e) From the `hello`, literally.** A long-lived binding makes its recipient unknown at the moment it disconnects.
- **(f) Ever bound** (the PoC so far): unbounded, and not what §13.3 says.

**Draft choice: (a′) and (d).** Implemented as an Impl choice pending a decision (#177).

**Decided (2026-10-16, user: "go with your choice on gap 131"): (a′) and (d).** `Relay::forget` (Rust),
`Relay.forget` (Python) and impl-ts run it on every clock advance, after queue expiry, and emit nothing.

**Pinned.** `state/relay-attempt-forgotten-after-the-queue-cap`: a `queued` progress 1,000 s in restarts the count; the
attempt is still held exactly 1,800 s after it (2,800 s after the invite) and forwards the answer; it is gone 1,801 s after
that answer, when a late `answer` is delivered by `to`, not forwarded, and a device binding becomes no leg. `state/relay-known-identity-forgotten-after-retention`: a device bound for twice the retention
stays known after it unbinds; at exactly `offline_retention_s` after that an invite is still queued; once the queue has
expired and the window passed, an invite to the identity and a `bye` to the device are refused
`transport.unknown-recipient`; binding again makes it known again. `state/relay-known-identity-default-retention`: with no
`offline_retention_s` configured the window is the §13.3 RECOMMENDED 86,400 s (impl-ts had applied none; the README now
states the default).

**Proposed text.** §13.3, after the *known* paragraph: "The retention window runs from the end of the recipient's last
binding: an identity or device is known while a device is bound for it, for `offline_retention_s` after its last binding
ended, and while the relay holds an envelope for it. A relay MAY discard an attempt (§12.7) once more than the T-Queue cap (1,800 s) has
passed since it forked the invite, added a leg, or received an attempt-scoped message for it; traffic for the session is
then routed as for a session the relay holds no attempt for."

**Also found, not part of the choice.** The reference relay binary never told the tracker a leg had expired, so it
never sent `transport.no-response` (§12.7 rule 6, a MUST) when every leg rang out. That has to wait for a decision on
*when* a leg expires: an invite's `expires_at` can be shorter than the callee's ring time, and expiring legs at
`expires_at` would end calls that are still ringing.

**Fix, transcribed into v0.16 (Appendix A.13).** §13.3 gains "What a relay forgets", the proposed text above; the core
document's A.13 now lists one core change. The vectors README marks 131 decided; the `Impl:` notes in the three
implementations became `Spec: §13.3` citations.

## 132. §12.7 rule 6 / §12.9 — a relay is never told when a leg has expired

**Found (2026-10-16, while fixing the relay's memory, #177).** §12.7 rule 6 says a relay MUST signal the attempt's
outcome, and spec-gap 76 decided what it sends when every leg expired and none rejected: its own `error`
`transport.no-response`. Rule 3 lists "expired" among a leg's terminal states. Nothing says when a leg expires. The
reference relay's tracker took expiry as an outside event (`leg_expired`), and the relay binary never produced one: it
never sent `transport.no-response`, and the conformance vectors could not notice, because they feed the event in.

The obvious clock is the wrong one. The reference endpoint signs an invite for 30 s; T-Ring-Local runs 120 s by default
(30–300 s). Expiring every outstanding leg at the invite's `expires_at` would end calls that are still ringing.

Choices:

- **(a) A leg that has sent nothing once the invite has expired is expired.** No `progress`, `answer` or `reject` by
  `expires_at` (expired is `expires_at < now`, §12.9). A responder acts only on an unexpired invite, and acts at once:
  it alerts and sends `progress`, or answers, or rejects. So a leg still silent past the expiry never processed the
  invite: a frozen or vanished device. A leg that rang is left alone; it ends itself with `reject user.no-answer` at
  T-Ring-Local, which the relay already forwards as the outcome.
- **(b) Expire every outstanding leg at the invite's expiry.** Simple, and wrong for any ring longer than the invite's
  lifetime (above).
- **(c) A relay timer of its own** (say T-Ring's 300 s upper bound). Adds a constant the spec does not have, and is
  slower than (a) for the case that matters (a dead device) without being more correct for a ringing one.

**Draft choice: (a).** Implemented as an Impl choice pending a decision (#179).

**Decided (2026-10-16, user: "go with your choice on gap 132"): (a).** The tracker expires silent legs on every clock
advance (after queue expiry, before forgetting): attempts in id order, legs in device order, then rule 6 for each attempt
that changed. It applies after an answer too (a silent leg becomes `expired`; nothing is emitted). An attempt forked
without an invite on record (the suite's `{"relay":"invite"}` event) still expires legs only by `leg_expired`. The relay
binary advances its clock every second, without traffic too, and acts on what that emits; the tracker's forwarded
emissions now name their attempt (`Emission::Forward.session`, not part of the vector shape) so an outcome reached on a
tick finds its initiator.

**Pinned.** `state/relay-silent-legs-expire-with-the-invite` (still outstanding at `expires_at`, expired one second
later, `transport.no-response`), `relay-ringing-leg-outlives-the-invite` (the leg that rang outlives the expiry and ends
the attempt with its own `reject user.no-answer`; the silent one beside it expires), `relay-silent-leg-expires-after-an-answer`.
Two older vectors had legs that never spoke past the invite's expiry; they gain the ringing `progress` a real leg sends,
so they keep testing what they were written for (`relay-leg-added-at-the-invites-last-second`,
`relay-attempt-forgotten-after-the-queue-cap`). `demos/relay-no-response-demo.sh` (CI) checks it on the wire: a frozen
callee (SIGSTOP) and the caller ends on `transport.no-response` 31 s after the invite; a ringing callee rings on past 40 s.

**Proposed text.** §12.7 rule 3, after "(answered, rejected, or expired)": "A leg is expired when the invite has expired
(§12.9) and the leg has sent the relay no `progress`, `answer` or `reject` for the attempt; a leg that has is ended by
its own `reject` (T-Ring-Local) or by the initiator."

**Fix, transcribed into v0.16 (Appendix A.13).** §12.7 rule 3 gains the sentence proposed above; A.13 lists it. The
vectors README marks 132 decided; the `Impl:` notes in the three implementations became `Spec: §12.7` citations.

## 133. C§4 / G§3 / G§7 — a gateway is never told what to do with a recording the DSIP side declares

**Found (2026-10-18, dsip-rs stage 2c, moving the gateway onto the call glue).** C§4 binds "a counterparty's client":
it MUST render a declaration that is not `off`, a callee MUST NOT answer before acceptance, and a caller MUST hold its
media until acceptance. A gateway is the DSIP counterparty of every call that crosses it, but the party being recorded
is on the PSTN, behind a trunk that carries no declaration (SIP has SIPREC's `a=record` indication, RFC 7866 §7.1.2,
which few trunks pass). The Gateway Profile says nothing about `recording`: G§3 maps the crossing events, and G§7
names what a crossing loses, with no loss for "the other side records and the PSTN party was not told". The reference
gateway never read `recording`, so it answered and bridged as if nothing were declared. When its calls ran on the
glue, the glue's consent would have held its answer (a DSIP caller declaring recording) or its media (a DSIP callee
declaring it) for an acceptance no one can give.

Choices:

- **(a) The gateway accepts by policy (`always`) and says nothing.** What it did before; the PSTN party is recorded
  without being told.
- **(b) The gateway accepts, and the crossing is downgraded:** a G§7 loss (say `recording-not-disclosed`) in the
  `gateway.downgraded` error, so the recording party knows the disclosure did not cross. Needs a loss token.
- **(c) The gateway passes the declaration on:** SIPREC's `a=record:on` in the SDP toward the trunk (RFC 7866 §7.1.2),
  or an announcement played to the PSTN party before media, and accepts once that is done. Needs trunk support, or
  media the gateway plays.
- **(d) The gateway declines (`policy.recording-declined`)** unless its operator's policy says otherwise. Safe for the
  PSTN party, and breaks every recorded call centre that dials out.

**Draft choice: (b)** as the minimum: the recording party learns that the disclosure stopped at the gateway, in the
same place a crossing reports what else it lost. (c) is the full answer where trunks carry `a=record`. (Stage 2c first
shipped (a), unchanged behaviour, #202.)

**Decided (2026-10-18, user: "go with your choice on gap 133"): (b).** The gateway accepts the declaration on the PSTN
party's behalf (`CallsConfig.recording: AcceptPolicy::Always`) and names the loss `recording-not-disclosed`, last in
the G§7 order: in its outbound downgrade error when the DSIP caller's invite declares recording (fact
`recording_declared`), and in a `gateway.downgraded` of its own, once per call, when a declaration first arrives later
(an inbound call's answer, an `update`). The trust summary renders it as "the PSTN party was not told this call is
recorded".

**Pinned.** `gateway/downgrade-outbound-recording-not-disclosed`, `downgrade-inbound-recording-not-disclosed`,
`downgrade-outbound-recording-after-the-other-losses`, `trust/downgrade-recording-not-disclosed`.
`demos/number-gateway-demo.sh` (CI) cases 4 and 5: a recorded caller dials out and is told; a recorded callee answers a
PSTN call and is told by the far gateway, and its media is bridged.

**Fix, for the next spec version (v0.16 is final).** The proposed text below goes into G§7 and G§3 when v0.17 is
assembled; until then the three implementations cite this gap.

**Proposed text.** G§7, a loss: "`recording-not-disclosed`: the DSIP side declared recording (C§3) and the PSTN side
was not told." G§3 (or C§4): "A gateway is not the recorded party's client. It accepts a declaration on the PSTN
party's behalf only as its operator's policy says, and when the declaration does not cross, the crossing is
downgraded with `recording-not-disclosed`."

## 134. §9.3 / §9.4 — a device's signed presence record has no way to reach the authority

**Found (2026-10-19, reviewing a presence proposal against v0.16).** Spec-gap 19 named two ways an authority can know
presence. v0.7 adopted only the second: the authority asserts presence from its own connection bindings, `available`
when any device of the target is bound and `offline` otherwise. The first way is the subject-signed record of §9.4,
which §9.3 RECOMMENDS whenever the notifier is not the subject. Nothing defines how that record gets to the
authority. No message carries it from a device to the relay, no rule says how long the relay keeps it, and no rule
says what replaces it once it expires. A deployment that follows the RECOMMENDED form therefore can't, so every
implementation (the PoC included) sends only authority-asserted presence. That presence is two states, and the relay
can forge it.

Choices:

- **(a) A `publish` of the record.** A device sends the signed §9.4 record to its relay over its existing binding.
  The relay answers `accepted`, keeps the record until its `expires_at`, and sends it as the `body` of every
  authorized `notify`. A new message type, plus a `dsip-subscription-event` rule for presence.
- **(b) The record in the device's `hello`/binding refresh.** No new message, but presence changes, such as going busy
  in the middle of a binding, then need a re-hello, and the binding and the presence record get a lifetime in common.
- **(c) Leave it to a profile.** The core keeps authority-asserted presence, and a Presence Profile defines the
  publish path.

**Draft choice: (a), defined in a Presence Profile (c)** (`impl/docs/presence-profile-outline.md`, P§3). The core
needs one line in §9.3: "how a subject's record reaches its authority is defined by the Presence Profile; an authority
holding a valid record MUST send it rather than its own assertion." When a record expires the authority falls back to
assertion, so a subscriber always knows which kind of presence it is looking at.

**Decided (2026-10-19, user: "go with your choices on 134–137"): (a), in a Presence Profile.** A device sends its signed record by `publish`; the authority keeps it until `expires_at` and sends it rather than its own assertion, falling back to assertion when no valid record is left.

**Pinned** (2026-10-22, v0.17 draft `v0.17/dsip-presence-profile-v0.17-draft.md` P§3, P§8): `envelope/presence-*` (age bounded by `expires_at`, cap 3,600 s, §12.9), `state/presence-*` (the authority's refusal order, silent acceptance, notify on body change, expiry, T-Presence-Grace, publish interval), `semantic/reason-presence-*`. The outline's `publish` message became the §9.4 `presence` record itself (`publish` is §22's), under `dsip.signaling`, so `presence.not-delegated` is the pipeline's existing `delegation-capability`; refusals use the new `presence` reason category.

**Fix, for the next spec version (v0.16 is final).** §9.3 gains: "How a subject's record reaches its authority is defined by the Presence Profile. An authority holding a valid subject-signed record MUST send it rather than its own assertion." The publish path goes into the Presence Profile draft (P§3) in `v0.17/`.

## 135. §9.4 — an identity with several devices has no single presence record

**Found (2026-10-19, with 134).** §9.4's record has `subject` (the identity) and one `seq`. Presence records "must be
signed by the DID or delegated keys" (§8.1 rule 5), so each device can sign one for the identity. Two
devices then publish records with the same `subject` and unrelated `seq` counters. The receiver rule from §9.3
("discard lower-than-seen `seq`") then drops one device's state whenever the other's counter happens to be higher, so
the laptop going idle can hide the phone's call. The record has no `device` field, so a receiver can't keep the two
apart even if it tried. Combining them would need a signer that speaks for every device. The identity key is that
signer, and §7.3 keeps it off devices.

Choices:

- **(a) Per-device records, combined by the subscriber.** The record gains `device` (the signing device's DID, which
  must match the signer). `seq` is ordered per `(subject, device)`. The authority sends each device's current record,
  and the subscriber's client computes the identity's state with a fixed precedence rule (P§4). No new signer is needed.
- **(b) The authority combines them and signs.** The result is the authority's claim, like today's assertion, so
  the reason for subject-signed presence is gone.
- **(c) One device is the presence primary.** The other devices report to it, and it signs for the identity. That
  needs device-to-device signalling and a choice of primary, and the primary going offline loses everyone's presence.

**Draft choice: (a).** Each device's record carries the device's own signature, the combining rule is deterministic,
so every subscriber computes the same answer, and the authority stays a carrier. A record without `device` (v0.16
form) is treated as one that comes from a single unnamed device.

**Decided (2026-10-19, user: "go with your choices on 134–137"): (a).** Records carry `device` (= the signer), `seq` is ordered per `(subject, device)`, and the subscriber combines the records by the P§4 precedence rule; a record without `device` is one unnamed device.

**Pinned** (2026-10-22, P§4): `presence/aggregate-*` (the combining rule, with its tie-breaks: registered before unknown, code-point order, a record before the assertion), `state/presence-seq-per-device`, `semantic/presence-signer-mismatch`, `envelope/presence-signer-mismatch`.

**Fix, for the next spec version (v0.16 is final).** §9.4's record gains `device`; §9.3's `seq` rule reads "per `(subject, device)`". The combining rule goes into P§4.

## 136. §9.3 / §9.4 — presence `state` has no registry, and "invisible" has no defined wire form

**Found (2026-10-19, with 134).** `state` appears in §9.3 and §9.4 only as examples (`available`, `offline`). It isn't
in the §24.2 registry list, and the schema checks its shape only. Two implementations can't agree on `busy` or `dnd`,
and nothing says what a receiver does with a value it doesn't know. User-facing "invisible" mode also has no defined
form on the wire. If it were a state, it would tell the subscriber the very thing it is meant to hide.

Choices:

- **(a) A `dsip-presence-state` registry** with fallback for unknown tokens, as for reason tokens (§15). Initial values:
  `available`, `busy`, `away`, `dnd`, `offline`. Unknown `state` is rendered as `available` with the token shown raw.
  "Invisible" is not registered: an invisible device publishes `offline`, or nothing.
- **(b) A closed enum.** Contrary to the registry rule every other DSIP state follows, and to CLAUDE.md.
- **(c) Free text.** No interoperability.

**Draft choice: (a).** Registered in the Presence Profile (P§5). The fallback is `available` rather than `offline` so
that a newer state such as `in-meeting` doesn't make a reachable person look unreachable. §9.2's privacy default is
not touched.

**Decided (2026-10-19, user: "go with your choices on 134–137"): (a).** Registry `dsip-presence-state` (`available`, `busy`, `away`, `dnd`, `offline`), open, unknown tokens shown and ranked as `available`; "invisible" is publishing `offline` or nothing.

**Pinned** (2026-10-22, P§5): `payload/presence-*` (the token shape, at most 64 characters), `semantic/presence-unknown-state-fallback` (`effective.state` `available` with warning `presence-state-unknown`), `presence/aggregate-unknown-*`.

**Fix, for the next spec version (v0.16 is final).** §24.2 lists `dsip-presence-state` (Presence Profile P§5, draft); §9.4 says `state` is registry-governed.

## 137. §9.1 — reachability is not required to depend on presence, but nothing forbids it

**Found (2026-10-19, with 134).** §9.1 says "an endpoint can initiate a DSIP session without global public presence"
and lists "no presence" as a valid exposure. That protects the caller. Nothing protects the callee: a relay, mailbox
or gateway may refuse to deliver an `invite` or deposit to an identity that publishes no presence, or route by
presence state (dropping calls to `offline` without trying the binding). In the same way, a refusal whose reason or
timing depends on presence state (`dnd` rejected at once, `offline` after T-Ring) turns calling into the presence
oracle §9.3's anti-enumeration rule closes for `subscribe`.

Choices:

- **(a) A MUST in §9.1:** "No relay, mailbox or other service may require presence publication as a condition of
  delivery or reachability. Delivery decisions use bindings (§13.2), never presence records." The anti-enumeration
  rule of §9.3 is extended to every response sent to a party not authorized for the target's presence: such a
  response MUST NOT vary with presence state.
- **(b) A SHOULD,** leaving enterprise deployments free to gate.
- **(c) Leave it implicit.**

**Draft choice: (a).** An enterprise that wants presence-gated routing can do it in its own clients, for its own
identities, which the MUST doesn't reach. A rejection a callee's client sends is its user's choice and is not
covered. What the MUST covers is a service deciding on the callee's behalf from presence.

**Decided (2026-10-19, user: "go with your choices on 134–137"): (a).** No service may require presence publication as a condition of delivery or reachability, and responses to a party not authorized for the target's presence MUST NOT vary with its presence state. A callee's own client rejecting is not covered.

**Pinned.** Not yet: the vectors in `impl/docs/presence-profile-outline.md` P§2 come first (rule 1), then Rust and `impl-ts`.

**Fix, for the next spec version (v0.16 is final).** §9.1 gains: "No relay, mailbox or other service may require presence publication as a condition of delivery or reachability; delivery decisions use bindings (§13.2), never presence records." §9.3's anti-enumeration paragraph gains: "This extends to every response to a party not authorized for the target's presence: it MUST NOT vary, in reason or timing, with the target's presence state."

## 138. M§5.4 / M§8.5 — an item that can never be processed: acknowledged or not

**Found (2026-10-20, dsip-rs stage 3i-3).** M§5.4 lets a device acknowledge what it has "durably processed", and
spec-gap 44 made the MLS effect and the delivery state commit together. Neither says what happens to an item whose
processing fails: a handshake or application message that does not decrypt or validate, or a welcome that cannot be
joined. Such an item fails again on every redelivery. The two clients differed. dsip-msg rolled back and recorded the
item as handled, so it was acknowledged and its seq counted as processed. The browser did neither, but its cursor
moved past the item with the next one that was processed, so unless the item came last it was acknowledged anyway, without its seq
being recorded and without its partial MLS writes being undone.

Choices:

- **(a) Roll back, then commit as handled:** the device MUST NOT keep any MLS state change from a failed item, and
  SHOULD then record it as processed (cursor and seq) so it is acknowledged and later copies collapse as duplicates
  (M§8.5). In `queue` mode the mailbox may then delete it, as for any processed item.
- **(b) Roll back, never acknowledge:** the item stays at the mailbox until it expires. In `queue` mode, a cursor
  that cannot pass it holds back the acknowledgement of everything after it, so the mailbox keeps every later item.
- **(c) Leave it to the device.**

**Draft choice: (a).** The failure is permanent: it does not depend on time or on later items. An item behind a seq
gap is the only case processing might later succeed, and M§6.5 already holds those (spec-gap 69). A device that wants
to keep the bytes for diagnosis can do so locally. (b) costs storage at the mailbox for nothing. The rollback is
spec-gap 44's rule applied to the failure path: without it, an MLS group may keep a partial change the device's
delivery state never recorded.

**Decided (2026-10-20, user: "138 (a)"): (a).** A failed item leaves no MLS change; the device SHOULD then treat it
as processed, so it is acknowledged and later copies are duplicates.

**Pinned.** Not by a vector: the rule is about a device's local state, which the vector harness does not model.
`dsip-messaging-device`'s `Inbound::commit_processed` implements (a) behind `Config::roll_back_unprocessable`
(dsip-msg on; the browser keeps its old behaviour until the option is turned on with a web test), and
`tests/inbound.rs` covers both settings.

**Fix, transcribed into v0.17 (M§5.4, Appendix M-B; 2026-10-26).** M§5.4 gains, after the `ack_through` rule: "An item
whose processing fails leaves no change to the device's MLS state. Since that failure recurs on redelivery, the device
SHOULD then treat the item as processed: it advances its cursor and seq positions past it, and later copies are
duplicates (M§8.5)."

## 139. M§7.5 — the roster recorded for the successor checks: does a lapsed leaf's identity count?

**Found (2026-10-21, dsip-rs: the last `Config` options).** M§7.5 has a receiving device check that a successor group
adds nobody outside "the predecessor's last roster", and spec-gap 61 made that "the roster the checking device last
processed". The roster is by identity, and M§6.2 says the identity a leaf belongs to is its delegation's `subject`. It
does not say whether a leaf whose delegation no longer verifies (expired, or its subject's key rotated as compromised
or lost) still counts. Such a leaf is common: a phone offline for longer than its delegation lasts. The two clients
differed. dsip-msg recorded no roster while any leaf failed to authenticate, so the recorded one went stale and could
refuse a successor that re-adds someone added since. The browser recorded only the identities of leaves that
authenticate, so a member whose only leaf had lapsed dropped out of it, and a valid successor re-adding them was
treated as first contact.

Choices:

- **(a) Only leaves that authenticate now.** A lapsed member drops out of the roster, and out of every successor.
- **(b) Nothing while any leaf fails.** The roster stays as it was before the lapse; it misses changes made since.
- **(c) Every leaf's delegation subject, live or not.** A leaf was authenticated when it entered (M§6.2), and only a
  commit ends a membership (M§7.3 lets any member remove a lapsed leaf, which is that commit).

**Draft choice: (c).** Membership is a commit's to change; a delegation lapsing changes what a leaf may say (M§6.2: its
content is unauthenticated), not who is in the group. (a) lets the clock remove members from successors; (b) loses
changes that were made properly. The successor's creator uses the same roster for whom it re-adds, so it adds nobody a
checker would refuse.

**Decided (2026-10-21, user: "go with all three recommendations"): (c).**

**Pinned.** Not by a vector: `successor-check` takes `predecessor_roster` as input, and which roster a device records
is its local state. `dsip-messaging-device`'s `commits::roster` (over `dsip_mls::leaf_subject`) implements (c) for both
clients, the recorded roster and the successor's re-adds alike; `tests/commits.rs` covers a lapsed leaf.

**Fix, transcribed into v0.17 (M§7.5, Appendix M-B; 2026-10-26).** M§7.5 spec-gap 61 "The check", after "the roster the
checking device last processed", adds: "by identity: the `subject` of every leaf's delegation, whether or not that
delegation is still live (M§6.2). A lapsed leaf stays in the roster until a commit removes it."

## 140. M§12.1 — an `archive-key` under an `akid` already held, with another key

**Found (2026-10-21, dsip-rs: the last `Config` options).** M§12.1 has devices keep every archive key by `akid`, a
ULID, but does not say what a device does when an `archive-key` arrives naming an `akid` it already holds with a
different `key`. Only the identity's own devices send to the personal group, so this happens only through a bug or a
compromised device. dsip-msg replaced the held key; the browser kept the first.

Choices:

- **(a) Keep the first, ignore the other, and surface it.**
- **(b) Replace it with the newer.**
- **(c) Keep both and try each when opening an archive record.**

**Draft choice: (a).** An `akid` names one key: archive records already sealed under it were sealed with the first, so
replacing it makes them unreadable to this device (b). (c) makes an `akid` ambiguous for every reader. A compromised
sibling gains nothing from (a) it does not already have, since it can read the archive anyway; surfacing the conflict is
what tells the person.

**Decided (2026-10-21, user: "go with all three recommendations"): (a).**

**Pinned.** Not by a vector: archive keys are a device's local state. `dsip-messaging-device`'s `archive::take_key`
implements (a) for both clients, and the `Messenger` reports the conflict as `{ui: dropped}`; `tests/history.rs` covers
it.

**Fix, transcribed into v0.17 (M§12.1, Appendix M-B; 2026-10-26).** M§12.1 gains, after "Devices keep all prior keys": "An
`archive-key` naming an `akid` the device already holds with a different `key` is ignored: the first key under an
`akid` stays, so archive already sealed under it stays readable. The device SHOULD surface the conflict."

## 141. §12.9 — the `expires_at` boundary, and id deduplication for records kept past the replay window

**Found (2026-10-22, the Presence Profile vectors; the independent TypeScript reading).** Two inconsistencies, older
than presence, that presence makes visible:

1. **The boundary.** §12.9's exceptions for `introduction`, `reachability-hint` and now `presence` say a record is
   accepted "while … `now < expires_at`", so at `now == expires_at` it is expired. The pipeline (all three
   implementations, and the vectors README `expired` row) rejects only when `expires_at < now`, so it accepts at
   equality. P§3/P§4 (a record is valid while `expires_at` is after now; the authority drops it when `expires_at` ≤
   now) use the strict reading. The envelope pipeline therefore accepts a presence record that the authority drops at
   its next `advance`. No vector sits on the boundary.
2. **Id deduplication.** §12.9 says a `reachability-hint`'s `id` "is not deduplicated", and the `presence` exception
   says `seq` decides a re-observed record. Stage 10 (`duplicate-id`) still runs for every type in all three
   implementations whenever the id is in `context.seen_ids`. A subscriber that verifies each record carried in
   successive `notify` bodies, with ordinary replay tracking, would reject the second sight of the same record.

Choices:

- **(a) Strict everywhere, and no id dedup for records kept past the window:** `expired` when `now ≥ expires_at`
  (README row and pipeline change; a boundary vector per type), and stage 10 skipped for `reachability-hint` and
  `presence` (their `seq` decides).
- **(b) Keep the pipeline as it is and fix the text:** "while `now ≤ expires_at`", and say stage 10 applies to every
  type; P§3/P§4 move to the same inclusive bound.
- **(c) Split:** (a) for the boundary, (b) for dedup.

**Draft choice: (a).** An `expires_at` is the first instant a record is no longer good (as for the authority's drop
and P§4), and the text has said so since v0.8; the pipeline is the outlier. A record that is forwarded many times by
design must not trip replay tracking, which the hint text already says.

**Decided (2026-10-22, user: "141 (a)"): (a).** Applied wherever an `expires_at` is judged, not only at stage 9, so one
reading holds throughout: v0.17 §12.9 gains an **Expiry** paragraph (valid while `now < expires_at`, expired when
`now ≥ expires_at`), the invite row says "at or after", and the `presence` exception says its id is not deduplicated.

**Pinned.** Stage 9 `expired` at `expires_at ≤ now`, stage 10 skipped for `reachability-hint` and `presence` (vectors
README rows). New vectors: `envelope/invite-at-expiry`, `envelope/invite-one-second-before-expiry`,
`envelope/introduction-held-at-expiry`, `envelope/presence-at-expiry`, `envelope/presence-id-already-seen`,
`dht/hint-at-expiry`, `dht/hint-one-second-before-expiry`, `dht/existing-at-expiry-ignored` (§8.3's existing record),
`dht/hint-id-already-seen`, `state/invite-at-expiry-before-alerting`, `state/invite-alerting-a-second-before-expiry`,
`messaging/hub-ephemeral-at-expiry-dropped`, `messaging/mailbox-ephemeral-dropped-at-expiry`. Four vectors that pinned
the inclusive reading were re-authored to the exclusive one, each still showing both sides of the edge:
`state/relay-silent-legs-expire-with-the-invite` and `state/relay-leg-added-at-the-invites-last-second` (spec-gap 132
had taken its boundary from the pipeline row), `messaging/client-activity-shown-until-expiry` (M§11.2) and
`messaging/mailbox-introduction-dropped-at-expiry` (§19.4).

## 142. §9.4 / P§3 — the profile a `presence` record names in `dsip.profiles`

**Found (2026-10-22, the presence clients).** §11.2 has a receiver reject a payload with `session.unsupported-profile-version`
when none of the `profiles` it names is one the receiver supports. The §9.4 example record names
`interactive-media/1.0`; P§ calls itself `presence/0.1` but never says a record names it. The first record the CLI sent
named `presence/0.1`, and the relay, which implements P§3 but listed only the two 1.0 profiles, refused it.

Choices:

- **(a) A record names `presence/0.1`,** and an authority or subscriber that implements P§ lists it among its supported
  profiles; the §9.4 example changes to it.
- **(b) A record names no profile** (`profiles: []`, which §11.2 accepts); presence stays a core message whose processing
  P§ describes.
- **(c) A record names `interactive-media/1.0`,** as the example does.

**Draft choice: (a).** The profile is what tells a receiver how to process the record (P§3's authority rules, P§4's
combining); a receiver that does not implement it refusing the record is correct, and (c) would claim a profile the
record has nothing to do with.

**Decided (2026-10-22, user: "142 (a)"): (a).** v0.17 §9.4: the example names `presence/0.1`, and the text says a
record names it and a processor of records lists it as supported (§11.2); P§3 says the same; A.14 entry.

**Implemented.** `dsip_broadcast::presence::PROFILE` = `presence/0.1` in every record the clients send;
`Supported::all_known()` lists it, so the relay and the endpoints accept it. No vector depends on it (vectors pin
negotiation with explicit contexts).

## 143. §9.3 — how a subscriber reaches the target's authority

**Found (2026-10-22, the presence clients).** §9.3: `to` is "the authority answering for the target (the target's relay
or domain endpoint per its DID document)". Two things are unsaid:

1. **A `did:key` target has no DID document,** so its relay is known only from its reachability hint (§8.3), which is
   not authoritative (§8.1). A hint-located authority is fine for presence records, which the subscriber verifies itself
   (P§3), but its own assertion (§9.3) is then a claim from a relay the target only says it uses.
2. **A relay routes frames from connections that bound to it** (§13.2). A subscriber bound elsewhere has to bind at the
   target's relay to send the `subscribe` and to receive the notifies. That binding also makes the subscriber reachable
   through that relay, and an authority that counts bound devices sees it.

Choices:

- **(a) The subscriber binds at the target's relay,** found through the target's DID document or, failing one, its
  hint; the text says so, and that the binding has the same effects as any other (§13.2).
- **(b) A relay forwards a `subscribe` for a target it does not serve to the target's relay, and the notifies back,**
  relay to relay; nothing in the core defines relay-to-relay forwarding yet.
- **(c) Only identities with a DID document can be watched** across relays.

**Draft choice: (a).** It is what an introduction already does (§19.4, the browser opens a connection to the relay the
target's hint names) and needs no new machinery; records are verified end to end whatever relay carries them.

**Decided (2026-10-22, user: "143 (a)"): (a).** v0.17 §9.3's `to` bullet: the subscriber binds at the target's
authority, the relay or endpoint its DID document names or, without one, the one its hint names; a hint-located
authority's assertion is hint-sourced, the records it carries are verified end to end; the binding has the effects of
any other. A.14 entry.

**Implemented.** The browser subscribes at its own relay, or, when the contact's hint names another, over its one
connection to that relay (`peerRelay` in `impl/web/app.js`), shared with the calls and introductions routed there: a
second binding of the device would replace the first, and the two would keep replacing each other. The CLI subscribes
at the relay it is given.

## 144. §9.2 / §9.3 / P§6 — who may watch: the subject's policy, and how its authority learns it

**Found (2026-10-23, drafting P§6; the WAN presence check).** §9.2: "DSIP clients default to private presence." §9.3
makes authorization the authority's policy decision, but no message lets a subject tell its authority that policy,
so an authority has only local configuration. The PoC relay has none: with no policy for a target, every
`subscribe` is admitted (`Authority::authorized`, the `None` arm), so anyone who knows a DID can watch it. Before
#236 that showed only the relay's assertion (bound or not); since #236 it also shows the records a user publishes from
the browser picker. The deployed L1/L2 relays behave this way now. Private-by-default is not yet implementable, since
nothing tells the authority who is allowed.

§19.4 already has the consent receipt this needs: a `grant` whose `scope` may include `dsip.subscribe` (already
registered, used by nothing yet), signed by the target's device, held by the grantee, with `valid_until`.

Choices:

- **(a) A grant admits a subscriber.** A `subscribe` for presence is admitted when the subscriber's identity holds a
  live grant from the target whose `scope` includes `dsip.subscribe`. The subscriber presents the signed grant
  envelope in `claims` (an entry `{"type": "dsip-grant", "grant": <envelope>}`); the authority verifies it against the
  target's identity (signature, delegation, `to` is the subscriber's identity, `valid_until` after now) and does not
  need to have seen it before. With no admitting grant and no other policy, the answer is the uniform
  `policy.blocked`. An authority MAY also admit by local policy (an organisation's directory, `public` for a
  broadcaster); a client that grants contact includes `dsip.subscribe` unless the user said otherwise.
- **(b) A new signed `presence-policy` message** from a subject's device to its authority, listing who may watch
  (and, with 145, in which audience). The authority keeps it per identity.
- **(c) Local configuration only,** as today; the text says that an authority with no policy for a target MUST refuse.

**Draft choice: (a).** It is private by default with no new message, it reuses consent the user already gives (the
grant), it works when the subscriber's relay never saw the grant (the grantee presents it), and a presented grant
cannot be forged by the authority or another subscriber. (b) would duplicate the grant list at the authority and
need its own revocation. Separately from the choice: (c)'s MUST-refuse rule is needed under any choice, so a relay
with no policy and no grant never serves presence publicly by accident.

**Interim (not a spec choice):** until this is decided and implemented, the PoC relay could refuse presence
subscriptions for targets with no policy, except for the subscriber's own identity (its other devices). The browser
contact badges would then show nothing for contacts, which would also make the WAN presence check fail.

**Decided (2026-10-23, user: "144 (a)"): (a).** v0.17 §9.3 gains "Presence is private by default": a grant from the
target with `dsip.subscribe`, presented in `claims` as `{"type": "dsip-grant", "grant": <envelope>}`, admits; an
authority with no policy and no admitting grant or capability refuses, except the target's own devices. P§6 gives the
admission order: own devices, a grant, a capability, the authority's policy. A presented grant is verified as the
mailbox already verifies one (M§14.2): signature and delegation now, not its delivery window (`dsip_core::grant`).

**Pinned.** `state/presence-private-by-default`, `-grant-admits`, `-grant-not-admitting`, `-first-admitting-grant`,
`-policy-admits-with-its-audience`, `payload/subscribe-with-grant-claim-valid`.

**Implemented.** The authority in all three implementations; the relay verifies presented grants and has
`--presence-public DID` for its own policy; the CLI and the browser present held grants when watching and grant
`dsip.subscribe` with contact; the interim stopgap was not needed.

## 145. P§6 — audiences: what a record is for and who sees it

**Found (2026-10-23, drafting P§6).** P§6 sketches one record per audience, named by `audience` (in the §9.4 schema
since v0.17, unconstrained), and "the authority sends each subscriber only the records for that subscriber's
audience". Unsaid: what an audience token is, how the authority puts a subscriber in one, what a record without
`audience` means, and how P§3's per-device rules (`seq`, `presence.stale`, the 5 s interval) apply when one device
publishes several records at once.

Choices:

- **(a) Audiences are named in the grant.** A grant with `dsip.subscribe` MAY carry `presence_audience`, a token
  (`[a-z][a-z0-9-]*`, at most 64 characters) that the subject chooses (`family`, `work`, …). A subscriber admitted by a
  grant sees the records whose `audience` equals its grant's `presence_audience`, and the records with no
  `audience`. A subscriber admitted by local policy sees only records with no `audience`, unless the policy names an
  audience. A record's `seq`, staleness and publish interval are per `(subject, device, audience)` (no `audience`
  counts as one audience of its own).
- **(b) Three fixed audiences** equal to the detail levels (`basic`, `standard`, `detailed`); the grant says which
  level.
- **(c) One audience per subject:** no `audience` field; a reduced view is out of scope for 0.1.

**Draft choice: (a).** The subject chooses who sees what, the grant already identifies who, and the authority only
compares two tokens. A record with no `audience` stays the default view, so a client that never uses audiences works
as now. Making the rules per `(subject, device, audience)` lets a device publish its `family` and `work` records
together without tripping its own rate limit or `seq`.

**Detail levels** (P§6's `basic`/`standard`/`detailed`, the `activity` registry and `note`). **Draft:** not in 0.1.
Audiences already let a device publish a coarser state to some people (for example `available` to `work` while
`family` sees `busy`). New fields can come in a later version without changing the audience rule.

**Decided (2026-10-23, user: "145 (a)"): (a).** P§6 Audiences; §19.4 `presence_audience`; the record's `audience` is a
token (schema pattern). Detail levels are out of 0.1 (P§1, P§6 Detail).

**Pinned.** `state/presence-audiences`, `-seq-and-interval-per-audience`, `-expiry-per-audience`,
`-grace-drops-every-audience`, `payload/presence-audience-*`, `payload/grant-presence-audience-*`. The clients do not
publish per-audience records yet.

## 146. P§4 / P§6 — a device with no record for a subscriber's audience (P§11 question 3)

**Found (2026-10-23, drafting P§6).** Under 145, a subscriber sees some of a device's records and not others. When a
device has records for other audiences but none this subscriber may see, P§4 has two readings: the device counts in
the authority's assertion (it has "no record" for this subscriber), or it is left out.

Choices:

- **(a) It counts in the assertion, per subscriber.** The body's assertion `S` is computed over the subject's devices
  that hold no record *visible to this subscriber*. The body therefore differs between subscribers, and each
  subscription is notified when its own body changes.
- **(b) It is left out:** a device with any record is never asserted, whoever is watching.
- **(c) The authority sends nothing for that device and no assertion at all** to subscribers outside every audience
  it publishes to.

**Draft choice: (a).** It gives the same answer as P§4 already gives for a device that publishes nothing: bound means
`available (relay says)`. It also keeps P§2.2: under (b), a subscriber shown `offline` while the subject is bound learns
that the device publishes to some other audience, which is a presence oracle in a small way. Under (a), what a
subscriber sees depends only on what it may see.

**Decided (2026-10-23, user: "146 (a)"): (a).** P§6 "The body per subscription". **Pinned:**
`state/presence-assertion-per-subscription`.

## 147. P§7 / §19.4 — time-boxed shares, and ending a share early

**Found (2026-10-23, drafting P§7).** P§7 sketches a share as an authority-issued `capability` token for one
subscriber and an audience, with an expiry. That needs a way for the subject to ask its authority to mint one, which
does not exist. Under 144 (a) a share is simply a grant with `dsip.subscribe` and a short `valid_until`. What is still
missing is how a share ends: when `valid_until` passes during a subscription, and when the subject withdraws it
early. §19.4 calls revocation "local policy at the granting side, optionally propagated as a signed revocation"
without defining one.

Choices:

- **(a) A share is a grant; the authority enforces `valid_until` on live subscriptions; early withdrawal is a new
  signed `grant-revocation`** (`grant`: the grant's id, `grantee`: its identity) that a device of the subject sends to
  its authority. The authority keeps it until the grant's `valid_until`. A subscription admitted by a grant that
  expires or is revoked gets a `terminated` notify with reason `policy.terminated`, and a later `subscribe` presenting
  that grant gets `policy.blocked`. The revocation also binds the subject's relay for invites (§19.4).
- **(b) The same, but early withdrawal is local only:** the subject's device tells nothing to the authority, and a
  share ends only at `valid_until` (short shares make that acceptable).
- **(c) The capability-token design as sketched,** with a new subject→authority request to mint tokens.

**Draft choice: (a).** Ending a share early is the reason to have a share at all ("stop showing my presence to this
person"). (a) does it with one small message that also fills the gap §19.4 has left open for invites. Expiry is
enforced where the subscription lives, so the subscriber's client does not have to cooperate. Revocation stops
future notifies only; what was already shown stays shown, as P§7 says.

**Decided (2026-10-23, user: "147 (a)"): (a).** P§7 rewritten; §19.4 defines `grant-revocation` (new core message,
schema `grant-revocation.schema.json`), kept by the authority until the grant's `valid_until`; `grantee` is
informative (the match is by grant id and the revoking identity).

**Pinned.** `state/presence-share-ends-at-valid-until`, `-lapse-before-share-end`, `-revocation-ends-subscriptions`,
`-revocation-by-another-identity`, `-revoked-before-subscribe`, `payload/grant-revocation-*`,
`envelope/grant-revocation-accepted`.

**Implemented.** The browser revokes the grants it issued when a contact is removed; the CLI console's `revoke` sends
the revocation to the relay.

## 148. P§11 question 4 — presence in messaging groups

**Found (2026-10-23, drafting P§6).** M§11 activity already travels inside a conversation's MLS group, encrypted to
its members. P§11 asks whether a member's presence should also travel there.

Choices:

- **(a) Not in `presence/0.1`:** presence has one path, through the authority, under 144–147's policy. A client MAY
  show messaging activity (M§11) beside presence; the two are not combined.
- **(b) Members also send their presence as an M§11 activity,** combined with P§4.

**Draft choice: (a).** Two paths with different audiences would make a person's presence depend on which path a
watcher used. Encrypted presence (P§11 question 1) is the better reason to revisit this, and it waits for P§6 to
settle.

**Decided (2026-10-23, user: "148 (a)"): (a).** P§1 out of scope, P§11 question 3.

## 149. §9.3 — which targets an authority has "seen", for the uniform reject

**Found (2026-10-23, the independent TypeScript reading of P§6).** §9.3's anti-enumeration rule refuses targets the
authority "has never seen" exactly as unauthorized ones, but "seen" is not defined. The PoC (README authority rules)
counts a presence target as known when it is an identity the authority holds a device for, has a bound device, or has
a policy. A target named only by a capability the authority issued is not known, so the capability cannot admit
until that identity has bound once. impl-ts first read it otherwise and diverged both ways; it now matches.

Choices:

- **(a) Seen = has bound here (now or within the relay's retention, §13.3 spec-gap 131), or has a policy or an issued
  capability here.** A capability or policy the authority holds for a target is itself knowledge of it.
- **(b) Seen = has bound here, or has a policy here** (the PoC's rule; a capability alone does not count).
- **(c) Leave "seen" to the authority,** only requiring that the answer for an unseen target equal the one for an
  unauthorized target.

**Draft choice: (a).** An authority that issued a follow token for a target plainly knows it, and refusing the token's
holder until the target binds is surprising. The retention link keeps "seen" from growing forever.

**Decided (2026-10-23, user: "149 (a)"): (a).** §9.3 defines a seen presence target after the anti-enumeration rule
(bound within the §13.3 retention, or a policy or issued capability held for it); a publication target is seen while
published (unchanged). P§6 rule 3 points to it. Vector `state/presence-capability-makes-target-seen` (a capability
admits a target that never bound; nothing or another token is still `policy.blocked`); the harness, the Rust authority
and impl-ts count an issued capability. The authority trace keeps `context.identities` and current bindings as its
stand-in for retention: it models no retention clock.

## 150. §19.4 / P§7 — changing a grant, or ending a share and keeping calls

**Found (2026-10-23, the browser's grant controls).** A grant is issued only in answer to an introduction (§19.4
outcome 1; P§7: a share "is issued as any grant is"), and it is withdrawn whole. The browser grants
`dsip.invite` and `dsip.subscribe` in one grant, so a user who wants to stop sharing presence also stops the contact's
calls, and changing a share's audience or length means asking the contact to introduce again. Nothing in §19.4 says
whether a grantor may issue a grant without a fresh introduction, or answer one introduction with more than one grant.

Choices:

- **(a) Status quo.** One grant per introduction, withdrawn whole. A client that wants presence and calls separable
  must say so before granting; any change needs a new introduction. No spec change.
- **(b) A grantor MAY issue a further grant to an identity it holds a live grant for, without an introduction.** The
  new grant's `session` names the grant it follows (not an introduction). The grantor then revokes the old one if it
  replaces it. One mechanism covers narrowing (an invite-only grant, then revoke the old), a new audience and a new
  length. Needs §19.4 text, a schema change to the grant's `session` and vectors; the anti-spam bound is that the
  grantee already holds a grant from the same identity.
- **(c) An introduction MAY be answered by more than one grant.** Clients issue calls and presence as separate grants,
  so a share can be revoked alone. Changing an audience or length still needs a new introduction.

**Draft choice: (b).** It is the only choice that lets a user change a share without involving the contact, which is
what a share's controls are for; (c) helps only with the first of the two cases and (a) with neither. The bound keeps
it from becoming unsolicited contact: a grant can only follow a grant.

**Decided (2026-10-23, user: "150 (b)"): (b).** §19.4 "A grant that follows a grant": the new grant's `session` names
the live grant it replaces (no schema change; ids are ULIDs, so an introduction id and a grant id never collide), the
grantor withdraws the old one and SHOULD send its authority a `grant-revocation` for it, and the grantee holds the new
grant in place of the old one only when it holds a live grant with that id from the same identity; any other grant
whose `session` names neither is dropped. P§7 "Changing a share". Vectors `state/first-contact-regrant`,
`-regrant-expired`, `-initiator-regranted`, `-initiator-regrant-of-expired`, `semantic/grant-follows-held-grant`,
`-follows-unknown-grant` (context `held_grants`); the endpoint's local event `regrant`; fuzz endpoint target extended.

## 151. §19.4 — which grant admits an invite, and which one an invite names

**Found (2026-10-23, probing the three implementations while implementing spec-gap 150).** §19.4: "A live grant admits
an invite when the invite's `grant` names it **or** the inviting identity is the grantee — the `grant` field is an
optimisation, never a requirement". The three readings differ, and no vector separates them:

- Python and Rust admit when the inviting identity is the grantee of a live `dsip.invite` grant **and**, when the
  invite names a grant, it names that one. An invite naming a replaced or unknown grant is refused even though its
  sender holds a live grant: after a regrant (spec-gap 150), an invite in flight naming the old grant is refused.
- impl-ts admits when the invite names **any** live issued grant **or** the identity is a grantee. Bob's invite naming
  the id of a grant issued to Carol is admitted; so is Carol's naming a grant that does not exist.
- The sender side differs too: Python and Rust reference only a held grant that is live and has `dsip.invite`; impl-ts
  references any grant held from the callee, expired or presence-only.

Choices:

- **(a) Admission is by grantee only; `grant` is a hint.** An invite is admitted when its identity is the grantee of a
  live grant with `dsip.invite`; the `grant` field never admits and never refuses (a stateless relay may use it to find
  the grant). A sender names only a live `dsip.invite` grant it holds.
- **(b) Grantee, and the reference must match when given** (Python and Rust today): `grant` can refuse but never admit.
- **(c) The literal "or"** (impl-ts today): a reference to any live grant admits, whoever sends it.

**Draft choice: (a).** It is what "an optimisation, never a requirement" means; (b) makes the optimisation a way to be
refused (exactly the regrant race), and (c) lets anyone who learns a grant id call as its grantee.

**Decided (2026-10-26, user: "151 (a)"): (a).** Written into v0.17 §19.4. Vectors
`state/first-contact-grant-reference-is-a-hint` (an invite naming a replaced or unknown grant from the grantee is
offered; one naming another's live grant from an ungranted identity is refused) and
`state/first-contact-initiator-references-only-a-live-invite-grant` (an expired or presence-only grant is not named).
Python and Rust dropped the reference match, impl-ts the "or" and the sender's unfiltered reference; the endpoint fuzz
now also delivers presence-only grants. The vectors README said "matched by the invite's `grant` reference or by
grantee", which is what impl-ts followed; it now says grantee only.

## 152. P§11 question 1 / P§6 — presence encrypted to subscribers: how the key reaches them, and rotation

**Found (2026-10-23, the authority reads every record).** P§6's last paragraph accepts that the authority sees every
audience's states, and P§11 question 1 leaves encryption open, naming an MLS group per audience as one route.
`impl/docs/presence-encryption-design.md` worked the options (D1) and the rotation that removal needs (D3).

Choices (D1): **(a)** an MLS group per audience (removal is a Remove commit; presence then needs the messaging stack:
a hub, mailboxes, key packages per grantee device); **(b)** the audience key HPKE-sealed into the grant that admits
the subscriber (no new message; rotation is a new grant to each remaining grantee, which needs spec-gap 150 (b));
**(c)** a separate `presence-key` message (rotation leaves grants alone; adds delivery, retry and an admitted-but-no-key
window). D3: rotation **(i)** never, **(ii)** on removal, **(iii)** on a schedule and on removal.

**Draft choice: D1 (b), D3 (ii).** The key travels with the permission; rotation on removal is the only defence when
a former subscriber colludes with the authority, and removal is rare next to publishing.

**Decided (2026-10-23, user: "encryption now with (b) and D2–D6 as drafted"): D1 (b), D3 (ii).** P§12.3: a grant MAY
carry `presence_keys`, `{alg, enc, ct}`, HPKE to the grantee identity's key agreement key, info `dsip presence keys
v1`, AAD `id ‖ 0x00 ‖ from ‖ 0x00 ‖ to`, plaintext `{"keys": [{kid, key}]}` padded to a multiple of 256 bytes, holding
`main` and the grant's audience at the grantor's current epoch. P§12.5: rotation when a grant ends (revoked or past
`valid_until`), at most once per T-Presence-Rotate (P§8, 60 s, 0–3,600 s), and a grant that follows each remaining
grant (§19.4, spec-gap 150) carries the new keys without revoking it. Core §19.4 and §9.4 name the field. **Pinned**
(E1): `presence/grant-keys-*` (opening, splicing, scopes, padding), `payload/grant-presence-keys-*`. Rotation and
re-granting are E2 (state vectors, with spec-gap 159).

## 153. P§6 / P§12 — the audience on the wire when records are sealed

**Found (2026-10-23, same note, D2).** An audience label (`family`) tells the authority how the subject sorts its
contacts even when no state can be read. Choices: **(i)** keep the label; **(ii)** an opaque tag per audience.

**Draft choice: (ii).** **Decided (2026-10-23): (ii).** Working out D7 (a) (spec-gap 157) refined it: the subject's
devices must agree on the tag without exchanging anything, so it is derived, `k-` + base32 of 10 bytes of HKDF from the
identity's key agreement secret, the subject and the label (P§12.1), and stays the same across rotations (the epoch, in
`kid`, is what changes). **Pinned:** `presence/audience-tag`, `-per-label`, `-per-subject`, `-from-clamped-secret`.

## 154. P§4 / P§12 — a record the subscriber cannot read

**Found (2026-10-23, D4).** A subscriber without the key (or with an old one) holds a record it cannot read; the
authority cannot tell. Choices: **(i)** it counts as holding no record (the authority's assertion rule unchanged);
**(ii)** it counts as unknown, shown as "presence hidden".

**Draft choice: (i)**, and a client MAY say it holds presence it cannot read. **Decided (2026-10-23): (i).** P§12.4:
unreadable, in order, when no key is held for the `kid`, the decoded `sealed_state` is not 156 bytes, it does not open,
or the plaintext is not exactly `{"state": S}` with `S` a P§5 token; such a record takes no part in combining (P§4).
**Pinned:** `presence/open-record-*`, `presence/view-*` (`unreadable` lists the devices).

## 155. P§12 — what timing and size still say

**Found (2026-10-23, D5).** A sealed state's length would say which state it is, and a new record's timing says that
something changed. Choices: **(i)** accept both; **(ii)** pad (MUST) and refresh on a steady cadence (SHOULD).

**Draft choice: (ii).** **Decided (2026-10-23): (ii).** P§12.2: the plaintext is padded with spaces to exactly 128
bytes, so every `sealed_state` is 156 bytes; P§10 says a steady refresh keeps a change from showing in a record's
timing. Writing the vectors fixed the sealer's bytes (`{"state":"busy"}`, no whitespace) while a reader accepts any
JSON text of that one key. **Pinned:** `presence/seal-record` (the exact bytes), `presence/open-record-truncated`.

## 156. P§12 / §11.2 — versioning sealed records, and who is given them

**Found (2026-10-23, D6).** A subscriber that does not implement sealing cannot read a sealed record, and a subject
moving to sealing may still have such subscribers. Choices: per audience, or per record, or all at once.

**Draft choice:** sealed records name `presence/0.2`; a subject chooses per audience; no record is published in both
forms; a subscription whose `subscribe` does not list `presence/0.2` is given plain audiences only. **Decided
(2026-10-23): as drafted.** P§12.6: such a subscription is given no sealed record, and in its assertion their devices
count as holding none it sees; this applies to the subject's own devices too. P§12.2: a sealed record MUST name
`presence/0.2`, its `audience` is never `main`, and its `kid`'s scope is its audience (`main` without one): otherwise
`presence-sealed-invalid`, reason `presence.sealed-invalid` (P§9). Writing the record turned up that the field cannot
be `sealed`, as the design note had it: a record is addressed to its authority, and an addressee implementing
`sealed-body/1.0` refuses `sealed` without that extension in `dsip.critical` (§10.4); it is `sealed_state`. **Pinned:**
`state/presence-sealed-by-profile`, `-sealed-audience-beside-plain`, `-sealed-checked-as-plain`,
`semantic/presence-sealed-*`, `semantic/reason-presence-sealed-invalid-registered`, `payload/presence-sealed-*`,
`payload/presence-kid-*`, `envelope/presence-sealed-accepted`; fuzz targets `presence-admission` (sealed records,
subscriber profiles) and `presence-sealed` (opening).

## 157. P§12 — how the subject's own devices share the keys and the epoch

**Found (2026-10-23, working the construction).** Every device of the subject publishes, so all need the same key per
audience and epoch, and must agree on the epoch; the design note's D1–D6 did not say how.

Choices: **(a)** derive every key from the identity's X25519 key agreement secret, which every device of the identity
holds and no grantee does (§10.4), with the epoch in clear in `kid`, each device publishing at the highest epoch it has
seen; **(b)** random keys sent to sibling devices, sealed to the identity, through the authority or the mailbox (a new
message, its delivery and retry); **(c)** only one device publishes sealed records.

**Draft choice: (a).** No new message and no coordination beyond what P§6 rule 1 already gives; the authority learns
how many rotations each audience has had.

**Decided (2026-10-24, user: "157 (a)"): (a).** P§12.1: `s` is the secret after RFC 7748 clamping; tags as spec-gap
153; `kid` = scope (`main` or the tag) ‖ `.` ‖ epoch (decimal, no leading zeros); `key = HKDF-SHA256(s, "dsip presence
key v1" ‖ 0x00 ‖ subject ‖ 0x00 ‖ kid)`. P§12.2: AES-256-GCM, AAD `dsip presence v1 ‖ 0x00 ‖ subject ‖ 0x00 ‖ device ‖
0x00 ‖ audience ‖ 0x00 ‖ kid ‖ 0x00 ‖ u64be(seq) ‖ u64be(expires_at)`. P§12.5: a device's current epoch per scope is
the highest it has seen in its own identity's records or reached by rotating; every device re-grants the live grants
*it* issued when an epoch rises, its own rotation or a sibling's, since a device knows only its own grants (an offline
sibling's grantees cannot read the new epoch until it returns). **Pinned:** `presence/key-*`, `presence/seal-record`,
`presence/open-record-spliced-*`; the epoch rules are E2.

## 158. §13.2 — a replaced connection cannot tell it was replaced, so it reconnects

**Found (2026-10-24, the presence-audiences demo failing on main; PR #246).** §13.2 makes simultaneous connections from
one device to the same relay "undefined behavior in `ws/1.0`", and lets a relay "treat a new verified `hello` from an
already-bound device as replacing the prior connection" and "close the old one". The relay that closes it had no way to
say why, and the client no way to tell a replacement from any other drop; §13.2 "Keepalive and reconnection" then says it
SHOULD reconnect, with a fresh `hello` — which replaces the other connection, and the two connections of one device
replace each other in turn for as long as both processes live. Observed with two `dsip answer` processes of one device:
a replacement about every 0.5 s (each loss is a new outage to the client, so its backoff restarts at 1 s); and two tabs of
one browser profile (one device key) bound 11 and 10 times in 6 s. The browser had worked around it for peer relays by
sharing one connection per relay; the mailbox keeps a second connection as a standby beside the binding instead of
replacing it. #246 fixed a separate relay bug on the same path (the replaced connection's cleanup closed the new one too).

Choices:

- **(a) Name the replacement.** A relay that replaces a connection MUST send on it, before closing it, an `error`
  `transport.replaced` (a new `transport` token, valid on `error`). A client that receives it MUST NOT reconnect to that
  relay by itself — its device is bound there already — SHOULD tell its user, and MAY reconnect on the user's word. A
  client that does not know the token falls back to the category default, "reconnect/retry per binding rules", so old
  clients keep the loop; the registry entry says the token is the exception.
- **(b) Refuse the second hello.** The relay keeps the first connection. Locks out the common legitimate case, an old
  connection that is dead and not yet noticed (network change, NAT rebinding): refused until the 90 s Ping/Pong timeout.
- **(c) Leave it undefined; clients mitigate** (a client whose connection drops within seconds of binding keeps growing
  its backoff). Slows the loop, does not end it, and never tells the user why.
- **(d) Define several connections per device** (a standby, as the mailbox has, or delivery to the newest): which
  connection gets a frame, duplicates and session moves all need rules. A feature, not a `ws/1.0` fix.

**Draft choice: (a).** It keeps replacement, which a relay needs for a stale connection, and tells the replaced side the
one thing it cannot work out by itself, with the mechanism §13.2 already relies on (no silent drops on a live connection).

**Decided (2026-10-24, user: "158 (a), transport.replaced"): (a).** §13.2 Connection model gains the rule (relay MUST
send `transport.replaced` on the replaced connection before closing it; the client MUST NOT reconnect by itself, SHOULD
tell its user, MAY reconnect when asked), "Keepalive and reconnection" says such a close is not an unexpected loss, §15
registers `transport.replaced` (error; the client does not reconnect, unlike the category default), A.14 lists it.

**Pinned.** `semantic/reason-transport-replaced-registered` (registered on `error`, no fallback) and
`semantic/reason-transport-replaced-on-reject` (outside its valid-on column: accepted with `reason-not-valid-on-type`,
spec-gap 10). Reconnection is not modelled by any vector kind, so the wire behaviour is pinned by
`demos/relay-rebind-demo.sh` (CI: a frozen client, resumed, reads `transport.replaced` and stops; two live processes of
one device give one rebinding, and the older stops) and `web/test/relay-replaced.mjs` (two tabs of one profile: the first
says it was replaced and binds once, the second stays bound). Implementations: the relay sends the error and closes the
old connection cleanly; `dsip-transport`'s agent returns `Error::Replaced` instead of reconnecting (the CLI stops with
it); the browser's `Relay.replaced()` stops reconnection, for its relay (status line and a notice) and for peer relays.
The mailbox does not replace a connection (its second connection is a standby) and is unchanged.

## 159. P§12.5 / P§7 — a rotation grant leaves its predecessor admitting

**Found (2026-10-24, writing P§12.5).** A rotation re-grants every remaining grantee with a grant that follows theirs
(spec-gap 150) and does not revoke the old one, so nobody watching is cut off. The authority then holds two grants that
admit the same grantee, and the subscription it already has was admitted by the old one. When the share later ends,
the grantor revokes the grant it holds now, the newest: the subscription the old grant admitted keeps running, and the
old grant still admits a renewal, until its `valid_until`.

Choices:

- **(a) Ending a share revokes its whole chain.** The grantor revokes every grant of the chain still before its
  `valid_until` (rotation keeps `valid_until`, so the chain is the grants that followed one another by rotation, and the
  grantor's devices know them because each issued its own). Nothing changes at the authority.
- **(b) A rotation grant revokes its predecessor**, and the grantee re-subscribes with the new grant at once: one short
  gap in its notifies per rotation, and a rotation burst becomes a burst of re-subscriptions.
- **(c) The authority links them:** a grant whose `session` names a grant stands in for it, so revoking either ends
  what both admitted. The authority must keep the chain, from grants it was shown in `claims`.

**Decided (2026-10-25, user: "159 (a)"): (a).** It keeps the authority as it is and costs one revocation per link, at a
moment that is already rare (a share ending). P§12.5 gains "Rotation chains"; P§7's ending and changing a share revoke
the chain. In the endpoint traces (`impl/vectors/README.md`), `revoke` and `regrant` emit `{"revoke": [ids]}`: the grant,
then its chain newest first.

## 160. P§8 — a publisher that waits exactly the publish interval is refused

**Found (2026-10-25, CI on PR #248: web test `presence`, "no record of Bob's was refused").** P§8 measures the publish
interval between two records the authority *accepted*, on its own clock in whole seconds. A publisher can only measure
from when it *sent*. A record that crosses a second boundary in transit, followed by one that does not, arrives 4 s
after the first by the authority's clock although the publisher waited 5 s, and is refused `policy.rate-limited`
(it is sent again after `retry_after`, so presence recovers, but a conforming publisher was refused). The same holds
for a retry at exactly `retry_after`.

Choices:

- **(a) Editorial note in P§8:** the interval is the authority's, so a publisher leaves a margin for transit and
  whole-second clocks (the reference publisher waits interval + 1 s, and `retry_after` + 1 s). No wire change.
- **(b) Measure at the record:** the authority compares the records' `issued_at`, which the publisher controls. A
  publisher could then backdate within the replay window to send a burst, which the interval exists to prevent.
- **(c) Tolerance at the authority:** the authority accepts at interval − 1 s. It moves the margin, but a publisher
  still cannot know what the authority will allow.

**Decided (2026-10-25, user: "160 (a)"): (a).** P§8 gains the note after its table. The reference publisher
(`dsip_broadcast::presence::HOLD_BACK_S`) waits the interval + 1 s, and `retry_after` + 1 s; the authority rule and its
vectors are unchanged.

## 161. P§12.5 — which scopes an ending grant rotates

**Found (2026-10-25, writing the E2 endpoint traces).** P§12.5 rotated `main` and the audience whenever "a grant that
admits presence ends". Two cases read badly. A grant issued before its scopes were sealed carried no keys: its grantee
holds nothing to lose, yet every grant would be re-granted. A share changed by a following grant (P§7, spec-gap 150)
ends the old grant, so `main` rotates and every grantee is re-granted, although the following grant gives the same
grantee `main` again at once.

Choices:

- **(a) Rotate what the grantee loses:** the scopes whose keys the ended grant carried, except a scope the grant that
  changed the share carries too. Moving a grantee from `family` to no audience rotates `family` only; a change of
  length rotates nothing.
- **(b) As written:** `main` and the audience of every ended grant that admits presence, keys or not.
- **(c) Never on a change:** a changed share rotates nothing. A grantee moved out of an audience then keeps reading it.

**Decided (2026-10-25, user: "161 (a)"): (a).** P§12.5 keeps the text as drafted; the E2 endpoint traces pin it.

## 162. P§12.3 — a grant whose `presence_keys` cannot be sealed or opened

**Found (2026-10-25, writing the E2b core).** P§12.3 says a grant that admits a presence subscriber to a sealed record
MAY carry `presence_keys`, and P§12.4 says how a record fails to open, but neither says what becomes of the grant when
its keys cannot be sealed (the grantor cannot resolve the grantee identity's key agreement key) or cannot be opened (an
unknown `alg`, a failed HPKE open, a plaintext naming a foreign scope).

Choices:

- **(a) The grant stands without keys:** a grantor that cannot seal sends the grant without `presence_keys`; a grantee
  that cannot open them holds the grant as if it carried none. The grant still admits at the authority (P§6), and the
  subject's sealed records stay unreadable to the grantee (P§12.4, `presence-key-unknown`) until a following grant
  (P§12.5) carries keys it opens.
- **(b) The grantee refuses the grant:** it drops the whole grant, so it holds no admission it cannot use. The grantor
  is not told, and the grant still admits at the authority.
- **(c) The grantor does not issue it:** a grant for a sealed scope is refused locally when its keys cannot be sealed.

**Decided (2026-10-25, user: "162 (a)"): (a).** Every reason a grant exists other than presence (`dsip.invite`) is unaffected by its keys, and
the failure shows where P§12.4 already shows it. Written into P§12.3 as drafted; `dsip-endpoint` `Core` implements it
(`Impl:` notes in `core.rs`, `tests/presence_keys.rs`).

## 163. §11.2 / §11.4 — what a 1.x revision may add, when the schemas are closed

**Found (2026-10-27, assembling 1.0).** §11.2 says minor versions are backward-compatible, and 1.0 promises that a
later 1.x keeps every conformant 1.0 implementation conformant. But every core payload schema is closed
(`additionalProperties: false`), and the vectors pin it (`payload/invite-unknown-top-level-field` and seven more
`*-extra-field*` vectors expect `schema-invalid`): a 1.0 receiver rejects a field it does not know. A 1.x that adds
an optional field to an existing core message would therefore break 1.0 peers — as v0.17's `grant`
`presence_audience` and `presence_keys` would have broken a v0.16 receiver.

Choices:

- **(a) Closed schemas; new fields negotiated.** No wire change. A 1.x may add message types (a 1.0 receiver refuses
  them as unknown types, §12.1), registry entries (category fallback, §15), profiles and extensions. A field added to
  an existing core message is defined by an extension or profile, and a sender includes it only for a receiver known
  to support it: its `dsip.profiles` or `dsip.extensions` in a message it sent, its `hello` capabilities, or its DID
  document. Anything else — a field every receiver must accept, a changed rule, a removal — is 2.0.
- **(b) Must-ignore unknown fields.** 1.0 opens the schemas' top level; 1.x adds optional fields freely. A wire
  change at 1.0: the extra-field vectors flip to accept, all three implementations change, and an unknown field no
  longer fails loudly.
- **(c) Closed schemas; any new field is 2.0.** 1.x adds only message types, tokens, profiles and extensions.

**Decided (2026-10-27, user): (a).** Written into 1.0 as §11.4 "Stability of Core 1.0"; no schema or vector changes.

## 164. M§4.1 — whether a mailbox's operator may end an enrolment

**Found (2026-10-29, service nodes S5 in dsip-rs: `dsip-mailbox admin release`).** M§4.1 names two ways an enrolment
ends: the identity's `release` and, at the operator's choice, idle expiry. An operator who wants a place back now (a
full mailbox, an abusive identity, a test account) has neither: a release comes only from a device of the identity, and
idle expiry waits `mls_retention_s` after the last `hello`.

Choices:

- **(a) The operator MAY end an enrolment**, with the same effects as a release: everything held for the identity is
  deleted, its bindings closed, its place freed. No message is sent. A configured identity is not ended this way; the
  operator removes it from the configuration.
- **(b) Only the two ways.** An operator who wants a place back closes the mailbox's bindings and waits for idle
  expiry, or enlarges the bound.

**Decided (2026-10-30, user: "164 (a)"): (a).** It is a local action of the mailbox and changes nothing on the wire,
so §11.4 allows it in 1.0 (A.16). M§4.1 gains "By its operator". The `enrolment-trace` gains the event
`{operator_release: {identity}}`, which emits `released {cause: "operator"}` for an enrolled identity and nothing for
any other (`enrolment-operator-ends-an-enrolment`, `enrolment-operator-end-spares-configured-and-unserved`).

## 165. E§2 — a `device-event` from a device without `dsip.events`

**Found (2026-10-31, auditing the Device Events Profile for 1.0).** E§2 delegates a gateway with the capability
`dsip.events`, but says nothing of what a member does with a `device-event` whose sender's device lacks it. No
implementation checked it, so any member device of the alarm group could raise an alarm, and an escalation agent
(E§6) would call someone for it.

Choices:

- **(a) Refuse it.** The member's content check refuses it with the existing token `delegation-capability`; it never
  reaches the alarm list. An `alarm-ack` needs no capability: any member may acknowledge.
- **(b) Render it, marked as not from a gateway, and keep it out of the alarm list and escalation.**
- **(c) Informational.** The capability is advice to operators; members do not check it.

**Decided (2026-10-31, user): (a).** E§2 gains the rule. Kind `messaging`'s `check: "object"` gains
`context.leaf_capabilities`, the capabilities of the sender leaf's device delegation (absent is none), and a
`device-event` without `dsip.events` there is `delegation-capability`, after `content-body`
(`content-device-event-without-capability`, `content-device-event-capabilities-absent`).

## 166. E§5 — the shape of a `device-event`'s and an `alarm-ack`'s body

**Found (2026-10-31, auditing the Device Events Profile for 1.0).** M§8.2 requires `event` on a `device-event`, and
`alarm` and `state` on an `alarm-ack`, and the vectors checked only that they were present. What `event` holds
(`source`, `alarm`, `heartbeat`) and what a member does with an `alarm-ack` whose `state` is neither `ack` nor
`closed` were not stated.

Choices:

- **(a) A minimal shape.** Required members and their types only; members not named are ignored; tokens keep their
  registry fallbacks; an unknown `alarm-ack` `state` is accepted and ignored by the alarm list.
- **(b) The full shape.** Every member E§2 and E§5 list (`raw.snmp`, `raw.syslog`, `usm`, `tsm`, `signed`,
  `syslog_gap`, …), each as a body rule.
- **(c) Presence only**, as before.

**Decided (2026-10-31, user): (a).** E§5 gains **Bodies**; `impl/vectors/README.md` states them exactly (kind
`device-events`, **Content bodies**), and a broken one is `content-body`. `source` is required unless `heartbeat` is
present: E§5 never gave a heartbeat one, and its sender is the gateway itself. The alarm list ignores an `ack` with an
unknown `state` (`alarm-ack-unknown-state-ignored`), so a later revision can register one.

## 167. E§4 — an inform's clear when a clear for the same alarm is held

**Found (2026-10-31, auditing the Device Events Profile for 1.0).** E§4's hold-down deposits an event from an SNMP
inform at once, so an inform's clear is never held. It did not say what happens to a clear already held for the same
alarm: left alone, it is deposited when due, a second clear that members count as a repeat.

Choices:

- **(a) The inform's report drops it**, as a raise for the same alarm does: the alarm's state is settled by the
  inform's report.
- **(b) It stays, and is deposited when due.**

**Decided (2026-10-31, editor's proposal, to be confirmed): (a).** It matches the raise rule and deposits one clear
for one state. The hold-down traces' `report` gains `inform: true` (`holddown-inform-clear-not-held`,
`holddown-inform-clear-drops-held-clear`).

## 168. E§3 — the bytes of the gateway's SNMPv3 Reports and Responses

**Found (2026-10-31, auditing the Device Events Profile for 1.0).** E§3 named what the gateway answers (a Report for
discovery and for an inform outside the time window, a Response once an inform's event is stored) but not its bytes,
and the vectors only said whether a Report was sent. A device that cannot read the Response retries the inform
forever. RFC 3412, 3414 and 3416 settle most fields: `msgID` copied (RFC 3412 §6.2, §7.1 step 2b); a Report at
noAuthNoPriv for discovery and authNoPriv for the time window (RFC 3414 §3.2 steps 3b, 7a; RFC 3412 §7.1 step 3d),
never reportable (§6.4); its contextEngineID the local engine's and contextName "" (§7.1 step 3d); the local
engine's boots and time (RFC 3414 §3.1 step 6); the counter after it was incremented; a Response with the inform's
request-id and variable bindings, error status and index 0 (RFC 3416 §4.2.7), at the inform's security level; the
AES salt the sender's own (RFC 3826 §3.1.2.1). They leave open:

1. a Report's request-id when, as always for a USM error, the PDU was not read: RFC 3412 §7.1 step 3c4 gives 0, but
   step 3a says "if possible";
2. `msgMaxSize` ("implementation-dependent", §7.1 step 7c);
3. a Response's contextEngineID and contextName (supplied by the application, RFC 3413);
4. the encoding, which BER lets vary;
5. which `msgFlags` bits besides auth and priv a Response carries.

**Decided (2026-10-31, user: pin the bytes before 1.0; values chosen by the editor, to be confirmed):**

1. request-id 0, the literal reading; a Report is matched by its `msgID` (RFC 3412 §6.2);
2. 65507, the largest UDP payload;
3. the inform's, as E§3 already says for TSM;
4. the shortest lengths and integers, and the inform's VarBindList copied as received, never re-encoded;
5. only the auth and priv bits (`& 0x03`).

`check: "snmp-answer"` (README, kind `device-events`) pins them for USM Reports and Responses and for TSM Responses
and discovery answers (`snmp-answer-*`).

## 169. W§4 — how a waker is authorized to wake a device

**Found (2026-10-31, app plan stage A1; `impl/docs/wake-profile-outline.md`).** §13.3 makes waking a sleeping device
the relay's job and says push is centralized, but not who may ask a push gateway to wake whom. RFC 8599 hands the
server a bearer token: whoever holds it can push. In DSIP the token goes to relays and mailboxes run by anyone, so a
bearer token lets any of them, or anyone it leaks to, wake the phone.

Choices:

- **(a) A device-signed registration** naming the waker, the gateway and the handle, with a `not_after`. The waker
  shows it to the gateway with every wake; the gateway checks it is signed by the key the handle names and that the
  waker signed the wake. Offline: no gateway round trip per waker, and the gateway keeps no table.
- **(b) Per-waker tokens issued by the gateway.** The device asks the gateway for a token for each waker. The gateway
  keeps them, and adding a relay or mailbox needs the gateway.
- **(c) A bearer token**, as RFC 8599.

**Decided (2026-10-31, user: "all (a)"): (a).**

## 170. W§4 — where a device gives a waker its push address

**Found (2026-10-31, as 169).** The app plan put the address "in its `hello` or its `mailbox-config`". A binding
ends with its connection, and a sleeping device has none, so the address must outlive what it rides in; and a field
in `hello` or `mailbox-config` is a new field in a closed core or profile message (spec-gap 163).

Choices:

- **(a) A new message, `wake-register`**, the same to a relay and a mailbox, answered `accepted` or `error`; the
  waker holds the registration until it ends (spec-gap 174).
- **(b) Fields in `hello` and `mailbox-config`**, negotiated as §11.4 allows, held past the binding by rule.

**Decided (2026-10-31, user: "all (a)"): (a).**

## 171. W§6 — what a wake may carry

**Found (2026-10-31, as 169).** §13.3: "the push payload need carry nothing but a wake signal". iOS needs a call
reported the moment a VoIP push arrives, before the app can bind, so a bare signal rings as "unknown" until the invite
arrives. APNs and FCM bound a payload at 4 KB, under an invite with its offer.

Choices:

- **(a) Kind and session, plus a hint sealed to the device**: HPKE (M§6.9's suite) to a key in the registration,
  holding the invite's `from` and `on_behalf_of`. The app shows the contact it already holds; neither the gateway nor
  the provider sees the caller. The hint is the relay's claim, replaced by the verified invite.
- **(b) Kind and session only.**
- **(c) The held envelope sealed to the device.** Does not fit for an invite.

**Decided (2026-10-31, user: "all (a)"): (a).**

## 172. W§5 — when a waker wakes, coalescing and retries

**Found (2026-10-31, as 169).** Nothing says which held traffic wakes a device, how a woken call that is cancelled
before the device binds is ended on its screen (Apple requires the call reported), how often messages may wake it,
or whether a failed wake is retried.

Choices:

- **(a)** `call` once per held invite per device, including legs of an identity-addressed invite; `call-ended` when
  the relay drops a held invite it woke for before the device bound (cancel or expiry); `message` for a stored item
  while the device is unbound, at most once per W-Coalesce (60 s) per device, never for an `ephemeral` deposit; one
  retry for a transport failure, before the wake's `expires`; none for an answered wake. Call timing is untouched:
  T-Establish ends an attempt whose device does not bind in time.
- **(b)** As (a) without `call-ended`: the app ends a call whose invite does not arrive.
- **(c)** Wakes for calls only; messages wait for the next time the app runs.

**Decided (2026-10-31, user: "all (a)"): (a).**

## 173. W§3, W§5 — how wakers and devices reach the gateway

**Found (2026-10-31, as 169).**

Choices:

- **(a) HTTPS POST of a signed envelope** to the `DSIPWake` service endpoint in the gateway's DID document, answered
  with a signed envelope: verified with the same code as every envelope, stateless for the gateway.
- **(b) A `ws/1.0` binding** with `hello`: a connection held from every waker to the gateway.

**Decided (2026-10-31, user: "all (a)"): (a).**

## 174. W§4 — when a registration ends

**Found (2026-10-31, as 169).**

Choices:

- **(a)** At its `not_after` (at most W-Registration cap, 30 days, after `issued_at`); when replaced by the device's
  next registration (one per device per waker); on `wake-register` `remove: true`; when the gateway answers
  `wake.registration-ended` or `wake.not-authorized`; when the device's delegation is revoked or expires; and when
  the waker forgets the device (§13.3 retention, M§4.4).
- **(b)** As (a) without a lifetime: a registration lasts until one of the other events.

**Decided (2026-10-31, user: "all (a)"): (a).**

## 175. W§3 — what identifies a device to the push gateway

**Found (2026-10-31, as 169).** The gateway must tie a handle to whoever may sign registrations for it. Using the
device DID tells the app's publisher every device that runs the app and, through delegations, its identity.

Choices:

- **(a) A per-enrolment wake key**: an Ed25519 key the device makes for the enrolment, signing the enrolment and the
  registrations. The gateway never learns the device's DID; the waker sees the registration arrive on the device's
  binding, so it needs no link either.
- **(b) The device DID.** One key fewer.

**Decided (2026-10-31, user: "all (a)"): (a).**

## 176. W§4.2 — whether `wake-register` at a mailbox is an owner operation

**Found (2026-11-01, implementing the mailbox's `message` wakes in dsip-rs).** W§4.2 says a waker needs no capability
beyond binding's (§13.2; M§4.3 for a mailbox), and lists four checks, all on the registration. Any device can bind to
a mailbox with a verified `hello`, whether or not the mailbox serves its identity (M§4.1). A registration from an
identity the mailbox does not serve can never be used, since nothing is stored for it, but the mailbox would keep it
for up to W-Registration. The Messaging Profile has a rule for this case already: an owner operation (`sync`,
`key-packages`, `mailbox-config`) from an identity not served either enrols it, while the operator's bound has room,
or is refused `mailbox.not-served` (M§4.1, spec-gaps 115, 130).

Choices:

- **(a) An owner operation.** Before W§4.2's checks, a mailbox treats `wake-register` as M§4.1 treats an owner
  operation: an identity it serves registers; one it does not serve enrols by it, or is refused `mailbox.not-served`.
  A relay is unchanged (§13.6 decides whom it serves at binding).
- **(b) As drafted.** Any bound device registers; a registration of an identity the mailbox does not serve is kept
  and never used.

**Decided (2026-11-01, user: "176 (a)"): (a).** W§4.2 says so; dsip-rs's mailbox implements it (`dsip-mailbox`'s
`service.rs`, `crates/dsip-mailbox/tests/wake.rs`). No vector changes: the `wake/` vectors' register checks are the
profile's own, run after the binding's.

## 177. §9.3 — whose subscription a renewal replaces

**Found (2026-11-01, sealed presence on the native phone, dsip-rs #30).** §9.3: subscriptions "expire unless renewed
by a fresh `subscribe` for the same `target`+`events` (which replaces the prior subscription)", and `expires_in: 0`
"terminates a matching subscription". Neither says the same *what*: the subscriber's identity or the subscribing
device. dsip-rs's authority (`dsip-broadcast` `authority.rs`) matches per subscriber identity, so a second device of
one identity that subscribes to the same target replaces the first device's subscription, and only the second is
notified (the authority notifies the subscription's `device`). Two cases break:

- P§12.5: each device of a sealing subject watches its own identity (P§6 rule 1) to learn the epochs its siblings
  reach. With two devices, only the last to subscribe holds that watch; the other never moves to a sibling's epoch,
  and grantees given only the new key cannot read it (`presence-key-unknown`).
- A user's phone and laptop following the same contact: each renewal moves the subscription to the device that
  renewed, and the other's view goes stale until it renews in turn.

Choices:

- **(a) Per subscribing device.** A subscription belongs to the device that sent the `subscribe` (its `from`). A
  renewal or `expires_in: 0` matches the same device, `target` and `events`. Each device of an identity holds its
  own, and is admitted, counted and notified on its own. A grant presented by one device admits that device's
  subscription only. A revocation (P§7) ends every subscription the grant admitted, whichever device holds it.
- **(b) Per subscriber identity, notified to every bound device.** One subscription per `(identity, target, events)`,
  as now, delivered to each of the identity's devices bound at the authority. This needs a bound-device fan-out the
  authority does not otherwise do. A device bound elsewhere (a subscriber reaching a hint-located authority, §9.3)
  is not bound there, so it is still missed.
- **(c) Per subscriber identity, as implemented.** The last subscribing device holds it. P§12.5's own watch then
  works for one device only, so the profile would have to say that siblings learn epochs some other way.

**Decided (2026-11-01, user: "(a) Per device"): (a).** §9.3 says so, in place (A.16). Vector
`state/broadcast-authority-renewal-per-device`: two devices of one identity subscribe to one target, both are
notified, and one's renewal and termination leave the other's in place (the Python harness matching per identity
fails it). The Python harness, impl-ts and dsip-rs's authority match on the subscription's device.

## 178. W§3, W§5.3 — a `message` wake to an iOS device has no token APNs will take

**Found (2026-11-06, iOS PushKit in the app, dsip-app A5d-3).** W§2 says an iOS device holds "a PushKit VoIP token",
W§3 enrols one token per enrolment with `app` "the APNs topic (the bundle ID with `.voip`)", and W§5.3 sends a
`message`-class push as `apns-push-type: alert` with `mutable-content: 1` on "the app's bundle ID" topic to the
**same** token (dsip-push strips `.voip` from `app`). APNs refuses that: a PushKit VoIP token is issued for the `.voip`
topic only. An alert push needs the separate device token from `registerForRemoteNotifications`, and APNs answers a
VoIP token on the bundle topic with 400 `DeviceTokenNotForTopic`. So no iOS device can get a `message` wake as the
draft stands. Android is not affected, because FCM has one token for both classes.

A `message` cannot move to PushKit. Apple ends VoIP delivery to an app that does not report a call to CallKit for
every VoIP push.

Choices:

- **(a) Two enrolments per iOS device.** One token per enrolment (W§3 unchanged): the VoIP token enrolled with
  `app` `<bundle>.voip`, the alert token enrolled with `app` `<bundle>`. Each gives its own handle and registration.
  The device registers the `.voip` one with relays (`call`, `call-ended`) and the bundle one with mailboxes
  (`message`). W§5.3's `message` row then uses the handle's `app` as its topic, not one derived from it. Nothing new on
  the wire. The cost is two enrolments and two refreshes for one iOS device.
- **(b) Two tokens in one enrolment.** `wake-enrol` gains an optional `message_token` (APNs only). The handle stands
  for both, and the gateway picks one by class. One registration serves both wakers. This is a schema change, and
  the handle grows.
- **(c) Calls only on iOS.** iOS devices get no `message` wakes. The mailbox is fetched on open, or on the user's own
  background refresh. W§5.3's `message` row becomes FCM only. This is simplest, and it drops iOS message wakes.

**Decided (2026-11-06, user: "(a) for gap 178"): (a).** It keeps one token per handle, which every other rule
assumes (a registration ending on APNs 410, W§5.3's `wake.registration-ended`). In place in the draft:

- W§2: an iOS device holds two tokens.
- W§3: `app` is the topic of the token, the `.voip` topic or the bundle ID. An enrolment is one token, each under its
  own wake key.
- W§4.2: the VoIP handle is registered with relays, the alert handle with mailboxes.
- W§5.3: the `message` row's topic is the handle's `app`.

Vectors: `wake/enrol-apns-alert-token` (a gateway pushing for both topics accepts the alert token's enrolment) and
`wake/gateway-message-apns-alert-token` (a mailbox's `message` wake is forwarded on the alert handle, its `app` as
given). Python, impl-ts and dsip-rs at c31b392 already agree: the gateway check forwards the handle's `app`
unchanged. dsip-rs's `dsip-push` APNs adapter derived the message topic by stripping `.voip`; it now takes the
handle's `app`. The iOS app's alert token and notification service extension follow in dsip-app.

## 179. §7.3, §19.4, M§6.9, P§12 — a `did:key` identity's key agreement secret is its signing key

**Found (2026-11-06, dsip-app A6c, adding a second device).** Sealed introductions (§19.4, M§6.9), sealed bodies
(§10.4) and sealed presence (P§12) are sealed to the identity's X25519 key agreement key. "Every device acting for an
identity holds that identity's key agreement private key" (§10.4). For `did:key` that key is the one the method
derives from the Ed25519 key. Its private half is the first 32 bytes of SHA-512 of the Ed25519 seed, clamped. That is
exactly Ed25519's secret scalar, and that scalar is all an Ed25519 signer needs: a verifier never checks how the
nonce was made. So a device that can open what is sealed to a `did:key` identity can also sign as that identity:
delegations, revocations (§7.4, §7.5), grants. Nothing in the spec says so.

Decision 5 (a) of the app plan, the identity key on one device and later devices holding only device keys and
delegations, is therefore impossible for a `did:key` identity whose later devices take first contact or follow
sealed presence. §7.3's separation of identity and device keys holds for signing only. M§6.9 lets a `did:web`
identity publish an independent X25519 key (spec-gap 55). A `did:key` identity has no document to publish one in.

Choices:

- **(a) A key agreement delegation.** The identity signs a credential naming an independent X25519 public key:
  `{"type": "KeyAgreementDelegation", "subject": "<identity>", "key": "<multibase X25519>", "issued_at", "expires_at"}`,
  in the delegation's envelope form. Its private half goes to every device acting for the identity, and no device
  then needs the identity key to open anything.
  - A sender seals to it in place of the derived key when it holds a verified one for the recipient. It finds one
    where it finds the recipient's devices: in the recipient's signed reachability hint (a new optional member,
    verified against the identity like the hint's delegation, §8.3), and in a grant (P§12).
  - With none, the sender seals to the derived key as now, and only devices holding the identity key open it.
  - A `did:web` identity's document `keyAgreement` stays authoritative (§8.1). The credential is for `did:key`
    identities, and is ignored for an identity whose document names one.
  - Rotation: a new credential replaces the old one, as a key-rotation does (§7.5).
  - Costs: a credential type, a hint member, sender logic, and vectors. It is a 1.x addition (§11.4).
- **(b) State it, and leave the arrangement.** §7.3 and M§6.9 say that for `did:key` the key agreement secret is
  the signing key. A `did:key` identity's every device that opens sealed content holds the identity key in effect,
  and separation needs `did:web` with an independent `keyAgreement` key. No wire change. The app's decision 5 (a)
  then holds only for `did:web`.
- **(c) Seal to devices.** The sender seals once per device of the recipient, using device keys from the hints, so
  no shared secret exists. Devices the sender does not see (no hint, or hints withheld) never get it. Each sealed
  item grows with the device count, and an introduction to a newly added device is lost. Spec-gap 55 (b) rejected
  this for introductions.

**Decided (2026-11-06, user: "(a) KA delegation"): (a), with (b)'s statement.** In place:

- **Core §7.3:** the derived secret is the signing scalar, stated. The `KeyAgreementDelegation` credential: its form,
  its verification, which delegation is current, and the key agreement key of a DID (document, else delegation, else
  derived).
- **§10.4 rule 3:** the recipient key in that order. A delegation a hint carries is the subject's own credential, not
  hint data.
- **M§6.9 and P§12.1:** the delegation's key. A new key is a rotation (P§12.5).
- **DHT Hints Profile:** the optional `key_agreement` member, and the hint refused when it does not verify.
- **Schemas:** `key-agreement-delegation` in the core set; the hint's member.
- **A.16:** a line.

Vectors: `key-agreement/` (credential verification in order `credential-invalid` → `schema-invalid` →
`not-subject-signed` → `subject-mismatch` → `validity-invalid` → `not-yet-valid` → `expired`; the recipient key) and
`dht/key-agreement-*` (`key-agreement-invalid`). Carrying the delegation in an introduction or a grant is left for
when a sender needs it beyond hints.
