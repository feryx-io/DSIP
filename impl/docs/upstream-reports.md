# Upstream reports — ready to send

Findings from implementing did:webvh (spec-gaps 101–102) and KEYTRANS (spec-gaps 104), rechecked on 2026-10-05
against the current texts, and again on 2026-10-09 (every report below still stands):
- the did:webvh v1.0 spec as of `7846c94` (2026-10-09; the commits since `7e39c70` concern DID URL handling and an
  at-risk note on implicit services, nothing on entries, JCS, I-JSON or the schema; `schemas/v1.0/log_entry.json`
  still has `minItems: 1` on the three arrays, a `proof` that may be one object, and `"type": "date-time"`);
- `didwebvh-ts` 2.8.0 (still the latest on npm, published 2026-06-26; the repository has moved on, with
  `nextKeyHashes` guards merged 2026-10-01, and nothing newer is published) and `didwebvh-rs` 0.8.0 (the latest on
  crates.io, 2026-10-01);
- `draft-ietf-keytrans-protocol` -05 (still the latest revision on the datatracker), and the editors' copy still at
  `a214b15` (2026-09-16); issue #51 is still open;
- net-snmp: Debian trixie still ships 5.9.4+dfsg-2+deb13u1 and Ubuntu noble-updates 5.9.4+dfsg-1.1ubuntu3.2, both
  with the TLS 1.0 cap; unstable and the next Ubuntu carry 5.9.5.2;
- RFC 5848: no errata on file.

Findings already fixed upstream are listed at the end and are **not** to be sent. Each report links to a vector in
`https://github.com/feryx-io/DSIP/tree/main/impl/vectors`, so it can be reproduced.

---

## did:webvh — specification (github.com/decentralized-identity/didwebvh)

### 1. Log entries may carry properties that no signature covers

**Title:** Log entry: unknown properties are dropped before hashing, so they are covered by no signature

The spec lists a log entry's properties (`versionId`, `versionTime`, `parameters`, `state`, `proof`), but never says
an entry MUST NOT have others. Both reference libraries strip unknown entry properties before computing the entry
hash and verifying the proof. As a result, a property added **after** the entry was hashed and signed resolves as
valid in `didwebvh-rs` 0.8.0 and `didwebvh-ts` 2.8.0, and its content is covered by no signature. A consumer that
reads the raw log, or a later spec version that gives a new property meaning, would trust unsigned data.

**Reproduce:** the vector `did-webvh/unknown-entry-key.json` is a valid log with one extra entry key.

**Suggest:** "A log entry MUST NOT contain properties other than these five. A resolver MUST reject a log
containing one." This mirrors the existing rule for unknown `method` values.

### 2. I-JSON is not required, but JCS assumes it

**Title:** Require I-JSON (RFC 7493) for log entries: JCS (RFC 8785) is undefined outside it

Entry hashes and Data Integrity proofs use JCS, and RFC 8785 is defined only for I-JSON input. The method never
requires I-JSON, so implementations disagree on logs that fall outside it:
- integers beyond 2^53, which some parsers round;
- duplicate member names, where implementations keep the first or the last;
- lone surrogates in strings;
- `-0`.

Different implementations then compute different hashes for the same bytes.

**Reproduce:** the `did-webvh/ijson-*.json` vectors (`ijson-duplicate-name`, `ijson-integer-beyond-max-safe`,
`ijson-lone-surrogate`, `ijson-minus-zero`).

**Suggest:** "The log file, every entry, and the witness file MUST be I-JSON (RFC 7493). A resolver MUST reject
input that is not."

### 3. `schemas/v1.0/log_entry.json` disagrees with the prose

**Title:** log_entry.json: minItems contradicts the prose; proof shape; invalid "type": "date-time"

- `updateKeys`, `nextKeyHashes` and `watchers` have `minItems: 1`. But the prose uses `[]`: an empty `updateKeys` to
  deactivate, and an empty `nextKeyHashes` to end pre-rotation. A schema-validating resolver rejects valid logs.
- `proof` is accepted as a single object, where the prose requires an array.
- `"type": "date-time"` (lines 11 and 264) is not valid JSON Schema. It should be `"type": "string", "format":
  "date-time"`.

### 4. Smaller inconsistencies

**Title:** v1.0 editorial: monotonicity wording, examples, value types

- The security section says `versionTime` must move forward by "one second"; the normative text says "strictly
  greater".
- A `nextKeyHashes` example still uses the legacy base32 form.
- The metadata `ttl` and `witness.threshold` are specified as strings, while implementations emit integers.
- `portable: false` together with a move in the same entry is not addressed.
- Leading zeros in the `versionId` number, and fractional seconds in `versionTime`, are neither allowed nor forbidden.

---

## didwebvh-rs (github.com/decentralized-identity/didwebvh-rs)

### 5. Accepts an unknown `method` version, and unsigned extra entry keys

**Title:** 0.8.0 accepts `method: "did:webvh:9.9"` and log entries with extra keys

- The spec says unrecognised `method` values are rejected and never silently downgraded (its own negative example is
  `did:webvh:99.0`). 0.8.0 resolves a log whose first entry has `parameters.method: "did:webvh:9.9"`. Reproduce with
  the vector `did-webvh/method-unknown.json`, which expects a rejection.
- 0.8.0 also resolves a log entry carrying a key beyond the five defined ones (report 1).

---

## didwebvh-ts (github.com/decentralized-identity/didwebvh-ts)

### 6. The published package predates the June hardening

**Title:** Publish 3.0.0: npm's 2.8.0 accepts logs the current spec rejects

The latest version on npm, 2.8.0, accepts each of the following, all of which the current spec rejects. Where a
DSIP vector reproduces one, it is named:
- an entry after deactivation (`entry-after-deactivation`);
- a portable move without `alsoKnownAs`;
- an empty `proof` array;
- an omitted `nextKeyHashes` under pre-rotation (`pre-rotation-omits-nexthashes`);
- unknown parameters (`unknown-parameter`);
- extra entry keys (`unknown-entry-key`).

The repository is at 3.0.0, which is not published to npm, so anyone installing from npm gets 2.8.0. We have not
tested 3.0.0 against these cases.

---

## KEYTRANS — protocol draft (github.com/ietf-wg-keytrans/draft-protocol, or keytrans@ietf.org)

### 7. The root of an empty prefix tree is unspecified

**Title:** Define the prefix-tree root value when the tree is empty

The prefix tree's root is defined in terms of its children, but neither -05 nor the current editors' copy says what
the root value is when the tree holds no search keys (for example, before any label is inserted). Implementations
must pick something (all zeros, an empty hash, or absent), and if they pick differently they compute different
`TreeHeadTBS` values. Suggest defining it explicitly.

### 8. `Kc` wording

**Title:** Kc: "the byte sequence equal to the hex-encoded string" is ambiguous

The cipher-suite text defines `Kc` as "the byte sequence equal to the hex-encoded string
`d821f8790d97709796b4d7903357c3f5`". That can be read as the 16 bytes that string encodes, or as the 32 ASCII bytes
of the string. The independent implementation `katie`, and ours, use the 16 decoded bytes. Suggest: "the 16 bytes
whose hexadecimal encoding is …".

### 9. VRF details that change outputs

**Title:** State the ECVRF validate_key choice, point decoding, and TAI counter bound

The suites use ECVRF-P256-SHA256-TAI and ECVRF-EDWARDS25519-SHA512-TAI (RFC 9381). RFC 9381 leaves choices that
can change whether a proof verifies:
- whether `ECVRF_verify` runs with `validate_key` (rejecting low-order public keys);
- whether point decoding must be canonical.

Two conforming implementations can therefore disagree on the same proof. Suggest fixing both for KT.

### 10. Comment on issue #51 (PrefixProof parsing)

The current editors' copy now defines the `depth` of a `nonInclusionParent` result as the depth of the missing
(stand-in) leaf, not of its parent. That looks like it settles the depth half of #51. Is the question of which
`elements` such a proof carries now settled too, or still open? (A question to ask, not a finding to assert.)

---

## net-snmp in Debian trixie and Ubuntu 24.04 (bugs.debian.org, package net-snmp; Launchpad, net-snmp)

### 11. The `tls:` transport cannot connect: backport upstream commit 8570eb2b

**Title:** net-snmp 5.9.4: TLS client capped at TLS 1.0, so snmptrap/snmpget over `tls:` always fail

Found 2026-10-06 while testing SNMP over TLS (RFC 6353). net-snmp 5.9.4's `snmpTLSTCPDomain.c` calls
`SSL_CTX_set_max_proto_version(ctx, TLS1_VERSION)` on the client side. OpenSSL 3 at its default security level
refuses TLS 1.0, so the client sends a fatal `protocol_version` alert (`15 03 03 00 02 02 46`) before any
ClientHello. snmptrap then reports `tlstcp: failed to ssl_connect` and `Unknown host`.

Upstream fixed this in 5.9.5 with commit `8570eb2b40dd342fb4e2e2f0a34fe0eef400079a` ("Allow TLS protocols higher
than TLS10", 2 lines). Debian forky and sid already ship 5.9.5.2. Trixie (5.9.4+dfsg-2+deb13u1) and Ubuntu noble
(5.9.4+dfsg-1.1ubuntu3.2) do not.

**Reproduce:** run any TLS server that requires a client certificate, then
`snmptrap -v 3 --defSecurityModel=tsm -l authPriv -T localCert=… -T trustCert=… tls:host:10162 …`.
The server sees only the alert.

**Suggest:** a stable update that cherry-picks `8570eb2b`.

---

## RFC 5848 (syslog-sign): errata (rfc-editor.org/errata.php, "Submit Errata")

Found 2026-10-06 while implementing a collector. Both of RFC 5848's examples verify: the Certificate Block's `K` key
checks its own signature and the Signature Block's, with SHA-1 over the message with ` SIGN="…"` removed. The
DSIP vectors `syslog-sign-rfc5848-*` carry them verbatim. RFC 5848 has no errata on file.

### 12. FRAG: the field table says base64, the example carries the payload text

**Type:** Technical. **Section:** 5.3.2 (table), 5.3.2.7; example 5.3.2.9.

The field table describes FRAG as "variable (base64 encoded binary)". The example's FRAG is the Payload Block
itself, `2009-05-03T14:00:39.519005+02:00 K BACsLMZ…`, 587 octets, with FLEN and TPBL both 587. It is not base64 of
it. The Payload Block is already printable (§5.2.1 base64-encodes its key blob), so carrying it directly is what the
example's signer does, and a collector that base64-decodes FRAG rejects the RFC's own example.

**Suggest:** in the table, "variable (a fragment of the Payload Block, which is printable ASCII)"; in 5.3.2.7, "FRAG
is the fragment itself, not further encoded."

### 13. The example's MPI bit count does not match its value

**Type:** Editorial. **Section:** 4.2.8, 4.2.9.

The Signature Block example's SIGN starts `AKBb…`: an MPI declaring 160 bits (`00 a0`), whose first byte `0x5b` makes
the value 159 bits long. RFC 4880 §3.2 defines the count as the value's exact bit length. A collector that enforces
RFC 4880 strictly rejects the RFC's own example, so 4.2.8 should say whether the count is exact or only a length.

**Suggest:** "The bit count of each MPI gives its length; collectors MUST NOT require it to equal the value's bit
length", or else correct the example.

---

## Already fixed upstream (not to be sent)

- **KEYTRANS Mode-1 `leaf_public_key`.** The editors' copy keeps it only for third-party management (commit
  `b97f81d`).
- **KEYTRANS vector-length semantics.** The editors' copy now says lengths count elements.
- **KEYTRANS stray `UpdateRequest request;`.** It is gone from the editors' copy.
- **did:webvh unknown `method` values.** The spec now rejects them explicitly, with the negative example
  `did:webvh:99.0`; only the library behaviour (report 5) remains.
