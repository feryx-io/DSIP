# DSIP: an overview

October 2026 · James Ferris

## What DSIP is

DSIP, the Decentralized Session Initiation Protocol, is a protocol for setting up calls, video sessions, broadcasts and messaging between parties who can prove who they are, before any media flows. It takes its ideas from SIP but is not wire-compatible with it, and it is not limited to telephony.

In the phone network, and in most SIP deployments, the carrier is the authority: it assigns your number, routes your calls and vouches (or fails to vouch) for who is calling. DSIP moves that authority to the parties themselves:

- **You are a key, not a number.** Every party has a decentralized identifier (DID) that it controls. Every message is signed, so a receiver checks who sent it rather than trusting the network.
- **Servers carry traffic but vouch for nothing.** Relays, mailboxes and DHT nodes move and store messages. None of them can impersonate a user, and none of them is an authority on who a user is.
- **The receiver decides before media flows.** A call arrives with a verified identity, its trust tier, and its policies on recording, transcription and AI processing. Media starts only after a signed answer.

**Status.** The current revision is DSIP Core 1.0, final in October 2026: the v0.17 text declared normative 1.0, with a stated rule for what a later 1.x may change (§11.4). Its wire protocol has been version `1.0` throughout, and its state machine and envelope rules have not changed since v0.12. The core, the WebRTC Media Binding, the Gateway Profile and the Messaging Profile are normative 1.0 text. Seven further profiles are drafts. A suite of 2,325 language-neutral test vectors pins the behaviour, and three implementations (Python, Rust and TypeScript) agree on every vector.

## How it works

DSIP rests on three ideas: identities are DIDs, devices act for an identity under a signed delegation, and every message is a signed envelope that anyone can verify.

### Identity and devices

An **identity** is a DID such as `did:web:example.com:alice` (a document hosted on a domain), `did:webvh` (a domain-hosted document with a verifiable history the host cannot forge) or `did:key` (a bare public key). The identity's **DID document** is the authority for its keys and for where it can be reached.

The identity's controller key stays off everyday devices. Instead it signs a **delegation** for each device (phone, laptop, browser, media server, AI agent): a short-lived credential saying "this device key may signal and carry media for me". Devices sign with their own keys, so a lost phone is revoked without replacing the identity.

### Signed messages

Every DSIP message is a **DSIP-JOSE envelope**: a JSON payload signed with Ed25519 (JWS). The signature covers the exact bytes sent, and a receiver checks it, the delegation behind it, a 300-second replay window and the payload's shape before acting on anything. Envelopes are signed, not encrypted, but the `sealed-body` extension encrypts the fields a relay has no need to read: SDP, ICE candidates, display names and DTMF digits.

### Finding someone

Discovery follows a strict authority order: the DID document, then an alias resolved to a DID (`alice@example.com`), then a local cache, then **hints**. Hints are signed, expiring reachability records found on a DHT. They help a caller find a relay, and they are never trusted for identity.

### A call, end to end

1. Alice's device resolves Bob's DID and finds his **relay** in his DID document (or, for a `did:key`, in a hint).
2. Each device keeps a WebSocket open to its relay (`ws/1.0`, TLS 1.3). It opens with a signed `hello` that binds the connection to the device and its delegation.
3. Alice's device sends a signed `invite` carrying her identity claims, a media offer (WebRTC SDP) and her session policy.
4. Bob's relay **forks** the invite to each of Bob's devices. Each device verifies Alice and shows her identity and trust tier, and the relay passes `progress` (ringing) back to Alice.
5. The first device to `answer` wins. Alice cancels the other legs, and the answer's `answered_by` says who or what answered: `user` (Bob himself), `service` (voicemail or an AI assistant), `screening` or `gateway`. Clients must show a voicemail answer differently from Bob's.
6. ICE candidates travel in signed `info` messages, and media flows directly between the devices (or via TURN) only after the signed answer. There is no early media.
7. Either side ends the call with `bye`. Every refusal carries a structured reason code such as `policy.rate-limited` or `session.answered-elsewhere`.

A stranger cannot simply ring Bob. Their first contact is an `introduction`: at most 4,096 bytes, rate-limited, with no media. Bob can answer it with a signed `grant` that lets them call.

### A message, end to end

Messaging uses the same identities. Each conversation is an **MLS group** (RFC 9420) whose members are devices, so it is end-to-end encrypted across every device each person has.

1. Alice's device encrypts the message and deposits it at her **mailbox**.
2. The conversation's **hub** (one of the members' mailboxes) gives it the next sequence number and fans it out to every member's mailbox.
3. Bob's mailbox pushes it at once to his online devices and holds it for the others until they sync. Mailboxes store only ciphertext.

**What a mailbox keeps.** Every message is deposited, even when the recipient is online: push is the fast path, not a fallback, so there is no "try live, then store" race. A mailbox deletes a message only once every one of the owner's devices has acknowledged processing it, not when it sends it, so a device that crashes mid-delivery gets it again. A device that has been away longer than the retention bound (30 days recommended) is no longer waited for; when it returns it rejoins its conversations instead of replaying the backlog. The owner picks what happens after every device has acknowledged:

- **`queue`**: the message is deleted. Nothing is kept, and a device added later sees no history.
- **`sync`** (the default): content is also kept as encrypted archive items for the owner's retention period, within the operator's limit, so a device added later can rebuild the history.

Typing indicators and other activity are never stored; they reach only the devices connected at that moment.

## The components

Every component below is itself a DSIP identity that signs what it sends. None is an authority on who anyone else is: that stays with each identity's DID document.

![Servers carry signed traffic; identity stays with the DID document. Discovery in authority order (DID document, alias provider and log, DHT hints nodes); Alice's devices send a signed invite to the relay, which forks it to each of Bob's devices; media flows after the signed answer, directly or via TURN; messages go from Alice's devices to her mailbox (the hub), then to Bob's mailbox, which pushes or holds them for his devices.](overview.svg)

Calls go device to relay to every device of the callee, with media flowing directly once answered. Messages go through mailboxes, with one mailbox acting as the conversation's hub. A gateway (not drawn) joins a call to SIP or the PSTN.

### Parties

| Component | What it is | What it is trusted with |
| --- | --- | --- |
| **Identity** | A person, organisation, service or broadcaster, named by a DID. Its DID document lists its keys, its relay (`DSIPSignaling`) and its mailbox (`DSIPMailbox`). | It is the authority on itself. |
| **Controller key** | The identity's root key. It signs delegations, key rotations and revocations, and should live off everyday devices. | Everything the identity can do. |
| **Device** | A phone, browser, desktop, media server or AI agent acting for an identity under a delegation, with its own key and its own DID. | What its delegation's capabilities allow (`dsip.signaling`, `dsip.media.interactive`, `dsip.messaging`, `dsip.record`). |
| **Delegation** | A signed, expiring credential from the identity to a device. It can be revoked early with a `delegation-revocation`. | Not applicable: it is a credential, not a party. |

### Services that carry calls

| Component | What it does | What it can see |
| --- | --- | --- |
| **Relay** | The identity's signaling server. Devices hold a WebSocket to it; it routes envelopes by recipient, forks invites to every device, holds envelopes for offline devices for a bounded time, and serves presence and broadcast subscriptions. A relay may be open, private or closed. | Who talks to whom and when. Without `sealed-body`, also SDP, ICE candidates and display names. It cannot forge a message. |
| **STUN / TURN server** | Standard WebRTC NAT traversal. TURN relays media when two devices cannot connect directly. Clients get short-lived TURN credentials by configuration, not through DSIP signaling. | Encrypted media packets and IP addresses. |
| **Gateway** | A back-to-back user agent between DSIP and SIP/PSTN. It maps reason codes, SDP and caller identity across, and marks the crossing as a trust downgrade unless it can carry the identity through (STIR/SHAKEN). | Both sides of the call, including media. |
| **Group focus** | A conference service (an SFU) that is itself a DSIP endpoint with a service identity. Multi-party calls join it. | The media it mixes or forwards. |

### Services that carry messages

| Component | What it does | What it can see |
| --- | --- | --- |
| **Mailbox** | A service identity that stores encrypted deposits for the identities it serves, pushes them to their online devices, and serves their MLS key packages and file blobs. It may share a server and an identity with a relay. | Ciphertext and routing metadata only. It cannot read messages or impersonate its owner. |
| **Hub** | The mailbox that orders one conversation: it gives each message its sequence number, settles which membership change wins, and fans every message out to the members' mailboxes. A hub is a role a mailbox plays for a group, not a separate server. | Ciphertext, the group's device list and its timing. |

### Discovery services

| Component | What it does | What it is trusted with |
| --- | --- | --- |
| **DHT / hints node** | A node on a distributed hash table that stores and serves **reachability hints**: signed, expiring records of which relay an identity can currently be reached at. Hints help `did:key` identities and devices that have moved. They also travel on Pkarr (the BitTorrent Mainline DHT). | Nothing: every hint is checked against the identity's keys and treated as a hint, never as authority. |
| **Alias provider** | The domain behind an alias such as `alice@example.com`, which resolves it to a DID (for example via WebFinger). | Availability always. With the Alias Transparency Profile, not correctness: it must prove each answer against a public log. |
| **Transparency log** | The alias provider's append-only log, built on IETF KEYTRANS. Clients check lookups against it, alias owners monitor their own entry, and peers compare tree heads to catch a provider that shows different answers to different people. Aliases are blinded, so the log cannot be used to list users. | Nothing beyond what it can prove. |
| **Number issuer** | A telephone-number holder that signs a binding from an E.164 number to a DID (Number Attestation Profile), so a number can lead to a DSIP identity. | The binding it signed. |

### Profile-specific roles

| Component | Profile | What it does |
| --- | --- | --- |
| **Broadcaster** | Verified Broadcast | An identity that publishes signed records for a live stream, so viewers can verify who published it. A **provenance processor** (a transcoder, a captioner) attaches its own signed statement to the publication. |
| **Recorder** | Recording | A device whose delegation carries `dsip.record`. Every other party is shown the disclosure and asked to accept before recording. |
| **Record-keeper** | Recording | An organisation's service identity that collects metadata-only call records from its devices, for compliance. |
| **Device-events gateway** | Device Events | Turns SNMP traps and syslog from network equipment into signed events in an encrypted alarm group. An **escalation agent** calls the on-call person when an alarm goes unacknowledged. |

## The documents

The specification is a small core plus companion profiles, each cited by its own section prefix. Four documents are normative 1.0; the rest are drafts that implementations should treat as subject to change.

| Document | Prefix | Status | What it covers |
| --- | --- | --- | --- |
| [DSIP core](../v1.0/dsip_v_1_0_decentralized_session_initiation_protocol.md) | §n | 1.0 | Identity, discovery, envelopes, the call state machine, the `ws/1.0` relay binding, reason codes, first contact, Verified Broadcast |
| [WebRTC Media Binding](../v1.0/dsip-webrtc-media-binding-v1.0.md) | B§n | 1.0 | How WebRTC media (ICE, DTLS-SRTP, SDP) rides DSIP, and how media is tied to the signed identity |
| [Gateway Profile](../v1.0/dsip-gateway-profile-v1.0.md) | G§n | 1.0 | Interworking with SIP and the PSTN |
| [Messaging Profile and Mailbox](../v1.0/dsip-messaging-profile-v1.0.md) | M§n | 1.0 | Mailboxes, hubs, MLS groups, content, voicemail, history |
| [RTP/SRTP Media Binding](../v1.0/dsip-rtp-srtp-media-binding-v1.0-draft.md) | R§n | Draft | Non-WebRTC RTP media, as SIP trunks use |
| [DHT Reachability Hints](../v1.0/dsip-dht-hints-profile-v1.0-draft.md) | (core §8.5) | Draft | Hint records, the DSIP overlay DHT and Pkarr |
| [Alias Transparency](../v1.0/dsip-alias-transparency-profile-v1.0-draft.md) | T§n | Draft | Auditable alias lookups on KEYTRANS; proof checking waits for KEYTRANS -06 |
| [Number Attestation](../v1.0/dsip-number-attestation-profile-v1.0-draft.md) | N§n | Draft | Binding phone numbers to DIDs; a live trial needs a pilot partner |
| [Recording](../v1.0/dsip-recording-profile-v1.0-draft.md) | C§n | Draft | Recording with consent, and metadata-only call records |
| [Device Events](../v1.0/dsip-device-events-profile-v1.0.md) | E§n | 1.0 | Network alarms (SNMP, syslog) delivered as encrypted messages |
| [Presence](../v1.0/dsip-presence-profile-v1.0-draft.md) | P§n | Draft | A device's signed presence published to its authority, several devices combined into one presence |

JSON Schemas for every message ship beside the core and the Messaging Profile.

## What DSIP does not do

The core states its limits outright (§4), so that nobody builds on a guarantee it does not make:

- **No universal anti-spam system.** It gives trust tiers, introductions, grants and mandatory rate limits; deciding who may ring stays with the receiver.
- **No trust in anonymous identities by default.** Anyone can mint a `did:key`; it starts at the lowest trust tier.
- **No authority in the DHT.** Hints are reachability only. Sybil resistance is measured, not claimed solved.
- **No decentralized emergency calling,** and no enforcement of AI disclosure: there is a mechanism for disclosing AI processing (§18.4), but the protocol cannot prove a party used it honestly.
- **No blockchain and no single global registry.**
- **No signaling over UDP, and no early or delayed media.** Media never flows before a signed answer, and every invite carries an offer.
- **No replacement for media transports.** WebRTC and RTP carry the media; DSIP negotiates and authenticates them.
- **Not yet in core:** call transfer, conference moderation, device control and emergency priority are left to future profiles.

## Status and getting involved

DSIP is a complete, tested draft looking for reviewers and independent implementers. It is not yet a standard: no implementer outside the project has built it, and its own security mechanisms have not had outside review.

**How conformance works.** The test vectors are the contract. Each vector is a language-neutral JSON file: a message or a sequence of events, and the outcome the spec requires, written by hand from the spec text and never recorded from an implementation. An implementation passes when it produces every expected outcome. Three runners agree on all 2,130 today:

| Implementation | Language | How it was written |
| --- | --- | --- |
| Reference harness | Python | Alongside the vectors |
| Reference implementation ([dsip-rs](https://github.com/feryx-io/dsip-rs)) | Rust | From the spec; runs real calls, messaging, a gateway and DHT nodes over the internet |
| Second implementation | TypeScript | From the spec, the schemas and the vectors README only, without reading the other two |

A differential fuzzer also drives random message sequences through all three and compares what they do. Every disagreement it finds becomes a hand-written vector or a recorded spec decision; 132 such decisions are on record.

**What would help most:**

- **An independent implementation,** in any language, measured against the vectors. A failing vector is either your bug or a spec bug, and both are worth reporting.
- **Security review** of envelope signing, delegation and revocation, relay anti-splicing, and the first-contact anti-enumeration rules. The underlying standards (MLS, JOSE, DIDs) are established; DSIP's use of them is not yet reviewed.
- **Use cases for the next profiles:** call transfer, conferencing, and identity recovery.

**Where to start.** The current documents are in [`v1.0/`](../v1.0/), starting with its [README](../v1.0/README.md); the vectors and their [README](../impl/vectors/README.md), which defines the order checks run in, are in [`impl/vectors/`](../impl/vectors/).

**Licences.** The specification documents are under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): anyone may copy, adapt and build on them with attribution. The code, JSON Schemas and test vectors are under MIT or Apache-2.0, at the user's option, so any implementation, open or closed, can embed the schemas and run the vector suite.
