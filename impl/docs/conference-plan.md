# DSIP Video Conferencing Plan

**Tracks:** DSIP Core 1.0 (§17.4 small-group model), WebRTC Media Binding 1.0, Messaging Profile 1.0
**Status:** Parked (2026-11-14). Resumes once the core is stable: one-to-one video calls (video plan phases 2–4)
shipped and tested on devices.
**Repositories:** DSIP (spec, vectors, harness, impl-ts), dsip-rs (focus service, media), dsip-app (UI)

---

## 1. Goal and what "decentralized" means here

Meetings of several people with video, screen sharing and recording, the way Zoom and Webex hold them, without a
central account system or a single operator:

- **Identities are DIDs.** Nobody's account lives on the conference provider.
- **Anyone can run the conference server** (a *group focus*, §17.4): a person, a company, a community. A meeting
  names its focus by DID; participants verify it, and it verifies them.
- **The focus is replaceable and, eventually, untrusted with media**: with end-to-end encryption (phase 4) it
  forwards packets it cannot read.

Not claimed: no servers. A focus, TURN and relays still run somewhere. The focus sees who joins, when, and how much
each sends, even with end-to-end encryption.

## 2. What exists

| Piece | Where | State |
|---|---|---|
| Group model: a focus is an ordinary endpoint; a meeting is N one-to-one sessions | Core §17.4 | normative, 1.0 |
| Video in a call: H.264 CB (MUST), VP8, loss repair, per-call video | B§3.4, dsip-rs v2026.11.14 | released |
| Stream switching for a forwarding server (`StreamRewriter`, RTX, keyframe gating) | forge-media `forge-rtp::video` | used by Anvil's video rooms |
| Screen capture (X11, PipeWire, SCK, DXGI, MediaProjection, ReplayKit) | anvil-video | in Anvil |
| Group keys (MLS, RFC 9420) | dsip-rs messaging | released (conversations) |
| Recording with consent and disclosure | Recording Profile (draft, C§) | vectors, dsip-rs |
| One-to-many events | Verified Broadcast (§22) | 1.0 |
| Reserved: `group-roster/1.0`, `sframe-e2ee/1.0` | Core §6.2, §17.4 | names only |

## 3. Phases

Each phase ends in a demo, and follows the PoC's rules: vectors before code (spec work first in DSIP, three-way
parity), `Spec:`/`Impl:` lines, spec-gaps for every choice the text leaves open.

### Phase C1 — a focus service (no spec change)

A `dsip-focus` service in dsip-rs, beside the relay and mailbox: a `service`-class identity (§7.1) that answers
calls to a meeting.

- A meeting is a resource of the focus (`did:…#meeting-<id>` or an invite field; choice → spec-gap). Calling it
  joins; `bye` leaves.
- Media: one leg per participant (dsip-media), audio mixed or forwarded, video forwarded as a selective forwarding
  unit (SFU): the active speaker at full quality, the rest as thumbnails (simulcast is out of scope in B§1, so the
  focus asks each sender for one layer and switches with `StreamRewriter`, asking for keyframes on switch).
- Bandwidth: REMB from the focus to each sender; per-receiver limits.
- Packages like the other services (static binary, .deb, image, one-host compose).
- **Demo:** three apps in one meeting through a local focus; then the WAN testbed.
- **Tests:** an in-process meeting (testkit network, synthetic video): each participant receives the others' audio
  and the speaker's video; leaving ends one session only.

### Phase C2 — the roster: `group-roster/1.0` (spec first)

Who is in the meeting, and who may do what. A profile on top of §17.4, carried as `info` (or `notify`) from the
focus to each participant, signed by the focus:

- roster: participants (DID, display name as a claim, devices), joined/left events, who speaks;
- roles: host, participant; host actions: mute, remove, lock, admit from a waiting room;
- what the focus asserts about participants is the focus's claim (§17.4 consequence), shown as such.

Spec work: the profile text, schemas, registry entries (roster events, reason tokens such as `policy.removed`),
vectors (roster traces, host-action authorization), Python, impl-ts, dsip-rs. Spec-gaps for each open choice
(e.g. ordering of roster events across reconnects, a host leaving).

- **Demo:** a host mutes and removes a participant; every app's roster agrees.

### Phase C3 — the app's meeting UI

- A grid of tiles (one texture per stream, the existing tile path), active speaker large, self-view.
- Meeting links: a message carrying the focus DID and meeting id (a new content kind or a `contact`-like object;
  Messaging Profile choice → spec-gap), "join with camera off", a pre-join check of camera and microphone.
- Screen sharing: anvil-video's capture as a second video section (`a=content:slides`, forge supports it).
- Mobile: background audio-only, bandwidth limits on cellular.
- **Demo:** Android and Windows in a meeting with screen sharing.

### Phase C4 — end-to-end encryption: `sframe-e2ee/1.0` (spec first)

Media the focus forwards but cannot read:

- Keys from an MLS group whose members are the meeting's participants (the messaging stack's MLS); the focus is not
  a member. Joins and leaves are MLS commits; the media key ratchets with each epoch.
- SFrame (RFC 9605) per frame, inside the RTP payload, so the focus still forwards and switches.
- Who distributes Welcome messages and commits (the focus as delivery service, never as member), and what the roster
  shows as "verified end to end".
- Spec work: the extension, its negotiation (`dsip.extensions`), vectors for key schedule and epoch changes.
- **Demo:** a packet capture at the focus shows only ciphertext; a participant removed can no longer decrypt.

### Phase C5 — scale and events

- Focus cascading (focus-to-focus legs) for meetings past one server's capacity.
- Webinars: Verified Broadcast for one-to-many with a small interactive panel.
- Recording through the Recording Profile (a recorder participant; consent shown to everyone).

## 4. Dependencies and order

1. Core stable first: one-to-one video (video plan phases 2–4) shipped and tested on devices.
2. C1 needs nothing new in the spec; C2 and C4 start in DSIP (vectors before code).
3. C3 can follow C1 with a minimal roster from the focus's own state, replaced by C2's.
4. C4 depends on C2 (who is in the group is the roster).

## 5. Risks and open questions

- **Bandwidth and CPU on the focus**: forwarding is cheap, but one layer per sender (no simulcast in B§1) makes
  thumbnails expensive for senders on poor links; simulcast may need a binding revision.
- **Mobile**: decoding several streams on phones; background rules on Android and iOS.
- **E2EE and recording** pull against each other: a recorder must be an MLS member and disclosed (C§).
- **Abuse**: open meetings need admission control (waiting room, host-only invite), which the roster profile must
  carry.
- **Interop**: a browser joining needs the web client to do SFrame (WebRTC encoded transforms).
