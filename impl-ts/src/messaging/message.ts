/**
 * Profile messages: the refusals a mailbox or hub applies to a decoded profile payload.
 *
 * Spec: M§5.1 (refusal order, 60 s / 10 s lifetimes, MAX_MLS_BYTES), M§5.2 (deposit classes and
 * their fields), M§5.5 (key-packages), M§5.7 / M§4.4 (mailbox modes), §19.4 (a carried
 * introduction keeps its 4,096-byte cap).
 */
import type { JsonObject } from "../did.js";
import { reject, type Verdict } from "../verdict.js";
import { messagingSchemas } from "./schemas.js";
import { introductionCapCompact } from "../profile-card.js";

/** Spec: M§5.1 */
export const MAX_MLS_BYTES = 24576;
const MAX_LIFETIME_S = 60;
const MAX_EPHEMERAL_LIFETIME_S = 10;
/** Spec: §19.4 */

/** Profile message types (the other schemas in the set are content objects and documents). */
const MESSAGE_TYPES = ["deposit", "accepted", "sync", "items", "key-packages", "key-package-fetch", "blob-put", "mailbox-config"];

/** Spec: M§4.4 — registry `dsip-mailbox-mode`. */
const MODES = ["sync", "queue"];

/**
 * Spec: M§5.2 class table — what each deposit class MUST carry and what else it MAY carry.
 * Any other class-specific field is a `deposit-fields` refusal. `recipient` is addressing, not
 * class: it is allowed on every deposit to a mailbox. `blobs` is the manifest of what *content*
 * references (M§8.4), so only `application`; a ratchet tree too large to inline is named by
 * `ratchet_tree_blob` wherever a tree travels (M§6.4): commits, welcomes, GroupInfo.
 */
const CLASS_FIELDS: Record<string, { required: string[]; optional: string[] }> = {
  handshake: { required: ["group", "mls"], optional: ["welcome", "group_info", "ratchet_tree_blob", "grants", "seq"] },
  application: { required: ["group", "mls"], optional: ["seq", "blobs"] },
  // `seq`: the adding commit's, so the new member knows where it starts counting (spec-gap 83)
  welcome: { required: ["group", "mls", "hub"], optional: ["ratchet_tree_blob", "grants", "origin", "successor_of", "seq"] },
  "group-info": { required: ["group", "mls"], optional: ["ratchet_tree_blob", "handover_seq"] },
  ephemeral: { required: ["group", "sealed"], optional: [] },
  archive: { required: ["group", "archive", "akid", "ref_group", "ref_seq"], optional: [] },
  introduction: { required: ["recipient", "envelope"], optional: [] },
  grant: { required: ["recipient", "envelope"], optional: [] },
};

/** Fields every deposit may have, whatever its class. */
const COMMON = ["dsip", "type", "id", "from", "to", "class", "recipient", "issued_at", "expires_at"];

/** Spec: M§5.1 — decoded length from the base64url text, ⌊length × 3 / 4⌋, so decoders cannot disagree. */
export function decodedLength(b64url: string): number {
  return Math.floor((b64url.length * 3) / 4);
}

/** Check one profile message. Order is M§5.1's: schema, lifetime, class, class fields, size. */
export function checkMessage(payload: JsonObject): Verdict {
  const type = payload["type"];
  if (typeof type !== "string" || !MESSAGE_TYPES.includes(type)) return reject("unknown-type");
  if (!messagingSchemas.valid(type, payload)) return reject("schema-invalid");

  const ephemeral = type === "deposit" && payload["class"] === "ephemeral";
  const lifetime = (payload["expires_at"] as number) - (payload["issued_at"] as number);
  if (lifetime > (ephemeral ? MAX_EPHEMERAL_LIFETIME_S : MAX_LIFETIME_S)) return reject("lifetime-exceeded");

  if (type === "deposit") {
    const fields = CLASS_FIELDS[payload["class"] as string];
    // M§5.2: class is structural, not presentational — an unknown one is refused, never ignored
    if (!fields) return reject("deposit-class-unsupported", "mailbox.unsupported-class");
    const allowed = [...COMMON, ...fields.required, ...fields.optional];
    if (fields.required.some((f) => !(f in payload)) || Object.keys(payload).some((k) => !allowed.includes(k))) {
      return reject("deposit-fields");
    }
    for (const f of ["mls", "welcome", "group_info", "sealed", "archive"]) {
      const value = payload[f];
      if (typeof value === "string" && decodedLength(value) > MAX_MLS_BYTES) return reject("object-too-large", "mailbox.object-too-large");
    }
    if (typeof payload["envelope"] === "string" && payload["class"] === "introduction") {
      // §19.4: 4,096 bytes, or 16,384 for one that carries `sealed` and lists profile-card/1.0
      if (Buffer.byteLength(payload["envelope"], "utf8") > introductionCapCompact(payload["envelope"])) {
        return reject("introduction-too-large", "transport.envelope-too-large");
      }
    }
  }
  if (type === "mailbox-config" && "mode" in payload && !MODES.includes(payload["mode"] as string)) {
    return reject("mailbox-mode-unsupported", "mailbox.unsupported-mode");
  }
  if (type === "key-packages" && (payload["key_packages"] as unknown[]).length === 0) return reject("key-packages-empty");
  return { verdict: "accept" };
}

/** Spec: M§6.3 — conversation kinds; an unknown kind is handled as `group`. */
const KINDS = ["direct", "group", "personal"];

/** Check a `dsip_conversation` GroupContext extension value. Spec: M§6.3 */
export function checkConversationExt(extension: JsonObject): Verdict {
  if (!messagingSchemas.valid("dsip-conversation", extension)) return reject("schema-invalid");
  const kind = extension["kind"] as string;
  return { verdict: "accept", effective: { kind: KINDS.includes(kind) ? kind : "group" } };
}

/**
 * What a GroupContextExtensions commit may change. Spec: M§7.4 (spec-gap 60) — only the hub; the
 * conversation id, its kind and `successor_of` are fixed for the group's life (M§6.3, M§7.5).
 */
export function checkConversationUpdate(before: JsonObject, after: JsonObject): Verdict {
  if (!messagingSchemas.valid("dsip-conversation", after)) return reject("schema-invalid");
  for (const fixed of ["conversation", "kind", "successor_of"]) {
    if (JSON.stringify(before[fixed] ?? null) !== JSON.stringify(after[fixed] ?? null)) return reject("conversation-immutable");
  }
  const [was, now] = [before["hub"] as JsonObject | undefined, after["hub"] as JsonObject];
  return { verdict: "accept", effective: { moves_to: was?.["did"] !== now["did"] ? now["did"]! : null, hub: now } };
}
