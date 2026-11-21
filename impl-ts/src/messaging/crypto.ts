/**
 * The cryptographic formats of the Messaging Profile below MLS itself: extension encoding, the
 * DSIP authentication service for MLS leaves, AES-256-GCM sealing, and HPKE for sealed introductions.
 *
 * Spec: M§6.2 (credentials), M§6.3 (`dsip_conversation` bytes), M§6.9 (HPKE suite, RFC 9180 base
 * mode), M§8.4 / M§11.1 / M§12.2 (sealing and its AAD), M§14.1 (sealed introductions), M§17
 * (codepoints), RFC 9420 §2.1.2 (variable-length integers).
 */
import { createCipheriv, createDecipheriv, createHash } from "node:crypto";
import type { Json, JsonObject } from "../did.js";
import { b64urlDecode, ed25519FromMultibase, utf8Decode } from "../encoding.js";
import { decodePayload, delegationSubject, type ReceiverContext } from "../envelope.js";
import { reject, type Verdict } from "../verdict.js";
import { checkConversationExt } from "./message.js";
import { HPKE_SEALED_ALG, hpkeOpen } from "../hpke.js";
import { listsProfileCard, takeCard } from "../profile-card.js";

export { hpkeDeriveKeyPair, hpkeOpen, x25519FromEd25519Seed } from "../hpke.js";

/** Spec: M§17 — private-use MLS extension type carrying the leaf's DeviceDelegation. */
export const DSIP_DELEGATION = 0xf0d1;
/** Spec: M§17 — private-use MLS GroupContext extension type. */
export const DSIP_CONVERSATION = 0xf0d2;

// ---- RFC 9420 §2.1.2 extension encoding

/** `uint16 type ‖ minimal variable-length size ‖ data`. */
export function encodeExtension(type: number, data: Buffer): Buffer {
  const n = data.length;
  const size =
    n < 0x40 ? Buffer.from([n])
    : n < 0x4000 ? Buffer.from([0x40 | (n >> 8), n & 0xff])
    : Buffer.from([0x80 | (n >>> 24), (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff]);
  return Buffer.concat([Buffer.from([type >> 8, type & 0xff]), size, data]);
}

/** Decode one extension; the length must be minimal and nothing may follow the data. */
export function decodeExtension(bytes: Buffer): Verdict {
  if (bytes.length < 3) return reject("mls-truncated");
  const prefix = bytes[2]! >> 6;
  if (prefix === 3) return reject("mls-length-invalid"); // the 8-byte form exceeds MLS's 30-bit bound
  const width = 1 << prefix;
  if (bytes.length < 2 + width) return reject("mls-truncated");
  let n = bytes[2]! & 0x3f;
  for (let i = 1; i < width; i++) n = n * 256 + bytes[2 + i]!;
  if ((width === 2 && n < 0x40) || (width === 4 && n < 0x4000)) return reject("mls-length-non-minimal");
  const data = bytes.subarray(2 + width);
  if (data.length < n) return reject("mls-truncated");
  if (data.length > n) return reject("mls-trailing-bytes");
  return { verdict: "accept", extension_type: bytes.readUInt16BE(0), data_hex: data.toString("hex") };
}

/** Spec: M§6.3 — the extension data is UTF-8 JSON obeying §10.3, then the `dsip-conversation` shape. */
export function checkConversationBytes(data: Buffer): Verdict {
  const decoded = decodePayload(data);
  return decoded.ok ? checkConversationExt(decoded.value) : decoded.error;
}

// ---- M§6.2 the DSIP authentication service

/** Spec: M§6.2 — the checks, in the order the profile lists them. */
export function checkCredential(
  credential: { credential_type: number; identity_hex: string },
  signatureKey: Buffer,
  extensions: { extension_type: number; data_hex: string }[],
  ctx: ReceiverContext,
): Verdict {
  if (credential.credential_type !== 1) return reject("credential-type"); // `basic` only in 1.0
  const device = utf8Decode(Buffer.from(credential.identity_hex, "hex"));
  if (device === null || !/^did:[a-z0-9]+:\S+$/.test(device)) return reject("credential-identity");
  const delegations = extensions.filter((e) => e.extension_type === DSIP_DELEGATION);
  if (delegations.length === 0) return reject("delegation-missing");
  if (delegations.length > 1) return reject("delegation-invalid"); // exactly one
  // the data is the compact envelope as ASCII bytes
  const compact = Buffer.from(delegations[0]!.data_hex, "hex").toString("latin1");
  const bound = delegationSubject(compact, device, "dsip.messaging", ctx);
  if ("verdict" in bound) return bound;
  // one device key signs both DSIP envelopes and MLS leaf operations
  const deviceKey = device.startsWith("did:key:") ? ed25519FromMultibase(device.slice("did:key:".length)) : null;
  if (!deviceKey || !deviceKey.equals(signatureKey)) return reject("credential-key-mismatch");
  return { verdict: "accept", identity: bound.subject, device };
}

// ---- AES-256-GCM sealing

function u64be(n: number): Buffer {
  const b = Buffer.alloc(8);
  b.writeBigUInt64BE(BigInt(n));
  return b;
}

/** What is being sealed, and the values its AAD binds. */
export interface SealUse {
  use: "blob" | "activity" | "archive";
  group_hex?: string;
  epoch?: number;
  seq?: number;
}

/** Spec: M§8.4 (no AAD), M§11.1 (`group_id ‖ epoch`), M§12.2 (`group_id ‖ seq`); integers are 8-byte big-endian. */
function aad(u: SealUse): Buffer {
  if (u.use === "blob") return Buffer.alloc(0);
  return Buffer.concat([Buffer.from(u.group_hex!, "hex"), u64be(u.use === "activity" ? u.epoch! : u.seq!)]);
}

/** `nonce (12) ‖ ciphertext ‖ tag (16)`. */
export function seal(u: SealUse, key: Buffer, nonce: Buffer, plaintext: Buffer): Buffer {
  const c = createCipheriv("aes-256-gcm", key, nonce);
  c.setAAD(aad(u));
  return Buffer.concat([nonce, c.update(plaintext), c.final(), c.getAuthTag()]);
}

/** Open sealed bytes. Spec: M§8.4 rule 7 — a blob's size and hash are verified before decrypting. */
export function open(u: SealUse & { size?: number; sha256?: string }, key: Buffer, sealed: Buffer): Verdict {
  if (u.use === "blob") {
    if (u.size !== undefined && sealed.length !== u.size) return reject("blob-size-mismatch");
    if (u.sha256 !== undefined && createHash("sha256").update(sealed).digest("hex") !== u.sha256) return reject("blob-hash-mismatch");
  }
  if (sealed.length < 28) return reject("sealed-too-short");
  try {
    const d = createDecipheriv("aes-256-gcm", key, sealed.subarray(0, 12));
    d.setAAD(aad(u));
    d.setAuthTag(sealed.subarray(sealed.length - 16));
    const plaintext = Buffer.concat([d.update(sealed.subarray(12, sealed.length - 16)), d.final()]);
    return { verdict: "accept", plaintext_hex: plaintext.toString("hex") };
  } catch {
    return reject("aead-open-failed");
  }
}

// ---- M§14.1 sealed introductions

const SEALED_ALG = HPKE_SEALED_ALG;
const SEALED_INFO = Buffer.from("dsip sealed introduction v1");
/** Spec: §19.4 — `purpose` is at most 280 characters, sealed or not. */
const MAX_PURPOSE_CHARS = 280;

/**
 * The purpose of an introduction, and the introducer's profile card when the sealed plaintext holds one, opening
 * `sealed` with the recipient's key agreement key.
 *
 * Spec: M§14.1, §19.4
 */
export function openIntroduction(payload: JsonObject, recipientSk: Buffer): Verdict {
  const sealed = payload["sealed"] as JsonObject | undefined;
  if (!sealed) return { verdict: "accept", purpose: (payload["purpose"] ?? null) as Json };
  if (sealed["alg"] !== SEALED_ALG) return reject("sealed-alg-unsupported");
  // AAD = id ‖ 0x00 ‖ from ‖ 0x00 ‖ to: a sealed body cannot be spliced into another introduction
  const zero = Buffer.from([0]);
  const aadBytes = Buffer.concat([
    Buffer.from(payload["id"] as string, "utf8"), zero, Buffer.from(payload["from"] as string, "utf8"), zero,
    Buffer.from(payload["to"] as string, "utf8"),
  ]);
  const enc = b64urlDecode(sealed["enc"] as string);
  const ct = b64urlDecode(sealed["ct"] as string);
  const plaintext = enc && ct ? hpkeOpen(enc, recipientSk, SEALED_INFO, aadBytes, ct) : null;
  if (!plaintext) return reject("sealed-open-failed");
  const decoded = decodePayload(plaintext); // §10.3: UTF-8, a JSON object, no floats
  if (!decoded.ok) return reject("sealed-plaintext-invalid");
  const value: Json = decoded.value;
  // the plaintext is exactly {"purpose": "…"}, optionally with `profile` (§19.4, profile-card/1.0)
  const exact = value !== null && typeof value === "object" && !Array.isArray(value) &&
    typeof value["purpose"] === "string" && Object.keys(value).every((k) => k === "purpose" || k === "profile");
  if (!exact) return reject("sealed-plaintext-invalid");
  const purpose = (value as JsonObject)["purpose"] as string;
  if ([...purpose].length > MAX_PURPOSE_CHARS) return reject("purpose-too-long");
  if (!("profile" in (value as JsonObject))) return { verdict: "accept", purpose };
  // §19.4: a card that fails, or one on an introduction that does not list the extension, leaves the purpose as it is
  const card = listsProfileCard(payload) ? takeCard((value as JsonObject)["profile"]) : null;
  return card === null ? { verdict: "accept", purpose, profile_ignored: true } : { verdict: "accept", purpose, profile: card };
}
