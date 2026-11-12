# DSIP: Decentralized Session Initiation Protocol

## A Narrow Core for Trusted Real-Time Media Sessions

**Version:** 1.0
**Status:** Normative — DSIP Core 1.0 (`dsip.core` `1.0`); what a later 1.x revision may change is §11.4
**Editor:** James Ferris
**Date:** October 2026
**Supersedes:** v0.17
**Companion documents:** WebRTC Media Binding 1.0 (`dsip-webrtc-media-binding-v1.0.md`); Gateway Profile 1.0 (`dsip-gateway-profile-v1.0.md`); Messaging Profile 1.0 (`dsip-messaging-profile-v1.0.md`, with its schema set `dsip-messaging-schemas-draft/`); RTP/SRTP Media Binding (draft, `dsip-rtp-srtp-media-binding-v1.0-draft.md`); DHT Hints Profile (draft, `dsip-dht-hints-profile-v1.0-draft.md`); Alias Transparency Profile (draft, `dsip-alias-transparency-profile-v1.0-draft.md`); Device Events Profile 1.0 (`dsip-device-events-profile-v1.0.md`); Recording Profile (draft, `dsip-recording-profile-v1.0-draft.md`); Number Attestation Profile (draft, `dsip-number-attestation-profile-v1.0-draft.md`); Presence Profile (draft, `dsip-presence-profile-v1.0-draft.md`); Wake Profile (draft, `dsip-wake-profile-v1.0-draft.md`, with its schema set `dsip-wake-schemas-draft/`); JSON Schema set v0.17 (`dsip-schemas-v1.0/`); conformance vectors (`impl/vectors/`, 2,475 vectors on which the Python harness, the Rust reference implementation and the independent TypeScript implementation agree)

---

## 1. Abstract

DSIP, the **Decentralized Session Initiation Protocol**, is an identity-first signaling and media negotiation protocol for establishing trusted real-time sessions between identity-aware endpoints.

DSIP is inspired by SIP, but it is not a wire-compatible replacement for SIP and it is not limited to telephony. DSIP uses decentralized identifiers, signed signaling, explicit media negotiation, and verifiable session identity to let participants answer a small set of critical questions before media flows:

- Who is initiating or publishing this session?
- Can that identity be verified?
- What kind of session is being requested?
- What media types and codecs are supported?
- What transport and encryption modes are available?
- What policies apply to recording, transcription, relay, AI processing, and redistribution?
- What trust level should the receiver apply?

The long-term vision for DSIP includes calls, video sessions, broadcasts, AI agents, device media, messaging, public safety, and future real-time media use cases. The v1.0 scope is intentionally smaller.

**DSIP Core v1.0 focuses on two initial profiles:**

1. **Interactive Media Profile** — one-to-one and small-group real-time audio/video/data sessions.
2. **Verified Broadcast Profile** — signed publication and subscription metadata for live audio/video streams.

Other use cases, including device control, vehicle media, sensor telemetry, emergency calling, public-safety dispatch, contact-center routing, and rich messaging, are future profiles that build on the DSIP core rather than being included in the first implementable specification.

The purpose of DSIP v1.0 is not to solve every real-time media problem. It is to define a credible, implementable foundation for trusted session initiation and negotiation.

The industry context sharpens the motivation. Carriers are exiting the voice business to concentrate on network infrastructure and AI-era connectivity, abandoning the registrar role they have held for a century. The question is no longer whether real-time communication identity gets rebuilt outside the carrier model, but on what substrate. DSIP proposes that substrate.

---

## 2. Definition

DSIP stands for:
> **Decentralized Session Initiation Protocol**

DSIP should not be described primarily as "Decentralized SIP."

A better definition is:
> DSIP is a decentralized, identity-first protocol for initiating, authenticating, and negotiating trusted real-time media sessions.

An endpoint may eventually be a person, browser, phone, media server, AI agent, broadcaster, device, gateway, or service. But DSIP Core v1.0 only requires endpoint behavior needed for interactive media sessions and verified broadcast publication/subscription.

---

## 3. Scope of DSIP Core v1.0

### 3.1 In Scope

DSIP Core v1.0 defines:

- Endpoint identity using DIDs or DID-compatible identifiers
- Signed signaling envelopes
- Version negotiation
- Capability discovery
- Media offer/answer negotiation
- Codec and transport capability exchange
- Session lifecycle: a complete state machine with defined races, timers, forking, and renegotiation (§12)
- Signaling transport bindings, with WebSocket Secure mandatory-to-implement (§13)
- Answer semantics and media timing rules (§14)
- A unified reason code framework (§15)
- Trust metadata
- Policy declarations
- Error handling
- Extension negotiation
- Relay semantics for connection binding, delivery, forking, and per-leg cancellation
- Two initial application profiles:
  * Interactive Media
  * Verified Broadcast

### 3.2 Out of Scope for Core v1.0

The following are not part of the DSIP Core v1.0 requirement set:

- Full messaging interoperability as a core requirement (messaging is the companion Messaging Profile, §6.1)
- Device command/control
- Sensor telemetry
- Vehicle communication
- Emergency calling to 911/112/999 (see Appendix B)
- Lawful intercept frameworks
- Contact-center queue semantics beyond the bounded-wait behavior of §12
- AI agent orchestration
- Payment settlement
- Global reputation algorithms
- Global identity governance
- New media transport protocols
- New audio/video codecs
- Replacement for WebRTC, RTP, HLS, DASH, SRT, RIST, or QUIC media

These are valid future profiles or bindings, but they are not required for v1.0 interoperability.

### 3.3 Initial Profiles

DSIP v1.0 defines only two required profiles.

#### Interactive Media Profile

Supports real-time conversational sessions such as:

- Voice call
- Video call
- Small group media session (star topology via a group focus, §17.4)
- Browser-to-browser media
- SIP/WebRTC gateway scenario
- AI gateway as an endpoint, but without standardizing AI behavior

#### Verified Broadcast Profile

Supports publication and subscription metadata for live media such as:

- Radio stream
- TV audio/video stream
- Live event stream
- Public meeting stream
- News stream
- Sports commentary stream
- Organization-owned media feed

This profile verifies publisher identity and stream metadata. It does not replace CDNs, HLS, DASH, SRT, RIST, WebRTC, or broadcast contribution/distribution systems.

#### Companion Profiles (v0.8)

Two further profiles are published beside the core as optional conformance pieces (§24.4). Neither is required of every endpoint, and the core depends on neither.

- **Gateway Profile 1.0** — DSIP ↔ SIP/PSTN gateways (§6.3, Appendix C).
- **Messaging Profile 1.0** — mailboxes, end-to-end encrypted conversations, multi-device history and voicemail (§6.1).

---

## 4. Non-Goals

DSIP v1.0 explicitly states what it does not attempt to solve.

DSIP does not define a universal anti-spam system.

DSIP does not make anonymous self-issued identities trustworthy by default.

DSIP does not make emergency calling decentralized.

DSIP does not make AI disclosure technically enforceable.

DSIP does not guarantee that a verified logo means a user should trust the caller.

DSIP does not require blockchain infrastructure.

DSIP does not replace media transports.

DSIP does not require a single global registry.

DSIP does not solve all key recovery and consumer identity UX problems by itself.

**DSIP does not define signaling over raw UDP datagrams.** Signed DSIP envelopes routinely exceed practical UDP datagram limits, and session state integrity requires reliable delivery that would otherwise have to be reinvented at the application layer — a burden that SIP's dual UDP/TCP transport model demonstrated to be a major source of implementation complexity and interoperability failure. Loss-tolerant transport belongs to the media layer, where the negotiated media stack already provides it.

**DSIP does not define early media or delayed media.** Media never flows before a signed `answer`, and every `invite` carries a media offer. Early media existed in SIP because the PSTN coupled *answer* to *billing supervision*: anything the network wanted to play without charging the caller — ringback, announcements, intercepts — had to happen before answer. Delayed media (offerless INVITE) existed for third-party call control. Both mechanisms purchased their functionality at severe cost: media flowing before authentication and consent completed, SRTP key-establishment ordering ambiguity, the forked-early-media rendering problem, decades of one-way-audio interoperability failures (RFC 3960 exists to manage them), and fraud through unbilled media paths. DSIP has no billing supervision coupled to answer, so the economic reason to play media "before answer" does not exist. Call progress is carried in signaling (`progress`); announcements are carried as structured reason codes (§15) or delivered by simply answering the session; screening is performed by answering with constrained media and escalating (§14.4). Applying §5.7: the conventions early media served survive; the mechanism does not re-earn its place.

DSIP provides protocol mechanisms that deployments and profiles can use to build safer systems. It should not claim to solve social, regulatory, or economic problems solely through message formats.

---

## 5. Core Principles

### 5.1 Small Core, Explicit Profiles

The DSIP core remains small. Features that are not required for all endpoints are moved into profiles or extensions.

### 5.2 Identity First, But Not Identity Naive

Every DSIP session is bound to cryptographic identity. However, identity alone is not trust. A self-issued identity proves key control, not legitimacy.

DSIP must distinguish between:

- Self-issued identity
- Domain-bound identity
- Organization-verified identity
- Credential-backed identity
- Regulated identity
- Anonymous or ephemeral identity

### 5.3 Trust Is Contextual

A credential is only meaningful if the verifier trusts the issuer for that claim.

A client should not display a generic "verified" badge without context. It should display claims in a way that makes the trust basis clear.

Examples:

- "Domain verified: acme.com"
- "Organization credential issued by Example CA"
- "Emergency publisher credential issued by State Authority"
- "Self-issued identity; not externally verified"

### 5.4 Protocol Mechanism, Not Policy Magic

DSIP can provide identity, signatures, credentials, policy declarations, and consent receipts. It cannot force good behavior by malicious actors.

Spam prevention, AI disclosure compliance, moderation, and abuse response require deployment policy, credential issuers, client UX, rate limits, payment models, reputation, regulation, or a combination of those.

### 5.5 Transport Independence for Media

DSIP negotiates media sessions. It does not mandate one media transport.

The first interoperable implementations should use WebRTC and/or RTP/SRTP because existing media stacks already solve NAT traversal, congestion control, jitter handling, and encryption.

Signaling transport is treated differently: signaling requires reliable, ordered, encrypted delivery, and Core v1.0 mandates one implementable binding (§13). The division of labor is deliberate: media is loss-tolerant and latency-critical, so it runs over UDP-based media stacks; signaling is loss-intolerant — a dropped `cancel` or `bye` corrupts session state — so it runs over reliable transport.

### 5.6 Realistic Decentralization

DSIP is honest about decentralization.

- `did:key` is self-certifying but hard to recover and hard to make human-friendly.
- `did:web` is practical for organizations but depends on DNS and Web PKI.
- `did:webvh` keeps `did:web`'s hosting but makes the document unforgeable by the host; availability still depends on it (v0.9).
- DHTs may improve censorship resistance but introduce Sybil and eclipse attack risks.
- WebFinger can improve usability but may leak account existence.
- Federation reduces dependence on one provider but does not eliminate trust boundaries.
- Waking sleeping mobile devices requires platform push services, which are centralized (§13.3).

DSIP supports multiple discovery mechanisms, but v1.0 defines clear authority and conflict-resolution rules.

### 5.7 Conventions, Not Mechanisms

DSIP preserves the interaction conventions users already understand — ringing, answering, declining, holding, hanging up — but does not inherit implementation mechanisms from legacy protocols unless those mechanisms independently meet today's requirements.

When evaluating whether to adopt a mechanism from SIP, XMPP, or the PSTN, the question is never "is this how it was done?" but "would we design this today?" The user-facing convention survives; the mechanism beneath it must re-earn its place. This principle decided the exclusions of UDP signaling, early media, delayed media, and numeric reason codes in this draft, and it should govern future evaluations of E.164 interop conventions, offer/answer variants, and presence models.

---

## 6. Relationship to Adjacent Standards

DSIP reuses existing standards wherever possible and avoids reinventing mature work.

Relevant standards and work areas include:

- W3C DID Core for decentralized identifiers
- W3C Verifiable Credentials for cryptographic claims and presentations
- IETF MLS for group key establishment and secure group messaging
- IETF MIMI for messaging interoperability lessons and identity introduction problems
- IETF SFrame for end-to-end media encryption through SFUs
- SIP, SDP, RTP, SRTP, ICE, TURN, and WebRTC for existing real-time media behavior
- STIR/SHAKEN, PASSporT, and Rich Call Data for PSTN identity interop
- SCITT-style transparency patterns for auditable signed statements
- C2PA for content provenance vocabulary alignment in the broadcast profile
- RFC 4103 / T.140 real-time text for accessibility
- HLS, DASH, SRT, RIST, WebRTC, and QUIC-based systems for media distribution

DSIP positions itself as a session identity and negotiation layer, not as a replacement for these systems.

### 6.1 Messaging

DSIP Core does not become a messaging standard.

Messaging is the companion **DSIP Messaging Profile 1.0** (`messaging/1.0`): mailbox services that store and forward for identities, MLS end-to-end encryption with one ordering hub per group, multi-device history through an identity-level archive key, receipts and activity, voicemail, and first contact through the core introduction/grant exchange (§19.4). It uses core identity, delegation, envelopes and discovery unchanged, adds its own message types and conformance pieces (§12.1, §24.4), and reuses MIMI/MLS concepts rather than inventing new ones. The core does not depend on it.

### 6.2 Group Security

For group messaging and some control channels, MLS should be considered before inventing a new group key management model. The Messaging Profile adopts MLS (RFC 9420) for conversation content and HPKE (RFC 9180) for sealed introductions (§19.4). For media through SFUs, SFrame should be considered before inventing a new E2EE media frame protection mechanism.

The v1.0 encryption floor is explicit: transport encryption for the negotiated media binding (DTLS-SRTP for the WebRTC binding) is REQUIRED. End-to-end encryption through SFUs via SFrame is a named future extension (`sframe-e2ee/1.0`, reserved), not a v1.0 requirement.

### 6.3 SIP/PSTN Interop

SIP/PSTN interop is a gateway profile, not a core assumption. The companion **DSIP Gateway Profile 1.0** defines it: gateway identity, the gateway controller, reason mapping in both directions (§15.5), `tel` caller claims (§18.1), the conditions that trigger `gateway.downgraded`, and early media at the gateway. Its media side toward SIP trunks is the RTP/SRTP Media Binding (§17.2, draft).

A DSIP-to-SIP gateway can translate session signaling, but it cannot preserve all DSIP trust semantics across the PSTN. Identity, consent, policy, and rich session metadata may be downgraded or lost. Appendix C describes the full reality of PSTN gateway obligations; the core carries only the principle:

> Crossing into the PSTN is a trust downgrade unless the gateway can preserve and assert DSIP identity semantics through supported PSTN identity mechanisms.

---

## 7. Identity Model

### 7.1 Identity Types

DSIP supports several identity classes:

```
self-issued
personal
organizational
service
broadcaster
gateway
relay
ephemeral
anonymous
regulated
```

The class helps clients apply the right UX and policy.

### 7.2 DID Usage

Recommended DID methods for early DSIP profiles:

```
did:key    Self-certifying identities, test endpoints, ephemeral users, devices
did:webvh  Organizations and individuals who want a domain-hosted document the host cannot forge (v0.9)
did:web    Organizations, broadcasters, domains, gateways, service providers
```

Other DID methods may be supported by extension, but v1.0 keeps the required set small.

**`did:webvh` (v0.9, spec-gap 101).** `did:webvh` v1.0 (DIF Ratified Specification, `did:webvh:1.0`) is `did:web` plus a verifiable history: the DID document is published as a log of entries, each hash-chained to the one before and signed by the identity's update keys, and the DID itself embeds a self-certifying identifier (SCID) derived from the first entry. The host serving the log can withhold it or serve an older version, but it cannot forge one. Keys rotate within the log, optionally pre-committed (pre-rotation), and optional witnesses co-sign updates. A DSIP resolver of `did:webvh`:

- MUST verify the whole log as the method specifies, and MUST reject it if any entry fails. It MUST NOT return the document of a deactivated DID; such an identity has no keys.
- MUST support `did:webvh:1.0` and MUST reject other method versions.
- MUST read the log as I-JSON (RFC 7493), since the method's canonicalization (JCS, RFC 8785) assumes it.
- MUST remember, per DID, the highest `versionId` it has verified, and MUST reject a log that ends before it (rollback) or holds a different entry at that position (fork). Without this, a host could roll an identity back to a key it has since rotated away from. It MAY also consult the DID's watchers.
- reads the same document properties as for any method (below), and applies §8.1 unchanged: the verified document is the DID document.

The method's canonicalization applies inside its own hashes and proofs only. A DSIP envelope's signature still covers its bytes as sent (§10.2).

**Document properties DSIP reads (v0.8).** Beyond verification methods: service entries (`DSIPSignaling`, §13.2; `DSIPMailbox`, Messaging Profile), embedded X25519 `keyAgreement` methods (the key sealed introductions are encrypted to, §19.4), and `dsipDelegationRevocations` (§7.4). All are authoritative in the order of §8.1.

### 7.3 Identity Keys vs Device Keys

A major usability issue in DID-based systems is key loss and multi-device use.

DSIP separates:

- **Identity controller key** — controls the DID or long-term identity.
- **Device keys** — used by individual devices to sign session messages.
- **Recovery keys** — used to rotate or regain control after loss.
- **Delegation credentials** — authorize devices, agents, gateways, or services to act for an identity.

A user should be able to use multiple devices without sharing one private key across all devices.

**Key agreement delegation (1.x, spec-gap 179).** What is sealed to an identity (sealed introductions §19.4, sealed
bodies §10.4, sealed presence P§12) is sealed to its X25519 key agreement key. For a `did:key` identity with no other,
that key is the one the method derives from the Ed25519 key, and its private half (the first 32 bytes of SHA-512 of the
Ed25519 seed) is Ed25519's own secret scalar: a holder of it can sign as the identity. A device that opens what is
sealed to such an identity therefore holds the identity key in effect. To separate the two, an identity MAY sign a
**key agreement delegation** naming an independent X25519 key:

```json
{
  "type": "KeyAgreementDelegation",
  "subject": "did:key:z6MkUser",
  "key": "z6LSbysY2xFMRpGMhb7tFTLMpeuPRaqaWM1yECx2AtzE3KCc",
  "issued_at": 1760000000,
  "expires_at": 1791536000
}
```

- It is carried as a DSIP-JOSE envelope (§10.2) whose payload is that object, signed **directly by a verification key
  of the subject**, never by a device, as a delegation is (§7.4). `key` is the X25519 public key as `did:key`
  encodes one: multibase base58btc (`z`) of the multicodec `x25519-pub` (0xec 0x01) followed by the 32 bytes.
- It verifies when the signature does, the payload is that object (schema `key-agreement-delegation`),
  `issued_at < expires_at ≤ issued_at + 31,536,000`, `issued_at ≤ now + 300` and `now < expires_at`. It is a
  credential: its source does not matter, only its signature and subject. A verifier holds the verified ones it is
  given.
- The identity's devices hold the private half; how they receive it is the identity's own matter, as for the
  controller key (M§6.9). A device holding only it, its device key and its delegation can open everything sealed to
  the identity and sign nothing as the identity.
- A newer one replaces an older one: of the verified delegations a verifier holds for a subject, the one with the
  greatest `issued_at` is current, ties going to the smaller `key` (compared as strings). An identity that loses the
  private half issues a new one; until senders hold it, they seal to the old.
- It is carried in the subject's reachability hint (DHT Hints Profile §2) and MAY be presented anywhere else a
  credential can be.
- The **key agreement key** of a DID is, in this order (§8.1): its DID document's `keyAgreement` method; else its
  current verified key agreement delegation; else, for `did:key`, the derived key. A key agreement delegation is
  ignored for a DID whose document names a `keyAgreement` method.

### 7.4 Device Delegation

A DID document or credential should be able to state:

```json
{
  "type": "DeviceDelegation",
  "subject": "did:key:z6MkUser",
  "device": "did:key:z6MkPhoneDevice",
  "capabilities": ["dsip.signaling", "dsip.media.interactive"],
  "issued_at": 1760000000,
  "expires_at": 1760600000
}
```

This allows a phone, laptop, browser, or media appliance to participate without exposing the identity root key. Device delegation is load-bearing throughout this specification: session messages are signed by device keys (§12), forked invites create per-device legs (§12.7), and transport connections are bound to device DIDs (§13.2).

**Conveyance (v0.7).** A delegation is carried as a DSIP-JOSE envelope (§10.2) whose payload is the `DeviceDelegation` object and whose signature is made **directly by a verification key of the subject** — delegation chains (a device delegating another device) are not valid in Core v1.0. A verifier obtains delegations from its own store, from the subject's DID document or credentials where the method supports it, and from an optional `delegations` array in the protected header of any envelope the device sends; this last path is what makes `did:key` identities, which have no document to host delegations, usable with devices. Presented delegations are verified like any envelope (signature, `issued_at ≤ now < expires_at`, `dsip.signaling` present) before they bind a `kid` to a `from`.

**Capabilities (v0.8).** Delegation capabilities are registered values (registry `dsip-delegation-capability`: `dsip.signaling`, `dsip.media.interactive`, `dsip.messaging`). Binding any envelope — `hello` included — to its `from` requires `dsip.signaling`. A profile that needs authority of its own adds its capability beside `dsip.signaling`, not instead of it: a Messaging Profile device carries both `dsip.signaling` and `dsip.messaging`, and a device delegated for `dsip.messaging` alone cannot bind, introduce, or grant.

**Revocation (v0.8).** A delegation is revoked before it expires by a `delegation-revocation` record (schema `delegation-revocation.schema.json`):

```json
{
  "dsip": { "core": "1.0", "min_core": "1.0", "profiles": [], "extensions": [], "critical": [] },
  "type": "delegation-revocation",
  "id": "01J5Y0QJR0T00AAAAAAAAAAAAH",
  "from": "did:web:example.com:users:bob",
  "subject": "did:web:example.com:users:bob",
  "device": "did:key:z6MkBobLaptop",
  "revoked_at": 1760000000,
  "reason": "lost",
  "issued_at": 1760000000,
  "expires_at": 1760000300
}
```

Rules:

- `from` MUST equal `subject`, and the record MUST be signed directly by a verification key of the subject — never by a device, including the device it names.
- It revokes every delegation of `device` for `subject` whose `issued_at` is at or before `revoked_at`. A delegation issued later re-enrolls the device.
- `reason` is a registered token (registry `dsip-revocation-reason`; initial values `lost`, `compromised`, `retired`, `policy`).
- Verifiers find revocations in the subject's DID document property `dsipDelegationRevocations` (an array of compact envelopes; authoritative, §8.1) and in any store they hold, however obtained. A validly signed revocation can only remove authority, so its source does not matter. The record is a credential: it is verified by its signature and subject, not by a delivery window.
- A delegation covered by a revocation fails with `delegation-revoked`, after the signature, capability and validity checks. A service that is handed a revocation for a device it has bound SHOULD end that binding at once; the device's next `hello` is refused (`transport.hello-rejected`).
- `did:key` subjects have no document. Their revocations reach verifiers only by distribution — to the identity's own services, or presented alongside. (v0.12, spec-gap 113) Over `ws/1.0` any bound device of the subject MAY send the record itself as a frame (§13.2): the relay verifies that a key of the subject signed it, holds it for every later verification, ends the binding of the device it names, and answers only when it refuses the record (a signed `error`). The Messaging Profile carries revocations to a mailbox in `mailbox-config` (M§5.7).

### 7.5 Key Rotation

DSIP must support key rotation without destroying social identity: the same DID, a new verification key.

Two things carry rotation, and they have different authority:

1. **The DID document is authoritative** (§8.1). A verifier resolves `kid` through the subject's current document; after rotation the retired fragment names no verification method and signatures under it fail (`kid` unresolvable), a delegation signed by the retired key fails with its own verdict, and signatures and delegations under the new key verify. Nothing in DSIP overrides the document.
2. **The `key-rotation` record is the artifact.** It is what transparency logs (§7.7) keep, what caches use to stop trusting a retired key before they re-resolve, and what clients show as trust metadata ("key rotated on …, reason …"). It is a core message type (schema `key-rotation.schema.json`):

```json
{
  "dsip": { "core": "1.0", "min_core": "1.0", "profiles": [], "extensions": [], "critical": [] },
  "type": "key-rotation",
  "id": "01J5Y0QJR0T00AAAAAAAAAAAAF",
  "from": "did:web:example.com:users:bob",
  "subject": "did:web:example.com:users:bob",
  "previous": "did:web:example.com:users:bob#key-1",
  "next": "did:web:example.com:users:bob#key-2",
  "next_public_key_multibase": "z6MkrgXgMcSfqUQ6bhMEL1dhqvPYU4YaueY56Mw8aee9YN4R",
  "reason": "scheduled",
  "devices": ["did:key:z6MkBobLaptop"],
  "issued_at": 1760000000,
  "expires_at": 1760086400
}
```

Rules:

- `from` MUST equal `subject`: only the identity rotates its own keys.
- The envelope MUST be signed by `previous` (the key being retired). When that key is lost, a recovery key of the subject (§7.6) signs instead and the record carries `recovery: true`; verifiers then require the signing `kid` to be a method the subject's document designates for recovery. A record signed by any other key of the subject without `recovery` is invalid.
- `next` MUST differ from `previous`; `next_public_key_multibase` makes the record self-contained for logs and caches.
- `reason` is a registered token (registry `dsip-rotation-reason`; initial values `scheduled`, `compromised`, `lost`, `policy`). `compromised` and `lost` SHOULD cause receivers to drop cached delegations issued under `previous`.
- `devices` lists the device DIDs whose delegations are re-issued under `next` — the device-list update. Delegations signed by `previous` are invalid once the document no longer lists it, whether or not they appear here.
- Replay protection is the envelope's own (`id`, `issued_at`, the §12.9 window); a record is published once and logged, not re-sent.
- `did:key` identities cannot rotate — the DID *is* the key. Rotation for them is a new identity plus a `reject`/`error` with `identity.moved` from the old one (or a signed redirection credential, a future extension), which is why organizations and long-lived personal identities SHOULD use a method with a mutable document.

### 7.6 Recovery Models

DSIP does not mandate one recovery model. Recovery is method- and deployment-specific — offline recovery keys, multi-device quorum, social recovery, organization-admin recovery, hardware security keys, custodial providers, and domain recovery for `did:web` all have different security properties. Clients SHOULD surface the recovery model as part of trust metadata when relevant. A full recovery taxonomy is deferred to deployment guidance. Where a profile keeps identity-level secrets on devices — the Messaging Profile's archive key — whether an escrowed or backed-up copy exists is part of the recovery model and SHOULD be described with it.

### 7.7 Key Transparency

For high-trust deployments, DSIP supports transparency logs or append-only audit mechanisms for key changes, credential issuance, and delegation changes.

This helps detect:

- Silent key substitution
- Compromised issuer behavior
- Unauthorized device addition
- Malicious gateway delegation
- Broadcast publisher hijacking

This is optional in Core v1.0 but recommended for organizational and broadcast identities.

---

## 8. Discovery Model

### 8.1 Discovery Must Have Authority Rules

DSIP v1.0 defines a strict order:

1. **Input identifier is normalized.**
2. **If the input is a DID, resolve it using the DID method.**
3. **If the input is an alias, resolve the alias to a DID using the alias method.**
4. **The DID document is authoritative for DSIP service endpoints, key agreement keys and delegation revocations (§7.2, §7.4).**
5. **Presence, publication, and relay records must be signed by the DID or delegated keys.**
6. **Caches, DHTs, and relays may distribute records but are not authoritative unless the profile explicitly says so.**

### 8.2 Alias Resolution

Human-friendly aliases are necessary for adoption.

Examples:

```
alice@example.com
support@acme.com
live@wxyz.com
wxyz.com/radio/main
```

Alias methods may include:

- WebFinger
- DNS records
- HTTPS well-known endpoints
- QR codes
- Contact cards
- Enterprise directories

Alias resolution returns a DID. The DID, not the alias resolver, becomes the cryptographic identity for the session.

### 8.3 Conflict Resolution

Conflicts must be handled explicitly.

Examples:

- WebFinger says one DID, DNS says another.
- DID document lists multiple DSIP endpoints.
- A relay publishes stale presence.
- A cached record conflicts with a newly resolved record.

Rules:

- DID resolution wins over alias cache.
- Signed records beat unsigned records.
- Newer sequence numbers beat older sequence numbers.
- Records past expiration are invalid.
- Conflicting live records from the same key trigger a warning or hard failure depending on profile.
- DHT records are hints, not authority, unless signed and verified.

### 8.4 Honest Treatment of `did:web`

`did:web` is useful and deployable, especially for organizations and broadcasters. But it is not fully decentralized. It depends on DNS, TLS, domain control, and web hosting.

DSIP describes `did:web` as:
> A practical domain-bound identity method that removes dependence on carrier registrars but still depends on DNS/Web PKI.

The host of a `did:web` document can also rewrite it, replacing the identity's keys, and nothing in the document shows it. `did:webvh` (§7.2) keeps the domain hosting and removes that power: the host still controls whether the log is available, but not what it says, and a resolver that has seen a version detects any older one served in its place.

### 8.5 DHTs and Decentralized Discovery

A DSIP identity needs no DHT, registrar or directory to exist or to be trusted: it is a key (`did:key`) or a document its controller publishes (`did:web`, §7.2), and every record about it is signed by it (§8.1). What a DHT can add is **discovery**: finding where an identity can currently be reached when nothing else says so (a `did:key` has no document). DSIP uses a DHT for that and nothing more. It is an optional **hints tier** (§8.1 rule 6), specified by the DHT Reachability Hints Profile (draft companion). Hints travel on DSIP's own overlay and, for `did:key` identities that publish with their identity key, on the BitTorrent Mainline DHT through Pkarr (v0.9; profile §9).

**What the hints tier guarantees by construction.**

- **Integrity.** A hint is an envelope signed by the identity it describes. Every node verifies it (§10.2) before storing, forwarding or returning it, and the reader verifies it again. A hostile node cannot forge, alter or poison a hint, and a record that does not verify is refused at the first hop, so spam cannot be indexed. A reader collects every record returned for a key and selects by §8.3, never the first one to arrive.
- **Bounded staleness.** A hint expires by its own `expires_at`, under a 3,600 s cap (§12.9; spec-gap 96). An older hint replayed loses to the higher `seq`.
- **No authority.** A hint only chooses which signaling endpoint to dial. Identity, delegation and session security come from the session's own signed envelopes. A hint never overrides a DID document (§8.1) and is presented as hint-sourced.

**What it does not guarantee.**

- **Availability.** Nodes that control the part of the DHT near a key (Sybil and eclipse attacks) can withhold hints or serve stale but valid ones. They cannot forge one, so the worst case is failing to find an endpoint, never reaching the wrong one.
- **Privacy.** Publishing a hint discloses the identity's current relay to anyone who knows its DID; looking one up discloses interest in that DID to the nodes near its key. Publishing is opt-in, and presence MUST NOT be published to the DHT (§9).
- **A first contact with the overlay.** The bootstrap peers a node starts from are a point where a newcomer can be censored.

DHT discovery is therefore optional, not the default. An identity whose DID document advertises a signaling endpoint needs none. A `did:key` identity may publish hints, or give its endpoint directly: in an introduction (§19.4), or in whatever contact exchange put the two parties in touch.

---

## 9. Presence Model

Presence is harder than it looks. SIP and XMPP both included presence; both encountered scale, privacy, and federation challenges. DSIP treats presence as optional and privacy-sensitive.

### 9.1 Presence Is Not Required for Calling

An endpoint can initiate a DSIP session without global public presence.

A DSIP identity may expose:

- No presence
- Contact-only presence
- Domain-only reachability
- Relay-only reachability
- Public broadcast status
- Temporary session availability

### 9.2 Presence Privacy

Presence can reveal sensitive information: whether a person is online, when they are active, which device they use, which network they are on, whether they are in a call, whether they are at home or traveling.

DSIP clients default to private presence.

### 9.3 Subscription Protocol

Presence and publication events use one explicit subscription mechanism, carried by the `subscribe` and `notify` messages. The same mechanics serve the Verified Broadcast Profile's subscribe flow (§22).

A presence record may be visible only to: existing contacts, same organization, authorized subscribers, anonymous users with reduced detail, broadcast followers, or nobody.

#### Subscribing

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["interactive-media/1.0"],
    "extensions": [],
    "critical": []
  },
  "type": "subscribe",
  "id": "01J5Y0QGSXB00AAAAAAAAAAAAD",
  "from": "did:key:z6MkAlicePhone",
  "to": "did:web:example.com",
  "target": "did:web:example.com:users:bob",
  "events": ["presence"],
  "expires_in": 600,
  "issued_at": 1760000000,
  "expires_at": 1760000030
}
```

- `to` is the authority answering for the target (the target's relay or domain endpoint per its DID document); `target` is the subject. A subscriber reaches that authority as any device reaches a relay: it binds there (§13.2), at the relay or endpoint the target's DID document names or, when the target has none (a `did:key` identity), the one the target's reachability hint names (§8.3). A hint-located authority is hint-sourced (§8.1): its own assertion (below) is a claim from a relay the target says it uses, while the subject-signed records it carries are verified by the subscriber whatever relay carries them (§9.4). The binding has the effects of any other: while it lasts the subscriber is reachable through that relay, and an authority that counts bound devices counts it.
- `events` names registered event classes (registry `dsip-subscription-event`; initial values: `presence`, `publication`).
- `expires_in` is the requested subscription lifetime in seconds. Hard caps: 3,600 for `presence`, 86,400 for `publication`; when several event classes are named, the tightest cap applies. A `subscribe` whose `expires_in` exceeds the cap MUST be refused with `error` (reason `policy.subscription-lifetime`); an authority MUST NOT silently clamp, because a clamped lifetime leaves the subscriber's view of its own subscription wrong. Subscriptions are soft state: they expire unless renewed by a fresh `subscribe` for the same `target`+`events` from the same device (which replaces the prior subscription). `expires_in: 0` terminates a matching subscription. A subscription is the subscribing device's (its `from`), so two devices of one identity hold one each for the same target, are notified on their own, and neither's renewal or termination touches the other's (spec-gap 177).
- Optional fields `claims` (verifiable credential presentations) and `capability` (an opaque authorization token previously issued by the target's authority, e.g. via a contact grant or a broadcast follow token) carry authorization evidence.

#### Authorization

Authorization is the **target authority's policy decision** based on the verified subscriber identity, optionally informed by presented `claims` or a `capability` token. The protocol defines the carriage of authorization evidence, not the policy: contacts-only, same-organization, follower-token, and public are all deployment policies applied at the authority.

**Presence is private by default (v0.17, spec-gap 144).** For the `presence` event class an authority admits a
subscriber that presents, in `claims`, a grant from the target whose `scope` includes `dsip.subscribe` (§19.4): an
entry `{"type": "dsip-grant", "grant": <the signed grant envelope>}`. The grantee holds the grant, so the authority
need not have seen it before. The Presence Profile gives the full admission order (P§6). An authority that has no
policy for a target, and is shown no admitting grant or capability, MUST refuse a presence subscription to it with the
uniform `policy.blocked`, except from the target's own devices; it never serves presence publicly by default.

**Anti-enumeration rule.** An authority MUST return the identical response — `reject` with reason `policy.blocked` — for (a) an unauthorized subscription to an existing target and (b) a subscription to a nonexistent target, and SHOULD normalize response timing. Distinguishing "you may not see Alice" from "there is no Alice" turns the subscription system into an account-enumeration oracle. `identity.unknown` is reserved for contexts where existence is already public (e.g., broadcast stream ids published openly). An authority has **seen** a presence target when a device has bound to it for that identity within its retention (§13.3: while bound, and for `offline_retention_s` after the last binding ended), or when it holds a policy for that target or has issued a capability for it (v0.17, spec-gap 149): what the authority issued or was told about a target is knowledge of it, so a capability admits its holder before the target first binds. A publication target is seen while it is published.

#### Notification

Acceptance is signaled by the first `notify`, which MUST carry the current state:

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["interactive-media/1.0"],
    "extensions": [],
    "critical": []
  },
  "type": "notify",
  "id": "01J5Y0QHNTF00AAAAAAAAAAAAE",
  "from": "did:web:example.com",
  "to": "did:key:z6MkAlicePhone",
  "subscription": "01J5Y0QGSXB00AAAAAAAAAAAAD",
  "seq": 1,
  "state": "active",
  "body": { "type": "presence", "state": "available", "audience": "contacts-only" },
  "issued_at": 1760000001,
  "expires_at": 1760000031
}
```

- `subscription` references the `subscribe` this serves; `seq` orders notifies within a subscription (receivers discard lower-than-seen `seq`).
- `state` is `active` or `terminated`. A `terminated` notify is final and SHOULD carry a `reason` (e.g., `session.expired` for lapsed subscriptions, `policy.terminated` for revoked authorization).
- `body` carries the event record. For presence, `body` MAY be the full signed presence record envelope (§9.4) rather than a bare object; the signed form is RECOMMENDED whenever the notifying authority is not the subject itself, so the subscriber can verify the record independently of the relay.
- **Authority-asserted presence.** An authority holding no subject-signed record MAY assert presence from its own connection bindings (§13.2): `available` when any device of the target is bound to it, else `offline`. Such a body is the authority's claim, not the subject's, and clients MUST render it as one. The uniform `policy.blocked` reject applies to targets the authority has never seen exactly as to unauthorized ones (anti-enumeration, above).
- For `publication` events, `body` carries the publication state and `publication` id and, when processors have attached statements (§22.3), a `provenance` list of processor DIDs; the statements themselves are fetched alongside the record.

### 9.4 Signed Presence Records

A signed presence record, as a device publishes it to its authority (Presence Profile P§3, v0.17):

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["presence/0.1"],
    "extensions": [],
    "critical": []
  },
  "type": "presence",
  "id": "01J5Y0QDPRES0AAAAAAAAAAAAA",
  "from": "did:key:z6MkAlicePhone",
  "to": "did:web:example.com",
  "subject": "did:web:example.com:users:alice",
  "device": "did:key:z6MkAlicePhone",
  "audience": "contacts-only",
  "state": "available",
  "profiles": ["interactive-media"],
  "endpoints": [
    {
      "transport": "wss",
      "uri": "wss://relay.example.com/dsip/alice"
    }
  ],
  "seq": 58,
  "issued_at": 1760000000,
  "expires_at": 1760000180
}
```

The signature covers the payload bytes. A record names the Presence Profile, `presence/0.1`, in `dsip.profiles`; an
authority or subscriber that processes presence records lists it among the profiles it supports, and one that does not
refuses the record as any other with no supported profile (§11.2). `device` names the device the record describes and
MUST equal the signer;
`seq` is ordered per `(subject, device)`. `state` is from the open registry `dsip-presence-state` (P§5). How a device
publishes the record, how the authority carries it and how several devices' records combine are the Presence
Profile's (P§3, P§4); a record's age at any receiver is bounded by its own `expires_at` (§12.9).

A record MAY instead be **sealed** to the subscribers its audience admits (Presence Profile `presence/0.2`, P§12;
spec-gaps 152–157): it then carries `kid` and `sealed_state`, the state encrypted under a key derived from the
identity's key agreement secret, in place of `state`, and names `presence/0.2`. The authority checks and routes it
as any record, reading only fields in clear.

### 9.5 Scale Tradeoff

Short TTLs reduce stale presence but increase traffic. Long TTLs reduce traffic but create stale presence. Presence freshness is profile-specific:

```
interactive-media: short-lived or subscription-driven
broadcast: publication state can tolerate slightly longer TTL
emergency/public safety: future regulated profile with stricter requirements
```

---

## 10. Wire Format

### 10.1 One Mandatory Format

DSIP v1.0 defines one mandatory-to-implement envelope format:

> **DSIP-JOSE: UTF-8 JSON payloads secured using JWS.**

Reasons: easy for web developers, easy to debug, familiar to API developers, compatible with DID/VC ecosystems, works well with HTTPS/WebSocket/QUIC APIs, lower adoption friction for early prototypes.

A compact binary profile may be defined later:
> **DSIP-COSE: CBOR payloads secured using COSE.**

DSIP-COSE is optional unless a constrained-device profile later requires it.

### 10.2 Signature Semantics

The signature must cover the exact payload bytes. Implementations must not rely on JSON field ordering after parsing. The signed object is serialized, signed, and transmitted as a signed envelope:

```json
{
  "protected": "base64url(jose-protected-header)",
  "payload": "base64url(dsip-json-payload)",
  "signature": "base64url(signature)"
}
```

Mandatory algorithm set for v1.0: **Ed25519 (EdDSA) MUST be implemented; ES256 MAY be implemented; all other algorithms MUST be rejected.** Algorithm agility beyond this set is a documented v2 concern, not a v1 feature — algorithm sprawl is where signature interop dies. The `kid` of the protected header MUST be a DID URL identifying the verification method (identity key or delegated device key) used to sign; verifiers resolve `kid` through the DID document and delegation credentials (§7.4).

**`from` and the acting identity (v0.12, spec-gap 117).** `from` names the signer: a device acting for an identity under a delegation (§7.4), or the identity itself. The two forms verify the same, and a receiver that needs the identity takes it from the delegation that binds the signer — as it does for `hello`'s `on_behalf_of` (§13.2) and for every session message — whatever the message type. A `grant` or `introduction` whose `from` is a device is from the identity its delegation names, and is checked as that identity's where consent is checked (§19.4, M§14.2).

### 10.3 Payload Rules

DSIP JSON payloads:

- Use UTF-8
- Avoid floating point values
- Use integer timestamps
- Use explicit arrays instead of overloaded strings
- Use registered identifiers for profiles, transports, policies, and codecs
- Use extension namespaces
- Treat unknown non-critical fields as ignorable
- Treat unknown critical fields as fatal

Message `id` values are **ULIDs** (26-character Crockford base32). ULIDs are time-ordered, which the glare resolution rules (§12.6) depend on. JSON Schema files for every message type accompany this specification and are normative for payload shape; prose examples defer to the schemas where they conflict.

### 10.4 Sealed Bodies (extension `sealed-body/1.0`)

*(v0.8, spec-gap 97.)* Envelopes are signed, not encrypted (§20.7): every relay that routes a session reads its SDP and trickled ICE candidates (the participants' IP addresses), display names, DTMF digits and policy, although no routing rule reads any of them. The extension `sealed-body/1.0` moves those fields into a ciphertext only the addressee can open, and leaves in clear everything a relay routes and tracks by. It protects bodies, not metadata: a relay still learns who talks to whom and when, because `hello` binds every connection to a device (§13.2).

**Sealable fields.** Only these, per type; every other field stays in clear.

| Type | Sealable fields |
|---|---|
| `invite` | `identity`, `intent`, `policy`, `media`, `transports` |
| `answer`, `update` | `answered_by`, `media`, `policy`, `transports` |
| `info` | `about`, `data` |
| `reject`, `cancel`, `bye` | `detail` |

`type`, `id`, `from`, `to`, `session`, `in_reply_to`, `issued_at`, `expires_at`, `dsip`, `reason`, `retry_after`, `status` and `grant` are never sealed: relays route by `to` (§13.3), track attempts and choose among leg rejects by `reason` (§12.7), and enforce the replay window (§12.9).

**Construction.** A sender seals one or more sealable fields (it SHOULD seal all of a message's sealable fields) as `sealed: {alg, enc, ct}`, base64url-encoded:

1. The plaintext is a UTF-8 JSON object holding only sealed fields of that type, obeying §10.3, followed by ASCII spaces (0x20) so that its length is a positive multiple of 256 bytes. JSON permits trailing whitespace, so the padded text parses unchanged; the padding hides how many candidates or codecs an SDP carries.
2. `alg` is `hpke-base-x25519-sha256-aes128gcm`: HPKE (RFC 9180) base mode, DHKEM(X25519, HKDF-SHA256), HKDF-SHA256, AES-128-GCM — the suite of sealed introductions (§19.4; M§14.1).
3. The recipient key is the X25519 key agreement key of the DID in `to` (§7.3): its DID document's `keyAgreement` method (§7.2); else its current verified key agreement delegation (1.x, spec-gap 179); else, for `did:key`, the X25519 key the method derives from its Ed25519 key (M§6.9). `to` names an identity on an `invite` (every device acting for it holds the identity's key agreement key) and may name a device on a response (a device `did:key`, whose key only that device holds). It is resolved under the authority order of §8.1 and is never taken from a hint; a key agreement delegation a hint carries is the subject's own signed credential, verified against the subject whatever carried it, not hint data.
4. HPKE `info` is `dsip sealed body v1`; the AAD is `type ‖ 0x00 ‖ id ‖ 0x00 ‖ from ‖ 0x00 ‖ to` (UTF-8), so a ciphertext cannot be moved into another message.
5. The payload lists `sealed-body/1.0` in both `dsip.extensions` and `dsip.critical`. The envelope is then signed as usual (§10.2): the signature covers the ciphertext, so relays still verify every envelope and apply the replay window.

**Routing.** A relay, mailbox or other service that routes an envelope not addressed to it MUST route a sealed payload whether or not it implements `sealed-body/1.0`: the critical-extension rule of §11.2 binds the addressee. It validates the clear part against the schemas, which admit `sealed` in place of the sealable fields.

**Receiving.** An addressee that implements the extension opens the seal after the version check (§11.2) and before schema validation, rejecting the message on the first failing condition (a payload whose `sealed` is not an object of three strings `alg`, `enc`, `ct`, or whose clear `type`, `id`, `from` or `to` is not a string, is not opened — schema validation rejects it): `sealed` present without `sealed-body/1.0` in `dsip.critical` (a `critical` that is not an array lists nothing); an unknown `alg`; a ciphertext that does not open; a plaintext that is not a §10.3 JSON object with at least one key, or whose length is not a positive multiple of 256; a key outside the type's sealable fields (a type with no sealable fields admits none); a key present both sealed and in clear. The opened fields then join the clear ones, `sealed` is removed, and schema and semantic validation run on the result. An addressee that does not implement the extension rejects the message with `session.unsupported-critical-extension` (§11.3); the sender MAY send a new message in clear if its policy allows.

**Limits.** HPKE base mode to a static key gives no forward secrecy: whoever later obtains the addressee's key agreement key can open captured sealed bodies, so key agreement keys SHOULD be rotated (§7.5). Every device acting for an identity holds that identity's key agreement private key, as for sealed introductions; a message addressed to one device opens only on that device. Relays can no longer screen sealed content; rate limits still apply.

---

## 11. Version and Extension Negotiation

### 11.1 Core Version Fields

Every DSIP payload includes:

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["interactive-media/1.0"],
    "extensions": ["relay-basic/1.0"],
    "critical": []
  }
}
```

### 11.2 Compatibility Rules

- Major versions are incompatible by default.
- Minor versions are backward-compatible unless marked otherwise.
- Unknown non-critical extensions may be ignored.
- Unknown critical extensions require rejection.
- A responder must indicate the selected mutually supported version.
- Downgrade attempts must be detectable because version negotiation is signed.

### 11.3 Version Errors

Version errors are explicit reason tokens in the unified registry (§15):

```
session.unsupported-core-version
session.unsupported-profile-version
session.unsupported-critical-extension
session.version-downgrade-detected
session.unsupported-wire-format
```

### 11.4 Stability of Core 1.0

(v1.0, spec-gap 163) This document is DSIP Core 1.0, the version every payload names in `dsip.core`. A later 1.x
revision keeps every conformant 1.0 implementation conformant: what 1.0 accepts 1.x accepts, what 1.0 rejects 1.x
rejects, and both act the same on the same message. Within that, a 1.x revision MAY:

- add message types: a 1.0 receiver refuses one it does not know as an unknown type (§12.1), and a sender of a new
  type expects that refusal from a 1.0 peer;
- register reason tokens and other registry entries, which a 1.0 receiver handles by the category's fallback (§15,
  §24.2);
- define profiles and extensions (§11.1, §11.2), and clarify text that is ambiguous.

The payload schemas are closed: a 1.0 receiver rejects a field it does not know as a schema failure. A field that a
1.x revision adds to an existing core message is therefore defined by an extension or a profile, and a sender MUST
include it only for a receiver known to support that extension or profile — from the `dsip.profiles` or
`dsip.extensions` of a message the receiver sent, its `hello` capabilities (§13.2), or its DID document. A field
every receiver would have to accept, a changed rule, a removed field or token, or any other change that would make a
1.0 implementation reject what 1.x accepts or accept what 1.x rejects is a new major version, 2.0, negotiated as
§11.2 says. `dsip.core` stays `"1.0"` across 1.x revisions. Errata — text that contradicts itself or the conformance
vectors (`impl/vectors/`) — are corrected in place and listed in Appendix A, each with the spec-gap that decided it.

---

## 12. Core Signaling Messages and Session Lifecycle

### 12.1 Message Set

DSIP Core v1.0 keeps message types minimal.

```
invite       Start an interactive session
progress     Report pre-answer handling status for an invite
answer       Accept an interactive session or an update
reject       Decline an interactive session, update, introduction, or subscription
cancel       Withdraw an invite before answer
update       Modify an established session
info         Carry transport-binding data within an established session (§12.12)
bye          End an established session
introduction Request permission for future contact from an unknown identity (§19.4)
grant        Issue a signed contact grant in response to an introduction (§19.4)
grant-revocation
             Withdraw a grant before its valid_until (§19.4; v0.17)
publish      Publish a signed broadcast/session availability record
subscribe    Subscribe to presence or publication events (§9.3)
notify       Deliver a subscription update (§9.3)
unpublish    Withdraw a publication
provenance   Attach a processor's signed statement to a publication (§22.3)
key-rotation Publish a verification-key change for an identity (§7.5)
delegation-revocation
             Revoke a device delegation before it expires (§7.4)
error        Report protocol/policy failure
```

The DHT Hints Profile (companion document) adds `reachability-hint`, a signed, expiring reachability record that is never authoritative (§8.3, §8.5).

Companion profiles define message types of their own under their profile identifiers — the Messaging Profile's mailbox messages (`deposit`, `accepted`, `sync`, `items`, `key-packages`, `key-package-fetch`, `blob-put`, `mailbox-config`). They are not core messages, and a core-only receiver refuses them as unknown types.

One additional message type, `hello`, exists at the transport-binding scope (§13.2) and is not part of the session message set.

Messages such as transfer, conference moderation, device control, AI orchestration, and emergency priority are profile extensions, not core v1.0.

Without `progress`, a caller cannot render the familiar "ringing" state, violating §5.7's promise to preserve established interaction conventions. Without `cancel`, an invite cannot be withdrawn, which makes multi-device forking and normal call abandonment impossible to implement correctly. Both are therefore core.

### 12.2 Session Identification

The `id` of the `invite` message is the **session identifier** for the resulting session. Every subsequent message that operates on the session (`progress`, `answer`, `reject`, `cancel`, `update`, `bye`, and session-scoped `error`) MUST carry:

```
"session": "<invite id>"
```

The `session` field is covered by the envelope signature. A message whose `session` value does not match a known session MUST be rejected with `session.unknown-session`.

When an invite is forked to multiple devices of the same identity (§7.4), each device constitutes a distinct **leg** of the session attempt, identified by the device DID in the `from` field of messages signed by that device.

### 12.3 Transport Assumption

DSIP Core v1.0 signaling bindings MUST provide **reliable, ordered delivery** of envelopes within a single signaling connection (§13). The state machine below assumes this property and defines no message retransmission or acknowledgment mechanism at the DSIP layer. From the state machine's perspective, a message "arrives" when the endpoint receives and successfully verifies it.

### 12.4 Session State Machine

The initiator (caller) and responder (callee device) each maintain a per-session state machine. States are defined per endpoint; there is no shared network state.

#### Initiator states

| State | Meaning |
|---|---|
| `IDLE` | No session in progress. |
| `INVITING` | Invite sent; no response received. |
| `PROCEEDING` | At least one `progress` received; awaiting answer. |
| `ACTIVE` | Answer accepted; media establishment may proceed. A RENEGOTIATING sub-state exists while an `update` is outstanding (§12.8). |
| `ENDING` | `bye` sent; awaiting local teardown completion. |
| `ENDED` | Terminal. Session state MAY be discarded after the replay window. |

#### Initiator transitions

| Current state | Event | Action | Next state |
|---|---|---|---|
| IDLE | Local: place call | Send `invite` | INVITING |
| INVITING | Recv `progress` | Update UI (ringing, etc.) | PROCEEDING |
| INVITING | Recv `answer` (valid) | Begin media establishment; if the invite was identity-addressed (the answer's `from` ≠ the invite's `to`), send `cancel` (reason `session.answered-elsewhere`) to the invite's `to` (§12.7 rule 3) | ACTIVE |
| INVITING | Recv `reject` | Surface reason | ENDED |
| INVITING | Local: abandon call | Send `cancel` (reason `user.cancelled`) | ENDED |
| INVITING | T-Establish expires | Send `cancel` (reason `session.timeout`); surface failure | ENDED |
| PROCEEDING | Recv `answer` (valid, first) | Begin media; if the invite was identity-addressed, send `cancel` (reason `session.answered-elsewhere`) to the invite's `to` (§12.7 rule 3) | ACTIVE |
| PROCEEDING | Recv `progress` | Update UI; adjust timers per §12.9 | PROCEEDING |
| PROCEEDING | Recv `reject` (attempt outcome, §12.7) | Surface reason | ENDED |
| PROCEEDING | Local: abandon call | Send `cancel` (reason `user.cancelled`) | ENDED |
| PROCEEDING | T-Ring or T-Queue expires | Send `cancel` (reason `session.timeout`) | ENDED |
| INVITING, PROCEEDING | Recv `error` (reason `transport.no-response`) from the relay the invite went through (§12.7 rule 6) | Surface reason; send nothing — the relay has closed every leg | ENDED |
| ACTIVE | Recv `answer` (late, different leg) | Send `bye` (reason `session.already-answered`) to that leg only | ACTIVE |
| ACTIVE | Renegotiation events | Per §12.8 | ACTIVE |
| ACTIVE | Local: hang up | Send `bye` | ENDING → ENDED |
| ACTIVE | Recv `bye` | Tear down media | ENDED |
| ENDED (attempt ended by `reject` or timeout) | Recv `answer` (late) | Send `bye` (reason `session.failed`) to that leg; do not resurrect | ENDED |
| ENDED (the session was ACTIVE and has ended, by either side's `bye`) | Recv `answer` (late, different leg) | Send `bye` (reason `session.already-answered`) to that leg; do not resurrect (§12.7 rule 4; spec-gap 85) | ENDED |
| any | Recv message invalid for state | Send `error` (`session.invalid-state`) | unchanged |

`ENDING` is observable only where teardown is asynchronous; an implementation whose local teardown is synchronous MAY collapse `ENDING` into `ENDED` — no message differs.

#### Responder states

| State | Meaning |
|---|---|
| `IDLE` | No session in progress. |
| `OFFERED` | Valid invite received; trust policy being applied; not yet alerting the user. |
| `ALERTING` | User is being alerted; at least one `progress` sent. |
| `ACTIVE` | Answer sent; media establishment may proceed. |
| `ENDED` | Terminal. |

#### Responder transitions

| Current state | Event | Action | Next state |
|---|---|---|---|
| IDLE | Recv `invite` (valid signature, version, policy) | Apply local trust policy (§19) | OFFERED |
| IDLE | Recv `invite` (invalid) | Send `error` or silently drop per policy | IDLE |
| OFFERED | Policy: alert user | Send `progress` (status `ringing`) | ALERTING |
| OFFERED | Policy: auto-reject | Send `reject` | ENDED |
| OFFERED | Recv `cancel` | Discard; MAY log missed contact per policy | ENDED |
| ALERTING | User accepts | Send `answer` | ACTIVE |
| ALERTING | User declines | Send `reject` (reason `user.declined`) | ENDED |
| ALERTING | Recv `cancel` (reason `user.cancelled` / `session.timeout`) | Stop alerting; surface missed call | ENDED |
| ALERTING | Recv `cancel` (reason `session.answered-elsewhere`) | Stop alerting; do NOT surface missed call | ENDED |
| ALERTING | Local ring timeout | Send `reject` (reason `user.no-answer`) | ENDED |
| ALERTING | Invite `expires_at` passed before alerting began | Send `reject` (reason `session.expired`) | ENDED |
| ACTIVE | Recv `bye` | Tear down media | ENDED |
| ACTIVE | Recv `cancel` (crossed: no initiator message has arrived since our `answer`; any reason but `session.answered-elsewhere`) | Treat as §12.5 rule 2: tear down, no error | ENDED |
| ACTIVE | Recv `cancel` (reason `session.answered-elsewhere`) | This leg is the one that answered (§12.5 rule 2; spec-gap 75): send `error` (`session.invalid-state`); session continues | ACTIVE |
| ACTIVE | Recv `cancel` (late: the initiator has already spoken post-answer — `info`, `update`, an update reply, `bye`) | Send `error` (`session.invalid-state`); session continues | ACTIVE |
| ACTIVE | Local: hang up | Send `bye` | ENDED |
| any | Recv message invalid for state | Send `error` (`session.invalid-state`) | unchanged |

### 12.5 The Cancel/Answer Race

`cancel` and `answer` can cross in flight. Resolution:

1. If the responder receives `cancel` **before** the user answers, the session ends (§12.4).
2. If the responder has already sent `answer` when `cancel` arrives **and no message from the initiator has arrived since that answer**, the cancel crossed the answer: the responder MUST treat the session as ended and tear down any media setup in progress, and MUST NOT treat the crossed `cancel` as an error. One reason is never a crossed withdrawal (spec-gap 75): `session.answered-elsewhere` is what an initiator sends *because* it accepted an answer (§12.7 rule 3), so a responder that has answered and receives it — from a relay that does not track legs, or a direct fan-out — is the leg that answered. It MUST NOT end the session: it answers `error` (`session.invalid-state`) and the session continues. Once the initiator has spoken post-answer (`info`, `update`, an answer or reject to an update, `bye`), a `cancel` is late, not crossed, and is `session.invalid-state` (§12.4). An initiator MUST NOT send `cancel` after accepting an answer, except `session.answered-elsewhere` addressed to the identity per §12.7 rule 3.
3. If the initiator receives an `answer` after having sent `cancel`, the initiator MUST send `bye` with reason `session.cancelled` to that leg. The initiator MUST NOT resurrect the session.

The invariant: **`cancel` is authoritative for the initiator's intent.** A session only becomes ACTIVE at the initiator when the initiator has not cancelled.

### 12.6 Glare

Glare occurs when two endpoints send each other invites for a new session at approximately the same time.

Resolution rule: each endpoint compares the `id` of its outbound invite with the `id` of the inbound invite. Because `id` values are ULIDs and therefore lexicographically time-ordered, **the invite with the lexicographically smaller `id` wins**. Both endpoints apply this rule deterministically:

- The endpoint whose invite lost MUST withdraw its own invite with `cancel` (reason `session.glare`) — the initiator's withdrawal verb — and proceed as responder for the winning invite.
- The endpoint whose invite won MUST answer the inbound losing invite with `reject` (reason `session.glare`) and proceed as initiator. Both legs of the losing invite therefore end deterministically whichever message arrives first.

If the `id` values are equal (pathological), both invites MUST be rejected with reason `session.glare` and either party MAY retry after a random delay of 1–4 seconds.

See §20.6 for the glare-backdating threat model note.

### 12.7 Forking

When an identity has multiple delegated devices, the entity performing delivery (typically the recipient's designated relay per its DID document service endpoint) MAY deliver the same invite to multiple devices. Forking rules:

1. Each device processes the invite independently as a responder leg.
2. The **first `answer` that the initiator accepts** establishes the session. Acceptance means: valid signature by a delegated device key, valid `session` reference, initiator still in INVITING or PROCEEDING state.
3. The initiator cannot observe forking, so the rule is stated in terms it can: upon accepting an answer to an **identity-addressed** invite (the answer's `from` differs from the invite's `to`), the initiator MUST send `cancel` with reason `session.answered-elsewhere` to the invite's `to`; an invite addressed to a device DID directly needs none. A forking relay MUST track which legs it delivered the invite to and which have terminated (answered, rejected, or expired), and MUST deliver the cancel **per-leg** to every leg that has not terminated. A leg is expired when the invite has expired (§12.9) and the leg has sent the relay no `progress`, `answer` or `reject` for the attempt (v0.16, spec-gap 132): a responder acts on an unexpired invite at once, so a leg still silent never processed it; a leg that has spoken is ended by its own `reject` (T-Ring-Local) or by the initiator. A device that binds (§13.2) while an attempt is live becomes a leg of that attempt if the invite is still unexpired. Identity-addressed fan-out without leg tracking is not conformant relay behavior: it risks re-alerting terminated legs, misses legs added mid-attempt, and cannot support targeted cancellation. Leg tracking screens what a terminated leg still sends — a stale `progress`, a second `reject` — but a relay MUST NOT withhold an `answer` from any leg, cancelled, expired or rejected included (spec-gap 86): an answer can cross the cancel, or follow an expiry the device had not seen, and only the initiator can end the leg that sent it (rule 4, §12.5 rule 3, §12.4). The forwarded answer does not change the relay's record of that leg or of the attempt's outcome.
4. Exactly one answer is ever applied per invite. Any subsequent `answer` from another leg MUST be terminated by the initiator with `bye`, reason `session.already-answered`, addressed to that device — also once the session has ended (spec-gap 85): the reason names what the invite was, not how the call finished (`session.cancelled` only when the initiator withdrew it, §12.5 rule 3; `session.failed` only when no answer was ever applied, §12.4). This holds for media too: every leg receives the same media offer and each answers with its own selection (its own SDP answer under the WebRTC binding), but only the accepted leg's selection is applied, so forked media cannot occur (§14.1).
5. `progress` messages from multiple legs are all valid; the initiator treats the session as PROCEEDING if any leg has sent progress.
6. A `reject` ends the session attempt only when all legs have rejected or expired. Because the relay tracks leg state (rule 3), the relay MUST signal attempt completion to the initiator: when the final outstanding leg terminates without an answer, the relay forwards that leg's `reject` as the attempt outcome (choosing the most informative reason if legs differed — `user.declined` over `user.no-answer` over `endpoint.busy` over `endpoint.unavailable`; among tokens outside that order, the first seen). (spec-gap 76) When every leg expired and none rejected, there is no `reject` to forward, and a relay MUST NOT compose one in a leg's name (§15.2): it signals the outcome in its own voice, a relay-signed `error` with reason `transport.no-response` and `session` naming the invite, addressed to the initiator. An initiator in INVITING or PROCEEDING that receives it from the relay its invite went through ends the attempt and sends no `cancel`; a late `answer` is then handled as after any ended attempt (§12.4). In any other state it is an `error` like any other: surfaced, no state change. The initiator's T-Ring/T-Establish remain the backstop if the relay fails to signal.

### 12.8 Renegotiation

`update` renegotiates an established session (media escalation, codec change, adding video, screening escalation per §14.4). Rules:

1. `update` is valid only in ACTIVE state, MUST carry a media offer from its sender, and is answered with `answer` (carrying the selection, referencing the same `session`, and naming the update via `in_reply_to`) or `reject` (likewise via `in_reply_to`). The session remains ACTIVE with prior negotiated parameters until the update's `answer` is applied.
2. While an update is outstanding (sent but not yet answered or rejected), the sub-state is **RENEGOTIATING** for the sender. **Only one update may be outstanding per session, across both directions.**
3. An endpoint receiving an `update` while its own update is outstanding resolves the collision with the glare rule (§12.6): the update with the lexicographically smaller `id` proceeds; the loser is rejected with `session.glare`, and the losing sender re-evaluates whether its change is still needed after the winning update resolves.
4. An endpoint sending a second `update` before its first resolves is a protocol violation; the receiver responds with `error` (`session.update-pending`) and processes neither: both updates are discarded and the session has no outstanding update afterwards. The sender re-offers if it still needs the change.
5. A rejected `update` leaves the session in its prior negotiated state. Rejection of an update MUST NOT terminate the session; ending a session is exclusively `bye`.
6. `bye` and update collision: `bye` always wins. An endpoint MAY send `bye` while an update is outstanding; the receiver processes the `bye` and discards the pending update.

### 12.9 Timers

| Timer | Owner | Default | Bounds | Behavior |
|---|---|---|---|---|
| T-Establish | Initiator | 15 s | 5–60 s | Started on sending `invite`. If neither `progress` nor `answer` arrives, cancel with reason `session.timeout`. Stopped by first `progress` or `answer`. |
| T-Ring | Initiator | 120 s | 30–300 s | Started on first `progress` with status `ringing`. If no `answer`, cancel with reason `session.timeout`. A `ringing` progress carrying `ring_timeout` (re)starts T-Ring at `ring_timeout` clamped to the bounds; a `ringing` without it starts T-Ring only if none is running (repeated `ringing` does not extend). A non-`ringing`, non-`queued` progress (`trying`, `forwarded`) starts T-Ring at its default when neither T-Ring nor T-Queue is running, so PROCEEDING is always bounded. |
| T-Queue | Initiator | per `queue_timeout` | ≤ 1800 s (hard cap) | Started on `progress` status `queued`, replacing T-Ring (§12.10). On expiry, cancel with reason `session.timeout`. Cancelled by a subsequent `ringing` progress; restarted by a subsequent `queued` (bounded re-queues). |
| T-Ring-Local | Responder | 120 s | 30–300 s | Started when alerting begins. On expiry, send `reject` with reason `user.no-answer`. SHOULD be ≤ the advertised `ring_timeout` if one was sent. |
| Invite validity | Both | 30 s | — | The invite's `expires_at` minus `issued_at`. Bounds pre-alerting delivery: an invite received at or after `expires_at` MUST be rejected with reason `session.expired`. Once ALERTING has begun, T-Ring governs, not `expires_at`. |
| Replay window | Both | 300 s | — | Envelopes with `issued_at` outside the window in **either** direction — older than 300 s, or more than 300 s in the future — MUST be rejected. Message `id` values MUST be tracked for deduplication within the window. Exception (v0.8): an `introduction` is held for offline recipients (§19.4), so its age is bounded by its own `expires_at` instead — it is accepted while `issued_at` is no more than 300 s in the future and `now < expires_at`, its `expires_at − issued_at` is capped at 604,800 s, and its `id` is deduplicated until `expires_at`. Exception (v0.8, spec-gap 96): a `reachability-hint` is stored, replicated and read across the DHT for its whole lifetime (§8.5), so its age is likewise bounded by its own `expires_at` — accepted while `issued_at` is no more than 300 s in the future and `now < expires_at`, with `expires_at − issued_at` capped at 3,600 s. Its `id` is not deduplicated: a re-observed hint is resolved by §8.3 (identical content is a no-op, a lower `seq` loses). Exception (v0.17, spec-gap 134): a `presence` record is kept by the authority and forwarded in `notify` bodies for its whole lifetime (Presence Profile P§3), so its age is bounded the same way — accepted while `issued_at` is no more than 300 s in the future and `now < expires_at`, with `expires_at − issued_at` capped at 3,600 s; its `id` is not deduplicated either: its `seq` per `(subject, device)` decides a re-observed record. |

**Expiry (v0.17, spec-gap 141).** Every `expires_at` in this specification and its profiles is the first instant the message is no longer valid: a message is valid while `now < expires_at`, and expired when `now ≥ expires_at`. This holds wherever an `expires_at` is judged: at receipt, for a held or queued message, for a record kept past the replay window, and for the activity or invite it bounds. It holds for every other expiry instant too: a grant's `valid_until` (§19.4), the end of a subscription granted by `expires_in` (§9.3), and a relay's retention bound for a queued message (§13.3).

Design relationship: `expires_at` bounds *delivery*, T-Ring bounds *human answer time*. This keeps invites short-lived on the wire (limiting replay surface) without forcing 30-second ring windows.

### 12.10 `progress`

Sent by a responder leg after a valid invite has passed local trust policy and before `answer` or `reject`. Multiple `progress` messages per leg are permitted. `progress` commits nothing: it carries no media selection and creates no obligation to answer.

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["interactive-media/1.0"],
    "extensions": [],
    "critical": []
  },
  "type": "progress",
  "id": "01J5Y0Q7A1BCD2EF3GH4JK5MN6",
  "session": "01J5Y0Q6K8ZJ4M2N7P9R3S5T7V",
  "from": "did:key:z6MkBobPhoneDevice",
  "to": "did:key:z6MkAlicePhone",
  "status": "ringing",
  "ring_timeout": 120,
  "issued_at": 1760000002,
  "expires_at": 1760000032
}
```

- `status` (required): registered value (registry `dsip-progress-status`): `trying`, `ringing`, `queued`, `forwarded`. Unknown values are treated as `trying`.
- `ring_timeout` (optional): seconds the responder intends to alert before giving up. Only meaningful with status `ringing`.
- `from` MUST be a device key covered by a valid delegation for the invited identity (§7.4). Initiators MUST verify the delegation before treating the progress as authentic.
- `progress` MUST NOT be interpreted as identity confirmation for trust display purposes beyond "a delegated device of the invited identity is reachable."

**Queued timing.** A `progress` with status `queued` MUST include a `queue_timeout` field (seconds). On receiving it, the initiator suspends T-Ring and starts T-Queue at `min(queue_timeout, 1800)` — the 30-minute cap is a core constant. On T-Queue expiry with no further progress, the initiator cancels with reason `session.timeout`. A subsequent `ringing` progress from any leg cancels T-Queue and starts T-Ring normally. A subsequent `queued` restarts T-Queue with the new value (still capped); implementations MUST limit consecutive re-queues (RECOMMENDED: 3) to prevent indefinite parking: a `queued` beyond the limit is treated as T-Queue expiry (`cancel`, reason `session.timeout`). The initiating user can abandon a queued session at any time via `cancel` (reason `user.cancelled`). Richer queue semantics (position updates, estimated wait, callback offers) belong to a future contact-center profile and MUST use an extension namespace; the core defines only the bounded-wait behavior above.

Media establishment during PROCEEDING is excluded by design, not deferred: see the early-media non-goal (§4) and the answer-early/escalate pattern (§14.4). PROCEEDING is a signaling-only state in all profiles.

### 12.11 `cancel`

Sent by the initiator to withdraw an invite before accepting an answer. Also propagated per-leg by forking relays per §12.7.

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["interactive-media/1.0"],
    "extensions": [],
    "critical": []
  },
  "type": "cancel",
  "id": "01J5Y0Q9C6DE7FG8HJ9KM0NP1Q",
  "session": "01J5Y0Q6K8ZJ4M2N7P9R3S5T7V",
  "from": "did:key:z6MkAlicePhone",
  "to": "did:web:example.com:users:bob",
  "reason": "user.cancelled",
  "issued_at": 1760000010,
  "expires_at": 1760000040
}
```

- `reason` (required): registered token (§15). Valid cancel reasons: `user.cancelled`, `session.answered-elsewhere`, `session.timeout`, `session.glare`, `policy.blocked`.
- `to` MAY be the invited identity DID (relay fans out per-leg) or a specific device DID (targeted cancel of one leg).
- A `cancel` MUST be signed by the same identity (or a delegated device of the same identity) that signed the invite. Responders MUST verify this before acting; an unauthenticated cancel is a denial-of-service vector.
- `cancel` is valid only for sessions not yet ACTIVE at the sender. A `cancel` received for an ACTIVE session is answered with `error` (`session.invalid-state`) and ignored. Ending an active session requires `bye`.
- A responder receiving reason `session.answered-elsewhere` MUST NOT present the event as a missed call. All other reasons MAY be surfaced per client policy.

### 12.12 `info`

`info` carries transport-binding data — most importantly trickle ICE candidates — within an established session. It exists because renegotiation and transport chatter are different things: `update` carries the one-outstanding-at-a-time, answer-or-reject semantics of changing *what was negotiated* (§12.8), while ICE candidate exchange fires many small messages rapidly in both directions and changes nothing about the negotiated session.

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["interactive-media/1.0"],
    "extensions": [],
    "critical": []
  },
  "type": "info",
  "id": "01J5Y0QF1CE00AAAAAAAAAAAAC",
  "session": "01J5Y0Q6K8ZJ4M2N7P9R3S5T7V",
  "from": "did:key:z6MkBobPhoneDevice",
  "to": "did:key:z6MkAlicePhone",
  "about": "transport:webrtc",
  "data": {
    "candidates": [
      { "candidate": "candidate:842163049 1 udp 1677729535 203.0.113.7 61481 typ srflx", "sdp_mid": "0", "sdp_m_line_index": 0 }
    ],
    "end_of_candidates": false
  },
  "issued_at": 1760000012,
  "expires_at": 1760000042
}
```

Rules:

- `info` is valid **only in ACTIVE state** (including its RENEGOTIATING sub-state). Because Core v1.0 has no pre-answer media (§14.1), candidates are only ever needed after `answer`, so no earlier state requires it. `info` in any other state is answered with `error` (`session.invalid-state`).
- `about` (required) names the registered transport or extension the data belongs to (registry `dsip-info-about`; initial values are the media transport identifiers, e.g. `transport:webrtc`, and `media:dtmf`). An endpoint receiving `info` with an unrecognized `about` MUST ignore it silently — `info` is never critical.

(spec-gap 70) **`media:dtmf`** carries DTMF within an established session, the events a user presses during a call:

```json
{ "about": "media:dtmf", "data": { "digits": "12#", "duration_ms": 160 } }
```

`digits` is one to 32 RFC 4733 events (`0`–`9`, `*`, `#`, `A`–`D`) in the order pressed; `duration_ms` (40–10,000) is the tone length of each digit in that message and MAY be omitted. Like any `info` it is ACTIVE-only, never critical, expects no reply, and changes nothing about the negotiated session: a receiver that does not act on DTMF ignores it. Ordering is the ordering of the messages themselves (§12.9 deduplicates by `id`); an endpoint MUST NOT reorder digits, and a gateway MUST NOT re-time them.
- `data` (required) is an object whose structure is defined by the binding named in `about`. For `transport:webrtc`, the structure above is normative in the **WebRTC Media Binding 1.0** companion document (`dsip-webrtc-media-binding-v1.0.md`, Appendix A; schema `webrtc-info-data.schema.json`). A receiver validates `data` against the schema of each binding it implements and rejects a malformed `data` as it would any schema failure; for an `about` it does not implement, `data` is not inspected.
- `info` MUST NOT alter negotiated session parameters, elicits no `answer` or `reject`, and causes no state transition. Anything that changes the negotiation is an `update`.
- Because candidates ride in signed envelopes, candidate injection requires a key compromise, not just a network position — this is why unsigned side-channel candidate exchange is prohibited.
- Bindings SHOULD define rate expectations; implementations SHOULD apply per-session `info` rate limits and respond to abuse with `error` (`policy.rate-limited`).

---

## 13. Signaling Transport

### 13.1 Binding Requirements

A DSIP signaling binding is a specification for moving DSIP envelopes between two endpoints, or between an endpoint and a relay. Every conformant signaling binding MUST provide, for the lifetime of a connection:

1. **Reliable delivery** — an envelope accepted by the transport is delivered exactly once or the connection fails detectably.
2. **Ordered delivery** — envelopes sent on one connection arrive in the order sent.
3. **Transport encryption** — confidentiality and integrity at the transport layer, independent of envelope signatures.
4. **Server authentication** — the connecting party can authenticate the endpoint it dialed.

Transport encryption is not a substitute for envelope signatures, and envelope signatures are not a substitute for transport encryption. Signatures establish *who sent* a message regardless of path; transport encryption protects messages *in motion* and reduces metadata exposure to passive observers.

The mandatory-to-implement binding for Core v1.0 is WebSocket Secure (§13.2). A QUIC binding is planned (§13.4). Additional bindings MAY be defined, but an implementation cannot claim Core v1.0 conformance without the WebSocket binding. Bindings over unreliable transports are out of scope for Core v1.0 and MUST define their own reliability layer before claiming conformance.

### 13.2 WebSocket Binding `ws/1.0`

#### Endpoint advertisement

A DSIP endpoint or relay advertises its signaling endpoint in its DID document as a service entry:

```json
{
  "id": "did:web:example.com#dsip-signaling",
  "type": "DSIPSignaling",
  "serviceEndpoint": {
    "uri": "wss://relay.example.com/dsip",
    "bindings": ["ws/1.0"]
  }
}
```

The URI scheme MUST be `wss`. Plaintext `ws` MUST NOT be advertised, offered, or accepted. TLS 1.3 or later is REQUIRED, with server certificate validation against the advertised hostname using Web PKI rules.

#### Connection model

- Connections are always **client-initiated and outbound**. An endpoint behind NAT or firewall dials out to its own relay and to (or via) the peer's advertised endpoint; no inbound port is ever required of an endpoint. This is a deliberate property, not a limitation.
- One connection carries **any number of concurrent sessions**. Implementations MUST NOT require a connection per session.
- The session state machine is independent of connection state. A dropped connection does not, by itself, change any session's state; it suspends delivery.
- A device MAY hold simultaneous connections to **different** relays (multihoming for redundancy); each connection carries its own `hello` and is an independent delivery path. Simultaneous connections from the same device to the **same** relay are undefined behavior in `ws/1.0`: a relay MAY treat a new verified `hello` from an already-bound device as replacing the prior connection and MAY close the old one. (v0.17, spec-gap 158) A relay that replaces a connection MUST send on it, before closing it, a signed `error` with reason `transport.replaced`. A client that receives `transport.replaced` from the relay it is bound to MUST NOT reconnect to that relay by itself: its device is bound there on another connection, which a reconnect would replace in turn, and so on for as long as both run. It SHOULD tell its user, and MAY reconnect when the user asks it to.

#### Framing

- Each WebSocket message carries exactly **one DSIP envelope**, as a text frame containing the UTF-8 JSON envelope (§10.2). No batching, no partial envelopes.
- Maximum envelope size: **64 KiB (65,536 bytes)** — a fixed binding constant of `ws/1.0`, not a negotiable parameter; changing it requires a new binding version. A receiver MUST reject larger envelopes by closing the connection with WebSocket status 1009 or responding with `transport.envelope-too-large`. Profiles carry bulk data outside the signaling binding rather than raising or fragmenting across this cap (the Messaging Profile bounds every MLS value at 24,576 bytes and moves larger payloads to encrypted blobs over HTTPS).
- WebSocket compression extensions (e.g., permessage-deflate) SHOULD NOT be enabled: compressing attacker-influenced plaintext alongside sensitive fields on an encrypted channel creates compression-oracle risk for no meaningful benefit at DSIP message sizes.

#### Connection binding: `hello`

Envelope signatures authenticate messages, but a relay must also know **which device is reachable on which connection** in order to deliver inbound envelopes. The first envelope on any connection MUST therefore be a `hello`:

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": [],
    "extensions": [],
    "critical": []
  },
  "type": "hello",
  "id": "01J5Y0QBD8EF9GH0JK1MN2PQ3R",
  "from": "did:key:z6MkBobPhoneDevice",
  "on_behalf_of": "did:web:example.com:users:bob",
  "bindings": ["ws/1.0"],
  "issued_at": 1760000000,
  "expires_at": 1760000030
}
```

The relay responds with a signed `hello` of its own:

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": [],
    "extensions": [],
    "critical": []
  },
  "type": "hello",
  "id": "01J5Y0QCS4TV5WX6YZ7A8B9C0D",
  "in_reply_to": "01J5Y0QBD8EF9GH0JK1MN2PQ3R",
  "from": "did:web:relay.example.com",
  "capabilities": {
    "max_envelope_bytes": 65536,
    "store_and_forward": true,
    "offline_retention_s": 86400,
    "rate_limit": {
      "envelopes_per_minute": 120,
      "invites_per_minute": 10
    },
    "push_wake": ["apns", "fcm"]
  },
  "issued_at": 1760000001,
  "expires_at": 1760000031
}
```

Rules:

- `hello` is signed by the device key like any envelope. The relay MUST verify the signature and, when `on_behalf_of` is present, verify a valid device delegation (§7.4) before routing any traffic for that identity to this connection.
- The relay's `hello` completes mutual identification at the DSIP layer. TLS authenticated the server *host*; `hello` authenticates the relay *identity*, which may differ from the hostname.
- The relay's `hello` MUST include `in_reply_to` set to the `id` of the client's `hello`, binding the exchange cryptographically. The client MUST verify the match and MUST close the connection on mismatch. This forecloses connection-splicing attacks in which a signed relay `hello` captured from one connection is replayed onto another; TLS channel properties alone are not relied upon for this binding (§20.5).
- The relay's `hello` MUST include a `capabilities` object. `max_envelope_bytes` MUST be present and MUST equal the binding constant. All other fields are OPTIONAL; unknown capability fields MUST be ignored. Capability values are informative for client behavior tuning; enforcement remains server-side, and a relay MAY apply stricter limits per identity or trust tier than the advertised connection-level values.
- A connection with no verified `hello` MUST NOT receive inbound session traffic and SHOULD be closed after a short timeout (RECOMMENDED: 10 seconds).
- `hello` is subject to the standard replay window (§12.9). Re-sending `hello` on an established connection replaces the prior binding (e.g., after key rotation). Binding multiple device DIDs to one connection is NOT supported in v1.0.
- Direct peer-to-peer connections (no relay) follow the same rule: each side sends `hello` before session traffic.

`hello` is a transport-binding message: session-scoped to nothing, carrying no `session` field, and outside the core session message set.

#### Delivery semantics

- Once a `hello` is verified, the relay MUST deliver inbound envelopes addressed to the bound device (or to its identity, subject to forking rules in §12.7) on this connection, preserving arrival order per sender.
- If the addressed device has no live connection, behavior is governed by the relay's store-and-forward policy (§13.3). From this binding's perspective, an envelope handed to the transport on a live connection is delivered or the connection fails.
- (v0.12, spec-gap 113) A `delegation-revocation` record received on a bound connection is not routed: it carries no `to`. The relay verifies it as §7.4 says, holds it, and ends the binding of the device it names; a record it refuses is answered with a signed `error`, an accepted one with nothing.
- (v0.12, spec-gap 114) Nothing a client needs for media (ICE servers, TURN credentials) or for the hints tier (which nodes to ask) comes from the relay's `hello`: capabilities describe the relay's own protocol behaviour. These reach a client from the origin that serves it, or from its own configuration; the WebRTC Media Binding (§4) names the convention for short-lived TURN credentials, and the DHT Hints Profile (§10) says the same of nodes.
- A relay MUST NOT silently drop envelopes on a live connection. If it refuses to route an envelope (policy, rate limit, unknown recipient), it MUST respond with a signed `error` (`transport.routing-refused`, `transport.unknown-recipient`, or `transport.rate-limited`) — **except for `introduction`**, where §19.4 anti-enumeration governs: a relay MUST accept an introduction for any recipient without a routing response, MAY hold it (bounded per recipient inbox) until its `expires_at`, and delivers it on the recipient's next binding. A refused payload whose reason is a registered token of its own (e.g. `policy.subscription-lifetime`, §9.3) is answered with that token rather than the generic routing refusal.

#### Keepalive and reconnection

- Idle connections are kept alive with WebSocket Ping/Pong frames, not DSIP envelopes. RECOMMENDED: client Ping after 30 s of inactivity; either side MAY close after 90 s with no traffic and no Pong. These numbers are connection liveness, not session liveness; session liveness is governed by §12.9 timers and media-layer consent freshness.
- On unexpected connection loss, an endpoint SHOULD reconnect with exponential backoff plus jitter (RECOMMENDED: initial 1 s, factor 2, max 60 s, full jitter), and MUST send a fresh `hello` before anything else. A connection the relay closed after `transport.replaced` was not lost unexpectedly and is not reconnected (Connection model; spec-gap 158).
- Sessions in ACTIVE state survive reconnection: media continues independently, and signaling resumes when the connection returns. Sessions mid-establishment during a prolonged outage resolve via the §12.9 timers; implementations MUST NOT assume the peer observed the outage. The replay window's deduplication protects against duplicates arising from relay retransmission across reconnects.

### 13.3 Offline Delivery Boundary

The WebSocket binding delivers envelopes between *connected* parties. Reaching a device that is offline or asleep — including waking mobile devices via platform push services (APNs, FCM) — is the responsibility of the relay store-and-forward layer.

**Routing is by `to`, with or without an attempt (spec-gap 82).** A relay tracks an attempt from the invite it forked (§12.7), and uses that record for exactly three things: forwarding a leg's pre-answer `progress`/`answer`/`reject` to the initiator (an `answer` from any leg, even one it has cancelled, expired or seen reject — §12.7 rule 3, spec-gap 86), delivering a `cancel` per leg, and signalling the attempt's outcome. Everything else — post-answer traffic, traffic from a device that is not a leg of the attempt, a `cancel` addressed to a device that is not one of its legs, and **all** traffic for a session the relay holds no attempt for (it restarted mid-call; the invite went through another relay) — is routed like any envelope: delivered to the bound device it is addressed to, or to every device bound for the identity it is addressed to; held for a known recipient that is offline (below); and otherwise refused to its sender with `transport.unknown-recipient`, never dropped silently (§13.2). A relay therefore loses no call signaling by restarting.

**Known versus unknown (v0.7).** A recipient identity is *known* to a relay when a device has completed a verified `hello` for it at that relay within the relay's retention window; store-and-forward applies only to known identities. An envelope for a known-but-offline device is held until the earlier of its `expires_at` and the relay's `offline_retention_s` (advertised in the `hello` capabilities; RECOMMENDED default 86,400 s) and flushed in order on the device's next binding; a held `invite` becomes a tracked leg when flushed, and an initiator `cancel` that arrives first simply drops it. Expiry of a held envelope is **not** signalled — the initiator's §12.9 timers are the backstop. Identities never seen at this relay get `transport.unknown-recipient` (§13.2), introductions excepted.

**What a relay forgets (v0.16, spec-gap 131).** The retention window runs from the end of the recipient's last binding: an identity or device is known while a device is bound for it, for `offline_retention_s` after its last binding ended, and while the relay holds an envelope for it; after that it is never seen at this relay until a device binds for it again. A relay MAY discard an attempt (§12.7) once more than the T-Queue cap (1,800 s, §12.10) has passed since it forked the invite, added a leg, or received an attempt-scoped message for it from a leg or the initiator: every pre-answer wait ends within that of the last `progress`. Traffic for the session is then routed as for a session the relay holds no attempt for (above).

**Bounded store (v0.8, spec-gap 99).** A relay holds store-and-forward envelopes within bounds it chooses: per recipient, and in total across recipients. An envelope that would exceed a bound is refused with a signed `error` (`transport.routing-refused`), never dropped silently (§13.2) — except an `introduction`, which is dropped silently at either bound so that a full relay is indistinguishable from an ignoring recipient (§19.4). A `cancel` for an `invite` still held for its recipient only shrinks the store (§12.11) and is never refused for either bound.

The honest statement, in the spirit of §8.4: mobile wake-up on today's platforms requires platform push services, which are centralized. A DSIP relay that uses push to wake a device reintroduces a platform dependency for *delivery latency*, not for *identity or trust* — the envelope that eventually flows is still signed end-to-end, and the push payload need carry nothing but a wake signal. That trade is stated, not hidden. The Wake Profile (draft, `dsip-wake-profile-v1.0-draft.md`, cited `W§n`) defines how a device asks its relay and its mailbox to wake it through a push gateway, who may, and what a wake carries.

### 13.4 QUIC Binding (Planned)

A QUIC-based binding (`quic/1.0`, likely via WebTransport or raw QUIC streams) is planned as the second signaling binding. It MUST satisfy the same four requirements in §13.1 — QUIC streams are reliable, ordered, and encrypted — so the session state machine and all message semantics carry over unchanged.

Expected benefits over WebSocket: faster connection establishment (0-RTT resumption), no TCP head-of-line blocking across multiplexed sessions, and **connection migration** — a device moving from Wi-Fi to cellular can retain its signaling connection without re-dialing and re-`hello`ing, directly valuable for a calling protocol.

The QUIC binding is not required for Core v1.0 conformance and MUST NOT be the only binding an endpoint offers while `ws/1.0` remains the mandatory baseline.

### 13.5 Constrained Devices

A future constrained-device profile (paired with DSIP-COSE, §10.1) MAY define a binding suited to CoAP/UDP-class environments, including its own reliability layer. Such a binding is a profile concern and does not alter the Core v1.0 requirement set.


### 13.6 Relay Service Scope (v0.8, spec-gap 100)

A relay *serves* an identity when it is that identity's designated relay: it holds store-and-forward envelopes for it (§13.3), forks invites to its devices (§12.7), and acts as its presence and broadcast authority (§9.3, §22). Discovery reaches a relay through the DID documents that name it (§8.1); no relay is required to carry traffic for identities that do not.

- An **open** relay serves every identity whose device completes a verified `hello`.
- A **private** relay serves a set of identities chosen by its operator. It MUST still accept a verified `hello` from any device, so that outside parties can reach the identities it serves, but it routes only envelopes to or from a served identity, holds envelopes only for served identities, and accepts `publish`, `unpublish` and `provenance` only from them and `subscribe` only for a served target. It refuses anything else with a signed `error` (`transport.routing-refused`, §13.2); an `introduction` it does not route is dropped silently (§19.4).
- A relay MAY additionally refuse `hello` from devices of identities it does not serve. Such a *closed* deployment is conformant, but its identities cannot be reached from outside it.

Serving is a relay's own policy: no relay is obliged to serve, forward for, or federate with any other party, and nothing in DSIP grants a relay authority over an identity it serves (§8.1 — the DID document remains the authority).
---

## 14. Answer Semantics and Media Timing

### 14.1 What `answer` Means

`answer` means: **a verified, delegated endpoint of the invited identity commits to establishing the negotiated media session.**

`answer` does NOT mean a human accepted the call. A voicemail service, an IVR, a screening agent, and a gateway all answer sessions. The caller's client distinguishes these cases through the `answered_by` field, not by listening to the audio and guessing — which is what PSTN callers have done for fifty years.

The core security invariant:

> **No media without a signed answer.** Media establishment begins only when the initiator transitions to ACTIVE, which requires a valid `answer` signed by a delegated device key of the invited identity. The PROCEEDING state carries no media path. There are no exceptions in Core v1.0, and profiles MUST NOT weaken this invariant.

This makes the forked-media problem structurally impossible (only the accepted leg ever has a media path), makes key establishment unambiguous (media keys are negotiated in exactly one place), and gives security reviewers a one-sentence property to verify.

### 14.2 Offer/Answer Direction

Core v1.0 defines exactly one negotiation pattern:

- An `invite` MUST contain a media offer (§16).
- An `answer` MUST contain the selection from that offer, and exactly one selected transport binding — an answer is a selection, not a second offer. *Subset* is defined per field: each selected media descriptor matches an offered one on `type` and `purpose`; its `codecs[].id` are a subset of the offered codec ids; its `direction` is a valid answer to the offered direction (offered `sendrecv` → any; `sendonly` → `recvonly`/`inactive`; `recvonly` → `sendonly`/`inactive`; `inactive` → `inactive`); and the selected transport `id` was offered. A selection that is not a subset is rejected.
- An `invite` without a media offer MUST be rejected with reason `media.offer-required`.

There is no offerless invite and no answer-side counter-offer. Renegotiation after establishment uses `update`, which likewise always carries an offer from its sender. Third-party call control patterns that cannot know media parameters at invite time are an orchestration concern for a future gateway/3PCC profile and MUST NOT be accommodated by weakening the core pattern.

### 14.3 The `answered_by` Field

`answer` carries a required `answered_by` field. Registered values (registry `dsip-answered-by`):

```
user        A human accepted at this endpoint
service     An automated service answered (voicemail, IVR, assistant, announcement playback)
screening   The session is answered in screening mode; full acceptance has not occurred
gateway     A protocol gateway answered on behalf of a party beyond the DSIP trust boundary
```

- Clients MUST render `service`, `screening`, and `gateway` answers distinguishably from `user` answers. "Voicemail answered" and "Bob answered" are different events and MUST NOT be displayed identically.
- `answered_by` is a claim by the answering endpoint. Like display names (§18.2), it is authenticated as *coming from a delegated endpoint of the invited identity* but is not independently verified beyond that. The trust basis is the identity, per §5.4.
- Unknown `answered_by` values MUST be treated as `service` (the conservative rendering).
- An AI agent answering on behalf of an identity uses `service` together with the AI disclosure mechanisms of §18.4; `answered_by` is not the AI disclosure channel.

### 14.4 Screening Pattern

Call screening — previewing or interrogating a caller before a human commits — is performed **inside** the session, not before it:

1. The callee endpoint sends `answer` with `answered_by: "screening"` and a constrained media selection (typically `recvonly` audio, or the subset the screening policy requires).
2. The caller's client MUST indicate screening mode to the caller. The caller is aware they are being screened; there is no covert path.
3. If the human accepts, the callee endpoint sends `update` escalating media (e.g., to `sendrecv` audio/video) and MAY include `answered_by: "user"` in the update to signal the transition.
4. If the human declines, the callee sends `bye` with an appropriate reason (e.g., `user.declined`).

This pattern requires no new states, no pre-answer media path, and no exception to the §14.1 invariant. Doorbell preview, assistant-mediated screening, and enterprise intake flows are all expressible with it.

---

## 15. Reason Codes

### 15.1 Design

Several message types carry a `reason` communicating *why* something happened: `reject`, `cancel`, `bye`, and `error`, and a terminal `notify` (§9.3; spec-gap 73). DSIP defines a single unified reason framework.

**Reasons are namespaced string tokens, not bare numerics.**

SIP inherited numeric response codes (and Q.850 cause values) from an era of constrained parsers and telephony signaling. Applying §5.7: numerics forced every implementer to keep a lookup table in their head, collapsed distinct conditions into overloaded codes, and coupled DSIP-independent semantics to telephony history. Self-describing tokens in JSON cost a few bytes and eliminate an entire class of misuse. What numerics *did* provide — family-based fallback, where an unknown 4xx could be treated as a generic client error — is preserved through namespaces.

Token grammar:

```
reason-token = category "." condition
category     = "user" / "endpoint" / "identity" / "session" /
               "media" / "policy" / "transport" / "gateway" /
               "mailbox" / "presence"
```

**Fallback rule:** an implementation receiving an unregistered token MUST fall back to the defined behavior of its category (§15.3). An implementation receiving an unrecognized *category* MUST treat the reason as `session.failed`.

### 15.2 Wire Structure

```json
{
  "type": "reject",
  "session": "01J5Y0Q6K8ZJ4M2N7P9R3S5T7V",
  "reason": "identity.not-in-service",
  "detail": "This address was closed by its owner on 2026-06-01",
  "retry_after": 0
}
```

- `reason` (required on `reject`, `cancel`, `bye`; required within `error`): a registered token.
- `detail` (optional): free-text elaboration, or an object whose shape the profile registering the reason token defines (the Gateway Profile's `gateway.downgraded` carries `{"losses": [...]}`, G§7; spec-gap 112). Clients MAY display it but MUST attribute it to the signing identity and MUST NOT render it in a way that implies independent verification — `detail` is a claim, exactly like display names (§18.2). Relays and gateways MUST NOT inject `detail` into envelopes they did not sign.
- `retry_after` (optional, seconds): a hint that retrying may succeed after the interval. `0` means retrying will not help. Absence means no guidance.

### 15.3 Categories

| Category | Meaning | Default fallback behavior for unknown condition |
|---|---|---|
| `user` | A human made a decision | Terminal for this attempt; retrying soon is socially inappropriate, not just technically futile. Clients SHOULD NOT auto-retry. |
| `endpoint` | Device/endpoint state prevented the session | MAY retry after a delay; other legs or devices may succeed |
| `identity` | Condition concerns the identity itself (existence, standing, reachability as an identity) | Terminal; do not retry without new information. Update local contact state if applicable. |
| `session` | Protocol-level session lifecycle condition | Behavior defined per state machine (§12); generally terminal for the attempt |
| `media` | Media negotiation could not complete | Retry only with a changed offer |
| `policy` | A policy engine (local, organizational, relay) blocked the action | Retry only after satisfying the stated requirement, if any |
| `transport` | Transport binding condition (§13) | Reconnect/retry per binding rules |
| `gateway` | Condition arose beyond a protocol gateway | Treat per mapped semantics; trust per Appendix C downgrade rules |
| `mailbox` | A mailbox or hub condition (Messaging Profile; v0.8) | Re-sync, retry once, then surface the failure |
| `presence` | A presence record refused by its authority (Presence Profile P§9; v0.17) | Do not send the same record again; publish a corrected one |
| `wake` | A wake registration or a wake refused (Wake Profile W§8.1; 1.0, A.16) | End the registration; register again on the next binding |

### 15.4 Core Registry

Registry: `dsip-reason`. Columns: token — meaning — valid on.

The "valid on" column governs the four session message types, `reject`, `cancel`, `bye` and `error`. It does not govern a terminal `notify` (§9.3; spec-gap 73): there the `reason` says why a subscription ended, not why a session did, and any registered token is valid — `session.expired` for a lapsed subscription and `policy.terminated` for a revoked authorization are the usual two. An unregistered token on a `notify` falls back by category like any other (§15.3).

**user.**

| Token | Meaning | Valid on |
|---|---|---|
| `user.declined` | Human declined the session | reject, bye |
| `user.no-answer` | Alerting ended without human response | reject |
| `user.hangup` | Normal termination by a participant | bye |
| `user.cancelled` | Initiating human abandoned the attempt | cancel |
| `user.blocked` | Recipient has blocked this identity; disclosure of this token is a client policy choice — clients MAY send `user.declined` instead | reject |

**endpoint.**

| Token | Meaning | Valid on |
|---|---|---|
| `endpoint.busy` | Endpoint unwilling to alert due to an existing session | reject |
| `endpoint.unavailable` | Endpoint temporarily cannot handle sessions (DND, resource limits) | reject |
| `endpoint.capability` | Endpoint cannot satisfy a required capability of the invite | reject |

**identity.**

| Token | Meaning | Valid on |
|---|---|---|
| `identity.not-in-service` | The identity/address is permanently no longer in service — the "number disconnected" analog. Sent by the identity's relay or domain authority. | reject, error |
| `identity.moved` | Identity has moved; a successor identifier MAY be present in `detail` or a signed redirection credential (future extension for the signed form) | reject |
| `identity.suspended` | Identity temporarily suspended by its domain/organization | reject |
| `identity.unknown` | No such identity at this authority | reject, error |

**session.**

| Token | Meaning | Valid on |
|---|---|---|
| `session.expired` | Invite received or processed after `expires_at` | reject |
| `session.timeout` | T-Establish, T-Ring, or T-Queue expired; on `bye`, a timer of the far network reported by a gateway mid-call (spec-gap 78) | cancel, bye |
| `session.glare` | Deterministic glare resolution (§12.6, §12.8) | reject, cancel |
| `session.answered-elsewhere` | Another leg answered — MUST NOT surface as missed call | cancel |
| `session.already-answered` | Late answer to an established session | bye |
| `session.cancelled` | Teardown of a leg whose answer crossed a cancel (§12.5) | bye |
| `session.invalid-state` | Message type not valid in current session state | error |
| `session.unknown-session` | `session` field does not reference a known session | error |
| `session.update-pending` | A second update was received while one is outstanding (§12.8) | error |
| `session.unsupported-core-version` | No mutually supported core version | reject, error |
| `session.unsupported-profile-version` | No mutually supported profile version | reject, error |
| `session.unsupported-critical-extension` | A critical extension is not supported | reject, error |
| `session.version-downgrade-detected` | Signed version negotiation indicates downgrade attempt | error |
| `session.unsupported-wire-format` | Wire format not supported | error |
| `session.failed` | Unspecified session failure; also the fallback for unrecognized categories | reject, bye, error |

**media.**

| Token | Meaning | Valid on |
|---|---|---|
| `media.unsupported` | No mutually acceptable codec/transport in the offer; on `bye`, the call ends because none is left (spec-gap 78) | reject, bye |
| `media.offer-required` | Invite or update carried no media offer (§14.2) | reject |
| `media.encryption-required` | Offer did not satisfy the receiver's encryption floor | reject |
| `media.failed` | Established media path failed and could not be recovered | bye |

**policy.**

| Token | Meaning | Valid on |
|---|---|---|
| `policy.trust-insufficient` | Sender's trust tier/verification basis below receiver's threshold (§19.1) | reject |
| `policy.first-contact-required` | Unknown identity must complete the first-contact mechanism (§19.4) before inviting | reject |
| `policy.blocked` | Organizational or relay policy refused the session | reject, cancel |
| `policy.terminated` | Session terminated by policy authority (e.g., organizational compliance) | bye |
| `policy.recording-declined` | A party declined to be recorded (Recording Profile C§4, draft) | reject, bye |
| `policy.rate-limited` | Sender exceeded a policy rate limit; `retry_after` SHOULD be present | reject, error |
| `policy.subscription-lifetime` | `subscribe.expires_in` exceeds the per-event cap (§9.3); the cap SHOULD appear in `detail` | error |

**transport.**

| Token | Meaning | Valid on |
|---|---|---|
| `transport.envelope-too-large` | Envelope exceeds binding size limit | error |
| `transport.hello-required` | Session traffic received before verified `hello` | error |
| `transport.hello-rejected` | `hello` signature, delegation, or replay check failed | error |
| `transport.routing-refused` | Relay declines to route this envelope (policy) | error |
| `transport.unknown-recipient` | Relay has no route for the addressed identity/device | error |
| `transport.rate-limited` | Sender exceeded relay rate policy | error |
| `transport.no-response` | Every leg of a forked invite expired without any response; sent by the forking relay as the attempt outcome (§12.7 rule 6; spec-gap 76) | error |
| `transport.replaced` | The device bound to this relay again on another connection, which replaced this one; sent by the relay on the replaced connection before closing it (§13.2; spec-gap 158). Unlike the category default, the client does not reconnect | error |

**gateway.**

| Token | Meaning | Valid on |
|---|---|---|
| `gateway.unreachable` | The far side beyond the gateway could not be reached, or was lost mid-call (`bye`; spec-gap 78) | reject, bye, error |
| `gateway.downgraded` | Session proceeded but trust semantics were downgraded crossing the gateway (informational) | error |
| `gateway.mapped` | Condition mapped from a foreign protocol; original code SHOULD appear in `detail` | reject, bye, error |

**mailbox.** (v0.8; defined by the Messaging Profile, M§16)

| Token | Meaning | Valid on |
|---|---|---|
| `mailbox.commit-conflict` | A commit for this epoch was already accepted; sync and re-propose | error |
| `mailbox.stale-epoch` | Traffic for an epoch older than the hub accepts | error |
| `mailbox.unknown-group` | The hub does not host this group, or the mailbox has no registration for it | error |
| `mailbox.cursor-invalid` | The `sync` cursor is unknown or expired; re-sync from `null` | error |
| `mailbox.object-too-large` | A value exceeds the profile's size bound, or a blob exceeds `max_blob_bytes` | error |
| `mailbox.quota-exceeded` | The owner's quota is exhausted; `retry_after` MAY be present | error |
| `mailbox.no-key-packages` | No KeyPackage or last resort is available for the target | error |
| `mailbox.unsupported-class` | Unknown deposit class, or one the receiver refuses | error |
| `mailbox.unsupported-mode` | Unregistered mailbox mode; nothing is changed | error |
| `mailbox.blob-mismatch` | An uploaded blob's length or SHA-256 differs from its authorization | error |

### 15.5 PSTN/SIP Mapping (for the Gateway Profile)

A DSIP–SIP gateway MUST map foreign codes to DSIP reasons rather than tunneling numerics to clients. Informative initial mapping; the normative tables, in both directions, are the Gateway Profile's, which also keeps the DSIP reason visible on the SIP side as `Reason: DSIP;text=`:

| Inbound (SIP / Q.850) | DSIP reason |
|---|---|
| SIP 486 Busy Here / Q.850 17 | `endpoint.busy` |
| SIP 480 Temporarily Unavailable / Q.850 18–20 | `endpoint.unavailable` |
| SIP 603 Decline | `user.declined` |
| SIP 404 Not Found / Q.850 1 (unallocated number) | `identity.unknown` |
| SIP 410 Gone / Q.850 22 (number changed) | `identity.not-in-service` or `identity.moved` per available data |
| SIP 484 Address Incomplete / Q.850 28 | `identity.unknown` |
| SIP 488 Not Acceptable Here | `media.unsupported` |
| SIP 503 Service Unavailable / Q.850 34, 38, 41–44 | `gateway.unreachable` |
| SIP 487 Request Terminated | `session.cancelled` |
| Unmappable / other | `gateway.mapped` with original code in `detail` |

PSTN in-band announcements ("the number you have dialed…") SHOULD be mapped by the gateway to the corresponding reason token when the gateway can classify them; when it cannot, the gateway answers the DSIP leg (`answered_by: "gateway"`) and passes the audio through — free, because DSIP answer carries no billing semantics.

### 15.6 Registry Policy

- Tokens are registered in `dsip-reason` with: token, meaning, valid message types, fallback category confirmation.
- New conditions SHOULD be registered rather than expressed through `detail`. `detail` never substitutes for a token.
- Extensions MAY define tokens in their own namespace using the extension identifier as category prefix (e.g., `x-contactcenter.queue-full`); receivers apply the unrecognized-category fallback unless they support the extension.
- Tokens are never removed; obsolete tokens are marked deprecated with a replacement pointer.
- The "valid on" column is guidance for senders. A receiver that gets a registered token on a message type the registry does not list for it MUST NOT reject on that ground; it applies the token's meaning and MAY log the mismatch.

---

## 16. Media Negotiation

### 16.1 Goals

DSIP media negotiation allows endpoints to agree on:

- Media type
- Codec
- Codec parameters
- Transport
- Encryption mode
- Relay mode
- Latency target
- Bandwidth constraints
- Accessibility streams
- Recording/transcription/AI processing policy

### 16.2 Registry-Based Codec Identifiers

Codec identifiers live in a registry, not as hardcoded spec text. The spec includes examples using Opus, H.264, AV1, AAC, and other codecs, but the normative identifiers are registered and versioned.

**Codec entries are objects**, never bare strings: a registered `id` plus codec-specific parameters. (This resolves an inconsistency in v0.5 between §14.2 and §15.3; the object form is normative and the JSON Schemas enforce it.)

```json
{
  "media": [
    {
      "type": "audio",
      "direction": "sendrecv",
      "codecs": [
        {
          "id": "codec:audio/opus",
          "sample_rates": [48000],
          "channels": [1, 2],
          "packetization_ms": [20]
        },
        {
          "id": "codec:audio/pcmu",
          "sample_rates": [8000],
          "channels": [1]
        }
      ]
    },
    {
      "type": "video",
      "direction": "sendrecv",
      "codecs": [
        {
          "id": "codec:video/h264",
          "profiles": ["baseline", "main"],
          "resolutions": ["720p", "1080p"],
          "framerates": [30]
        }
      ]
    }
  ]
}
```

### 16.3 Relationship to SDP

DSIP supports SDP interop but is not limited to SDP.

- DSIP-native negotiation uses structured JSON media descriptors.
- SIP/WebRTC gateways may include SDP as a transport binding object.
- If both structured media and SDP are present, the binding must define which one is authoritative.

SDP rides on the transport descriptor itself: the descriptor in `transports[]` keeps its registered `id` and carries the binding's `sdp` (an offer on `invite`/`update`, an answer on `answer`):

```json
{
  "transports": [
    { "id": "transport:webrtc", "ice": "trickle", "sdp": "v=0\r\no=- 4611731400430051336 2 IN IP4 127.0.0.1\r\n..." }
  ]
}
```

Authority between the two is fixed: the structured `media` descriptors are authoritative for **what was negotiated** (media, direction, purpose, selected codec ids, policy — what the state machine and UI act on); the SDP is authoritative for **transport parameters** (ICE credentials and candidates, DTLS fingerprint and role, payload types, BUNDLE/rtcp-mux). The two MUST be consistent and an inconsistency is rejected (`media.unsupported`). The WebRTC Media Binding 1.0 companion document defines the descriptor, the consistency rules, role and DTLS mapping, and renegotiation.

The WebRTC media binding must also define ICE candidate exchange. Trickle ICE requires signaling round trips after answer; candidates ride inside signed session-scoped `info` envelopes (§12.12) with `about: "transport:webrtc"` — unsigned candidate exchange is an injection vector, and `update` is the wrong vehicle because candidate exchange is high-frequency transport chatter, not renegotiation.

### 16.4 Media Policy

Policy is negotiated alongside media.

```json
{
  "policy": {
    "recording": "consent-required",
    "transcription": "allowed-with-notice",
    "ai_processing": "denied",
    "redistribution": "forbidden",
    "relay": "authorized-only"
  }
}
```

Policy statements do not magically enforce behavior. They provide signed declarations that clients, gateways, relays, and applications can enforce or display.

`policy.recording` states what a party accepts **from the other side**: `allowed`, `consent-required` (the default) or `forbidden`. That a party **is** recording is a different statement, its signed `recording` declaration. The Recording Profile (draft) defines it, with what a counterparty's client must render and when it must ask for acceptance (C§3–C§4).

---

## 17. Interactive Media Profile v1.0

The Interactive Media Profile supports real-time two-way media between two or more endpoints.

### 17.1 Required Capabilities

A conformant implementation MUST support:

- DID or DID-compatible identity, with device delegation verification (§7.4)
- Signed `invite`/`progress`/`answer`/`reject`/`cancel`/`update`/`bye`/`error`
- The initiator and responder state machines (§12.4), including the cancel/answer race rules (§12.5), glare resolution (§12.6), and renegotiation rules (§12.8) with the one-outstanding-update constraint
- The `session` field on all session-scoped messages
- `progress` send (at minimum status `ringing`) and receive (all registered statuses, unknown treated as `trying`), including T-Queue behavior for status `queued`
- `cancel` send and receive with all registered reasons; correct handling of `session.answered-elsewhere` (never a missed call)
- A media offer in every `invite`, rejecting offerless invites with `media.offer-required`
- `answered_by` on every answer, rendering non-`user` answers distinguishably; unknown values render as `service`
- The screening pattern (§14.4): screening answer, escalation update, and screening-mode indication to the caller
- Registered reason tokens with category fallback (§15)
- `info` receive for the implemented media transport binding, ignoring unrecognized `about` values silently; `info` send as required by that binding's candidate exchange (§12.12)
- The `introduction`/`grant` first-contact exchange (§19.4): send and receive introductions, issue and honor grants, enforce the 4,096-byte introduction cap, and render introductions outside the call surface
- `subscribe`/`notify` per §9.3 is OPTIONAL for interactive endpoints (presence is not required for calling, §9.1) but REQUIRED for any implementation advertising presence and for Verified Broadcast subscription flows; the anti-enumeration response rule is REQUIRED wherever subscription is implemented
- Version negotiation
- At least one audio codec
- The `ws/1.0` signaling binding as client, including `hello`, `in_reply_to` verification, the 64 KiB cap, and reconnection with backoff (§13.2)
- At least one media transport binding
- Media policy declaration
- Replay window and invite validity enforcement (§12.9)
- The no-media-without-signed-answer invariant (§14.1); implementations claiming conformance MUST document how they enforce it

Relay conformance additionally requires: verified-`hello` gating of inbound delivery, ordered per-sender delivery, per-leg state tracking with per-leg cancel delivery and attempt-completion signaling (§12.7), signed `error` responses for refused routing, and Ping/Pong liveness.

### 17.2 Recommended Transport Binding

The first implementation defines one recommended media transport binding for interoperability:

- WebRTC binding for browsers and modern applications — `transport:webrtc` 1.0, the companion document `dsip-webrtc-media-binding-v1.0.md`
- RTP/SRTP binding for SIP and telecom gateways — `transport:rtp`, the companion draft `dsip-rtp-srtp-media-binding-v1.0-draft.md`, used by the Gateway Profile

The spec may define both, but v1.0 interoperability does not require every endpoint to support every binding. The v1.0 encryption floor: transport-encrypted media (DTLS-SRTP for the WebRTC binding) is REQUIRED; E2EE through SFUs via SFrame is a reserved future extension (§6.2).

### 17.3 Example Invite Payload

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["interactive-media/1.0"],
    "extensions": [],
    "critical": []
  },
  "type": "invite",
  "id": "01J5Y0Q6K8ZJ4M2N7P9R3S5T7V",
  "from": "did:key:z6MkAlicePhone",
  "to": "did:web:example.com:users:bob",
  "issued_at": 1760000000,
  "expires_at": 1760000030,
  "intent": "interactive",
  "identity": {
    "display_name": "Alice",
    "claims": []
  },
  "media": [
    {
      "type": "audio",
      "direction": "sendrecv",
      "codecs": [
        { "id": "codec:audio/opus", "sample_rates": [48000], "channels": [1, 2] },
        { "id": "codec:audio/pcmu", "sample_rates": [8000], "channels": [1] }
      ]
    },
    {
      "type": "video",
      "direction": "sendrecv",
      "codecs": [
        { "id": "codec:video/h264", "profiles": ["baseline"] }
      ]
    }
  ],
  "transports": [
    {
      "id": "transport:webrtc",
      "ice": "trickle"
    }
  ],
  "policy": {
    "recording": "consent-required",
    "ai_processing": "denied"
  }
}
```

(Message `id` values in examples are valid ULIDs; the JSON Schemas reject the illustrative short ids used in earlier drafts.)

### 17.4 Small-Group Session Model

Small-group sessions in v1.0 use a **star topology through a group focus**:

- A group focus (an SFU or conference service) is itself a DSIP endpoint with a `service`-class identity (§7.1) and its own DID, delegations, and signaling endpoint.
- Each participant establishes an **ordinary 1:1 DSIP session with the focus**, using the standard state machine, invite/answer negotiation, and policy declaration. Joining a group is inviting the focus (or being invited by it for dial-out); leaving is `bye`.
- A group call is therefore **N sessions, not one N-party session**. No group-specific message types, states, or negotiation semantics exist in Core v1.0.

Consequences stated honestly:

- The focus terminates media and signaling trust: participants verify the focus's identity, and the focus verifies each participant's. Participant-to-participant identity assertions are relayed claims by the focus unless a future extension adds end-to-end participant attestation.
- Membership visibility, roster events, moderation, and mute/kick controls are focus policy and future extension territory (`group-roster/1.0`, reserved), not core protocol.
- Group E2EE key management (MLS) and E2EE media through the focus (SFrame) are reserved extensions per §6.2; in v1.0, group media is transport-encrypted to the focus.

This model keeps small-group in scope without new protocol machinery, and nothing in it forecloses richer group semantics later.

---

## 18. Rich Session Identity

Rich Caller ID evolves into **Rich Session Identity**. This must be designed carefully because identity UI can become a phishing vector.

### 18.1 No Generic Verified Badge

Clients avoid generic "verified" badges. Instead, display the basis of verification:

```
Self-issued identity
Domain verified by did:web
Organization credential issued by Example Trust Registry
Broadcast credential issued by State Media Registry
Gateway attested by Example Carrier
```

A PSTN caller has no DID; a gateway carries its number as a `tel` claim (a registered claim type; Gateway Profile), which clients render with its attestation level and the gateway that asserts it — never as a verified identity of the caller.

### 18.2 Logo and Brand Claims

Logos, avatars, brand names, and display names are claims, not truth.

A logo is shown as verified only if:

- It is included in a signed credential or trusted metadata source.
- The issuer is trusted for brand/logo claims.
- The credential status has been checked.
- The client can explain the trust basis to the user.

### 18.3 Revocation

Credential revocation must be real-time enough for session establishment. At minimum, clients support:

- Credential expiration
- Status checks
- Revocation lists or status endpoints
- Cached status with short maximum age for high-risk claims
- Hard failure for revoked high-trust credentials

### 18.4 AI Disclosure

DSIP can include an AI disclosure field, but that field is not self-enforcing. A malicious operator can omit it.

Therefore, AI disclosure is a policy and credential problem:

- AI agent credentials may require disclosure claims.
- Clients may label endpoints as "AI-disclosed" only when backed by a trusted credential.
- Organizations may require agent credentials for inbound/outbound AI sessions.
- Regulations may impose penalties for false disclosure.

Protocol fields help honest actors interoperate. They do not force dishonest actors to comply. Note that `answered_by: "service"` (§14.3) identifies automated answering but is not the AI disclosure channel; disclosure rides on credentials.

---

## 19. Abuse, Spam, and Sybil Resistance

Spam and abuse are among the hardest DSIP problems. A system where anyone can mint unlimited `did:key` identities creates trivial Sybil attacks. At the same time, requiring strong credentials for everyone undermines open participation. DSIP acknowledges this tension directly.

### 19.1 Trust Tiers

DSIP supports trust tiers rather than one universal trust model.

```
Tier 0: Anonymous / ephemeral
Tier 1: Self-issued persistent identity
Tier 2: Relationship-gated identity
Tier 3: Domain-bound identity
Tier 4: Credential-backed identity
Tier 5: Regulated or high-assurance identity
```

Clients and services decide which tiers are allowed for which actions:

- Anonymous calls may be blocked by default.
- Self-issued identities may require prior contact approval.
- Domain-bound identities may reach public business endpoints.
- Credential-backed identities may bypass spam screening.
- An identity with a verified phone-number binding (Number Attestation Profile, draft) counts as domain-bound by default: a number proves control of a rented resource, as a domain does, and never by itself bypasses screening (spec-gap 110, item D).
- Regulated identities may access emergency or public-sector profiles.

### 19.2 Abuse Controls

DSIP defines hooks for abuse control, not one global algorithm:

- Contact allowlists
- First-contact consent prompts
- Proof-of-work or cost tokens
- Rate limits at relays (advertised via `hello` capabilities, enforced server-side)
- Credential-gated access
- Reputation provider plugins
- User-controlled blocklists
- Organization policy engines
- Signed abuse reports
- Gateway-level traffic screening
- Paid relay quotas

### 19.3 Consent Receipts and Grants

Consent receipts help with accountability but are not anti-spam by themselves. A consent receipt records: who consented, what was allowed, when, which profile it applies to, expiration, revocation. The `grant` message (§19.4) is the consent receipt in first-class message form.

### 19.4 First Contact

The first-contact problem is central. DSIP must define how an unknown identity requests permission to initiate future sessions without allowing that request mechanism itself to become spam.

Core v1.0 defines one mandatory-to-implement mechanism — the `introduction`/`grant` exchange — plus out-of-band **contact tokens**. QR pairing flows, organization intake endpoints, and paid or credential-backed introduction schemes are extensions layered on these two.

#### The `introduction` message

An `introduction` is a constrained, media-less, session-less request for permission to contact:

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["interactive-media/1.0"],
    "extensions": [],
    "critical": []
  },
  "type": "introduction",
  "id": "01J5Y0QJ1NT00AAAAAAAAAAAAF",
  "from": "did:key:z6MkCarolPhone",
  "to": "did:web:example.com:users:bob",
  "identity": {
    "display_name": "Carol Nguyen",
    "claims": []
  },
  "purpose": "We met at the Syracuse mesh-networking meetup; following up about the antenna group buy.",
  "issued_at": 1760000000,
  "expires_at": 1760432000
}
```

Constraints that keep the request channel spam-bounded:

- **Size:** the encoded introduction envelope MUST NOT exceed 4,096 bytes (a core constant, deliberately far below the transport cap). `purpose` is limited to 280 characters and is a claim like any display field (§18.2) — clients render it attributed and unverified.
- **No media, no session:** an introduction cannot become a call. It carries no media offer and creates no session state beyond the pending request.
- **Validity:** `expires_at − issued_at` MAY be up to 604,800 seconds (7 days), because introductions are store-and-forward friendly by design — the recipient may be offline for days.
- **Rate limits are mandatory:** relays MUST rate-limit introductions per sender identity and per recipient inbox, with tier-aware defaults (§19.1) — e.g., self-issued identities a few per day, credential-backed identities more. Exceeded limits return `policy.rate-limited` with `retry_after`.
- **Optional `contact_token`:** an opaque token the recipient's authority previously issued out of band (QR code, printed card, link, directory entry). An introduction bearing a valid token SHOULD bypass rate limits and MAY be auto-granted per recipient policy. Tokens are single-audience, **single-use** (the first introduction carrying a token is auto-granted and the token is consumed; multi-use tokens are a deployment extension), and expirable at the issuer's discretion.
- **Relays and unknown recipients:** a relay MUST accept an introduction without a routing response whether or not it knows the recipient (§13.2), MAY hold it bounded per recipient inbox (RECOMMENDED: 16) until `expires_at`, and delivers it on the recipient's next binding. This is what makes a nonexistent recipient and an ignoring one indistinguishable. A held introduction is verified against its own `expires_at`, not the 300 s replay window (§12.9).
- **Other holders (v0.8):** these rules bind any service that holds introductions for recipients, not only relays. The Messaging Profile's mailboxes hold introductions and the grants that answer them for their owners, under the same rate limits, anti-enumeration and bounds.
- **Sealed purpose (v0.8):** an introduction MAY replace `purpose` with `sealed` — `{alg, enc, ct}`, the purpose encrypted with HPKE to the recipient's X25519 `keyAgreement` key and bound to the introduction's `id`, `from` and `to` (the construction is the Messaging Profile's, M§6.9 and M§14.1). `purpose` and `sealed` MUST NOT both be present. Sealing hides the request text from every service that holds it and so defeats content screening; rate limits still apply.

#### Outcomes

Three outcomes, deliberately including silence:

1. **`grant`** — the recipient (or their authority, per policy) issues a signed contact grant:

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["interactive-media/1.0"],
    "extensions": [],
    "critical": []
  },
  "type": "grant",
  "id": "01J5Y0QKGRT00AAAAAAAAAAAAG",
  "session": "01J5Y0QJ1NT00AAAAAAAAAAAAF",
  "from": "did:web:example.com:users:bob",
  "to": "did:key:z6MkCarol",
  "scope": ["dsip.invite"],
  "valid_until": 1791536000,
  "issued_at": 1760000600,
  "expires_at": 1760000630
}
```

   The grant is the consent receipt (§19.3) in message form: `scope` names what it permits (registry `dsip-grant-scope`; initial values `dsip.invite`, `dsip.subscribe`, and `dsip.message` for the Messaging Profile since v0.8), and `valid_until` bounds its life independently of the envelope's delivery expiry. The recipient's endpoint and relay record the grant; the grantee also holds the signed grant and MAY reference it in a future invite via the optional `grant` field (the grant's `id`) to aid stateless or migrated relays. A live grant admits an invite when the inviting identity is its grantee, and a grant admits only the operations in its `scope`: an invite requires `dsip.invite`. The invite's `grant` field is an optimisation, never a requirement (v0.17, spec-gap 151): it helps a relay find the grant, but it never admits an identity that is not the grantee, and it never refuses one that is, even when it names a grant since replaced or one the recipient does not know. A grantee references only a live grant with `dsip.invite` that it holds from the callee. Grants are revocable: revocation is local policy at the granting side, optionally propagated as a signed `grant-revocation` (below).

   A grant MAY carry `presence_audience` (v0.17, spec-gap 145): the audience, a token `[a-z][a-z0-9-]*` of at most 64 characters chosen by the grantor, whose presence records a subscriber admitted by this grant sees (Presence Profile P§6). It MAY carry `presence_keys`
   (spec-gaps 152, 157): the keys of the grantor's sealed presence records that the grantee may read, HPKE-sealed to the
   grantee identity's key agreement key and bound to the grant's `id`, `from` and `to` (P§12.3).

   **A grant that follows a grant** (v0.17, spec-gap 150). The grantor MAY replace a live grant it issued, without a new introduction, by issuing a grant to the same grantee identity whose `session` names the grant it replaces instead of an introduction. The new grant's `scope`, `valid_until` and `presence_audience` are its own, so it can narrow, widen or re-time what the old one permitted (a grant without `dsip.subscribe` ends a presence share and keeps the calls). Issuing it withdraws the old grant at the granting side, and the granting device SHOULD send its authority a `grant-revocation` for the old grant, so that what the old grant admitted there ends (P§7). The grantee accepts such a grant only when it holds a live grant with that id from the same grantor identity, and then holds the new grant in place of the old one. A grant whose `session` names neither an introduction the grantee sent nor such a grant is dropped. A grant can only follow a grant: this gives no way to reach anyone who has not first introduced themselves.

   **`grant-revocation`** (v0.17, spec-gap 147). A device of the granting identity withdraws a grant before its `valid_until` by sending its authority (its relay, §9.3) a signed `grant-revocation` naming the grant's `id` (`grant`), the grantee identity (`grantee`) and the grant's `valid_until`. It is not answered. The authority keeps it until that `valid_until`. A grant so revoked no longer admits anything there: neither a presence subscription (P§7, which also ends the subscriptions it admitted) nor an invite, where that relay admits invites by grants. The granting endpoint itself stops honouring the grant when the user revokes it, whether or not a revocation is sent. Revocation stops what follows; it recalls nothing already delivered.

2. **`reject`** — with `session` set to the introduction `id` and a registered reason (`user.declined`, `policy.blocked`). Sending a rejection is a policy choice, not an obligation.

   (spec-gap 74) Both signed outcomes are addressed to the introducing **identity** — the identity the introduction's signer acts for (§7.4) — not to the device that sent it: a grant is held by an identity, any of whose devices may invite under it, and a rejection is equally the identity's to know, or its other devices would go on showing the request as pending. The identity's relay or mailbox delivers it to its devices.

3. **Silence** — the default posture. No response is ever required, no response deadline exists, and senders MUST NOT interpret silence as anything. Combined with the anti-enumeration rule (§9.3), this means an introduction to a nonexistent identity and an ignored introduction are indistinguishable to the sender.

An `invite` from an identity holding no grant (and matching no other allow policy) is rejected with `policy.first-contact-required` — the rejection that points the sender at this mechanism.

#### UX requirement

Introductions MUST NOT be rendered as calls, ring the device, or appear in call history. They belong in a distinct requests surface the user reviews deliberately. The entire design collapses if a spammer can make a phone buzz by sending introductions.

#### Pairwise identities and `did:peer` (note, v0.9)

This note is informative.

Introductions and grants work by identity, so a party that wants its contacts unable to correlate it can already use a **pairwise identity**: a fresh `did:key` for each contact, introduced and granted like any other. Nothing in this section changes for that.

`did:peer` (DIF Peer DID Method, v1.0 Draft) is designed for exactly this case: identifiers exchanged between two parties, with no third party and no public resolution. Its variants 2 and 4 carry keys and services inline (4 in a short form resolvable only by a peer that has seen the long form). It is not among the §7.2 methods, for two reasons:

- **Rotation.** Peer DIDs cannot be updated: rotating a key means moving to a new DID. DSIP's `key-rotation` record (§7.5) assumes an identifier that persists across keys. Supporting `did:peer` therefore needs a pairwise rotation message, signed by the old key, that tells the one counterparty the new DID.
- **Contacts, not discovery.** A pairwise DID helps the parties that already share it, never a stranger looking someone up (§8).

Full support is deferred: registration in §7.2, delegation from a `did:peer` subject, and that pairwise rotation message. Until then, a pairwise `did:key` gives the same unlinkability, at the cost of no rotation.

---

## 20. Security Threat Model

### 20.1 Assets

Assets to protect: identity keys, device keys, recovery keys, session metadata, media negotiation contents, media encryption keys, presence state, publication records, credential status, user consent decisions, gateway trust mappings, connection-to-device bindings.

### 20.2 Attackers

Potential attackers:

- Passive network observer
- Malicious relay
- Malicious media server
- Malicious connection splicer
- Compromised credential issuer
- Compromised DID controller key
- Compromised device key
- Spam originator
- Sybil identity farm
- Malicious broadcaster relay
- Downgrade attacker
- Replay attacker
- Resolver DoS attacker
- Cross-federation replay attacker
- Malicious gateway

### 20.3 Required Protections

DSIP Core v1.0 requires:

- Signed signaling envelopes
- Expiration timestamps
- Unique message IDs (ULIDs) with replay detection within the 300 s window
- Version negotiation covered by signatures
- Critical-extension negotiation
- Credential status checking for high-trust claims
- Delegation verification for device-signed messages and `hello` bindings
- No media path before a signed answer (§14.1)
- Explicit trust downgrade when crossing gateways
- Policy visibility before sensitive media actions

### 20.4 Downgrade Attacks

Attackers may try to remove encryption, remove critical extensions, force older protocol versions, remove AI disclosure, or strip policy fields.

Mitigation: version and extension lists are signed; required policies are marked critical; responders echo selected versions and extensions; clients fail closed when required extensions are missing.

### 20.5 Connection Binding

The `hello` exchange is cryptographically bound: the relay's `hello` echoes the client `hello` `id` via `in_reply_to`, and both messages are signed. A relay `hello` is therefore valid only for the specific exchange it answers and cannot be replayed onto a spliced or proxied connection to impersonate relay identity. Implementations MUST NOT substitute TLS channel properties for this check: TLS authenticates the server *host*, while the bound `hello` exchange authenticates the relay *identity* for this connection, and the two can legitimately differ (hosted relays, migrations, multi-tenant infrastructure).

### 20.6 Glare Backdating

Glare resolution compares ULIDs, whose leading component is a timestamp under the sender's control; a malicious party can backdate its invite `id` to deterministically win glare. The direct impact is limited to role selection — who proceeds as initiator versus responder — and neither role carries billing, priority, or disclosure asymmetry in Core v1.0. Two guardrails keep it that way: (1) receivers MUST verify that an envelope's `id` timestamp component is within the replay window (300 s) of its signed `issued_at` and MUST reject it otherwise; (2) any future profile that attaches an asymmetric privilege or cost to the initiator role MUST re-evaluate glare resolution before relying on it, and MUST NOT assume role assignment is adversarially neutral.

### 20.7 Traffic Analysis

Even if signaling payloads are encrypted in transit, metadata can leak: who contacted whom, when, session duration, which relay, which profile, presence patterns. DSIP supports relay privacy and encrypted transport, but is honest that metadata privacy is difficult.

Envelope payloads are signed but not end-to-end encrypted in Core v1.0: a relay that routes an invite can read it, including display names and the calling relationship. This is a stated v1.0 limitation, not an oversight. Payload encryption to the recipient's key-agreement key is the extension `sealed-body/1.0` (§10.4, spec-gap 97): it seals SDP, identity claims, DTMF and policy, and leaves routing metadata in clear; it does not hide the sender from the relay it binds to. Deployments that need metadata confidentiality from relays should run their own relays. Three things are encrypted end to end as of v0.8: the Messaging Profile's conversation content (MLS), a sealed introduction's purpose (§19.4), and a sealed body (§10.4). The envelopes that carry them remain readable to the services that route them.

### 20.8 Resolver DoS

Resolvers and DID document hosts can be attacked. Mitigations: caching with signed records, multiple service endpoints, domain-level redundancy, optional transparency logs, rate limiting, relay fallback, graceful degradation using recently verified records.

---

## 21. Accessibility Requirements

Accessibility is not bolted on later. DSIP profiles treat accessibility media as first-class negotiable streams.

### 21.1 Real-Time Text

The Interactive Media Profile includes support for real-time text negotiation. RTT may use existing RTP/T.140 mechanisms where RTP is used, or equivalent real-time text data channels where WebRTC/QUIC is used.

### 21.2 Captions

Caption streams include negotiated properties: language, format, source, latency target, human-generated vs automatic, confidence metadata if machine-generated, persistence policy.

```json
{
  "type": "caption",
  "format": "webvtt",
  "language": "en-US",
  "source": "automatic",
  "latency_target_ms": 1500
}
```

### 21.3 Sign Language Video

Sign language video is a first-class media purpose, not just a generic camera feed.

```json
{
  "type": "video",
  "purpose": "sign-language",
  "language": "ase",
  "resolution_min": "720p",
  "framerate_min": 30
}
```

### 21.4 TTY and Legacy Interop

A future PSTN gateway profile should consider TTY/RTT interop requirements for regulated voice services.

---

## 22. Verified Broadcast Profile v1.0

The Verified Broadcast Profile supports signed publication and subscription metadata for live media streams. The purpose is not to replace CDNs or streaming protocols. The purpose is to verify who published a stream, describe available variants, attach signed metadata, and preserve provenance through relays and transcoders.

### 22.1 Broadcast Publication Record

```json
{
  "dsip": {
    "core": "1.0",
    "min_core": "1.0",
    "profiles": ["verified-broadcast/1.0"],
    "extensions": [],
    "critical": []
  },
  "type": "publish",
  "id": "01J5Y0QEPXB00AAAAAAAAAAAAB",
  "from": "did:web:wxyz.com",
  "publisher": "did:web:wxyz.com",
  "stream_id": "did:web:wxyz.com:radio:main",
  "title": "WXYZ Live Radio",
  "state": "live",
  "integrity": "metadata-only",
  "issued_at": 1760000000,
  "expires_at": 1760000300,
  "variants": [
    {
      "id": "main-opus-low-latency",
      "media": ["audio"],
      "codec": "codec:audio/opus",
      "transport": "transport:webrtc",
      "uri": "wss://live.wxyz.com/dsip/webrtc/main"
    },
    {
      "id": "main-aac-hls",
      "media": ["audio"],
      "codec": "codec:audio/aac",
      "transport": "transport:hls",
      "uri": "https://live.wxyz.com/main.m3u8"
    }
  ],
  "policy": {
    "redistribution": "allowed-with-attribution",
    "recording": "allowed",
    "transcoding": "allowed"
  }
}
```

Rules (v0.7):

- `publisher` MUST equal the verified signing identity — the signer, or the delegator of a delegated device (§7.4). A record whose `publisher` is anyone else is rejected.
- `stream_id` MUST be the publisher DID or a colon-suffixed extension of it (`did:web:wxyz.com:radio:main`): streams live in their publisher's namespace.
- A `publish` whose `id` is ULID-older than the record an authority holds for the same `stream_id` is stale and ignored; a newer record replaces the older one and starts with no provenance statements.
- `unpublish` MUST be signed by the same identity and MUST name the held `publication` id.
- Variant order is the publisher's preference; a receiver selects the first variant whose codec and transport it supports.

### 22.2 Integrity Modes

Broadcast signatures are tricky because CDNs often transcode media into adaptive bitrate variants. Signing the original raw media bytes will usually break after transcoding. DSIP defines integrity modes.

**Core v1.0 defines two:**

```
metadata-only       Publisher signs stream identity, title, policy, and variant metadata.
derivative-bound    Transcoder signs a derivative stream and references the original publisher record.
```

The record declares its mode in the record-level `integrity` field (registry `dsip-integrity-mode`); absent means `metadata-only`. A variant MAY carry its own `integrity` to override the record's for that variant. Unknown tokens are not a rejection: a receiver treats a mode it does not recognise as `metadata-only`, the weaker claim. Independently of what the record declares, a receiver that has verified a transcode statement (§22.3) for the stream it is consuming displays `derivative-bound`.

**Reserved as registered-but-unspecified extension identifiers** (registry `dsip-integrity-mode`), each a serious engineering effort deferred until the core proves itself:

```
manifest-bound      Publisher signs a manifest or manifest hash.
segment-bound       Publisher signs segment hashes or a Merkle root of segments.
frame-bound         Signing individual media frames or groups of frames.
```

Where the provenance vocabulary overlaps C2PA, the broadcast profile should align terms with C2PA or document the divergence, rather than inventing a parallel taxonomy.

### 22.3 Provenance Through Relays and Transcoders

A relay or transcoder does not overwrite the original publisher identity. It adds its own signed provenance statement — the core `provenance` message (schema `provenance.schema.json`; no extension declaration is needed since v0.7):

```json
{
  "dsip": { "core": "1.0", "min_core": "1.0", "profiles": ["verified-broadcast/1.0"], "extensions": [], "critical": [] },
  "type": "provenance",
  "id": "01J5Y0QFPRV00AAAAAAAAAAAAC",
  "from": "did:web:cdn.example",
  "original_stream": "did:web:wxyz.com:radio:main",
  "original_publication": "01J5Y0QEPXB00AAAAAAAAAAAAB",
  "processor": "did:web:cdn.example",
  "operation": "transcode",
  "input_variant": "main-opus-low-latency",
  "output_variant": "main-aac-hls",
  "output_uri": "https://cdn.example/wxyz/main.m3u8",
  "issued_at": 1760000100,
  "expires_at": 1760003700
}
```

Rules:

- `processor` MUST equal the verified signing identity; `original_publication` and `original_stream` MUST name a publication the receiver has verified, and `input_variant` MUST be one that publication advertises. A statement failing any of these is rejected; the publication stands.
- `operation` is a registered token (registry `dsip-provenance-operation`; initial values `transcode`, `relay`, `repackage`). `transcode` makes the output `derivative-bound` and lists the processor under "transcoded by"; other operations list it under "delivered by". (spec-gap 77) A statement has no integrity mode of its own: there is one integrity mode, the delivered stream's (§22.2), and a receiver MUST NOT present a `relay` or `repackage` statement as `derivative-bound`.
- Carriage: a processor sends its statement to the publisher's authority (the relay or domain endpoint that holds the record), which attaches it to the record and lists processors in `notify.body.provenance` (§9.3); receivers fetch statements alongside the record. A receiver MAY also obtain statements directly from a processor. Either way it verifies them itself.
- A statement is evaluated against the publication's `policy` (§16.4): a `transcode` where the policy forbids transcoding, or any statement where it forbids redistribution, still verifies but is surfaced as a policy violation — policy is displayed and enforced by receivers, not by magic.

Receivers can then display:

```
Original publisher: WXYZ
Delivered by: Example CDN
Transcoded by: Example CDN
Integrity mode: derivative-bound
```

This makes provenance honest even when byte-for-byte media signatures cannot survive transcoding.

---

## 23. Economic and Operational Model

### 23.1 Costs Exist

Real deployments need: TURN servers, SFUs, media relays, broadcast relays, DID resolvers, credential issuers, revocation infrastructure, abuse mitigation, monitoring, gateway infrastructure, customer support.

"Free peer-to-peer" is possible only for a subset of sessions. Many users are behind NAT, many sessions need relays, mobile reachability needs push-capable relays (§13.3), and broadcast needs distribution infrastructure.

### 23.2 Payment Is Not Core Protocol

DSIP does not embed a payment system in v1.0. Instead, DSIP allows policy and authorization hooks: relay authorization tokens, subscription credentials, quota declarations (advertised via `hello` capabilities), enterprise policy checks, paid service endpoints, broadcast access tokens.

### 23.3 Likely Operating Models

- Self-hosted personal DSIP agent
- Organization-hosted DSIP domain
- Commercial DSIP relay provider
- Enterprise DSIP gateway
- Broadcast identity and publication provider
- Credential issuer
- PSTN/SIP interop provider
- AI media gateway provider
- Group focus / conference service provider (§17.4)

The protocol supports these without requiring any single one.

---

## 24. Governance and Registries

### 24.1 Initial Path

1. Publish DSIP as an open technical draft.
2. Build a reference implementation.
3. Define test vectors and interop tests (JSON Schemas and a 737-vector conformance suite with two independent runners exist as of v0.8).
4. Gather feedback from SIP/WebRTC/DID/security communities.
5. Submit an Internet-Draft to the IETF if there is interest.
6. Coordinate DID/VC-related work with W3C ecosystems.
7. Create a lightweight DSIP registry process for early experimentation.

### 24.2 Registries

DSIP needs registries for:

- Core versions
- Profile identifiers
- Extension identifiers
- Media type and purpose identifiers
- Codec identifiers (`dsip-codec`)
- Transport identifiers (`dsip-transport`)
- Signaling transport bindings (`dsip-transport-binding`: `ws/1.0`; reserved `quic/1.0`)
- Policy keys and values
- Reason tokens (`dsip-reason`, §15.4; category `mailbox` since v0.8)
- Progress statuses (`dsip-progress-status`, §12.10)
- Answered-by values (`dsip-answered-by`, §14.3)
- Info data namespaces (`dsip-info-about`, §12.12)
- Subscription event classes (`dsip-subscription-event`: `presence`, `publication`; §9.3)
- Grant scopes (`dsip-grant-scope`: `dsip.invite`, `dsip.subscribe`, `dsip.message`; §19.4)
- Delegation capabilities (`dsip-delegation-capability`: `dsip.signaling`, `dsip.media.interactive`, `dsip.messaging`; §7.4; `dsip.events`, Device Events Profile 1.0 E§2; `dsip.record`, Recording Profile C§1, draft)
- The Device Events Profile's own registries (device-event basis, alarm type, alarm severity; E§7)
- Recording states and purposes (`dsip-recording-state`: `on`, `paused`, `off`; `dsip-recording-purpose`: `compliance`, `quality`, `personal`; Recording Profile C§7, draft)
- Delegation-revocation reasons (`dsip-revocation-reason`: `lost`, `compromised`, `retired`, `policy`; §7.4)
- DID service types (`DSIPSignaling`, §13.2; `DSIPMailbox`, Messaging Profile)
- Credential claim types (`tel`, Gateway Profile)
- Endpoint classes
- Integrity modes (`dsip-integrity-mode`: `metadata-only`, `derivative-bound`; §22.2)
- Provenance operations (`dsip-provenance-operation`: `transcode`, `relay`, `repackage`; §22.3)
- Key-rotation reasons (`dsip-rotation-reason`: `scheduled`, `compromised`, `lost`, `policy`; §7.5)
- ICE candidate-exchange modes (`dsip-ice-mode`: `trickle`; WebRTC Media Binding)
- The Messaging Profile's own registries (deposit classes, content kinds and purposes, receipt kinds, activities, mailbox modes, conversation kinds; M§17)

### 24.3 Registry Governance

Early registries may be maintained by the project; a mature DSIP standard moves to a neutral governance body: an IETF working group or dispatch path, a W3C community group for identity-related pieces, an independent DSIP foundation as an incubator, or IANA-style registries if standardized through IETF.

### 24.4 Conformance

A DSIP implementation claims conformance to specific pieces:

```
DSIP Core 1.0
DSIP Interactive Media Profile 1.0
DSIP Verified Broadcast Profile 1.0
DSIP WebSocket Signaling Binding 1.0
DSIP WebRTC Media Binding 1.0
DSIP RTP/SRTP Media Binding 1.0 (draft)
DSIP Relay 1.0
DSIP Gateway Profile 1.0
DSIP Messaging Profile 1.0
DSIP Mailbox 1.0
DSIP DHT Hints Profile 1.0 (draft)
DSIP Alias Transparency Profile 0.1 (draft, stage 1)
DSIP Device Events Profile 1.0
DSIP Recording Profile 0.1 (draft)
```

(The v0.6 "Broadcast Provenance Extension" is gone: provenance is a core message of the Verified Broadcast Profile since v0.7.)

This avoids meaningless claims like "supports DSIP" without saying which profiles are implemented.

---

## 25. Minimal Reference Implementation

A credible prototype should be small. (As of v0.8, Phases 1–4 exist in the `impl/` reference implementation, conformant to this revision, together with the Messaging Profile running over the wire.)

### 25.1 Phase 1: Core

- DID generation for `did:key`; `did:web` resolver
- Signed DSIP-JOSE envelopes (Ed25519), `kid`-to-DID verification
- Payload validation against the published JSON Schemas
- Version negotiation
- Full session message set: invite/progress/answer/reject/cancel/update/bye/error
- Session state machine with timers, races, glare, and renegotiation (§12), driven by the test vector suite
- `ws/1.0` signaling binding with `hello`, capabilities, and reconnection
- Structured media capability negotiation
- CLI test tool

### 25.2 Phase 2: Interactive Media

- Browser demo and native/CLI endpoint demo
- Audio and video call setup over the WebRTC media binding
- Screening-pattern demo (`answered_by`, escalation update)
- Policy display; identity verification display; unknown identity warning
- Contact allowlist; introduction/grant first-contact flow (§19.4)
- Forking relay with per-leg tracking and store-and-forward

### 25.3 Phase 3: Verified Broadcast

- Broadcast publication record generator and signed publication verifier
- HLS/WebRTC variant advertisement; subscribe flow
- Basic publisher and receiver UI
- CDN/relay provenance proof-of-concept (`derivative-bound`)

### 25.4 Phase 4: SIP/WebRTC Gateway

- DSIP to SIP INVITE gateway; SDP mapping; RTP/SRTP media bridge
- Reason code mapping per §15.5
- Trust downgrade indicator
- Optional STIR/PASSporT/RCD mapping research

---

## 26. Example: Interactive Session Flow

1. Alice enters Bob's alias.
2. Alice resolves the alias to Bob's DID, then Bob's DID document, and discovers Bob's DSIP service endpoint.
3. Alice's device connects (`wss`), exchanges verified `hello` with the relay, and sends a signed `invite` containing a media offer.
4. The relay forks the invite to Bob's phone and laptop, tracking both legs.
5. Bob's phone verifies Alice's DID, delegation, and signature, applies local trust policy, and sends `progress` (status `ringing`). Alice's client plays locally generated ringback.
6. Bob accepts on his phone. The phone sends `answer` with `answered_by: "user"` and the selected media/transport.
7. Alice accepts the answer, transitions to ACTIVE, and sends `cancel` (reason `session.answered-elsewhere`); the relay delivers it per-leg to the laptop, which stops alerting without logging a missed call.
8. Media is established via the negotiated WebRTC binding (DTLS-SRTP). ICE candidates ride in signed `info` envelopes (§12.12), buffered until ACTIVE.
9. Mid-call, Bob adds video: `update` with a video offer; Alice's client sends `answer` referencing the update via `in_reply_to`.
10. Either side sends signed `bye` (reason `user.hangup`).

---

## 27. Example: Verified Broadcast Flow

1. WXYZ publishes a signed DSIP publication record.
2. A listener resolves `live@wxyz.com` or `did:web:wxyz.com:radio:main`.
3. The receiver verifies the publisher identity, publication expiration, and policy.
4. The receiver selects a compatible stream variant and subscribes or fetches the advertised media endpoint.
5. If a CDN transcodes the stream, the CDN adds a signed provenance statement (`derivative-bound`).
6. The receiver displays the original publisher and delivery path.

---

## 28. Summary

The stronger DSIP direction is not "SIP for everything."

The stronger direction is:
> **A small decentralized session core with explicit profiles for trusted real-time media.**

The first credible version focuses on:

- DID-based identity with device delegation
- Signed signaling over one mandatory reliable transport binding
- A complete session lifecycle: state machine, races, timers, forking, renegotiation
- One negotiation pattern with no media before a signed answer
- Structured progress, cancellation, and namespaced reason codes
- Trust-aware session identity and `answered_by` transparency
- Abuse-aware first contact via the introduction/grant exchange
- Interactive media sessions, including star-topology small groups
- Verified broadcast publication/subscription with honest provenance
- Clear extension and profile boundaries, with machine-validated payload schemas

Future profiles can add AI agents, device media, emergency services, contact centers, messaging, and other verticals once the core has proven itself.

The goal is not to create another protocol that can theoretically do everything. The goal is to create a protocol that does a few foundational things well enough that others can build on it.

---

## 29. Positioning Statement

> DSIP is a decentralized session initiation protocol for trusted real-time media. It uses verifiable identity, signed signaling, and explicit media negotiation to let endpoints establish interactive sessions or publish verified live media without depending on phone numbers, carrier registrars, or proprietary platform identity.

---

## Appendix A: Design Evolution

### A.1 From v0.4 to v0.5

The v0.4 draft expanded DSIP into a universal control plane for nearly every real-time media scenario: calls, video, broadcasts, IoT, AI agents, emergency services, vehicles, sensors, contact centers, and public safety video. That vision is useful, but the scope was too broad for an implementable v1.0.

Protocols that try to support every vertical from day one fail in predictable ways: the core becomes too large to implement completely; vendors implement incompatible profile subsets; profile dialects emerge without strong interoperability; the protocol loses to focused competitors in each vertical; security analysis becomes too broad to be useful; governance becomes impossible. SIP suffered from this. XMPP suffered from this.

The v0.5 correction: **a small, stable session core and a disciplined profile model**, useful by itself but narrow enough that two independent teams can implement it and interoperate.

### A.2 From v0.5 to v0.6

v0.6 converts the session layer from description to specification. Resolved decisions, recorded with rationale:

1. **Session state machine added** (§12): initiator and responder states, transition tables, the cancel/answer race, deterministic glare resolution, forking, and timers. The `session` field was added to all session-scoped messages (v0.5 never defined how an `answer` referenced its invite).
2. **`progress` and `cancel` added to core.** Without them, ringing UX and multi-device forking are unimplementable.
3. **Signaling transport specified** (§13): bindings MUST be reliable, ordered, encrypted; `ws/1.0` (WebSocket over TLS 1.3) is mandatory-to-implement; raw UDP signaling is a stated non-goal; QUIC is the planned second binding. Rationale: envelope sizes exceed UDP datagram limits, and SIP's dual-transport model was a proven source of interop failure.
4. **`hello` connection binding added**, with mutual signed identification, mandatory `in_reply_to` echo (anti-splicing — the more secure option over TLS channel binding), and a relay `capabilities` object. 64 KiB envelope cap is a fixed binding constant. Multihoming across different relays permitted; same-relay parallel connections undefined.
5. **Early media and delayed media excluded by design** (§4, §14), replaced by the answer-early/escalate pattern, the `answered_by` field, and the no-media-without-signed-answer invariant.
6. **Unified namespaced reason registry** (§15) replaced ad-hoc per-message tokens and numeric-code proposals, preserving family fallback through categories. PSTN/Q.850/SIP mapping table added for the gateway profile.
7. **`queued` progress** suspends T-Ring for a mandatory `queue_timeout` hard-capped at 1800 s with bounded re-queues; richer queue semantics deferred to a contact-center extension.
8. **Per-leg cancel is REQUIRED for relay conformance** — relays track leg state and signal attempt completion; identity-addressed fan-out alone is non-conformant.
9. **Renegotiation**: RENEGOTIATING sub-state, one outstanding `update` per session across both directions, glare-rule collision resolution, `bye` wins.
10. **Glare backdating** documented (§20.6) with a tripwire obligation on future profiles that make roles asymmetric.
11. **Scope decisions**: small-group retained in v1.0 via the star-topology focus model (§17.4); broadcast integrity modes trimmed to `metadata-only` + `derivative-bound` with the other three reserved; v0.4-correction narrative, emergency services, and PSTN reality moved to appendices.
12. **Crypto floor fixed**: Ed25519 MUST, ES256 MAY, all else rejected; `kid` is a DID URL. Codec entries are normatively objects. JSON Schemas for all fifteen message types accompany the spec and are authoritative for payload shape.

### A.3 v0.6 Final Additions

A second v0.6 pass closed the three gaps the first pass had named:

13. **`info` message added** (§12.12) for transport-binding data, replacing the earlier plan to carry ICE candidates in `update` envelopes. Renegotiation and transport chatter have different semantics: `update` is one-outstanding with mandatory answer/reject; trickle ICE is high-frequency and answerless. `info` is ACTIVE-only, signed, never critical, and forbidden from altering negotiated parameters.
14. **First-contact mechanism specified** (§19.4): the mandatory `introduction`/`grant` exchange — 4 KiB envelope cap, 280-char purpose, 7-day validity, mandatory tier-aware relay rate limits, optional out-of-band contact tokens, and silence as the default no-response posture. Grants are consent receipts in message form, scoped and revocable; `policy.first-contact-required` is the rejection that points at the mechanism. Introductions never render as calls.
15. **Subscription protocol specified** (§9.3): soft-state subscribe with per-event lifetime caps (presence 3,600 s, publication 86,400 s), refresh-by-resubscribe, `expires_in: 0` termination, seq-ordered notifies with a terminal state, authorization as the target authority's policy decision over verified identity plus optional claims/capability tokens, and a mandatory anti-enumeration rule: unauthorized and nonexistent targets are indistinguishable.

With these, no section of this draft is marked as a known open design gap. Forward work is additive: the QUIC binding, the reserved extensions (SFrame E2EE, group roster, broadcast integrity modes), sealed-sender signaling confidentiality, and the future profiles named throughout.

### A.4 From v0.6 to v0.7

v0.7 is the revision written *from* an implementation: the reference implementation (`impl/`) implemented every MUST of v0.6, and each ambiguity it hit became a numbered `spec-gap` with the choice the implementation made and a conformance vector pinning it. v0.7 transcribes those 22 dispositions plus the companion documents the implementation forced into existence. No wire-format change: `dsip.core` stays `1.0`.

16. **Resolved ambiguities of the session machine** (§12.4–§12.10): crossed versus late `cancel` in ACTIVE (the distinguishing condition is whether the initiator has spoken post-answer); glare loser withdraws with `cancel session.glare`, winner rejects with `reject session.glare`; a second outstanding `update` discards both; T-Ring restart semantics and a PROCEEDING backstop; the initiator's forking rule stated in terms it can observe (identity-addressed invites); `bye session.failed` for an answer after a terminated attempt; ENDING collapsible; the re-queue limit is a MUST.
17. **Replay and glare guardrails tightened** (§12.9, §20.6): the replay window is symmetric, and the ULID/`issued_at` consistency check is a MUST with a 300 s tolerance.
18. **Delegation conveyance defined** (§7.4): a delegation is a DSIP-JOSE envelope signed directly by the subject, presentable in the protected header `delegations` array; no chains.
19. **Key rotation has a record** (§7.5): the `key-rotation` message, signed by the retiring key or a recovery key, with the DID document remaining authoritative; `did:key` identities cannot rotate. Registry `dsip-rotation-reason`.
20. **Selection subset defined per field** (§14.2); registry "valid on" is sender guidance (§15.6).
21. **Relay semantics** (§13.2, §13.3): introductions are accepted regardless of recipient existence (anti-enumeration); *known* identity defined; store-and-forward bounds, silent expiry, mid-attempt legs.
22. **First contact** (§19.4): grant matching by reference or by grantee, `scope` enforcement, single-use contact tokens, relay inbox bound.
23. **Subscriptions** (§9.3): over-cap `expires_in` is refused with the new `policy.subscription-lifetime`, never clamped; authority-asserted presence is named and rendered as the authority's claim.
24. **Verified Broadcast** (§22): publisher/stream-id binding and stale-record rules; record-level `integrity` with variant override and registry fallback; `provenance` is a core message with a schema and a defined carriage; registry `dsip-provenance-operation`.
25. **WebRTC Media Binding 1.0** published as a companion document (the §12.12/§16.3 references now resolve): SDP in `transports[].sdp` with the descriptor/SDP authority rule, role and DTLS mapping, trickle ICE in `info` with buffering and attribution rules and a normative `info.data` schema, renegotiation on the same transport, ICE restart explicitly unsupported, one applied answer per forked offer. §26 step 8 corrected.
26. **DHT Hints Profile** published as a companion document with the `reachability-hint` message; the DHT remains a hints tier only (§8.1).

Every item above is pinned by at least one vector in the v0.7 conformance suite.

### A.5 From v0.7 to v0.8

v0.8 is again written from an implementation. The reference implementation built a SIP/PSTN gateway and then a complete messaging system on DSIP, including real MLS and HPKE, several mailboxes, multiple devices and voicemail. Every ambiguity it hit became a numbered spec-gap (23–57) with a vector pinning the choice. Most of them are settled inside the two new companion profiles; the items below are what the core itself says differently. No wire-format change: `dsip.core` stays `1.0`, and every addition is an optional field, a new message type or a new registry value.

27. **Companion profiles** (§3.3, §6.1–§6.3, §17.2, §24.4): the **Gateway Profile 1.0** (spec-gaps 23–25, 27–29) and the **Messaging Profile 1.0** with **Mailbox 1.0** (32–35, 40–55) are published as conformance pieces; the **RTP/SRTP Media Binding** is published as a draft (30).
28. **Held introductions** (§12.9, §19.4; spec-gap 31): an introduction's age is bounded by its own `expires_at`, not the 300 s replay window, under the 7-day cap — a v0.7 defect that made store-and-forward introductions fail after five minutes.
29. **Delegation capabilities** (§7.4, §24.2; spec-gaps 39, 56): the `dsip-delegation-capability` registry; binding every envelope still requires `dsip.signaling`, and profile capabilities are added beside it.
30. **Delegation revocation** (§7.2, §7.4, §8.1; spec-gap 57): the `delegation-revocation` record, the `dsipDelegationRevocations` document property, and the `delegation-revoked` verification outcome. Before v0.8 a lost device's delegation kept verifying until it expired.
31. **First contact** (§19.4; spec-gaps 36, 54): the `dsip.message` grant scope; the optional `sealed` purpose; the relay rules bind any service that holds introductions.
32. **DID document properties** (§7.2; spec-gaps 37, 55): `DSIPMailbox` service entries and `keyAgreement` keys are read and authoritative; DHT hints may name the service they stand in for.
33. **Reason category `mailbox`** (§15.1, §15.3, §15.4; spec-gaps 38, 48), with the fallback "re-sync, retry once, then surface".
34. **`tel` claims** (§18.1, §24.2; spec-gap 25).
35. **Statements** (§13.2, §20.7, §7.6; spec-gaps 33, 35, 40): profiles carry bulk data outside the signaling binding; what is end-to-end encrypted as of v0.8; identity-level profile secrets belong to the recovery model.

36. **DTMF** (§12.12; spec-gap 70): `media:dtmf` in `dsip-info-about`. This closes spec-gap 26, which the first v0.8 text left open.
37. **Relay forking and routing** (§12.4, §12.5, §12.7, §13.3, §15.4; spec-gaps 75, 76, 82, 85, 86): `session.answered-elsewhere` at the leg that answered; the relay's `transport.no-response` as the outcome of an attempt no leg answered or rejected; routing by `to` with or without an attempt; the `bye` a late answer gets once the call has ended; and a relay never withholding an `answer`.
38. **Reason tokens** (§15.1, §15.4; spec-gaps 73, 78): reason tokens on a terminal `notify`; `bye` admitted for `gateway.unreachable`, `media.unsupported` and `session.timeout`.
39. **First contact** (§19.4; spec-gap 74): who an introduction's outcome is addressed to.
40. **Verified Broadcast** (§22.3; spec-gap 77): a single integrity mode for a statement that is not a transcode.
41. **Reachability hints** (§8.5, §12.9; spec-gap 96): a hint's age is bounded by its own `expires_at` under a 3,600 s cap, not by the 300 s replay window, which had made every hint unusable five minutes after signing. §8.5 now states what the hints tier guarantees (integrity, bounded staleness, no authority) and what it does not (availability, privacy), in place of "experimental".
42. **Sealed bodies** (§10.4, §20.7; spec-gap 97): the extension `sealed-body/1.0` encrypts SDP, ICE candidates, display names, DTMF and policy to the addressee, leaving in clear only what relays route by.
43. **Storage limits** (§13.3; spec-gap 99): relays bound store-and-forward per recipient and in total and refuse beyond it, never dropping silently. The Messaging Profile's side (`accepted` means durably stored, what `quota_bytes` counts, the blob endpoint's `507`) is M§4.4, M§5.6, M§9.3 and M§9.4.
44. **Relay service scope** (§13.6; spec-gap 100): open, private and closed relays; no relay is obliged to serve or forward for anyone.

The companion profiles were revised in place over the same period, each change marked with its spec-gap number: the Messaging Profile for spec-gaps 58–69, 71, 72, 80, 81, 83, 87, 88, 91, 92, 94, 95 and 99 (its Appendix M-B), the Gateway Profile for 78 and 79, and the DHT Reachability Hints draft for 96.

Every item above is pinned by the v0.8 conformance suite (979 vectors; the Python harness, the Rust reference implementation and the independent TypeScript implementation agree on every one) except item 44, a relay's routing policy outside its state machine, which the reference relay's private-relay demo exercises.

---

### A.6 From v0.8 to v0.9

v0.8 is final at tag `poc-v0.8.1`; v0.9 is final at tag `poc-v0.9`. v0.9 work, decided 2026-10-04 from `impl/docs/v0.9-research.md`:

- `did:webvh` as a recommended DID method beside `did:web` (§7.2, §8.4; spec-gap 101): resolvers verify the whole log, support v1.0 only, read I-JSON, and reject rollback and fork against the highest `versionId` they have verified. Pinned by the `did-webvh/` vectors.
- Reachability hints on the BitTorrent Mainline DHT (Pkarr) for `did:key` subjects, in addition to the hints overlay (§8.5; DHT Reachability Hints Profile §9; spec-gap 105): compact `_dsip` TXT records signed by the identity key, with a signed expiry of the timestamp plus the smallest TTL (≤ 3600 s), the checks Pkarr omits, and §8.3 conflicts. Pinned by the `pkarr/` vectors and confirmed against the pkarr crate.
- Alias transparency: a log that makes an alias provider's `alias → DID` answers auditable (§8.2) — companion profile `v1.0/dsip-alias-transparency-profile-v1.0-draft.md` (cited `T§n`; spec-gap 104), KEYTRANS-shaped with VRF-blinded aliases. Stage 1 (this revision): the profile's choices and the KEYTRANS building blocks, pinned by the `alias-transparency/` vectors and confirmed against the KEYTRANS editor's implementation. Lookup verification, owner monitoring and fork detection follow KEYTRANS -06.
- A Device Events Profile: signed device alarms and events, gatewayed from SNMP and syslog (companion profile `v1.0/dsip-device-events-profile-v1.0.md`, cited `E§n`; spec-gap 103): RFC 3584 trap translation without the community, an RFC 3877-shaped rule table, an RFC 8632-style alarm list every member computes from the group's order, acknowledgement separate from read receipts, gateway silence, and an escalation trigger run by a member. Later in the revision: SNMPv2c informs answered only once the hub has stored the event; SNMPv3 with USM (RFC 3414 order, HMAC-SHA-2, AES-128; `noAuthNoPriv` and DES refused); syslog over UDP and TLS (RFC 5424 and RFC 3164) with its rules; and the identity an authenticated basis adds to the claim (E§2). Pinned by the `device-events/` vectors.
- Reachability hints on Pkarr, publishing (DHT Reachability Hints Profile §9; spec-gap 105): a publisher carries every record another application put in its zone, re-encoding the names in the RFC 1035 types RFC 3597 §4 lets compress; and it signs `max(clock, previous + 1)`, the one case signed ahead of the clock being a clock stepped back. Hints travel through Pkarr relays and the Mainline DHT directly. Pinned by the `pkarr/` vectors.
- A Recording Profile for compliance recording under end-to-end encryption (companion profile `v1.0/dsip-recording-profile-v1.0-draft.md`, cited `C§n`; spec-gaps 107, 108). Recording happens at endpoints the organisation controls, and is disclosed:
  - a signed `recording` declaration on `invite`, `answer` and `update` (§16.4 now separates that declaration from the `policy.recording` preference) and `recording_session` metadata on `invite` — the first core schema additions since v0.8, both optional;
  - a counterparty's client renders the declaration and acts only after acceptance; declining is the new reason `policy.recording-declined` (§15.4);
  - the delegation capability `dsip.record` (§24.2) marks a recorder device, which is receive-only, joins conversations but never its identity's personal group, and never stands in for the person;
  - a recorder leg forks a call's media to the declared recorder, end to end.

  Pinned by the `recording/` vectors and four `semantic/` ones.
- A note on pairwise identities and `did:peer` (§19.4; research decision 5): a pairwise `did:key` per contact today; `did:peer` deferred until DSIP has a pairwise rotation message.
- The Messaging Profile, revised in place (its Appendix M-B): a device whose blob fetch finds nothing tries again (M§8.4; spec-gap 106).

No wire-format change: `dsip.core` stays `1.0`, and every addition is an optional field, a new registry value or a companion profile. Every item is pinned by the v0.9 conformance suite (1,385 vectors; the Python harness, the Rust reference implementation and the independent TypeScript implementation agree on every one).

---

### A.7 From v0.9 to v0.10

v0.9 is final at tag `poc-v0.9`; v0.10 is final at tag `poc-v0.10`. v0.10 completes work v0.9 left open: the multi-device and device-events items its
spec-gaps listed, and recording acceptance across a person's devices. Each item names its spec-gap.

- Recording acceptance is the person's, not one device's (Recording Profile C§5; spec-gap 107): the device on which
  the user accepts sends a `recording-acceptance` object to the identity's personal group, and every device of the
  identity applies it. The object is registered in M§8.1; older devices ignore it as an unknown object.
- Multi-device identities on Pkarr (DHT Reachability Hints Profile §9.1; spec-gap 105 option (b)): the identity key
  signs a pointer to its devices, valid up to 7 days, and each device publishes its own hint with its delegation, so
  the identity key can stay offline. Revocation is bounded, not immediate, and the profile states the bound.
- Device Events (spec-gap 103): an optional gateway hold-down that delays clears, so a flapping link is one alarm
  (E§4); and an optional `source.name`, the gateway's name for a verified device identity (E§2).
- Device Events (spec-gap 103): SNMPv3 over TLS (RFC 6353) with the Transport Security Model, basis `snmpv3-tls`.
  It covers RFC 6353's certificate-to-name table, framing, RFC 5343 discovery and the inform Response (E§3).
- Device Events (spec-gap 103): signed syslog (RFC 5848), basis `syslog-signed`. A configured signer's messages are
  held until a verified Signature Block lists them, or are deposited with their transport's basis (E§3).

No wire-format change: `dsip.core` stays `1.0`, and every addition is a new optional field, object, registry value
or profile section. Every item is pinned by the v0.10 conformance suite (1,539 vectors; the Python harness, the Rust
reference implementation and the independent TypeScript implementation agree on every one).

### A.8 From v0.10 to v0.11

v0.10 is final at tag `poc-v0.10`; v0.11 is final at tag `poc-v0.11`. v0.11 adds number attestation, finishes the
Device Events items spec-gap 103 left open, and gives hints an HTTP face. Each item names its spec-gap.

- Number attestation (Number Attestation Profile, draft, `N§n`; spec-gap 110): the holder of a number's STIR
  authority signs a short-lived binding of an E.164 number to a DID, and the DID document claims the number back in
  `alsoKnownAs`. Clients verify both offline, against the STI-CA roots the PSTN already trusts. The number stays an
  alias (§8.2). Stage 1 pins the binding and the order of its checks (N§3). Stage 2 pins the `tel` claim that
  carries a binding and its rendering (N§4), and the warning when a number moves to another identity (N§5). Stage
  3 adds discovery: a `dsip-node` holds bindings by number, and a caller dialling `tel:` verifies them and chooses
  one (N§6 route 1, N§7). Stage 4 is the gateway (N§4.1, N§6.1): a DSIP caller's attested number crosses to the
  PSTN with a SHAKEN PASSporT signed only under a certificate that covers the number, normally an RFC 9060 delegate
  certificate (never `B` on a binding alone, item A), a PSTN caller's PASSporT is verified before the G§5 claim is
  rendered, and an inbound call to a bound number is routed by the operator's table, then by the binding. An
  identity with a verified number counts as domain-bound (Tier 3) for first contact by default (§19.1, item D).
- The invite's `destination` (spec-gap 111): a `tel:` E.164 URI naming the PSTN number a caller asks a gateway to
  reach, ignored by any other callee. G§3.1 had never said how the number was named.
- `detail` on `error`, `reject`, `cancel` and `bye` may be an object a profile defines (§15; spec-gap 112): G§7's
  `gateway.downgraded` carries `{"losses": [...]}`, which the suite and the clients had pinned while the schema
  typed `detail` as a string; a relay refused the first one ever sent on the wire.
- Device Events (spec-gap 103): gap detection from signed syslog (E§3). A gateway configured to receive all of a
  signer's messages reports the message numbers that no Signature Block covered, or that were signed but never
  arrived. It raises the new alarm type `dsip-syslog-gap` (E§7), from a gateway event carrying `syslog_gap` (E§5).
- Device Events (spec-gap 103): RFC 5848's remaining key blob types for signed syslog (E§3). `N` uses the signer's
  pre-distributed key; `P` is an OpenPGP KeyID and certificate, read as RFC 4880 packets with a v4 DSA public key
  first; `U` has no interoperable reading and is refused.
- Device Events (spec-gap 103): SNMPv3 over DTLS (RFC 6353 over UDP; E§3). The session's client certificate names
  the sender through the same table as TLS, a nameless session is closed, and each DTLS record carries exactly one
  message. The `tsm` claim says which transport (E§2).
- HTTP access to hints (DHT Reachability Hints Profile §10; spec-gap 105): a node serves Pkarr's relay interface and
  the overlay's records over HTTP, so browsers, which join no DHT, get hints they verify offline. A node stores any
  application's verified Pkarr packet under §8.3's `ts` rule; withholding is its only power. A node holding a packet
  SHOULD look on Mainline for a newer one before serving it past its TTL (spec-gap 109).

No wire-format change: `dsip.core` stays `1.0`; the two schema additions are an optional invite member and a wider
`detail`, and everything else is a registry value or a profile section. Every item is pinned by the v0.11
conformance suite (1,924 vectors; the Python harness, the Rust reference implementation and the independent
TypeScript implementation agree on every one).

---

### A.9 From v0.11 to v0.12

v0.11 is final at tag `poc-v0.11`. Each v0.12 item is listed here as it lands, with its spec-gap number.

- Number attestation, discovery route 2's serving half (Number Attestation Profile N§6; spec-gap 110 item J): a
  number's authority serves the bindings it issued at `https://<authority>/.well-known/dsip/tn/<tn>`; a client asks
  the authorities it is configured with, pools their answers with route 1's, chooses by N§7 and keeps the names of
  the authorities that served the answer. The Alias Transparency Profile's T§3 gains the `tel:` label (a global tel
  URI, E.164 digits), so the log entry route 2 calls for is defined; verifying it waits for T§6 (KEYTRANS -06).
- A node holding a Pkarr packet looks for a newer one before serving it past its TTL (DHT Hints Profile §10;
  spec-gap 109).
- A `did:key` identity hands its relay a revocation as a frame on a bound connection; the relay holds it and ends
  the named device's binding (§7.4, §13.2; spec-gap 113).
- ICE servers, TURN credentials and hints nodes reach a client from the origin that serves it or from
  configuration, never from the relay's `hello` (§13.2, WebRTC Media Binding §4, DHT Hints Profile §10; spec-gap
  114).
- `from` names the signer, device or identity; the acting identity comes from the delegation, whatever the type
  (§10.2; spec-gap 117).
- Messaging Profile: a mailbox may serve identities that enrol by binding (M§4.1; spec-gap 115); a hub resolves
  each member's mailbox per M§4.2 at every delivery, never from where the member once bound (M§6.5 rule 5;
  spec-gap 116); a hub-forwarded welcome's `origin` is bounded by age, not skew (M§14.2; spec-gap 118).

No wire-format change: `dsip.core` stays `1.0`; the schema sets are unchanged from v0.11. Every item is pinned by
the v0.12 conformance suite (1,956 vectors; the Python harness, the Rust reference implementation and the
independent TypeScript implementation agree on every one), or by the browser client's headless tests where the
decision is a host's and no message changes (113, 114, 115, 116).

---

### A.10 From v0.12 to v0.13

v0.12 is final at tag `poc-v0.12`; v0.13 is final at tag `poc-v0.13`. Each v0.13 item is listed with its spec-gap number.

- Messaging Profile: a hub keeps a member identity's fan-out queues for at most `mls_retention_s` without an
  acknowledgement, then drops them, welcome included (M§6.5; spec-gap 119); whether a new device waits for a sibling
  or joins by external commit is its own decision (M§6.8; spec-gap 120); what a device does when its identity moves
  to another mailbox (M§4.1, M§5.7; spec-gap 122).
- Call detail records (spec-gap 121): Appendix D (informative) says what an organisation's relay, gateway and
  mailboxes can record of its calls, and what they cannot; the Recording Profile's C§9 adds the endpoint-side
  `call-record` object, sent by each device to its organisation's record-keeper after every call leg, which the
  Messaging Profile lists (M§8.1) and its schema set defines (`call-record.schema.json`, the one schema change).
  The record-keeper opens the conversation with each party, since a party cannot add an identity whose devices are
  all recorders (C§5, C§9; spec-gap 123).


### A.11 From v0.13 to v0.14

v0.13 is final at tag `poc-v0.13`; v0.14 is final at tag `poc-v0.14`. Each v0.14 item is listed with its spec-gap number.

- Alias transparency, the DSIP side of stage 2 (spec-gap 124): the provider's query endpoint answers an absent
  alias, a hidden one and a non-owner's monitor request with one `not-found`, after a rate limit that counts every
  query (T§7); an owner, current or former, authorizes monitoring with an `alias-monitor` message (T§8, the one
  core schema addition); signed tree heads travel between peers as an `alias-log-head` claim, and two heads of one
  size with different roots prove a fork (T§9); a lookup result is `audited`, `unaudited` or `not-found` (T§10).
  Verifying KEYTRANS's proofs stays staged for -06 (T§6).
- Messaging Profile: leaving a conversation (M§7.3; spec-gap 125). The leaver proposes the removal of its identity's
  leaves, since MLS forbids committing one's own removal, and another member commits them.

### A.12 From v0.14 to v0.15

v0.14 is final at tag `poc-v0.14`; v0.15 is final at tag `poc-v0.15`. v0.15 changes only the Messaging Profile; the core text, the wire format and both
schema sets are unchanged. Each item is listed with its spec-gap number.

- Members enforce the roster rules themselves (M§7.3; spec-gap 126): every commit is checked by the hub's own rule
  before it is merged, and one that fails is not merged.
- Removal ends the join (M§8.5; spec-gap 127): a removed device deletes the group's state, so adding it back is a
  join; its processed `seq` positions are kept.
- A group may come back to a hub it left (M§7.4; spec-gap 128): the committer's handover `group-info` returns it, and
  the hub numbers on from `handover_seq + 1`.
- A member may reach the new hub before the GroupInfo that sets it up (M§7.4; spec-gap 129): it retries the same
  deposit with the §13.2 backoff for at most 300 s (RECOMMENDED) before the refusal counts.

### A.13 From v0.15 to v0.16

v0.15 is final at tag `poc-v0.15`; v0.16 is final at tag `poc-v0.16`. v0.16 changes the Messaging Profile and two core sections (§12.7, §13.3). Each item is
listed with its spec-gap number.

- An enrolment at a mailbox can end (M§4.1, M§5.7, M§16; spec-gap 130): a device releases its identity's enrolment
  with `mailbox-config` `release: true`, and the mailbox deletes everything it holds for the identity; a mailbox MAY
  release an enrolled identity that no longer has a registered device (M§4.4); an owner operation from an
  identity the mailbox neither serves nor can enrol is refused `mailbox.not-served`. The Messaging Profile schema set
  gains `mailbox-config.release`.
- What a relay forgets (§13.3; spec-gap 131): a recipient stays *known* for `offline_retention_s` after its last
  binding ended, and while anything is held for it; a relay MAY discard an attempt once more than the T-Queue cap
  (1,800 s) passes with nothing for it, after which the session is routed by `to` as after a restart.
- When a leg expires (§12.7 rule 3; spec-gap 132): a leg that has sent the relay no `progress`, `answer` or `reject`
  once the invite has expired is expired, so the relay can signal `transport.no-response` (rule 6); a leg that rang
  ends itself with `reject user.no-answer` at T-Ring-Local.

### A.14 From v0.16 to v0.17

v0.16 is final at tag `poc-v0.16`; v0.17 is final at tag `poc-v0.17`. v0.17 adds the Presence Profile (draft), the
core messages and fields it needs, and three Messaging Profile clarifications. Each item is listed with its spec-gap
number.

- The Presence Profile (`presence/0.1`, draft, cited `P§n`; spec-gaps 134–137): a device publishes its signed §9.4
  `presence` record to its authority (P§3); records are per device and a subscriber combines them by a fixed rule
  (P§4); presence states are an open registry with fallback `available` (P§5); presence never gates reachability
  (P§2). In the core: `presence` is a message (schema `presence.schema.json`), its record names its `device` (§9.4),
  its age is bounded by its own `expires_at` (§12.9), and the reason category `presence` is registered (§15).
- Expiry is exclusive everywhere (spec-gap 141, §12.9): a message is valid while `now < expires_at` and expired from
  `expires_at` on, at receipt and wherever a held message, a kept record or an activity is judged. Record ids that are
  kept and forwarded for their lifetime (`reachability-hint`, `presence`) are not deduplicated.
- Presence is private by default (spec-gap 144, §9.3): a grant from the target with `dsip.subscribe`, presented in
  `claims`, admits a presence subscriber; an authority with no policy and no admitting grant refuses, except the
  target's own devices.
- A grant MAY carry `presence_audience` (spec-gap 145, §19.4), and the new core message `grant-revocation` withdraws a
  grant before its `valid_until` (spec-gap 147, §19.4).
- A presence record names `presence/0.1` in `dsip.profiles` (spec-gap 142, §9.4); a processor of records lists it as
  supported (§11.2).
- A subscriber reaches the target's authority by binding there, at the relay its DID document names or, without one,
  the one its hint names, with the effects of any binding (spec-gap 143, §9.3).
- A presence target is *seen*, for the uniform reject, when it has bound within the authority's retention or the
  authority holds a policy or an issued capability for it (spec-gap 149, §9.3): a capability admits before its target
  first binds.
- An invite is admitted when its identity is the grantee of a live `dsip.invite` grant (spec-gap 151, §19.4); its
  `grant` field is a hint that never admits or refuses on its own, so an invite in flight that names a grant since
  replaced still gets through, and naming someone else's grant gets nobody in.
- A grant MAY follow a live grant without a new introduction (spec-gap 150, §19.4): its `session` names the grant it
  replaces, and the grantee holds it in place of the old one. A share's audience or length changes this way, and a
  share ends while calls stay.
- A relay that replaces a device's connection with a newer one says so on the old one, `error` `transport.replaced`
  (spec-gap 158, §13.2, §15), and the client does not reconnect: two connections of one device (two processes, two
  tabs) no longer replace each other in turn.
- Presence records MAY be sealed to subscribers (`presence/0.2`, P§12; spec-gaps 152–157, §9.4): the record carries
  `kid` and `sealed_state` in place of `state`, keys are derived from the identity's key agreement secret, and a grant
  MAY carry them as `presence_keys` (§19.4). The reason `presence.sealed-invalid` joins the `presence` category.
- Within the Presence Profile only: a device with no record this subscriber may see counts in the authority's
  assertion for that subscriber, so the body differs per subscription (spec-gap 146, P§4, P§6); presence has one
  path, through the authority, and none through messaging groups (spec-gap 148, P§11); grants that rotate
  keys form a chain revoked whole, newest first (spec-gap 159, P§12.5, P§7); a publisher leaves a margin over the
  authority's publish interval (spec-gap 160, P§8); an ending grant rotates the scopes it carried keys for (spec-gap
  161, P§12.5); a grant whose keys cannot be sealed or opened stands without them (spec-gap 162, P§12.3).
- In the Messaging Profile, three clarifications (Appendix M-B): an item whose processing fails is treated as
  processed (spec-gap 138, M§5.4); the successor check's roster counts every leaf's identity, lapsed or not (spec-gap
  139, M§7.5); a second key under an `akid` already held is ignored (spec-gap 140, M§12.1).

### A.15 From v0.17 to 1.0

v0.17 is final at tag `poc-v0.17`; 1.0 is final at tag `poc-v1.0`. 1.0 is the v0.17 text declared DSIP Core 1.0. No
message, field, rule, schema or vector changes: the core's state machine and envelope rules have stood unchanged
since v0.12, and every payload has carried `dsip.core` `1.0` and every schema the `$id` `…/schema/1.0/…` throughout.

- The document is normative 1.0 (header), and the snapshot is named for it: `v1.0/`, its schema set
  `dsip-schemas-v1.0/`.
- What a 1.x revision may change, and what needs 2.0 (spec-gap 163, §11.4): new message types, registry entries,
  profiles and extensions; a new field on an existing core message only through an extension or profile the receiver
  is known to support, since the schemas stay closed.
- The companion documents are carried unchanged: WebRTC Media Binding 1.0, Gateway Profile 1.0 and Messaging Profile
  1.0 stay normative, and the drafts (RTP/SRTP, DHT Hints, Alias Transparency, Device Events, Recording, Number
  Attestation, Presence) stay drafts. Each carries its own version.

### A.16 Within 1.0

Clarifications made in place after `poc-v1.0`, each allowed by §11.4: none changes what a 1.0 implementation accepts
or rejects.

- Messaging Profile 1.0: a mailbox's operator MAY end an enrolment, with the same effects as a release (spec-gap 164,
  M§4.1). It is a local action of the mailbox; nothing on the wire changes.
- Device Events Profile 1.0 (`device-events/1.0`, final at `poc-v1.0.2`; a draft until then, so §11.4 bounds it from
  here on). The core is unchanged; the profile's own rules settled before it became final:
  - a member refuses a `device-event` from a device whose delegation lacks `dsip.events` (spec-gap 165, E§2);
  - `device-event` and `alarm-ack` bodies have a minimal shape, and an unknown `alarm-ack` state is ignored (spec-gap
    166, E§5);
  - an inform's report drops a clear held for its alarm (spec-gap 167, E§4);
  - the gateway's SNMPv3 Reports and Responses are pinned byte for byte (spec-gap 168, E§3);
  - erratum: E§5's example objects carry the members every content object has (M§8.1).
- The Wake Profile (`wake/0.1`, draft, cited `W§n`; spec-gaps 169–175): how a device asks its relay (calls) and its
  mailbox (messages) to wake it through a push gateway (§13.3), with new message types (`wake-enrol`, `wake-accepted`,
  `wake-register`, `wake`), a `WakeRegistration` credential, a `wake` capability member in `hello` and the reason
  category `wake` (§15.1). A 1.0 receiver that does not implement it refuses the messages as unknown types; no core
  message, schema or rule changes. 116 `wake/` vectors.
- §9.3: a renewal, and `expires_in: 0`, match the subscribing device's subscription; two devices of one identity
  hold one each (spec-gap 177). Nothing on the wire changes; an authority that matched per identity replaced one
  device's subscription with another's.
- §7.3: a `did:key` identity's derived key agreement secret is its Ed25519 signing scalar, stated; and a **key
  agreement delegation**, an identity-signed `KeyAgreementDelegation` credential naming an independent X25519 key, so
  that devices open what is sealed to the identity without holding its signing key (spec-gap 179). The recipient key
  of §10.4, §19.4, M§6.9 and P§12 is then the document's `keyAgreement`, else the current delegation, else the derived
  key; the DHT Hints Profile's hint carries the delegation (`key_agreement`). A sender that does not implement it
  seals to the derived key as before, which only devices holding the identity key open; no 1.0 message changes.
  `key-agreement/` vectors.
- Messaging Profile 1.0, M§5.4: the cap on an `items` page is on the encoded envelope, so a page may hold fewer than
  `limit` items; a device whose mailbox sends an envelope over the cap syncs again with half the `limit`, never the
  same `sync` unchanged (spec-gap 180). Nothing on the wire changes; a device that does not do it loops on such a
  mailbox, as it did before.

---

## Appendix B: Emergency Services and Regulated Profiles

Emergency calling conflicts with pure decentralization. 911, 112, 999, NG911, and similar systems require regulated behavior: verified location, persistent identifiers, carrier or provider accountability, emergency service routing, lawful intercept rules in some jurisdictions, abuse prevention, call-back mechanisms, reliability obligations.

DSIP Core v1.0 does not claim to replace emergency calling. Emergency communication should be a future regulated DSIP profile with stricter identity, location, gateway, and compliance requirements.

**Gateway model.** A DSIP emergency profile likely requires carrier-class or public-authority gateways. This reintroduces centralization, but that is the regulatory reality of emergency communications.

**Location.** Location is not mandatory for all DSIP sessions, but may be mandatory for emergency profiles:

```
Normal DSIP sessions: location optional and privacy-preserving.
Emergency DSIP profile: verified location likely required.
Broadcast profile: location may be publisher metadata, not user metadata.
```

---

## Appendix C: SIP/PSTN Gateway Reality

A DSIP-to-SIP mapping table is only a small part of PSTN interop. A real gateway must handle:

- SIP INVITE/200 OK/ACK/BYE behavior
- SDP offer/answer mapping
- RTP/SRTP media anchoring
- E.164 numbering and number portability
- STIR/SHAKEN attestation, Rich Call Data, CNAM behavior
- Rate-center/routing requirements
- Emergency calling rules
- Lawful intercept obligations where applicable
- TCPA and robocall compliance where applicable
- Spam analytics and traffic labeling
- Reason code mapping (§15.5)
- Trust downgrade signaling
- Inbound early media mapping: classify announcements to reason tokens where possible; otherwise answer the DSIP leg (`answered_by: "gateway"`) and pass audio through

The honest principle carried in the core (§6.3): crossing into the PSTN is a trust downgrade unless the gateway can preserve and assert DSIP identity semantics through supported PSTN identity mechanisms. The companion Gateway Profile 1.0 turns this list into the requirements of a conformant gateway.

---

## Appendix D: Call Detail Records (informative)

(v0.13, spec-gap 121.)

Organisations often must keep a record of every call: who, when, for how long, and how it ended. DSIP has no
central switch that sees every call. The records come from the infrastructure the organisation runs, and DSIP's
signatures make them stronger than a switch's: each one can be checked against the signed messages it summarises.
This appendix says where records come from, what a relay record holds, and what it cannot cover. Recording content
is a separate matter, governed by the Recording Profile; lawful intercept is out of scope (§3, Appendix B).

### D.1 Where records come from

| Source | Sees | Does not see |
|---|---|---|
| The organisation's relay | every session message to or from a device bound to it (§13.2): type, `id`, `from`, `to`, `session`, `in_reply_to`, `issued_at`, `reason`, `status`, and the bodies unless sealed (§10.4); each leg of a forked invite (§12.7); which device holds which connection, from `hello` | calls of its devices bound elsewhere; media, which flows end to end or through TURN (B§) |
| The organisation's gateway | both legs of a PSTN call: the DSIP session and the SIP dialog, with the reason mapping of G§4 | DSIP-only calls |
| The organisation's mailboxes and hubs | deposits (sender device, group, class, size, time, seq), and the roster of each hubbed group, since commits are PublicMessages (M§6.4) | message content, which is MLS-encrypted |
| An endpoint the organisation controls | everything about its own calls, sent as `call-record` objects (Recording Profile C§9) | other devices' calls; it is trusted only as far as the organisation controls it |

The relay is the main source for calls, as a switch or SBC is in SIP networks. A call between two organisations
produces one record at each side's relay, as SIP peering does.

### D.2 A relay record

A relay keeps one record per session attempt, keyed by the session id (the invite's `id`, §12.2), and one sub-record
per leg. Every field comes from a message the relay routed:

| Field | Source |
|---|---|
| `session` | `invite.id` |
| `caller`, `caller_device` | the identity the invite's signer acts for (its delegation, §10.2) and the signing device (`from`) |
| `callee` | `invite.to` |
| `relay` | this relay's DID |
| `invited_at` | `invite.issued_at` |
| `legs[]` | per device the invite reached: `device`, `progress` (first `progress.status`, §12.10), `ended` (`reject`, `cancel`, expiry) with its `reason` |
| `answered_at`, `answered_device` | the applied `answer` (§12.7 rule 4): its `issued_at` and `from` |
| `answered_by` | `answer.answered_by` (§14.3), when not sealed |
| `ended_at`, `ended_by`, `reason` | the `bye`, `cancel` or attempt-ending `reject` or `error` (§12.7 rule 6): its `issued_at`, which side sent it, and its `reason` token (§15) |
| `outcome` | `answered`; or `cancelled` (the caller's `cancel`), `rejected` (the attempt outcome's `reason`), `no-response` (`transport.no-response`) |
| `media` | the media types of the applied answer, when not sealed (§10.4: `media` is sealable) |
| `recording` | the C§3 declarations seen, with their `recorder` and `purpose` |
| `evidence` | the signed envelopes, or their SHA-256 (D.4) |

Reason tokens are recorded as received, not mapped to numbers. A token outside the registry is kept as is, with its
category (§15.1).

### D.3 Time and duration

A record has two clocks. `issued_at` is the sender's clock, signed, and bounded by the replay window (§12.9): a
message more than the window away from the relay's clock is refused, so a signed time is within that window of the
relay's. The relay's own receive time is unsigned but consistent across the record. Records SHOULD keep both and
compute duration from the relay's receive times, from the applied `answer` to the session's end.

A session can end without a `bye`: a device that loses power sends nothing. The relay then ends the record when the
connection of either answered party closes (§13.2: either side MAY close after 90 s with no traffic and no Pong) and
marks `ended_by: transport`. A duration ending that way is an upper bound. For PSTN legs, the gateway's SIP times are
the billing times, as they are for the PSTN side today.

### D.4 Evidence

Every session message is signed by a device under a delegation from its identity (§7.4, §10.2). A record that
keeps the signed envelopes, byte for byte as received (§10.2: never re-serialised), can be checked later by anyone:
the caller's invite shows who called and when, the answer who answered on which device, the bye who ended it and
why. A record that keeps only the SHA-256 of each envelope can be matched against envelopes kept elsewhere, by the
peer's relay or by the endpoints.

Checking a signature later needs the key that made it, as it was then. Keys rotate (§7.5) and delegations expire or
are revoked (§7.4). A deployment that keeps evidence SHOULD keep, beside it, the delegation each envelope carried and
the identity's key-rotation records, or rely on a transparency log (§7.7).

### D.5 Sealed bodies

`sealed-body/1.0` (§10.4) seals bodies but never what relays route and track by: `type`, `id`, `from`, `to`,
`session`, `in_reply_to`, `issued_at`, `expires_at`, `reason`, `retry_after` and `status` stay in clear. Every field
of D.2 except `answered_by`, `media` and the declarations survives sealing. A record of a sealed session says who
called whom, when, who answered, how long and why it ended, but not with what media.

### D.6 What a relay record cannot cover

- **Calls on other relays.** A device MAY connect to several relays (§13.2), and a device away from the office may
  bind elsewhere. Nothing in the protocol pins a delegated device to its organisation's relay. Deployment policy can
  (client configuration, network policy), and the protocol cannot enforce it. The Recording Profile's call records
  (C§9) cover these calls from the endpoint side: each device sends its organisation's record-keeper a record of every
  leg, on any relay, and the relay's records are the cross-check.
- **Media.** The relay sees negotiation, not media. Whether media actually flowed, and for how long, is known only to
  the endpoints and to any TURN server that relayed it.
- **Content.** Recording what was said is the Recording Profile's: disclosed, at endpoints the organisation controls,
  never by decrypting at relays.

### D.7 Messaging

A mailbox or hub record holds deposits: the depositing device and the identity it acts for, the group, the class
(`application`, `handshake`, `welcome`, `group-info`, …), the size, the time, and the hub's `seq`. A hub also sees
each group's roster, because commits are PublicMessages it validates (M§6.4). Content stays MLS-encrypted. An
organisation that must keep message content uses a recorder device in its members' conversations (C§5), which is
disclosed to every member.

### D.8 Privacy

Call records are personal data, and they reveal the relationships §20.7 says relays already learn. DSIP does not
require a per-call disclosure for records of what an organisation's own relay or gateway routes, as SIP networks do
not; an organisation discloses its records policy as a standing notice and keeps them under its jurisdiction's
retention rules. Recording content needs the per-call declaration of the Recording Profile (C§3). An endpoint-side
record sent to the organisation (C§9) holds no more than the party's own relay sees, and needs no per-call
declaration either.
