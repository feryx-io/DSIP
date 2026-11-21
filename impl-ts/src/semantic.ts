/**
 * Checks on a decoded payload: version negotiation, shape, and the stateless semantic checks.
 *
 * Spec: §11 (versions), §10.3 (schemas), §10.4 (sealed bodies), §15.1 (reason fallback), and the schema README's semantic checks
 * 5, 7, 9, 11, 12; P§3 (the `presence` record's `device`), P§5 (`dsip-presence-state` fallback).
 */
import { didOf, type Json, type JsonObject } from "./did.js";
import { b64urlDecode } from "./encoding.js";
import { decodePayload } from "./envelope.js";
import { HPKE_SEALED_ALG, hpkeOpen } from "./hpke.js";
import { introductionCap } from "./profile-card.js";
import { effectiveAnsweredBy, effectivePresenceState, effectiveReason, effectiveStatus, isRegisteredPresenceState } from "./registry.js";
import type { SchemaSet } from "./schema.js";
import { reject, type Verdict } from "./verdict.js";

/** What the receiver supports. Spec: §11.1 */
export interface Supported {
  /** Highest core version implemented, `major.minor`. */
  core: string;
  /** Profiles implemented, `name/major.minor`. */
  profiles: string[];
  /** Extensions implemented. */
  extensions: string[];
}

/** Receiver context the stateless checks read. Absent members switch their check off. */
export interface SemanticContext {
  supported?: Supported;
  /** The offer an `answer` refers to (check 9). */
  offer?: JsonObject;
  /** Ids of introductions this receiver sent or holds (check 11). */
  known_introductions?: string[];
  /** Live grants held from the signer's identity, which a grant may follow (spec-gap 150; with check 11 only). */
  held_grants?: string[];
  /** Id of the client `hello` actually sent on this connection (check 7). */
  sent_hello_id?: string;
  /** Size of the envelope as received, in bytes (check 11). */
  encoded_size?: number;
  /** The `kid` that signed the envelope (check 12). */
  signer_kid?: string;
  /** The addressee's X25519 key agreement private key, hex: the receiver opens seals (stage 12b). Spec: §10.4 */
  unseal_key_hex?: string;
  /** The receiver routes rather than receives: it never opens a seal. Spec: §10.4 */
  router?: boolean;
}

/** Spec: §9.3 — per-event `expires_in` cap for presence. */
const MAX_PRESENCE_SUBSCRIPTION_S = 3600;

function version(text: Json | undefined): [number, number] | null {
  const m = typeof text === "string" ? /^(\d+)\.(\d+)$/.exec(text) : null;
  return m ? [Number(m[1]), Number(m[2])] : null;
}

/**
 * Stage 12. Spec: §11.2 — major versions are incompatible, minor versions are backward-compatible,
 * unknown critical extensions require rejection; §11.3 names the tokens.
 * Impl: a profile list is acceptable when at least one entry matches a supported profile's name and
 * major version; the spec says only "no mutually supported profile version".
 */
export function checkVersion(payload: JsonObject, supported: Supported, router = false): Verdict | null {
  const block = payload["dsip"] as JsonObject;
  const ours = version(supported.core);
  const core = version(block["core"]);
  const min = version(block["min_core"]);
  if (!ours || !core || !min) return null; // shape is stage 13's concern
  const minAboveOurs = min[0] > ours[0] || (min[0] === ours[0] && min[1] > ours[1]);
  if (core[0] !== ours[0] || minAboveOurs) return reject("version-unsupported", "session.unsupported-core-version");
  const profiles = Array.isArray(block["profiles"]) ? block["profiles"] : [];
  if (profiles.length > 0) {
    const mutual = profiles.some((p) => {
      const [name, v] = typeof p === "string" ? p.split("/") : [];
      const pv = version(v);
      return supported.profiles.some((s) => {
        const [sname, sv] = s.split("/");
        const spv = version(sv);
        return pv && spv && sname === name && spv[0] === pv[0];
      });
    });
    if (!mutual) return reject("version-unsupported", "session.unsupported-profile-version");
  }
  let critical = Array.isArray(block["critical"]) ? block["critical"] : [];
  // §10.4: a router routes a sealed payload whether or not it implements `sealed-body/1.0`;
  // the critical-extension rule binds the addressee.
  if (router && "sealed" in payload) critical = critical.filter((c) => c !== SEALED_BODY_EXTENSION);
  if (critical.some((c) => typeof c !== "string" || !supported.extensions.includes(c))) {
    return reject("version-unsupported", "session.unsupported-critical-extension");
  }
  return null;
}

/** Spec: §10.4 — the extension token that announces a sealed body. */
export const SEALED_BODY_EXTENSION = "sealed-body/1.0";
/** Spec: §10.4 — HPKE `info` for sealed bodies. */
export const SEALED_BODY_INFO = "dsip sealed body v1";
/** Spec: §10.4 — the plaintext is padded to a positive multiple of this many bytes. */
const SEALED_BODY_BLOCK = 256;
/** Spec: §10.4 table — the fields each message type may seal; every other field stays in clear. */
export const SEALABLE_FIELDS: Record<string, readonly string[]> = {
  invite: ["identity", "intent", "policy", "media", "transports"],
  answer: ["answered_by", "media", "policy", "transports"],
  update: ["answered_by", "media", "policy", "transports"],
  info: ["about", "data"],
  reject: ["detail"],
  cancel: ["detail"],
  bye: ["detail"],
};

/**
 * Stage 12b: open a sealed body with the addressee's key agreement key and merge it into the clear
 * fields. Returns the merged payload and the opened keys (sorted), a rejection, or `null` when there
 * is nothing for this stage to do (no `sealed`, or a `sealed` whose shape stage 13 will judge).
 *
 * Spec: §10.4 — conditions in order: not critical, unknown `alg`, does not open, plaintext not a
 * §10.3 JSON object with at least one key or not padded to a positive multiple of 256 bytes, a key
 * outside the type's sealable fields, a key both sealed and in clear. AAD = `type ‖ 0x00 ‖ id ‖ 0x00 ‖
 * from ‖ 0x00 ‖ to`.
 * Impl: a payload whose `type`, `id`, `from` or `to` is not a string (no AAD can be formed) is left
 * for stage 13, as a malformed `sealed` is; a `dsip.critical` that is not an array lists nothing.
 */
export function openSealedBody(
  payload: JsonObject,
  recipientSk: Buffer,
): { payload: JsonObject; opened: string[] } | Verdict | null {
  const sealed = payload["sealed"];
  if (sealed === undefined) return null;
  if (!sealed || typeof sealed !== "object" || Array.isArray(sealed)) return null;
  const { alg, enc, ct } = sealed as JsonObject;
  if (typeof alg !== "string" || typeof enc !== "string" || typeof ct !== "string") return null;
  const aadParts = [payload["type"], payload["id"], payload["from"], payload["to"]];
  if (aadParts.some((x) => typeof x !== "string")) return null;
  const block = payload["dsip"];
  const critical = block && typeof block === "object" && !Array.isArray(block) && Array.isArray(block["critical"])
    ? block["critical"] : [];
  if (!critical.includes(SEALED_BODY_EXTENSION)) return reject("sealed-not-critical");
  if (alg !== HPKE_SEALED_ALG) return reject("sealed-alg-unsupported");
  const aad = Buffer.from((aadParts as string[]).join("\u0000"), "utf8");
  const encBytes = b64urlDecode(enc);
  const ctBytes = b64urlDecode(ct);
  const plaintext = encBytes && ctBytes ? hpkeOpen(encBytes, recipientSk, Buffer.from(SEALED_BODY_INFO), aad, ctBytes) : null;
  if (!plaintext) return reject("body-unseal-failed");
  const decoded = decodePayload(plaintext); // §10.3: UTF-8, JSON object, no floats
  if (!decoded.ok) return reject("sealed-plaintext-invalid");
  const fields = decoded.value;
  const keys = Object.keys(fields);
  if (keys.length === 0 || plaintext.length === 0 || plaintext.length % SEALED_BODY_BLOCK !== 0) {
    return reject("sealed-plaintext-invalid");
  }
  const sealable = SEALABLE_FIELDS[payload["type"] as string] ?? [];
  if (keys.some((k) => !sealable.includes(k))) return reject("sealed-field-not-sealable");
  if (keys.some((k) => k in payload)) return reject("sealed-field-in-clear");
  const merged: JsonObject = { ...payload, ...fields };
  delete merged["sealed"];
  return { payload: merged, opened: keys.sort() };
}

/** Stage 13. Spec: §10.3 */
export function checkShape(payload: JsonObject, schemas: SchemaSet): Verdict | null {
  const type = payload["type"];
  if (typeof type !== "string" || !schemas.isMessageType(type)) return reject("unknown-type");
  return schemas.validMessage(type, payload) ? null : reject("schema-invalid");
}

/** SDP-style answers to an offered direction. Spec: §14.2; Impl: vectors README, check 9 */
const ANSWERS: Record<string, string[]> = {
  sendrecv: ["sendrecv", "sendonly", "recvonly", "inactive"],
  sendonly: ["recvonly", "inactive"],
  recvonly: ["sendonly", "inactive"],
  inactive: ["inactive"],
};

function isSubset(selection: JsonObject, offer: JsonObject): boolean {
  const offered = (offer["media"] ?? []) as JsonObject[];
  for (const sel of (selection["media"] ?? []) as JsonObject[]) {
    const match = offered.find(
      (o) => o["type"] === sel["type"] && (!("purpose" in sel) || o["purpose"] === sel["purpose"]),
    );
    if (!match) return false;
    const ids = ((match["codecs"] ?? []) as JsonObject[]).map((c) => c["id"]);
    if (((sel["codecs"] ?? []) as JsonObject[]).some((c) => !ids.includes(c["id"]!))) return false;
    const offeredDir = (match["direction"] ?? "sendrecv") as string;
    const selectedDir = (sel["direction"] ?? "sendrecv") as string;
    if (!(ANSWERS[offeredDir] ?? []).includes(selectedDir)) return false;
  }
  const transports = ((offer["transports"] ?? []) as JsonObject[]).map((t) => t["id"]);
  return ((selection["transports"] ?? []) as JsonObject[]).every((t) => transports.includes(t["id"]!));
}

/** Stage 14, rejecting half. */
export function checkSemantics(payload: JsonObject, ctx: SemanticContext): Verdict | null {
  const type = payload["type"];
  if ((type === "answer" || type === "reject") && ctx.offer && !isSubset(payload, ctx.offer)) {
    return reject("selection-not-subset"); // check 9
  }
  if (type === "subscribe") {
    const events = (payload["events"] ?? []) as Json[];
    if (events.includes("presence") && (payload["expires_in"] as number) > MAX_PRESENCE_SUBSCRIPTION_S) {
      return reject("subscription-lifetime-exceeded", "policy.subscription-lifetime"); // §9.3
    }
  }
  if (type === "introduction") {
    if ("purpose" in payload && "sealed" in payload) return reject("introduction-purpose-and-sealed"); // §19.4
    if (ctx.encoded_size !== undefined && ctx.encoded_size > introductionCap(payload)) {
      return reject("introduction-too-large"); // §19.4: 4,096, or 16,384 with `sealed` and profile-card/1.0
    }
  }
  if (type === "grant" && ctx.known_introductions && !ctx.known_introductions.includes(payload["session"] as string)
    && !(ctx.held_grants ?? []).includes(payload["session"] as string)) {
    return reject("grant-unknown-introduction"); // §19.4, spec-gap 150
  }
  if (type === "hello" && "in_reply_to" in payload && ctx.sent_hello_id !== undefined) {
    // §13.2, §20.5: anti-splicing — the relay's hello answers the hello this client sent.
    if (payload["in_reply_to"] !== ctx.sent_hello_id) return reject("hello-in-reply-to-mismatch");
  }
  if (type === "presence" && "device" in payload && payload["device"] !== payload["from"]) {
    // P§3: a record's `device`, when present, is its signer; without it, a v0.16-form record (P§4).
    return reject("presence-signer-mismatch", "presence.signer-mismatch");
  }
  if (type === "presence" && "sealed_state" in payload) {
    // P§12.2: a sealed record names presence/0.2; its audience is never `main`; its kid's scope is its audience, or `main` without one.
    const profiles = (payload["dsip"] as JsonObject | undefined)?.["profiles"];
    const audience = typeof payload["audience"] === "string" ? payload["audience"] : undefined;
    const kid = String(payload["kid"]);
    const scope = kid.includes(".") ? kid.slice(0, kid.lastIndexOf(".")) : kid;
    if (!Array.isArray(profiles) || !profiles.includes("presence/0.2") || audience === "main" || scope !== (audience ?? "main")) {
      return reject("presence-sealed-invalid", "presence.sealed-invalid");
    }
  }
  if (type === "key-rotation") {
    // §7.5
    if (payload["from"] !== payload["subject"]) return reject("rotation-subject-mismatch");
    if (payload["next"] === payload["previous"]) return reject("rotation-next-same-as-previous");
    if (ctx.signer_kid !== undefined && ctx.signer_kid !== payload["previous"] && payload["recovery"] !== true) {
      return reject("rotation-signer-not-previous");
    }
  }
  if (type === "delegation-revocation") {
    // §7.4 (v0.8)
    if (payload["from"] !== payload["subject"]) return reject("revocation-subject-mismatch");
    if (ctx.signer_kid !== undefined && didOf(ctx.signer_kid) !== payload["subject"]) {
      return reject("revocation-signer-not-subject");
    }
  }
  return null;
}

/** Stage 14, accepting half: the effective reading of registry-governed values (check 5). */
export function interpret(payload: JsonObject): { effective?: JsonObject; warnings?: string[] } {
  const type = payload["type"] as string;
  const effective: JsonObject = {};
  const warnings: string[] = [];
  if (["reject", "cancel", "bye", "error", "notify"].includes(type) && typeof payload["reason"] === "string") {
    const e = effectiveReason(payload["reason"], type);
    effective["reason"] = e.reason;
    effective["fallback"] = e.fallback;
    // Impl: §9.3 puts `session.expired` / `policy.terminated` on a terminal `notify`, but the §15.4
    // "valid on" column never lists `notify`; the column is not applied to it (spec-gap 73).
    if (!e.validOnType && type !== "notify") warnings.push("reason-not-valid-on-type");
  }
  if (typeof payload["answered_by"] === "string") effective["answered_by"] = effectiveAnsweredBy(payload["answered_by"]);
  if (type === "progress" && typeof payload["status"] === "string") effective["status"] = effectiveStatus(payload["status"]);
  if (type === "presence" && typeof payload["state"] === "string") {
    // P§5: the registry is open — an unknown state is accepted and read as `available`.
    effective["state"] = effectivePresenceState(payload["state"]);
    if (!isRegisteredPresenceState(payload["state"])) warnings.push("presence-state-unknown");
  }
  return {
    ...(Object.keys(effective).length ? { effective } : {}),
    ...(warnings.length ? { warnings } : {}),
  };
}

/** Stages 12–14 over a decoded payload. Spec: §11.2, §10.4, §10.3 */
export function checkPayload(payload: JsonObject, ctx: SemanticContext, schemas: SchemaSet): Verdict {
  const router = ctx.router === true;
  const versionFailed = ctx.supported ? checkVersion(payload, ctx.supported, router) : null;
  if (versionFailed) return versionFailed;
  let opened: string[] | null = null;
  if (!router && ctx.unseal_key_hex !== undefined) {
    const result = openSealedBody(payload, Buffer.from(ctx.unseal_key_hex, "hex"));
    if (result && "verdict" in result) return result as Verdict;
    if (result) ({ payload, opened } = result as { payload: JsonObject; opened: string[] });
  }
  const failed = checkShape(payload, schemas) ?? checkSemantics(payload, ctx);
  if (failed) return failed;
  const { effective, warnings } = interpret(payload);
  const eff: JsonObject = { ...(effective ?? {}), ...(opened ? { sealed: opened } : {}) };
  return {
    verdict: "accept",
    ...(Object.keys(eff).length ? { effective: eff } : {}),
    ...(warnings ? { warnings } : {}),
  };
}
