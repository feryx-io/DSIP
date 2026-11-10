# CLAUDE.md — DSIP Repository

## What this project is

DSIP (Decentralized Session Initiation Protocol) is an identity-first signaling
and media negotiation protocol for trusted real-time sessions. This repo holds
the **specification** (versioned document snapshots), the **conformance suite**
(language-neutral vectors and the Python reference harness), and a **second
implementation** (`impl-ts/`, TypeScript) written from the spec and the vectors
alone, which passes the whole suite.

The **Rust reference implementation** grew here as `impl/crates` and moved, with
its history, to **dsip-rs** (github.com/feryx-io/dsip-rs, 2026-10-29): the
crates, the workspace, the demos and the browser client. dsip-rs takes DSIP as
its `spec/` submodule. DSIP's CI measures dsip-rs at the commit pinned in
`impl/dsip-rs.rev`, checked out into `dsip-rs/` by `impl/tools/dsip-rs.sh` and
built against this checkout's spec and vectors (`impl/tools/dsip_rs.py`). Code
changes to the Rust go to dsip-rs, never here.

The PoC's purpose, in priority order:
1. **Prove the spec is implementable.** Every MUST is implemented or generates a filed spec issue.
2. **Produce a conformance contract.** The language-neutral test vector suite is the artifact second implementations are measured against. The vectors outlive the Rust code.
3. **Demo the story.** Each phase ends in something demonstrable.

Full plan: `impl/docs/dsip_poc_dev_plan.md`. Read it before large changes.

## Repository map

```
v0.5/ … v0.17/, v1.0/  Spec snapshots. v1.0 (DSIP Core 1.0) is current, final at poc-v1.0; 1.x errata and drafts change in place within §11.4 (v0.17 final at poc-v0.17). NEVER edit v0.5 … v0.17.
v1.0/dsip-schemas…  Canonical JSON Schemas (draft 2020-12) + generate_schemas.py
v1.0/dsip-messaging-schemas-draft/  Messaging Profile schema set (own generator)
impl/               Conformance: vectors, tools, docs (spec versions tracked via git tags
                    poc-v0.6, …, poc-v1.0, never via folder placement); dsip-rs.rev pins dsip-rs
impl/vectors/       Language-neutral JSON test vectors (envelope/ payload/
                    semantic/ state/ transport/ dht/ broadcast/ media-binding/
                    gateway/ trust/ messaging/ device-events/ recording/ tn-binding/ wake/ …)
impl/tools/         Python: vector generator + reference harness (dsipvec/), parity.py
                    (Rust/Python), parity_ts.py (Python/TypeScript), fuzz.py (differential
                    fuzzing of all three), spec_lint.py (Spec: headers of dsip-rs's crates +
                    docs/coverage.md), dht_testnet.py, wan/ testbed (builds from dsip-rs),
                    dsip-rs.sh + dsip_rs.py (the pinned dsip-rs checkout and its environment)
impl/docs/          Plans, spec-gaps.md (every gap and its disposition), coverage.md
                    (generated), DHT / STIR findings
dsip-rs/            (not committed) dsip-rs at impl/dsip-rs.rev, from impl/tools/dsip-rs.sh
impl-ts/            Second implementation (TypeScript), measured against impl/vectors.
                    Written from the spec, schemas and vectors README ONLY — never by
                    reading dsip-rs or impl/tools/dsipvec verdict logic (impl-ts/README.md)
```

In dsip-rs, crate dependency order mirrors verification order: core → schema →
session. A message reaching `dsip-session` has already passed signature, replay,
and shape checks. Never invert this (dsip-rs's CLAUDE.md carries the rules for
its code).

## Non-negotiable engineering rules

1. **Vectors before code.** No stateful behavior (state machine transition,
   timer, race resolution) ships without a vector or trace exercising it.
   When implementing new behavior: write/generate the vector first in
   `impl/tools/`, confirm the Python harness verdict, implement it in `impl-ts`,
   then in dsip-rs (its `spec/` submodule at the DSIP commit with the vector),
   and move `impl/dsip-rs.rev` to that dsip-rs commit, until all three agree. Expected outcomes are
   authored by hand from the spec, never recorded from an implementation.

2. **Three-way parity is CI-enforced.** Every vector must produce the same
   result from the Python harness, the Rust runner (`parity.py`) and `impl-ts`
   (`parity_ts.py --require-all`: it may skip nothing). If they disagree, stop
   and find out why before proceeding — a divergence is a vector bug, an
   implementation bug or a spec gap, and it must be identified, never papered
   over. Rust and Python share an author and rarely disagree; `impl-ts` is the
   independent reading. Passing the suite is not agreement: for table-shaped
   rules and state machines, probe all three with temporary generated vectors
   and compare actual with actual — `impl/tools/fuzz.py` does it. What it finds becomes a hand-authored
   vector or a spec-gap, never a recorded expectation.

3. **Signature over bytes.** The base64url payload is carried as raw bytes
   through signature verification and only then decoded to JSON (spec §10.2).
   Never re-serialize on the verify path. Never "canonicalize."

4. **Authority order (spec §8.1) is untouchable.** DID document > alias
   resolution > cache > hints. The DHT is a hints tier ONLY — signed, expiring
   reachability records verified against the DID before use. No code path may
   treat a DHT record, cache entry, or relay claim as authoritative.

5. **Schemas are canonical in the spec folder.** Edit
   `v1.0/…/generate_schemas.py`, never the generated schema files.
   dsip-rs's `dsip-schema` embeds schemas from the spec folder at build time
   (here, this checkout's, via `DSIP_SPEC`); the freshness check fails the build
   on drift. Regenerate after edits.

6. **Wire format rules at parse (spec §10.3):** UTF-8 only, integer
   timestamps, reject floats. Enforced in dsip-rs's `dsip-core` parsing and in
   `impl-ts`, tested by vectors.

7. **Spec version drift lands in vectors first.** When a new spec version
   arrives, express the diff as vector changes, then change code until green.

## Documentation standard (enforced)

This applies to `impl-ts` here and to dsip-rs's crates, which DSIP's CI lints.

- Every module, public type, and public function implementing normative
  behavior carries a doc comment (rustdoc; TSDoc in `impl-ts`) with a `Spec:`
  line citing the current (1.0) section (e.g. `Spec: §12.6`, `Spec: M§6.5`). Grep-able,
  consistent format; `spec_lint.py --check` enforces the Rust module headers.
- Where code resolves a choice the spec leaves open, add an `Impl:` line
  explaining the decision. `Spec:` = citation, `Impl:` = decision. Never mix.
- Every `Impl:` note resolving a genuine ambiguity requires a matching
  `spec-gap` issue (section number, choices considered, choice made). The
  comment records the local decision; the issue drives the spec fix.
- Branch-level inline comments cite the spec where a line exists *because*
  the spec says so (timer bounds, reason tokens, race resolutions).
- `#![deny(missing_docs)]` on all library crates — undocumented public items
  fail the build.
- Modules with no normative content must carry `Spec: none (infrastructure)`.
- Crate `lib.rs` opens with a doc comment stating which spec sections the
  crate owns.

## Common commands

```bash
# Schemas: regenerate after editing the generator, then sanity-check
python3 v1.0/dsip-schemas-v1.0/dsip-schemas/generate_schemas.py v1.0/dsip-schemas-v1.0/dsip-schemas/schemas
python3 v1.0/dsip-schemas-v1.0/dsip-schemas/validate_samples.py
python3 v1.0/dsip-messaging-schemas-draft/generate_schemas.py v1.0/dsip-messaging-schemas-draft/schemas

# Vectors: regenerate + Python verdicts
python3 impl/tools/generate_vectors.py
python3 impl/tools/run_vectors.py            # Python side of parity

# Rust: dsip-rs at impl/dsip-rs.rev in dsip-rs/ (or $DSIP_RS), built against this checkout
impl/tools/dsip-rs.sh                         # [commit] to try another; dsip-rs's own CI runs its tests and demos
(cd dsip-rs && DSIP_SPEC=$PWD/.. DSIP_VECTORS=$PWD/../impl/vectors cargo build -p dsip-cli -p dsip-dht)
python3 impl/tools/parity.py                  # Rust/Python, actual against actual (sets DSIP_SPEC/DSIP_VECTORS itself)
python3 impl/tools/spec_lint.py --check       # Spec: headers; regenerates docs/coverage.md without --check

# Second implementation (TypeScript): build, vectors, Python/TypeScript parity
(cd impl-ts && npm ci && npm run build && npm run vectors)
python3 impl/tools/parity_ts.py --require-all

# Differential fuzz: random traces through all three implementations, actual against actual
python3 impl/tools/fuzz.py                      # seed 1 (CI's regression seed); CI also runs its run number as a seed, 800/target
python3 impl/tools/fuzz.py --seed random --target endpoint,hub --count 1000 --out /tmp/found

# DHT local testnet (integration, not vectors)
python3 impl/tools/dht_testnet.py --nodes 5
```

pip installs in this environment need `--break-system-packages`.
`dsip-rs/target/debug` grows without bound (impl/target filled the disk before): `cargo clean --profile dev` there when short of space.

## Key spec sections (1.0; numbering unchanged from v0.6) you will cite constantly

| Section | Topic |
|---|---|
| §7.3–7.5 | Identity vs device keys, delegation, rotation |
| §8.1–8.5 | Discovery authority order, conflict rules, DHT status |
| §9.3 | Presence subscription protocol (subscribe/notify) |
| §10.2–10.3 | Envelope signature semantics, payload rules |
| §12.4–12.10 | State machine, cancel/answer race, glare, forking, renegotiation, timers |
| §13.2 | ws/1.0 binding, hello, anti-splicing, 65,536-byte cap |
| §14.3–14.4 | answered_by, screening pattern |
| §15 | Reason codes: `category.condition`, category fallback |
| §19.4 | First contact: introduction/grant |
| §22 | Verified Broadcast profile |
| B§2–B§8 | WebRTC Media Binding 1.0 (`v1.0/dsip-webrtc-media-binding-v1.0.md`) — cite as `B§n` |
| G§n | Gateway Profile 1.0 (`v1.0/dsip-gateway-profile-v1.0.md`) — cite as `G§n` |
| M§n | Messaging Profile 1.0 (`v1.0/dsip-messaging-profile-v1.0.md`) — cite as `M§n` |
| R§n | RTP/SRTP Media Binding, draft (`v1.0/dsip-rtp-srtp-media-binding-v1.0-draft.md`) — cite as `R§n` |
| T§n | Alias Transparency Profile, draft (`v1.0/dsip-alias-transparency-profile-v1.0-draft.md`) — cite as `T§n` |
| E§n | Device Events Profile 1.0 (`v1.0/dsip-device-events-profile-v1.0.md`) — cite as `E§n` |
| C§n | Recording Profile, draft (`v1.0/dsip-recording-profile-v1.0-draft.md`) — cite as `C§n` |
| N§n | Number Attestation Profile, draft (`v1.0/dsip-number-attestation-profile-v1.0-draft.md`) — cite as `N§n` |
| P§n | Presence Profile, draft (`v1.0/dsip-presence-profile-v1.0-draft.md`) — cite as `P§n` |
| W§n | Wake Profile, draft (`v1.0/dsip-wake-profile-v1.0-draft.md`) — cite as `W§n` |
| — | DHT Reachability Hints Profile, draft (`v1.0/dsip-dht-hints-profile-v1.0-draft.md`) — no prefix of its own; cite core §8.3 / §8.5 |

## Semantic checks (post-schema, must-implement)

The 12 checks in the schema README are the authoritative list. Highlights that
recur in reviews: 300 s replay window + `expires_at` > `issued_at`; ULID
timestamp consistent with `issued_at` (glare-backdating guard); one
outstanding `update` per session across both directions; relay `hello`
`in_reply_to` anti-splicing; answer/reject selections ⊆ referenced offer;
registry *shape* in schema vs *membership* in registries with category
fallback for unknown tokens; `key-rotation` and `delegation-revocation`
subject/signer rules (§7.4, §7.5). The pipeline order that decides which
failure is reported is normative in `impl/vectors/README.md`.

## Things Claude should NOT do

- Do not edit generated schema files, anything in `v0.5/` … `v0.17/`,
  or renumber spec sections without an explicit request.
- Do not resolve a spec ambiguity silently — implement a choice only alongside
  an `Impl:` comment and a `spec-gap` issue.
- Do not weaken a vector to make an implementation pass. If a vector looks
  wrong, flag it; the vector suite is the contract.
- Do not introduce closed enums for registry-governed values (`answered_by`,
  `progress.status`, reason tokens) — registries grow; use shape validation
  plus membership checks with fallback.
- Do not add DHT authority, DHT-stored presence, or Sybil "solutions" —
  instrumented, not solved (§3.2, plan §10.5).
- Do not treat prose example ids like `01HZINVITEABC` as valid ULIDs; they
  fail validation by design.
- Do not change Rust code here: it lives in dsip-rs. DSIP moves `impl/dsip-rs.rev`.
- Do not write `impl-ts` by reading dsip-rs or the verdict logic in
  `impl/tools/dsipvec`; when the spec and the vectors README are not enough,
  that is a finding to fix there. Observing the other implementations through
  probe vectors is fine; reading them is not.
- Do not leave probe vectors (`zzprobe-*`) in `impl/vectors`: they are
  temporary; a disagreement they find becomes a hand-authored vector.
- Do not extend the gateway past Gateway Profile 1.0 without an explicit
  request: production outbound STIR signing, video across the gateway, SIP 3xx
  as DSIP forking (spec-gap 29) and REFER/transfer are out of scope.

## Workflow expectations

- Section-renumbering or cross-reference edits in any document: map every
  internal reference first, then apply exact unique-string replacements
  (assert uniqueness), descending order — never blind pattern replacement.
  Internal doc §refs and spec §refs overlap numerically; verify which is which.
- Multi-stage document edits: verify intermediate state before the next stage;
  never overwrite a partially-applied edit set.
- When a task produces a spec finding (ambiguity, inconsistency, missing
  registry entry), end the task by drafting the `spec-gap` issue text.
- Conformance tagging: when the implementation fully passes the suite for a
  spec version, tag `poc-vX.Y` before any next-version changes land.
