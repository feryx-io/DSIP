# DSIP Presence Profile (`presence/0.1`, `presence/0.2`)

**Status:** DRAFT, companion profile to DSIP 1.0. Cite as `P§n`. It collects spec-gaps 134–137, decided 2026-10-19,
and the choices made 2026-10-22 on the outline (`impl/docs/presence-profile-outline.md`): a device sends its signed
`presence` record itself (no new message), under `dsip.signaling`, with the timers of P§8 and the reason category
`presence` (P§9). Spec-gaps 142–148, decided 2026-10-22/23, add the record's profile token, how a subscriber reaches
the authority, who may watch, audiences and shares (P§6, P§7). Spec-gaps 152–157, decided 2026-10-23/24, add records sealed to subscribers, `presence/0.2` (P§12).
P§3–P§8 and P§12 are pinned by vectors.

The core stays as it is: presence is optional (§9.1), private by default (§9.2), carried by `subscribe`/`notify`
(§9.3), and never published to the DHT (§8.5). This profile fills in what §9 leaves open: how a device's signed record
reaches its authority, how several devices make one identity's presence, which states exist, and what each subscriber
is shown.

## P§1 Scope

This profile defines:

- how a device **publishes** its signed presence record to its authority (P§3);
- **per-device records** and the rule that combines them into an identity's presence (P§4);
- the **`dsip-presence-state`** registry and its fallback (P§5);
- **who may watch** and **audiences**: which subscribers are admitted, and which records each sees (P§6);
- **time-boxed shares** of presence, and ending one early (P§7);
- the profile's **timers** (P§8) and **reason tokens** (P§9);
- **sealed records** (`presence/0.2`): a record's state encrypted to the subscribers its audience admits (P§12).

Out of scope: presence bridged to SIP SIMPLE, XMPP or carrier presence; calendar or meeting integration; enterprise policy distribution (a deployment pattern, P§11); detail levels beyond the
state (`activity`, `note`; P§6); presence carried in messaging groups (P§11, spec-gap 148).

## P§2 Principles

1. **Reachability never depends on presence** (spec-gap 137). No relay, mailbox or other service may require presence
   publication as a condition of delivery or reachability. Delivery decisions use bindings (§13.2), never presence
   records. A callee's own client declining a call is not covered by this rule.
2. **No presence oracle.** A response to a party not authorized for the target's presence MUST NOT vary with the
   target's presence state. This extends §9.3's anti-enumeration rule beyond `subscribe`.
3. **The authority carries presence and never authors it** when a subject-signed record exists (P§3). What it asserts
   by itself (§9.3) is labelled as such, and is used only for a device that holds no valid record.
4. **Signed by the device that knows.** Each record is signed by the device it describes. Nothing signs for another
   device, and the identity key stays offline (§7.3).

## P§3 Publishing (spec-gap 134)

A device publishes by sending its §9.4 `presence` record, signed by itself, to its **authority**: the relay it binds to
(§13.2), which answers `subscribe` for its identity (§9.3). `to` is the authority's DID. Publishing needs no capability
beyond `dsip.signaling`, which every envelope's delegation already carries (§7.4): a device that may bind can already
make the authority assert it `available`, so a record reveals nothing a binding does not. The record names this
profile, `presence/0.1`, in `dsip.profiles` (spec-gap 142); an authority or subscriber that implements it lists it as
supported, and one that does not refuses the record (§11.2).

```json
{
  "dsip": {"core": "1.0", "min_core": "1.0", "profiles": ["presence/0.1"], "extensions": [], "critical": []},
  "type": "presence",
  "id": "01K742SG0000000000PRES0001",
  "from": "did:key:z6MkAlicePhone",
  "to": "did:key:z6MkAliceRelay",
  "subject": "did:web:alice.example",
  "device": "did:key:z6MkAlicePhone",
  "state": "busy",
  "seq": 58,
  "issued_at": 1760000000,
  "expires_at": 1760000300
}
```

**Validity at any receiver** (§12.9). A record is kept and forwarded for its whole lifetime, so like a reachability
hint (spec-gap 96) its age is bounded by `expires_at`, not by the 300 s replay window: a `presence` envelope whose
`expires_at − issued_at` exceeds 3,600 s is invalid (`presence-validity`), an `issued_at` more than 300 s in the future
is invalid (`replay-window`), and one past its `expires_at` is expired. The record's `seq` (below), not its id, decides
whether a re-observed record replaces another.

**Payload rule.** When `device` is present it MUST equal `from`, the signing device (`presence-signer-mismatch`,
reason `presence.signer-mismatch`). A record without `device` is a v0.16-form record (P§4).

**At the authority.** A record comes over the device's binding: traffic from a device that has not bound never reaches
these checks (`transport.hello-required`, §13.2), so the identity in rule 1 is always known. A record that passed the
envelope pipeline is refused with `error` (`to` the publishing device,
`in_reply_to` the record's id), checked in this order, the first that applies:

1. `presence.signer-mismatch`: the record names no `device`, or its `subject` is not the identity the signing device
   is delegated by (§7.4), as the authority learned it when the device bound (§13.2).
2. `presence.lifetime`: `expires_at − issued_at` is below 60 s or above 3,600 s (P§8).
3. `presence.stale`: the authority holds a record for the same `(subject, device, audience)` (P§6) whose `seq` is equal
   or greater.
4. `policy.rate-limited`: the authority accepted a record from this device for the same audience less than 5 s earlier
   (P§8), whether or not that record is still held; the `error` carries `retry_after`, the whole seconds left.

Otherwise the record is accepted. The authority does not acknowledge it (as for `publish`, §22.1): it keeps it as the
device's current record for its audience, replacing any earlier one, and every active presence subscription to the
subject whose body it changes (P§6) gets a `notify` (§9.3) carrying the new body.

**The body.** A presence `notify` body is `{"event": "presence", "state": S}`, as in §9.3, where `S` is the authority's
assertion about the subject's devices that hold **no** record: `available` when any of them is bound to it, else
`offline`. When the authority holds any record for the subject, the body also has `records`: each record it holds,
ordered by `device`. A record in a body is the signed envelope (§9.3 RECOMMENDS the signed form, and P§2.3 requires
it); a subscriber verifies each independently of the authority. A body without `records` is the v0.16 body.

**Expiry.** A record past its `expires_at` is dropped, and the authority forgets its `seq`. With no record left for a
device, that device counts in the assertion again. When the clock passes several records' expiry at once, each
subscription gets one `notify` for its subject, subjects in order.

**Unbinding.** A device that unbinds keeps its record until T-Presence-Grace (P§8) has passed since the unbind, so a
phone changing networks does not flicker `offline`. The grace runs from the first unbind: a further unbind while it
runs changes nothing, and a record accepted from the device meanwhile keeps the grace running. A device that binds
again within the grace keeps its record as if it had never left. When the grace runs out, the record is dropped as at
expiry. A grace of 0 drops it at the unbind.

**Notifying.** A subscription gets a `notify` when an event changes its body: an accepted record, a record dropped, or
a binding change of a device that holds no record. A binding change that leaves the body as it was sends nothing.

## P§4 Several devices, one identity (spec-gap 135)

- The §9.4 record carries `device`, the DID of the device it describes, which MUST equal the signer (P§3). `seq` is
  ordered per `(subject, device)`: one device's counter never makes another's record stale.
- A presence `notify` body carries the current record of every device the subscriber may see. The subscriber's client
  computes the identity's presence from them; the authority does not.
- **Combining rule**, deterministic so every subscriber agrees. The candidates are the state of every record that is
  still valid (`expires_at` after now), plus `available` when the body's assertion is `available`. With no candidate,
  the identity is `offline`. Otherwise it takes the highest-ranked candidate: `dnd` > `busy` > `available` > `away` >
  `offline`, an unknown state ranking as `available` (P§5). Among candidates of equal rank, a record comes before the
  assertion (the device's own signed word before the authority's claim); then a registered state before an unknown
  one; then unknown ones in code-point order.
- The result names the effective state (a registered value), the token that won (shown raw when unknown, P§5), and
  whether it came from a record, from the assertion, or from nothing. A client MUST render a state that came from the
  assertion as the authority's claim (§9.3).
- A v0.16-form record, without `device`, counts as one unnamed device's record.

## P§5 States (spec-gap 136)

- Registry `dsip-presence-state`, shape `[a-z][a-z0-9-]*`, at most 64 characters; initial values `available`, `busy`,
  `away`, `dnd`, `offline`. It is open: implementations MUST NOT reject an unknown token.
- Fallback: an unknown state is shown as `available` (and ranked as `available` in P§4), with the token displayed raw.
  A newer state must never make a reachable person look unreachable.
- "Invisible" is client behaviour, not a state: an invisible device publishes `offline`, or nothing. P§2.2 is what
  keeps it from leaking.

## P§6 Who may watch, and audiences (spec-gaps 144–146)

**Admission** (spec-gap 144). Presence is private by default (§9.2). An authority admits a presence `subscribe` by
the first of these that applies, at every `subscribe`, a renewal included:

1. **The subject's own devices:** the subscriber's identity is the target. Such a subscription sees every record.
2. **A grant:** an entry of the `subscribe`'s `claims` is `{"type": "dsip-grant", "grant": E}`, where `E` is a signed
   `grant` envelope (§19.4) whose signature and delegation verify (§10.2, §7.4); its `issued_at` and `expires_at`
   bound its delivery, not its life, so the replay window and delivery expiry are not applied. It admits when the
   identity its signer acts for is the target, its `to` is the subscriber's identity, its `scope` includes
   `dsip.subscribe`, its `valid_until` is after now (§12.9), and the target has not revoked it (P§7). The first
   admitting entry, in `claims` order, is used.
3. **A capability** the authority issued for the target (§9.3). Issuing it makes the target seen (§9.3, spec-gap 149),
   so it admits before the target has ever bound.
4. **The authority's own policy** for the target (for example `public` for a public figure, or an organisation's
   directory).

Otherwise the answer is `reject` with `policy.blocked`, as for a target that does not exist (§9.3). An authority with
no policy for a target admits by 1–3 only.

**Audiences** (spec-gap 145). A record MAY carry `audience`, and a grant MAY carry `presence_audience`: a token
`[a-z][a-z0-9-]*` of at most 64 characters that the subject chooses (`family`, `work`, …). A subscription's audience
is fixed when it is admitted: under rule 1, every audience; under rule 2, the grant's `presence_audience`, or none when
the grant has none; under rules 3 and 4, none, unless the authority's policy names one. A subscription sees the records
with no `audience`, and those whose `audience` equals its own.

A device publishes one record per audience it shares with, each signed by itself. The authority never edits a record,
so a reduced view is a separately signed record, never a redacted one. Records are kept per `(subject, device,
audience)`, a record without `audience` counting as an audience of its own. P§3's `presence.stale` compares `seq`
within that key, and the publish interval runs per device and audience. Each record expires by itself; the unbind
grace is per device and applies to all of the device's records.

**The body per subscription** (spec-gap 146). A subscription's `notify` body is P§3's body computed over what that
subscription sees. `records` lists the records it sees, ordered by device, then by audience, a record without one
first. The assertion is `available` when any bound device of the subject holds no record the subscription sees, else
`offline`. A device that publishes only to other audiences therefore counts in the assertion, exactly as a device that
publishes nothing. Bodies differ between subscriptions, and a subscription is notified exactly when an event changes
its own body.

**Detail.** This version defines no detail beyond the state: `activity` and `note` are not fields of a record. A
coarser view for an audience is a record with a coarser state (for example `available` for `work` while `family` sees
`busy`).

The authority sees every plain record's state, and the audiences' labels. A subject that does not want it to seals its
records (P§12): the authority then routes by an opaque tag and never sees a state.

## P§7 Time-boxed shares (spec-gap 147)

- **A share is a grant** with `dsip.subscribe`, optionally a `presence_audience`, and a `valid_until` at the end of the
  share. It is issued as any grant is (§19.4): in answer to an introduction, which a contact token handed over out of
  band (a link, a QR code) may admit.
- **Expiry.** A subscription admitted by a grant ends when the authority's clock reaches the grant's `valid_until`: a
  `terminated` notify with reason `policy.terminated`. A subscription that lapses at the same instant ends with
  `session.expired` instead (§9.3).
- **Ending a share early.** A device of the subject sends its authority a `grant-revocation` (§19.4) for the grant,
  and for every grant of its rotation chain (P§12.5, spec-gap 159).
  The authority keeps it until the grant's `valid_until`. Every subscription that grant admitted, the grant issued by
  the revocation signer's identity, ends at once with a `terminated` notify, reason `policy.terminated`, in
  subscription order. A later `subscribe` presenting the grant is not admitted by it (rule 2); another rule may still
  admit. A revocation is not answered.
- Revocation stops future notifies only. What was already shown cannot be recalled.
- **Changing a share** (spec-gap 150). A share's audience or length changes by a grant that follows it (§19.4): the
  grantor revokes the old grant, with its rotation chain, at its authority as above, which ends what it admitted, and the grantee subscribes again
  presenting the new one. A following grant without `dsip.subscribe` ends the share and keeps the calls.

## P§8 Timers

| Timer | Default | Bounds | Meaning |
|---|---|---|---|
| Record lifetime | 300 s | 60–3,600 s | A record's `expires_at` minus `issued_at`. Devices publish again before expiry. |
| T-Presence-Grace | 60 s | 0–300 s | After a device unbinds, how long the authority keeps its record. |
| Publish interval | — | ≥ 5 s per device | Between two accepted records of one device; sooner is refused `policy.rate-limited`. Keeps presence from being a traffic channel. |
| T-Presence-Rotate | 60 s | 0–3,600 s | The least time between two rotations of one key scope by one device (P§12.5). Grants ending meanwhile are rotated together when it has passed. |

The grace is the authority's choice within its bounds; the lifetime bounds and the publish interval are checked as P§3
says. T-Presence-Rotate is the subject's devices' choice.

The publish interval is the authority's: it is measured on the authority's clock, in whole seconds, between two records
it accepted. A device measures only from when it sent, so one that waits exactly 5 s, or exactly a refusal's
`retry_after`, can be refused when the earlier record took longer in transit. A device leaves a margin for transit and
whole-second clocks (spec-gap 160).

## P§9 Reason tokens

The profile registers the category `presence` in the core reason registry (§15). Its default fallback for an unknown
condition: the record is refused; the device does not send the same record again, and publishes a corrected one.

| Token | Meaning | Carried on |
|---|---|---|
| `presence.signer-mismatch` | The record's `device` is missing or is not the signer, or its `subject` is not the signer's identity | `error` |
| `presence.lifetime` | The record's lifetime is outside P§8's bounds | `error` |
| `presence.stale` | The authority holds a record of the same device with an equal or greater `seq` | `error` |
| `presence.sealed-invalid` | A sealed record does not name `presence/0.2`, or its `kid` is not for its audience (P§12.2) | `error` |

`policy.rate-limited` (§15) covers the publish interval.

## P§10 Security and privacy considerations

- Calls, deposits and subscription answers must not leak presence by their reason or timing (P§2.2).
- The authority is trusted with presence plaintext, and not trusted to forge it: a subscriber checks each record's
  signature and delegation (§7.4).
- A record names a device. Showing the per-device breakdown to subscribers reveals how many devices someone has and
  which one is active. Clients SHOULD show the combined state only.
- Presence history is metadata. Authorities SHOULD keep no record past its expiry; P§3 has them forget it.
- A sealed record (P§12) hides its state and its audience's name from the authority, not that the device is bound, when
  it publishes, how many audiences it publishes for, or how many times each audience's key has rotated (the epoch is in
  `kid`). P§12.2's padding and a steady refresh keep a state change from showing in a record's size or timing.

## P§11 Open questions

1. **Encryption to subscribers** (spec-gaps 152–157, decided): P§12, keys carried in grants. An MLS group per
   audience, as Messaging Profile activity is sealed (M§11), was considered and not taken: it would make presence
   depend on the messaging infrastructure, and every share a membership change
   (`impl/docs/presence-encryption-design.md`).
2. **Enterprise policy.** A deployment pattern, not protocol: an organisation runs the `did:web` authority for its
   identities and applies policy there (§9.3 already makes authorization the authority's decision).
3. **Messaging** (spec-gap 148, decided for 0.1): presence has one path, through the authority. A client MAY show
   messaging activity (M§11) beside presence; the two are not combined. Encrypted presence (question 1) is the
   occasion to revisit this.

## P§12 Sealed records (`presence/0.2`; spec-gaps 152–157)

A subject MAY seal its records, so that the authority carries a state it cannot read. The authority's checks (P§3) and
routing (P§6) read only fields that stay in clear, so they do not change. Sealing is chosen per audience (P§12.6).

### P§12.1 Keys

Every device acting for the subject holds the identity's X25519 key agreement secret (§7.3, §10.4: the 32-byte private
key of its `keyAgreement` method, else of its current key agreement delegation (spec-gap 179), else for `did:key` the
secret derived from the identity's Ed25519 key, M§6.9). A new key agreement key changes `s`, and so every key below: it
is a rotation (P§12.5). `s` is that
secret with RFC 7748's clamping applied (`decodeScalar25519`), so every encoding of the key gives the same `s`. A
grantee never holds it. Every key and tag below is derived from `s`, so no key is ever sent between the subject's devices.
HKDF is HKDF-SHA256 (RFC 5869) with an empty salt; strings are UTF-8; `‖` is concatenation.

- **Audience tags.** An audience the subject names `L` (a label kept on its own devices, never sent) is written on the
  wire as `k-` followed by the unpadded lower-case base32 (RFC 4648 §6) of the first 10 bytes of
  `HKDF(s, "dsip presence audience v1" ‖ 0x00 ‖ subject ‖ 0x00 ‖ L)`: 18 characters, a P§6 token. Records and grants
  for a sealed audience carry the tag as `audience` and `presence_audience`.
- **Key ids.** A key belongs to a *scope*, `main` for records with no `audience` or the audience's tag, and an
  *epoch*, an integer from 0. Its id is `kid` = scope ‖ `.` ‖ the epoch in decimal without leading zeros (`main.0`,
  `k-mfrggzdfmztwq2lk.3`).
- **Keys.** `key(kid) = HKDF(s, "dsip presence key v1" ‖ 0x00 ‖ subject ‖ 0x00 ‖ kid)`, 32 bytes.

### P§12.2 The sealed record

A sealed record carries `kid` and `sealed_state` in place of `state`, and names `presence/0.2` in `dsip.profiles`:

```json
{
  "dsip": {"core": "1.0", "min_core": "1.0", "profiles": ["presence/0.2"], "extensions": [], "critical": []},
  "type": "presence", "id": "01K742SG0000000000PRES0002",
  "from": "did:key:z6MkAlicePhone", "to": "did:key:z6MkAliceRelay",
  "subject": "did:web:alice.example", "device": "did:key:z6MkAlicePhone",
  "audience": "k-mfrggzdfmztwq2lk", "kid": "k-mfrggzdfmztwq2lk.3",
  "seq": 59, "issued_at": 1760000000, "expires_at": 1760000300,
  "sealed_state": "<base64url, 208 characters>"
}
```

- The plaintext is the UTF-8 JSON object `{"state": S}`, its only key, obeying §10.3, followed by ASCII spaces (0x20)
  to exactly 128 bytes. Every record is the same size, whatever its state. A sealer writes the object without
  whitespace (`{"state":"busy"}`); a subscriber reads any JSON text of that one key.
- `sealed_state` is the unpadded base64url of `nonce ‖ ciphertext ‖ tag`: a random 12-byte nonce and AES-256-GCM
  under `key(kid)`, as M§11.1, so 156 bytes. The AAD is `"dsip presence v1" ‖ 0x00 ‖ subject ‖ 0x00 ‖ device ‖ 0x00 ‖
  audience ‖ 0x00 ‖ kid ‖ 0x00 ‖ u64be(seq) ‖ u64be(expires_at)`, with `audience` empty when absent: a ciphertext
  cannot be moved to another record, device, audience or key.
- The field is not `sealed`: a record is addressed to its authority, and `sealed` on a payload is the sealed-body
  extension's (§10.4).
- `state` and `sealed_state` MUST NOT both be present, and `kid` is present exactly when `sealed_state` is (schema).
  A sealed record MUST name `presence/0.2`, its `audience` is never `main`, and its `kid`'s scope MUST be `main` when
  it has no `audience` and its `audience` otherwise; any receiver refuses one that breaks either (`presence-sealed-invalid`, reason
  `presence.sealed-invalid` on the authority's `error`).
- The envelope signature covers `sealed_state` and `kid`; a subscriber verifies the record (P§2.4) before opening it.

### P§12.3 Keys in a grant

A grant (§19.4) that admits a presence subscriber to a sealed record MAY carry `presence_keys`: `{alg, enc, ct}`, HPKE
as for a sealed purpose (§19.4, M§14.1), `alg` `hpke-base-x25519-sha256-aes128gcm`, to the key agreement key of the
grant's `to` (the grantee identity, so every device of the grantee opens it), info `dsip presence keys v1`, AAD
`id ‖ 0x00 ‖ from ‖ 0x00 ‖ to` of the grant. The plaintext is the JSON object `{"keys": [{"kid": K, "key": B}, …]}`,
`B` the unpadded base64url of the 32-byte key, followed by spaces to a positive multiple of 256 bytes. It holds the
`main` key and, when the grant has a `presence_audience`, that audience's key, each at the grantor's current epoch
(P§12.5), and no other scope.

A grantor that cannot seal the keys (it cannot resolve the grantee's key agreement key) sends the grant without them,
and a grantee that cannot open them holds the grant as if it carried none (spec-gap 162): the grant still admits, and
the records it would open stay unreadable (P§12.4) until a following grant carries keys the grantee opens.

### P§12.4 Subscribers

A subscriber that supports `presence/0.2` lists it in its `subscribe`'s `dsip.profiles`. It opens a body's sealed
records with the keys its grants carried, and keeps for each scope the keys of the two highest epochs it has received
(a record under the previous key stays valid until its own `expires_at`). A record is **unreadable** when any of these
fails, in order: the subscriber holds no key for its `kid` (`presence-key-unknown`); `sealed_state` is not 156 bytes
(`sealed-too-short`); it does not open (`aead-open-failed`); the plaintext is not 128 bytes holding exactly
`{"state": S}` with `S` a P§5 token (`presence-plaintext-invalid`). An unreadable record takes no part in combining
(P§4): it is neither shown as `offline` nor guessed. The authority's assertion still counts only devices that hold no
record the subscription sees (P§6), so a device whose only record is unreadable shows the assertion's word, if any.
A client MAY say that it holds presence it cannot read.

### P§12.5 Epochs and rotation

- Each device of the subject keeps a current epoch per scope, from 0: the highest it has seen in its own identity's
  records (it watches its own identity, P§6 rule 1, and sees every record) or reached by rotating. It seals at it.
- **Rotation.** When a grant the device issued that carried keys ends (it revoked it, P§7, its `valid_until`
  passed, or a grant changing the share followed it), the device rotates each scope whose key the grant carried, `main`
  and the grant's audience, if any, except a scope the grant that changed the share carries too (spec-gap 161): the
  scope's epoch rises by one. It rotates a scope at most once per T-Presence-Rotate (P§8): the first time at once,
  then a scope whose grant ends sooner is rotated when that time has passed, with every scope due then.
- **Re-granting.** When a scope's epoch rises, by its own rotation or a sibling's record, the device issues, for each
  live grant it issued that carries that scope's key, a grant that follows it (§19.4, spec-gap 150) with the same
  `scope`, `valid_until` and `presence_audience` and the new keys. A rotation changes nothing the grantee may do, so the
  followed grant is not revoked at the authority. A grant issued by an offline sibling is re-granted when that sibling
  returns; until then its grantee cannot read the new epoch.
- **Rotation chains** (spec-gap 159). The grants that followed one another by re-granting form a chain, which all share
  one `valid_until`; the device that issued them keeps it. Each still admits at the authority, so when the share ends
  early or changes (P§7), the device revokes every grant of the chain, not only the newest. A chain whose `valid_until`
  has passed needs no revocation.

### P§12.6 Profiles and migration

- The authority stores and routes sealed records as any other: P§3's checks and P§6's routing read only `subject`,
  `device`, `audience`, `seq`, `issued_at` and `expires_at`.
- A subscription whose `subscribe` does not list `presence/0.2` in `dsip.profiles` is not given sealed records, and
  in its assertion their devices count as holding no record it sees.
- A subject chooses per audience: one audience sealed and another plain is allowed, the same audience both ways is not,
  and no record is ever published in both forms.
