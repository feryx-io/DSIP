/**
 * What a device keeps across syncs and restarts: its ack cursor and per-group `seq` positions,
 * its history (archive records and MLS copies as one timeline), and its view of successor groups.
 *
 * Spec: M§5.4 / M§8.5 (durable processing, spec-gap 44; own items, spec-gap 47; re-joining,
 * spec-gap 69), M§12.1–M§12.3 (archive keys, archiving, a new device's first sync — spec-gaps 51,
 * 63, 64, 68), M§7.5 (successor groups, spec-gap 61).
 */
import type { Json, JsonObject } from "../did.js";
import type { Machine, Step } from "./device.js";
import { successorCheck, successorSelect } from "./rules.js";

// ---- M§5.4 / M§8.5 resume

interface Position {
  contiguous: number;
  seen: number[];
}

/** The device's durable delivery state. Spec: M§5.4 (spec-gap 44) */
export class Resume implements Machine {
  private cursor: string | null;
  private readonly groups: Record<string, Position>;
  private joined: string[];
  /** The device's own `limit`, when the trace states one; not durable, so a restart returns to it. */
  private readonly baseLimit: number | undefined;
  /** The `limit` it syncs with now: halved for each envelope over the cap. Spec: M§5.4 (spec-gap 180) */
  private limit: number | undefined;

  constructor(ctx: { cursor: string | null; groups: Record<string, Position>; joined: string[]; limit?: number }) {
    this.cursor = ctx.cursor;
    this.groups = structuredClone(ctx.groups);
    this.joined = [...ctx.joined];
    this.baseLimit = ctx.limit;
    this.limit = ctx.limit;
  }

  step(e: JsonObject): Step {
    const emit: Json[] = [];
    if ("items" in e) {
      const { items, crash_at } = e["items"] as { items: JsonObject[]; crash_at?: string };
      for (const item of items) {
        const cursor = item["cursor"] as string;
        if (cursor === crash_at) {
          // MLS state and delivery state commit together: a crash rolls both back, the item is redelivered
          emit.push({ crash: cursor });
          break;
        }
        emit.push(this.process(item, cursor));
        this.cursor = cursor; // a duplicate advances the ack position like any other
      }
    } else if ("sent" in e) {
      // M§6.5 (spec-gap 47): the seq of our own `accepted` is processed; the fanned-back copy is a duplicate
      const { group, seq } = e["sent"] as { group: string; seq: number };
      this.mark(group, seq);
    } else if ("rejoined" in e) {
      // spec-gap 69: every seq up to the highest seen is passed
      const { group, seq } = e["rejoined"] as { group: string; seq: number };
      const p = (this.groups[group] ??= { contiguous: 0, seen: [] });
      p.contiguous = Math.max(p.contiguous, seq, ...p.seen);
      p.seen = [];
      if (!this.joined.includes(group)) this.joined = [...this.joined, group].sort(); // an external commit is a join
    } else if ("removed" in e) {
      // spec-gap 127: a commit removed this identity; a welcome adding it back is a join, the seq positions stay
      const { group } = e["removed"] as { group: string };
      this.joined = this.joined.filter((g) => g !== group);
    } else {
      if ("cursor_invalid" in e) this.cursor = null; // mailbox.cursor-invalid: re-sync from null
      if ("restart" in e) this.limit = this.baseLimit; // only durable state survives a restart
      if ("too_large" in e) {
        // M§5.4 (spec-gap 180): the same sync would get the same oversized envelope. Halve the limit, at least 1; at 1
        // the mailbox is at fault (MAX_MLS_BYTES), and the same sync waits out the §13.2 reconnection backoff.
        if (this.limit === 1) emit.push({ backoff: {} });
        else this.limit = Math.max(1, Math.floor(this.limit! / 2));
      }
      const sync: JsonObject = this.cursor === null ? { since: null } : { since: this.cursor, ack_through: this.cursor };
      if (this.limit !== undefined) sync["limit"] = this.limit;
      emit.push({ sync });
    }
    return { emit, state: { cursor: this.cursor, groups: structuredClone(this.groups) as unknown as JsonObject, joined: [...this.joined] } };
  }

  private mark(group: string, seq: number): boolean {
    const p = this.groups[group];
    if (!p) {
      // a device counts gaps from where it starts, not from seq 1
      this.groups[group] = { contiguous: seq, seen: [] };
      return true;
    }
    if (seq <= p.contiguous || p.seen.includes(seq)) return false;
    p.seen.push(seq);
    p.seen.sort((a, b) => a - b);
    while (p.seen[0] === p.contiguous + 1) p.contiguous = p.seen.shift()!;
    return true;
  }

  private process(item: JsonObject, cursor: string): Json {
    const group = item["group"] as string;
    if (item["class"] === "welcome") {
      if (this.joined.includes(group)) return { duplicate: cursor }; // its KeyPackage is consumed
      if (item["sibling"] === true) return { sibling: cursor }; // acknowledged, not a join (M§12.3 step 5)
      this.joined = [...this.joined, group].sort();
      // spec-gap 83: the welcome carries the seq of the commit that added this device — its exact position. What is
      // at or below it is pre-join history; without it the first item processed is taken as the position (`mark`).
      if (typeof item["seq"] === "number") this.groups[group] = { contiguous: item["seq"], seen: [] };
      return { process: cursor };
    }
    // MLS cannot decrypt twice, so a redelivered sequenced item is recognised by its seq alone;
    // unsequenced state (group-info) is simply processed again
    if (typeof item["seq"] !== "number") return { process: cursor };
    return this.mark(group, item["seq"]) ? { process: cursor } : { duplicate: cursor };
  }
}

// ---- M§12 history

interface HeldRecord {
  cursor: string;
  akid: string;
  record: JsonObject;
}

/** Whether a history step's `object` is a timeline entry: content, or no object named. Spec: M§12.2, M§13.3 */
function isTimeline(object: Json | undefined): boolean {
  return object === undefined || object === "content";
}

/** One timeline out of MLS items, the device's own sent items, and archive records. Spec: M§12.2, M§12.3 */
export class History implements Machine {
  private readonly keys = new Map<string, number>();
  private readonly joined: Record<string, number>;
  private readonly timeline: { id: string; seq: number }[] = [];
  private readonly known = new Set<string>();
  private held: HeldRecord[] = [];

  constructor(ctx: { keys: { akid: string; created_at: number }[]; joined: Record<string, number> }) {
    for (const k of ctx.keys) this.keys.set(k.akid, k.created_at);
    this.joined = { ...ctx.joined };
  }

  /** Spec: M§12.1 (spec-gap 51) — the greatest `created_at`, ties broken by `akid`. */
  private get current(): string | null {
    const sorted = [...this.keys].sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1));
    return sorted.at(-1)?.[0] ?? null;
  }

  step(e: JsonObject): Step {
    const emit: Json[] = [];
    if ("archive" in e) {
      const record = e["archive"] as JsonObject;
      const [cursor, akid] = [record["cursor"] as string, record["akid"] as string];
      // kept durably, still encrypted, until its key arrives
      if (!this.keys.has(akid)) {
        this.held.push({ cursor, akid, record });
        emit.push({ hold: cursor });
      } else emit.push(this.restore(record));
    } else if ("archive_key" in e) {
      const { akid, created_at } = e["archive_key"] as { akid: string; created_at: number };
      this.keys.set(akid, created_at);
      const released = this.held.filter((h) => h.akid === akid);
      this.held = this.held.filter((h) => h.akid !== akid);
      for (const h of released) emit.push(this.restore(h.record));
    } else if ("joined" in e) {
      const { group, epoch } = e["joined"] as { group: string; epoch: number };
      this.joined[group] = epoch;
    } else {
      const own = "sent" in e;
      const item = (e["mls"] ?? e["sent"]) as JsonObject;
      const [group, seq, id] = [item["group"] as string, item["seq"] as number, item["id"] as string];
      const joinEpoch = this.joined[group];
      if (!own && joinEpoch !== undefined && (item["epoch"] as number) < joinEpoch) {
        emit.push({ prejoin: seq }); // epochs before the join cannot be decrypted: skipped, no error
      } else if (this.known.has(id)) {
        emit.push({ duplicate: id });
      } else {
        this.known.add(id);
        // a receipt or call event is state, not a timeline entry; content (or no object named) is
        if (isTimeline(item["object"])) {
          this.show(id, seq);
          emit.push({ show: id });
        }
        if (this.current !== null) emit.push({ archive: { group, seq, akid: this.current } });
      }
    }
    return {
      emit,
      state: { timeline: this.timeline.map((t) => t.id), held: this.held.map((h) => h.cursor), current_akid: this.current },
    };
  }

  private show(id: string, seq: number): void {
    this.timeline.push({ id, seq });
    this.timeline.sort((a, b) => a.seq - b.seq); // display order is hub seq order
  }

  /** Spec: M§12.2 (spec-gap 64) — restored records are history: no receipts sent, nothing archived again. */
  private restore(record: JsonObject): Json {
    const id = record["id"] as string;
    if (this.known.has(id)) return { duplicate: id };
    this.known.add(id);
    if (!isTimeline(record["object"])) return { apply: record["cursor"]! };
    this.show(id, record["seq"] as number);
    return { show: id };
  }
}

// ---- M§7.5 successors

/** A device's view of the successors of groups it was in. Spec: M§7.5 (spec-gap 61) */
export class SuccessorTracker implements Machine {
  private readonly groups: Record<string, string[]>;
  private readonly candidates: Record<string, string[]> = {};
  private readonly chosen: Record<string, string> = {};

  constructor(ctx: { groups: Record<string, string[]> }) {
    this.groups = ctx.groups;
  }

  step(e: JsonObject): Step {
    const emit: Json[] = [];
    if ("welcome" in e) {
      const w = e["welcome"] as { group: string; successor_of: string; creator: string; roster: string[] };
      const last = this.groups[w.successor_of];
      // never a member of the predecessor, or the check fails: a new conversation under first contact
      if (!last || successorCheck(last, w.creator, w.roster).verdict === "reject") emit.push({ first_contact: w.group });
      else this.candidate(w.successor_of, w.group, emit, true);
    } else if ("create" in e) {
      const predecessor = (e["create"] as JsonObject)["predecessor"] as string;
      const roster = this.groups[predecessor];
      if (!roster) emit.push({ refuse: "not-a-member" });
      else if (this.chosen[predecessor]) emit.push({ use: this.chosen[predecessor]! }); // already converged: no second one
      else emit.push({ create: { successor_of: predecessor, roster: [...roster].sort() } });
    } else {
      const c = e["created"] as { group: string; successor_of: string };
      this.candidate(c.successor_of, c.group, emit, false);
    }
    const state: JsonObject = {};
    for (const [p, list] of Object.entries(this.candidates)) state[p] = { successor: this.chosen[p]!, candidates: [...list] };
    return { emit, state };
  }

  /** Stay in only the lowest group id (compared as the decoded ULID); leave one joined or created when a lower appears. */
  private candidate(predecessor: string, group: string, emit: Json[], welcomed: boolean): void {
    const list = (this.candidates[predecessor] ??= []);
    if (!list.includes(group)) list.push(group);
    list.sort();
    const winner = successorSelect(list)["winner"] as string | null;
    if (winner === group) {
      if (welcomed) emit.push({ join: group });
      // what we were in until now — joined or created — is left for the lower one
      for (const other of this.member) if (other !== group && list.includes(other)) emit.push({ leave: other });
      for (const other of list) this.member.delete(other);
      this.member.add(group);
    } else emit.push(welcomed ? { decline: group } : { leave: group }); // not the lowest: never joined — or, if we created it, left
    if (winner !== null) this.chosen[predecessor] = winner;
  }

  /** Successor groups this device is in: welcomed and joined, or created. */
  private readonly member = new Set<string>();
}
