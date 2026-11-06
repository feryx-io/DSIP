**Status:** DRAFT, companion document to DSIP 1.0 (the `reachability-hint` schema is in the v0.8 schema set; the DHT is a hints tier only, §8.1). v0.8 adds `endpoints[].service` (spec-gap 37).

# Draft: DSIP Reachability Hints Profile (`dht-hints/0.1`)

**Status:** draft carried from the v0.7 spec feedback loop (plan §10.4 deliverable 4). Candidate text
for an *optional* profile under §8.5. Nothing here changes §8.1: a hint is never authoritative.

## 1. Purpose

An endpoint whose DID has no DID document (`did:key`) — or whose document does not advertise a
reachable signaling endpoint — can publish a **reachability hint**: a signed, expiring statement
of where it can currently be reached. Other endpoints use the hint only to choose which
signaling endpoint to dial; identity, delegation, and session security come entirely from the
signed envelopes of the session itself (§10.2, §12).

## 2. Record format

A hint is a DSIP-JOSE envelope (§10.2) whose payload is:

```json
{
  "dsip": {"core": "1.0", "min_core": "1.0", "profiles": [], "extensions": [], "critical": []},
  "type": "reachability-hint",
  "id": "<ULID>",
  "from": "<subject DID>",
  "subject": "<subject DID>",
  "endpoints": [{"uri": "wss://relay.example/dsip", "bindings": ["ws/1.0"]}],
  "seq": 1787262059,
  "issued_at": 1787262059,
  "expires_at": 1787265659
}
```

- `from` MUST equal `subject`. The signing key (`kid`) MUST be a key of the subject or a device
  delegated by the subject (§7.4); the delegation MAY be presented in the protected header
  `delegations` array so that nodes can verify without any external lookup.
- `endpoints[].uri` MUST be `wss://` (§13.2). `bindings` lists signaling bindings.
- `endpoints[].service` (optional, v0.8) names the DID service type the endpoint stands in for:
  `DSIPSignaling` when absent, `DSIPMailbox` for a Messaging Profile mailbox (which then carries that
  service entry's fields, M§4.2). Hints serve only identities with no document entry of that type,
  and never override one (§8.1).
- `key_agreement` (optional, 1.x, spec-gap 179): the subject's current key agreement delegation (core §7.3), an
  envelope object (`{protected, payload, signature}`, §10.2) as the `delegations` header carries delegations. Publishers whose identity has one SHOULD carry it, so that senders find the key they seal to where they
  find the subject's devices.
- `seq` MUST be strictly increasing per subject across publications. Using `issued_at` as `seq`
  satisfies this for a single publisher clock; multi-device publishers SHOULD coordinate or
  accept that the latest clock wins.
- `expires_at − issued_at` MUST be ≤ 3,600 s (v0.8, spec-gap 96). Publishers SHOULD re-sign at ⅔ of
  the lifetime.
- Envelope rules apply, with the core §12.9 exception for hints: the age bound is the record's own
  `expires_at`, not the 300 s replay window — a node stores, replicates and returns a hint, and a
  reader accepts it, while `issued_at` is no more than 300 s in the future and `now < expires_at`.
  The 300 s window would otherwise make every hint unusable 300 s after signing, whatever its TTL,
  and no node that missed the first 300 s could ever store it (measured on the WAN testbed). Replay
  of a hint is harmless: §8.3 discards a lower `seq` and treats identical content as a no-op, so
  `id` deduplication does not apply. ULID/`issued_at` consistency and the 65,536-byte cap apply
  unchanged.

Schema: `reachability-hint.schema.json` in the v0.8 spec schema set.

## 3. Keying and transport

- DHT key = multihash `sha2-256` (`0x12 0x20` ‖ digest) of the **normalized** subject DID:
  `did:` prefix and method lower-cased, method-specific id untouched.
- Value = the envelope's text frame (compact JSON), forwarded byte-for-byte.
- Overlay: libp2p Kademlia, protocol `/dsip/hints/0.6`, server mode for nodes that accept
  storage. Bootstrap peers are configuration; implementations SHOULD accept several and SHOULD
  persist learned peers across restarts.

## 4. Verification (MUST, at every hop)

Before a node stores, forwards, or returns a record it MUST:

1. Verify the envelope (§10.2 pipeline) and that `from == subject == verified identity`.
2. Validate the payload against the hint schema. A `key_agreement` member must verify as a key agreement delegation
   (core §7.3) whose `subject` is the hint's `subject`; a hint whose member does not is refused as a whole
   (`key-agreement-invalid`), as its publisher signed it.
3. Apply §8.3 against any live record it holds for the key:
   higher `seq` replaces; lower `seq` is discarded; identical content is a no-op; same `seq` with
   different content is a conflict — keep the held record, surface a warning.
4. Treat records past `expires_at` as absent.

A node MUST NOT store a record that fails 1–2 (this is the poisoning defense) and SHOULD count
rejections per remote peer for rate limiting.

## 5. Reading

A reader MUST collect **all** records returned for a key, apply §4 to each, and select the
winner by §8.3. Taking the first record returned is non-conformant. The selected hint MUST be
presented to users and logs as hint-sourced, never as an authoritative endpoint.

## 6. Privacy statement (normative)

Publishing a hint discloses, to anyone who knows the subject DID, the subject's current relay
and the fact that it published recently. It is an explicit opt-in. Presence records (§9.4) MUST
NOT be published to this overlay. Querying a key discloses interest in that DID to the nodes
closest to the key.

## 7. Known limits (informative)

Sybil and eclipse are not addressed: a hostile majority near a key can withhold records or
serve stale-but-valid ones; it cannot forge them. Bootstrap entry points are a censorship point
for newcomers. See `docs/dht-findings.md`.

## 8. Registry entries requested

- `dsip-profile`: `dht-hints/0.1` (optional).
- message type `reachability-hint` (not a session message; §12.1 unaffected).
- `dsip-info-about` unchanged.

## 9. Pkarr carrier (v0.9, spec-gap 105)

A `did:key` identity whose identity key can publish MAY also carry its hint on the BitTorrent Mainline DHT through
Pkarr: a BEP 44 mutable item under the identity's own Ed25519 key, whose value is a DNS message. This is in addition
to the overlay of §3, not a replacement. Device-signed hints stay on the overlay, because a BEP 44 item can only be
signed by the key it is stored under.

**Record.**
- The identity publishes TXT records named `_dsip.<z32(key)>`, where `z32` is the z-base-32 encoding Pkarr uses.
- Each record is one endpoint, made of `key=value` character-strings:
  - exactly one `uri=` with a `wss://` URI;
  - one or more `b=` bindings;
  - optionally one `svc=`, the service type the endpoint stands in for, as `endpoints[].service` in §2.
  - Unknown keys are ignored.
- The record's TTL, at most 3600 s, bounds the hint's life:
  - `issued_at` is the signed timestamp, in seconds;
  - `expires_at` is `issued_at` plus the smallest `_dsip` TTL.
- The BEP 44 `seq` is the signed timestamp, in µs, and §8.3 applies to it: a higher `seq` wins, and an equal `seq`
  with different content is a conflict that keeps the held hint. Pkarr's own "larger packet wins" does not apply.

**Publishing.**
- Sign with the identity key over BEP 44's buffer, with no salt.
- Compress names.
- Keep the DNS message at most 996 bytes, so the bencoded value stays within BEP 44's 1000.
- Keep the zone's other records, since the key has one slot shared by every Pkarr use. Every IN record outside
  `_dsip` is carried over:
  - in the RFC 1035 types in which RFC 3597 §4 allows name compression (NS, CNAME, SOA, PTR, MX, MINFO, and the
    obsolete MD, MF, MB, MG, MR), the names inside the record data are expanded and the record re-encoded;
  - every other type is copied byte for byte, since RFC 3597 forbids compression in it.

  Nothing another application published is dropped (`check: "carry"`).
- Sign `max(clock, previous + 1)` (µs), where `previous` is this key's newest timestamp. Never sign ahead of the clock
  otherwise: honest nodes then refuse every lower `seq`. The one exception is after the clock steps backwards, when
  `previous + 1` is ahead of it; a lower `seq` would be refused everywhere (`check: "next-ts"`). A timestamp above
  2^53−1 µs is never signed, since readers reject it.
- Re-sign before `expires_at`. Anyone may re-announce the signed bytes, but that never extends a hint.
- Fetching from Pkarr relays (HTTP `GET /<z32>`) is equivalent to the DHT. A relay can withhold or serve an older
  hint; it cannot forge one.

**Reading.** A reader verifies the payload offline before use, in the order and with the reason tokens of
`impl/vectors/README.md`, kind `pkarr`:
1. the subject is a `did:key`;
2. the payload is the right size;
3. the BEP 44 signature verifies under the DID's key;
4. the timestamp is at most 2^53−1 µs and no more than 300 s ahead;
5. the DNS message parses, with backward-only compression pointers;
6. only `_dsip.<z32>` TXT records are used, compared label by label without case;
7. the endpoints are well formed;
8. every TTL is at most 3600 s;
9. the hint has not expired.

These are the checks Pkarr itself does not make: it accepts future timestamps, records outside the key's zone,
non-canonical z-base-32 and any TXT content. A hint from Pkarr is a hint like any other (§1): it never overrides a DID
document and is shown as hint-sourced.

**Privacy.** As §6, plus the relays: a relay sees the client's address and which key it looks up.

### 9.1 Multi-device identities (v0.10; spec-gap 105 option (b))

An identity whose key stays offline still publishes on Pkarr. The identity key signs a long-lived **pointer** naming
its devices, and each device signs its **own** hint in its own zone, carrying the delegation that makes it the
identity's.

**Pointer** (in the identity's zone, signed by the identity key):
- TXT records named `_dsip-devices.<z32(identity key)>`, one per device. Each has exactly one `dev=` character-string
  whose value is the device's `did:key`; unknown keys are ignored.
- Each TTL is at most 604,800 s (7 days). The pointer expires at its signed timestamp plus the smallest of those
  TTLs.
- It may share the zone with the identity's own `_dsip` records (§9): readers of §9 ignore it.

**Device hint** (in the device's zone, signed by the device key):
- the `_dsip` records of §9, read exactly as §9 says, so the 3,600 s cap applies;
- exactly one TXT record named `_dsip-delegation.<z32(device key)>`. Its character-strings, concatenated in order, are
  the compact delegation (§7.4) from the identity to the device.

**Reading.** A reader resolves the pointer, then each device it lists, in order, as `impl/vectors/README.md`
specifies (`check: "devices"`). A device counts only if its hint reads as §9 and its delegation verifies (§7.4:
signed by the identity, naming this device, with `dsip.signaling`, live, not revoked by any revocation the reader
holds). The device's hint is usable until the earlier of its own expiry and its delegation's.

**Revocation is bounded, not immediate.** A revoked device stops counting as soon as the reader holds the revocation
(§7.4). A reader that does not hold it can still reach that device until one of three things happens: the device's
delegation expires, its hourly hint lapses (a revoked device can still sign one), or the identity re-signs the
pointer without it, at most 7 days later. Short delegation lifetimes tighten this bound. A hint never carries
authority (§8.1), so a stale device costs at most a failed attempt to reach it, never trust.

## 10. HTTP access (v0.11)

A node MAY serve hints over HTTP for clients that cannot join a DHT: browsers, which have no UDP and no libp2p, and
light clients. It is the same tier as the DHT. A client verifies everything it receives exactly as it would from the
DHT (§4, §9). **Withholding, or serving an older hint, is a node's only power**: it cannot forge one, as §9 says of
Pkarr relays.

| request | answer |
|---|---|
| `GET /<z32>` | 200 with the Pkarr relay payload (`signature ‖ ts ‖ dns`), or 404 |
| `PUT /<z32>` | 204 stored, or the same bytes held; 409 an older or conflicting `ts`; 400 rejected |
| `GET /dsip/v1/hints/<did>` | 200 `{"hints": ["<record>", …]}`, the §2 records held for the DID, each verified and unexpired; `[]` when there are none |
| `POST /dsip/v1/hints` | a §2 record: 202 stored; 409 a held record wins (§8.3); 400 rejected |
| `GET /dsip/v1/tn/<tn>` | 200 `{"bindings": [...]}`: number bindings (Number Attestation N§6, draft), when the node serves numbers; else 404 |
| `PUT /dsip/v1/tn/<tn>` | a number binding: 204 stored or the same one held; 409 an older one, or the set is full; 400 rejected |

- **`/<z32>` is Pkarr's relay interface,** so Pkarr clients and DSIP's Pkarr readers use a node unchanged. The path
  is the key's canonical z-base-32, lowercase: unlike an owner name in the DNS message, it is not compared without
  case.
  - A node serves **every** application's packets, so before storing a `PUT` it checks only what every packet must
    pass: the canonical key, the frame, the signature, the timestamp and the DNS message. Then it applies §8.3's
    `ts` rule against what it holds (`check: "store"`).
  - `_dsip` content is judged by readers.
  - A stored packet MAY be put on the Mainline DHT.
  - **A held packet is a cache, not a store of record.** A packet is fresh until its `ts` plus its shortest record
    TTL; a node can compute this for any application's packet. A node SHOULD look for a newer packet on Mainline
    before serving one that is no longer fresh. It MAY also look while the packet is fresh, without delaying the
    answer. Without this, an honest node serves a packet that expired after its publisher re-signed, which readers
    cannot tell from withholding (spec-gap 109).
- **`/dsip/v1/hints` is the overlay's.** A posted record is verified as §4 requires before it is stored or put on the
  overlay, and §8.3 decides between it and a held record.
- **Answers** carry `Access-Control-Allow-Origin: *`. A node MAY limit request rates, answering 429.
- **Pointing a client at a node** is configuration, like a Pkarr relay (spec-gap 114: a client is given its nodes by
  the origin that serves it or by hand, never by its relay's `hello`). Nothing in DSIP makes any node authoritative.

