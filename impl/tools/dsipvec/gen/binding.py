"""`media-binding` vectors — the WebRTC Media Binding 1.0 (v0.7 companion) conformance set.

B§2 descriptor/SDP authority rule and SDP profile, B§3 roles and DTLS role from a=setup, B§4
candidate carriage/timing/attribution, B§5 renegotiation (ICE restart unsupported), B§6.1 one
answer per offer. Inputs are decoded payloads (envelope checks are upstream) or event traces.
"""
from __future__ import annotations

import copy

from .. import fixtures as F
from .common import NOW, vector, accept, reject, uid

APH, BPH, BLA = F.did("alice-phone"), F.did("bob-phone"), F.did("bob-laptop")
FP = "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99"
UFRAG, PWD = "0123456789abcdef0123456789abcdef", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def sdp(sections=(("audio", "sendrecv", ("opus",)),), *, setup="actpass", ufrag=UFRAG, rtcp_mux=True, fingerprint=FP,
        protocol="UDP/TLS/RTP/SAVPF", ice_creds=True, session_level_direction=None, extra_sections=()):
    """Build a binding-profile SDP. `sections` = (kind, direction, encodings[, port]) tuples."""
    lines = ["v=0", "o=- 1 1 IN IP4 127.0.0.1", "s=-", "t=0 0", "a=group:BUNDLE " + " ".join(str(i) for i in range(len(sections) + len(extra_sections)))]
    if session_level_direction:
        lines.append(f"a={session_level_direction}")
    pts = {"opus": ("111", "opus/48000/2"), "H264": ("96", "H264/90000"), "VP8": ("97", "VP8/90000"), "PCMU": ("0", "PCMU/8000"),
           "PCMA": ("8", "PCMA/8000"), "G722": ("9", "G722/8000"), "VP9": ("98", "VP9/90000")}
    i = 0
    for sec in list(sections) + list(extra_sections):
        kind, direction, encs = sec[0], sec[1], sec[2]
        port = sec[3] if len(sec) > 3 else 9
        fmts = [pts[e][0] for e in encs] if kind != "application" else ["webrtc-datachannel"]
        lines.append(f"m={kind} {port} {protocol if kind != 'application' else 'UDP/DTLS/SCTP'} " + " ".join(fmts))
        lines.append("c=IN IP4 0.0.0.0")
        if ice_creds:
            lines += [f"a=ice-ufrag:{ufrag}", f"a=ice-pwd:{PWD}"]
        if fingerprint:
            lines.append(f"a=fingerprint:sha-256 {fingerprint}")
        lines += [f"a=setup:{setup}", f"a=mid:{i}"]
        if direction:
            lines.append(f"a={direction}")
        if rtcp_mux and kind != "application":
            lines.append("a=rtcp-mux")
        for e in encs:
            if kind != "application":
                lines.append(f"a=rtpmap:{pts[e][0]} {pts[e][1]}")
        i += 1
    return "\r\n".join(lines) + "\r\n"


AUDIO = [{"type": "audio", "direction": "sendrecv", "codecs": [{"id": "codec:audio/opus"}]}]
AV = AUDIO + [{"type": "video", "direction": "sendrecv", "codecs": [{"id": "codec:video/h264"}]}]


def offer(media=None, s=None, ice="trickle", with_sdp=True):
    t = {"id": "transport:webrtc"}
    if ice is not None:
        t["ice"] = ice
    if with_sdp:
        t["sdp"] = s if s is not None else sdp()
    return {"media": copy.deepcopy(media if media is not None else AUDIO), "transports": [t]}


def answer(media=None, s=None, frm=BPH):
    return {"from": frm, "media": copy.deepcopy(media if media is not None else AUDIO),
            "transports": [{"id": "transport:webrtc", "sdp": s if s is not None else sdp(setup="active")}]}


def bv(vid, desc, refs, inp, expect, ctx=None):
    return vector(f"media-binding/{vid}", "media-binding", desc, refs, ctx or {}, inp, expect)


def trace(vid, desc, refs, check, steps, ctx):
    return bv(vid, desc, refs, {"check": check, "steps": [{"event": e} for e, _ in steps]},
              {"steps": [{"emit": em} for _, em in steps]}, ctx=ctx)


def vectors() -> list[dict]:
    out = []
    # ---- B§2 offers
    out.append(bv("offer-valid-audio", "A binding-profile audio offer: one m=audio, actpass, rtcp-mux, sha-256 fingerprint, trickle.",
                  ["B§2", "B§2.2"], {"check": "offer", "payload": offer()}, accept()))
    out.append(bv("offer-valid-audio-video", "Two descriptors ↔ two m= sections in order.", ["B§2.1"],
                  {"check": "offer", "payload": offer(AV, sdp((("audio", "sendrecv", ("opus",)), ("video", "sendrecv", ("H264",)))))}, accept()))
    out.append(bv("offer-not-webrtc-unchecked", "A non-WebRTC transport is outside this binding; nothing is checked.", ["B§1"],
                  {"check": "offer", "payload": {"media": AUDIO, "transports": [{"id": "transport:rtp", "sdp": "v=0"}]}}, accept(binding="not-webrtc")))
    out.append(bv("offer-ice-mode-unknown", "`ice` other than trickle is rejected media.unsupported.", ["B§2"],
                  {"check": "offer", "payload": offer(ice="full")}, reject("binding-ice-mode", "media.unsupported")))
    out.append(bv("offer-ice-mode-missing", "`ice` is required on offers.", ["B§2"],
                  {"check": "offer", "payload": offer(ice=None)}, reject("binding-ice-mode", "media.unsupported")))
    out.append(bv("offer-sdp-missing", "An offer selecting transport:webrtc without sdp is media.offer-required.", ["B§2"],
                  {"check": "offer", "payload": offer(with_sdp=False)}, reject("binding-sdp-missing", "media.offer-required")))
    out.append(bv("offer-sdp-unparseable", "sdp that is not SDP.", ["B§2"],
                  {"check": "offer", "payload": offer(s="hello")}, reject("binding-sdp-invalid", "media.unsupported")))
    out.append(bv("offer-section-count-mismatch", "Two descriptors but one m= section.", ["B§2.1"],
                  {"check": "offer", "payload": offer(AV)}, reject("binding-section-count", "media.unsupported")))
    out.append(bv("offer-kind-mismatch", "Descriptor order is m= order: video descriptor first but m=audio first.", ["B§2.1"],
                  {"check": "offer", "payload": offer(list(reversed(AV)), sdp((("audio", "sendrecv", ("opus",)), ("video", "sendrecv", ("H264",)))))},
                  reject("binding-kind-mismatch", "media.unsupported")))
    out.append(bv("offer-direction-mismatch", "Descriptor says sendrecv, SDP says sendonly.", ["B§2.1"],
                  {"check": "offer", "payload": offer(s=sdp((("audio", "sendonly", ("opus",)),)))}, reject("binding-direction-mismatch", "media.unsupported")))
    out.append(bv("offer-direction-session-level", "A session-level direction applies to sections without their own.", ["B§2.1"],
                  {"check": "offer", "payload": offer([{"type": "audio", "direction": "recvonly", "codecs": [{"id": "codec:audio/opus"}]}],
                                                       sdp((("audio", None, ("opus",)),), session_level_direction="recvonly"))}, accept()))
    out.append(bv("offer-codec-missing", "Descriptor offers opus but the SDP has no opus rtpmap.", ["B§2.1", "B§3.4"],
                  {"check": "offer", "payload": offer(s=sdp((("audio", "sendrecv", ("PCMU",)),)))}, reject("binding-codec-missing", "media.unsupported")))
    # spec-gap 182: every row of B§3.4 is checked; a codec with no row is not
    def video(codec):
        return AUDIO + [{"type": "video", "direction": "sendrecv", "codecs": [{"id": codec}]}]

    def audio(codec):
        return [{"type": "audio", "direction": "sendrecv", "codecs": [{"id": codec}]}]

    av = lambda enc: sdp((("audio", "sendrecv", ("opus",)), ("video", "sendrecv", (enc,))))
    out.append(bv("offer-codec-vp9-valid", "VP9 has a B§3.4 row: a vp9 descriptor with a VP9/90000 rtpmap.", ["B§2.1", "B§3.4"],
                  {"check": "offer", "payload": offer(video("codec:video/vp9"), av("VP9"))}, accept()))
    out.append(bv("offer-codec-vp9-missing", "A vp9 descriptor whose m=video carries only VP8: the row's rtpmap is missing.",
                  ["B§2.1", "B§3.4"], {"check": "offer", "payload": offer(video("codec:video/vp9"), av("VP8"))},
                  reject("binding-codec-missing", "media.unsupported")))
    out.append(bv("offer-codec-pcma-valid", "PCMA has a B§3.4 row: a pcma descriptor with a PCMA/8000 rtpmap.", ["B§2.1", "B§3.4"],
                  {"check": "offer", "payload": offer(audio("codec:audio/pcma"), sdp((("audio", "sendrecv", ("PCMA",)),)))}, accept()))
    out.append(bv("offer-codec-g722-missing", "A g722 descriptor whose m=audio carries only opus: the row's rtpmap is missing.",
                  ["B§2.1", "B§3.4"], {"check": "offer", "payload": offer(audio("codec:audio/g722"))},
                  reject("binding-codec-missing", "media.unsupported")))
    out.append(bv("offer-codec-unmapped-unchecked", "A codec with no B§3.4 row (codec:audio/aac) has no mapping: §2.1 does "
                  "not check it, and the offer stands on its other codecs.", ["B§2.1", "B§3.4"],
                  {"check": "offer", "payload": offer([{"type": "audio", "direction": "sendrecv",
                                                        "codecs": [{"id": "codec:audio/opus"}, {"id": "codec:audio/aac"}]}])}, accept()))
    out.append(bv("offer-extra-payload-types-ok", "The SDP may carry payload types DSIP does not describe.", ["B§2.1"],
                  {"check": "offer", "payload": offer(s=sdp((("audio", "sendrecv", ("opus", "PCMU")),)))}, accept()))
    out.append(bv("offer-data-channel-rejected", "An m=application section is outside Core v1.0.", ["B§2.1"],
                  {"check": "offer", "payload": offer(s=sdp(extra_sections=(("application", None, ()),)))}, reject("binding-extra-section", "media.unsupported")))
    out.append(bv("offer-plain-rtp-rejected", "RTP/AVP (no DTLS) fails the encryption floor.", ["B§7", "§17.2"],
                  {"check": "offer", "payload": offer(s=sdp(protocol="RTP/AVP"))}, reject("binding-encryption", "media.encryption-required")))
    out.append(bv("offer-no-rtcp-mux", "rtcp-mux is REQUIRED.", ["B§2.2"],
                  {"check": "offer", "payload": offer(s=sdp(rtcp_mux=False))}, reject("binding-rtcp-mux-missing", "media.unsupported")))
    out.append(bv("offer-no-fingerprint", "A sha-256 fingerprint is REQUIRED (identity-bound media).", ["B§2.2", "B§7"],
                  {"check": "offer", "payload": offer(s=sdp(fingerprint=None))}, reject("binding-fingerprint-missing", "media.unsupported")))
    out.append(bv("offer-no-ice-credentials", "ICE credentials are REQUIRED.", ["B§2.2", "B§4.1"],
                  {"check": "offer", "payload": offer(s=sdp(ice_creds=False))}, reject("binding-ice-credentials-missing", "media.unsupported")))
    out.append(bv("offer-setup-active-rejected", "An offer MUST be a=setup:actpass.", ["B§3.3"],
                  {"check": "offer", "payload": offer(s=sdp(setup="active"))}, reject("binding-setup-invalid", "media.unsupported")))

    # ---- B§2/B§3.1 answers
    off = offer()
    out.append(bv("answer-valid-active", "The answer mirrors the offer's one section and is a=setup:active.", ["B§3.1", "B§3.3"],
                  {"check": "answer", "offer": off, "payload": answer()}, accept()))
    out.append(bv("answer-screening-recvonly", "A screening answer: descriptor recvonly, SDP a=recvonly.", ["B§6.2", "§14.4"],
                  {"check": "answer", "offer": off, "payload": answer([{"type": "audio", "direction": "recvonly", "codecs": [{"id": "codec:audio/opus"}]}],
                                                                        sdp((("audio", "recvonly", ("opus",)),), setup="active"))}, accept()))
    out.append(bv("answer-actpass-rejected", "An answer carrying a=setup:actpass is not an answer (media.failed → bye).", ["B§3.1", "B§3.3"],
                  {"check": "answer", "offer": off, "payload": answer(s=sdp(setup="actpass"))}, reject("binding-setup-invalid", "media.failed")))
    out.append(bv("answer-rejects-video-with-port-zero", "Offer has audio+video; the answer accepts audio and rejects video with port 0 — still two sections.", ["B§2.1"],
                  {"check": "answer", "offer": offer(AV, sdp((("audio", "sendrecv", ("opus",)), ("video", "sendrecv", ("H264",))))),
                   "payload": answer(s=sdp((("audio", "sendrecv", ("opus",)), ("video", "inactive", ("H264",), 0)), setup="active"))}, accept()))
    out.append(bv("answer-section-count-mismatch", "Offer has two sections; the answer has one — not an RFC 3264 answer.", ["B§2.1"],
                  {"check": "answer", "offer": offer(AV, sdp((("audio", "sendrecv", ("opus",)), ("video", "sendrecv", ("H264",))))),
                   "payload": answer()}, reject("binding-section-count", "media.failed")))
    out.append(bv("answer-direction-mismatch", "Descriptor recvonly but SDP sendrecv.", ["B§2.1"],
                  {"check": "answer", "offer": off, "payload": answer([{"type": "audio", "direction": "recvonly", "codecs": [{"id": "codec:audio/opus"}]}],
                                                                        sdp(setup="active"))}, reject("binding-direction-mismatch", "media.failed")))
    out.append(bv("answer-sdp-missing", "An answer selecting transport:webrtc without sdp is not a valid selection.", ["B§2"],
                  {"check": "answer", "offer": off, "payload": {"from": BPH, "media": AUDIO, "transports": [{"id": "transport:webrtc"}]}},
                  reject("binding-sdp-missing", "media.failed")))

    # ---- B§3.3 roles
    out.append(bv("role-actpass-active", "Offer actpass + answer active: answerer is DTLS client, offerer server.", ["B§3.3"],
                  {"check": "role", "offer_setup": "actpass", "answer_setup": "active"}, {"verdict": "accept", "offerer": "server", "answerer": "client"}))
    out.append(bv("role-actpass-passive", "Answer passive (permitted when the answerer cannot act as client): offerer is client.", ["B§3.3"],
                  {"check": "role", "offer_setup": "actpass", "answer_setup": "passive"}, {"verdict": "accept", "offerer": "client", "answerer": "server"}))
    out.append(bv("role-answer-actpass-invalid", "An answer MUST NOT be actpass.", ["B§3.3"],
                  {"check": "role", "offer_setup": "actpass", "answer_setup": "actpass"}, reject("binding-setup-invalid", "media.failed")))
    out.append(bv("role-holdconn-invalid", "holdconn MUST NOT be used.", ["B§3.3"],
                  {"check": "role", "offer_setup": "actpass", "answer_setup": "holdconn"}, reject("binding-setup-invalid", "media.failed")))
    out.append(bv("role-offer-active-invalid", "An offer MUST be actpass.", ["B§3.3"],
                  {"check": "role", "offer_setup": "active", "answer_setup": "passive"}, reject("binding-setup-invalid", "media.unsupported")))

    # ---- B§4 candidate exchange traces
    c = lambda n: {"candidate": f"candidate:{n} 1 udp 2130706431 192.0.2.{n} 5000{n} typ host", "sdp_mid": "0", "sdp_m_line_index": 0}
    out.append(trace("candidates-initiator-buffers-until-active", "Initiator: candidates gathered before the answer are buffered and sent in one info once ACTIVE; gathering completes later → a lone end marker.",
                     ["B§4.3", "§12.12"], "candidates", [
        ({"local_candidate": c(1)}, [{"buffer": "local", "n": 1}]),
        ({"local_candidate": c(2)}, [{"buffer": "local", "n": 2}]),
        ({"active": True}, [{"send_info": {"candidates": 2, "end_of_candidates": False}}]),
        ({"local_candidate": c(3)}, [{"send_info": {"candidates": 1, "end_of_candidates": False}}]),
        ({"gathering_complete": True}, [{"send_info": {"candidates": 0, "end_of_candidates": True}}]),
        ({"gathering_complete": True}, []),
    ], ctx={"peer": BPH}))
    out.append(trace("candidates-gathering-complete-before-active", "Gathering finished before ACTIVE: the first info carries everything and the end marker together.",
                     ["B§4.2", "B§4.3"], "candidates", [
        ({"local_candidate": c(1)}, [{"buffer": "local", "n": 1}]),
        ({"gathering_complete": True}, []),
        ({"active": True}, [{"send_info": {"candidates": 1, "end_of_candidates": True}}]),
    ], ctx={"peer": BPH}))
    out.append(trace("candidates-remote-buffered-until-description", "Remote candidates that overtake the answer are buffered and applied in order once the remote description is applied.",
                     ["B§4.3"], "candidates", [
        ({"remote_info": {"from": BPH, "candidates": [c(1), c(2)], "end_of_candidates": False}}, [{"buffer": "remote", "n": 2}]),
        ({"remote_description": True}, [{"apply": 2}]),
        ({"remote_info": {"from": BPH, "candidates": [c(3)], "end_of_candidates": True}}, [{"apply": 1}, {"remote_end": True}]),
        ({"remote_info": {"from": BPH, "candidates": [c(4)], "end_of_candidates": False}}, [{"ignore": "after-end"}]),
    ], ctx={"peer": BPH}))
    out.append(trace("candidates-non-party-ignored", "info from a device that is not party to the session (a released fork leg) is ignored.",
                     ["B§4.4", "§12.7"], "candidates", [
        ({"remote_description": True}, []),
        ({"remote_info": {"from": BLA, "candidates": [c(1)], "end_of_candidates": False}}, [{"ignore": "not-party"}]),
        ({"remote_info": {"from": BPH, "candidates": [c(1)], "end_of_candidates": False}}, [{"apply": 1}]),
    ], ctx={"peer": BPH}))
    out.append(trace("candidates-dropped-on-session-end", "Buffered candidates are dropped, not applied, when the session ends.",
                     ["B§4.3"], "candidates", [
        ({"remote_info": {"from": BPH, "candidates": [c(1)], "end_of_candidates": False}}, [{"buffer": "remote", "n": 1}]),
        ({"local_candidate": c(2)}, [{"buffer": "local", "n": 1}]),
        ({"session_end": True}, [{"drop_buffered": 2}]),
        ({"remote_description": True}, [{"ignore": "ended"}]),
    ], ctx={"peer": BPH}))

    # ---- B§5 renegotiation traces
    out.append(trace("renegotiation-reoffer-answered", "A re-offer keeps the ICE credentials; the pending description becomes current when the answer applies.",
                     ["B§5.1", "B§5.2"], "renegotiation", [
        ({"local_reoffer": {"ufrag": "abcd"}}, [{"local_description": "pending"}]),
        ({"remote_answer": True}, [{"apply": "answer"}, {"local_description": "current"}]),
    ], ctx={"ufrag": "abcd"}))
    out.append(trace("renegotiation-reoffer-rejected-rolls-back", "A rejected re-offer rolls the local description back; nothing on the transport changed.",
                     ["B§5.2", "§12.8"], "renegotiation", [
        ({"local_reoffer": {"ufrag": "abcd"}}, [{"local_description": "pending"}]),
        ({"remote_reject": True}, [{"rollback": True}, {"local_description": "current"}]),
        ({"remote_answer": True}, [{"ignore": "no-pending-offer"}]),
    ], ctx={"ufrag": "abcd"}))
    out.append(trace("renegotiation-ice-restart-refused", "A remote re-offer that changes the ICE credentials is an ICE restart: rejected media.unsupported, session continues.",
                     ["B§5.4"], "renegotiation", [
        ({"remote_reoffer": {"ufrag": "abcd"}}, [{"ui": "update_offered"}]),
        ({"answer_update": True}, [{"apply": "remote-offer+answer"}]),
        ({"remote_reoffer": {"ufrag": "zzzz"}}, [{"reject": {"reason": "media.unsupported", "detail": "ice-restart"}}]),
    ], ctx={"ufrag": "abcd"}))
    out.append(trace("renegotiation-local-restart-is-a-bug", "Our own re-offer MUST keep the credentials; changing them is a sender error, never sent.",
                     ["B§5.4"], "renegotiation", [
        ({"local_reoffer": {"ufrag": "zzzz"}}, [{"error": "binding-ice-restart", "detail": "a re-offer MUST keep the ICE credentials"}]),
    ], ctx={"ufrag": "abcd"}))

    # ---- B§6.1 one answer per offer
    out.append(bv("one-answer-first-valid-applied", "Two legs answer; the first valid answer is applied, the later one is released with bye session.already-answered.",
                  ["B§6.1", "§12.7"], {"check": "one-answer", "offer": off, "answers": [answer(frm=BPH), answer(frm=BLA)]},
                  {"applied": BPH, "legs": [{"from": BPH, "applied": True}, {"from": BLA, "bye": "session.already-answered"}]}))
    out.append(bv("one-answer-invalid-first-then-valid", "The first leg's answer is not an answer (actpass) → bye media.failed to it; the second valid one is applied.",
                  ["B§6.1", "B§8"], {"check": "one-answer", "offer": off, "answers": [answer(frm=BPH, s=sdp(setup="actpass")), answer(frm=BLA)]},
                  {"applied": BLA, "legs": [{"from": BPH, "bye": "media.failed", "code": "binding-setup-invalid"}, {"from": BLA, "applied": True}]}))
    return out
