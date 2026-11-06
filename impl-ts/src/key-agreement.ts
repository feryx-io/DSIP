/**
 * Key agreement delegation: an identity-signed credential naming an independent X25519 key, and the
 * X25519 key agreement key a sender seals to.
 *
 * Spec: §7.3 ("Key agreement delegation", 1.x, spec-gap 179), §10.4 rule 3 (the recipient key),
 * DHT Hints Profile §2 and §4 step 2 (the hint's `key_agreement` member). Contract:
 * `impl/vectors/README.md`, "Kind: `key-agreement`".
 */
import type { Json, JsonObject } from "./did.js";
import { base58Decode, base58Encode, ed25519FromMultibase } from "./encoding.js";
import { openCredential, type ReceiverContext } from "./envelope.js";
import type { SchemaSet } from "./schema.js";
import { reject, type Verdict } from "./verdict.js";

/** The longest key agreement delegation. Spec: §7.3 (`expires_at ≤ issued_at + 31,536,000`). */
export const MAX_KEY_AGREEMENT_VALIDITY_S = 31_536_000;
/** How far ahead `issued_at` may be. Spec: §7.3 (`issued_at ≤ now + 300`). */
const FUTURE_S = 300;
/** Multicodec `x25519-pub`. Spec: §7.3 (`key` is encoded as did:key encodes an X25519 key). */
const X25519_PUB = [0xec, 0x01];

/** The 32 raw bytes of a `z6LS…` multibase X25519 key, or `null`. Spec: §7.3 */
export function x25519FromMultibase(multibase: string): Buffer | null {
  if (!multibase.startsWith("z")) return null;
  const raw = base58Decode(multibase.slice(1));
  if (!raw || raw.length !== 34 || raw[0] !== X25519_PUB[0] || raw[1] !== X25519_PUB[1]) return null;
  return raw.subarray(2);
}

/** Multibase base58btc of `x25519-pub` and the key. Spec: §7.3 */
export function x25519ToMultibase(key: Uint8Array): string {
  return "z" + base58Encode(Buffer.concat([Buffer.from(X25519_PUB), Buffer.from(key)]));
}

const P = 2n ** 255n - 19n;

function modPow(base: bigint, exp: bigint): bigint {
  let result = 1n;
  let b = ((base % P) + P) % P;
  for (let e = exp; e > 0n; e >>= 1n) {
    if (e & 1n) result = (result * b) % P;
    b = (b * b) % P;
  }
  return result;
}

/**
 * The X25519 public key the did:key method derives from an Ed25519 public key: the Montgomery
 * `u = (1 + y) / (1 − y) mod 2^255 − 19`, little-endian.
 *
 * Spec: §7.3, §10.4 rule 3, M§6.9 (the derived key); README "Kind: `key-agreement`".
 */
export function x25519FromEd25519Public(ed25519: Uint8Array): Buffer {
  let y = 0n;
  for (let i = 31; i >= 0; i--) y = (y << 8n) | BigInt(ed25519[i]!);
  y &= (1n << 255n) - 1n; // the top bit is the sign of x
  const u = (((1n + y) % P) * modPow(1n - y, P - 2n)) % P;
  const out = Buffer.alloc(32);
  let n = u;
  for (let i = 0; i < 32; i++, n >>= 8n) out[i] = Number(n & 0xffn);
  return out;
}

/** A verified key agreement delegation. */
export interface KeyAgreementDelegation {
  subject: string;
  key: string;
  x25519: Buffer;
  issued_at: number;
  expires_at: number;
}

/**
 * Verify one key agreement delegation at `ctx.now`, optionally for `subject`.
 *
 * Spec: §7.3 — a credential (stages 2–6 as a delegation, no replay window, no dedup), valid against
 * `key-agreement-delegation`, signed directly by a verification key of its subject (never a device,
 * whatever delegation it holds), `issued_at < expires_at ≤ issued_at + 31,536,000`,
 * `issued_at ≤ now + 300`, `now < expires_at`. Refusal order: README "Kind: `key-agreement`".
 */
export function verifyKeyAgreement(
  value: Json | undefined,
  ctx: ReceiverContext,
  schemas: SchemaSet,
  subject?: string,
): KeyAgreementDelegation | ReturnType<typeof reject> {
  const opened = openCredential(value, ctx.did_documents ?? {});
  if ("verdict" in opened) return reject("credential-invalid");
  const p = opened.payload;
  // §7.3, vectors README (kind `key-agreement`): `key` must also decode to 0xec 0x01 + 32 bytes, which the
  // schema's pattern does not assure; a key that does not is `schema-invalid`.
  const x25519 = schemas.valid("key-agreement-delegation", p) ? x25519FromMultibase(p["key"] as string) : null;
  if (!x25519) return reject("schema-invalid");
  if (opened.signer !== p["subject"]) return reject("not-subject-signed");
  if (subject !== undefined && p["subject"] !== subject) return reject("subject-mismatch");
  const issued = p["issued_at"] as number;
  const expires = p["expires_at"] as number;
  if (!(issued < expires && expires <= issued + MAX_KEY_AGREEMENT_VALIDITY_S)) return reject("validity-invalid");
  if (issued > ctx.now + FUTURE_S) return reject("not-yet-valid");
  if (ctx.now >= expires) return reject("expired");
  return { subject: p["subject"] as string, key: p["key"] as string, x25519, issued_at: issued, expires_at: expires };
}

function isDelegation(v: KeyAgreementDelegation | ReturnType<typeof reject>): v is KeyAgreementDelegation {
  return !("verdict" in v);
}

/**
 * The current key agreement delegation among `candidates` for `did`: of those that verify, the
 * greatest `issued_at`, ties to the smaller `key` (compared as strings).
 *
 * Spec: §7.3 ("A newer one replaces an older one").
 */
export function currentKeyAgreement(
  did: string,
  candidates: Json[],
  ctx: ReceiverContext,
  schemas: SchemaSet,
): KeyAgreementDelegation | null {
  let best: KeyAgreementDelegation | null = null;
  for (const c of candidates) {
    const d = verifyKeyAgreement(c, ctx, schemas, did);
    if (!isDelegation(d)) continue;
    if (!best || d.issued_at > best.issued_at || (d.issued_at === best.issued_at && d.key < best.key)) best = d;
  }
  return best;
}

/**
 * The X25519 key agreement key of `did`: the document's `keyAgreement` method, else the current
 * verified key agreement delegation, else for `did:key` the derived key, else none.
 *
 * Spec: §7.3 (the key agreement key, in §8.1 order; a delegation is ignored when the document names
 * one), §10.4 rule 3.
 */
export function recipientKey(
  did: string,
  delegations: Json[],
  documentKeyAgreement: string | undefined,
  ctx: ReceiverContext,
  schemas: SchemaSet,
): JsonObject {
  const found = (source: string, key: string, raw: Buffer | null): JsonObject =>
    raw ? { verdict: "accept", source, key, x25519_pk_hex: raw.toString("hex") } : { verdict: "accept", source, key };
  if (documentKeyAgreement !== undefined) {
    return found("document", documentKeyAgreement, x25519FromMultibase(documentKeyAgreement));
  }
  const current = currentKeyAgreement(did, delegations, ctx, schemas);
  if (current) return found("delegation", current.key, current.x25519);
  if (did.startsWith("did:key:")) {
    const ed = ed25519FromMultibase(did.slice("did:key:".length));
    if (ed) {
      const x = x25519FromEd25519Public(ed);
      return found("derived", x25519ToMultibase(x), x);
    }
  }
  return { verdict: "accept", source: "none" };
}

/** Kind `key-agreement`: checks `delegation` and `recipient-key`. Contract: README "Kind: `key-agreement`". */
export function runKeyAgreement(ctx: JsonObject, input: JsonObject, schemas: SchemaSet): Verdict {
  const rctx = ctx as unknown as ReceiverContext;
  switch (input["check"]) {
    case "delegation": {
      const subject = typeof input["subject"] === "string" ? input["subject"] : undefined;
      const d = verifyKeyAgreement(input["delegation"], rctx, schemas, subject);
      if (!isDelegation(d)) return d;
      return { verdict: "accept", subject: d.subject, key: d.key, x25519_pk_hex: d.x25519.toString("hex"), expires_at: d.expires_at };
    }
    case "recipient-key": {
      const doc = input["document_key_agreement"];
      return recipientKey(
        input["did"] as string,
        (input["delegations"] ?? []) as Json[],
        typeof doc === "string" ? doc : undefined,
        rctx,
        schemas,
      ) as Verdict;
    }
    default:
      throw new Error(`unknown key-agreement check ${String(input["check"])}`);
  }
}
