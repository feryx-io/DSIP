/**
 * A mailbox's `items` pages: each one fits the `ws/1.0` cap as it goes on the wire, encoded and signed.
 *
 * Spec: M§5.4 ("A mailbox MUST paginate so every `items` envelope fits the transport cap"; spec-gap 180), §13.2
 * (65,536 bytes), M§5.1 (`MAX_MLS_BYTES` makes any one item fit).
 */
import { createHash, createPrivateKey, createPublicKey, sign, type KeyObject } from "node:crypto";
import type { Json, JsonObject } from "../did.js";
import { base58Encode } from "../encoding.js";
import { MAX_FRAME_BYTES } from "../envelope.js";

/** A fixture key from its name: Ed25519, seeded with `sha256("dsip-vector:" + name)` (vectors README, Fixed fixtures). Spec: none (infrastructure) */
function fixtureKey(name: string): { key: KeyObject; did: string } {
  const seed = createHash("sha256").update("dsip-vector:" + name).digest();
  const key = createPrivateKey({ key: Buffer.concat([Buffer.from("302e020100300506032b657004220420", "hex"), seed]), format: "der", type: "pkcs8" });
  const pub = createPublicKey(key).export({ format: "der", type: "spki" }).subarray(-32);
  return { key, did: "did:key:z" + base58Encode(Buffer.concat([Buffer.from([0xed, 0x01]), pub])) };
}

const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

/** A ULID for `ms` whose random part is `n`. Spec: none (infrastructure) */
function ulid(ms: number, n: number): string {
  let time = "";
  for (let t = ms, i = 0; i < 10; i++, t = Math.floor(t / 32)) time = CROCKFORD[t % 32] + time;
  let rand = "";
  for (let r = n, i = 0; i < 16; i++, r = Math.floor(r / 32)) rand = CROCKFORD[r % 32] + rand;
  return time + rand;
}

interface PagesInput {
  limit?: number;
  items: (JsonObject & { cursor: string; mls_bytes: number })[];
}

/**
 * Answers a `sync` from `null` with signed `items` envelopes, and follows each `next`, as the device would, until it is
 * `null`. Reports the cursors delivered, whether every frame fits the cap and every page the limit, and whether `next`
 * chains (each page's last cursor; `null` only on the last, with nothing left).
 *
 * Spec: M§5.4, §13.2 (spec-gap 180).
 * Impl: a page is the longest prefix of what is left, at most `limit`, whose frame fits; one item always goes.
 */
export function itemsPages(ctx: JsonObject, input: PagesInput): JsonObject {
  const { key, did } = fixtureKey(ctx["mailbox_key"] as string);
  const kid = `${did}#${did.slice("did:key:".length)}`;
  const now = ctx["now"] as number;
  const limit = input.limit ?? 200;
  const stored: JsonObject[] = input.items.map(({ mls_bytes, ...rest }) => ({ ...rest, mls: Buffer.alloc(mls_bytes).toString("base64url") }));
  const syncId = ulid(now * 1000, 0);
  let n = 0;
  const frame = (page: JsonObject[], next: Json): string => {
    const payload = {
      dsip: { core: "1.0", min_core: "1.0", profiles: ["messaging/1.0"], extensions: [], critical: [] },
      type: "items", id: ulid(now * 1000, n), from: did, to: ctx["device"], in_reply_to: syncId,
      items: page, next, issued_at: now, expires_at: now + 30,
    };
    const prot = Buffer.from(JSON.stringify({ alg: "EdDSA", kid, typ: "dsip+json" })).toString("base64url");
    const pay = Buffer.from(JSON.stringify(payload)).toString("base64url");
    const sig = sign(null, Buffer.from(`${prot}.${pay}`), key).toString("base64url");
    return JSON.stringify({ protected: prot, payload: pay, signature: sig });
  };
  const fits = (f: string): boolean => Buffer.byteLength(f, "utf8") <= MAX_FRAME_BYTES;

  const cursors: string[] = [];
  let fit = true, withinLimit = true, chain = true;
  let rest = stored;
  for (;;) {
    let k = Math.min(limit, rest.length);
    while (k > 1 && !fits(frame(rest.slice(0, k), rest[k - 1]!["cursor"]!))) k--;
    const page = rest.slice(0, k);
    const next = rest.length > k ? page[k - 1]!["cursor"]! : null;
    fit &&= fits(frame(page, next));
    n++;
    withinLimit &&= page.length <= limit;
    cursors.push(...page.map((it) => it["cursor"] as string));
    rest = rest.slice(k);
    if (next === null) {
      chain &&= rest.length === 0;
      break;
    }
    chain &&= page.length > 0 && next === page[page.length - 1]!["cursor"];
  }
  return { cursors, fit, within_limit: withinLimit, next_chain: chain };
}
