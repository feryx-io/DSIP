/**
 * Reachability hints: signed, expiring records that are hints, never authority.
 *
 * Spec: §8.3 (conflict rules), §8.5 (DHT status), §8.1 (hints sit last in the authority order),
 * DHT Hints Profile §4 (receiving a hint).
 */
import type { Json, JsonObject } from "./did.js";
import { b64urlDecode } from "./encoding.js";
import { verifyEnvelope, type Envelope, type ReceiverContext } from "./envelope.js";
import { verifyKeyAgreement } from "./key-agreement.js";
import type { SchemaSet } from "./schema.js";
import { reject, type Verdict } from "./verdict.js";

function payloadOf(envelope: Json): JsonObject {
  return JSON.parse(b64urlDecode((envelope as unknown as Envelope).payload)!.toString("utf8"));
}

/**
 * Verify a hint and decide whether it replaces `existing`, a record accepted earlier for the subject.
 *
 * Spec: §8.3 — the record is verified against the DID before use; its verified identity MUST be
 * its `subject`; higher `seq` wins; a record past expiration is invalid and carries no authority;
 * two live records with the same `seq` and different content are a warning and the existing one is kept.
 * DHT Hints Profile §4 step 2: a `key_agreement` member that does not verify refuses the hint.
 */
export function verifyHint(envelope: Json, ctx: ReceiverContext, schemas: SchemaSet, existing?: Json): Verdict {
  const verdict = verifyEnvelope(envelope, ctx, schemas);
  if (verdict.verdict === "reject") return verdict;
  const hint = payloadOf(envelope);
  if (hint["type"] !== "reachability-hint" || hint["subject"] !== verdict["identity"]) {
    return reject("hint-subject-mismatch");
  }
  // DHT Hints Profile §4 step 2, core §7.3 (spec-gap 179): a `key_agreement` member must verify as a
  // key agreement delegation of the hint's subject, or the whole hint is refused.
  // Checked last, after `hint-subject-mismatch` (profile §4 step 1 precedes step 2; vectors README, kind `dht`).
  if ("key_agreement" in hint && "verdict" in verifyKeyAgreement(hint["key_agreement"], ctx, schemas, hint["subject"] as string)) {
    return reject("key-agreement-invalid");
  }
  let winner = "input";
  let conflict = "none";
  // Impl: the existing record was verified when it was accepted; only its liveness is re-checked.
  // §8.3, §12.9 (spec-gap 141): the existing record is live while now < expires_at.
  const held = existing === undefined ? null : payloadOf(existing);
  if (held && ctx.now < (held["expires_at"] as number)) {
    const [a, b] = [hint["seq"] as number, held["seq"] as number];
    if (a > b) conflict = "newer-seq";
    else if (a < b) [winner, conflict] = ["existing", "older-seq"];
    else {
      const same = (envelope as unknown as Envelope).payload === (existing as unknown as Envelope).payload;
      [winner, conflict] = ["existing", same ? "none" : "same-seq-live"];
    }
  }
  return { ...verdict, winner, conflict };
}
