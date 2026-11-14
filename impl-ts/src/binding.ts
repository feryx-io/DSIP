/**
 * WebRTC Media Binding 1.0: consistency between DSIP media descriptors and the SDP they carry,
 * DTLS roles, trickle-candidate timing, renegotiation, and one answer per offer.
 *
 * Spec: B§2 (transport descriptor), B§2.1 (descriptor/SDP authority), B§2.2 (SDP profile),
 * B§3.3 (DTLS role), B§3.4 (codec mapping), B§4.3–B§4.4 (candidate timing and attribution),
 * B§5 (renegotiation, no ICE restart), B§6.1 (one answer per offer), B§7 (encryption floor),
 * B§8 (failure handling). `B§n` cites `v0.8/dsip-webrtc-media-binding-v0.8.md`.
 */
import type { Json, JsonObject } from "./did.js";
import { reject, type Reject, type Verdict } from "./verdict.js";

const WEBRTC = "transport:webrtc";

/** Spec: B§3.4 — DSIP codec id → the `a=rtpmap` that must be present; a codec with no row is not checked (spec-gap 182). */
const RTPMAP: Record<string, string> = {
  "codec:audio/opus": "opus/48000/2",
  "codec:audio/pcmu": "PCMU/8000",
  "codec:audio/pcma": "PCMA/8000",
  "codec:audio/g722": "G722/8000",
  "codec:video/h264": "H264/90000",
  "codec:video/vp8": "VP8/90000",
  "codec:video/vp9": "VP9/90000",
  "codec:video/av1": "AV1/90000",
};

interface Section {
  kind: string;
  port: number;
  proto: string;
  attributes: string[];
}

interface Sdp {
  session: string[];
  sections: Section[];
}

function parseSdp(text: string): Sdp | null {
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  if (lines[0] !== "v=0" || !lines.every((l) => /^[a-z]=/.test(l))) return null;
  const sdp: Sdp = { session: [], sections: [] };
  for (const line of lines) {
    if (line.startsWith("m=")) {
      const [kind, port, proto] = line.slice(2).split(" ");
      if (kind === undefined || port === undefined || proto === undefined) return null;
      sdp.sections.push({ kind, port: Number(port), proto, attributes: [] });
    } else if (line.startsWith("a=")) {
      (sdp.sections.at(-1)?.attributes ?? sdp.session).push(line.slice(2));
    }
  }
  return sdp.sections.length ? sdp : null;
}

/** An attribute of a section, falling back to the session level. */
function attribute(sdp: Sdp, section: Section, name: string): string | undefined {
  const find = (list: string[]): string | undefined => list.find((a) => a === name || a.startsWith(`${name}:`));
  return find(section.attributes) ?? find(sdp.session);
}

function direction(sdp: Sdp, section: Section): string {
  const names = ["sendrecv", "sendonly", "recvonly", "inactive"];
  return names.find((d) => section.attributes.includes(d)) ?? names.find((d) => sdp.session.includes(d)) ?? "sendrecv";
}

function webrtcTransport(payload: JsonObject): JsonObject | undefined {
  return ((payload["transports"] ?? []) as JsonObject[]).find((t) => t["id"] === WEBRTC);
}

/**
 * Check a descriptor set against its SDP. `as` decides the failure token (B§8): an inconsistent
 * offer is rejected `media.unsupported`; an inconsistent answer fails the accepted leg, `media.failed`.
 */
function checkDescription(payload: JsonObject, as: "offer" | "answer", offered?: Sdp): Reject | Sdp {
  const fail = (code: string, offerReason = "media.unsupported"): Reject => reject(code, as === "offer" ? offerReason : "media.failed");
  const transport = webrtcTransport(payload)!;
  // B§2: `ice` is required on offers; when present it MUST be `trickle`
  if (as === "offer" ? transport["ice"] !== "trickle" : "ice" in transport && transport["ice"] !== "trickle") {
    return fail("binding-ice-mode");
  }
  if (typeof transport["sdp"] !== "string") return fail("binding-sdp-missing", "media.offer-required");
  const sdp = parseSdp(transport["sdp"]);
  if (!sdp) return fail("binding-sdp-invalid");

  // B§2.1: no other m= sections; media[i] is the i-th non-rejected section
  if (sdp.sections.some((s) => s.kind === "application")) return fail("binding-extra-section");
  const media = (payload["media"] ?? []) as JsonObject[];
  const live = sdp.sections.filter((s) => s.port !== 0);
  if (live.length !== media.length) return fail("binding-section-count");
  if (offered && offered.sections.length !== sdp.sections.length) return fail("binding-section-count");

  for (const [i, section] of live.entries()) {
    const d = media[i]!;
    if (section.kind !== d["type"]) return fail("binding-kind-mismatch");
    if (direction(sdp, section) !== ((d["direction"] as string | undefined) ?? "sendrecv")) return fail("binding-direction-mismatch");
    const rtpmaps = section.attributes.filter((a) => a.startsWith("rtpmap:")).map((a) => a.split(" ")[1]?.toLowerCase());
    for (const codec of (d["codecs"] ?? []) as JsonObject[]) {
      const mapped = RTPMAP[codec["id"] as string];
      if (mapped && !rtpmaps.includes(mapped.toLowerCase())) return fail("binding-codec-missing");
    }
  }
  for (const section of live) {
    // B§7: DTLS-SRTP is the floor; plain RTP is never offered or accepted
    if (!section.proto.includes("SAVP")) return fail("binding-encryption", "media.encryption-required");
    // B§2.2
    if (attribute(sdp, section, "rtcp-mux") === undefined) return fail("binding-rtcp-mux-missing");
    if (!attribute(sdp, section, "fingerprint")?.toLowerCase().startsWith("fingerprint:sha-256 ")) return fail("binding-fingerprint-missing");
    if (attribute(sdp, section, "ice-ufrag") === undefined || attribute(sdp, section, "ice-pwd") === undefined) {
      return fail("binding-ice-credentials-missing");
    }
    // B§3.3
    const setup = attribute(sdp, section, "setup")?.slice("setup:".length);
    if (as === "offer" ? setup !== "actpass" : setup !== "active" && setup !== "passive") return fail("binding-setup-invalid");
  }
  return sdp;
}

function isReject(v: Reject | Sdp): v is Reject {
  return "verdict" in v;
}

/** Check an `invite`/`update` body. A payload that does not select `transport:webrtc` is outside this binding. */
export function checkOffer(payload: JsonObject): Verdict {
  if (!webrtcTransport(payload)) return { verdict: "accept", binding: "not-webrtc" };
  const result = checkDescription(payload, "offer");
  return isReject(result) ? result : { verdict: "accept" };
}

/** Check an `answer` body against the offer it answers. Spec: B§3.1 — an answer is an SDP answer, never a counter-offer. */
export function checkAnswer(offer: JsonObject, payload: JsonObject): Verdict {
  if (!webrtcTransport(payload)) return { verdict: "accept", binding: "not-webrtc" };
  const offerSdp = parseSdp((webrtcTransport(offer)?.["sdp"] as string | undefined) ?? "");
  const result = checkDescription(payload, "answer", offerSdp ?? undefined);
  return isReject(result) ? result : { verdict: "accept" };
}

/** DTLS roles from the two `a=setup` values. Spec: B§3.3 */
export function dtlsRoles(offerSetup: string, answerSetup: string): Verdict {
  if (offerSetup !== "actpass") return reject("binding-setup-invalid", "media.unsupported");
  if (answerSetup === "active") return { verdict: "accept", offerer: "server", answerer: "client" };
  if (answerSetup === "passive") return { verdict: "accept", offerer: "client", answerer: "server" };
  return reject("binding-setup-invalid", "media.failed");
}

/** Spec: B§6.1 — apply exactly one answer, the first valid one; release every other leg. */
export function oneAnswer(offer: JsonObject, answers: JsonObject[]): JsonObject {
  let applied: string | null = null;
  const legs = answers.map((answer): Json => {
    const from = answer["from"] as string;
    if (applied !== null) return { from, bye: "session.already-answered" };
    const v = checkAnswer(offer, answer);
    if (v.verdict === "reject") return { from, bye: "media.failed", code: v.code };
    applied = from;
    return { from, applied: true };
  });
  return { applied, legs };
}

/** Trickle-candidate timing for one session. Spec: B§4.3, B§4.4 */
export class Candidates {
  private active = false;
  private ended = false;
  private remoteDescription = false;
  private gatheringComplete = false;
  private endSent = false;
  private remoteEnded = false;
  private local = 0;
  private remote = 0;

  constructor(private readonly peer: string) {}

  /** Apply one event; returns the emissions. */
  step(e: JsonObject): Json[] {
    if (this.ended) return [{ ignore: "ended" }];
    if ("session_end" in e) {
      // B§4.3 rule 3: buffered candidates are dropped, not applied, if the session ends
      this.ended = true;
      const n = this.local + this.remote;
      return n ? [{ drop_buffered: n }] : [];
    }
    if ("local_candidate" in e) {
      // B§4.3 rules 1–2: info is ACTIVE-only, so earlier candidates wait
      if (this.active) return [{ send_info: { candidates: 1, end_of_candidates: false } }];
      this.local += 1;
      return [{ buffer: "local", n: this.local }];
    }
    if ("gathering_complete" in e) {
      if (this.gatheringComplete) return [];
      this.gatheringComplete = true;
      if (!this.active) return [];
      this.endSent = true;
      return [{ send_info: { candidates: 0, end_of_candidates: true } }];
    }
    if ("active" in e) {
      this.active = true;
      if (this.local === 0 && !this.gatheringComplete) return [];
      const out = [{ send_info: { candidates: this.local, end_of_candidates: this.gatheringComplete } }];
      this.endSent = this.gatheringComplete;
      this.local = 0;
      return out;
    }
    if ("remote_description" in e) {
      this.remoteDescription = true;
      const n = this.remote;
      this.remote = 0;
      return n ? [{ apply: n }] : [];
    }
    const info = e["remote_info"] as JsonObject;
    // B§4.4: only the device that is party to the media session
    if (info["from"] !== this.peer) return [{ ignore: "not-party" }];
    if (this.remoteEnded) return [{ ignore: "after-end" }];
    const n = (info["candidates"] as Json[]).length;
    if (!this.remoteDescription) {
      this.remote += n;
      if (info["end_of_candidates"] === true) this.remoteEnded = true;
      return [{ buffer: "remote", n: this.remote }];
    }
    const out: Json[] = n ? [{ apply: n }] : [];
    if (info["end_of_candidates"] === true) {
      this.remoteEnded = true;
      out.push({ remote_end: true });
    }
    return out;
  }
}

/** Local-description handling across a renegotiation. Spec: B§5.2, B§5.4 */
export class Renegotiation {
  private pendingLocal = false;
  private pendingRemote = false;

  constructor(private readonly ufrag: string) {}

  /** Apply one event; returns the emissions. */
  step(e: JsonObject): Json[] {
    if ("local_reoffer" in e) {
      // B§5.4: binding 1.0 has no ICE restart; our own re-offer MUST keep the credentials
      if ((e["local_reoffer"] as JsonObject)["ufrag"] !== this.ufrag) {
        return [{ error: "binding-ice-restart", detail: "a re-offer MUST keep the ICE credentials" }];
      }
      this.pendingLocal = true;
      return [{ local_description: "pending" }];
    }
    if ("remote_answer" in e || "remote_reject" in e) {
      if (!this.pendingLocal) return [{ ignore: "no-pending-offer" }];
      this.pendingLocal = false;
      // B§5.2: on reject, roll back so the media path is exactly the last negotiated one
      return ["remote_answer" in e ? { apply: "answer" } : { rollback: true }, { local_description: "current" }];
    }
    if ("remote_reoffer" in e) {
      if ((e["remote_reoffer"] as JsonObject)["ufrag"] !== this.ufrag) {
        return [{ reject: { reason: "media.unsupported", detail: "ice-restart" } }];
      }
      // B§5.2: the offer is not applied until we decide to answer
      this.pendingRemote = true;
      return [{ ui: "update_offered" }];
    }
    if ("answer_update" in e) {
      if (!this.pendingRemote) return [{ ignore: "no-pending-offer" }];
      this.pendingRemote = false;
      return [{ apply: "remote-offer+answer" }];
    }
    throw new Error(`unknown renegotiation event ${JSON.stringify(e)}`);
  }
}
