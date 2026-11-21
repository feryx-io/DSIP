/**
 * Profile cards: the extension `profile-card/1.0`. A card is the name and small picture an identity asks to be shown
 * as, sealed to the other party on an `introduction` (in the sealed plaintext, beside `purpose`) or on a `grant`
 * (member `profile`). This module holds the card's own rules, the introduction cap the extension raises, opening a
 * grant's card, and the sender's decision whether a card may go.
 *
 * Spec: §19.4 (Profile cards), §11.4, §18.2
 */

import type { Json, JsonObject } from "./did.js";
import { b64urlDecode, utf8Decode } from "./encoding.js";
import { decodePayload } from "./envelope.js";
import { HPKE_SEALED_ALG, hpkeOpen } from "./hpke.js";
import { reject, type Verdict } from "./verdict.js";

/** The extension's id, as listed in `dsip.extensions`. Spec: §19.4 */
export const PROFILE_CARD_EXT = "profile-card/1.0";
/** Spec: §19.4 — the core constant every introduction without the extension keeps. */
export const MAX_INTRODUCTION_BYTES = 4096;
/** Spec: §19.4 — the cap of an introduction that carries `sealed` and lists the extension. */
export const MAX_CARD_INTRODUCTION_BYTES = 16384;

const MAX_NAME_CHARS = 256;
const MAX_PICTURE_BYTES = 4096;
const PICTURE_TYPES = ["image/jpeg", "image/png"];
const PROFILE_INFO = Buffer.from("dsip profile card v1");

function isObject(value: Json | undefined): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Whether a payload lists the extension in `dsip.extensions`. Spec: §19.4 */
export function listsProfileCard(payload: JsonObject): boolean {
  const dsip = payload["dsip"];
  const extensions = isObject(dsip) ? dsip["extensions"] : undefined;
  return Array.isArray(extensions) && extensions.includes(PROFILE_CARD_EXT);
}

/**
 * The cap of an introduction: 16,384 bytes when it carries `sealed` and lists the extension, 4,096 otherwise. A holder
 * cannot see whether the sealed plaintext holds a card, so the cap is the extension's, not the card's.
 *
 * Spec: §19.4
 */
export function introductionCap(payload: JsonObject): number {
  return "sealed" in payload && listsProfileCard(payload) ? MAX_CARD_INTRODUCTION_BYTES : MAX_INTRODUCTION_BYTES;
}

/**
 * The cap of an introduction carried as a compact envelope (a mailbox deposit): the holder reads its payload for
 * `sealed` and the extension. An envelope that cannot be read as three parts with a JSON object payload stays at 4,096.
 *
 * Spec: §19.4, M§14.1
 */
export function introductionCapCompact(envelope: string): number {
  const parts = envelope.split(".");
  if (parts.length !== 3) return MAX_INTRODUCTION_BYTES;
  const bytes = b64urlDecode(parts[1] as string);
  const text = bytes ? utf8Decode(bytes) : null;
  if (text === null) return MAX_INTRODUCTION_BYTES;
  let payload: Json;
  try {
    payload = JSON.parse(text);
  } catch {
    return MAX_INTRODUCTION_BYTES;
  }
  return isObject(payload) ? introductionCap(payload) : MAX_INTRODUCTION_BYTES;
}

/**
 * A card as taken: its known members, any other dropped. `null` when the card is ignored, which is whole or not at
 * all: not an object, a `display_name` that is not 1 to 256 characters, or a `picture` that is not exactly a listed
 * `content_type` and unpadded base64url `data` of 1 to 4,096 bytes.
 *
 * Spec: §19.4
 * Impl: the picture's bytes are counted from the length of `data`, ⌊3n/4⌋, as the vectors README fixes; the string is
 * not decoded and the image is not parsed (spec-gap 186).
 */
export function takeCard(card: Json | undefined): JsonObject | null {
  if (!isObject(card)) return null;
  const taken: JsonObject = {};
  if ("display_name" in card) {
    const name = card["display_name"];
    if (typeof name !== "string") return null;
    const chars = [...name].length; // Unicode code points, not UTF-16 units
    if (chars < 1 || chars > MAX_NAME_CHARS) return null;
    taken["display_name"] = name;
  }
  if ("picture" in card) {
    const picture = card["picture"];
    if (!isObject(picture) || Object.keys(picture).length !== 2) return null;
    const contentType = picture["content_type"];
    const data = picture["data"];
    if (typeof contentType !== "string" || typeof data !== "string" || !PICTURE_TYPES.includes(contentType)) return null;
    if (!/^[A-Za-z0-9_-]+$/.test(data) || data.length % 4 === 1) return null;
    const bytes = Math.floor((data.length * 3) / 4);
    if (bytes < 1 || bytes > MAX_PICTURE_BYTES) return null;
    taken["picture"] = { content_type: contentType, data };
  }
  return taken;
}

/**
 * The card a grant's `profile` carries, opened with the grantee identity's key agreement key, or why it is ignored.
 * Every refusal here leaves the grant standing as if it carried no card.
 *
 * Spec: §19.4
 */
export function openGrantProfile(grant: JsonObject, recipientSk: Buffer): Verdict {
  const sealed = grant["profile"];
  if (sealed === undefined) return { verdict: "accept", profile: null };
  if (!listsProfileCard(grant)) return reject("profile-extension-unlisted");
  if (!isObject(sealed) || sealed["alg"] !== HPKE_SEALED_ALG) return reject("sealed-alg-unsupported");
  // AAD = id ‖ 0x00 ‖ from ‖ 0x00 ‖ to of the grant: a card cannot be moved to another grant
  const zero = Buffer.from([0]);
  const aad = Buffer.concat([
    Buffer.from(grant["id"] as string, "utf8"), zero, Buffer.from(grant["from"] as string, "utf8"), zero,
    Buffer.from(grant["to"] as string, "utf8"),
  ]);
  const enc = typeof sealed["enc"] === "string" ? b64urlDecode(sealed["enc"]) : null;
  const ct = typeof sealed["ct"] === "string" ? b64urlDecode(sealed["ct"]) : null;
  const plaintext = enc && ct ? hpkeOpen(enc, recipientSk, PROFILE_INFO, aad, ct) : null;
  if (!plaintext) return reject("sealed-open-failed");
  const decoded = decodePayload(plaintext); // §10.3: UTF-8, a JSON object, no floats
  if (!decoded.ok) return reject("sealed-plaintext-invalid");
  const value: JsonObject = decoded.value;
  // the plaintext is exactly {"profile": card}
  if (Object.keys(value).length !== 1 || !("profile" in value)) return reject("sealed-plaintext-invalid");
  const card = takeCard(value["profile"]);
  return card === null ? reject("profile-card-invalid") : { verdict: "accept", profile: card };
}

/** What `profile-card-send` is asked. Spec: §19.4 */
export interface CardSendInput {
  /** The user's standing choice for this carrier; off by default. */
  sharing: boolean;
  /** The message the card would ride. */
  carrier: "introduction" | "grant";
  /** What is known of the receiving identity's support. */
  peer?: { listed?: string[]; document?: JsonObject | null; out_of_band?: string[] } | null;
  /** The encoded envelope with the card. */
  encoded_size: number;
  /** The `hello` capability of the service an introduction would be handed to; absent when it advertises none. */
  service_introduction_max_bytes?: number;
}

/**
 * Whether a card goes with an introduction or a grant: only by the user's choice, only to an identity known to support
 * the extension, and on an introduction only through a service that takes an envelope of that size.
 *
 * Spec: §19.4, §11.4
 */
export function profileCardSend(input: CardSendInput): JsonObject {
  if (!input.sharing) return { card: false, why: "sharing-off" };
  const peer = input.peer ?? {};
  const documented = isObject(peer.document ?? null) ? (peer.document as JsonObject)["dsipExtensions"] : undefined;
  const known = (peer.listed ?? []).includes(PROFILE_CARD_EXT)
    || (Array.isArray(documented) && documented.includes(PROFILE_CARD_EXT))
    || (peer.out_of_band ?? []).includes(PROFILE_CARD_EXT);
  if (!known) return { card: false, why: "peer-unsupported" };
  if (input.carrier === "introduction") {
    const cap = input.service_introduction_max_bytes ?? MAX_INTRODUCTION_BYTES;
    if (input.encoded_size > cap) return { card: false, why: "service-cap" };
  }
  return { card: true };
}
