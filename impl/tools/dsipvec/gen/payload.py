"""Payload (schema) vectors — every schema gets ≥1 accept and ≥1 reject (spec §10.3; schema README)."""
from __future__ import annotations

import copy

from .. import fixtures as F
from .common import (NOW, invite, hello_client, hello_relay, session_msg, vector, accept, reject, uid,
                     MEDIA_OFFER, AUDIO_SELECTION, ONE_TRANSPORT)

APH, BPH = F.did("alice-phone"), F.did("bob-phone")
V = F.VERSION
BCAST_V = {"core": "1.0", "min_core": "1.0", "profiles": ["verified-broadcast/1.0"],
           "extensions": [], "critical": []}


def pv(vid, schema, desc, refs, payload, ok=True):
    return vector(f"payload/{vid}", "payload", desc, refs, {}, {"schema": schema, "payload": payload},
                  accept() if ok else reject("schema-invalid"))


def vectors() -> list[dict]:
    out = []
    inv = invite()
    sid = inv["id"]

    # invite
    out.append(pv("invite-valid", "invite", "Complete invite with media offer, transports, identity, policy.", ["§12.1", "§14.2"], inv))
    out.append(pv("invite-offerless", "invite", "Invite without media: schema rejects (media.offer-required at the semantic layer).",
                  ["§14.2"], {k: v for k, v in inv.items() if k != "media"}, ok=False))
    out.append(pv("invite-no-transports", "invite", "Invite without transports.", ["§14.2"],
                  {k: v for k, v in inv.items() if k != "transports"}, ok=False))
    out.append(pv("invite-codec-bare-string", "invite", "Codec entries must be objects, not bare strings (resolves §15.3 vs §16.2).",
                  ["§16.2"], {**inv, "media": [{"type": "audio", "direction": "sendrecv", "codecs": ["codec:audio/opus"]}]}, ok=False))
    out.append(pv("invite-bad-direction", "invite", "Unknown media direction.", ["§16.2"],
                  {**inv, "media": [{"type": "audio", "direction": "both", "codecs": [{"id": "codec:audio/opus"}]}]}, ok=False))
    out.append(pv("invite-float-timestamp", "invite", "Non-integral timestamp fails the integer type. (Integral floats like 1760000000.0 "
                  "satisfy JSON Schema's `integer`; they are caught at parse — see envelope/payload-float-timestamp.)", ["§10.3"],
                  {**inv, "issued_at": NOW + 0.5}, ok=False))
    out.append(pv("invite-version-block-missing-critical", "invite", "Version block without critical array.", ["§11.1"],
                  {**inv, "dsip": {k: v for k, v in V.items() if k != "critical"}}, ok=False))
    out.append(pv("invite-unknown-top-level-field", "invite", "Unknown top-level field: invite schema is closed.", ["§10.3"],
                  {**inv, "surprise": True}, ok=False))
    out.append(pv("invite-policy-bad-value", "invite", "Policy value with uppercase fails the registered-token shape.", ["§16.4"],
                  {**inv, "policy": {"recording": "Consent-Required"}}, ok=False))
    out.append(pv("invite-with-grant-ref", "invite", "Invite referencing a contact grant id.", ["§19.4"],
                  {**inv, "grant": uid("grant")}))
    out.append(pv("invite-destination-tel", "invite", "A tel URI destination: the PSTN number asked of a gateway (Number "
                  "Attestation N§4.1; spec-gap 111).", ["N§4.1", "G§3.1"], {**inv, "destination": "tel:+15552000001"}))
    out.append(pv("invite-destination-not-tel", "invite", "A destination that is not an E.164 tel URI.", ["N§4.1"],
                  {**inv, "destination": "sip:+15552000001@gw.example"}, ok=False))
    out.append(pv("invite-accessibility-purpose", "invite", "Media descriptor with a registered purpose (sign-language).", ["§21.3"],
                  {**inv, "media": MEDIA_OFFER + [{"type": "video", "purpose": "sign-language", "direction": "sendrecv",
                                                    "codecs": [{"id": "codec:video/av1"}]}]}))

    # progress
    prog = session_msg("progress", "prog", sid, BPH, APH, NOW + 1, status="ringing", ring_timeout=120)
    out.append(pv("progress-ringing", "progress", "Ringing progress with ring_timeout.", ["§12.10"], prog))
    out.append(pv("progress-queued-valid", "progress", "Queued progress with queue_timeout.", ["§12.10"],
                  {**prog, "status": "queued", "queue_timeout": 600}))
    out.append(pv("progress-queued-missing-timeout", "progress", "queued REQUIRES queue_timeout.", ["§12.10"],
                  {**prog, "status": "queued"}, ok=False))
    out.append(pv("progress-queue-timeout-over-cap", "progress", "queue_timeout above the 1800 s core cap.", ["§12.10", "§12.9"],
                  {**prog, "status": "queued", "queue_timeout": 3600}, ok=False))
    out.append(pv("progress-ring-timeout-below-bound", "progress", "ring_timeout below the 30 s lower bound.", ["§12.9"],
                  {**prog, "ring_timeout": 10}, ok=False))
    out.append(pv("progress-unknown-status-shape-ok", "progress", "Unregistered but well-formed status passes the schema (fallback is semantic).",
                  ["§12.10"], {**prog, "status": "pondering"}))
    out.append(pv("progress-missing-session", "progress", "Session-scoped message without session.", ["§12.2"],
                  {k: v for k, v in prog.items() if k != "session"}, ok=False))

    # answer
    ans = session_msg("answer", "ans", sid, BPH, APH, NOW + 5, answered_by="user", media=AUDIO_SELECTION, transports=ONE_TRANSPORT)
    out.append(pv("answer-valid", "answer", "Answer with selection and exactly one transport.", ["§14.1", "§14.2"], ans))
    out.append(pv("answer-screening", "answer", "Screening answer with recvonly audio.", ["§14.4"],
                  {**ans, "answered_by": "screening",
                   "media": [{"type": "audio", "direction": "recvonly", "codecs": [{"id": "codec:audio/opus"}]}]}))
    out.append(pv("answer-missing-answered-by", "answer", "answered_by is required.", ["§14.3"],
                  {k: v for k, v in ans.items() if k != "answered_by"}, ok=False))
    out.append(pv("answer-two-transports", "answer", "An answer is a selection: exactly one transport.", ["§14.2"],
                  {**ans, "transports": ONE_TRANSPORT + [{"id": "transport:rtp-sdes"}]}, ok=False))
    out.append(pv("answer-update-reply", "answer", "Answer to an update via in_reply_to.", ["§12.8"], {**ans, "in_reply_to": uid("upd")}))
    out.append(pv("answer-unknown-answered-by-shape-ok", "answer", "Unregistered answered_by passes the schema (renders as service).",
                  ["§14.3"], {**ans, "answered_by": "butler"}))

    # reject / cancel / bye
    rej = session_msg("reject", "rej", sid, BPH, APH, NOW + 5, reason="user.declined")
    out.append(pv("reject-valid", "reject", "Reject with a registered reason.", ["§15.2"], rej))
    out.append(pv("reject-with-detail-retry", "reject", "Reject with detail and retry_after.", ["§15.2"],
                  {**rej, "reason": "endpoint.busy", "detail": "In another call", "retry_after": 120}))
    out.append(pv("reject-flat-token", "reject", "Legacy flat token lacks the category.condition shape.", ["§15.1"],
                  {**rej, "reason": "declined"}, ok=False))
    out.append(pv("reject-extension-namespace", "reject", "Extension-namespace token passes the shape rule.", ["§15.6"],
                  {**rej, "reason": "x-contactcenter.queue-full"}))
    out.append(pv("reject-missing-reason", "reject", "reason is required.", ["§15.2"],
                  {k: v for k, v in rej.items() if k != "reason"}, ok=False))
    can = session_msg("cancel", "can", sid, APH, F.BOB_WEB, NOW + 6, reason="user.cancelled")
    out.append(pv("cancel-valid", "cancel", "Cancel with user.cancelled.", ["§12.11"], can))
    out.append(pv("cancel-detail-too-long", "cancel", "detail above 1024 chars.", ["§15.2"], {**can, "detail": "x" * 1025}, ok=False))
    bye = session_msg("bye", "bye", sid, APH, BPH, NOW + 300, reason="user.hangup")
    out.append(pv("bye-valid", "bye", "Normal hangup.", ["§12.1"], bye))
    out.append(pv("bye-no-session", "bye", "bye without session.", ["§12.2"], {k: v for k, v in bye.items() if k != "session"}, ok=False))

    # update / info
    upd = session_msg("update", "upd", sid, BPH, APH, NOW + 60, answered_by="user",
                      media=[{"type": "video", "direction": "sendrecv", "codecs": [{"id": "codec:video/h264"}]}])
    out.append(pv("update-valid-escalation", "update", "Screening → user escalation update with video offer.", ["§12.8", "§14.4"], upd))
    out.append(pv("update-no-media", "update", "update MUST carry a media offer.", ["§12.8"],
                  {k: v for k, v in upd.items() if k != "media"}, ok=False))
    info = session_msg("info", "info", sid, BPH, APH, NOW + 6, about="transport:webrtc",
                       data={"candidates": [{"candidate": "candidate:1 1 udp 1 203.0.113.7 61481 typ srflx",
                                             "sdp_mid": "0", "sdp_m_line_index": 0}], "end_of_candidates": False})
    out.append(pv("info-valid-ice", "info", "info carrying trickle ICE candidates.", ["§12.12"], info))
    out.append(pv("info-missing-data", "info", "data is required.", ["§12.12"], {k: v for k, v in info.items() if k != "data"}, ok=False))
    out.append(pv("info-bad-about", "info", "about must be namespace:value.", ["§12.12"], {**info, "about": "webrtc"}, ok=False))
    # WebRTC Media Binding, Appendix A (v0.7, spec-gap 16): info.data is validated for about = transport:webrtc
    out.append(pv("info-webrtc-missing-mid", "info", "A webrtc candidate without sdp_mid fails the binding's data schema.", ["§12.12", "§16.3"],
                  {**info, "data": {"candidates": [{"candidate": "candidate:1 1 udp 1 203.0.113.7 61481 typ srflx"}], "end_of_candidates": False}}, ok=False))
    out.append(pv("info-webrtc-end-only", "info", "An empty batch with end_of_candidates true is the end-of-gathering marker.", ["§12.12"],
                  {**info, "data": {"candidates": [], "end_of_candidates": True}}))
    # DTMF (spec-gap 70): the same vehicle, a registered about and its own data shape
    dtmf = {**info, "about": "media:dtmf", "data": {"digits": "12#", "duration_ms": 160}}
    out.append(pv("info-dtmf-valid", "info", "DTMF digits carried in an info within an established session.", ["§12.12"], dtmf))
    out.append(pv("info-dtmf-digits-only", "info", "duration_ms is optional; the digits are what matter.", ["§12.12"],
                  {**dtmf, "data": {"digits": "5"}}))
    out.append(pv("info-dtmf-bad-digit", "info", "Only RFC 4733 events: 0-9, *, #, A-D.", ["§12.12"],
                  {**dtmf, "data": {"digits": "1E"}}, ok=False))
    out.append(pv("info-dtmf-empty", "info", "An info that carries no digit says nothing.", ["§12.12"],
                  {**dtmf, "data": {"digits": ""}}, ok=False))
    out.append(pv("info-dtmf-too-long", "info", "At most 32 digits in one info.", ["§12.12"],
                  {**dtmf, "data": {"digits": "1" * 33}}, ok=False))
    out.append(pv("info-dtmf-duration-too-short", "info", "An RFC 4733 event lasts at least 40 ms.", ["§12.12"],
                  {**dtmf, "data": {"digits": "1", "duration_ms": 39}}, ok=False))
    out.append(pv("info-dtmf-extra-field", "info", "The binding's data carries digits and duration, nothing else.", ["§12.12"],
                  {**dtmf, "data": {"digits": "1", "tone": "ring"}}, ok=False))
    out.append(pv("info-other-about-data-unchecked", "info", "data for an about the receiver does not implement is not validated (unknown about is ignored, never rejected).", ["§12.12"],
                  {**info, "about": "transport:other", "data": {"anything": 1}}))

    # error
    err = {"dsip": F.VERSION_TRANSPORT, "type": "error", "id": uid("err"), "from": F.RELAY_WEB, "to": APH,
           "reason": "transport.rate-limited", "retry_after": 30, "in_reply_to": sid, "issued_at": NOW, "expires_at": NOW + 30}
    out.append(pv("error-transport-scoped", "error", "Transport-scoped error without session.", ["§15.4"], err))
    out.append(pv("error-session-scoped", "error", "Session-scoped error.", ["§12.4"],
                  {**err, "session": sid, "reason": "session.invalid-state", "from": BPH}))
    out.append(pv("error-missing-reason", "error", "reason is required.", ["§15.2"], {k: v for k, v in err.items() if k != "reason"}, ok=False))
    out.append(pv("error-detail-object", "error", "A profile-defined object detail: G§7's gateway.downgraded names the lost "
                  "guarantees (spec-gap 112).", ["G§7", "§15"],
                  {**err, "from": BPH, "reason": "gateway.downgraded", "detail": {"losses": ["no-srtp-on-trunk", "identity-not-assertable"]}}))
    out.append(pv("error-detail-number", "error", "A detail that is neither text nor an object.", ["§15"],
                  {**err, "detail": 7}, ok=False))

    # hello
    hc = hello_client(on_behalf_of=F.BOB_WEB)
    out.append(pv("hello-client-valid", "hello", "Client hello with bindings and on_behalf_of.", ["§13.2"], hc))
    out.append(pv("hello-client-no-bindings", "hello", "Client form requires bindings.", ["§13.2"],
                  {k: v for k, v in hc.items() if k != "bindings"}, ok=False))
    out.append(pv("hello-with-session-field", "hello", "hello is session-scoped to nothing.", ["§13.2"], {**hc, "session": sid}, ok=False))
    hr = hello_relay(hc["id"])
    out.append(pv("hello-relay-valid", "hello", "Relay hello with in_reply_to and capabilities.", ["§13.2"], hr))
    out.append(pv("hello-relay-no-capabilities", "hello", "in_reply_to entails capabilities.", ["§13.2"],
                  {k: v for k, v in hr.items() if k != "capabilities"}, ok=False))
    out.append(pv("hello-relay-wrong-max-envelope", "hello", "max_envelope_bytes must equal the 65536 binding constant.", ["§13.2"],
                  {**hr, "capabilities": {**hr["capabilities"], "max_envelope_bytes": 32768}}, ok=False))
    out.append(pv("hello-relay-unknown-capability-ok", "hello", "Unknown capability fields MUST be ignored.", ["§13.2"],
                  {**hr, "capabilities": {**hr["capabilities"], "x_future": {"a": 1}}}))
    out.append(pv("hello-relay-introduction-max-bytes", "hello", "A service that accepts larger introductions says so "
                  "(profile-card/1.0, spec-gap 186).", ["§13.2", "§19.4"],
                  {**hr, "capabilities": {**hr["capabilities"], "introduction_max_bytes": 16384}}))
    out.append(pv("hello-relay-introduction-max-bytes-below-core", "hello", "introduction_max_bytes is never below the core 4,096.",
                  ["§13.2", "§19.4"], {**hr, "capabilities": {**hr["capabilities"], "introduction_max_bytes": 4095}}, ok=False))
    out.append(pv("hello-relay-introduction-max-bytes-not-integer", "hello", "introduction_max_bytes is an integer.",
                  ["§13.2", "§19.4"], {**hr, "capabilities": {**hr["capabilities"], "introduction_max_bytes": "16384"}}, ok=False))
    out.append(pv("hello-capabilities-without-in-reply-to", "hello", "capabilities entails in_reply_to.", ["§13.2"],
                  {k: v for k, v in hr.items() if k != "in_reply_to"}, ok=False))

    # introduction / grant
    intro = {"dsip": V, "type": "introduction", "id": uid("intro"), "from": F.did("carol-phone"), "to": F.BOB_WEB,
             "identity": {"display_name": "Carol Nguyen", "claims": []}, "purpose": "Following up from the meetup.",
             "issued_at": NOW, "expires_at": NOW + 604800}
    out.append(pv("introduction-valid", "introduction", "Valid introduction.", ["§19.4"], intro))
    out.append(pv("introduction-purpose-too-long", "introduction", "purpose over 280 characters.", ["§19.4"], {**intro, "purpose": "x" * 281}, ok=False))
    out.append(pv("introduction-with-media", "introduction", "An introduction cannot carry a media offer.", ["§19.4"],
                  {**intro, "media": MEDIA_OFFER}, ok=False))
    out.append(pv("introduction-contact-token", "introduction", "Introduction bearing an out-of-band contact token.", ["§19.4"],
                  {**intro, "contact_token": "tok_0123456789"}))
    grant = {"dsip": V, "type": "grant", "id": uid("grant"), "session": intro["id"], "from": F.BOB_WEB, "to": F.did("carol-phone"),
             "scope": ["dsip.invite"], "valid_until": NOW + 31536000, "issued_at": NOW + 600, "expires_at": NOW + 630}
    out.append(pv("grant-valid", "grant", "Grant referencing the introduction.", ["§19.4"], grant))
    sealed_card = {"alg": "hpke-base-x25519-sha256-aes128gcm", "enc": "N_2jVnvb1ijohmjDyNfpfR0SU7bU6m1EwVD3QfG_RDE",
                   "ct": "-ThVi11y8aI4ELS-KrT4QzGswC_JeavFOlKughijVamGh3CsjNB76ofhPFEq"}
    carded = {**grant, "dsip": {**V, "extensions": ["profile-card/1.0"]}, "profile": sealed_card}
    out.append(pv("grant-profile-valid", "grant", "A grant may carry profile, {alg, enc, ct}: the grantor's sealed profile card "
                  "(profile-card/1.0, spec-gap 186).", ["§19.4"], carded))
    out.append(pv("grant-profile-missing-ct-invalid", "grant", "profile carries alg, enc and ct.", ["§19.4"],
                  {**carded, "profile": {k: v for k, v in sealed_card.items() if k != "ct"}}, ok=False))
    out.append(pv("grant-profile-extra-field-invalid", "grant", "profile takes no other field: a card is never in clear.", ["§19.4"],
                  {**carded, "profile": {**sealed_card, "display_name": "Bob"}}, ok=False))
    out.append(pv("grant-scope-unprefixed", "grant", "Scope without the dsip. prefix.", ["§19.4"], {**grant, "scope": ["invite"]}, ok=False))
    out.append(pv("grant-empty-scope", "grant", "scope must be non-empty.", ["§19.4"], {**grant, "scope": []}, ok=False))

    # subscribe / notify / publish / unpublish
    sub = {"dsip": V, "type": "subscribe", "id": uid("sub"), "from": APH, "to": "did:web:example.com", "target": F.BOB_WEB,
           "events": ["presence"], "expires_in": 600, "issued_at": NOW, "expires_at": NOW + 30}
    out.append(pv("subscribe-valid", "subscribe", "Presence subscription.", ["§9.3"], sub))
    out.append(pv("subscribe-terminate", "subscribe", "expires_in 0 terminates.", ["§9.3"], {**sub, "expires_in": 0}))
    out.append(pv("subscribe-over-schema-ceiling", "subscribe", "expires_in above the 86,400 schema ceiling.", ["§9.3"],
                  {**sub, "expires_in": 100000}, ok=False))
    out.append(pv("subscribe-no-events", "subscribe", "events must be non-empty.", ["§9.3"], {**sub, "events": []}, ok=False))
    ntf = {"dsip": V, "type": "notify", "id": uid("ntf"), "from": "did:web:example.com", "to": APH, "subscription": sub["id"],
           "seq": 1, "state": "active", "body": {"type": "presence", "state": "available"}, "issued_at": NOW + 1, "expires_at": NOW + 31}
    out.append(pv("notify-initial", "notify", "First notify carrying current state.", ["§9.3"], ntf))
    out.append(pv("notify-terminated", "notify", "Terminal notify with reason.", ["§9.3"],
                  {**ntf, "seq": 9, "state": "terminated", "reason": "policy.terminated", "body": {}}))
    out.append(pv("notify-seq-zero", "notify", "seq starts at 1.", ["§9.3"], {**ntf, "seq": 0}, ok=False))
    out.append(pv("notify-bad-state", "notify", "state must be active|terminated.", ["§9.3"], {**ntf, "state": "paused"}, ok=False))
    pub = {"dsip": BCAST_V, "type": "publish", "id": uid("pub"), "from": "did:web:wxyz.com", "publisher": "did:web:wxyz.com",
           "stream_id": "did:web:wxyz.com:radio:main", "title": "WXYZ Live Radio", "state": "live",
           "variants": [{"id": "main-opus", "media": ["audio"], "codec": "codec:audio/opus", "transport": "transport:webrtc",
                         "uri": "wss://live.wxyz.com/dsip/webrtc/main"}],
           "policy": {"redistribution": "allowed-with-attribution"}, "issued_at": NOW, "expires_at": NOW + 300}
    out.append(pv("publish-valid", "publish", "Broadcast publication record.", ["§22.1"], pub))
    out.append(pv("publish-no-variants", "publish", "variants must be non-empty.", ["§22.1"], {**pub, "variants": []}, ok=False))
    out.append(pv("publish-bad-state", "publish", "Unknown publication state.", ["§22.1"], {**pub, "state": "paused"}, ok=False))
    unp = {"dsip": BCAST_V, "type": "unpublish", "id": uid("unpub"), "from": "did:web:wxyz.com", "publisher": "did:web:wxyz.com",
           "stream_id": "did:web:wxyz.com:radio:main", "publication": pub["id"], "issued_at": NOW + 600, "expires_at": NOW + 630}
    out.append(pv("unpublish-valid", "unpublish", "Withdraw a publication.", ["§22.1"], unp))
    out.append(pv("unpublish-missing-publication", "unpublish", "publication id is required.", ["§22.1"],
                  {k: v for k, v in unp.items() if k != "publication"}, ok=False))
    out.append(pv("publish-integrity-declared", "publish", "Record-level integrity mode (v0.7).", ["§22.2"], {**pub, "integrity": "derivative-bound"}))
    out.append(pv("publish-integrity-bad-shape", "publish", "integrity must be a token.", ["§22.2"], {**pub, "integrity": "Metadata Only"}, ok=False))
    prov = {"dsip": BCAST_V, "type": "provenance", "id": uid("prov"), "from": "did:web:cdn.example",
            "original_stream": pub["stream_id"], "original_publication": pub["id"], "processor": "did:web:cdn.example",
            "operation": "transcode", "input_variant": "main-opus", "output_variant": "main-aac-hls",
            "output_uri": "https://cdn.example/wxyz/main.m3u8", "issued_at": NOW + 100, "expires_at": NOW + 3700}
    out.append(pv("provenance-valid", "provenance", "Processor statement (core message in v0.7, §22.3).", ["§22.3"], prov))
    out.append(pv("provenance-missing-output-variant", "provenance", "output_variant is required.", ["§22.3"],
                  {k: v for k, v in prov.items() if k != "output_variant"}, ok=False))
    rot = {"dsip": V, "type": "key-rotation", "id": uid("rot"), "from": F.BOB_WEB, "subject": F.BOB_WEB,
           "previous": F.web_kid(F.BOB_WEB), "next": f"{F.BOB_WEB}#key-2", "next_public_key_multibase": F.multibase_pub("bob-next"),
           "reason": "scheduled", "devices": [BPH], "issued_at": NOW, "expires_at": NOW + 86400}
    out.append(pv("key-rotation-valid", "key-rotation", "Rotation record signed by the retiring key (§7.5, v0.7).", ["§7.5"], rot))
    out.append(pv("key-rotation-bad-reason-token", "key-rotation", "reason must be a token.", ["§7.5"], {**rot, "reason": "Scheduled!"}, ok=False))
    out.append(pv("key-rotation-missing-next-key", "key-rotation", "next_public_key_multibase is required.", ["§7.5"],
                  {k: v for k, v in rot.items() if k != "next_public_key_multibase"}, ok=False))

    # v0.8: sealed introductions (§19.4, spec-gap 36), delegation revocation (§7.4, spec-gap 57)
    intro = {"dsip": V, "type": "introduction", "id": uid("intro"), "from": F.did("alice"), "to": F.BOB_WEB,
             "identity": {"display_name": "Alice"}, "issued_at": NOW, "expires_at": NOW + 604800}
    sealed = {"alg": "hpke-base-x25519-sha256-aes128gcm", "enc": "N_2jVnvb1ijohmjDyNfpfR0SU7bU6m1EwVD3QfG_RDE",
              "ct": "-ThVi11y8aI4ELS-KrT4QzGswC_JeavFOlKughijVamGh3CsjNB76ofhPFEq"}
    out.append(pv("introduction-sealed-valid", "introduction", "An introduction may carry sealed instead of purpose (v0.8).", ["§19.4"],
                  {**intro, "sealed": sealed}))
    out.append(pv("introduction-sealed-missing-enc", "introduction", "A sealed body names alg, enc and ct.", ["§19.4"],
                  {**intro, "sealed": {k: v for k, v in sealed.items() if k != "enc"}}, ok=False))
    out.append(pv("introduction-sealed-extra-field", "introduction", "Nothing else rides in a sealed body.", ["§19.4"],
                  {**intro, "sealed": {**sealed, "purpose": "leak"}}, ok=False))
    rev = {"dsip": V, "type": "delegation-revocation", "id": uid("rev"), "from": F.BOB_WEB, "subject": F.BOB_WEB,
           "device": BPH, "revoked_at": NOW, "reason": "lost", "issued_at": NOW, "expires_at": NOW + 300}
    out.append(pv("delegation-revocation-valid", "delegation-revocation", "Revocation record (§7.4, v0.8).", ["§7.4"], rev))
    out.append(pv("delegation-revocation-missing-revoked-at", "delegation-revocation", "revoked_at is required: it is what allows re-enrollment.",
                  ["§7.4"], {k: v for k, v in rev.items() if k != "revoked_at"}, ok=False))
    out.append(pv("delegation-revocation-missing-device", "delegation-revocation", "A revocation names one device.", ["§7.4"],
                  {k: v for k, v in rev.items() if k != "device"}, ok=False))
    out.append(pv("delegation-revocation-bad-reason-token", "delegation-revocation", "reason must be a token.", ["§7.4"],
                  {**rev, "reason": "Lost!"}, ok=False))

    hint = {"dsip": V, "type": "reachability-hint", "id": uid("hint-mbx"), "from": F.did("alice-phone"), "subject": F.did("alice"),
            "endpoints": [{"uri": "wss://mbx.example.net/dsip", "bindings": ["ws/1.0"], "service": "DSIPMailbox"}], "seq": 4,
            "issued_at": NOW, "expires_at": NOW + 3600}
    out.append(pv("reachability-hint-service-mailbox", "reachability-hint", "A hint endpoint may name the service type it stands in for (v0.8, spec-gap 37).",
                  ["§8.5"], hint))
    out.append(pv("reachability-hint-service-not-a-type-name", "reachability-hint", "service is a DID service type name.", ["§8.5"],
                  {**hint, "endpoints": [{**hint["endpoints"][0], "service": "dsip mailbox"}]}, ok=False))

    # Alias Transparency T§8 (v0.14, spec-gap 124): an owner's monitoring authorization
    mon = {"dsip": V, "type": "alias-monitor", "id": uid("alias-monitor"), "from": "did:web:alice.example", "to": "did:web:example.com",
           "issued_at": NOW, "expires_at": NOW + 60, "alias": "alice@example.com"}
    out.append(pv("alias-monitor-valid", "alias-monitor", "An owner's monitoring authorization, addressed to the provider (T§8).",
                  ["T§8"], mon))
    out.append(pv("alias-monitor-missing-alias", "alias-monitor", "alias-monitor names the alias.", ["T§8"],
                  {k: v for k, v in mon.items() if k != "alias"}, ok=False))
    out.append(pv("alias-monitor-missing-to", "alias-monitor", "alias-monitor is addressed to the provider.", ["T§8"],
                  {k: v for k, v in mon.items() if k != "to"}, ok=False))
    out.append(pv("alias-monitor-alias-too-long", "alias-monitor", "An alias is at most 255 characters (T§3).", ["T§8", "T§3"],
                  {**mon, "alias": "a" * 244 + "@example.com"}, ok=False))
    out.append(pv("alias-monitor-extra-field", "alias-monitor", "alias-monitor takes no other field (the KEYTRANS request is the "
                  "HTTP body, never in the payload, T§2).", ["T§8", "T§2"], {**mon, "request": "AAAA"}, ok=False))

    # JSON Schema patterns are ECMA-262 (draft 2020-12 §6.4): `$` is the end of the string, never before a final LF
    out.append(pv("invite-id-trailing-newline", "invite", "An id with a trailing LF fails the ULID pattern: `$` is the end "
                  "of the string (ECMA-262), not before a final newline.", ["§10.3", "§20.6"], {**inv, "id": inv["id"] + "\n"},
                  ok=False))
    out.append(pv("invite-from-trailing-newline", "invite", "A `from` DID with a trailing LF fails the DID pattern.",
                  ["§10.3", "§7.1"], {**inv, "from": inv["from"] + "\n"}, ok=False))
    bye_lf = session_msg("bye", "bye-lf", sid, F.did("alice-phone"), F.BOB_WEB, reason="session.ended\n")
    out.append(pv("bye-reason-trailing-newline", "bye", "A reason token with a trailing LF fails the token pattern.",
                  ["§15.1"], bye_lf, ok=False))

    # envelope schema (shape only)
    from .common import signed
    env = signed(inv, "alice-phone")
    out.append(pv("envelope-shape-valid", "envelope", "Envelope object shape.", ["§10.2"], env))
    out.append(pv("envelope-shape-missing-signature", "envelope", "Envelope without signature.", ["§10.2"],
                  {k: v for k, v in env.items() if k != "signature"}, ok=False))
    from .presence_vectors import payload_vectors
    from . import presence_sealed
    out.extend(payload_vectors())
    out.extend(presence_sealed.payload_vectors())
    return out
