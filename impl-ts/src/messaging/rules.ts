/**
 * Client-side rules of the Messaging Profile that need no state: when voicemail may be offered,
 * what goes into call history, which mailbox to use, which of two concurrent conversations wins,
 * and what a successor group or an external commit may do.
 *
 * Spec: M§4.2 (mailbox discovery; §8.1 authority order), M§15.4 (mailbox redirection), M§6.8
 * (external joins, spec-gap 62), M§7.2 (direct-conversation convergence), M§7.5 (successor groups),
 * M§13.2 (voicemail offer), M§13.3 (call history, spec-gap 63), M§5.7 (registration on removal, spec-gap 53).
 */
import type { JsonObject } from "../did.js";
import { b64urlDecode, ulidSeconds, utf8Decode } from "../encoding.js";
import { isRegisteredReason } from "../registry.js";
import { reject, type Verdict } from "../verdict.js";
import { messagingSchemas } from "./schemas.js";

// ---- M§13.2 voicemail

/** Spec: M§13.2 rule 3 — attempt outcomes after which a caller MAY offer voicemail. */
const VOICEMAIL_REJECTS = ["user.no-answer", "user.declined", "endpoint.busy", "endpoint.unavailable"];

/** Spec: M§13.2 — and the voicemail's kind: video only after an attempt that offered video, to a callee that accepts it
 * (spec-gap 184). */
export function voicemailOffer(
  voicemail: JsonObject | null,
  canSend: boolean,
  outcome: { type: string; reason: string },
  callVideo = false,
  accepts: readonly string[] = [],
): JsonObject {
  const { type, reason } = outcome;
  const listed = type === "reject" ? VOICEMAIL_REJECTS.includes(reason) : type === "cancel" && reason === "session.timeout";
  // §15.1 fallback: an unregistered endpoint.* condition is endpoint state, like busy; any other category may be block-like
  const byCategory = type === "reject" && !isRegisteredReason(reason) && reason.startsWith("endpoint.");
  if (voicemail === null || !canSend || !(listed || byCategory)) return { offer: false };
  const kind = callVideo && accepts.includes("video") ? "video" : "audio";
  return { offer: true, kind, ...("max_duration_s" in voicemail ? { max_duration_s: voicemail["max_duration_s"]! } : {}) };
}

// ---- M§13.3 call history

/** Spec: M§13.3 (spec-gap 63) — whether this device records the leg, and as what. */
export function callEvent(leg: { alerted: boolean; answered_here: boolean; ended_by: string; reason: string }): JsonObject {
  if (!leg.alerted || leg.answered_here || leg.reason === "session.answered-elsewhere") return { send: false };
  // `declined` only when this device ended the leg on its user's decision
  return { send: true, outcome: leg.ended_by === "local" && leg.reason === "user.declined" ? "declined" : "missed" };
}

/** Spec: M§13.3 — content keeps `seq` order; a call goes before the first content item later than it. */
export function peerTimeline(content: { id: string; at: number }[], calls: { session: string; at: number }[]): JsonObject {
  const seen = new Set<string>();
  const collapsed: string[] = [];
  const unique = calls.filter((c) => {
    // one call, one entry: collapse by session, keeping the first by seq
    if (!seen.has(c.session)) return seen.add(c.session), true;
    if (!collapsed.includes(c.session)) collapsed.push(c.session);
    return false;
  });
  const timeline: string[] = [];
  let next = 0;
  for (const item of content) {
    while (next < unique.length && unique[next]!.at < item.at) timeline.push(`call:${unique[next++]!.session}`);
    timeline.push(`content:${item.id}`);
  }
  while (next < unique.length) timeline.push(`call:${unique[next++]!.session}`);
  return { timeline, collapsed };
}

// ---- M§4.2 mailbox discovery

function usable(entry: JsonObject): boolean {
  const { service: _service, ...shape } = entry; // a hint entry names its service; the shape is otherwise the same
  return messagingSchemas.valid("mailbox-service", shape) && (entry["profiles"] as string[]).includes("messaging/1.0");
}

/**
 * Spec: M§4.2 — the DID document is authoritative; hints are consulted only when the document
 * lists no entry at all, never when it lists entries and none is usable (§8.1, M§15.4).
 */
export function mailboxSelect(documentEntries: JsonObject[], hintEntries: JsonObject[], reachable?: string[]): JsonObject {
  const fromDocument = documentEntries.length > 0;
  const entries = fromDocument ? documentEntries : hintEntries;
  if (entries.length === 0) return { source: null, selected: null, order: [], sync_targets: [], discarded: [] };
  const discarded = entries.filter((e) => !usable(e)).map((e) => e["uri"] as string);
  // lower priority first; absent is 0; equal priorities keep document order (sort is stable)
  const order = entries
    .filter(usable)
    .sort((a, b) => ((a["priority"] as number | undefined) ?? 0) - ((b["priority"] as number | undefined) ?? 0))
    .map((e) => e["mailbox"] as string);
  const selected = order.find((m) => reachable === undefined || reachable.includes(m)) ?? null;
  // the owner's devices sync every listed mailbox
  return { source: fromDocument ? "did-document" : "hint", selected, order, sync_targets: order, discarded };
}

/** Spec: M§4.2, M§15.4 — a hint never moves the mailbox of an established conversation. */
export function mailboxSwitch(established: { mailbox: string }, candidate: { mailbox: string; source: string }): JsonObject {
  if (candidate.mailbox === established.mailbox) return { switch: false, reason: "unchanged" };
  if (candidate.source === "hint") return { switch: false, reason: "hint-sourced" };
  return { switch: true, reason: "did-document" };
}

// ---- M§7.2, M§7.5 convergence

/** Spec: M§7.2 — concurrent direct conversations converge on the lowest ULID that passes the §20.6 guard. */
export function directSelect(candidates: { conversation: string; issued_at: number }[]): JsonObject {
  const ok = (c: { conversation: string; issued_at: number }): boolean => {
    const at = ulidSeconds(c.conversation);
    return at !== null && Math.abs(at - c.issued_at) <= 300;
  };
  const valid = candidates.filter(ok).map((c) => c.conversation).sort();
  return { winner: valid[0] ?? null, discarded: candidates.filter((c) => !ok(c)).map((c) => c.conversation) };
}

/** A group id is the base64url of a ULID's text. */
function groupUlid(groupId: string): string | null {
  const bytes = b64urlDecode(groupId);
  const text = bytes ? utf8Decode(bytes) : null;
  return text !== null && ulidSeconds(text) !== null ? text : null;
}

/** Spec: M§7.5 — concurrent successors converge on the lowest group id, compared as the decoded ULID. */
export function successorSelect(candidates: string[]): JsonObject {
  const valid = candidates.filter((g) => groupUlid(g) !== null).sort((a, b) => (groupUlid(a)! < groupUlid(b)! ? -1 : 1));
  return { winner: valid[0] ?? null, discarded: candidates.filter((g) => groupUlid(g) === null) };
}

/** Spec: M§7.5 — created by a predecessor member, adding no one from outside; it may omit members. */
export function successorCheck(predecessorRoster: string[], creator: string, roster: string[]): Verdict {
  const ok = predecessorRoster.includes(creator) && roster.every((identity) => predecessorRoster.includes(identity));
  return ok ? { verdict: "accept" } : reject("successor-invalid");
}

// ---- M§6.8 external joins

interface Leaf {
  identity: string;
  device: string;
}

/** Spec: M§6.8 (spec-gap 62) — an external commit adds exactly the joiner's device and may remove only its own identity's leaves. */
export function externalJoin(i: { kind: string; owner?: string; roster: string[]; joiner: Leaf; adds: Leaf[]; removes: Leaf[] }): Verdict {
  const { joiner } = i;
  const addsOnlySelf = i.adds.length === 1 && i.adds[0]!.identity === joiner.identity && i.adds[0]!.device === joiner.device;
  if (!addsOnlySelf) return reject("external-join-adds");
  // a personal group belongs to its owner, even with no surviving leaf; any other group needs a member identity
  const member = i.kind === "personal" ? joiner.identity === i.owner : i.roster.includes(joiner.identity);
  if (!member) return reject("external-join-not-member");
  if (i.removes.some((leaf) => leaf.identity !== joiner.identity)) return reject("external-join-removes-other");
  return { verdict: "accept" };
}

/** Spec: M§5.7 (spec-gap 53) — a registration belongs to the identity: `left` only when no leaf of it remains. */
export function registrationOnRemoval(me: string, remainingIdentities: string[]): JsonObject {
  return { left: !remainingIdentities.includes(me) };
}

/** What a member's device does with an identity's pending Remove proposals.
 * Spec: M§7.3 "Leaving" (v0.14, spec-gap 125) — a leaver proposes every leaf of its identity; another member commits. */
export function leaveProposals(i: { me: string; proposer: Leaf; removes: Leaf[]; others: number; roster: Leaf[] }): Record<string, string> {
  if (i.others > 0) return { action: "ignore", reason: "not-a-leave" };
  const who = i.proposer.identity;
  const leaves = new Set(i.roster.filter((r) => r.identity === who).map((r) => r.device));
  const removed = new Set<string>();
  for (const r of i.removes) {
    if (r.identity !== who || !leaves.has(r.device)) return { action: "ignore", reason: "not-own-leaves" };
    removed.add(r.device);
  }
  if (removed.size !== leaves.size) return { action: "wait" };
  if (who === i.me) return { action: "left" };
  return { action: "commit" };
}

/** The roster rules a member checks on every commit before merging it; the hub checks them too.
 * Spec: M§7.3 — another identity's devices are its own to add; its leaves are removed all together, or each because
 * its delegation no longer verifies (M§6.2). Members enforce this themselves (spec-gap 126). */
export function rosterChange(i: { committer: string; roster: Leaf[]; adds: Leaf[]; removes: (Leaf & { delegation_valid?: boolean })[] }): JsonObject {
  const members = new Set(i.roster.map((r) => r.identity));
  if (i.adds.some((a) => a.identity !== i.committer && members.has(a.identity))) return reject("roster-adds-other-devices");
  const others = new Set(i.removes.map((r) => r.identity).filter((w) => w !== i.committer));
  for (const who of others) {
    const rs = i.removes.filter((r) => r.identity === who);
    const removed = new Set(rs.map((r) => r.device));
    const whole = i.roster.filter((r) => r.identity === who).every((r) => removed.has(r.device));
    const lapsed = rs.every((r) => r.delegation_valid === false);
    if (!whole && !lapsed) return reject("roster-removes-part-of-identity");
  }
  return { verdict: "accept" };
}
