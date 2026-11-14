# DSIP Conformance Test Vectors

**Tracks:** DSIP Core 1.0 (`v1.0/`, in progress; v0.17 final at `poc-v0.17`) + JSON Schema set 1.0 (draft 2020-12); the Messaging Profile schema set for `messaging/`
**Format version:** 1

These vectors are the language-neutral conformance contract for DSIP Core v1.0.
They are *generated* by `impl/tools/generate_vectors.py` (deterministic keys,
deterministic ULIDs, byte-reproducible signatures) and *verified* independently
by the Python harness (`impl/tools/run_vectors.py`), the Rust runner
(dsip-rs: `cargo run -p dsip-cli -- vectors run`), and a second implementation written from this
document and the spec alone (`impl-ts/`, TypeScript; `impl/tools/parity_ts.py`). A vector is
only trusted when the runners agree with its `expect` block.

Expected outcomes are authored by hand from the spec text in the generator
modules — they are never derived from either implementation's output.

## File layout

```
vectors/
  envelope/    Signature, header, kid→DID resolution, delegation, replay, ULID/issued_at
  media-binding/ WebRTC Media Binding 1.0 conformance (descriptor/SDP authority, roles, candidates, renegotiation, one answer)
  gateway/     SIP/PSTN gateway (Phase 4): §15.5 reason mapping both ways, SDP ⇄ descriptors, PSTN caller claims, downgrade rule, B2BUA controller traces
  messaging/   Messaging Profile 1.0 (M§n): profile messages, content objects, hub/mailbox/client/history traces, MLS layer, HPKE, blobs, first contact
  payload/     JSON Schema pass/fail per message type (shape only)
  semantic/    Stateless post-schema checks (schema README list of 11)
  state/       Scripted endpoint and relay state-machine traces (§12)
  transport/   ws/1.0 hello binding, anti-splicing, size cap (§13.2)
  dht/         Reachability hint records and §8.3 conflict rules
  broadcast/   Receiver-side verification of a publication record and its provenance (§22)
  trust/       The basis-of-verification lines a client shows (§18.1, §6.3) — exact text
  did-webvh/   Resolving a did:webvh v1.0 log for DSIP (§7.2, §8.1, §8.4; v0.9, spec-gap 101)
  device-events/ Device Events Profile 1.0 (E§3–E§6): traps → events → alarms, the alarm list, escalation
  recording/   Recording Profile draft (C§3–C§6): the counterparty's consent, recorded conversations, the recorder leg
  alias-transparency/ Alias Transparency Profile draft (T§2–T§5): KEYTRANS building blocks, alias normalization
  pkarr/       Reachability hints on Pkarr / BEP 44 for did:key subjects (§8.5; DHT Hints Profile §9; spec-gap 105)
  tn-binding/  Number Attestation Profile draft: a STIR-signed number → DID binding and its checks (N§3), the claim and
               identity-change warning (N§4–N§5), a node's store and the reader's choice (N§6–N§7), and the gateway's
               PASSporT verification, routing and assertion (N§4.1, N§6.1, G§5) (spec-gap 110)
  presence/    Presence Profile draft (P§4–P§5): the subscriber's rule combining several devices' records (spec-gaps 135, 136);
               sealed records (P§12): keys, sealing, opening, keys in a grant, the subscriber's view (spec-gaps 152–157);
               the record's age (envelope/), shape (payload/), checks (semantic/) and the authority (state/) are beside
               their kinds
  wake/        Wake Profile draft (W§3–W§6; spec-gaps 169–175): the messages' shapes, enrolment at the push gateway, a
               waker's checks on a registration, the gateway's checks on a wake and what it forwards, the sealed hint,
               and the relay's and mailbox's wake traces
```

One vector per file. The vector id is its path relative to `vectors/` without
the `.json` suffix (e.g. `envelope/valid-ed25519`).

## Common envelope

```json
{
  "vector": "envelope/valid-ed25519",
  "format": 1,
  "kind": "envelope",
  "description": "Human-readable statement of what is being tested",
  "spec_ref": ["§10.2"],
  "context": { ... kind-specific receiver context ... },
  "input":   { ... kind-specific input ... },
  "expect":  { ... kind-specific expectation ... }
}
```

`spec_ref` entries cite v0.8 section numbers (unchanged from v0.6 and v0.7 for every section the vectors cite); `B§n` cites a section of the WebRTC Media Binding 1.0 companion document. Every vector has at least one.

## Runner results

A runner compares what it computed (`actual`) with `expect` for **deep equality** — arrays in
order, objects member by member, nothing extra. A member absent from `expect` is therefore a claim:
no `warnings` means the implementation raised none, no `effective` means nothing registry-governed
was read, no `reason` means the spec assigns no token. Trace kinds compare each step's `emit`
exactly and, of the snapshot, the members (sessions, attempts, …) the step names.

With `--json FILE` a runner writes `{ "<vector id>": {"ok": bool, "actual": …} }` (`"steps": […]`
in place of `actual` for traces). Parity tools diff these files, so two implementations that both
satisfy `expect` but disagree on something it leaves unsaid are still caught. A runner that does
not implement a kind reports `{"ok": false, "skipped": true}`; a skipped vector never counts as agreeing.

## Beyond the vectors: differential fuzzing

A vector exercises one rule; implementations can pass every vector and still disagree when two rules meet.
`impl/tools/fuzz.py` generates random well-formed traces and table rows, runs them through all three runners
(`--dir`, `--json`) and compares actual with actual. CI runs it with a fixed seed and then with the run's own number as a second seed (printed, reproducible); a weekly
workflow uses a fresh one at a larger count.
A disagreement never becomes a recorded expectation: it becomes a hand-authored vector here, or a spec-gap.

## Fixed fixtures

All vectors share the fixture set in `fixtures.json` (also generated):

- **Keys** are Ed25519, seeded with `sha256("dsip-vector:" + name)`; the
  vectors carry only public material. `did:key` identifiers are the multicodec
  `ed25519-pub` (0xed01) form, base58btc, `z6Mk…`.
- **Identities:** `alice` and `bob` are identity controllers with delegated
  devices `alice-phone`, `alice-laptop`, `bob-phone`, `bob-laptop`. `bob-next` is
  the key bob's `did:web` identity rotates to (§7.5 vectors). `relay` is
  a relay identity. `carol` is an unknown first-contact identity. `mallory`
  holds a key with no delegation from anyone.
- **`did:web` documents** for `did:web:example.com:users:bob` and
  `did:web:relay.example.com` are supplied under `context.did_documents`
  wherever a vector needs them; resolvers under test MUST consult that map
  instead of the network.
- **Delegations** (§7.4) are DSIP-JOSE envelopes whose payload is the
  `DeviceDelegation` object, signed by the subject identity's controller key.
  They are supplied under `context.delegations` (and MAY also appear in the
  protected header `delegations` array — see `Impl` note in the envelope
  pipeline below).
- **Revocations** (§7.4, v0.8) are `delegation-revocation` envelopes the receiver holds, under
  `context.revocations`; a `did:web` document may also publish them (`dsipDelegationRevocations`, compact form).
- **Clock:** `context.now` is the receiver's clock at receipt, integer seconds.

## Verdict codes

Rejections are classified by an implementation-neutral `code`. Where the spec
assigns a reason token to the condition, `reason` is also given and the
implementation under test MUST emit that token when it signals the failure.

| code | meaning | reason (when defined) |
|---|---|---|
| `frame-too-large` | text frame exceeds 65,536 bytes (§13.2) | `transport.envelope-too-large` |
| `envelope-shape` | not a JSON object with exactly `protected`,`payload`,`signature` base64url strings | |
| `header-invalid` | protected header not a JSON object, or missing `alg`/`kid` | |
| `alg-unsupported` | `alg` is not `EdDSA` (ES256 is MAY; this PoC rejects it) (§10.2) | |
| `kid-invalid` | `kid` is not a DID URL with a fragment (§10.2) | |
| `kid-unresolvable` | `kid` DID cannot be resolved, or fragment names no Ed25519 verification method (§8.1) | |
| `signature-invalid` | Ed25519 verification over `protected.payload` failed (§10.2) | |
| `payload-not-utf8` | decoded payload is not valid UTF-8 (§10.3) | |
| `payload-not-json` | payload is not a JSON object (§10.3) | |
| `payload-float` | any number in the payload is non-integer (§10.3) | |
| `payload-shape` | core fields (`dsip`,`type`,`id`,`from`,`issued_at`,`expires_at`) missing or wrong primitive type, or `id` not a ULID (§10.3; every later stage that reads the id depends on it) | |
| `signer-mismatch` | `kid` DID ≠ `from` DID and no delegation presented linking them (§7.4, check 3) | `transport.hello-rejected` on `hello` |
| `delegation-invalid` | presented delegation fails: bad signature, wrong subject/device, not signed by subject controller | `transport.hello-rejected` on `hello` |
| `delegation-expired` | delegation not valid at `now` (`issued_at ≤ now < expires_at` required) | `transport.hello-rejected` on `hello` |
| `delegation-capability` | delegation lacks `dsip.signaling` (every envelope binds under it; spec-gap 56) | `transport.hello-rejected` on `hello` |
| `delegation-revoked` | a `delegation-revocation` signed by the subject covers the delegation (held, or in the subject's document) (§7.4, v0.8) | `transport.hello-rejected` on `hello` |
| `expiry-order` | `expires_at ≤ issued_at` (check 1) | |
| `replay-window` | `issued_at` outside `[now − 300, now + 300]` (§12.9, check 1); for `introduction` (spec-gap 31), `reachability-hint` (spec-gap 96) and `presence` (spec-gap 134, v0.17) only the future bound applies — their age is bounded by `expires_at` (§12.9) | |
| `introduction-validity` | `introduction` with `expires_at − issued_at` > 604,800 s (§12.9, §19.4; spec-gap 31) | |
| `hint-validity` | `reachability-hint` with `expires_at − issued_at` > 3,600 s (§12.9, DHT profile §2; spec-gap 96) | |
| `presence-validity` | `presence` with `expires_at − issued_at` > 3,600 s (§12.9, P§3, P§8; v0.17, spec-gap 134) | |
| `sealed-not-critical` | a payload carries `sealed` but `dsip.critical` does not list `sealed-body/1.0` (§10.4; spec-gap 97) | |
| `sealed-alg-unsupported` | `sealed.alg` is not `hpke-base-x25519-sha256-aes128gcm` (§10.4; also sealed introductions, kind `messaging`) | |
| `body-unseal-failed` | `enc`/`ct` not base64url, or the HPKE open fails — wrong key, tampered, or AAD of another message (§10.4) | |
| `sealed-plaintext-invalid` | the opened plaintext is not a §10.3 JSON object with at least one key, or its byte length is not a positive multiple of 256 (§10.4) | |
| `sealed-field-not-sealable` | the plaintext holds a key outside the type's sealable fields (§10.4 table) | |
| `sealed-field-in-clear` | a key is present both inside the seal and in clear (§10.4) | |
| `introduction-purpose-and-sealed` | an `introduction` carries both `purpose` and `sealed` (§19.4, v0.8) | |
| `revocation-subject-mismatch` / `revocation-signer-not-subject` | `delegation-revocation.from` ≠ `subject`; signed by a key other than the subject's (§7.4, v0.8; `context.signer_kid`) | |
| `lifetime-exceeded` / `deposit-class-unsupported` / `deposit-fields` / `object-too-large` / `mailbox-mode-unsupported` / `key-packages-empty` | Messaging Profile message rules (M§5; kind `messaging`) | `mailbox.unsupported-class` / — / — / `mailbox.object-too-large` / `mailbox.unsupported-mode` / — |
| `sender-mismatch` / `conversation-mismatch` / `ulid-sent-at-mismatch` / `personal-group-only` / `content-body` / `reaction-invalid` / `receipt-shape` | Messaging Profile content-object rules (M§8, M§10, M§12; kind `messaging`) | |
| `recorder-conversation-only` / `call-record-invalid` | the `call-record` object (Recording Profile C§9, v0.13; kind `messaging`) | |
| `successor-invalid` | successor group not created by a predecessor member, or adding outsiders (M§7.5; kind `messaging`) | |
| `mls-truncated` / `mls-length-invalid` / `mls-length-non-minimal` / `mls-trailing-bytes` | MLS extension wire encoding (RFC 9420 §2.1.2; kind `messaging`) | |
| `credential-type` / `credential-identity` / `delegation-missing` / `credential-key-mismatch` | MLS leaf authentication (M§6.2; kind `messaging`; also uses `delegation-invalid`/`-capability`/`-expired`) | |
| `blob-size-mismatch` / `blob-hash-mismatch` / `sealed-too-short` / `aead-open-failed` | AES-GCM formats (M§8.4, M§11.1, M§12.2; kind `messaging`) | |
| `expired` | `expires_at ≤ now` (§12.9: valid while `now < expires_at`, spec-gap 141) | `session.expired` on `invite` |
| `duplicate-id` | `id` already seen within the replay window (§12.9); never for a `reachability-hint` or a `presence` record, whose ids are not deduplicated (spec-gap 141) | |
| `ulid-issued-at-mismatch` | ULID timestamp component differs from `issued_at` by more than 300 s (§20.6, check 2) | |
| `version-unsupported` | §11 negotiation failed | one of the `session.unsupported-*` tokens |
| `schema-invalid` | payload fails its JSON Schema | |
| `unknown-type` | `type` is not a known message type | |
| `selection-not-subset` | `answer`/`reject` selection not ⊆ referenced offer (check 9) | |
| `subscription-lifetime-exceeded` | `expires_in` above the per-event cap (presence 3,600) (§9.3) | `policy.subscription-lifetime` on `error` (v0.7) |
| `presence-signer-mismatch` | a `presence` record whose `device` is present and is not `from` (P§3; v0.17, spec-gap 135) | `presence.signer-mismatch` on `error` |
| `presence-sealed-invalid` | a `presence` record carrying `sealed_state` whose `dsip.profiles` (a list) does not contain `presence/0.2`, whose `audience` is `main`, or whose `kid`'s scope (the part before its last `.`) is not its `audience` (`main` when it has none) (P§12.2; v0.17, spec-gaps 152, 157); checked after `presence-signer-mismatch` | `presence.sealed-invalid` on `error` |
| `rotation-subject-mismatch` | `key-rotation.from` ≠ `subject` (§7.5) | |
| `rotation-next-same-as-previous` | `key-rotation.next` = `previous` (§7.5) | |
| `rotation-signer-not-previous` | `key-rotation` signed by a method other than `previous` without `recovery: true` (§7.5; `context.signer_kid`) | |
| `introduction-too-large` | encoded introduction envelope > 4,096 bytes (§19.4) | |
| `grant-unknown-introduction` | `grant.session` references no known introduction (§19.4) and none of `context.held_grants` — the live grants the receiver holds from the signer's identity, which a grant may follow (spec-gap 150; absent = none) | |
| `hello-in-reply-to-mismatch` | relay `hello.in_reply_to` ≠ the client hello id actually sent (§13.2, §20.5) | |
| `hello-required` | session traffic before a verified `hello` (§13.2) | `transport.hello-required` |
| `hint-subject-mismatch` | DHT hint whose verified identity is not its `subject` (§8.3) | |
| `key-agreement-invalid` | DHT hint whose `key_agreement` member does not verify as a key agreement delegation of its `subject` (DHT Hints Profile §4; core §7.3; spec-gap 179); checked last, after `hint-subject-mismatch`, the version check and `schema-invalid` | |
| `binding-ice-mode` | `transports[].ice` absent or not `trickle` (B§2) | `media.unsupported` |
| `binding-sdp-missing` | webrtc descriptor without `sdp` (B§2) | `media.offer-required` on offers, `media.failed` on answers |
| `binding-sdp-invalid` | `sdp` is not SDP (B§2) | `media.unsupported` / `media.failed` |
| `binding-section-count` | live `m=` sections ≠ media descriptors; answer section count ≠ offer's (B§2.1) | `media.unsupported` / `media.failed` |
| `binding-extra-section` | an `m=application` section (B§2.1) | `media.unsupported` |
| `binding-kind-mismatch` / `binding-direction-mismatch` / `binding-codec-missing` | descriptor i and `m=` section i disagree (B§2.1) | `media.unsupported` / `media.failed` |
| `binding-encryption` | plain RTP profile (B§7) | `media.encryption-required` |
| `binding-rtcp-mux-missing` / `binding-fingerprint-missing` / `binding-ice-credentials-missing` | SDP profile violations (B§2.2) | `media.unsupported` / `media.failed` |
| `binding-setup-invalid` | offer not `actpass`, or answer not `active`/`passive` (B§3.3) | `media.unsupported` / `media.failed` |
| `binding-ice-restart` | a local re-offer changed the ICE credentials (B§5.4); a remote one is `reject media.unsupported` | |

## Pipeline order (normative for parity)

When several conditions hold at once, the verdict is the **first** failing
stage below. Stages 1–11 are the envelope pipeline (`kind: envelope`,
`transport`, `dht`); stages 12–14 run on decoded payloads (`kind: payload`
runs 13 only; `kind: semantic` runs 12–14).

1. `frame-too-large` (only when `input.frame` is present)
2. `envelope-shape`
3. `header-invalid` → `alg-unsupported` → `kid-invalid`
4. `kid-unresolvable`
5. `signature-invalid` — computed over the exact ASCII bytes `protected + "." + payload`
6. `payload-not-utf8` → `payload-not-json` → `payload-float` → `payload-shape`
7. `signer-mismatch` / `delegation-*` (binding `kid` to `from`; on `hello` with `on_behalf_of`, additionally binding `from` to `on_behalf_of`)
8. `expiry-order`
9. `introduction-validity` (introductions only) / `hint-validity` (reachability hints only) / `presence-validity` (presence records only) → `replay-window` → `expired`
10. `duplicate-id` (not for `reachability-hint` or `presence`)
11. `ulid-issued-at-mismatch`
11b. `hello-required` (transport binding state: `context.hello_verified` is `false` and the type is not `hello`)
12. `version-unsupported`
12b. Sealed body (§10.4, only when the payload has `sealed` and `context.unseal_key_hex` is present):
    `sealed-not-critical` → `sealed-alg-unsupported` → `body-unseal-failed` → `sealed-plaintext-invalid` →
    `sealed-field-not-sealable` → `sealed-field-in-clear`. A `sealed` that is not an object of three strings
    `alg`, `enc`, `ct`, or a payload whose `type`, `id`, `from` or `to` is not a string (the AAD inputs), is
    left for stage 13. A `dsip.critical` that is not an array lists nothing (`sealed-not-critical`). A type with
    no sealable fields admits none (`sealed-field-not-sealable` for any opened key). On success the opened fields replace `sealed` and stages 13–14
    run on the merged payload.
13. `unknown-type` → `schema-invalid`
14. Stateless semantic checks (`selection-not-subset`, `subscription-lifetime-exceeded`, `introduction-too-large`, `grant-unknown-introduction`, `hello-in-reply-to-mismatch`, `presence-signer-mismatch`, `rotation-*`)

Stage 13 also validates `info.data` against the binding schema named by `about` when the
receiver implements that binding (`transport:webrtc` → `webrtc-info-data.schema.json`); an
unimplemented `about` leaves `data` unchecked (§12.12: ignored, never rejected).

Registry membership (check 5) never rejects a well-formed token. It yields an
*effective* interpretation, reported on accept:

```json
"expect": {
  "verdict": "accept",
  "effective": { "reason": "session.failed", "fallback": "unknown-category" }
}
```

`fallback` ∈ `none` (registered), `category` (unregistered condition in a
known category), `unknown-category` (→ `session.failed`). For `answered_by`,
`effective.answered_by` is `service` for unknown values; for `progress`,
`effective.status` is `trying` for unknown values; for `presence` (P§5, v0.17), `effective.state` is the record's
`state` when registered (a sealed record, P§12, has no `state`: no `effective` is reported for it) (`available`, `busy`, `away`, `dnd`, `offline`) and otherwise `available`, with
`warnings: ["presence-state-unknown"]`. A registered token that the
registry does not list as valid on the carrying message type is accepted with
`warnings: ["reason-not-valid-on-type"]` (Impl decision; see spec-gap list). `effective.reason` is
reported for `reject`, `cancel`, `bye`, `error` and a `notify` that carries a `reason`; the "valid on"
column is not applied to `notify`, which §15.4 never lists (spec-gap 73).

## Kind: `envelope`

```json
"context": { "now": 1760000000, "did_documents": {}, "delegations": [], "seen_ids": [],
             "supported": {"core": "1.0", "profiles": ["interactive-media/1.0"], "extensions": []} },
"input":   { "envelope": {"protected": "...", "payload": "...", "signature": "..."} },
"expect":  { "verdict": "accept", "type": "invite", "signer": "did:key:z6Mk…", "identity": "did:key:z6Mk…" }
```

or `{"verdict": "reject", "code": "…", "reason": "…"}`. `signer` is the DID
of the `kid`; `identity` is the DID the signer acts for (`from`, or
`on_behalf_of` on `hello`).

## Kind: `payload`

```json
"input":  { "schema": "invite", "payload": { ... } },
"expect": { "verdict": "accept" } | { "verdict": "reject", "code": "schema-invalid" }
```

Schema `pattern`s are ECMA-262 regular expressions (JSON Schema 2020-12 §6.4). Two consequences:
- `$` matches only at the end of the string, so a value with a trailing newline fails `^…$`;
- `\d` is ASCII.

A validator built on another regex dialect must translate. Python's `re` needs both fixes; see
`tools/dsipvec/schema.py`.

## Kind: `semantic`

Input is a decoded payload plus whatever receiver context the check needs:

```json
"context": { "now": …, "supported": {…}, "offer": {"media": [...], "transports": [...]},
             "known_introductions": [], "held_grants": [], "sent_hello_id": "…", "encoded_size": 4200, "signer_kid": "did:…#key-1" },
"input":   { "payload": { ... } },
"expect":  { "verdict": "accept", "effective": {...}, "warnings": [...] } | { "verdict": "reject", "code": "…", "reason": "…" }
```

**Sealed bodies (§10.4, spec-gap 97).** `context.unseal_key_hex` is the X25519 private key of the DID in `to`
(32 bytes, hex; an identity's key agreement key, or a device `did:key`'s derived one): with it the receiver is the addressee and runs stage 12b. `context.router: true` makes the
receiver a router instead: it never opens a seal, and for a payload carrying `sealed` the critical-extension
rule of stage 12 does not apply to `sealed-body/1.0` (it binds the addressee); the clear part goes to stage 13
as it stands. With neither, a sealed payload is validated as it stands (the schemas admit `sealed` in place of
the type's sealable fields). Opening: HPKE (RFC 9180) base mode, DHKEM(X25519, HKDF-SHA256), HKDF-SHA256,
AES-128-GCM; `info` = `dsip sealed body v1`; AAD = `type ‖ 0x00 ‖ id ‖ 0x00 ‖ from ‖ 0x00 ‖ to` (UTF-8,
from the clear payload); `enc` and `ct` are base64url. Sealable fields: `invite` — `identity`, `intent`,
`policy`, `media`, `transports`; `answer`, `update` — `answered_by`, `media`, `policy`, `transports`; `info` —
`about`, `data`; `reject`, `cancel`, `bye` — `detail`. On accept, `effective.sealed` lists the opened keys,
sorted, beside whatever stage 14 reports.

Subset rule detail (check 9, Impl decision, spec-gap filed): each selected
media descriptor must match an offered descriptor on `type` (+ `purpose` when
present); every selected codec `id` must appear in that descriptor's offered
codecs; the selected direction must be an SDP-style answer to the offered
direction (`sendrecv`→any, `sendonly`→`recvonly|inactive`,
`recvonly`→`sendonly|inactive`, `inactive`→`inactive`); the single selected
transport `id` must be among the offered transports.

## Kind: `transport`

Same as `envelope`, with optional `input.frame` (the exact text frame, for the
size cap) and `context.sent_hello_id` / `context.hello_verified` for the
binding checks.

## Kind: `state`

A trace drives one **component** — an `endpoint` (holding any number of
sessions, each in initiator or responder role) or a forking `relay`
attempt — through a scripted event sequence with a mock clock.

```json
"context": {
  "component": "endpoint",
  "self": {"device": "did:key:…alice-phone", "identity": "did:key:…alice"},
  "identities": {"did:key:…bob-phone": "did:key:…bob", …},
  "start": 1760000000,
  "timers": {"t_establish": 15, "t_ring": 120, "t_ring_local": 120}
},
"input": { "steps": [ {"event": {...}, "expect": {...}}, … ] }
```

### Endpoint events

| event | meaning |
|---|---|
| `{"local":"place_call","session":ID,"to":DID}` | send `invite` (id = session), start T-Establish; when the endpoint holds a live grant with `dsip.invite` issued by `to`'s identity, the `send` carries `grant` (its id, §19.4); a grant past its `valid_until`, or one without `dsip.invite`, is not named (spec-gap 151); a session this endpoint already holds, live or ended, is `refused invalid-state` — an id is used once (§12.9; spec-gap 90) |
| `{"local":"cancel","session":ID}` | user abandons → `cancel user.cancelled` |
| `{"local":"hangup","session":ID,"reason":TOKEN?}` | `bye` with `reason` (default `user.hangup`; the media layer uses `media.failed`, B§8) |
| `{"local":"alert","session":ID,"ring_timeout":N?}` | policy admits invite → `progress ringing`, start T-Ring-Local |
| `{"local":"auto_reject","session":ID,"reason":TOKEN}` | policy rejects at OFFERED |
| `{"local":"accept","session":ID,"answered_by":V}` | user/service answers → `answer` |
| `{"local":"decline","session":ID,"reason"?}` | `reject` with `reason` (the host's choice, sent as given), or `user.declined` without one |
| `{"local":"update","session":ID,"id":ULID,"answered_by":V?}` | send `update` |
| `{"local":"answer_update","session":ID,"in_reply_to":ULID}` | answer the inbound outstanding update; the `send` carries `answered_by: "user"` (the schema requires it on every `answer`); with no matching inbound update → `refused no-pending-update` |
| `{"local":"reject_update","session":ID,"in_reply_to":ULID,"reason":TOKEN}` | reject it |
| `{"local":"info","session":ID}` | send `info` |
| `{"local":"introduce","id":ULID,"to":DID,"purpose":S,"contact_token":S?}` | send `introduction` (§19.4) |
| `{"local":"grant","introduction":ID,"id":ULID,"scope":[…],"valid_until":T,"presence_audience"?:A}` | issue a contact grant for a pending request: `send grant {to: the introducing IDENTITY, session: introduction id, id, scope, valid_until, presence_audience?}`; unknown request → `refused unknown-introduction`; then a `presence_audience` that is not a P§6 token (`[a-z][a-z0-9-]*`, at most 64 characters) → `refused invalid-audience`, nothing sent and the request kept (spec-gap 145) |
| `{"local":"reject_introduction","introduction":ID,"reason":TOKEN}` | decline a pending request (a policy choice): `send reject {to: the introducing IDENTITY, session, reason}` — the same addressee as a grant (§19.4, spec-gap 74) |
| `{"local":"revoke","grant":ID}` | revoke an issued grant (local policy): emits `{"revoke": [ID, …]}`, the grants whose `grant-revocation` the host sends its authority (P§7): the grant, then its rotation chain newest first (spec-gap 159; below), and the grant is gone from `grants_issued`; a grant not in `grants_issued` (unknown, or already followed) → `refused unknown-grant`. Then the rotation it causes (below) |
| `{"local":"regrant","grant":ID,"id":ULID,"scope":[…],"valid_until":T,"presence_audience"?:A}` | issue a grant that follows the live grant `grant` we issued, without an introduction (§19.4, spec-gap 150): first `{"revoke": [grant, …]}` as for `revoke` (P§7: the followed grant and its chain are revoked at the authority, spec-gap 159), then `send grant {to: that grant's grantee identity, session: the followed grant's id, id, scope, valid_until, presence_audience?, presence_keys?}`, and the followed grant is withdrawn (no longer in `grants_issued`); a grant we did not issue, already replaced or revoked, or whose `valid_until` has passed → `refused unknown-grant`; then an audience that is not a P§6 token → `refused invalid-audience`, nothing sent and the followed grant kept. Then the rotation it causes (below) |
| `{"local":"issue_token","token":S,"grant_id":ULID}` | pre-authorize an out-of-band contact token: the first introduction carrying it surfaces `introduction_received {token: true}` and is auto-granted at once — id `grant_id`, scope `["dsip.invite"]`, `valid_until` = now + 31,536,000 (Impl) — and the token is consumed |

`context.policy` = `{"first_contact_required": bool, "allow": [identity DIDs]}` (default: off).
With the policy on, an invite from an identity that is the grantee of no live `dsip.invite` grant and not in `allow`
is auto-rejected `policy.first-contact-required` without alerting. The invite's `grant` reference plays no part: it
neither admits an identity that is not the grantee nor refuses one that is (spec-gap 151). Introductions never create a session.
| `{"recv": MSG}` | a **verified** message arrives (signature, replay, schema already passed) |
| `{"advance": SECONDS}` | advance the mock clock; expired timers fire in deadline order, ties by start order |

`MSG` is an abbreviated payload: `type`, `id`, `from`, `session` (except
`invite`, whose `id` is the session), and the type-specific fields the
transition depends on (`status`, `ring_timeout`, `queue_timeout`, `reason`,
`answered_by`, `in_reply_to`, `about`, `expires_at` on `invite`, `to`).

### Endpoint presence keys (P§12.3, P§12.5; spec-gaps 157, 159, 161)

Opt-in: `context.presence_keys` = `{"sealed": [SCOPE, …], "t_rotate": N?, "grant_ids": [ULID, …]}`. Without it the
endpoint keeps no key state, no grant carries `presence_keys`, nothing rotates, and a received `presence` is ignored
(no emission); `revoke` and `regrant` still emit `{"revoke": […]}` (their chain is then always empty).

- **Scopes and epochs.** A scope is `main` or an audience tag; `sealed` lists the scopes this device seals (P§12.6).
  The device keeps a current epoch per scope: `main`, every sealed scope and any other scope a grant carries a key
  for start at 0; a scope it only learns of from a record starts at that record's epoch. `t_rotate` is T-Presence-Rotate, default 60, clamped to 0–3,600 (P§8).
  `grant_ids` are the ids the endpoint gives the grants it issues on its own (re-grants, below), taken in order;
  running out is an error in the vector.
- **Keys in a grant (P§12.3).** A grant the endpoint issues (`grant`, `regrant`, a re-grant; never a token's
  auto-grant, whose scope is `["dsip.invite"]`) carries `presence_keys` when its `scope` contains `dsip.subscribe` and
  `main` or its `presence_audience` is sealed. In a trace it is the list of key ids carried, abbreviating the HPKE
  object: `main.<epoch>`, then `<presence_audience>.<epoch>` when the grant has one, at the current epochs. The grant
  remembers which scopes it carried keys for.
- **Rotation (P§12.5, spec-gap 161).** A grant *ends* when it is revoked (`revoke`), when a `regrant` follows it,
  or when its `valid_until` is reached (`now ≥ valid_until`, spec-gap 141). An ending grant that carried keys makes
  each of those scopes *due*, except, for a `regrant`, a scope the new grant carries keys for. A due scope never rotated
  rotates at once; one last rotated at `r` rotates at once when `now ≥ r + t_rotate`, otherwise at `r + t_rotate`
  (a scope already waiting keeps its time). A grant ends once: revoking a grant whose `valid_until` was already reached
  makes nothing due.
- **Rotating.** At an instant, every scope due then rotates together: its epoch rises by one, its last rotation is now,
  and `{"keys": "rotated", "scope": S, "epoch": N}` is emitted per scope, `main` first, then tags in ascending order.
  Then each live grant in `grants_issued` (`valid_until > now`), in id order, that carried keys for any scope whose
  epoch just rose is **re-granted**, once: `send grant {to: its grantee, session: its id, id: the next of
  grant_ids, scope, valid_until, presence_audience?, presence_keys}` with the same `scope`, `valid_until` and
  `presence_audience` and the current key ids. The new grant takes the old one's place in `grants_issued`; the old one
  heads the new grant's **chain**, before the old grant's own chain. A re-grant is not an ending: nothing is due and
  nothing is revoked.
- **A sibling's epoch.** `{"recv": {"type": "presence", "from": DEVICE, "subject": S, "kid": K}}` is a verified record
  from a notify of our own watch (P§6 rule 1). When `S` is our identity and `K`'s epoch is above the current epoch of
  its scope (or the scope is new), the epoch becomes `K`'s, `{"keys": "seen", "scope", "epoch"}` is emitted, and live
  grants are re-granted as after a rotation. Anything else (another subject, no `kid`, an epoch not above ours) is
  ignored with no emission. Seeing an epoch is not a rotation: a scope waiting for its time still rotates then.
- **The grantee's side (P§12.4).** A received grant carrying `presence_keys` adds its key ids to those held from the
  grantor's identity; for each scope only the two highest epochs are kept. This needs no `context.presence_keys`.
- **`advance`.** Instants are taken in order up to the target: at each, the session timers due then fire (as above),
  then the grants whose `valid_until` it is end, in id order, then the scopes due rotate.

`expect.presence_keys` snapshots this state: `{"epochs": {SCOPE: N}, "due": {SCOPE: T}, "chains": {GRANT: [ID, …]},
"held": {IDENTITY: [KID, …]}}`. `chains` lists only grants in `grants_issued` with a non-empty chain, newest first;
`held` lists each grantor's key ids by scope (plain string order), then epoch.

### Relay events

| event | meaning |
|---|---|
| `{"relay":"invite","session":ID,"from":DID,"to":IDENTITY,"legs":[DEVICE,…]}` | fork an invite to the listed legs |
| `{"recv": MSG}` | message from a leg (`progress`/`answer`/`reject`) or the initiator (`cancel`) |
| `{"relay":"leg_expired","session":ID,"leg":DEVICE}` | relay's own per-leg delivery expiry |
| `{"relay":"bind"|"unbind","device":DEVICE,"identity":IDENTITY}` | a device (un)binds via `hello` (§13.2); binding flushes queued introductions |
| `{"recv": introduction}` / `{"recv": invite}` (without `legs`) | routed by the relay's bindings; introductions to unknown/offline identities are queued with no error (§19.4 anti-enumeration) |
| `{"recv": any}` to a *known* but unbound identity/device | queued (§13.3 store-and-forward) until `min(expires_at, context.offline_retention_s)` (default 86,400, the §13.3 RECOMMENDED value, when the context gives none), dropped at that instant (spec-gap 141); `advance` expires queues; `bind` flushes the identity's and the device's queues together in arrival order — the order the relay received them, whichever of the two each was addressed to (spec-gap 98) — turning queued invites into tracked legs |
| `{"advance": SECONDS}` | clock; expires queues, then silent legs, then forgets (below) |

**Silent legs expire with the invite (§12.7 rule 3, spec-gap 132).** After expiring queues, every `advance` expires each leg
that is still `delivered` and has never sent the attempt anything — no `progress`, `answer` or `reject` — once the
attempt's invite has expired (`expires_at ≤ now`, spec-gap 141: a second before `expires_at` it has not). A leg that has sent any of those
is not expired this way: it ends itself (a ringing leg rejects `user.no-answer` at T-Ring-Local). Attempts go in id order,
their legs in device order (spec-gap 89), and each attempt whose legs changed is then completed as §12.7 rule 6 says
(the most informative `reject` forwarded, or `send error transport.no-response`), so those emissions come in attempt
id order. This applies whatever the outcome: after an answer a silent leg still becomes `expired`, with nothing emitted.
An attempt forked by a `{"relay":"invite"}` event has no invite and expires legs only by `{"relay":"leg_expired"}`.
What counts as hearing from a leg is what the attempt itself handles: its `progress`, `answer` or `reject` without
`in_reply_to` (a message with `in_reply_to` is routed by `to` and leaves the leg silent). Expiring a silent leg is not
something the relay does *for* the attempt: it does not restart the 1800 s count below.

**What a relay forgets (§13.3, spec-gap 131).** After expiring queues, every `advance` drops, silently (no emission):
an **attempt** (and its invite) once more than 1800 s — the T-Queue hard cap, §12.9/§12.10 — have passed since the
relay last did anything for it: forked it (`{"relay":"invite"}` or a received `invite`), turned a queued invite into a
leg of it, added a leg mid-attempt, or received one of its attempt-scoped messages from a leg or its initiator (including
one it then screens with `drop`). The relay's own `{"relay":"leg_expired"}` does not count. Traffic the attempt does not handle — post-answer traffic, messages from a device that
is not a leg — does not count. At exactly 1800 s it is still held. From then on its session is routed by `to` like any
session the relay holds no attempt for (spec-gap 82), and a device that binds becomes no leg of it. And an **identity or device** that is *known* (§13.3) only through a past binding: one with no device bound now
and nothing queued for it is forgotten once its last binding ended (its last `unbind`) more than `offline_retention_s`
ago (strictly more: at exactly `offline_retention_s` it is still known); a forgotten recipient is never-seen again
(`send error transport.unknown-recipient` for session traffic, by identity and by device) until a device binds for it.
An identity is unbound from the moment its last bound device unbinds. A device stays known while it is bound however
long ago it bound.

### Expectation after each step

```json
"expect": {
  "emit": [ ...ordered emissions... ],
  "sessions": { ID: {"role":"initiator","state":"PROCEEDING","renegotiating":false,"outstanding_update":null} }
}
```

For the relay: `"attempts": { ID: {"legs": {DEVICE: "delivered|answered|rejected|expired|cancelled"}, "outcome": null|"answered"|"rejected"|"cancelled"|"no-response"} }`
(`cancelled`: the initiator withdrew and no leg is left outstanding; `no-response`: every leg expired and none rejected);
an attempt named with the value `null` is one the relay does not hold — never forked here, or forgotten (spec-gap 131). Optionally `"inbox": {RECIPIENT: count}` — every
envelope queued for an identity or device, of any type; recipients with nothing queued are absent.
When every leg ends without any leg having rejected there is nothing to forward: the relay speaks for itself,
`send error {to: the initiator, session, reason: transport.no-response, in_reply_to: the invite id}` (§12.7 rule 6, spec-gap 76).
An endpoint in INVITING or PROCEEDING that receives it ends the attempt (`timer stop` → `ui ended transport.no-response`,
no `cancel`); in any other state it is `ui error` like any other error. A forwarded `progress` carries its `status`. An `answer` is **never withheld**, whatever the leg's state: only the
initiator ends a leg that has answered (`bye session.already-answered` / `session.cancelled` / `session.failed`, below),
and the leg record moves only for a leg that was still outstanding — a cancelled, expired or rejected leg that answers stays
recorded as such, and the outcome is unchanged (spec-gap 86). A `progress` or `reject` from a leg that has already
terminated is `drop leg-terminated`: at an initiator that cannot see legs it would read as the attempt's own, and nobody
needs it.

The attempt record is used only for a leg's pre-answer traffic, a `cancel`, and the outcome. **Everything else is routed
by `to`** (§13.3, spec-gap 82) — post-answer traffic, traffic from a device that is not a leg, a `cancel` addressed to a
device that is not a leg, and any traffic for a session the relay holds no attempt for: `deliver` to the bound device
named, or to every device bound for the identity named, in device order; queued when the recipient is known and
offline; otherwise `send error transport.unknown-recipient` to the sender (`in_reply_to` the message's id). Nothing is
dropped for naming a session the relay does not know. A `cancel` whose `to` is one leg's device cancels that leg alone
(§12.11): the attempt goes on, and the identity's queued invite stays queued. A leg can be added while
`expires_at > now`. Queued envelopes that expire in the same step are reported in recipient order. Wherever one step
reaches several legs or attempts, it goes in device (DID) order and id order — the suite's order wherever a relay or
mailbox fans out: a `cancel` to the identity reaches its live legs in DID order, whatever order they were delivered
in, and a device that binds into several live attempts gets their invites in id order (spec-gap 89). An invite to an identity that has never bound here is answered `send error transport.unknown-recipient`.
For an endpoint, optionally `"contacts": {"allow": […], "grants_issued": […], "grants_held": […], "requests": […], "pending_sent": […]}` (sorted ids).

Only the sessions / attempts named in `expect` are compared (`{}` names none); `contacts`, `inbox`,
`publications` and `subscriptions` are compared in full when present. `emit` is compared exactly, in order.

### Emission vocabulary

| emission | fields |
|---|---|
| `{"send": {...}}` | `type`, `to`, `session`; plus `reason` (cancel/reject/bye/error), `status` (progress), `answered_by` (answer/update when set), `in_reply_to` (answer/reject/error when set), `id` only when the event supplied it |
| `{"deliver": {"leg": DEVICE, "type": …, "reason": …, "id": …}}` | relay forwards to a specific leg (`id` present when delivering a queued envelope or a leg added mid-attempt) |
| `{"dequeue": {"to": …, "type": …, "why": "expired"\|"cancelled"}}` | relay dropped a queued envelope (§13.3 boundary; the initiator's timers are the backstop) |
| `{"forward": {"type": …, "reason": …, "from": DEVICE}}` | relay forwards a leg message to the initiator |
| `{"timer": "start", "name": "T-Ring", "seconds": 120}` / `{"timer":"stop","name":…}` / `{"timer":"fire","name":…}` | timer lifecycle (`T-Establish`, `T-Ring`, `T-Queue`, `T-Ring-Local`); `stop` is emitted only for a running timer; a restart emits only `start` |
| `{"media": "start" \| "stop" \| "apply_update"}` | media-layer instruction |
| `{"ui": "progress", "status": …}` | caller-side ringing/queued/etc. |
| `{"ui": "answered", "answered_by": …}` | caller-side, including `screening` |
| `{"ui": "offered"}` | responder-side invite admitted to OFFERED |
| `{"ui": "update_offered"}` / `{"ui": "update_rejected", "reason": …}` | renegotiation surfaces |
| `{"ui": "missed_call"}` | responder surfaces a missed call (never on `session.answered-elsewhere`) |
| `{"ui": "ended", "reason": …}` | session reached ENDED because of a remote message or timer |
| `{"ui": "glare_retry"}` | equal-id glare; MAY retry after 1–4 s |
| `{"ui": "introduction_received", "from": IDENTITY, "token": true?}` | requests surface (§19.4) — never a ring |
| `{"ui": "granted", "by": IDENTITY}` / `{"ui": "introduction_rejected", "reason": …}` | sender-side outcomes. A received `grant` is held when its `session` names an introduction we sent (which is then no longer pending), or (spec-gap 150) a grant we hold from the same identity (the signer's) whose `valid_until` has not passed, which it then replaces in `grants_held`; otherwise `drop unknown-introduction` |
| `{"queue": {"to": IDENTITY, "type": "introduction"}}` | relay queued an introduction for an unbound identity |
| `{"ui": "error", "reason": …}` | a received `error` is surfaced; no state change |
| `{"info": {"about": …}}` | an `info` with a recognized `about` is handed to the binding |
| `{"refused": REASON}` | a local request was refused by the engine (`unknown-session` for any request about a session the endpoint does not hold, `update-pending`, `no-pending-update`, `unknown-introduction`, `invalid-audience`, `unknown-grant`) |
| `{"drop": REASON}` | message silently ignored (`ended-session`, `unknown-about`, `stale-update-reply`, `duplicate-introduction`, `unknown-introduction`) |

## Kind: `broadcast`

Receiver-side verification of a publication record and its provenance (§22).

```json
"input":  { "publication": ENVELOPE, "provenance": [ENVELOPE, …], "capabilities": {"codecs": […], "transports": […]} },
"expect": { "verdict": "accept", "type": "publish", "signer": …, "identity": …,
            "selected_variant": "main-opus" | null,
            "provenance": [ {"verdict":"accept","processor":…,"operation":…,"policy_violation"?:…} | {"verdict":"reject","code":…} ],
            "display": {"original_publisher": …, "delivered_by": […], "transcoded_by": […], "integrity_mode": "metadata-only"|"derivative-bound"} }
```

Extra codes: `publisher-mismatch` (record `publisher` ≠ verified identity), `stream-id-namespace`
(`stream_id` not under the publisher DID), and per-statement `provenance-unknown-publication`,
`provenance-stream-mismatch`, `provenance-processor-mismatch`, `provenance-variant-unknown`.
Provenance statements are the core `provenance` message (v0.7, §22.3; schema `provenance.schema.json`),
no extension declaration. The record's `integrity` (§22.2) is shown unless a verified transcode statement makes the
delivered stream `derivative-bound`; a selected variant's own `integrity` overrides the record's; unknown tokens fall back to `metadata-only`.

A verified statement's `policy_violation` is `redistribution` when the record's policy says `redistribution: "forbidden"`
(any operation), else `transcoding` for a `transcode` under `transcoding: "forbidden"`; absent otherwise. Its
A statement has no `integrity_mode` of its own (§22.3, spec-gap 77): the one integrity mode is `display.integrity_mode`. Statement checks run in this order after the envelope pipeline:
`provenance-unknown-publication` → `provenance-stream-mismatch` → `provenance-processor-mismatch` → `provenance-variant-unknown`
(`input_variant` only; the output variant is the processor's own).

### State components `authority` and `subscriber`

`authority` (a target's relay/domain endpoint, §9.3/§22): events `{"recv": publish|unpublish|subscribe|provenance|presence|grant-revocation}`,
`{"local":"policy","target":T,"mode":"public"|"allow","allow":[…],"audience"?}`, `{"local":"issue_capability","token":S,"target":T}`,
`{"relay":"bind"|"unbind","device","identity"}` (presence source), `advance`. Emissions: `send notify {to, subscription, seq, state, reason?, body}`,
`send reject {to, session, reason}`, `send error {to, in_reply_to, reason, retry_after?}`, `{"publication": {"stream", "state"}}`, `{"provenance": {"stream","processor"}}`,
`{"subscription": {"id","state": "replaced"|"terminated"}}`, `drop` reasons. Snapshots `publications`, `subscriptions` and
`presence`. A subscription is the subscribing device's (§9.3, spec-gap 177): a `subscribe` replaces, and one with
`expires_in: 0` terminates, the subscription with the same device (`from`), `target` and `events`; two devices of one
identity hold one each.

**Presence records** (Presence Profile P§3, P§4, P§8; v0.17, spec-gaps 134, 135). `context.identities` maps each device
to its identity; `context.presence_grace` is T-Presence-Grace (default 60). A received `presence` (`from`, `subject`,
`device?`, `state` or `kid` + `sealed_state`, `seq`, `issued_at`, `expires_at`) is refused with `send error {to: from, in_reply_to: id, reason}`,
the first that applies: `presence.signer-mismatch` (no `device`, `device` ≠ `from`, or `subject` ≠ the identity of
`from` in `context.identities`, the identity its delegation names) → `presence.lifetime` (`expires_at − issued_at` below 60 or above 3,600) → `presence.stale` (a record held for
`(subject, device)` with `seq` ≥ this one) → `policy.rate-limited` with `retry_after` = 5 − elapsed (a record of this
device accepted less than 5 s ago on the authority's clock, whether or not that record is still held). Otherwise it is accepted with no emission of its own: it
becomes the device's record and every presence subscription to the subject is notified.

The presence `body` is `{"event": "presence", "state": A}` plus `records` when any record is held for the subject:
`A` is `available` when any bound device of the subject holds no record, else `offline`; `records` lists every held
record of the subject as `{id, device, state, seq, expires_at}`, ordered by `device` (the trace's summary of each
record; on the wire a host carries the signed envelope, P§3). A subscription is notified on an
event exactly when it changes its subject's body: an accepted record, a dropped record, a bind or unbind. On `unbind` of
a device holding a record, the record is kept until the clock reaches unbind time + grace (with grace 0 it is dropped
at the unbind); the grace runs from the first unbind, so an `unbind` of a device already in its grace changes nothing,
and a record accepted from a device in its grace keeps the grace running; a `bind` of that device before then cancels
the drop. On `advance`, after subscription lapses and
publication expiry, every record with `expires_at` ≤ now and every record whose grace has run out (unbind time + grace
≤ now) is dropped, its `seq` forgotten, and each subject that lost one is notified once, subjects in order. Snapshot
`presence: {subject: {device: {seq, state, expires_at, grace_until?}}}`.

**Who may watch, audiences, shares** (P§6, P§7; v0.17, spec-gaps 144–147). A `subscribe` naming `presence` is admitted
by the first that applies, after the existing target-exists check (an unknown target is `policy.blocked` whatever is
presented): (1) the subscriber's identity is the target — `own`, sees every record; (2) the first entry of `claims`
of the form `{"type": "dsip-grant", "grant": G}` that admits, where `G` is the host's summary of the verified grant
envelope `{id, from, identity, to, scope, valid_until, presence_audience?, verified?}` (`identity` is the identity its
signer acts for; `verified: false` when its signature or delegation failed; a grant's replay window and delivery expiry
are not applied). It admits when `verified` is not false, `identity` = target, `to` = the subscriber's identity, `scope`
contains `dsip.subscribe`, `valid_until` > now, and (target, `id`) is not revoked; the subscription's audience is its
`presence_audience` and it records the grant; (3) a `capability` issued for the target; (4) a `policy` for the target
that admits (`public`, or the identity in `allow`), the audience being the policy's `audience`. With none of these, the
uniform `reject policy.blocked`. With **no policy** for a target only (1)–(3) admit: presence is private by default.
(A `subscribe` naming only `publication` keeps the publication rules: no policy admits. One naming `presence` and
`publication` is admitted by these rules, and the target-exists check is the publication one.) The target-exists check
is the existing one: for presence, a target is known when it is an identity in `context.identities`, has a bound device,
or the authority holds a policy or an issued capability for it (spec-gap 149 (a): what an authority issued or was told
about a target is knowledge of it, so a capability admits before its target ever binds); for publication, when it is
a published stream. A refused renewal leaves the earlier subscription as it
was, to lapse or end by itself.

A `presence` record MAY carry `audience`. Records are kept per `(subject, device, audience)` (absent = an audience of
its own): `presence.stale` compares `seq` within that key and the publish interval runs per `(device, audience)`. Each
record expires by itself; an unbind's grace is per device and, when it runs out, drops all the device's records. A
subscription sees the records with no `audience`, those whose `audience` equals its own, and, when `own`, all. Its body
is computed over what it sees: `records` (each summary with `audience` when it has one), ordered by device then audience
(none first), and the assertion `available` when any bound device of the subject holds no record the subscription sees,
else `offline`. Every event that may change presence (an accepted record, a bind, an unbind, an `advance` that drops
records) notifies exactly the subscriptions whose own body changed since their last notify. "Subscription order"
throughout is code-point order of subscription ids; across subjects (an `advance`), subjects in order, then
subscriptions in order. The unbind grace belongs to the device: once started it runs until it ends or the device binds
again, whatever its records do meanwhile (a record accepted during it is dropped with the others when it ends); a
device that unbinds holding no record starts none.

A received `grant-revocation` (`from`, `grant`, `grantee`, `valid_until`) is not answered: (the identity of `from`,
`grant`) is revoked until `valid_until`, and every subscription admitted by that grant whose target is that identity
gets `notify` `terminated` with `reason: policy.terminated`, in subscription order. `grantee` is informative: the match
is by the grant id and the revoking identity. On `advance`, one pass over the subscriptions in subscription order ends
each that lapsed (`session.expired`, which wins at the same instant) or whose admitting grant's `valid_until` ≤ now
(`policy.terminated`); then revocations whose `valid_until` ≤ now are forgotten; then publications expire and records
are dropped as above, so a subscription ended in this pass gets no notify for the drops. In the `presence` snapshot a record with an
audience is keyed `device/audience`. The `subscriptions` snapshot adds `own: true`, `grant` (the admitting grant's id)
and `audience` when present.

**Sealed records** (P§12.6; v0.17, spec-gaps 152–157). A record carrying `kid` and `sealed_state` in place of `state`
is checked, kept, expired and routed exactly as a plain one (the checks above read only `from`, `subject`, `device`,
`audience`, `seq`, `issued_at`, `expires_at`). Its summary in a body carries `kid` and `sealed_state` in place of
`state` (`{id, device, seq, expires_at, state | kid + sealed_state, audience?}`), and its `presence` snapshot entry
`kid` in place of `state` (`{seq, kid, expires_at, grace_until?}`). A `subscribe` MAY carry `profiles`, the
`dsip.profiles` of the envelope: a subscription whose `subscribe` lists `presence/0.2` there reads sealed records
(snapshot `sealed: true`); any other, `own` included, sees no sealed record at all — they are left out of its
`records`, and in its assertion their devices count as holding no record it sees.

`subscriber`: `{"local":"subscribe","id","to","target","events","expires_in"}`, `{"recv": notify|reject}`, `advance`.
Emissions: `send subscribe`, `{"ui":"notify","event","state"}`, `{"ui":"subscription_terminated","reason"}`,
`{"ui":"subscription_rejected","reason"}`, `{"ui":"subscription_lapsed","subscription"}`, `drop` (`stale-seq`,
`terminated-subscription`, `unknown-subscription`). Snapshot `subscriptions: {id: {target, state, seq}}`.

## Kind: `media-binding`

WebRTC Media Binding 1.0 (`v1.0/dsip-webrtc-media-binding-v1.0.md`) conformance, below the
envelope pipeline: inputs are decoded payloads or event traces. `input.check` selects:

| check | input | expect |
|---|---|---|
| `offer` | `payload` = an `invite`/`update` body (`media`, `transports`) | verdict (B§2, B§2.1, B§2.2) |
| `answer` | `offer` + `payload` (an `answer` body with `from`) | verdict (B§2.1, B§3.1, B§3.3) |
| `role` | `offer_setup`, `answer_setup` | `{"verdict":"accept","offerer":"server\|client","answerer":…}` or verdict (B§3.3) |
| `candidates` | `steps` of `local_candidate` / `gathering_complete` / `active` / `remote_description` / `remote_info{from,candidates,end_of_candidates}` / `session_end`; `context.peer` | per-step `emit`: `buffer{local\|remote,n}`, `send_info{candidates,end_of_candidates}`, `apply n`, `remote_end`, `ignore{after-end\|not-party\|ended}`, `drop_buffered n` (B§4.2–B§4.4) |
| `renegotiation` | `steps` of `local_reoffer{ufrag}` / `remote_answer` / `remote_reject` / `remote_reoffer{ufrag}` / `answer_update`; `context.ufrag` | per-step `emit`: `local_description{pending\|current}`, `apply`, `rollback`, `reject{reason,detail}`, `error binding-ice-restart` (B§5) |
| `one-answer` | `offer` + `answers[]` | `{"applied": DID, "legs": [{from, applied\|bye[,code]}]}` — first valid answer applied, earlier invalid legs `bye media.failed`, later legs `bye session.already-answered` (B§6.1) |

Offer/answer checks run in this order, first failure wins: `binding-ice-mode` → `binding-sdp-missing` →
`binding-sdp-invalid` → `binding-extra-section` → `binding-section-count` → per live section in order
`binding-kind-mismatch` → `binding-direction-mismatch` → `binding-codec-missing` → then per live section
`binding-encryption` → `binding-rtcp-mux-missing` → `binding-fingerprint-missing` → `binding-ice-credentials-missing` →
`binding-setup-invalid`. Almost every vector breaks exactly one rule, so of this order the suite itself pins only `binding-extra-section`
before `binding-section-count`; the rest is the order the implementations share. A live section is an `m=` line whose port is not 0; attributes fall back to the session level.
An offer or answer that does not select `transport:webrtc` is `{"verdict":"accept","binding":"not-webrtc"}`.
Trace checks (`candidates`, `renegotiation`) put their expectations in `expect.steps[i].emit`, parallel to
`input.steps[i].event` — unlike kind `state`, where each step carries its own `expect`.

## Kind: `trust`

The lines a client shows for who is on the other side (§18.1: the basis of verification, never a generic badge).
The spec gives the *form* of each line; the exact text below is this suite's and is compared as a string.
`expect` is the string itself (or `null`), not an object. `input.check` selects:

| check | input | expect |
|---|---|---|
| `basis` | `identity` (DID), `claims` | with a gateway `tel` claim (the first `tel` claim whose `verifier` is a string; it outranks the carrying identity's own basis — a `tel` claim with a `binding` (N§4) is the identity's own number and never changes the basis): `Gateway attested by <verifier> · STIR attestation <A\|B\|C> (verified\|unverified)`, or `… · no attestation` when `attestation` is `none`; `<verifier>` is the host of the claim's `did:web` verifier. Otherwise `Self-issued identity` (`did:key`), `Domain verified (<did>)` (`did:web`), `Unrecognized identity method` |
| `tel-caller` | `claim` | `PSTN caller <number>`, plus ` · <cnam>` when the claim has one; `null` for a claim that is not `tel`, or has no string `verifier` (a caller's own bound number, N§4, is not a PSTN caller) |
| `downgrade` | `losses` (tokens of the gateway `downgrade` check) | `Trust downgraded crossing the gateway (§6.3)`, then `: ` and the losses joined by `; ` — `no-srtp-on-trunk` → `media is not encrypted on the PSTN trunk`, `identity-not-assertable` → `your identity could not be asserted into the PSTN`, `no-attestation` → `the caller carried no verified attestation`, `policy-unenforceable` → `your media policy cannot be enforced past the gateway`, `recording-not-disclosed` → `the PSTN party was not told this call is recorded` (spec-gap 133) |

## Kind: `gateway`

Phase 4 (`impl/docs/dsip_gateway_plan.md` §8): the normative tables the Gateway Profile will
carry, pinned before the gateway exists. `input.check` selects:

| check | input | expect |
|---|---|---|
| `reason-inbound` | `sip_status`?, `q850`?, `phase` (`pre-answer`\|`active`\|`transport`), `moved_to`? | `{reason, carry: reject\|bye\|error, detail?}` — Q.850 cause wins over the status; unmappable → `gateway.mapped`; BYE without Reason → `user.hangup`; attempt-phase tokens arriving while ACTIVE become `gateway.mapped` (§15.5) |
| `reason-outbound` | `reason`, `phase` | pre-answer: `{status, q850?, reason_header: {protocol: "DSIP", text}, retry_after?}`; active: `{method: "BYE", q850, reason_header}` — every crossing carries `Reason: DSIP;text=<token>`; unregistered tokens fall back by category (§15.1) |
| `sdp-to-descriptors` | trunk `sdp` | `{media: [descriptors], srtp: none\|sdes\|dtls}` or `{error}` |
| `descriptors-to-sdp` | DSIP `media` | `{m_lines: [{kind, encodings, direction}]}` |
| `claims` | `from_tn`, `identity` (`attest`, `verified`, `orig_tn`)?, `cnam`? | `{claim: {type: tel, number, attestation, verified, verifier, cnam?}, trust_basis}` (§18.1: a basis line, never a badge; `orig` mismatch discards the attestation) |
| `downgrade` | `facts` (`direction`, `trunk_srtp`, `identity_assertable`, `attestation`, `policy_present`, `recording_declared`) | `{downgraded, lost: [no-srtp-on-trunk \| identity-not-assertable \| no-attestation \| policy-unenforceable \| recording-not-disclosed]}` (§6.3), in that order; `recording-not-disclosed` when `recording_declared` is true, in either direction (spec-gap 133) |
| `trace` | `steps` of `{dsip: MSG}` / `{sip: {status}\|{request, …}}` / `{timer: "C"}`; `context.direction`, `context.early_media` | per-step `emit` (what each leg is told: `{sip: "INVITE"\|"ACK"\|"CANCEL"\|{response, direction?, q850?, reason_header?}\|{request, …}}`, `{dsip: {local: …}}`, `{media: bridge\|release}`) and `state: {dsip, sip}` |

Details the table leaves out, all part of the contract:

- **The gateway's identity is fixed**: `did:web:gw.example` is the `verifier` of every `tel` claim, and `trust_basis` is the
  kind-`trust` `basis` line for that claim. `cnam` is carried only when given. A `moved_to` turns `identity.not-in-service`
  into `identity.moved` with `detail` = the target; otherwise `detail` is `Q.850 <n>` when a cause was given and mapped (or
  when there is no status), else `SIP <status>`. `phase` defaults to `pre-answer`.
- **Attempt tokens** that become `gateway.mapped` once ACTIVE: `endpoint.busy`, `endpoint.unavailable`, `user.declined`,
  `identity.unknown`, `identity.not-in-service`, `identity.moved`, `session.cancelled`, `policy.blocked` (spec-gap 78).
  `user.hangup`, `media.*`, `gateway.*` and `session.timeout` are reported as they map.
- **Outbound causes**: an unregistered token takes its category's status *and* the cause of that category's
  representative row — `user` 603/21, `endpoint` 480/18, `identity` 404/1, `session` 500/41, `media` 488/65, `policy` 403/21,
  `transport` 503/41, `gateway` 503/38; an unrecognized category is `session.failed`, 500/41 (spec-gap 79). A BYE carries
  cause 16 for `user.hangup`, `session.already-answered` and `session.cancelled`, 47 for `media.failed`, 31 for
  `policy.terminated`; any other registered token keeps its own row's cause (`session.timeout` → 102), and an
  unregistered token is 16 — category fallback is a pre-answer rule.
  `retry_after: true` appears only for `policy.rate-limited`.
- `downgrade-error` (input `facts`) is the `detail` of the informational `error gateway.downgraded` (the core error
  schema admits an object detail for it, spec-gap 112; `payload/error-detail-object`): `{losses: […]}`, or
  `null` when nothing was lost. Losses are listed in G§7 table order; `no-attestation` is inbound-only,
  `identity-not-assertable` outbound-only.
- `trace` keeps expectations in `expect.steps[i]` = `{emit, state}`, parallel to `input.steps[i].event`. States — DSIP leg:
  `inviting`/`proceeding` (outbound), `offered`/`alerting` (inbound), `active`, `ended`; SIP leg: `calling`, `early`,
  `confirmed`, `terminated`. The DSIP leg is told things as the endpoint engine's own local events: `place_call {claims,
  trust_basis}`, `alert`, `accept {answered_by: gateway}`, `auto_reject {reason, detail}`, `cancel`, `hangup {reason}`,
  `update {direction}`, `info {about, data}`. What is not carried is `{"ignore": TEXT}` with exactly: `dsip info <about>`,
  `dsip dtmf outside the established call`, `sip dtmf outside the established call`. A SIP request is answered before the
  DSIP leg is told (`200` then `hangup`; `200`, `cancel`, then `487`); a 2xx is ACKed before anything else.

## Kind: `messaging`

DSIP Messaging Profile 1.0 (`v1.0/dsip-messaging-profile-v1.0.md`, cited `M§n`), tranche 1.
Written **before** any implementation. The profile schema set is staged at
`v1.0/dsip-messaging-schemas-draft/` (generated, freshness-checked like the core set). MLS is
abstracted: traces carry what a hub or mailbox observes (epoch, commit adds/removes, validity, a
digest of the MLS bytes), just as relay traces abstract signatures. `input.check` selects:

| check | input | expect |
|---|---|---|
| `payload` | `schema`, `payload` | `accept` / `schema-invalid` |
| `message` | a profile message `payload` | `accept`, or the first failing rule: `unknown-type` → `schema-invalid` → `lifetime-exceeded` (> 60 s; ephemeral > 10 s) → `deposit-class-unsupported` (`mailbox.unsupported-class`) → `deposit-fields` (M§5.2 class table) → `object-too-large` (`mailbox.object-too-large`, decoded length > 24,576 computed as `len·3/4`); `mailbox-mode-unsupported` (`mailbox.unsupported-mode`); `key-packages-empty` |
| `object` | a decrypted content `object`; `context.conversation`, `conversation_kind`, `leaf_identity` | `payload-float` → unknown object `accept {effective: {render: ignore}}` → `schema-invalid` → `sender-mismatch` → `conversation-mismatch` → `ulid-sent-at-mismatch` (> 300 s) → `personal-group-only` (`archive-key`, `call-event`, `recording-acceptance`); `sender-mismatch` and `conversation-mismatch` apply to `content`, `receipt` and `activity` only (a `read` receipt in the personal group, and every `recording-acceptance`, name the conversation they describe, M§10.5, C§5); content: `content-body` (for `device-event` and `alarm-ack`, the shapes under kind `device-events`, **Content bodies**), `delegation-capability` (a `device-event` whose `context.leaf_capabilities`, the capabilities of the sender leaf's device delegation, lacks `dsip.events`; absent is none; E§2, spec-gap 165), `reaction-invalid`, `accept {effective: {kind, purpose}}` (unknown kind → `file` with a blob, else `unsupported`; unknown purpose → `message`); receipt: `receipt-shape`, `effective.receipt` or `render: ignore`; activity: `effective.activity` (unknown → `active`); `call-record` (C§9, v0.13), after `schema-invalid`, with `context.leaf_device`: `sender-mismatch` when its `device` is not `leaf_device` → `recorder-conversation-only` when `conversation_kind` is not `direct` → `call-record-invalid` when `answered_at` is present and `outcome` is not `answered`, or absent and `outcome` is `answered`, or `invited_at` ≤ `answered_at` (when present) ≤ `ended_at` does not hold → `accept {effective: {render: ignore, store: call-record}}` |
| `conversation-ext` | `extension` | `schema-invalid` or `effective.kind` (unknown → `group`) |
| `blob-replicate` | `mode`, `max_blob_bytes`, `stored`, `entry {uri, sha256, size}`, `fetched? {status, sha256, size}`, `attempt?`, `max_attempts?` | `{action: fetch\|skip\|store\|discard, reason?, retry?}` (M§8.4 rule 6, spec-gaps 65 and 67) |
| `blob-fetch` | `blob {sha256, size}` (the content's), `tried [{uri, status, sha256?, size?}]` (each source's result, in the order tried), `attempt?` (default 1), `max_attempts?` (default 5) | the first `tried` with status 200 and matching `sha256` and `size` → `{action: play, source: uri}`; otherwise, if any `tried` has a status other than 200, or `tried` is empty → `{action: retry, reason: unavailable}` while `attempt < max_attempts`, else `{action: give-up, reason: unavailable}`; otherwise (every source served other bytes) → `{action: give-up, reason: mismatch}` (M§8.4 "Fetching", spec-gap 106) |
| `items-blobs` | `blob_endpoint`, `stored`, `manifest` | `{blobs}` with held entries at the mailbox's endpoint (spec-gap 65) |
| `blob-sources` | `blob` (content), `manifest` | `{sources: [uri]}` in fetch order (M§8.4 rules 6–7, spec-gap 65) |
| `call-event` | `alerted`, `answered_here`, `ended_by` (`local`\|`remote`), `reason` | `{send, outcome?}` (M§13.3, spec-gap 63) |
| `peer-timeline` | `content: [{id, at}]` (seq order), `calls: [{session, at, outcome}]` (seq order) | `{timeline: [content:id\|call:session], collapsed}` (M§13.3, spec-gap 63) |
| `external-join` | `kind`, `owner?`, `roster` (identities), `joiner {identity, device}`, `adds`, `removes` | `accept`, or `external-join-adds` / `external-join-not-member` / `external-join-removes-other` (M§6.8, spec-gap 62) |
| `leave-proposals` | `me` (this device's identity), `proposer {identity, device}`, `removes [{identity, device}]` (the Remove proposals that proposer's identity has pending in this epoch, together), `others` (how many of its pending proposals are not Remove), `roster [{identity, device}]` (the group's leaves) | the first that applies: `others` > 0 → `{action: ignore, reason: not-a-leave}`; a remove whose `identity` is not the proposer's, or whose `device` is not a leaf of that identity in `roster` → `{action: ignore, reason: not-own-leaves}`; the removed devices are not every leaf of the proposer's identity → `{action: wait}`; `proposer.identity` = `me` → `{action: left}`; otherwise `{action: commit}` (M§7.3 "Leaving", spec-gap 125) |
| `roster-change` | `committer` (the committing leaf's identity; empty when it no longer authenticates), `roster [{identity, device}]` (the group's leaves before the commit), `adds [{identity, device}]`, `removes [{identity, device, delegation_valid?}]` (`delegation_valid` false when the removed leaf no longer verifies, M§6.2; absent means true) | the first that applies: an add whose `identity` is a member identity in `roster` other than `committer` → `roster-adds-other-devices`; for an identity other than `committer` with removes, unless its removes cover every one of its leaves in `roster` or every one of them has `delegation_valid` false → `roster-removes-part-of-identity`; otherwise `accept`. Every member checks it on every commit before merging and does not merge one that fails; the hub refuses such a commit `policy.blocked` (M§7.3, spec-gap 126) |
| `conversation-update` | `before`, `after` (`dsip_conversation` values) | `schema-invalid`, `conversation-immutable` (conversation, kind or successor_of changed), or `effective {moves_to: did\|null, hub}` (M§7.4, spec-gap 60) |
| `mailbox-select` | `document_entries`, `hint_entries`, optional `reachable` (mailbox DIDs that accept a connection) | `{source: did-document\|hint\|null, selected, order, sync_targets, discarded}` (M§4.2, §8.1) |
| `mailbox-switch` | `established {mailbox, source}`, `candidate {mailbox, source}` | `{switch, reason: unchanged\|hint-sourced\|did-document}` (M§4.2, M§15.4) |
| `mls-extension-encode` | `extension_type`, `data_hex` | `{hex}` — `uint16 type ‖ minimal RFC 9420 §2.1.2 length ‖ data` (M§17 codepoints `0xF0D1`, `0xF0D2`) |
| `mls-extension-decode` | `hex` | `accept {extension_type, data_hex}` or `mls-truncated` / `mls-length-invalid` (0b11 prefix) / `mls-length-non-minimal` / `mls-trailing-bytes` |
| `mls-credential` | `credential {credential_type, identity_hex}`, `signature_key_hex`, `extensions [{extension_type, data_hex}]`; standard `context` | `accept {identity, device}` or, in order, `credential-type` → `credential-identity` → `delegation-missing` → `delegation-invalid` → `delegation-capability` (needs `dsip.messaging`) → `delegation-expired` → `credential-key-mismatch` (M§6.2) |
| `mls-conversation-bytes` | `data_hex` | `payload-not-utf8` → `payload-not-json` → `payload-float` → `schema-invalid`, or `effective.kind` (M§6.3) |
| `seal` | `use` (`blob`\|`activity`\|`archive`), `key_hex`, `nonce_hex`, `plaintext_hex`, `group_hex` + `epoch`/`seq` | `{sealed_hex}` = nonce ‖ AES-256-GCM ciphertext ‖ tag; AAD none / `group ‖ u64be(epoch)` / `group ‖ u64be(seq)` (M§8.4, M§11.1, M§12.2) |
| `open` | as `seal` with `sealed_hex`; blobs add `size`, `sha256` | `accept {plaintext_hex}` or `blob-size-mismatch` → `blob-hash-mismatch` (blobs) → `sealed-too-short` → `aead-open-failed` |
| `voicemail-offer` | `voicemail` (the callee's advertisement or null), `can_send`, `outcome {type: reject\|cancel, reason}`, optional `call_video` (the attempt's `invite` offered video; absent is false) and `accepts` (the callee's entry's; absent lists nothing) | `{offer, kind?, max_duration_s?}` — reject `user.no-answer`/`user.declined`/`endpoint.busy`/`endpoint.unavailable`, the caller's `cancel session.timeout`, or an **unregistered** `endpoint.*` token (M§13.2); with an offer, `kind` is `video` when `call_video` and `accepts` has `video`, else `audio` (spec-gap 184) |
| `direct-select` | `candidates [{conversation, issued_at}]` | `{winner, discarded}` — lowest ULID among candidates passing the 300 s ULID/`issued_at` check (M§7.2) |
| `successor-check` | `predecessor_roster`, `creator`, `roster` | `accept` or `successor-invalid` (M§7.5) |
| `successor-select` | `candidates [group_id base64url]` | `{winner, discarded}` — lowest decoded ULID; non-ULID ids discarded (M§7.5) |
| `client-trace` | `steps` of `{sync: {items: [{seq, object}]}}` / `{restore: {items}}` (spec-gap 64: rendering state only) / `{read: {through}}` / `{play: {id}}` / `{activity: {activity, state}}` / `{advance: s}`; `context.me`, `policy {delivered, read, played, activity}`, `member_identities` | per step `emit` (`archive {seq}` for a receipt that changed rendering (spec-gap 64), `send {to: conversation\|personal, receipt, targets\|through}` / `send {to, activity, state}`) and `state {timeline, delivered, played, read_through}` (M§10, M§11.2, M§8.5) |
| `gap-trace` | `steps` of `{item: {seq, class}}` / `{advance: s}`; `context.contiguous`, `gap_timeout?` (spec-gap 69) | per step `emit` (`process`, `hold`, `duplicate`, `rejoin {held}`) and `state {contiguous, held}` (M§6.5) |
| `resume-trace` | `steps` of `{items: {items: [{cursor, class, group, seq?, sibling?}], crash_at?}}` / `{sent: {group, seq}}` / `{rejoined: {group, seq}}` (spec-gap 69; a join: the group is joined from then on, at that `seq`) / `{removed: {group}}` (spec-gap 127: a commit removed this device's identity; the group is no longer joined, its positions stay) / `{sync: {}}` / `{restart: {}}` / `{cursor_invalid: {}}` / `{too_large: {}}` (spec-gap 180: the mailbox answered the last `sync` with an envelope over the cap; the device halves its `limit`, at least 1, and syncs from the same cursor; already at 1 it emits `backoff` and syncs at 1); `context.cursor`, `groups`, `joined`, optional `limit` (the device's own; when present every `sync` emitted carries the current `limit`, which `restart` returns to `context.limit`: it is not durable state); a non-sibling `welcome` with `seq` sets the group's position to it, one without leaves the first sequenced item processed to set it (spec-gap 83) | per step `emit` (`process`, `duplicate`, `sibling`, `crash`, `backoff`, `sync {since, ack_through?, limit?}`) and `state {cursor, groups: {group: {contiguous, seen}}, joined}` (M§5.4, M§8.5; spec-gap 44) |
| `items-pages` | `limit`, `items` of `{cursor, stored_at, class, source, group, seq, mls_bytes}`; `context.mailbox_key` (a fixture key name), `device`, `now`. The mailbox holds the items (each `mls` is `mls_bytes` zero bytes, base64url) and answers a `sync` from `null` with `items` envelopes signed by `mailbox_key`, `from` its `did:key`, `to` `device`; the device syncs again from each `next` until it is `null`. Where the pages split is the mailbox's choice | `{cursors, fit, within_limit, next_chain}`: the cursors delivered, in order; every envelope's frame ≤ 65,536 bytes (§13.2); every page ≤ `limit` items; every page but the last non-empty with `next` its last cursor, the last with `next: null` (M§5.4, spec-gap 180) |
| `commit-retry-trace` | `steps` of `{answer: {reason?}}` / `{synced: {still_needed, hub_moved?}}`; `context.max_attempts` | per step `emit` (`merge`, `discard`, `sync`, `repropose {attempt}`, `done`, `surface`) and `state {attempt, state}` (M§6.5, spec-gap 58; `mailbox.unknown-group` retried only when `hub_moved`, spec-gap 60) |
| `successor-trace` | `steps` of `{welcome: {group, successor_of, creator, roster}}` / `{create: {predecessor}}` / `{created: {group, successor_of}}`; `context.groups` (group → roster by identity) | per step `emit` (`join`, `decline`, `leave`, `first_contact`, `create {successor_of, roster}`, `use`, `refuse`) and `state {predecessor: {successor, candidates}}` (M§7.5, spec-gap 61) |
| `history-trace` | `steps` of `{archive: {cursor, akid, group, seq, id, object?}}` / `{archive_key: {akid, created_at}}` / `{mls: {group, seq, epoch, id, object?}}` / `{sent: {group, seq, id, object?}}` / `{joined: {group, epoch}}`; `object` is the object's type: absent or `content` is a timeline entry, `receipt` or `call-event` is state (archived and applied once by `id`, never in the timeline; spec-gaps 63, 64, 68), wherever it came from; `context.keys`, `joined` | per step `emit` (`hold`, `show`, `apply` (a receipt or call event, spec-gaps 63–64, 68), `duplicate`, `prejoin`, `archive {group, seq, akid}`) and `state {timeline, held, current_akid}` (M§12.2, M§12.3, M§8.5) |
| `hub-trace` | `steps` of `{deposit: {id, device, identity, class, epoch?, digest, commit?: {adds, removes, valid?, external?, moves_to?}, expires_at?, handover_seq?, view?: {epoch, roster}}}` / `{ack: {identity, seq, class?}}` (`class: welcome` acknowledges the welcome queue, spec-gap 66) / `{advance: s}` / `{restart: {}}` (spec-gap 59: full state survives; every unacknowledged queue head is re-sent); a commit with `moves_to` leaves the hub refusing the group (spec-gap 60). **Return** (spec-gap 128): while moved, a `group-info` deposit carrying `handover_seq` brings the group back; its `view` is the epoch and roster of the GroupInfo, which names this hub. It is refused `policy.blocked` when the depositor's identity is not in `view.roster`, or when `handover_seq` is below the hub's `next_seq` (a seq would be given twice). Otherwise the hub is no longer moved; its epoch and roster become the view's, `next_seq` becomes `handover_seq` + 1, and it holds a GroupInfo. Its queues and welcome holds are kept and drain as before. It answers `accepted` with no seq, then fans the group-info out to every identity of the new roster, in identity order. Every other deposit while moved, a `group-info` without `handover_seq` included, is still `mailbox.unknown-group`; `context.epoch`, `roster`, `kind`, `owner?`, `mls_retention_s?` (default 2,592,000). The hub's clock is `context.now` plus every `advance` so far; an `ephemeral` whose `expires_at` is at or before it is dropped silently (M§11.2, spec-gap 141). **Retention** (spec-gap 119): per member identity the hub keeps a clock over everything queued for it, items and welcome together. It starts when that identity's queues go from all empty to not, restarts at every acknowledgement of a queue head that leaves something queued, and stops when they are empty again. An acknowledgement that is not of a head changes nothing. At an `advance` that brings an identity's clock to `mls_retention_s` or beyond, the hub drops every queue it holds for that identity, welcome included, and lifts its welcome hold; the identity stays in the roster, and what is sequenced afterwards is queued and fanned out to it as to any member (a returning device re-joins by external commit, M§6.8). Several identities are dropped in identity order. The clock survives `restart` | per step `emit` (`accepted {to, in_reply_to, seq, duplicate?}`, `error {to, in_reply_to, reason}`, `fanout {to, seq, class}` (a welcome carries the commit's seq, spec-gap 66), `forward {to, class: ephemeral}`, `dropped {identity, pending, welcomes}` (the seqs that were queued, in order)) and `state {epoch, next_seq, roster, pending, welcomes}` |
| `mailbox-trace` | `steps` of `welcome`, `hub_deposit`, `sync`, `unbind`, `config`, `archive`, `kp_upload`, `kp_fetch`, `advance`, `restart` (spec-gap 59: durable state survives, live bindings do not); a `hub_deposit` whose `seq` is at or below the group's highest stored is a redelivery (`accepted` with `duplicate`, and the retained item's cursor — found by group and seq, across a registration the owner left and made again, never an archive record's: spec-gap 92); a `config` group naming another `hub` with `handover_seq` moves the registration (spec-gap 60); a `kp_fetch` with `successor_of` naming a registered group needs no grant (spec-gap 61); `context.owner`, `serves`, `devices`, `mode`, `admit`, `groups`, `key_packages`, `pending_group_ttl`, `pending_group_max_items`, optional `quota_bytes` (spec-gap 99: a `welcome`, a stored `hub_deposit` or an `archive` may carry `size`; when the bytes of the retained items plus `size` would exceed `quota_bytes`, the deposit is refused `mailbox.quota-exceeded` — after the duplicate checks, so a redelivery is never refused, and before anything is stored or registered — a `group-info` that would replace the group's previous one is checked with the previous one still counted; every other refusal of that deposit (pending-group bound, hub move, queue-mode archive) comes first; `first_contact` items are never counted or refused for quota; the quota survives `restart`) | per step `emit` (`accepted {to, in_reply_to, cursor?, duplicate?}`, `error`, `items {to, in_reply_to, cursors, next}`, `push {to, cursor}` / `push {to, class: ephemeral}`, `key_packages {to, in_reply_to, devices}`) and `state {items: [cursor], groups: {group: pending\|joined}, key_packages}` (plus `used_bytes`, the sum of the retained items' `size`, when `quota_bytes` is set) |

Checks the table above did not list (found by the second implementation; all are in the suite):

| check | input | expect |
|---|---|---|
| `introduction` | a core `introduction` `payload` as the profile uses it | core stage 13 then 14 (`schema-invalid`, `introduction-purpose-and-sealed`), or `accept {effective: {sealed: bool}}` (M§14.1) |
| `sealed-introduction-open` | `payload`, `recipient_ed25519_seed_hex` (the recipient's X25519 key is derived from it as in `x25519-key-agreement`) | `accept {purpose}` (a plain `purpose` passes through; `null` when there is neither), or in order `sealed-alg-unsupported` → `sealed-open-failed` → `sealed-plaintext-invalid` (not exactly `{"purpose": string}`) → `purpose-too-long` (> 280 characters). HPKE `info` = `dsip sealed introduction v1`, AAD = `id ‖ 0x00 ‖ from ‖ 0x00 ‖ to` (M§14.1) |
| `hpke-open` | `enc_hex`, `sk_r_hex`, `info_hex`, `aad_hex`, `ct_hex` | `accept {plaintext_hex}` or `hpke-open-failed` — RFC 9180 base mode, DHKEM(X25519, HKDF-SHA256) / HKDF-SHA256 / AES-128-GCM, sequence 0 (M§6.9) |
| `hpke-derive-key-pair` | `ikm_hex` | `{sk_hex, pk_hex}` (RFC 9180 §7.1.3) |
| `x25519-key-agreement` | `ed25519_seed_hex` | `{x25519_pk_hex}` — secret = SHA-512(seed)[0..32] clamped, as `did:key` derives it (M§6.9, spec-gap 55) |
| `blob-put` | `mailbox {did, serves, max_blob_bytes, quota_bytes?, used_bytes?}`, `authorization` (`{identity, payload}` already verified, or `null`), `request {path_sha256, body_size, body_sha256}`, `stored` | `{status, reason}` in M§5.6 order — 401 `policy.blocked` → 403 `policy.blocked` (`to`) → 403 `transport.unknown-recipient` → 400 `policy.blocked` (path) → 413 `mailbox.object-too-large` → 507 `mailbox.quota-exceeded` (spec-gap 99: `quota_bytes` set, the hash not already stored, and `used_bytes + size > quota_bytes` — decided from the authorized size, before the body) → (a stored hash: `{status: 200, accepted: {in_reply_to, duplicate: true}}`) → 400 `mailbox.blob-mismatch` → `{status: 201, accepted: {in_reply_to}}` (spec-gap 48) |
| `blob-get` | `path_sha256`, `stored` | `{status: 200\|404}` |
| `registration-on-removal` | `me`, `remaining_identities` | `{left}` — true only when no leaf of the identity remains (M§5.7, spec-gap 53) |
| `hub-outage-trace` | see spec-gap 72 (events `deposit`, `answer`, `no_answer`, `advance`, `handover_failed`). An `answer` whose `reason` is `mailbox.hub-unreachable` or `mailbox.quota-exceeded` (the hub could not store it, M§9.3; spec-gap 99) is an outage exactly like `no_answer` — a `retry_after` on it is not an input, the outage backoff governs; any other reason is a refusal | per step `emit` and `state` `{state, pending, attempt, down_for, handover_attempt}` |
| `move-arrival-trace` | `steps` of `{moved: {hub}}` / `{answer: {hub, reason?}}` / `{advance: n}`; `context.now`, `context.arrival_wait` (default 300). `moved` names the hub the group moved to and starts the wait afresh (state `arriving`, attempt 0). Only an `answer` from that hub while `arriving` counts: no `reason` (accepted) → `hosted`; `mailbox.unknown-group` with less than `arrival_wait` since the move → `retry_in` with the §13.2 backoff (1 s, doubling, 60 s ceiling); at or past it → `expired`, once. Everything else emits nothing and changes nothing (M§7.4, spec-gap 129) | per step `emit` (`retry_in`, `expired`) and `state {state, hub, attempt, waited}` — `state` one of `none`, `arriving`, `hosted`, `expired`; `waited` is the time since the last `moved`, `null` before one |
| `enrolment-trace` | `steps` of `{owner_op: {identity, device, id}}` / `{release: {identity, device, id}}` / `{operator_release: {identity}}` / `{hello: {identity}}` / `{advance: n}`; `context.now`, `context.configured` (identities the operator lists), `context.serve_any` (the bound on enrolled identities, default 0: enrolment closed), `context.expire_idle` (default false), `context.mls_retention_s` (default 2,592,000). The service's view of whom it serves (M§4.1, spec-gap 130). `owner_op` (a `sync`, `key-packages` or `mailbox-config` without `release`, on a verified binding): a configured or enrolled identity emits nothing; another one enrols while fewer than `serve_any` are enrolled (`enrolled`, and its last `hello` is now), else `error` `mailbox.not-served` to `device`. `release` (`mailbox-config` `release: true`): enrolled → `accepted` to `device`, then `released {cause: "owner"}`; configured → `error` `mailbox.not-enrolled`; neither → `error` `mailbox.not-served` (a release never enrols). `operator_release` (the operator ends an enrolment, spec-gap 164): enrolled → `released {cause: "operator"}`, nothing sent to any device; a configured or unserved identity → nothing emitted, nothing changed. `hello` (a verified `hello` of a device of the identity) sets an enrolled identity's last `hello` to now; for any other identity it does nothing. An `owner_op` of an identity already served does not count as a `hello`. `advance` adds `n` to now; then, with `expire_idle`, every enrolled identity whose last `hello` is more than `mls_retention_s` ago (strictly: at exactly `mls_retention_s` it still has a registered device, M§4.4) is released, `released {cause: "idle"}`, in enrolment order. Configured identities never count against the bound and never expire. A released identity is no longer enrolled; a later `owner_op` enrols it afresh | per step `emit` (`enrolled {identity}`, `released {identity, cause}`, `accepted {to, in_reply_to}`, `error {to, in_reply_to, reason}`) and `state {enrolled, free}` — `enrolled` in enrolment order, `free` = `serve_any` minus the number enrolled |

**The deposit class table** behind `deposit-fields` (M§5.2 "The class field table" is the same table, spec-gap 80).
Every deposit may carry `recipient` — it is addressing, not class. Beyond the envelope fields, `class` and `recipient`:

| class | MUST carry | MAY carry |
|---|---|---|
| `handshake` | `group`, `mls` | `welcome`, `group_info`, `ratchet_tree_blob`, `grants`, `seq` |
| `application` | `group`, `mls` | `seq`, `blobs` |
| `welcome` | `group`, `mls`, `hub` | `ratchet_tree_blob`, `grants`, `origin`, `successor_of`, `seq` (the adding commit's: spec-gap 83) |
| `group-info` | `group`, `mls` | `ratchet_tree_blob`, `handover_seq` |
| `ephemeral` | `group`, `sealed` | — |
| `archive` | `group`, `archive`, `akid`, `ref_group`, `ref_seq` | — |
| `introduction`, `grant` | `recipient`, `envelope` (and no `group`: a schema rule) | — |

Anything else is `deposit-fields`. After it: `object-too-large` for `mls`, `welcome`, `group_info`, `sealed`, `archive`; then
`introduction-too-large` (`transport.envelope-too-large`) for a carried introduction `envelope` over 4,096 bytes.
`external-join` checks run `external-join-adds` → `external-join-not-member` → `external-join-removes-other`;
`blob-replicate` skips run `mode` → `stored` → `too-large` → `not-https`, and `attempt` defaults to 1 of `max_attempts` 5.

**All messaging traces** keep expectations in `expect.steps[i]` = `{emit, state}`, parallel to `input.steps[i].event`;
`state` is compared in full.

**Hub refusals, in order** (spec-gap 81): moved (`mailbox.unknown-group`, whatever the deposit) → class not one of
`handshake`/`application`/`ephemeral`/`group-info` (`mailbox.unsupported-class`) → an expired `ephemeral` is dropped with no
answer → a `handshake`/`application` whose `digest` was already sequenced is `accepted {seq, duplicate}` — before membership
and epoch → membership, or for an external commit the M§6.8 check (`policy.blocked`) → epoch (`mailbox.commit-conflict`
for a commit one epoch late, else `mailbox.stale-epoch`; an application is good for the current or previous epoch) →
the commit's validity and M§7.3 (`policy.blocked`). Device lists in `roster` are sorted. An `ack` is taken only for the
head of that identity's queue (a welcome's with `class: welcome`); anything else changes nothing. Fan-out to an identity
the commit brought in waits for its welcome's acknowledgement; a member gaining a device gets the commit *and* a welcome —
its queue is not held, on a retry or after a restart either, and its welcome's acknowledgement re-sends nothing: only an
identity with no registration yet was waiting — and an acknowledgement from one still waiting moves its queue but sends
nothing (spec-gap 87).
An external joiner's identity is not sent its own commit unless it was already a member.

**Mailbox events the table leaves out**: `first_contact {id, from, sender_identity, recipient, kind: introduction|grant,
expires_at}` (spec-gap 54) — rate-limited per sender identity and per recipient inbox at `context.intro_limit` per
`intro_window` (`error policy.rate-limited {retry_after}`, the seconds until the oldest counted deposit leaves the window;
both kinds count and both are limited, except a solicited grant — below), then accepted **without a cursor** for an unserved recipient or an inbox already
holding `inbox_cap` introductions, else stored until `expires_at` (kept a second before it, dropped at it, spec-gap 141); `forward {id, device,
identity, group, to}` (spec-gap 45) → `{"forward": {to, id}}`, or `policy.blocked` (not the owner's device) /
`mailbox.unknown-group` (unregistered group, or `to` is not its hub); `forward_failed {id, device, to}` → `error
mailbox.hub-unreachable` (spec-gap 72). Other emissions: `{"handover_expired": {group, hub: the OLD hub, missing}}`
(spec-gap 71) and `{"close": {device, reason: "delegation-revoked"}}` after the `accepted` of a config with
`revoked_devices` (spec-gap 57). `key_packages.devices` is a map `device → "one-time"|"last-resort"`; an upload is bounded
at 100 one-time packages per device. A pending group is dropped when its age **exceeds** `pending_group_ttl`, with the hub deposits it admitted; an
archive record that references it is the owner's history and stays (spec-gap 91). A `welcome` is a redelivery
(`duplicate`, the first one's cursor) only while the mailbox still holds a welcome with those MLS bytes (`digest`) for
that group — not after the pending registration expired and took it, and not for another group (spec-gap 94).
During a hub move the new hub is held off — whatever it sends, a GroupInfo included — while the old hub's items through
`handover_seq` are missing (judged by the highest `seq` stored: the hub delivers in order, so a stored `seq` says every
lower one came before it, spec-gap 95) and `handover_wait` has not run out; only then is a `seq` at or below `handover_seq` judged
(`policy.blocked`). The expiry is announced (`handover_expired`) once, at the new hub's first deposit after the wait ran
out, whether that deposit is then admitted or refused (spec-gap 88). Only that expiry makes the old hub's later items at or
below `handover_seq` fills to store; when nothing was missing, an old hub's item at or below the highest stored stays a
redelivery (spec-gap 93). A `first_contact` of kind `grant` may carry `session`, the introduction it answers: when that id is
one the owner's device listed in a `config` `introductions_sent`, the grant is solicited — not counted, not limited, and
the entry is consumed (one introduction, one answer; the list survives a restart). Pushes go to the bound devices in device (DID) order, never to the device that made the deposit.

Trace emission order: `accepted`/`error` first, then fan-out or pushes in identity/device order,
then welcomes. Cursors are `c:` + 16 lowercase hex digits (Impl). Grants in mailbox traces are
presented already verified; their signatures are the envelope pipeline's concern.

## Kind: `dht`

Reachability hint records (§8.3, §8.5; plan §10). Input is a hint envelope,
optionally with `context.existing` (a previously accepted record for the same
subject). Expect: envelope verdict plus, on accept, `"winner": "input" |
"existing"` and `"conflict": "none" | "newer-seq" | "older-seq" |
"same-seq-live"` per the §8.3 rules (higher `seq` wins; expired records are
invalid; same key + same `seq` + differing content → `same-seq-live`, which
the profile treats as a warning — the existing record is kept).

Last, after the envelope pipeline, `hint-subject-mismatch` (the profile's §4 step 1) and the version and schema
checks (step 2), a hint with a `key_agreement` member (1.x, spec-gap 179) is refused with
`key-agreement-invalid` unless the member verifies as a key agreement delegation (kind `key-agreement`, check
`delegation`) for the hint's `subject` at `context.now`, under the vector's `context` (its documents and delegations).

## Kind: `did-webvh`

Resolving a `did:webvh` DID from its log (v0.9 §7.2, §8.4; spec-gap 101), per the did:webvh v1.0
method specification (https://identity.foundation/didwebvh/v1.0/, DIF Ratified). Offline: the
vector supplies the log text, so no HTTPS fetch takes place.

**Input:** `{did, log, witness, cache, now}`.

- `did`: the requested DID.
- `log`: the `did.jsonl` text, one JSON entry per line. A single trailing `\n` is ignored.
- `witness`: the `did-witness.json` text, or `null`.
- `cache`: `{"versionId": "<n>-<hash>"}`, the highest versionId this resolver verified before for the
  DID, or `null`.
- `now`: integer Unix seconds, the resolver's clock.

**Expect**, exactly one of:

- `{"outcome": "resolved", "versionId", "versionTime", "document", "ttl", "cache"}`.
  - `versionId` and `versionTime` are the last entry's.
  - `document` is the last entry's `state`, byte-for-byte as JSON values.
  - `ttl` is the active `ttl` parameter, an integer (default 3600).
  - `cache` is the versionId to remember: the last entry's.
- `{"outcome": "deactivated", "versionId", "cache"}`. The active parameters have `deactivated: true`,
  so no document is returned (did:webvh §Deactivate). DSIP treats the DID as having no keys.
- `{"outcome": "rejected", "reason"}`, with `reason` one of the tokens below.

**Check order (normative for parity).** The first failing check gives the reason.

1. **The requested DID** (`invalid-did`). It must:
   - start `did:webvh:`;
   - have at least a SCID and a domain;
   - have a SCID of exactly 46 base58btc characters.

   The domain is `host[%3Aport]`:
   - `host` has at least two labels, each 1–63 characters of `[A-Za-z0-9-]`, and the labels are not
     all digits (an IP address);
   - `port` is 1–5 digits, 1–65535.

   Each further segment matches `([A-Za-z0-9._~-]|%XX)+`, with either hex case. Its percent-decoded
   bytes must be valid UTF-8. Once decoded, a segment must not be `.` or `..`, must not contain `/`,
   `\` or NUL, and must not begin or end with a Unicode `White_Space` character: U+0009–U+000D,
   U+0020, U+0085, U+00A0, U+1680, U+2000–U+200A, U+2028, U+2029, U+202F, U+205F or U+3000.
   U+FEFF is not whitespace.
2. **The log is not empty** (`log-malformed`). Then, for each line *n* in order, steps 3–11:
3. **Structure** (`log-malformed`):
   - the line is **I-JSON** (RFC 7493), as JCS requires:
     - it parses as JSON;
     - no object has a member name twice;
     - no string or name contains a lone surrogate, escaped or not;
     - every number is an integer from −(2^53−1) to 2^53−1, written without a fraction or exponent
       (`-0` is allowed, and JCS writes it `0`);
   - it is an object with **exactly** the keys `versionId`, `versionTime`, `parameters`, `state`,
     `proof`;
   - `state` is an object;
   - `proof` is a non-empty array;
   - `versionId` is a string.
4. **versionId** matches `^[1-9][0-9]*-<base58btc>$`, and its number is *n* (`version-number`). The
   part after the dash is a sha2-256 multihash, `0x12 0x20` plus 32 bytes (`entry-hash`).
5. **versionTime** (`version-time`):
   - matches `YYYY-MM-DDTHH:MM:SS[.1–9 digits](Z|+00:00)`;
   - is strictly greater than the previous entry's;
   - is not later than `now + 300` seconds.
6. **Parameters** (`after-deactivation`, then `parameters`):
   - An entry after one whose active parameters have `deactivated: true` gives
     `after-deactivation`.
   - Otherwise `parameters` must be an object holding only `method`, `scid`, `updateKeys`,
     `nextKeyHashes`, `witness`, `watchers`, `portable`, `deactivated` and `ttl`.
   - Entry 1 has `method`, `scid` and `updateKeys`. Later entries have no `scid`.
   - `method` is exactly `did:webvh:1.0`. DSIP supports v1.0 only.
   - `scid` is a sha2-256 multihash.
   - The three lists are lists of strings, and every `updateKeys` member is an Ed25519 multikey.
   - `portable` and `deactivated` are booleans. `ttl` is an integer from 0 to 2^31.
   - There is no `portable: true` after entry 1.
   - `witness` is `{}`, or exactly `{threshold, witnesses}`, where:
     - `witnesses` is non-empty, and each element is an object whose `id` is a `did:key:` +
       Ed25519 multikey;
     - the ids are unique;
     - `threshold` is an integer from 1 to the number of witnesses.

   The active parameters then become the previous ones updated by this entry's. The defaults are
   `nextKeyHashes []`, `witness {}`, `watchers []`, `portable false`, `deactivated false` and
   `ttl 3600`.
7. **SCID, entry 1 only** (`scid`).
   - Take the entry without `proof` and set `versionId` to the string `{SCID}`.
   - Serialise it to JSON text and replace every occurrence of the `scid` value with `{SCID}`.
   - Parse it again and JCS-canonicalise it.
   - `base58btc(0x12 0x20 ‖ sha256(bytes))` must equal `scid`. There is no multibase `z` prefix.
8. **entryHash** (`entry-hash`). Take the entry without `proof`, with `versionId` replaced by the
   predecessor: the SCID for entry 1, otherwise the previous entry's full versionId. Its JCS
   canonicalisation must hash, as in step 7, to the part after the dash.
9. **Pre-rotation** (`pre-rotation`). It applies when *n* > 1 and the previous active
   `nextKeyHashes` is non-empty. The entry must then itself carry both `updateKeys` and
   `nextKeyHashes`. For every one of its `updateKeys`, `base58btc(0x12 0x20 ‖ sha256(utf8(key)))`
   must be in the previous `nextKeyHashes`.
10. **Proofs** (`proof`, then `unauthorized-key`).
    - The authorised keys are this entry's `updateKeys` for entry 1 or under pre-rotation, and
      otherwise the previous active `updateKeys`.
    - For each proof in order:
      - Its `verificationMethod` must be `did:key:<mk>#<mk>` with identical parts; otherwise
        `proof`.
      - If `<mk>` is not authorised, skip the proof.
      - Otherwise it must have `type: DataIntegrityProof`, `cryptosuite: eddsa-jcs-2022`,
        `proofPurpose: assertionMethod` and a `z`+base58btc `proofValue`, and its Ed25519 signature
        must verify (else `proof`). The signature is over
        `sha256(JCS(proof without proofValue)) ‖ sha256(JCS(entry without proof))`.
    - If no proof was by an authorised key, the reason is `unauthorized-key`.
11. **state.id** (`identity`).
    - It passes step 1, and its SCID equals entry 1's `scid`.
    - If it differs from the previous entry's `state.id`, the active `portable` must be `true` and
      `state.alsoKnownAs` must be a list containing the previous id.
12. **The requested DID** has the log's SCID, and some entry's `state.id` equals it (`identity`).
13. **Witnesses** (`witness`).
    - The witness configuration for entry *n*:
      - entry 1's active witness;
      - an entry whose previous witness was `{}` takes its own active witness;
      - otherwise the previous active witness.
    - Every entry with a non-empty configuration needs `witness` to be non-null I-JSON. A text that is
      not I-JSON counts as absent. Its records
      are `[{versionId, proof: [...]}]`; records whose `versionId` is not in the log are ignored.
    - A witness proof counts when its `verificationMethod` is `did:key:<mk>#<mk>` and its
      eddsa-jcs-2022 proof verifies over the document `{"versionId": …}`.
    - An entry is approved by the distinct witness ids, among its configuration's `witnesses`, that
      have a valid proof for that entry or any later one. There must be at least `threshold`.
14. **Cache** (`rollback`, then `fork`). Applies if `cache` is set and its `versionId` is a decimal number
    without a leading zero, a `-`, then a non-empty remainder of any characters (line terminators
    included), giving number *k*. Any other cache value is treated as absent:
    - fewer than *k* entries gives `rollback`;
    - an entry *k* whose versionId differs from the cached one gives `fork`.

**JCS** is RFC 8785 restricted to the values these logs hold: objects, arrays, strings, integers,
booleans and null. Object keys are sorted by their UTF-16 code units. There is no whitespace. A string escapes only `"`, `\\` and the
control characters U+0000–U+001F: `\b \f \n \r \t` where they exist, otherwise `\u00xx` with
lowercase hex. Everything else, non-ASCII included, is written as UTF-8.

## Kind: `device-events`

Device Events Profile 1.0 (`v1.0/dsip-device-events-profile-v1.0.md`, cited `E§n`; spec-gaps 103, 165–168). There are two
shapes: stateless checks (`input.check`) and alarm-list traces (`input.steps`).

**Content bodies** (E§5, spec-gap 166) are checked by kind `messaging`'s `check: "object"`: a body that breaks these is
`content-body`. Members not named here are ignored, and token values are not checked against their registries (an
unknown basis, type or severity has its fallback where it is used).
- **`device-event`.** `event` is an object.
  - `source` is an object whose `address` is a non-empty string and whose `basis` is a string. It is required unless
    `heartbeat` is present.
  - `alarm`, when present, is an object: `resource` a string, `type` a non-empty string, `severity` a string or
    `null`, `cleared` a boolean, and, when present, `qualifier` and `text` strings.
  - `heartbeat`, when present, is an object whose `interval_s` is an integer, at least 1.
  - `raw` and `syslog_gap`, when present, are objects.
- **`alarm-ack`.** `alarm` is an object: `resource` a string, `type` a non-empty string, and, when present,
  `qualifier` a string. `state` is a string. A `state` other than `ack` and `closed` is accepted here, and the alarm
  list ignores it (below).

**`check: "trap"`** (E§3), with `input.trap`, outputs `{"snmp": {version, uptime, trap_oid, varbinds}}` or
`{"error": "malformed-trap"}`. `varbinds` must be an array, and each element an object with string `oid` and
`type` and a `value` (any JSON). Anything else is `malformed-trap`. The output copies exactly those three members of
each, in order, and drops any other member.

- **`version: "v1"`**, with `enterprise` and `agent_addr` (strings), `generic` (an integer from 0 to 6), `specific`
  and `timestamp` (integers) and `varbinds`. Anything missing or of another type is `malformed-trap`.
  - `uptime` is `timestamp`.
  - `trap_oid` is `enterprise + ".0." + specific` when `generic` is 6, and otherwise
    `"1.3.6.1.6.3.1.1.5." + (generic + 1)`.
  - Two varbinds are appended in this order, each only if no varbind already has that OID:
    - `{oid: "1.3.6.1.6.3.18.1.3.0", type: "IpAddress", value: agent_addr}`;
    - `{oid: "1.3.6.1.6.3.1.1.4.3.0", type: "OBJECT IDENTIFIER", value: enterprise}`.
- **`version: "v2c"` or `"v3"`.**
  - Varbind 0 must have OID `1.3.6.1.2.1.1.3.0` and varbind 1 OID `1.3.6.1.6.3.1.1.4.1.0`; otherwise
    `malformed-trap`.
  - `uptime` is varbind 0's value, which must be a string of decimal digits not exceeding 2^53−1 (else
    `malformed-trap`), read as an integer. `trap_oid` is varbind 1's value, which must be a string (else
    `malformed-trap`).
  - The remaining varbinds are kept in order.
- Any other version is `malformed-trap`.
- Finally, in every case, varbinds with OID `1.3.6.1.6.3.18.1.4.0` (`snmpTrapCommunity.0`) are removed. Any
  `community` field in the input is never output.

**`check: "syslog-severity"`**, with `severity` 0–7 and an optional `table` (string keys "0"–"7" overriding the
default), outputs `{"severity": <token or null>}`. The default is 0–2 → `critical`, 3 → `major`, 4 → `warning`,
5–7 → `null`.

**`check: "map"`**, with `raw` (a `check: "trap"` or `check: "syslog"` output), `rules`, `source` and, for syslog,
an optional `syslog_table` (as `syslog-severity`'s `table`). A rule with `trap_oid` only ever matches `raw.snmp`, and
a rule with `syslog` only `raw.syslog`.

For `raw.snmp`:

- Rules are tried in order. A rule matches when its `trap_oid` equals the raw `trap_oid` and, if it has
  `varbind: {oid, value}`, some varbind has that OID and the same value compared as strings. The first match wins.
- A `notify` rule, or no match, outputs `{"notify": true}`.
- Otherwise the output is `{"alarm": {resource, type, qualifier: "", severity, cleared}}`:
  - `cleared` is true for `clear`;
  - `severity` is the rule's for `raise` (`null` if the rule has none), and `null` for `clear`;
  - `resource` is `source`, or `source + "/" + value` of the first varbind whose OID equals the rule's
    `resource_varbind` or starts with it plus `.`.

For `raw.syslog` (E§4):

- A rule matches when every member present in its `syslog` object matches. `app_name`, `msgid` and `hostname` must
  equal the raw field (a `null` field equals nothing), `facility` must equal it as an integer, and `msg_contains`
  must be a substring of `msg`. The first match wins.
- A `notify` rule outputs `{"notify": true}`. A `clear` rule outputs the alarm with `severity: null` and
  `cleared: true`.
- A `raise` rule's severity is its own `severity` if present and not `null`, and otherwise the table's for the raw
  `severity` (`syslog-severity` with `syslog_table`). If that is `null` too, the output is `{"notify": true}`.
- `resource` is `source`, or `source + "/" + value` where the rule's `resource_sd: {id, param}` names the first
  structured-data element with that `id` and, in it, the first parameter with that `name`. `qualifier` is `""`.
- **No rule matches:** if the table gives a severity, output
  `{"alarm": {resource: source, type: "syslog", qualifier: app_name or "", severity, cleared: false}}`; otherwise
  `{"notify": true}`.

**`check: "syslog"`** (E§3), with `datagram` (hex), outputs `{"syslog": {format, facility, severity, timestamp,
hostname, app_name, procid, msgid, structured_data, msg}}` or `{"error": "malformed-syslog"}`. It works on bytes.

- **PRI.** Byte 0 is `<`, then 1–3 ASCII digits, then `>`. A leading `0` is allowed only as the single digit `0`
  (`<00>` is malformed), and the value is at most 191. `facility` is the value div 8, `severity` the value mod 8. Anything else is malformed.
- **RFC 5424** applies when the bytes after `>` are 1–3 digits, the first not `0`, followed by a space. The version
  must be `1` (else malformed). `format` is `"rfc5424"`. Then these fields follow, each preceded by exactly one space:
  - `TIMESTAMP`, `HOSTNAME` (≤ 255 bytes), `APP-NAME` (≤ 48), `PROCID` (≤ 128) and `MSGID` (≤ 32). Each is 1 or more
    bytes in 33–126, and `-` alone gives `null`. The timestamp is kept as given, not interpreted.
  - `STRUCTURED-DATA` is `-` (giving `[]`) or one or more elements with nothing between them. An element is `[`,
    then an SD-ID, then zero or more `SP PARAM-NAME="PARAM-VALUE"`, then `]`. SD-ID and PARAM-NAME are 1–32 bytes in
    33–126 other than `=`, space, `]` and `"`. PARAM-VALUE runs to the first `"` not preceded by an escaping
    backslash. A backslash followed by `"`, `\` or `]` gives that byte; any other backslash is kept, with the byte
    after it. The value is decoded as below. Each element becomes `{"id", "params": [{"name", "value"}]}`, in order.
  - After the structured data, either the datagram ends (`msg` is `""`) or a space follows and the rest is `MSG`.
    Anything else is malformed. A leading BOM (`EF BB BF`) is removed from `MSG`.
  - Any token rule broken is malformed.
- **RFC 3164** applies otherwise. `format` is `"rfc3164"`, `msgid` is `null` and `structured_data` is `[]`. On the
  bytes after `>`:
  - **Timestamp.** If they begin with exactly `Mmm dd hh:mm:ss ` (15 bytes, then a space), that is the timestamp.
    `Mmm` is `Jan` to `Dec`, `dd` is ` 1` to ` 9` or `10` to `31`, `hh` is `00` to `23`, and `mm` and `ss` are `00` to
    `59`. If the next token, up to a space, is 1 or more bytes in 33–126 and a space follows it, that token is the
    hostname and the content starts after that space. Otherwise the hostname is `null` and the content starts after
    the timestamp's space. With no such timestamp, both are `null` and the content is all the bytes after `>`.
  - **Tag.** Take the longest run of bytes from `A–Z a–z 0–9 _ . - /` at the start of the content. If it is 1–32
    bytes long and is followed by `:`, or by `[`, 1–10 digits, `]` and `:`, then `app_name` is the run and `procid`
    is the digits (or `null`). `msg` is what follows the `:`, minus one leading space if there is one. Otherwise
    `app_name` and `procid` are `null` and `msg` is the whole content.
- **Text.** `msg` and parameter values are decoded as UTF-8, each maximal invalid subpart replaced with U+FFFD
  (Unicode §3.9; WHATWG decode). Header fields are ASCII by the rules above. All trailing CR and LF characters are
  removed from `msg`.

**`check: "usm-key"`** (E§3, RFC 3414 A.2, RFC 7860 §9.3), with `auth` (`md5`, `sha`, `sha224`, `sha256`, `sha384`,
`sha512`), `password` (a non-empty string, its UTF-8 bytes) and `engine_id` (hex), outputs
`{"auth_key": hex, "priv_key": hex}`:

- `Ku` is the hash of the password repeated, and cut, to 1,048,576 bytes.
- The localized key is `H(Ku ‖ engine_id ‖ Ku)`, the length of the hash.
- `priv_key` is the first 16 bytes of the same localized key (AES-128, RFC 3826 §1.2.1).

An empty password outputs `{"error": "bad-password"}`.

**Traces** have context `{now, escalation?: {min_severity, after_s}}`. Each step has an `event` and an expect of
`{"emit": [...], "alarms": [...]}`.

`alarms` is sorted by key, the array `[resource, type, qualifier]` compared element by element. Each entry is
`{key, severity, cleared, operator, count, escalation_due}`.

Severity order is `indeterminate < warning < minor < major < critical`, and any other token orders as `indeterminate`.

An alarm is **eligible** when all of these hold: the policy is set, it is not cleared, its operator state is `none`,
it has not escalated since its last raise, and its severity ≥ `min_severity`. After every change, an eligible alarm
with no timer gets `escalation_due = now + after_s`. An ineligible alarm has `null`. A running timer is kept while the
alarm stays eligible.

Events:

- **`report: {resource, type, qualifier, severity, cleared}`.** Every report on an existing alarm adds 1 to `count`,
  clears included.
  - **Unknown key, not cleared:** create the alarm (count 1, operator `none`) and emit
    `{"raised": {key, severity, reopened: false}}`.
  - **Unknown key, cleared:** nothing.
  - **Active, cleared report:** set cleared and emit `{"cleared": {key}}`.
  - **Cleared alarm, cleared report:** nothing.
  - **Cleared alarm, not-cleared report:** reopen it. Set the severity, operator `none` and not escalated, and emit
    `{"raised": {key, severity, reopened: true}}`.
  - **Active, same severity:** nothing.
  - **Active, different severity:** emit `{"changed": {key, severity}}`.
- **`ack: {alarm: {resource, type, qualifier}, state, by}`.** A missing `qualifier` (here and in
  reports) is `""`, and a missing `by` is emitted as `null`. Ignored for an unknown key, for a `state` other than `ack`
  and `closed` (spec-gap 166), when the operator state is already `closed`, or when it equals `state`. Otherwise set the operator state and emit
  `{"operator": {key, state, by}}`.
- **`heartbeat: {gateway, interval_s}`.** Records the gateway's interval and `last = now`. If the alarm
  `[gateway, "dsip-gateway-silent", ""]` is active, apply a cleared report to it.
- **`advance: n`.** Sets `now += n`. Then:
  1. For each gateway, in order of gateway id (compared as strings), whose silence alarm is not active and where `now − last > 2 × interval_s`, apply the
     report `{gateway, "dsip-gateway-silent", "", "major", not cleared}`.
  2. For each alarm with `escalation_due ≤ now`, ordered by due time then key, emit `{"escalate": {key, severity}}`,
     mark it escalated, and set `escalation_due` to `null`.

**Inform traces** (`context.component: "informs"`, E§3) have context `{component, now}`. Each step's expect is
`{"emit": [...], "informs": [...]}`.

- `informs` is sorted by key: the source by code point, then `request_id` as a number (so 9 sorts before 10). Each
  entry is `{key: [source, request_id], status}`, where `status` is `pending` or `answered`.
- **`inform: {source, request_id}`.**
  - An unknown key becomes `pending` and emits `{"deposit": {"key"}}`.
  - A `pending` key emits nothing: a retransmission deposits no second event and is not answered.
  - An `answered` key emits `{"respond": {"key"}}`: the lost response is answered again.
- **`accepted: {key}`.** A `pending` key becomes `answered`, remembered until `now + 300`, and emits
  `{"respond": {"key"}}`. Anything else changes nothing.
- **`refused: {key}`.** A `pending` key is removed, so the next retransmission deposits anew. It emits nothing.
- **`advance: n`.** Sets `now += n`, then removes every `answered` key whose remembered-until time is `≤ now`.
  `pending` keys never expire. Advance emits nothing.

**Signed syslog traces** (`context.component: "syslog-sign"`, E§3, v0.10; RFC 5848) model a gateway's collector.

**Context:** `{component, now, hold_s, signers: [{hostname, type: "C" | "K" | "P", key, gaps?}]}`. `gaps: true` turns
on gap detection for that signer (v0.11).
- `key` is base64 of the signer's key blob (RFC 5848 §5.2.1): the certificate's DER for `C`; the four MPIs p, q, g,
  y for `K`; for `P`, the 8-byte OpenPGP KeyID followed by the OpenPGP certificate.
- **A `P` key** (v0.11) is read as follows, and a signer whose key does not read this way has no key: every block of
  its is `bad-signature`.
  - The certificate is a sequence of OpenPGP packets (RFC 4880 §4.2), framed as a whole: every packet's header is
    read, old or new format, with a definite length (an indeterminate old-format length, or a new-format partial
    body length, does not read, in any packet), and every packet must fit the bytes.
  - The first packet is a Public-Key packet (tag 6): version 4, a 4-byte creation time, public-key algorithm 17
    (DSA), then the MPIs p, q, g, y, which fill the body exactly (RFC 4880 §5.5.2). Only this packet's body is
    examined; the others are framed and passed over.
  - The KeyID equals the last 8 bytes of the key's V4 fingerprint: SHA-1 over `0x99`, the body's length as 2 bytes,
    and the body (RFC 4880 §12.2), whatever header the packet was carried with. A body longer than 65,535 bytes
    does not read.
- The key's `key_sha256` is the SHA-256 of the decoded `key` bytes, in hex.
- Hostnames compare without case (ASCII).

**Steps:**
- `{receive: {message}}`, where `message` is hex: one whole syslog message.
- `{advance: n}`.

Each step's expect is `{"emit": [...], "held": [...], "waiting": n}`:
- `held` is the held messages' `sha256` values, in arrival order;
- `waiting` is the number of signed hashes waiting for their message.

The **emits** are:
- `{"deposit": {"sha256", "signed"}}`, where `sha256` is the message's SHA-256 in hex, and `signed` is `null` or E§2's
  object;
- `{"session": {hostname, app_name, procid, rsid, key_sha256}}`;
- `{"refused": {"block": "ssign" | "ssign-cert", "reason"}}`, `reason` one of `malformed-block`,
  `unsupported-version`, `unknown-signer`, `bad-signature`, `old-session`, `fragment-mismatch`, `payload-mismatch`,
  `unsupported-key-blob`, `no-session`;
- `{"gap": {hostname, app_name, procid, rsid, sg, spri, from, to}}`, for signers with `gaps: true` (below).

**Classifying a received message.** It is parsed as `check: "syslog"` does.
1. **Not RFC 5424, or its HOSTNAME is `-`.** It is deposited at once, unsigned.
2. **A block:** an SD element whose id is `ssign` or `ssign-cert`; the first such element names the block. It is
   never deposited; see below.
3. **Otherwise, with a configured signer's HOSTNAME.** It is held until `now + hold_s`.
   - When a waiting signed hash matches it, it is deposited signed at once, that waiting entry is removed, and its
     number becomes authenticated. Match on the waiting entry's hash algorithm; when several match, the earliest
     added wins.
4. **Otherwise.** It is deposited at once, unsigned.

**A block** is checked in this order, and the first failure is its `reason`.

1. **`malformed-block`.**
   - **The element.** It is the message's only SD element, and its parameters are exactly, in order:
     - `ssign`: `VER RSID SG SPRI GBC FMN CNT HB SIGN`;
     - `ssign-cert`: `VER RSID SG SPRI TPBL INDEX FLEN FRAG SIGN`.
   - **Numbers.** Decimal with no leading zeros (`0` alone is allowed):
     - `RSID`, `GBC` and `FMN`: at most 10 digits, with `FMN` ≥ 1;
     - `SG`: 0–3;
     - `SPRI`: 0–191;
     - `CNT`: 1–99;
     - `TPBL` and `INDEX`: at most 8 digits, each ≥ 1;
     - `FLEN`: at most 4 digits, ≥ 1.
   - **`VER`** is 4 characters.
   - **`SIGN`** is padded base64 that decodes to exactly two MPIs. Each MPI is a 2-byte big-endian bit count, then
     ⌈bits/8⌉ bytes. The count is not checked against the value.
   - **`HB`** is `CNT` non-empty padded-base64 tokens separated by single spaces. When `VER` is supported, each
     decodes to the hash's size (20 or 32 bytes).
   - **Padded base64** throughout is RFC 4648's alphabet with `=` padding, its length a multiple of 4. Non-zero
     unused bits in the last character are accepted (RFC 4648 §3.5).
   - **`FRAG`'s** length in bytes, after RFC 5424 unescaping, equals `FLEN`, and `INDEX + FLEN − 1 ≤ TPBL`.
2. **`unsupported-version`.** `VER` is not `0111` or `0121`.
3. **`unknown-signer`.** No signer has this HOSTNAME.
4. **`bad-signature`.**
   - **The signed bytes** are the message with ` SIGN="<value>"` removed. That text ends just before the element's
     closing `]`. The element starts with the `[` after the sixth space of the message, and closes at the first `]`
     outside a quoted value (inside quotes, `\` escapes the next byte). Anything else is `malformed-block`.
   - **The verification** is DSA with the signer's key and the version's hash, digest truncated to q's bit length as
     FIPS 186 does. `r` and `s` must be in 1…q−1.
5. **`old-session`.** `RSID` > 0, and it is below the highest `RSID` of an established session of this signer
   (HOSTNAME, APP-NAME). A rebooted signer may take a new PROCID, but keeps its APP-NAME (RFC 5848 §4.1).

**Then, a Certificate Block** for session (hostname as configured, APP-NAME, PROCID, RSID):
- **Established session.** A fragment whose `TPBL` is the established payload's length, and whose bytes equal the
  payload's at `INDEX`, is ignored, emitting nothing. Any other fragment ends the session, dropping its authenticated numbers and its waiting hashes, and
  assembly starts anew with this fragment. The `old-session` floor stays: it counts every RSID ever established.
- **Assembling.**
  - A `TPBL` different from the stored fragments' is `fragment-mismatch`, and so are bytes that disagree with a stored
    fragment where they overlap. The fragment is dropped.
  - Otherwise it is stored. When the stored fragments cover bytes 1…`TPBL`, the payload is assembled and the stored
    fragments cleared.
- **The assembled payload** is fields separated by single spaces: a non-empty timestamp (not interpreted), a key
  blob type, and the key blob when the type carries one (RFC 5848 §5.2.1). The first rule that applies decides:
  1. **`payload-mismatch`**: fewer than two fields, more than three, an empty timestamp, or a type that is not
     exactly one of `C`, `K`, `P`, `N`, `U`.
  2. **`unsupported-key-blob`** (v0.11): the type is `U`, installation-specific key exchange information, which has
     no interoperable reading. With or without a third field.
  3. **`N`**, no key information sent (v0.11): exactly two fields. The key is pre-distributed: the signer's
     configured key, whatever its type. A third field is `payload-mismatch`.
  4. **`C`, `K` or `P`**: three fields, the type the signer's configured type, and padded base64 decoding to the
     signer's configured key bytes. Otherwise `payload-mismatch`.

  When it is right, `{"session"}` is emitted, with the Certificate Block message's HOSTNAME, and the session is
  established.

**Then, a Signature Block:**
- **Session.** Without an established session (hostname as configured, APP-NAME, PROCID, RSID), the block is
  `no-session`.
- **Hashes.** Otherwise, hash `i` (from 0) is message number `FMN + i` in the group (session, SG, SPRI), and the
  hashes are handled in order:
  - a number already authenticated in the group is skipped;
  - else the earliest held message with that hash under the version's algorithm is deposited signed, and the number
    becomes authenticated;
  - else, unless that (group, number) is already waiting, the hash waits until `now + hold_s`.

**`advance`** adds `n` to `now`. Then:
- held messages with due ≤ `now` are deposited unsigned, in arrival order;
- waiting hashes with due ≤ `now` are dropped. For a signer with `gaps: true`, each dropped hash's number is lost: they
  are emitted as gaps after the deposits.

**Gaps** (v0.11, signers with `gaps: true`). Each group (session, SG, SPRI) keeps `covered`: the highest number any
of its verified Signature Blocks covered (`FMN + CNT − 1`), 0 before the first.
- **Never covered.** A verified Signature Block of an established session with `covered` > 0 and `FMN > covered + 1`
  first emits a gap `from: covered + 1, to: FMN − 1`. Then it is processed as above, and `covered` becomes the
  greater of `covered` and `FMN + CNT − 1`. A group's first block reports nothing before it: the collector may have
  started late.
- **Signed, never arrived.** At `advance`, the lost numbers are sorted by group then number. Here a group's order is
  its hostname (lowercase), APP-NAME, PROCID (by code point, a `-` field as ""), then RSID, SG and SPRI. Runs of consecutive numbers in
  one group become one gap each, in that order.
- A gap's `hostname`, `app_name` and `procid` are the Signature Block message's: for a lost number, the block that
  listed its hash.
- Waiting hashes dropped when a session ends are not gaps, and a session's end drops its groups' `covered` with them:
  the numbers start again.
- A run takes its `hostname`, `app_name` and `procid` from the block that listed its lowest number.

**A deposited message's `signed`** is `{hostname, app_name, procid, rsid, sg, spri, message_number, key_sha256}`.
`hostname`, `app_name` and `procid` are the Signature Block message's, and the numbers are JSON integers.

**SNMPv3 over TLS** (E§3, v0.10) has three stateless checks.

**`check: "tsm-name"`**, with `certificate` and `table`, outputs `{"security_name", "row"}` (the row's `id`) or
`{"error": "no-security-name"}`.
- **`certificate`** is `{sha256, chain: [sha256...], san: [{type, value}...], cn: [...]}`:
  - `chain` lists the verified path's CA certificates;
  - each SAN `type` is `rfc822`, `dns`, `ip` or any other token. An `ip` value is the address bytes in hex, of either
    case; the others are text. A value or CN that is not a string fails its map;
  - `cn` is the subject's CommonName values, in order.
- **`table`** rows are `{id, fingerprint, map, data?}`, in any order. They are considered in ascending `id` (no two
  share one). A row matches when `fingerprint`, compared without case, equals `sha256` or an entry of `chain`.
- **Maps.** A matched row's map gives the name, or fails:
  - `specified`: `data`, which fails when it is missing or not a string.
  - `san-rfc822`: the first `rfc822` SAN. The part after its last `@` has A–Z lowercased; with no `@`, it fails.
  - `san-dns`: the first `dns` SAN, with A–Z lowercased.
  - `san-ip`: the first `ip` SAN. 4 bytes give a dotted quad of decimals with no leading zeros; 16 bytes give 32
    lowercase hex digits. Any other length fails.
  - `san-any`: the first SAN whose type is `rfc822`, `dns` or `ip`, mapped as that type.
  - `common-name`: `cn[0]`.
  - Any other map fails, as does a map whose SAN or CN is absent.
- **Length.** A name that is empty or longer than 32 bytes of UTF-8 fails the row. Failing passes to the next
  matching row. Only the first SAN of the map's type (or types, for `san-any`) is tried; when it fails, later SANs
  are not.

**`check: "tls-frames"`**, with `stream` (hex), splits a TLS byte stream into messages. It outputs `{"messages":
[hex...], "pending": hex}`, adding `"close": true` when it stops at an item it cannot frame. From the head of the
stream, repeatedly:
1. Fewer than 2 bytes left: they are `pending`.
2. A first byte other than `0x30`: close.
3. A length byte `0x80`, or `0x85`–`0xff`: close.
4. For `0x81`–`0x84`, too few length bytes present: the rest is `pending`.
5. A total size (tag, length and content) over 65,536: close.
6. Fewer bytes present than the total: the rest is `pending`.
7. Otherwise the message is taken, and splitting continues after it.

`pending` is `""` when nothing is left, and it is the unread rest of the stream after a close. A single byte waits
even when it is not `0x30` (step 1 comes first); a second byte decides.

**`check: "dtls-record"`** (v0.11), with `record` (hex), is the DTLS side of the same transport model (RFC 6353 over
UDP): a DTLS record carries exactly one message. The record is split as `tls-frames` splits a stream, and it is the
one message when that gives exactly one message, nothing pending and no close: `{"message": hex}`. Otherwise
`{"error": "not-one-message"}`, and the gateway drops the record; the session continues.

**`check: "tsm"`**, with `message` (hex), outputs one of:
- `{"accepted": {"trap": {"version": "v3", "varbinds": [...], "inform"?: {"request_id"}}}}`;
- `{"discovery": {"request_id"}}`, for RFC 5343 discovery: a PDU with tag `0xA0`, contextEngineID `8000000006`,
  and exactly one varbind, whose OID is `1.3.6.1.6.3.10.2.1.1.0` (its value is any valid value);
- `{"refused": {"reason"}}`.

The checks run in this order:
1. **`malformed`.** SNMPv3 traces' step 1, with two changes. `securityParameters` is any OCTET STRING, and its content
   is not read. `msgData` is a ScopedPDU whatever the flags say, so an OCTET STRING there is malformed.
2. **`unsupported-security-model`.** `msgSecurityModel` ≠ 4.
3. **`not-a-notification`.** The PDU's tag is not `0xA7` (trap) or `0xA6` (inform), and it is not discovery.

There are no other checks: the TLS connection authenticated the sender.

**SNMPv3 traces** (`context.component: "snmpv3"`, E§3) model a gateway's USM receiver (RFC 3414 §3.2).

The context is `{component, now, local: {engine_id, boots, time}, users: [...]}`. `local.time` is the gateway's
engine time at the context's `now`, and it advances with `advance`. Each user is
`{engine_id: hex | null, user, auth, auth_key? | auth_password?, priv: "aes128" | null, priv_key? | priv_password?}`:

- A key is already localized for its `engine_id`. A password is localized with the message's engine ID, as for
  `usm-key`.
- An `aes128` `priv_key` uses its first 16 bytes.
- A user with `engine_id: null` gives passwords, never keys.

Each step's expect is `{"emit": [...], "engines": [...]}`. `engines` is the non-authoritative cache, sorted by
`engine_id`. Each entry is `{engine_id, boots, time, latest}`, where `time` is the cached time advanced by the local
clock to now.

**`receive: {from, datagram}`** (hex) emits exactly one of these:

- `{"accepted": {"trap": {"version": "v3", "varbinds": [...], "inform"?: {"request_id"}}, "usm": {engine_id, user,
  level}}}`, where `level` is `authNoPriv` or `authPriv`;
- `{"refused": {"reason", "report"}}`, where `report` says whether the gateway answers with a Report.

The checks run in this order, and the first failure is the reason:

1. **`malformed`.**
   - **BER.** Tags are one byte; a high-tag-number tag is malformed. Lengths are definite, short form or long form
     with 1–4 length bytes. The indefinite length (`0x80`) is malformed. Content must fit in its parent, and nothing
     may follow the outer SEQUENCE. INTEGER content is 1–8 bytes, two's complement. Every SEQUENCE holds exactly
     the elements listed for it, and an extra element is malformed. Encodings need not be minimal, as BER (unlike
     DER) allows: padded INTEGER content, a long-form length that fits the short form, and `0x80` bytes leading an OID
     subidentifier are all accepted. A PDU's tag is any single byte; its constructed bit
     is not checked.
   - **The message** is `SEQUENCE {INTEGER 3, SEQUENCE {msgID, msgMaxSize, msgFlags, msgSecurityModel},
     OCTET STRING securityParameters, msgData}`:
     - `msgID` and `msgSecurityModel` are 0–2^31−1, and `msgMaxSize` is 484–2^31−1;
     - `msgFlags` is exactly 1 byte, with bit `0x01` auth, `0x02` priv and `0x04` reportable. Priv without auth is
       malformed, and other bits are ignored;
     - `securityParameters` must hold exactly `SEQUENCE {OCTET STRING engineID (0 or 5–32 bytes), INTEGER boots,
       INTEGER time (each 0–2^31−1), OCTET STRING userName (0–32 bytes), OCTET STRING authParams, OCTET STRING
       privParams}`.
   - **`msgData`** is an OCTET STRING when the priv flag is set, and otherwise a ScopedPDU:
     - **ScopedPDU** is `SEQUENCE {OCTET STRING contextEngineID, OCTET STRING contextName, PDU}`;
     - **PDU** is any tag holding `INTEGER request-id` (−2^31 to 2^31−1), two INTEGERs and `SEQUENCE` of varbinds.
       Each varbind is `SEQUENCE {OID, value}`.
   - **OIDs** are 1 or more base-128 subidentifiers (empty content is malformed), with no unterminated last byte,
     each at most 2^64−1. The first
     subidentifier X gives `0.X` (X < 40), `1.(X−40)` (X < 80) or `2.(X−80)`.
   - **Values** are typed as follows; any other tag is malformed:
     - `0x02` Integer32: decimal, −2^31 to 2^31−1 (RFC 2578);
     - `0x04` OCTET STRING: the text if it is valid UTF-8 with no code point in U+0000–U+001F or U+007F–U+009F,
       otherwise lowercase hex;
     - `0x05` NULL: `""`, with empty content (X.690 §8.8.2);
     - `0x06` OBJECT IDENTIFIER: dotted;
     - `0x40` IpAddress: exactly 4 bytes, dotted quad;
     - `0x41` Counter32, `0x42` Gauge32, `0x43` TimeTicks and `0x46` Counter64: unsigned decimal of 1–9 content
       bytes, where 9 bytes need a leading `00`. The first three are at most 2^32−1;
     - `0x44` Opaque: lowercase hex.

     Varbinds are `{oid, type, value}`, with the type names of `check: "trap"`.
2. **`unsupported-security-model`:** `msgSecurityModel` ≠ 3.
3. **`unknown-engine-id`:** an empty engineID. `report` is the reportable flag (RFC 3414 §4, discovery).
4. **`unknown-user`:** the user is the first entry whose `engine_id` equals the engineID (hex, lowercase) and whose
   `user` equals the userName bytes, read as UTF-8 (a userName that is not UTF-8 matches no user). Failing that, it is the first entry with `engine_id: null` and
   that `user`. Failing both, the reason is `unknown-user`.
5. **`unsupported-security-level`:** no auth flag, or the priv flag on a user without `priv`.
6. **`wrong-digest`:** the MAC lengths are `md5`/`sha` 12, `sha224` 16, `sha256` 24, `sha384` 32 and `sha512` 48.
   The digest is wrong if authParams is not that length. It is also wrong if it differs from the HMAC (with the
   protocol's hash, keyed with the localized key) of the received bytes with authParams' content bytes replaced by
   zeros, truncated to that length. The bytes are the received ones, never re-encoded.
7. **`not-in-time-window`.**
   - **Authoritative (engineID = `local.engine_id`).** Outside the window if `local.boots` is 2^31−1, or boots ≠
     `local.boots`, or |time − the gateway's time now| > 150. `report` is the reportable flag.
   - **Otherwise,** using the cache entry for the engineID:
     - if there is none, it is seeded with `{boots, time, latest: time}` at now;
     - else, if boots > the cached boots, or they are equal and time > `latest`, it is set to `{boots, time,
       latest: time}` at now;
     - then the message is outside the window if the cached boots is 2^31−1, or boots < the cached boots, or they
       are equal and time < (the cached time advanced to now) − 150. `report` is false.

     The cache changes even when a later step fails.
8. **`decryption-error`** (priv only):
   - privParams must be 8 bytes;
   - the IV is boots (4 bytes, big-endian), then time (4 bytes, big-endian), then privParams;
   - AES-128-CFB (128-bit feedback) with the 16-byte privacy key;
   - the plaintext must be exactly a ScopedPDU as in step 1 (any failure there, here, is `decryption-error`).
9. **`not-a-notification`:** the PDU tag is neither `0xA7` (SNMPv2-Trap) nor `0xA6` (InformRequest).
10. **`engine-id-mismatch`:** a trap whose engineID is `local.engine_id`, or an inform whose engineID is not.

`report` is false for every reason not named above. **`advance: n`** sets `now += n` and emits nothing.

**`check: "snmp-answer"`** (E§3, spec-gap 168) builds the gateway's answer to a received SNMPv3 message, byte for
byte. The input is `answer`, `message` (hex: the message as received, which earlier checks have already decided), and
`local: {engine_id, boots, time}` (the gateway's engine and its clock now). It outputs `{"answer": hex}`, or
`{"error": "malformed"}` when `message` is not an SNMPv3 message by the SNMPv3 traces' step 1 (or, encrypted, its
plaintext is not a ScopedPDU).

- **Encoding.** Every length is definite and as short as it can be (short form below 128, otherwise long form with
  the fewest length bytes); every INTEGER has the fewest content bytes in two's complement; an unsigned value (Counter32)
  the fewest bytes, with a leading `00` when its top bit would be set. The message is
  `SEQUENCE {INTEGER 3, SEQUENCE {msgID, msgMaxSize, msgFlags, msgSecurityModel}, OCTET STRING securityParameters,
  msgData}`. `msgID` is the received message's; `msgMaxSize` is 65507; `msgFlags` is one byte.
- **`answer: "unknown-engine-id"` and `"not-in-time-window"`** (USM, RFC 3414 §3.2 steps 3 and 7a; RFC 3412 §7.1
  step 3), with `counter`, the counter's value after it was incremented:
  - `msgFlags` is `00` for `unknown-engine-id` and `01` (authNoPriv, never encrypted) for `not-in-time-window`;
    `msgSecurityModel` is 3.
  - `securityParameters` holds `SEQUENCE {OCTET STRING local.engine_id, INTEGER local.boots, INTEGER local.time,
    OCTET STRING userName, OCTET STRING authParams, OCTET STRING ""}`, where `userName` is the received message's.
  - `msgData` is the ScopedPDU `SEQUENCE {OCTET STRING local.engine_id, OCTET STRING "", Report-PDU}`, the Report-PDU
    being tag `0xA8` holding `INTEGER 0` (request-id: the PDU was not read), `INTEGER 0`, `INTEGER 0` and
    `SEQUENCE {SEQUENCE {OID, Counter32 (0x41) counter}}`. The OID is `1.3.6.1.6.3.15.1.1.4.0`
    (usmStatsUnknownEngineIDs) or `1.3.6.1.6.3.15.1.1.2.0` (usmStatsNotInTimeWindows).
  - `authParams` is empty for `unknown-engine-id`. For `not-in-time-window` it is the MAC with `user: {auth,
    auth_key}`, the key localized for `local.engine_id`: the message is encoded with `authParams` as that many zero
    bytes (the MAC lengths of the SNMPv3 traces' step 6), the HMAC of the whole message with the protocol's hash and
    the key is taken, truncated to the MAC length, and written over the zeros.
- **`answer: "response"`** (RFC 3416 §4.2.7) answers an inform, with `user: {auth, auth_key, priv, priv_key?}` for
  USM, and `salt` (8 bytes, hex) when it is encrypted. The received ScopedPDU (for USM `authPriv`, first decrypted with
  `priv_key` and the received boots, time and privParams, as the SNMPv3 traces' step 8) gives the contextEngineID, the
  contextName, the request-id and the VarBindList, the last copied as its received bytes, tag and length included. The
  answer's ScopedPDU is `SEQUENCE {OCTET STRING contextEngineID, OCTET STRING contextName, Response-PDU}`, the
  Response-PDU being tag `0xA2` holding `INTEGER request-id`, `INTEGER 0`, `INTEGER 0` and the VarBindList.
  `msgFlags` is the received one's auth and priv bits (`& 0x03`), so never reportable.
  - **USM** (`msgSecurityModel` 3): `securityParameters` as for a Report, with the received `userName`, and
    `privParams` the `salt` when `priv` bit is set (else empty). When it is set, `msgData` is
    `OCTET STRING (AES-128-CFB of the ScopedPDU)` with the first 16 bytes of `priv_key` and the IV `local.boots`
    (4 bytes, big-endian), `local.time` (4 bytes), `salt`. The MAC is then computed as for a Report, over the whole
    message.
  - **TSM** (`msgSecurityModel` 4, E§3): `securityParameters` is an empty OCTET STRING and `msgData` the plaintext
    ScopedPDU.
- **`answer: "discovery"`** (TSM, RFC 5343) answers the discovery request (`check: "tsm"`'s `discovery`): as a TSM
  `response`, except that its VarBindList is `SEQUENCE {SEQUENCE {OID 1.3.6.1.6.3.10.2.1.1.0, OCTET STRING
  local.engine_id}}`.

**Hold-down traces** (`context.component: "holddown"`, E§4) have context `{component, now, hold_s}`. Each step's
expect is `{"emit": [...], "held": [...]}`. `held` lists the held clears, sorted by key, each as `{key, due}`.
- **`report: {resource, type, qualifier?, severity, cleared, inform?}`** (a missing `qualifier` is `""`):
  - **From an SNMP inform** (`inform: true`, E§4, spec-gap 167): it emits `{"deposit": report}` at once, cleared or not,
    and a clear held for its key is dropped. An inform is answered only once its event is stored (E§3).
  - **A cleared report:**
    - with `hold_s` 0, it emits `{"deposit": report}`;
    - with a clear already held for the key, it changes nothing;
    - otherwise the clear is held, `due = now + hold_s`, and it emits nothing.
  - **A report that is not cleared:** a held clear for its key is dropped. The report emits `{"deposit": report}`.
  - The emitted `report` is the step's, every field kept, with `qualifier` added when missing.
- Keys sort element by element by code point.
- **`event: {...}`** (an event with no alarm) emits `{"deposit": event}`.
- **`advance: n`** sets `now += n`, then deposits each held clear with `due ≤ now`, ordered by `due` then key, emitting
  `{"deposit": report}` for each and removing it.

## Kind: `recording`

Recording Profile draft (`v1.0/dsip-recording-profile-v1.0-draft.md`, cited `C§n`; spec-gap 107). Three shapes:
consent traces (C§4), `check: "conversation"` (C§5) and `check: "recording-session"` (C§6).

**`check: "add-devices"`** (C§5, M§5.5, M§7.2) is the devices a device adds for an identity, given what its KeyPackage
directory returned. The input is `{target, self_identity, self_device, purpose: "conversation" | "personal",
key_packages: [{device, identity, capabilities}]}`, and the output is `{"add": [device, …]}` or `{"refused": <token>}`:

1. The candidates are the entries whose `identity` is `target` and whose `device` is not `self_device`, in input
   order, keeping only the first entry for a device.
2. For `personal`, drop the candidates whose `capabilities` include `dsip.record` (C§5: never the personal group). An
   entry without `capabilities` has none.
3. `no-key-packages`: no candidate remains.
4. `recorder-only`: every remaining candidate carries `dsip.record` and `target` is not `self_identity` (a recorder
   never stands in for the person; when the adder is that person, it is present itself).
5. Otherwise `add` lists the remaining candidates' devices, in order.

**Consent traces** model one counterparty's client in one call. The context is
`{role: "caller" | "callee", accept: "ask" | "always" | "never"}`. Each step's expect is
`{"emit": [...], "disclosure", "pending", "hold_media", "accepted", "ended"}`:

- `disclosure` is the other side's current declaration, or `null` when it is off;
- `pending` is whether an acceptance is awaited, and `hold_media` equals it while the session has not ended;
- `accepted` is the recorders accepted in this session, sorted by code point;
- `ended` is `null` or the reason the client ended the session.

Events:

- **`received: {type, recording?}`** (`type` is `invite`, `answer` or `update`; any type is processed for either
  role). Declarations are schema-valid, so one that is not `off` names its recorder. After the client has ended the
  session, nothing happens. Otherwise:
  - An `answer` marks the session answered.
  - A missing `recording` means `{"state": "off"}`.
  - **`off`:** if `disclosure` is not `null`, emit `{"render": {"state": "off", "recorder": <its recorder>}}`, set it
    to `null`, and clear `pending`.
  - **Anything else:** if it differs from `disclosure` in `state`, `recorder` or `purpose`, emit
    `{"render": {state, recorder, purpose?}}` (`purpose` only when present) and set `disclosure` to it; `disclosure`
    holds only those three members. Then, whether or not it changed, apply the effective state: `paused` for
    `paused`, and `on` for `on` and for any unregistered state (the safe reading).
    - **Effective `paused`:** clear `pending`.
    - **Effective `on`, recorder already in `accepted`:** clear `pending` (a return to an accepted recorder needs
      no new acceptance).
    - **Effective `on`, recorder not accepted:**
      - `accept: "always"`: add it to `accepted` and emit `{"accepted": {recorder, "by": "policy"}}`;
      - `"never"`: decline (below);
      - `"ask"`: set `pending`.
- **`local: "accept"`.** If `pending`, add the disclosure's recorder to `accepted`, clear `pending`, and emit
  `{"accepted": {recorder, "by": "user"}}`.
- **`local: "decline"`.** If the session has not ended and `disclosure` is not `null`, decline.
- **`local: "answer"`.** For a caller, nothing happens. For a callee: if the session has ended, nothing happens. If `pending`, emit
  `{"blocked": "awaiting-acceptance"}`. Otherwise mark the session answered and emit `{"send": {"type": "answer"}}`.
- **Declining** emits `{"send": {"type", "reason": "policy.recording-declined"}}`. The type is `reject` for a callee
  that has not answered, and `bye` otherwise. Declining sets `ended` to the reason and clears `pending`.

**`check: "conversation"`** (C§5), with `leaves` (`[{device, subject, capabilities}]`), `accepted` (device ids) and
an optional `sender` (a device id), outputs `{recorded, recorders, may_send}`, plus `render_sender` when `sender` is
given:

- `recorders` lists the leaves whose `capabilities` include `dsip.record`, as `{device, subject}`, sorted by `device`;
- `recorded` is whether `recorders` is non-empty;
- `may_send` is whether every recorder's device is in `accepted` (a recorder that leaves asks nothing new);
- `render_sender` is false when `sender` is no leaf's device, or its leaf carries `dsip.record`, and true otherwise.

**`check: "call-record-outcome"`** (C§9, v0.13) is the `outcome` a device puts on its leg's record. The input is
`{direction: "inbound" | "outbound", answered, ended_by: "local" | "remote" | "transport", reason}` and the output is
`{"outcome": <token>}`, the first that applies:

1. `answered` when `answered` is true;
2. `answered-elsewhere` when `reason` is `session.answered-elsewhere`;
3. `failed` when `ended_by` is `transport` or `reason`'s category (the part before the first `.`) is `transport`;
4. `declined` when `reason` is `user.declined` and either `direction` is `inbound` with `ended_by` `local`, or
   `outbound` with `ended_by` `remote`;
5. `missed` for any other `inbound`;
6. `cancelled` for any other `outbound` with `ended_by` `local`;
7. `rejected` otherwise.

**`check: "call-record-evidence"`** (C§9, v0.13) matches a record's `evidence` against envelopes kept elsewhere.
The input is `{evidence: [<64 lowercase hex>, …], frames: [<text frame>, …]}`. A frame's digest is the SHA-256 of its
UTF-8 bytes exactly as given: never parsed and re-serialised (§10.2), so two frames that differ only in whitespace
have different digests. The output is `{"matched": [...], "unmatched": [...]}`: each `evidence` entry, in input
order, goes to `matched` when some frame's digest equals it and to `unmatched` otherwise. A repeated entry appears
each time it is listed.

**`check: "recording-session"`** (C§6), with `declared` (`{session, state?, recorder?}`: the recording party's
declaration in the recorded session), `recorder` (`{identity, capabilities}`: the recorder's verified delegation) and
`offer` (`{media: [{direction, …}], recording_session}`), outputs `{"ok": true}` or `{"refused": <token>}`. The tokens
are local results: on any of them the recording party sends no media to the recorder, and it ends a recording session
it has opened with `bye` and `policy.blocked`. The checks run in this order:

1. `not-declared`: `declared.state` is absent or `off` (an unregistered state counts as declared).
2. `recorder-mismatch`: `recorder.identity` differs from `declared.recorder`.
3. `missing-capability`: `recorder.capabilities` lacks `dsip.record`.
4. `wrong-session`: `recording_session.of` differs from `declared.session`.
5. `bad-stream-map`: there is no stream, a stream's `media` is not an integer index of `offer.media`, two streams
   share an index, or a stream's `participant` is not among `recording_session.participants[].identity`. (On the wire
   §10.3 rejects floats at parse, so a check never meets an index spelled `1.0`; vectors spell none.)
6. `direction`: a media section that a stream names is not `sendonly` (a missing `direction` is not `sendonly`).

## Kind: `alias-transparency`

Alias Transparency Profile draft, stage 1 (`v1.0/dsip-alias-transparency-profile-v1.0-draft.md`, cited `T§n`;
spec-gap 104). These are the KEYTRANS building blocks, following the editors' copy of draft-ietf-keytrans-protocol
(2026-09-16) and the editor's implementation katie (commit `e1640671`), plus the profile's own rules. Every computed
value here was confirmed with katie. The editors' copy differs from -05 only in the mode-1 Configuration.

- All binary values are lowercase hex strings, with no prefix.
- `label` and `value` are strings, used as their UTF-8 bytes.
- Integers are big-endian in every encoding.
- `SHA-256` is written `H`, and `‖` is concatenation.

Each vector has `input.check`. The checks and their outputs:

- **`alias`** (`{alias}`, T§3) → `{"label": <normalized>}` or `{"error": "not-an-alias"}`.
  - **A `tel:` alias** (v0.12; Number Attestation N§6 route 2): when the first four characters are `tel:` in any case,
    the rest is a global tel URI (RFC 3966) with no parameters: `+`, then digits with the visual separators `-`, `.`,
    `(` and `)` removed, and nothing else. The digits must be 2 to 15, the first not `0` (E.164). The label is
    `tel:+<digits>`; anything else is `not-an-alias`. The rules below are for every other alias.
  - Split at the **last** `@` into `local` and `domain`.
  - `local` is one or more characters, each U+0021–U+007E and not `@`.
  - `domain` is at least two `.`-separated labels. Each is 1–63 characters of `[A-Za-z0-9-]` and neither begins nor
    ends with `-`.
  - The result is `local + "@" + lowercase(domain)`, and must be at most 255 bytes.
- **`vrf-input`** (`{label, version}`) → `{"bytes"}` = `u8(len(label)) ‖ label ‖ u32(version)`. A label over 255
  bytes, or a version outside 0–2^32−1, gives `{"error": "vrf-input"}`.
- **`vrf-verify`** (`{public_key, alpha, proof}`) → `{"valid": true, "beta": <64-byte hex>}` or
  `{"valid": false, "beta": null}`.
  - The VRF is ECVRF-EDWARDS25519-SHA512-TAI, RFC 9381 §5.3, with `validate_key = TRUE` (§5.4.5).
  - Every point (the public key, Gamma, each encode-to-curve candidate) is decoded per RFC 8032 §5.1.3 and must be
    canonical: `y < p`, and not `x = 0` with the sign bit set. A non-canonical encoding does not decode.
  - `validate_key` refuses a key whose y-coordinate encoding, with its sign bit cleared, is one of
    `0, 1, bad_y2, p − bad_y2, p − 1, p, p + 1` (RFC 9381 §5.4.5). For decodable keys this is exactly the low-order
    points.
  - encode_to_curve's counter is one byte (0–255). Exhausting it gives no point, and the proof is invalid.
  - It is invalid when:
    - the public key does not decode;
    - the public key is one of the §5.4.5 low-order encodings;
    - the proof is not 80 bytes;
    - Gamma does not decode;
    - `s ≥ q`;
    - the challenge does not match.
- **`index`** (`{public_key, label, version, proof}`) → `{"index": beta[0..32]}`, where `beta` is `vrf-verify` over
  `alpha = VrfInput(label, version)`. A label over 255 bytes, or a version that is not an integer in 0–2^32−1, gives
  `{"error": "vrf-input"}`. A proof that does not verify gives `{"error": "vrf-invalid"}`.
- **`commitment`** (`{opening, label, version, value}`) → `{"commitment"}`, computed as:
  - `HMAC-SHA256(Kc, opening ‖ u8(len(label)) ‖ label ‖ u32(version) ‖ u32(len(value)) ‖ value)`;
  - `Kc` is the 16 bytes `d821f8790d97709796b4d7903357c3f5`;
  - `opening` must be 16 bytes, else `{"error": "opening"}`. Otherwise, a label over 255 bytes or a version outside
    0–2^32−1 gives `{"error": "label"}`.
- **`commitment-raw`** (`{opening, body}`, any lengths) → `{"commitment": HMAC-SHA256(Kc, opening ‖ body)}`.
- **`prefix-root`** (`{leaves: [{index, commitment}]}`) → `{"root"}`. The leaves have 32-byte, distinct indexes.
  - Bit *i* of an index is bit `7 − i mod 8` of byte `⌊i/8⌋`, so the most significant bit comes first.
  - The tree is the binary trie on these bits, with each leaf only as deep as needed to separate it from all others.
  - A leaf is `H(0x02 ‖ index ‖ commitment)`.
  - An internal node at depth *d* is `H(0x03 ‖ left ‖ right)`, where `left` and `right` are the subtrees of leaves
    whose bit *d* is 0 and 1. An empty side is 32 zero bytes.
  - With one leaf, the root is that leaf.
  - An empty list, an index or commitment that is not 32 bytes, or duplicate indexes, gives
    `{"error": "malformed"}`.
- **`prefix-parent`** (`{left, right}`, each hex or `null`) → `{"hash": H(0x03 ‖ left ‖ right)}`, where `null` is
  32 zero bytes.
- **`log-root`** (`{entries: [{timestamp, prefix_root}]}`, one or more) → `{"root"}`.
  - Leaf *j*'s value is `H(u64(timestamp) ‖ prefix_root)`.
  - For entries `[lo, hi)` with more than one entry, let *k* be the largest power of two less than `hi − lo`. The
    value is `H(tag(L) ‖ L ‖ tag(R) ‖ R)` over `[lo, lo+k)` and `[lo+k, hi)`, where `tag` is `0x00` for a single
    leaf and `0x01` for a computed parent.
  - With one entry, the root is that leaf's value. No entries gives `{"error": "malformed"}`.
- **`configuration`** (`{config}`; members other than those named below are ignored) → `{"bytes"}`, encoded in
  this order:
  1. `u16(ciphersuite)`;
  2. `u8(mode)`;
  3. twice `u16(len(key)) ‖ key`, for `signature_public_key` and `vrf_public_key`. This is the editors' copy: mode 1
     has no `leaf_public_key`, unlike -05;
  4. `u64` each of `max_ahead`, `max_behind` and `reasonable_monitoring_window`;
  5. `maximum_lifetime` as `0x00` when null, otherwise `0x01 ‖ u64(value)`.
- **`configuration-accept`** (`{bytes}`) parses that layout and applies T§2. Checks run in this order:
  1. a ciphersuite other than 2 → `{"error": "unsupported-suite"}`;
  2. a mode other than 1 → `{"error": "unsupported-mode"}`;
  3. any of these → `{"error": "malformed"}`:
     - the input runs out;
     - the presence byte is not 0 or 1;
     - there are trailing bytes;
     - a key is not 32 bytes;
     - a `u64` above 2^53−1.

  On success the output is `{"config": {signature_public_key, vrf_public_key, max_ahead, max_behind,
  reasonable_monitoring_window, maximum_lifetime}}`, with keys as hex and `maximum_lifetime` an integer or null.
- **`tree-head`** (`{configuration, tree_size, root, signature}`) → `{"valid"}`. It is true iff the configuration is
  accepted as above and the signature is a valid Ed25519 signature by its `signature_public_key` over
  `configuration ‖ u64(tree_size) ‖ root`. A configuration that is not accepted gives that error object instead.
- **`search-tree`** (`{n}`, n ≥ 1) → `{"root", "frontier"}`.
  - `root = 2^⌊log2 n⌋ − 1`.
  - `level(x)` is the number of trailing 1 bits of *x*.
  - `left(x) = x XOR 2^(level(x)−1)`.
  - `right(x)` is computed by setting `x ← x XOR (3 · 2^(level(x)−1))`, then replacing *x* with `left(x)` while
    `x ≥ n`.
  - The frontier is `[root]`, extended by `right(last)` until it reaches `n − 1`.
- **`ladder`** (`{version}`) → `{"ladder"}`, the base binary ladder.
  - Append `2^i − 1` for `i = 0, 1, …` until a value exceeds `version`.
  - Then binary-search between the last two: repeatedly append `mid = ⌊(lo + hi)/2⌋` while `lo + 1 < hi`, setting
    `lo = mid` if `mid ≤ version` and `hi = mid` otherwise.

**Stage 2, the DSIP side** (v0.14, T§7–T§10, spec-gap 124). These checks need no KEYTRANS proof bytes. Their inputs
are what the provider or the client knows once those proofs are done (T§6).

- **`alias-query`** (T§7: the provider's answer) — input `{request, over_limit, alias, exists, visible, authorized}`
  → `{"status", "answer"}`. The first rule that applies:
  1. `over_limit` is true → `{"status": 429, "answer": "rate-limited"}`;
  2. `request` is neither `search` nor `monitor` → `{"status": 400, "answer": "bad-request"}`;
  3. `alias` does not normalize (check `alias` above) → `{"status": 400, "answer": "alias-invalid"}`;
  4. a `search` with `exists` and `visible` both true → `{"status": 200, "answer": "search-response"}`;
  5. a `monitor` with `exists` and `authorized` both true → `{"status": 200, "answer": "monitor-response"}`;
  6. otherwise → `{"status": 404, "answer": "not-found"}`.

  `visible` matters only to a search, `authorized` only to a monitor request.
- **`alias-monitor`** (T§8: the provider's checks of a verified `alias-monitor` payload) — input `{payload, provider,
  values}`. `values` lists every DID the alias has had, oldest first; it is empty when the alias is absent. The
  output is `{"verdict": "accept", "label": <normalized alias>}` or `{"verdict": "refuse", "code"}`, the first that
  applies:
  1. `payload.to` ≠ `provider` → `wrong-audience`;
  2. `payload.alias` does not normalize → `alias-invalid`;
  3. `payload.from` is not in `values` → `not-owner`.
- **`alias-head`** (T§9: a received `alias-log-head` claim) — input `{claim, configuration, held}`.
  `configuration` is the hex Configuration the receiver pinned for `claim.provider`, or null; it is always one
  `configuration-accept` accepts. `held` is `[{tree_size, root}]`, the heads the receiver holds, at most one per size,
  `root` in base64url. The output is the first that applies:
  1. `{"outcome": "invalid", "reason": "malformed"}` when:
     - `claim.type` is not `alias-log-head`;
     - `claim.provider` is not a string that matches `^did:[a-z0-9]+:[A-Za-z0-9.%_:-]+$`;
     - `claim.tree_head` or `claim.root` is not a base64url string (the alphabet `A–Z a–z 0–9 - _`, no `=`, a length
       that is not 1 more than a multiple of 4; non-zero unused bits are accepted);
     - the decoded `root` is not 32 bytes;
     - the decoded `tree_head` is not exactly a `TreeHead`: `u64(tree_size) ‖ u16(n) ‖ n bytes`, nothing after;
     - `tree_size` is above 2^53−1 (portable as a JSON number, as in `configuration-accept`).
  2. `configuration` is null → `{"outcome": "ignored", "reason": "unknown-log"}`;
  3. the TreeHead's signature is not a valid Ed25519 signature by the configuration's `signature_public_key` over
     `configuration ‖ u64(tree_size) ‖ root` (check `tree-head` above) → `{"outcome": "invalid", "reason":
     "bad-signature"}`;
  4. `held` has this `tree_size` with another root → `{"outcome": "fork", "tree_size", "held_root", "claimed_root"}`,
     both roots in base64url as given;
  5. `held` has this `tree_size` with the same root → `{"outcome": "consistent", "tree_size"}`;
  6. otherwise → `{"outcome": "new", "tree_size"}`.

  Roots are compared as decoded bytes.
- **`alias-lookup-result`** (T§10) — input `{answer, proof, terminal_entry, rightmost_distinguished, fork}`. `answer`
  is `found` or `not-found`; `proof` is `verified` or `unverifiable`; `rightmost_distinguished` is an integer or null.
  The output is the first that applies:
  1. `answer` is `not-found` → `{"result": "not-found"}`;
  2. `fork` is true → `{"result": "unaudited", "reason": "fork"}`;
  3. `proof` is `unverifiable` → `{"result": "unaudited", "reason": "unverifiable"}`;
  4. `rightmost_distinguished` is null, or `terminal_entry > rightmost_distinguished` →
     `{"result": "unaudited", "reason": "pending"}`;
  5. otherwise → `{"result": "audited"}`.

## Kind: `pkarr`

Reachability hints carried on Pkarr: BEP 44 mutable items on the BitTorrent Mainline DHT (v0.9; DHT Hints Profile §9;
spec-gap 105).

- A `did:key` identity publishes `_dsip` TXT records in its own Pkarr zone, signed by its identity key.
- Binary values are lowercase hex. Integers in encodings are big-endian.
- `now` is Unix seconds, and a payload's timestamp `ts` is Unix **microseconds**.

**`check: "store"`** (v0.11, DHT Hints Profile §10) is a node's verify-before-store for `PUT /<z32>`. A node
serves every application's packets, so only the steps every Pkarr packet must pass are applied, plus §8.3's seq rule.
Readers still apply the full `hint` reader to what they fetch.
- **Input:** `{key, payload, held, now}`. `key` is the path segment, and `held` is the payload the node holds for that
  key, or `null`.
- **Output:** `{"outcome": "stored"}`, or `{"outcome": "kept", "reason"}` with reason `same`, `older` or
  `conflict`, or `{"outcome": "rejected", "reason"}`.

The first failing step gives the reason:
1. **`bad-key`:** `key` is not 52 characters of the z-base-32 alphabet (lowercase) with zero padding bits, so not
   the canonical encoding of a 32-byte key.
2. **Steps 2–5 of `check: "hint"`,** with `key` in place of the DID's key: `malformed`, `signature`, `future`.
3. **Against `held`** (none: `stored`). `held` is a packet this check stored earlier, so it is not verified again; only
   its `ts` is read. "The same bytes" compares the decoded payloads, not their hex text. With `ts` the payload's
   timestamp and `held_ts` the held one's:
   - `ts > held_ts`: `stored`;
   - equal, with the same bytes: `kept`, `same`;
   - equal, with different bytes: `kept`, `conflict` (§8.3 keeps the held one);
   - `ts < held_ts`: `kept`, `older`.

HTTP answers (profile §10): `stored` and `same` are 204, `older` and `conflict` are 409, and `rejected` is 400.

**`check: "hint"`** has input `{did, payload, now}`, where `payload` is a Pkarr relay payload:
`signature(64) ‖ ts(u64) ‖ dns`. The output is
`{"outcome": "hint", subject, seq, issued_at, expires_at, endpoints}` or `{"outcome": "rejected", reason}`.

The first failing step gives the reason:

1. **`did`** must be `did:key:z…` whose base58btc decodes to `0xed 0x01` plus 32 key bytes. Otherwise
   `not-did-key`.
2. **The payload** is hex (either case) for 72–1072 bytes. Anything else, including hex that does not decode, is
   `malformed`.
3. **The signature** is Ed25519 by the DID's key over the BEP 44 buffer
   `"3:seqi" ‖ decimal(ts) ‖ "e1:v" ‖ decimal(len(dns)) ‖ ":" ‖ dns`. A bad signature gives `signature`.
4. **`ts`** must be at most 2^53−1, so that it stays exact as a JSON number (Impl; BEP 44 allows up to 2^63−1, and
   2^53 µs is the year 2255), else `malformed`. It must also be at most `(now + 300) · 10^6`, else `future`.
5. **`dns`** must parse as an RFC 1035 message, else `malformed`:
   - It has a 12-byte header (ID, flags, QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT).
   - There are QDCOUNT questions (a name, then 4 bytes), then ANCOUNT + NSCOUNT + ARCOUNT records. Each record is
     a name, `type u16`, `class u16`, `ttl u32`, `rdlength u16` and `rdata`.
   - The message ends exactly where the last record does.
   - A name is a sequence of labels (length byte 1–63) ending in a zero byte, or ending in a compression pointer
     `0b11xxxxxx xxxxxxxx`. A pointer must point to an offset **before** the start of the name segment it appears in
     (counting from the start of the name, or from the previous pointer's target), and the name continues there.
   - Any other label type, or running past the end, is `malformed`.
   - Only the answer records are used.
6. **The DSIP records** are the answers whose name is exactly two labels, equal to `_dsip` and `z32(key)` after
   ASCII case-folding (A–Z only), with type 16 (TXT) and class exactly 1. Labels are compared one by one: a single
   label containing a `.` byte does not match. Every other answer is ignored.

   The DSIP records are processed in order. For each one, its rdata is first framed as a sequence of
   character-strings (a length byte, then that many bytes) that must consume it exactly, else `malformed`. Only then
   is its content checked. Each string must be UTF-8 `key=value`, split at the first `=`. The record
   becomes an endpoint `{uri, bindings[, service]}`:
   - exactly one `uri`, whose value starts with `wss://`;
   - one or more `b`, in order, which become `bindings`;
   - at most one `svc`, which becomes `service`, present only when given;
   - unknown keys are ignored.

   Anything else is `bad-endpoint`. Endpoints keep the records' order.
7. **No DSIP records** gives `no-endpoints`. Any DSIP record TTL above 3600 gives `ttl-too-long`.
8. **Expiry.** `issued_at = ⌊ts / 10^6⌋` and `expires_at = issued_at + min(TTL)`. If `now ≥ expires_at`, the
   reason is `expired`.
9. **The output:** `subject` is `did`, and `seq` is `ts`.

**`check: "select"`** (`{did, payload, held, now}`) applies §8.3 between a newly received payload and one already
held:
- `payload` is read as above; a rejection is the output.
- If `held` no longer reads (for example it has expired), the output is `{"winner": "input", "conflict": "none"}`.
- Otherwise:
  - a higher `seq` gives `{"winner": "input", "conflict": "newer-seq"}`;
  - a lower one gives `{"winner": "held", "conflict": "older-seq"}`;
  - an equal `seq` with byte-identical payloads gives `{"winner": "held", "conflict": "none"}`;
  - an equal `seq` with different payloads gives `{"winner": "held", "conflict": "same-seq-live"}`.

**`check: "bep44-signable"`** (`{seq, value, salt}`, salt hex or null) → `{"bytes"}`:
`["4:salt" ‖ decimal(len(salt)) ‖ ":" ‖ salt]` (only when the salt is non-empty) followed by
`"3:seqi" ‖ decimal(seq) ‖ "e1:v" ‖ decimal(len(value)) ‖ ":" ‖ value`.

**`check: "bep44-verify"`** (`{public_key, seq, value, salt, signature}`) → `{"valid"}`: an Ed25519 signature over
that buffer.

**`check: "z32-encode"`** (`{key}`) → `{"z32"}`, and **`check: "z32-decode"`** (`{z32}`) → `{"key"}`, or
`{"outcome": "rejected", "reason": "malformed" | "non-canonical"}`.
- z-base-32 uses the alphabet `ybndrfg8ejkmcpqxot1uwisza345h769`, most significant bit first.
- 32 bytes are 52 characters, the last carrying 1 key bit and 4 padding bits.
- Decoding requires exactly 52 alphabet characters (else `malformed`) and zero padding bits (else
  `non-canonical`).

**`check: "devices"`** (§9.1, multi-device identities; spec-gap 105 option (b)) resolves an identity's pointer and its
devices' hints. The input is `{did, payload, devices: {device_did: payload}, now, revocations?}`, where `devices`
holds the payloads fetched from each listed device's zone and `revocations` holds compact `delegation-revocation`
envelopes. The output is `{"outcome": "devices", seq, expires_at, devices: [...]}` or
`{"outcome": "rejected", reason}`.

**The pointer** (`payload`, under `did`) goes through steps 1–5 of `check: "hint"`, with their reasons. Then:
- **Records.** Only TXT records of class exactly 1, whose owner is exactly the two labels `_dsip-devices` and the
  zone (compared without case), are used, in message order. A record whose data does not split into
  character-strings is `malformed`.
- **Each record** must hold exactly one string starting `dev=`, whose value (read as UTF-8, invalid bytes replaced)
  is a `did:key` by step 1's rule. Otherwise the reason is `bad-pointer`, checked record by record before the rules
  below. Other strings are ignored.
- **None** gives `no-devices`.
- **A TTL above 604,800** gives `ttl-too-long`.
- **Expiry.** `expires_at` is the timestamp's seconds plus the smallest TTL; when `now ≥ expires_at`, `expired`.

The devices are the listed DIDs in record order, a repeated one (same text) kept once; every record's TTL counts
toward the smallest. Entries of `devices` the pointer does not list are ignored. Each entry of `devices`, in that order, is
`{device, outcome: "hint", endpoints, expires_at}` or `{device, outcome: "rejected", reason}`. The checks run in this
order:
1. `unavailable`: `devices` has no payload for it, or `null`.
2. Its payload read as `check: "hint"` under the device's DID; a failure gives that reason.
3. `delegation-missing`: no `_dsip-delegation.<z32(device)>` TXT record of class 1. `delegation-invalid`: more than
   one; data that does not split into character-strings; or strings whose concatenation is not three `.`-separated
   parts.
4. The delegation verified as §7.4 for `(did, device)` at `now`, with `revocations`. The reason is the verifier's:
   `delegation-invalid`, `delegation-capability`, `delegation-expired` or `delegation-revoked`.
5. Otherwise the device's `endpoints` are its hint's, and its `expires_at` is the earlier of the hint's and the
   delegation's.

**`check: "carry"`** (DHT Hints Profile §9 publishing, "keep the zone's other records"; spec-gap 105) is the records a
publisher carries over from its previous packet. The input is `{zone, dns}`: the zone's z-base-32 key, and the
previous packet's DNS message, already verified. The output is `{"keep": [{name, type, ttl, rdata}]}`, in message
order, or `{"error": "malformed"}`:

- **Parsing.** `dns` (hex; hex that does not decode is `malformed`) parses as for `check: "hint"`: the whole message,
  every section, and a failure anywhere is `malformed`, with no partial `keep`.
- **Which records.** Only the answer records are carried (Pkarr puts a zone's records there), minus those of class
  other than exactly IN (1), and those whose owner is exactly two labels, `_dsip`, `_dsip-devices` or
  `_dsip-delegation` then `zone`, of any type, compared ASCII case-insensitively (the publisher replaces those; §9.1). Records outside the zone are carried. An excluded record's
  rdata is not examined beyond its length.
- **`name`** is the owner name in uncompressed wire form (length-prefixed labels, then a zero byte), as hex. Label
  bytes keep their case.
- **Re-encoding.** Names inside `rdata` are expanded to the same uncompressed form for exactly the RFC 1035 types in
  which RFC 3597 §4 allows compression:
  - NS (2), MD (3), MF (4), CNAME (5), MB (7), MG (8), MR (9) and PTR (12): one name;
  - SOA (6): two names, then exactly 20 bytes;
  - MINFO (14): two names;
  - MX (15): 2 bytes, then a name.

  Each such `rdata` must hold exactly that, else `malformed`. Every byte a name occupies in place (its labels, its
  zero byte, or its 2 pointer bytes) must lie inside the `rdata`. A pointer follows the rule for owner names: it
  points before the start of the stretch it appears in, so it may reach an earlier record or an earlier name in the
  same `rdata`. Expanded names keep their label bytes' case. Every other type's `rdata` is copied as it is: RFC 3597 §4
  forbids compression in them.

**`check: "next-ts"`** (DHT Hints Profile §9) is the timestamp a publisher signs. The input is `{clock, previous?}`
(µs), and the output is `{"ts": max(clock, previous + 1)}`, or `{"ts": clock}` without `previous`. After the clock
steps backwards, this is ahead of the clock: the one case the profile allows, since a lower `seq` is refused
everywhere. A result above 2^53−1, which every reader rejects (`check: "hint"` step 4), is `{"error": "exhausted"}`:
the publisher signs nothing.

## Kind: `presence`

Presence Profile draft (`v1.0/dsip-presence-profile-v1.0-draft.md`, cited `P§n`; spec-gaps 135, 136): the subscriber's
side. `input.check` selects:

| check | input | expect |
|---|---|---|
| `aggregate` | `records` (each `{state, expires_at, device?}`), `asserted?` (`available` / `offline`, the body's `state`); `context.now` | `{state, token, source}` (P§4) |
| `audience-tag` | `secret_hex` (the identity's X25519 key agreement secret, 32 bytes, as stored: clamp it first), `subject`, `label` | `{tag}` (P§12.1) |
| `key` | `secret_hex`, `subject`, `kid` | `{key_hex}` (P§12.1) |
| `seal-record` | `record` (`subject`, `device`, `audience?`, `kid`, `seq`, `expires_at`), `state`, `key_hex`, `nonce_hex` | `{sealed_state}` (P§12.2) |
| `open-record` | `record` (as above with `sealed_state`), `keys` (`{kid: key_hex}`) | `accept {state}` (raw, no fallback), or in order `presence-key-unknown` → `sealed-too-short` → `aead-open-failed` → `presence-plaintext-invalid` (P§12.4) |
| `grant-keys-open` | `grant` (a `grant` payload with `presence_keys`), `recipient_secret_hex` (the grantee identity's secret, as stored) | `accept {keys: {kid: key_hex}}`, or in order `sealed-alg-unsupported` → `sealed-open-failed` → `sealed-plaintext-invalid` (P§12.3) |
| `view` | `records` (each a record's fields: `subject`, `device`, `seq`, `expires_at`, `audience?`, and `state` or `kid` + `sealed_state`), `keys`, `asserted?`; `context.now` | `{state, token, source, unreadable}` (P§12.4, P§4) |

`aggregate`: a record is valid while `expires_at` > now. The candidates are each valid record's `state` (source
`record`) and, when `asserted` is `available`, `available` (source `assertion`). With none the result is
`{"state": "offline", "token": "offline", "source": "none"}`. Otherwise the winner has the highest rank — `dnd` 4,
`busy` 3, `available` 2, `away` 1, `offline` 0, any other token ranking as `available` — and among equal ranks a
record before the assertion, then a registered token (`available`, `busy`, `away`, `dnd`, `offline`) before an
unknown one, then unknown tokens in code-point order. `token` is the winner's token, `state` the winner itself when registered and
`available` otherwise (P§5), `source` the winner's source. A record's `device` plays no part.

**Sealed records** (P§12; spec-gaps 152–157). HKDF is HKDF-SHA256 (RFC 5869) with an empty salt (32 zero bytes as
the HMAC key) and IKM `s`, the secret with RFC 7748 clamping applied (`s[0] &= 248; s[31] &= 127; s[31] |= 64`);
`0x00` separates the UTF-8 strings of every `info` and AAD.

- `audience-tag`: `"k-"` + the RFC 4648 base32 of the first 10 bytes of HKDF with info `dsip presence audience v1 ‖
  0x00 ‖ subject ‖ 0x00 ‖ label`, lower case, without padding (16 characters).
- `key`: 32 bytes of HKDF with info `dsip presence key v1 ‖ 0x00 ‖ subject ‖ 0x00 ‖ kid`.
- `seal-record`: the plaintext is `{"state":"S"}` (no whitespace) followed by spaces to 128 bytes; AES-256-GCM with
  `nonce_hex`; AAD `dsip presence v1 ‖ 0x00 ‖ subject ‖ 0x00 ‖ device ‖ 0x00 ‖ audience (empty when absent) ‖ 0x00 ‖
  kid ‖ 0x00 ‖ u64be(seq) ‖ u64be(expires_at)`; `sealed_state` is the unpadded base64url of nonce ‖ ciphertext ‖ tag.
- `open-record`: `presence-key-unknown` when `keys` has no entry for `kid`; `sealed-too-short` when the decoded
  `sealed_state` is not exactly 156 bytes; `aead-open-failed` when it does not open under that key and the AAD above;
  `presence-plaintext-invalid` unless the plaintext is UTF-8 JSON (§10.3, trailing spaces allowed) that is an object
  whose only key is `state`, a string matching `[a-z][a-z0-9-]*` of at most 64 characters.
- `grant-keys-open`: `sealed-alg-unsupported` unless `presence_keys.alg` is `hpke-base-x25519-sha256-aes128gcm`;
  `sealed-open-failed` when HPKE (as `hpke-open`) with the clamped recipient secret, info `dsip presence keys v1` and
  AAD `id ‖ 0x00 ‖ from ‖ 0x00 ‖ to` of the grant does not open; `sealed-plaintext-invalid` unless the plaintext's
  length is a positive multiple of 256 and it is UTF-8 JSON that is an object whose only key is `keys`, a list whose
  every entry is an object of exactly `kid` and `key`, both strings, `kid` matching `(main|[a-z][a-z0-9-]*)\.(0|[1-9][0-9]*)`
  with its scope (the part before the last `.`) `main` or the grant's `presence_audience`, and `key` the unpadded
  base64url of exactly 32 bytes. The result maps each `kid` to its key in hex (a later entry for the same `kid` wins).
- `view`: each record with `sealed_state` is opened as `open-record`; one that does not open is left out and its
  `device` listed in `unreadable` (sorted, each once); the rest go to `aggregate` as `{state, expires_at}` with the
  same `asserted`, whose result is returned with `unreadable` added.

## Kind: `tn-binding`

Verifying a number binding: a STIR-signed statement that a phone number is used by a DID (Number Attestation
Profile, draft, N§3; spec-gap 110). Everything is offline. The vector supplies the certificate chain that `x5u`
would serve, the trust list, the DID's document and the clock.

**Context:**

- `trust_anchors`: the STI-CA list. An array of DER certificates in padded base64 (RFC 4648 alphabet, `=` padding,
  no whitespace). An entry that is not such a string, or does not parse as a certificate (step 2), is ignored.
- `certificates`: `{url: text}`, what each `x5u` URL serves. A URL missing from this map cannot be fetched.
- `spc_numbers`: `{spc: [digits]}`, the relying party's lookup of the numbers assigned to each Service Provider
  Code. Numbers are written without the `+`.
- `require_status`: a boolean, the relying party's policy for step 8.
- `status`: `{url: "good" | "revoked"}`, what each status URL answers. A URL missing from this map does not answer,
  and neither does one whose value is anything other than these two strings.

**Input:** `{binding, did, did_document, now}`.

- `binding` is the compact JWS text.
- `did` is the DID being checked.
- `did_document` is its resolved document, or `null` when resolution failed.
- `now` is integer Unix seconds.

**Expect**, exactly one of:

- `{"outcome": "verified", "tn", "did", "expires", "attested_by"}`.
  - `tn` and `did` are the payload's.
  - `expires` is the payload's `exp`.
  - `attested_by` is the first organizationName (2.5.4.10) in the leaf certificate's subject, in encoded order. When
    there is none, it is the first commonName (2.5.4.3). When there is neither, it is `null`. Only UTF8String and
    PrintableString values count, and only when their bytes are valid UTF-8. Any other attribute of the right type is
    passed over: another string type, or bytes that are not UTF-8.
- `{"outcome": "rejected", "reason"}`, with `reason` from the steps below.

**Check order (normative for parity).** The first failing step gives the reason. Within a step, the order of the
checks does not matter, because they all give that step's reason.

1. **`malformed`.** Every pattern in this section matches the whole string: a trailing newline is not allowed.
   - **Shape.** `binding` is three segments separated by `.`. Each is base64url: the alphabet `A–Z a–z 0–9 - _`, no
     `=`, and a length that is not 1 more than a multiple of 4. Non-zero unused bits in the last character are
     accepted (RFC 4648 §3.5). The third segment is not empty.
   - **JSON.** The decoded header and the decoded payload are each UTF-8, and each is an I-JSON object:
     - it parses as JSON, and a leading byte-order mark is not JSON;
     - no object has a member name twice;
     - no string or name contains a lone surrogate, escaped or not;
     - every number is an integer from −(2^53−1) to 2^53−1, written without a fraction or exponent.
   - **Header.**
     - `alg` is the string `ES256`;
     - `typ` is the string `dsip-tn-binding+jwt`;
     - `x5u` is a string that starts `https://`;
     - there is no `crit` member.
     - Other members are ignored.
   - **Payload.**
     - `tn` is a string matching `^\+[1-9][0-9]{1,14}$`;
     - `did` is a string that starts `did:`;
     - `iat` is an integer ≥ 0;
     - `exp` is an integer greater than `iat`;
     - `jti` is a string matching `^[0-7][0-9A-HJKMNP-TV-Z]{25}$`;
     - `status` is absent, or a string that starts `https://`. `null` is not absent.
     - Other members are ignored.
2. **`untrusted-certificate`.**
   - **Fetch.** `certificates` has an entry for `x5u`.
   - **PEM.** The text holds at least one block from a `-----BEGIN CERTIFICATE-----` line to the next
     `-----END CERTIFICATE-----` line, with no block left open.
     - Lines end in LF or CRLF. A marker line is exactly the marker: no other characters, leading or trailing.
     - Text outside the blocks is ignored.
     - A block's body lines, with SP, HT, CR and LF removed, are padded base64: RFC 4648's alphabet, `=` padding,
       and a length that is a multiple of 4. Non-zero unused bits in the last character are accepted (RFC 4648 §3.5).
     - The blocks are the **chain**, leaf first. Every block must parse, including any after an anchor.
   - **Parse.** Each block is an X.509 v3 certificate (`version` 2) in DER, and nothing follows it. Also:
     - its `tbsCertificate` `signature` field is byte-for-byte the outer `signatureAlgorithm`;
     - no extension appears twice (RFC 5280 §4.2);
     - a basicConstraints with `cA` false has no pathLenConstraint (RFC 5280 §4.2.1.9);
     - its basicConstraints and keyUsage, if present, decode (a negative pathLenConstraint does not);
     - its TNAuthList, if present, is well-formed (below).

     These hold for every block, including blocks after an anchor.

     **Not pinned:** other encodings that DER or RFC 5280 forbid inside a certificate a CA signed. Examples:
     - a BOOLEAN other than `00` or `FF`;
     - a DEFAULT value encoded;
     - a non-minimal BIT STRING;
     - an empty `extensions` SEQUENCE;
     - GeneralizedTime before 2050;
     - a serial number that is negative, zero or longer than 20 bytes;
     - a PrintableString outside its character set.

     A verifier may refuse such a certificate (`untrusted-certificate`) or read it as it reads. The vectors and the
     differential fuzz avoid them (spec-gap 110).
   - **The path.** It is the chain up to and including the first certificate that is byte-for-byte a trust anchor,
     and the rest of the chain is ignored.
     - When no chain certificate is an anchor, the path is the whole chain plus an **issuing anchor**: a trust
       anchor whose subject equals the last chain certificate's issuer and whose key verifies its signature.
     - When several anchors qualify, step 2 passes if the path through any one of them passes every check below.
     - With no such anchor, the check fails.
   - **Links.** Each chain certificate on the path, except an anchor that ends it, must link to the certificate
     after it on the path:
     - its issuer is byte-for-byte the next one's subject (the DER `Name`, not compared as text);
     - the next one's key verifies its signature over its `tbsCertificate` bytes.
   - **Every certificate on the path,** the anchor included:
     - its `signatureAlgorithm` is ecdsa-with-SHA256 (1.2.840.10045.4.3.2), with no parameters;
     - its key is id-ecPublicKey on prime256v1 (1.2.840.10045.3.1.7), and the point is valid;
     - it is valid at `now`: notBefore ≤ `now` ≤ notAfter;
     - it has no critical extension other than basicConstraints (2.5.29.19), keyUsage (2.5.29.15) and TNAuthList
       (1.3.6.1.5.5.7.1.26).

     The anchor's own signature is never checked.
   - **Issuers.** Number the path from 0 (the leaf). Every certificate at position *p* ≥ 1 issues the one before it,
     and:
     - it has basicConstraints with `cA` true;
     - if it has keyUsage, `keyCertSign` is set;
     - if it has a pathLenConstraint *L*, then *p* − 1 ≤ *L*.
   - **Leaf.** If the leaf has keyUsage, `digitalSignature` is set.
   - **A well-formed TNAuthList** (RFC 8226 §9, EXPLICIT tags) is the extension's value: a DER `SEQUENCE` of one or
     more entries, and nothing after it. Each entry is exactly one of:
     - `[0]` (`A0`) wrapping an IA5String: an **spc**, at least 1 byte, every byte below 0x80;
     - `[1]` (`A1`) wrapping a `SEQUENCE` of exactly a TelephoneNumber **start** and an `INTEGER` **count** ≥ 2;
     - `[2]` (`A2`) wrapping a TelephoneNumber: **one**.

     A TelephoneNumber is an IA5String of 1 to 15 characters from `0123456789#*`. DER is strict:
     - lengths are definite and minimal (the short form below 128);
     - an `INTEGER` has no redundant leading `00` or `FF` byte;
     - every tagged or constructed element holds exactly its contents.
3. **`signature`.**
   - The third segment decodes to exactly 64 bytes. They are *r* then *s*, each 32 bytes big-endian.
   - 0 < *r*, *s* < *n*, the P-256 order.
   - The leaf key verifies ECDSA over SHA-256 of the signing input: the ASCII header segment, `.`, the payload
     segment, as received.
   - A high *s* is accepted, as ECDSA allows.
4. **`not-authorized-for-tn`.** The leaf has no TNAuthList, or some certificate on the path has a TNAuthList that does
   not cover `tn`. With *D* being `tn` without its `+`, a list covers it when one entry does:
   - **one**: the entry equals *D*;
   - **range**: start is all digits, start has the same length as *D*, and 0 ≤ *D* − start < count, compared as
     integers;
   - **spc**: `spc_numbers[spc]` exists and contains *D*.
5. **Time.**
   - **`lifetime-too-long`**: `exp − iat` > 604800.
   - **`not-yet-valid`**: `iat` > `now` + 300.
   - **`expired`**: `now` ≥ `exp`.

   These are checked in that order.
6. **`did-mismatch`.** The payload's `did` is not `did`, compared exactly.
7. **`not-claimed-by-did`.** `did_document` is not an object, its `id` is not `did`, its `alsoKnownAs` is not an
   array, or no element of that array is the string `tel:` + `tn`.
8. **Status**, only when `require_status` is true; otherwise `status` is never consulted:
   - **`status-unavailable`**: the payload has no `status`, or `status` has no entry for it;
   - **`revoked`**: the entry is `revoked`.

**`check`.** `input.check` selects what is tested. Absent, it is the verification above. Two more checks build on
it.

**`check: "claim"`** is a `tel` claim carrying a binding, in an invite's `identity.claims` (N§4).
- **Input:** `{check, claim, identity, did_document, now}`, with the same context as verification. `identity` is the
  envelope's verified signing identity: the binding is verified against it.
- **Expect**, one of:
  - `{"outcome": "ignored"}`: `claim` is not an object with `type` `tel` and a `binding` member (of any value), or
    it has a string `verifier`. A claim with a string `verifier` is a gateway's `tel` claim (G§5), even if it also
    carries a `binding`, and the `trust` kind renders it.
  - `{"outcome": "attested", "line", "issued", "expires"}`:
    - `line` is `<tn> · number attested by <attested_by> for this identity`, or `<tn> · number attested for this
      identity` when `attested_by` is `null`. `<tn>` is the E.164 string as it is.
    - `issued` is the binding's `iat`, and `expires` its `exp`.
  - `{"outcome": "dropped", "reason", "line"}`. The order:
    1. `binding` is not a string: `malformed`;
    2. otherwise the first failing verification step's reason;
    3. otherwise, the claim's `number` is not the binding's `tn` (compared exactly): `number-mismatch`.

    `line` is `<number> (unverified)` when the claim's `number` is a string matching `^\+[1-9][0-9]{1,14}$`, and
    `null` otherwise (§18.2: an unverified claim may still be shown, marked).

**`check: "contact"`** is N§5's warning, when a verified number now belongs to a different identity.
- **Input:** `{check, contacts, attested}`.
  - `contacts` is the client's address book: an array of `{name, did, numbers}`, with `numbers` in E.164.
  - `attested` is `{tn, did, attested_by, issued}`: a verified binding (`issued` is its `iat`).
- **Expect:** a string or `null`.
  - **`null`** when no contact lists `tn`, or when some contact listing `tn` has `did` equal to `attested.did`: that
    is the stored identity, unchanged.
  - **Otherwise, the first contact** (in array order) that lists `tn`:
    `<tn> now belongs to a different identity (number attested by <attested_by> since <date>). Your contact "<name>" is <contact did>.`
    - `<date>` is `issued` as a UTC calendar date, `YYYY-MM-DD`.
    - When `attested_by` is `null`, the parenthesis reads `(number attested since <date>)`.

**`check: "store"`** is a `dsip-node`'s verify-before-store for `PUT /dsip/v1/tn/<tn>`: discovery route 1 (N§6).
A node resolves no DIDs, so it applies verification steps 1–5 only. The reader applies all eight.
- **Input:** `{check, tn, binding, held, now}`, with the same context as verification.
  - `tn` is the path segment.
  - `held` is the array of bindings the node holds for `tn`. Each one passed this check earlier and is not verified
    again; only its payload is read. An entry whose payload does not read is dropped with the expired ones. Reading
    it means:
    - three `.`-separated segments, the second base64url;
    - decoding to an I-JSON object;
    - with a string `did`, and integer `iat` and `exp`.
  - A `held` that is not an array is empty.
  - A held set with two entries for one DID is outside the contract: this check never makes one.
- **Expect:** `{"outcome": "stored", "held"}`, `{"outcome": "kept", "reason"}` or `{"outcome": "rejected", "reason"}`.
  `held` is the new set: by `iat` newest first, then by binding text in byte order.

The first rule that applies decides:
1. **`bad-number`:** `tn` does not match `^\+[1-9][0-9]{1,14}$`.
2. **Verification steps 1–5:** the first failing step's reason (`malformed` … `expired`).
3. **`tn-mismatch`:** the payload's `tn` is not `tn`.
4. **Against `held`.**
   - Held bindings with `now` ≥ `exp` are dropped first.
   - When a held binding names the same `did`:
     - the same text: `kept`, `same`;
     - a greater `iat`: `stored`, replacing it;
     - otherwise: `kept`, `older`.
   - Otherwise, while fewer than **4** are held: `stored`, added.
   - Otherwise the **eviction candidate** is the held binding with the smallest `iat`; among equals, the greatest
     binding text. If the new `iat` is greater than the candidate's: `stored`, the candidate evicted. Otherwise:
     `kept`, `full`.

HTTP answers: `stored` and `same` are 204, `older` and `full` are 409, and `rejected` is 400. `GET
/dsip/v1/tn/<tn>` answers 200 `{"bindings": [...]}`: the unexpired held set, in the order above, and `[]` when there
are none.

**`check: "select"`** is the reader's choice among the bindings a lookup returned: number → DID (N§6, N§7).
- **Input:** `{check, tn, bindings, documents, now}`, with the same context as verification. `documents` maps each
  DID to its resolved document; a DID missing from it did not resolve.
- **Each binding** in `bindings` is verified, all eight steps, as follows:
  - the DID being checked is its own payload's `did`, and its document is `documents[did]` (or `null`);
  - a `bindings` that is not an array is empty, and a `documents` that is not an object resolves nothing;
  - a binding that does not parse, fails a step, or whose `tn` is not `tn` is passed over.
- **Expect:**
  - `{"outcome": "none"}` when none verifies.
  - Otherwise `{"outcome": "found", "did", "attested_by", "issued", "others"}`:
    - the **winner** is the verified binding with the greatest `iat`, ties broken by the smallest binding text in
      byte order;
    - `did`, `attested_by` and `issued` (its `iat`) are the winner's;
    - `others` holds the other verified bindings' DIDs that differ from the winner's, each once, sorted.

    A non-empty `others` means two identities hold verified claims to the number: a port in progress, or a hijack.
    The client uses the winner and says so (N§7).

**`check: "authority"`** (v0.12) is a client pooling what the number's authorities served it: discovery route 2
(N§6), its serving half. Each configured authority was asked `GET https://<authority>/.well-known/dsip/tn/<tn>`.
- **Input:** `{check, tn, answers, documents, now}`, with the same context as verification. `answers` is an array of
  `{authority, status, body}`, in the order the authorities are configured: `authority` is the string the client
  configured, `status` the HTTP status as an integer or `null` when there was no answer, and `body` the response
  body as JSON, any value, or `null`. `documents` is as in `select`.
- **The pool.** Each answer in order contributes when `status` is the JSON integer `200` (a number written with a
  fraction or exponent is not; the vectors carry none, since an implementation in a language without that
  distinction cannot tell) and `body` is an object whose `bindings` is an array: each element that is a string joins the pool, once, in first-occurrence order. Any other answer
  contributes nothing.
- **Expect:** the `select` check over the pool, with `tn`, `documents` and `now`: `{"outcome": "none"}`, or
  `{"outcome": "found", "did", "attested_by", "issued", "others", "served_by"}`, where `served_by` lists, in `answers`
  order and each once, the `authority` of every contributing answer whose `bindings` holds the winning binding's
  text: the parties accountable for the answer. An `answers` that is not an array is empty, and an element that is
  not an object contributes nothing. `authority` is a string in every vector; the check is not defined otherwise.

A binding served this way is verified exactly as one a node served; what the authority adds is its name on the
answer, and, with T§ stage 2, the log entry that makes that name auditable (N§6, T§6).

**Gateway checks** (stage 4 of the profile; spec-gap 110 item I). A DSIP↔PSTN gateway is a relying party on both
sides: it verifies a PSTN caller's SHAKEN PASSporT (G§5), it finds the DSIP identity behind a dialled number (N§6.1),
and it asserts a DSIP caller's bound number toward the PSTN (N§4.1). Three checks pin those rules.

**`check: "passport"`** is a gateway's verification of the `Identity` header on an inbound SIP INVITE (G§5, N§4.1;
RFC 8224 §6.2, RFC 8225, RFC 8588). Its result is the `identity` that the `gateway` kind's `claims` check renders.
- **Input:** `{check, identity, from_tn, to_tn, now}`, with the same context as verification. `require_status` and
  `status` are never consulted: a PASSporT has no status URL.
  - `identity` is the value of the INVITE's `Identity` header, as text, or `null` when the INVITE carried none.
  - `from_tn` is the user part of the `From` URI, and `to_tn` the user part of the Request-URI, as received.
  - `now` is integer Unix seconds.
- **Numbers are compared canonically** (RFC 8224 §8.3): a leading `+` is removed, then every `-`, `.`, `(`, `)` and
  SP; what remains must be 1 to 15 characters from `0`–`9`, otherwise the number matches nothing.
- **Expect:** `{"attest", "verified": true}` when verified, otherwise `{"attest", "verified": false, "reason"}`.
  `attest` is `A`, `B` or `C`, or `none` when no PASSporT was accepted. The first rule that applies decides:
  1. **`no-identity-header`** (`none`): `identity` is not a string.
  2. **`malformed`** (`none`): the header value does not read as a token and parameters. The value is split on `;`.
     The first part, with SP and HT removed from both ends, is the token. Every other part is `name=value`, with SP
     and HT removed from both ends of the name and of the value, the value being everything after the first `=`; a
     part without `=` (a trailing `;` makes one), an empty name, an empty value or a name given twice is `malformed`.
     Names are compared case-insensitively, values exactly. An `info` parameter is required, and its value is `<`,
     the URI, `>`; the URI may be empty, which rule 8 then refuses.
  3. **`unsupported`** (`none`): an `alg` parameter other than `ES256`, or a `ppt` parameter other than `shaken`
     (RFC 8224 §6.2.3: a verifier ignores an `Identity` header it cannot process). Other parameters are ignored.
  4. **`malformed`** (`none`): the token does not read.
     - It is three base64url segments, the first two decoding to I-JSON objects: the rules of verification step 1.
     - Header: `alg` is `ES256`, `typ` is `passport`, `ppt` is `shaken`, and `x5u` is a string that starts
       `https://`. Other members are ignored.
     - Payload: `attest` is `A`, `B` or `C`; `orig` is an object whose `tn` is a string with a canonical form;
       `dest` is an object whose `tn` is a non-empty array of strings, each with a canonical form; `iat` is an
       integer ≥ 0. Other members (`origid`, `rcd`, …) are ignored.
  5. **`orig-mismatch`** (`none`): `orig.tn` and `from_tn` differ canonically. The PASSporT attests some other call
     and is discarded whole (G§5): no level is kept.

  From here `attest` is the payload's, and when a rule fails, `verified` is false with its reason:

  6. **`dest-mismatch`**: no element of `dest.tn` equals `to_tn` canonically.
  7. **`stale`**: |`now` − `iat`| > 60 (RFC 8224 §6.2.1's freshness).
  8. **`x5u-mismatch`**: the header's `x5u` is not the `info` URI, compared exactly.
  9. **`untrusted-certificate`**: verification step 2 on `certificates[x5u]`, at `now`.
  10. **`signature`**: verification step 3, over the token's signing input.
  11. **`not-authorized-for-tn`**, for `attest` `A` only: verification step 4 with the canonical `orig.tn` as *D*. `B`
      and `C` attest no authority over the number (RFC 8588 §3), so the step is skipped for them.

**`check: "route"`** is a gateway resolving an inbound PSTN call's dialled number to the DSIP identity it invites
(G§3.2's "resolved DSIP target", N§6.1).
- **Input:** `{check, to_tn, configured, bindings, documents, now}`, with the same context as verification.
  - `to_tn` is the dialled number as the gateway canonicalized it: E.164 (`+` and digits) when it is a number, and
    otherwise the Request-URI user as received.
  - `configured` is the operator's own table, `{number: did}`.
  - `bindings` is what the N§6 route 1 lookup returned (`null` when no node answered), and `documents` is as in
    `select`.
- **Expect**, the first that applies:
  1. `{"outcome": "configured", "did"}`: `configured` is an object whose member named `to_tn` is a string. The
     operator's table is the operator's statement about its own trunk, and a binding never overrides it.
  2. `{"outcome": "binding", "did", "attested_by", "issued", "others"}`: `to_tn` matches `^\+[1-9][0-9]{1,14}$` and
     the `select` check, with `tn` = `to_tn`, finds a binding. The members are `select`'s.
  3. `{"outcome": "none"}`: the gateway refuses the INVITE `identity.unknown` (404, Q.850 cause 1; G§4.2).

**`check: "assert"`** is a gateway carrying a DSIP caller's bound number to the PSTN (N§4.1): the SIP `From` it
presents, and the SHAKEN PASSporT it signs under its own STIR certificate when it may.
- **Context:** verification's, plus `gateway`: `{x5u, key}`. `x5u` names the gateway's own certificate chain
  (`certificates[x5u]` serves it), and `key` is the private key of that chain's leaf: a P-256 key as a PKCS#8 PEM
  (`-----BEGIN PRIVATE KEY-----`). A context without `gateway` is a gateway that holds no STIR certificate.
- **Input:** `{check, claims, identity, did_document, to_tn, now, origid}`.
  - `claims` is the invite's `identity.claims`; `identity` is the envelope's verified signing identity, and
    `did_document` its document, as in `claim`.
  - `to_tn` is the number the DSIP caller dialled, as the gateway canonicalized it.
  - `origid` is the call's SHAKEN origination identifier, a string (RFC 8588 §4: a UUID the gateway makes per call).
    The inputs are what the gateway holds: `from_tn`, `to_tn` and `origid` are strings in every vector, and the
    checks are not defined for anything else.
- **Expect:** `{"from", "passport", "assertable"}`, with `reason` when `assertable` is false.
  - `from` is the number the gateway presents as the SIP `From` user, or `null`: the gateway's own identity.
  - `passport` is `{"header", "claims"}`, the PASSporT's decoded protected header and payload, or `null`. The
    signature is not pinned, because ECDSA signatures differ between implementations; the gateway sends the compact
    JWS as the `Identity` header value `<token>;info=<x5u>;alg=ES256;ppt=shaken`.
  - `assertable` false is G§7's `identity-not-assertable`.

  The first rule that applies decides:
  1. **The binding.** Each element of `claims` (a non-array is empty), in order, goes through the `claim` check with
     `identity`, `did_document` and `now`. The first `attested` claim gives the number: its `number`. When none is
     attested, the result is `{"from": null, "passport": null, "assertable": false, "reason"}`, with `reason` the
     first `dropped` claim's reason, or `no-binding` when no claim was dropped either.

  From here `from` is the number; a failing rule gives `passport` `null`, `assertable` false and its reason:

  2. **`bad-destination`**: `to_tn` does not match `^\+[1-9][0-9]{1,14}$`. The gateway then declines the DSIP
     invite `identity.unknown` (spec-gap 111), as it does when the invite names no `destination` at all.
  3. **`no-certificate`**: `gateway` is not an object, its `x5u` is not a string, or its `key` is not a string
     holding a PKCS#8 PEM (`-----BEGIN PRIVATE KEY-----`) P-256 private key. A SEC1 `EC PRIVATE KEY` PEM is not
     one.
  4. **`untrusted-certificate`**: verification step 2 on `certificates[gateway.x5u]`, at `now`.
  5. **`not-authorized-for-tn`**: verification step 4 for the number, on that path. An RFC 9060 delegate certificate
     covers exactly the numbers its carrier delegated (spec-gap 110 item A: path (c)).
  6. **`key-mismatch`**: the key's public point is not the leaf's.
  7. **Signed.** `assertable` is true and `passport` is:
     - `header`: `{"alg": "ES256", "ppt": "shaken", "typ": "passport", "x5u": <gateway.x5u>}`;
     - `claims`: `{"attest": "A", "dest": {"tn": [<to_tn> without its +]}, "iat": <now>, "orig": {"tn": <number>
       without its +}, "origid": <origid>}`.

     The token is the two objects serialized as RFC 8225 §9 says (members in lexicographic order, no whitespace),
     base64url-encoded and joined by `.`, then ES256-signed by the key over that signing input (RFC 7515 §5.1). The
     level is `A`: the caller proved to the gateway that the number is its own, and the certificate authorizes the
     gateway for it.

**Fixtures.** The vector generator makes a test STIR PKI:
- an STI-CA root;
- an intermediate CA;
- service-provider certificates with each kind of TNAuthList entry;
- an RFC 9060 delegate certificate: Carrier Example's delegation CA (a range of 100 numbers) issues Enterprise
  Example's leaf for the number. The gateway checks use it as the gateway's own chain, served at
  `https://gw.example/sti.pem`, with its key as the `gateway.key` PEM;
- SHAKEN PASSporTs signed by the service-provider and delegate leaves, with `origid`
  `9f1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d`;
- certificates that break each step-2 rule.

Keys are P-256 scalars from `sha256("dsip-vector-tn:" + name)`. Signatures use RFC 6979 deterministic nonces, so the
vectors regenerate byte for byte.

## Kind: `key-agreement`

Key agreement delegation (core §7.3, 1.x; spec-gap 179): an identity-signed credential naming an independent X25519 key,
which devices hold so that they open what is sealed to the identity without holding its signing key. Payload schema:
`key-agreement-delegation` in the core set (not a message type: not in the dispatcher). `context` is the usual one
(`now`, `did_documents`, `delegations`); `input.check` selects:

| check | input | expect |
|---|---|---|
| `delegation` | `delegation` (an envelope object, or anything else), `subject?` | `accept {subject, key, x25519_pk_hex, expires_at}`, or in order `credential-invalid` → `schema-invalid` → `not-subject-signed` → `subject-mismatch` → `validity-invalid` → `not-yet-valid` → `expired` |
| `recipient-key` | `did`, `delegations` (a list), `document_key_agreement?` (multibase) | `accept {source, key?, x25519_pk_hex?}` |

**Verifying one** (`delegation`): `credential-invalid` unless it passes stages 2–6 of the pipeline as a delegation does
(shape, header, `kid` resolution under `context`, signature, payload parse with the §10.3 rules; no core-field check, no
replay window, no dedup). Then `schema-invalid` unless the payload is valid against `key-agreement-delegation` and its
`key` decodes to `0xec 0x01` followed by 32 bytes (the pattern admits strings that do not);
`not-subject-signed` unless the DID of the signing `kid` is the payload's `subject` (a device's key never counts, even
under a live delegation); `subject-mismatch` when `input.subject` is given and differs; `validity-invalid` unless
`issued_at` < `expires_at` ≤ `issued_at` + 31,536,000; `not-yet-valid` when `issued_at` > `now` + 300; `expired` when
`now` ≥ `expires_at`. `key` is the payload's (multibase base58btc of `0xec 0x01` and the 32-byte key); `x25519_pk_hex`
those 32 bytes in lower-case hex.

**The recipient key** (`recipient-key`, §7.3 and §10.4 rule 3): `source` is `document` when
`document_key_agreement` is given (its key); else `delegation`, the current one of `delegations`: of those that verify
(as above, with `input.did` as the subject) the one with the greatest `issued_at`, ties to the smaller `key` compared
as strings; else `derived` for a `did:key` (the X25519 public key the did:key method derives from the Ed25519 public
key: the Montgomery `u = (1 + y) / (1 − y) mod 2^255 − 19`, `key` its multibase); else `none`, with no `key` and no
`x25519_pk_hex`.

## Kind: `wake`

Wake Profile draft (`v1.0/dsip-wake-profile-v1.0-draft.md`, cited `W§n`; spec-gaps 169–175). Schemas are the
profile's own set, `v1.0/dsip-wake-schemas-draft/schemas/` (names below without `.schema.json`). Every input that is a
message payload has already passed the envelope pipeline; these vectors start after it. `input.check` selects:

| check | input | expect |
|---|---|---|
| `schema` | `schema` (a name in the wake set), `value` | `accept`, or `schema-invalid` |
| `enrol` | `enrol` (a `wake-enrol` payload); `context.apps` (the `{provider, app}` pairs the gateway pushes for) | `accept {enrolment}`, or in order `schema-invalid` → `unsupported-app` |
| `register` | `register` (a `wake-register` payload), `device` (its verified signer); `context.waker`, `context.now`, `context.gateways?` | `accept {registration}` or `accept {removed: true}`, or in order `schema-invalid` → `registration-invalid` → `waker-mismatch` → `registration-invalid` → `gateway-unknown` |
| `gateway` | `wake` (a `wake` payload), `signer` (its verified `from`); `context.gateway`, `context.now`, `context.handles` | `accept {forward}`, or in order `schema-invalid` → `not-authorized` → `expired` |
| `open-hint` | `sealed`, `session`, `secret_hex` | `accept {hint}`, or in order `sealed-alg-unsupported` → `sealed-open-failed` → `sealed-plaintext-invalid` |
| (none) | `steps`, each `{event}`; `context.component` (`relay` or `mailbox`) | per step `{emit, registrations}` |

A refusal with a W§8.1 token is `{"verdict": "reject", "code": C, "reason": "wake.C"}` (`unsupported-app` →
`wake.unsupported-app`, and so on); `schema-invalid` and the `open-hint` codes carry no `reason`.

**Verifying a registration** (W§4.1), used by `register` and `gateway`: `registration` is a DSIP-JOSE envelope verified
as a delegation is, by stages 2–6 of the pipeline (shape, header, `kid` resolution, signature, payload parse with the
§10.3 rules) with no core-field check, no replay window and no dedup; then its payload must be valid against
`wake-registration`, and the DID of the signing `kid` must equal `key`. Any failure is "does not verify".

- `enrol` (W§3): `unsupported-app` unless `{provider, app}` is one of `context.apps` (compared as pairs; an unknown
  provider is simply not there). `enrolment` is `{key, provider, app, token}`, `key` the payload's `from`, plus
  `environment` (the payload's, default `production`) when `provider` is `apns` and never otherwise.
- `register` (W§4.2): after `schema-invalid`, a payload with `remove: true` is `accept {removed: true}`. Otherwise
  `registration-invalid` when the registration does not verify; `waker-mismatch` unless its `waker` is
  `context.waker`; `registration-invalid` unless `issued_at` < `expires_at` ≤ `issued_at` + 2,592,000, `expires_at` >
  `now` and `issued_at` ≤ `now` + 300; `gateway-unknown` when `context.gateways` is present and lacks its `gateway`
  (absent, any gateway is admitted). `registration` is `{device, key, gateway, handle, expires_at}` from `input.device`
  and the registration, plus `kinds` (the payload's, each once, sorted by code point) and `seal_key` when the payload
  has them.
- `gateway` (W§5.3): `context.handles` maps each handle the gateway issued to `{key, provider, app, token,
  environment?}`. `not-authorized` unless all hold: the registration verifies, its `handle` is in `handles`, its
  `key` is that entry's `key`, its `waker` is `input.signer`, its `gateway` is `context.gateway`, its `expires_at` >
  `now` (the lifetime cap is not checked here). Then `expired` when `deliver_by` ≤ `now`. `forward` is `{provider,
  app, token, class, deliver_by, data}` from the handle's entry and the wake, plus `environment` (the entry's, default
  `production`) when the provider is `apns`. `class` is `call` for kind `call` or `call-ended` and `message` for any
  other kind. `data` is `{"dsip-wake": {kind, waker, session?, sealed?}}`: the wake's `kind` as sent, `waker` the
  signer, and `session` and `sealed` copied when the wake has them.
- `open-hint` (W§6): `sealed-alg-unsupported` unless `sealed.alg` is `hpke-base-x25519-sha256-aes128gcm`;
  `sealed-open-failed` when `enc` or `ct` is not unpadded base64url, or HPKE base mode (M§6.9's suite; RFC 9180) with
  the X25519 private key `secret_hex`, `info` `dsip wake hint v1` and AAD the UTF-8 of `session` does not open;
  `sealed-plaintext-invalid` unless the plaintext is exactly 256 bytes and, with its trailing spaces (0x20) removed,
  is UTF-8 JSON under §10.3 (a number with a fraction or exponent is refused) valid against `wake-hint`. `hint` is that
  JSON object.

**Wake traces** (W§4.3, W§5.1). A waker holds a registration per device (`{identity, expires_at, kinds?}`), the set of
bound devices, and, at a relay, held invites; each event carries `at`. Before the event is applied, in this order:
every held invite with `expires_at` ≤ `at` stops being held at its `expires_at` (in session-id order); then every
registration with `expires_at` ≤ `at` ends with cause `expired` (in DID order). A registration is *live* at a time
`T` when it exists and its `expires_at` > `T`; a device *wants* a kind when its registration has no `kinds` or
`kinds` contains it. Events:

| event | effect |
|---|---|
| `register: {device, identity, expires_at, kinds?}` | stores the device's registration, replacing any; emits nothing |
| `remove`, `revoke`, `forget`: a device | ends its registration with cause `removed`, `revoked`, `forgotten` (nothing if it has none) |
| `answer: {device, reason}` | a reason in category `wake` (any `wake.*`, known or not) ends the registration with cause `gateway`; any other reason changes nothing |
| `bind: device` | the device is bound; every held invite stops being held for it, and it no longer counts as woken for any; its message count is cleared |
| `unbind: device` | the device is no longer bound |
| `hold: {session, devices, expires_at}` (relay) | nothing if `expires_at` ≤ `at`. Otherwise the invite is held (the first `hold` of a session sets its `expires_at`), and for each listed device in DID order that is not bound: it is held for, and if it is not yet woken for this session, is live at `at` and wants `call`, it is woken: `wake {device, kind: "call", session, deliver_by: expires_at}` |
| `drop: session` (relay) | if held, it stops being held at `at` |
| `store: {identity, class}` (mailbox) | nothing for class `ephemeral`. Otherwise, for each registered device of `identity` in DID order that is not bound, is live at `at`, wants `message`, and has no message wake within the last 60 s (`at` − its last < 60) since its last `bind`: `wake {device, kind: "message", deliver_by: at + 60}` |
| `tick: true` | nothing beyond the expiries above |

When an invite stops being held at time `W`, each device still held for it and woken for it, in DID order, that is
live at `W` and wants `call-ended` gets `wake {device, kind: "call-ended", session, deliver_by: W + 60}`; the invite
is forgotten. An ending registration emits `ended {device, cause}`. Emissions are in the order above: invite expiries,
registration expiries, then the event's own. `registrations` is the list of devices with a registration after the
step, sorted by code point.

## Spec-gap list (Impl decisions these vectors encode)

Each item has a matching `spec-gap` issue draft in `impl/docs/spec-gaps.md`.

1. §12.4 vs §12.5: responder in ACTIVE receiving `cancel` — error vs crossed-cancel teardown.
2. §12.6: which party sends `reject session.glare` vs `cancel session.glare`.
3. §12.8 rule 4: "processes neither" — both updates discarded.
4. §12.9: T-Ring restart semantics on repeated `ringing`, and what bounds PROCEEDING after a non-ringing `progress`.
5. §12.7 rule 3 / §12.4: when the initiator knows an invite was forked.
6. §20.6: ULID/`issued_at` mismatch tolerance (300 s) and rejection (not just MAY).
7. §12.9: future-dated `issued_at` (symmetric replay window).
8. §7.4: how delegation credentials are conveyed to a verifier.
9. §14.2 / check 9: precise subset semantics for media selections.
10. §15.4: registered token on a message type it is not listed as valid on.
11. §12.10: consecutive re-queue limit exceeded → treated as T-Queue expiry.
12. §12.4/§12.7: `bye` reason for an answer arriving after a terminal `reject` (`session.failed`).
13. §12.4: ENDING collapsed into ENDED (local teardown is synchronous in the reference engine).
14. §19.4 vs §13.2: relay treatment of introductions to unknown recipients (queued silently; no `transport.unknown-recipient`).
15. §19.4: grant matching (by `grant` reference or by grantee identity), scope check, single-use contact tokens.
16. §12.12/§16.3: WebRTC binding shapes (SDP in `transports[].sdp`, candidates in `info.data`).
17. §13.2/§13.3: "unknown recipient" at a store-and-forward relay = not bound here within the retention window (spec-gap 131); queued envelopes expire silently.
18. §22.1: `publisher` MUST equal the verified identity; `stream_id` is namespaced under the publisher; newer ULID replaces.
19. §9.3: presence derives from device bindings at the authority; targets never seen get the uniform reject.
20. §22.2: integrity mode is advertised per variant (`integrity`), the closed `publish` schema has no record-level field.
21. §22.3: provenance statements reach subscribers in `notify.body.provenance`; carriage is otherwise unspecified.
22. §7.5: rotation has no wire record; vectors pin only what a verifier observes through the rotated DID document (`envelope/rotated-did-web-*`).
31. §12.9 vs §19.4: held introductions — no 300 s age bound, 604,800 s validity cap enforced, id tracked until `expires_at` (`envelope/introduction-*`).
74. §19.4: **decided** — `grant` and `reject` of an introduction are both addressed to the introducing identity (`state/first-contact-*`).
75. §12.5 rule 2 vs §12.7 rule 3: `cancel session.answered-elsewhere` reaching the leg that answered is `session.invalid-state`, not a crossed cancel (`state/race-responder-answered-elsewhere-at-answering-leg`).
78. G§4: which tokens are "attempt" tokens once ACTIVE — the profile's list omits `endpoint.unavailable` and `identity.not-in-service` (`gateway/inbound-active-*`).
81. M§6.5 / M§7.4 / M§14.1: the order of a hub's refusals when several apply, what the new hub may send during a handover wait, and whether a grant deposit is rate-limited (`messaging/hub-refusal-order-*`, `mailbox-hub-move-wait-covers-*`, `mailbox-grant-counts-*`).
80. M§5.2: the deposit class table says what each class "carries", not which other fields it may or may not carry; the rule is in this README (`messaging/deposit-*`).
79. G§4.2: the Q.850 cause of a category-fallback response, and of a BYE for a token the BYE rows do not name (`gateway/outbound-unknown-*`, `outbound-bye-policy-terminated`).
77. §22.2/§22.3: **decided** — a statement has no integrity mode of its own; the per-statement field is gone.
76. §12.7 rule 6: **decided** — when every leg expired and none rejected the relay sends its own `error transport.no-response`, which ends the attempt at the initiator (`state/relay-all-legs-expired`, `initiator-relay-no-response-ends-attempt`).
87. M§6.5 / spec-gap 66: **decided** — the hold behind an unacknowledged welcome is for an identity the commit brought in;
    a member adding its own device gets the commit at once, again after a restart, and its welcome's acknowledgement
    re-sends nothing (`messaging/hub-member-adding-its-own-device-is-not-held-behind-the-welcome`).
88. M§7.4 / spec-gap 71: **decided** — the handover wait's expiry is announced at the new hub's first deposit after it,
    even when that deposit is itself refused `policy.blocked`
    (`messaging/mailbox-hub-move-handover-wait-expiry-announced-on-a-refused-deposit`).
89. §12.7 rule 3 / §12.11: **decided** — per-leg cancels go in device (DID) order and a late binder's invites in id order
    (`state/relay-cancel-reaches-live-legs-in-device-order`, `state/relay-late-binder-gets-live-invites-in-id-order`).
94. M§6.6 / spec-gap 66: **decided** — a welcome is a redelivery only while one with those bytes is still held for that
    group (`messaging/mailbox-welcome-after-pending-group-expiry-is-stored-anew`,
    `mailbox-welcome-same-bytes-for-another-group-is-its-own`).
95. M§7.4 / spec-gap 71: **decided** — what the old hub still owes is judged by the highest `seq` stored
    (`messaging/mailbox-hub-move-nothing-missing-once-the-highest-stored-reaches-handover-seq`).
93. M§7.4 / spec-gap 71: **decided** — an old hub's item at or below the highest stored is a fill only after the wait
    expired with items missing; otherwise it is a redelivery
    (`messaging/mailbox-hub-move-old-hub-item-below-the-highest-stored-is-a-redelivery`).
92. M§6.6 / spec-gap 59: **decided** — a redelivery's cursor is the retained hub item's, by group and seq, across a
    registration the owner left and made again, and never an archive record's
    (`messaging/mailbox-hub-deposit-redelivered-after-re-registration-carries-the-retained-cursor`,
    `mailbox-hub-deposit-redelivery-cursor-is-never-an-archive-records`).
91. M§6.6 / M§12.2: **decided** — a pending group's expiry drops the hub deposits it admitted, not archive records
    that reference the group (`messaging/mailbox-pending-group-expiry-keeps-archive-records`).
90. §12.4 / §12.9: **decided** — a local `place_call` naming a session the endpoint already holds is `refused invalid-state`
    (`state/place-call-on-a-held-session-is-refused`).
85. §12.4 / §12.7 rule 4: **decided** — the `bye` a late answer gets after the session has *ended* follows what the invite
    was, not how the call finished: `session.cancelled` when we withdrew it (§12.5 rule 3), `session.already-answered`
    when an answer was applied (however the call then ended), `session.failed` when the attempt was never answered
    (`state/fork-late-answer-after-the-call-ended`, `fork-late-answer-after-our-hangup`).
144. §9.2 / §9.3 / P§6: **decided** (v0.17) — presence is private by default; a presented grant with `dsip.subscribe`
    admits a subscriber, after the subject's own devices and before a capability and the authority's policy; with no
    policy only those three admit (`state/presence-private-by-default`, `-grant-admits`, `-grant-not-admitting`,
    `-first-admitting-grant`, `-policy-admits-with-its-audience`, `payload/subscribe-with-grant-claim-valid`).
145. P§6: **decided** (v0.17) — a record's `audience` and a grant's `presence_audience`; records, `seq` and the publish
    interval per audience (`state/presence-audiences`, `-seq-and-interval-per-audience`, `-expiry-per-audience`,
    `-grace-drops-every-audience`, `payload/presence-audience-*`, `payload/grant-presence-audience-*`).
146. P§6: **decided** (v0.17) — a body per subscription; a device with no record the subscription sees counts in its
    assertion (`state/presence-assertion-per-subscription`).
147. P§7 / §19.4: **decided** (v0.17) — a share is a grant; its `valid_until` ends the subscriptions it admitted
    (`policy.terminated`, a lapse at the same instant wins); `grant-revocation` ends them early
    (`state/presence-share-ends-at-valid-until`, `-lapse-before-share-end`, `-revocation-*`, `-revoked-before-subscribe`,
    `payload/grant-revocation-*`, `envelope/grant-revocation-accepted`).
149. §9.3 / P§6: **decided** (v0.17, (a)) — a presence target is seen when it has bound here or the authority holds a
    policy or an issued capability for it, so a capability admits before its target ever binds; a publication target
    when it is published (`state/presence-capability-makes-target-seen`).
151. §19.4: **decided** (v0.17, (a)) — an invite is admitted by grantee only; its `grant` field never admits and never
    refuses, and a sender names only a live `dsip.invite` grant it holds from the callee
    (`state/first-contact-grant-reference-is-a-hint`, `state/first-contact-initiator-references-only-a-live-invite-grant`).
152. P§12.3 / §19.4: **decided** (v0.17, D1 (b)) — a grant carries the subject's sealed-presence keys as
    `presence_keys`, HPKE to the grantee identity (`presence/grant-keys-*`, `payload/grant-presence-keys-*`).
153. P§12.1: **decided** (v0.17, (ii)) — a sealed audience is an opaque tag derived from the identity's key agreement
    secret (`presence/audience-tag*`).
154. P§12.4: **decided** (v0.17, (i)) — a record the subscriber cannot read takes no part in combining
    (`presence/open-record-*`, `presence/view-*`).
155. P§12.2: **decided** (v0.17, (ii)) — the sealed state is padded to 128 bytes (`presence/seal-record`).
156. P§12.6 / P§12.2: **decided** (v0.17) — sealed records name `presence/0.2`, are given only to subscriptions that
    listed it, and carry a `kid` for their audience (`state/presence-sealed-*`, `semantic/presence-sealed-*`,
    `payload/presence-sealed-*`, `payload/presence-kid-*`, `envelope/presence-sealed-accepted`).
157. P§12.1: **decided** (v0.17, (a)) — keys and tags are derived from the identity's key agreement secret, the epoch
    in clear in `kid` (`presence/key-*`, `presence/open-record-spliced-*`).
158. §13.2 / §15: **decided** (v0.17, (a)) — a relay that replaces a device's connection sends `error`
    `transport.replaced` on the old one before closing it, and the client does not reconnect; the token is registered
    for `error` (`semantic/reason-transport-replaced-registered`, `-on-reject`). Reconnection is outside the vector
    kinds: dsip-rs's `demos/relay-rebind-demo.sh` and `web/test/relay-replaced.mjs` pin the client side on the wire.
159. P§12.5 / P§7: **decided** (v0.17, (a)) — re-granted grants form a rotation chain; ending or changing a share
    revokes the whole chain, newest first (`state/presence-keys-revocation-rotates`, `-sibling-epoch`,
    `-changed-share-rotates-what-is-lost`; `revoke` and `regrant` emit `{"revoke": […]}` in every trace).
160. P§8: **decided** (v0.17, (a)) — the publish interval is the authority's; a publisher leaves a margin. Editorial:
    the authority's rule (`state/presence-rate-limited`) is unchanged.
161. P§12.5: **decided** (v0.17, (a)) — an ending grant rotates the scopes it carried keys for, except those the grant
    changing the share carries too (`state/presence-keys-changed-share-rotates-what-is-lost`, `-only-for-sealed-scopes`,
    `-valid-until-rotates`).
162. P§12.3: **decided** (v0.17, (a)) — a grant whose `presence_keys` cannot be sealed or opened stands without
    keys; the subject's sealed records stay unreadable to its grantee. Core behaviour, outside the vector kinds
    (`dsip-endpoint` `tests/presence_keys.rs`).
163. §11.2 / §11.4: **decided** (1.0, (a)) — the schemas stay closed (the `*-extra-field*` vectors stand); a 1.x adds
    message types, registry entries, profiles and extensions, and a field on an existing core message only through
    an extension or profile its receiver is known to support. Text only; no vector changes.
141. §12.9: **decided** (v0.17) — `expires_at` is exclusive everywhere: expired when `now ≥ expires_at`, at receipt and
    wherever a held message, kept record, leg or activity is judged; `reachability-hint` and `presence` ids are not
    deduplicated (`envelope/*-at-expiry`, `envelope/presence-id-already-seen`, `dht/hint-*`, `state/invite-*-expiry*`,
    `messaging/*-at-expiry*`).
134. §9.3 / §9.4: **decided** (v0.17, Presence Profile P§3) — a device publishes its signed `presence` record to its
    authority, which keeps it to `expires_at` (age bounded by `expires_at`, cap 3,600 s, §12.9), refuses it in the P§3
    order and notifies on body changes; an unbound device's record outlives the unbind by T-Presence-Grace
    (`envelope/presence-*`, `state/presence-*`).
135. §9.4: **decided** (v0.17, P§4) — one record per device (`device` = signer, `seq` per `(subject, device)`), combined
    by the subscriber (`presence/aggregate-*`, `state/presence-seq-per-device`, `semantic/presence-signer-mismatch`).
136. §9.3 / §9.4: **decided** (v0.17, P§5) — `dsip-presence-state` is open; an unknown state is shown and ranked as
    `available` (`payload/presence-*`, `semantic/presence-unknown-state-fallback`, `presence/aggregate-unknown-*`).
133. C§4 / G§3 / G§7: **decided** (next spec version) — a gateway is not the recorded party's client: it accepts a recording
    the DSIP side declares (C§3) on the PSTN party's behalf, and the crossing is downgraded with a new G§7 loss,
    `recording-not-disclosed`, last in the table order (`gateway/downgrade-outbound-recording-not-disclosed`,
    `downgrade-inbound-recording-not-disclosed`, `downgrade-outbound-recording-after-the-other-losses`,
    `trust/downgrade-recording-not-disclosed`).
132. §12.7 rule 6 / §12.9: **decided** (v0.16) — a leg that has sent nothing once the invite has expired is expired, so the relay
    can say `transport.no-response` (`state/relay-silent-legs-expire-with-the-invite`,
    `relay-ringing-leg-outlives-the-invite`, `relay-silent-leg-expires-after-an-answer`).
131. §12.7 / §13.3: **decided** (v0.16) — a relay forgets an attempt once more than 1800 s (the T-Queue cap) pass with nothing for it,
    and a known identity or device once nothing is bound or held for it and its last binding ended more than
    `offline_retention_s` ago (`state/relay-attempt-forgotten-after-the-queue-cap`,
    `relay-known-identity-forgotten-after-retention`, `relay-known-identity-default-retention`).
86. §12.7 rule 3/4 vs §13.2: **decided** — a forking relay never withholds an `answer`, even from a leg it has cancelled,
    expired or seen reject; only the initiator ends an answered leg. Stale `progress` and second `reject`s are still
    screened (`state/relay-user-cancel-all-legs`, `relay-answer-from-an-expired-leg-is-forwarded`,
    `relay-answer-from-a-rejected-leg-is-forwarded`).
73. §9.3 vs §15.4: a terminal `notify` carries `session.expired` / `policy.terminated`, tokens the registry lists as valid on other types only; no warning on `notify` (`semantic/notify-terminated-reason`, by the deep-equality rule above).
110. N§3 / N§7: Number Attestation Profile draft choices pinned by `tn-binding/*`:
     - the 7-day lifetime cap;
     - certificates checked at the verification time, not at `iat`;
     - every TNAuthList on the path must cover the number;
     - the 300 s `iat` tolerance;
     - the step 8 policy switch;
     - E.164 only.
34–43. Messaging Profile draft choices (hub ordering, archive first-wins, first-contact authorization, `mailbox` tokens, `MAX_MLS_BYTES`, ephemeral lifetime) pinned by `messaging/*`; see the v0.8 messaging worklist in `impl/docs/spec-gaps.md`.

Emission ordering convention for state traces: timer stops → sends → media →
ui → timer starts. A session ending emits `media stop` (when media was running)
before `ui ended`. The places the suite departs from that order, so they are part of the contract:

- accepting an answer: `timer stop` → `media start` → `ui answered` → **then** `send cancel session.answered-elsewhere`;
- a `progress`: `timer stop T-Establish` → `ui progress` → **then** the T-Ring / T-Queue adjustment (`stop`, `start`);
  a `queued` beyond the re-queue limit is `ui progress` → `timer stop T-Queue` → `send cancel` → `ui ended`;
- a `cancel` at ALERTING: `timer stop` → `ui missed_call` → `ui ended`; T-Ring-Local expiry is `timer fire` →
  `send reject user.no-answer` → `ui ended user.no-answer`, with no `missed_call`;
- equal-id glare: our invite is withdrawn first (`send cancel session.glare` → `ui ended`), then theirs is rejected
  (`send reject session.glare`), then `ui glare_retry`; one session entry (ours) remains under the shared id;
- an inbound `update` carrying `answered_by` (screening escalation, §14.4): `ui update_offered` → `ui answered`.

Found by `impl/tools/fuzz.py` and part of the contract since: a reason is surfaced as its **effective** token (§15.1: an
unrecognized category is `ui ended session.failed`); an `answer` or `reject` carrying `in_reply_to` is an update reply and
never the attempt's outcome (before ACTIVE: `error session.invalid-state`); an `invite` for a session already held is
`error session.invalid-state`, or `drop ended-session` once it has ended; with several live attempts of ours to one
identity, the smallest id of all the invites wins and every losing attempt of ours is withdrawn, in id order (spec-gap 84).
A `recv` is a message that passed the envelope pipeline: its id is new and an `invite` is not yet expired.

A responder in ACTIVE that receives `cancel session.answered-elsewhere` answers `error session.invalid-state` even when
the initiator has not spoken since the answer: that reason is never a crossed withdrawal (spec-gap 75).
