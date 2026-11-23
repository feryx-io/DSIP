/**
 * The endpoint session engine: per-session initiator and responder state machines, timers,
 * races, glare, renegotiation and first contact.
 *
 * Spec: §12.4 (state machine), §12.5 (cancel/answer race), §12.6 (glare), §12.7 (forking, as the
 * initiator sees it), §12.8 (renegotiation), §12.9 (timers), §12.10 (progress), §12.12 (info),
 * §19.4 (first contact), P§12.3–P§12.5 (presence keys in the grants issued and held, rotation, re-granting).
 *
 * Every message reaching this engine has already passed signature, replay and shape checks
 * (`envelope.ts`); the engine never verifies anything.
 * Impl: ENDING is collapsed into ENDED — local teardown is synchronous here (§12.4 allows it).
 */
import type { Json, JsonObject } from "./did.js";
import { effectiveAnsweredBy, effectiveReason, effectiveStatus } from "./registry.js";
import { Timers } from "./timers.js";

/** Spec: §12.9 timer defaults and bounds, seconds. */
const T_ESTABLISH = 15;
const T_RING = 120;
const T_RING_BOUNDS: [number, number] = [30, 300];
/** Spec: §12.10 — T-Queue hard cap and the RECOMMENDED consecutive re-queue limit. */
const T_QUEUE_CAP = 1800;
const MAX_REQUEUES = 3;
/** Spec: §12.12 — `about` values this endpoint hands to a binding. */
const KNOWN_ABOUT = ["transport:webrtc", "media:dtmf"];

type State = "INVITING" | "PROCEEDING" | "OFFERED" | "ALERTING" | "ACTIVE" | "ENDED";

interface Session {
  role: "initiator" | "responder";
  state: State;
  /** Initiator: the invite's `to`. Responder: the inviting device. */
  to: string;
  /** The device on the other side once known (answering leg, or the inviter). */
  peer?: string;
  /** Responder: the invite's `expires_at`. */
  inviteExpires?: number;
  outstanding: { id: string; direction: "outbound" | "inbound" } | null;
  /** The outstanding update's `expires_at`: unanswered then, it lapses (§12.8 rule 7). */
  updateExpires?: number;
  media: boolean;
  /** Consecutive `queued` progresses (§12.10). */
  requeues: number;
  /** Initiator: why the attempt ended, which decides the `bye` a late answer gets (§12.4, §12.5). */
  endedBy?: "cancel" | "other";
  /** Initiator: an answer was applied (the session reached ACTIVE), so any later one is `session.already-answered` (§12.7 rule 4). */
  answered?: boolean;
  /** Responder: a message from the initiator has arrived since our answer (§12.5 rule 2). */
  initiatorSpoke: boolean;
}

interface Grant {
  id: string;
  grantee: string;
  scope: string[];
  valid_until: number;
  presence_audience?: string;
  /** P§12.3: the scopes it carried keys for. */
  keyScopes: string[];
  /** P§12.5 (spec-gap 159): the grants it follows by re-granting, newest first. */
  chain: string[];
  /** P§12.5: it has ended; a grant ends once. */
  ended: boolean;
}

/** Spec: P§8 — T-Presence-Rotate default and bounds, seconds. */
const T_PRESENCE_ROTATE = 60;
const T_PRESENCE_ROTATE_BOUNDS: [number, number] = [0, 3600];

/** P§12.1: a key id's scope and epoch, or undefined when it is not `scope.digits`. */
function parseKid(kid: unknown): [string, number] | undefined {
  if (typeof kid !== "string") return undefined;
  const m = /^(.*)\.([0-9]+)$/.exec(kid);
  return m ? [m[1]!, Number(m[2])] : undefined;
}

/** Trace context for an endpoint (vectors README, kind `state`). */
export interface EndpointContext {
  self: { device: string; identity: string };
  /** Device DID → identity DID, standing in for verified delegations. */
  identities?: Record<string, string>;
  start: number;
  timers?: { t_establish?: number; t_ring?: number; t_ring_local?: number };
  policy?: { first_contact_required?: boolean; allow?: string[] };
  /** P§12.3, P§12.5: presence keys (vectors README "Endpoint presence keys"). */
  presence_keys?: { sealed?: string[]; t_rotate?: number; grant_ids?: string[] };
}

function clamp(v: number, [lo, hi]: [number, number]): number {
  return Math.min(hi, Math.max(lo, v));
}

/** One endpoint holding any number of sessions. */
export class Endpoint {
  private readonly sessions = new Map<string, Session>();
  private readonly timers: Timers;
  private emit: Json[] = [];
  private readonly requests = new Map<string, { device: string; identity: string }>(); // by introduction id
  private readonly pendingSent = new Set<string>();
  private readonly grantsIssued = new Map<string, Grant>();
  private readonly grantsHeld = new Map<string, { by: string; valid_until: number; scope: string[] }>(); // grant id → granting identity, life, scope
  private readonly tokens = new Map<string, string>(); // contact token → grant id to issue
  // P§12.4, P§12.5: presence keys
  private readonly sealed: Set<string>;
  private readonly tRotate: number;
  private readonly grantIds: string[];
  private readonly epochs = new Map<string, number>();
  private readonly lastRotated = new Map<string, number>();
  private readonly due = new Map<string, number>();
  private readonly heldKeys = new Map<string, Map<string, Set<number>>>(); // grantor → scope → epochs

  constructor(private readonly ctx: EndpointContext) {
    this.timers = new Timers(ctx.start);
    const pk = ctx.presence_keys;
    this.sealed = new Set(pk?.sealed ?? []);
    this.tRotate = clamp(pk?.t_rotate ?? T_PRESENCE_ROTATE, T_PRESENCE_ROTATE_BOUNDS);
    this.grantIds = [...(pk?.grant_ids ?? [])];
    if (pk) for (const scope of ["main", ...this.sealed]) this.epochs.set(scope, 0);
  }

  /** Apply one trace event; returns the ordered emissions. */
  step(event: JsonObject): Json[] {
    this.emit = [];
    if ("advance" in event) {
      this.timers.advance(event["advance"] as number, (name, session) => this.fire(name, session),
        () => [
          ...[...this.grantsIssued.values()].filter((g) => g.keyScopes.length > 0 && !g.ended).map((g) => g.valid_until),
          ...this.due.values(),
          ...[...this.sessions.values()].filter((s) => s.outstanding).map((s) => s.updateExpires!),
        ],
        () => {
          // §12.8 rule 7: an update unanswered at its expires_at is no longer outstanding, in session id order. Its
          // sender treats it as rejected, `session.expired`; its receiver may no longer answer it.
          for (const id of [...this.sessions.keys()].sort()) {
            const s = this.sessions.get(id)!;
            if (!s.outstanding || s.updateExpires! > this.now) continue;
            this.emit.push(s.outstanding.direction === "outbound"
              ? { ui: "update_rejected", reason: "session.expired" } : { ui: "update_lapsed" });
            s.outstanding = null;
          }
          // P§12.5: shares reaching their valid_until end at that instant (spec-gap 141), in id order; then rotation
          for (const id of [...this.grantsIssued.keys()].sort()) {
            const g = this.grantsIssued.get(id)!;
            if (g.keyScopes.length > 0 && !g.ended && g.valid_until <= this.now) this.endGrant(g, []);
          }
          this.rotateDue();
        });
    } else if ("recv" in event) {
      this.recv(event["recv"] as JsonObject);
    } else {
      this.local(event);
    }
    return this.emit;
  }

  /** The snapshot members a step's `expect` names. */
  snapshot(expect: JsonObject): JsonObject {
    const out: JsonObject = {};
    if ("sessions" in expect) {
      const sessions: JsonObject = {};
      for (const id of Object.keys(expect["sessions"] as JsonObject)) {
        const s = this.sessions.get(id);
        if (s) {
          sessions[id] = { role: s.role, state: s.state, renegotiating: s.outstanding?.direction === "outbound", outstanding_update: s.outstanding };
        }
      }
      out["sessions"] = sessions;
    }
    if ("contacts" in expect) {
      out["contacts"] = {
        allow: [...(this.ctx.policy?.allow ?? [])].sort(),
        grants_issued: [...this.grantsIssued.keys()].sort(),
        grants_held: [...this.grantsHeld.keys()].sort(),
        requests: [...this.requests.keys()].sort(),
        pending_sent: [...this.pendingSent].sort(),
      };
    }
    if ("presence_keys" in expect) {
      const chains: JsonObject = {};
      for (const id of [...this.grantsIssued.keys()].sort()) {
        const g = this.grantsIssued.get(id)!;
        if (g.chain.length > 0) chains[id] = [...g.chain];
      }
      const held: JsonObject = {};
      for (const by of [...this.heldKeys.keys()].sort()) {
        const scopes = this.heldKeys.get(by)!;
        held[by] = [...scopes.keys()].sort().flatMap((sc) => [...scopes.get(sc)!].sort((a, b) => a - b).map((e) => `${sc}.${e}`));
      }
      out["presence_keys"] = {
        epochs: Object.fromEntries(this.epochs),
        due: Object.fromEntries(this.due),
        chains,
        held,
      };
    }
    return out;
  }

  // ---- helpers

  private get now(): number {
    return this.timers.now;
  }

  private identityOf(did: string): string {
    return this.ctx.identities?.[did] ?? did;
  }

  private send(type: string, to: string, fields: JsonObject = {}): void {
    this.emit.push({ send: { type, to, ...fields } });
  }

  private stop(name: string, session: string): void {
    if (this.timers.stop(name, session)) this.emit.push({ timer: "stop", name });
  }

  private start(name: string, session: string, seconds: number): void {
    this.timers.start(name, session, seconds);
    this.emit.push({ timer: "start", name, seconds });
  }

  private stopAll(session: string): void {
    for (const name of ["T-Establish", "T-Ring", "T-Queue", "T-Ring-Local"]) this.stop(name, session);
  }

  /** End a session: media stops (when running) before the end is surfaced. */
  private end(id: string, s: Session, surface?: string): void {
    s.state = "ENDED";
    s.outstanding = null; // §12.8 rule 6: bye discards a pending update
    if (s.media) {
      s.media = false;
      this.emit.push({ media: "stop" });
    }
    if (surface !== undefined) this.emit.push({ ui: "ended", reason: surface });
  }

  private invalidState(msg: JsonObject): void {
    this.send("error", msg["from"] as string, {
      session: msg["session"] ?? msg["id"]!,
      reason: "session.invalid-state",
      in_reply_to: msg["id"]!,
    });
  }

  // ---- timers

  private fire(name: string, id: string): void {
    const s = this.sessions.get(id)!;
    this.emit.push({ timer: "fire", name });
    if (name === "T-Ring-Local") {
      // §12.9: local ring timeout → reject user.no-answer
      this.send("reject", s.to, { session: id, reason: "user.no-answer" });
      this.end(id, s, "user.no-answer");
    } else {
      this.timeoutCancel(id, s);
    }
  }

  /** §12.4: T-Establish / T-Ring / T-Queue expiry → cancel session.timeout. */
  private timeoutCancel(id: string, s: Session): void {
    this.send("cancel", s.to, { session: id, reason: "session.timeout" });
    s.endedBy = "cancel";
    this.end(id, s, "session.timeout");
  }

  // ---- local events

  private local(e: JsonObject): void {
    const verb = e["local"] as string;
    const id = e["session"] as string;
    const s = this.sessions.get(id);
    // a local request about a session this endpoint does not hold is refused as such
    const SESSION_VERBS = ["cancel", "hangup", "alert", "auto_reject", "accept", "decline", "update", "answer_update", "reject_update", "info"];
    if (!s && SESSION_VERBS.includes(verb)) return void this.emit.push({ refused: "unknown-session" });
    switch (verb) {
      case "place_call": {
        // a session id is used once (§12.9): a session this endpoint holds, live or ended, is never overwritten
        if (s) return void this.emit.push({ refused: "invalid-state" });
        const to = e["to"] as string;
        this.sessions.set(id, { role: "initiator", state: "INVITING", to, outstanding: null, media: false, requeues: 0, initiatorSpoke: false });
        // §19.4: the grantee MAY reference a held grant in the invite's `grant` field: only one that admits the
        // invite, i.e. live and carrying `dsip.invite` (spec-gap 151)
        const held = [...this.grantsHeld.entries()].find(
          ([, g]) => g.by === this.identityOf(to) && g.valid_until > this.now && g.scope.includes("dsip.invite"),
        )?.[0];
        this.send("invite", to, { session: id, ...(held !== undefined ? { grant: held } : {}) });
        this.start("T-Establish", id, this.ctx.timers?.t_establish ?? T_ESTABLISH);
        return;
      }
      case "cancel":
        if (!s || (s.state !== "INVITING" && s.state !== "PROCEEDING")) return void this.emit.push({ refused: "invalid-state" });
        this.stopAll(id);
        this.send("cancel", s.to, { session: id, reason: "user.cancelled" });
        s.endedBy = "cancel";
        return this.end(id, s);
      case "hangup":
        if (!s || s.state !== "ACTIVE") return void this.emit.push({ refused: "invalid-state" });
        this.send("bye", s.peer!, { session: id, reason: (e["reason"] as string) ?? "user.hangup" });
        return this.end(id, s);
      case "alert": {
        if (!s || s.state !== "OFFERED") return void this.emit.push({ refused: "invalid-state" });
        if (s.inviteExpires !== undefined && s.inviteExpires <= this.now) {
          // §12.9: expires_at bounds pre-alerting delivery; exclusive, expired at expires_at (spec-gap 141)
          this.send("reject", s.to, { session: id, reason: "session.expired" });
          return this.end(id, s);
        }
        const advertised = e["ring_timeout"] as number | undefined;
        s.state = "ALERTING";
        this.send("progress", s.to, { session: id, status: "ringing", ...(advertised !== undefined ? { ring_timeout: advertised } : {}) });
        // §12.9: T-Ring-Local SHOULD be ≤ the advertised ring_timeout
        this.start("T-Ring-Local", id, advertised ?? this.ctx.timers?.t_ring_local ?? T_RING);
        return;
      }
      case "auto_reject":
        if (!s || s.state !== "OFFERED") return void this.emit.push({ refused: "invalid-state" });
        this.send("reject", s.to, { session: id, reason: e["reason"]! });
        return this.end(id, s);
      case "accept":
        if (!s || s.state !== "ALERTING") return void this.emit.push({ refused: "invalid-state" });
        this.stop("T-Ring-Local", id);
        this.send("answer", s.to, { session: id, answered_by: e["answered_by"]! });
        s.state = "ACTIVE";
        s.peer = s.to;
        s.media = true;
        this.emit.push({ media: "start" });
        return;
      case "decline":
        if (!s || s.state !== "ALERTING") return void this.emit.push({ refused: "invalid-state" });
        this.stop("T-Ring-Local", id);
        // §12.4: the user's decline; a caller-named reason (e.g. Recording Profile C§4's
        // `policy.recording-declined`) is carried as given, `user.declined` otherwise
        this.send("reject", s.to, { session: id, reason: typeof e["reason"] === "string" ? e["reason"] : "user.declined" });
        return this.end(id, s);
      case "update":
        if (!s || s.state !== "ACTIVE") return void this.emit.push({ refused: "invalid-state" });
        // §12.8 rule 2: one outstanding update per session, across both directions
        if (s.outstanding) return void this.emit.push({ refused: "update-pending" });
        s.outstanding = { id: e["id"] as string, direction: "outbound" };
        // §12.9: the update's validity, 30 s unless the trace names one
        s.updateExpires = this.now + (typeof e["validity"] === "number" ? e["validity"] : 30);
        this.send("update", s.peer!, { session: id, id: e["id"]!, ...("answered_by" in e ? { answered_by: e["answered_by"]! } : {}) });
        return;
      case "answer_update":
      case "reject_update": {
        if (!s || s.outstanding?.direction !== "inbound" || s.outstanding.id !== e["in_reply_to"]) {
          return void this.emit.push({ refused: "no-pending-update" });
        }
        s.outstanding = null;
        if (verb === "answer_update") {
          // Impl: `answer` requires `answered_by`; a renegotiation answer is the user's unless the event says otherwise
          this.send("answer", s.peer!, { session: id, answered_by: e["answered_by"] ?? "user", in_reply_to: e["in_reply_to"]! });
          this.emit.push({ media: "apply_update" });
        } else {
          // §12.8 rule 5: a rejected update leaves the session as it was
          this.send("reject", s.peer!, { session: id, reason: e["reason"]!, in_reply_to: e["in_reply_to"]! });
        }
        return;
      }
      case "info":
        if (!s || s.state !== "ACTIVE") return void this.emit.push({ refused: "invalid-state" });
        return this.send("info", s.peer!, { session: id });
      case "introduce": {
        const intro = e["id"] as string;
        this.pendingSent.add(intro);
        const extra: JsonObject = {};
        for (const k of ["purpose", "contact_token"]) if (k in e) extra[k] = e[k]!;
        return this.send("introduction", e["to"] as string, { id: intro, ...extra });
      }
      case "grant": {
        const intro = e["introduction"] as string;
        const grantee = this.requests.get(intro)?.identity;
        if (grantee === undefined) return void this.emit.push({ refused: "unknown-introduction" });
        const audience = e["presence_audience"];
        // P§6 (spec-gap 145): an audience token; a malformed one sends nothing and keeps the request pending
        if (audience !== undefined && !(typeof audience === "string" && /^[a-z][a-z0-9-]{0,63}$/.test(audience))) {
          return void this.emit.push({ refused: "invalid-audience" });
        }
        this.requests.delete(intro);
        return this.issueGrant(intro, grantee, e["id"] as string, e["scope"] as string[], e["valid_until"] as number,
          audience as string | undefined);
      }
      case "regrant": {
        // §19.4 (spec-gap 150): a grant may follow a live grant we issued, without an introduction
        const followed = e["grant"] as string;
        const old = this.grantsIssued.get(followed);
        if (old === undefined || old.valid_until <= this.now) return void this.emit.push({ refused: "unknown-grant" });
        const audience = e["presence_audience"];
        if (audience !== undefined && !(typeof audience === "string" && /^[a-z][a-z0-9-]{0,63}$/.test(audience))) {
          return void this.emit.push({ refused: "invalid-audience" }); // P§6; nothing sent, the followed grant kept
        }
        // P§7 (spec-gap 159): the followed grant and its rotation chain are revoked at the authority
        this.emit.push({ revoke: [followed, ...old.chain] });
        this.grantsIssued.delete(followed); // the new grant withdraws the one it follows
        const id = e["id"] as string;
        this.issueGrant(followed, old.grantee, id, e["scope"] as string[], e["valid_until"] as number,
          audience as string | undefined);
        // P§12.5 (spec-gap 161): a scope the new grant still carries is not lost, so not rotated
        this.endGrant(old, this.grantsIssued.get(id)!.keyScopes);
        return this.rotateDue();
      }
      case "reject_introduction": {
        const intro = e["introduction"] as string;
        const from = this.requests.get(intro);
        if (from === undefined) return void this.emit.push({ refused: "unknown-introduction" });
        this.requests.delete(intro);
        // §19.4 (spec-gap 74): an introduction's outcome — grant or reject — is addressed to the introducing identity
        return this.send("reject", from.identity, { session: intro, reason: e["reason"]! });
      }
      case "revoke": {
        const id = e["grant"] as string;
        const g = this.grantsIssued.get(id);
        if (g === undefined) return void this.emit.push({ refused: "unknown-grant" });
        this.grantsIssued.delete(id);
        this.emit.push({ revoke: [id, ...g.chain] }); // P§7 (spec-gap 159): the grant and its rotation chain
        this.endGrant(g, []);
        return this.rotateDue();
      }
      case "issue_token":
        this.tokens.set(e["token"] as string, e["grant_id"] as string);
        return;
      default:
        throw new Error(`unknown local event ${verb}`);
    }
  }

  /**
   * `session` is the introduction answered, or the grant followed (spec-gap 150). P§12.3: a grant admitting presence
   * carries the keys of `main` and its audience at their current epochs, when either is sealed.
   */
  private issueGrant(intro: string, grantee: string, id: string, scope: string[], valid_until: number,
    presence_audience?: string, chain: string[] = []): void {
    const keyed = this.ctx.presence_keys !== undefined && scope.includes("dsip.subscribe")
      && (this.sealed.has("main") || (presence_audience !== undefined && this.sealed.has(presence_audience)));
    const keyScopes = keyed ? ["main", ...(presence_audience !== undefined ? [presence_audience] : [])] : [];
    for (const sc of keyScopes) if (!this.epochs.has(sc)) this.epochs.set(sc, 0);
    this.grantsIssued.set(id, { id, grantee, scope, valid_until, presence_audience, keyScopes, chain, ended: false });
    this.send("grant", grantee, {
      session: intro, id, scope, valid_until,
      ...(presence_audience !== undefined ? { presence_audience } : {}),
      ...(keyScopes.length > 0 ? { presence_keys: keyScopes.map((sc) => `${sc}.${this.epochs.get(sc)}`) } : {}),
    });
  }

  /** P§12.5: an ending grant makes the scopes it carried keys for due, but those in `keep`; a grant ends once. */
  private endGrant(g: Grant, keep: string[]): void {
    if (g.ended) return;
    g.ended = true;
    for (const sc of g.keyScopes) {
      if (keep.includes(sc) || this.due.has(sc)) continue;
      const last = this.lastRotated.get(sc);
      this.due.set(sc, last === undefined || this.now >= last + this.tRotate ? this.now : last + this.tRotate);
    }
  }

  /** P§12.5: the scopes due now rotate together, `main` first; then the live grants carrying them are re-granted. */
  private rotateDue(): void {
    const scopes = [...this.due].filter(([, t]) => t <= this.now).map(([sc]) => sc)
      .sort((a, b) => (a === "main" ? -1 : b === "main" ? 1 : a < b ? -1 : a > b ? 1 : 0));
    for (const sc of scopes) {
      this.due.delete(sc);
      this.epochs.set(sc, (this.epochs.get(sc) ?? 0) + 1);
      this.lastRotated.set(sc, this.now);
      this.emit.push({ keys: "rotated", scope: sc, epoch: this.epochs.get(sc)! });
    }
    this.regrant(new Set(scopes));
  }

  /** P§12.5: each live grant carrying a key of `scopes` is followed by one with the current keys; the old heads its chain. */
  private regrant(scopes: Set<string>): void {
    if (scopes.size === 0) return;
    for (const id of [...this.grantsIssued.keys()].sort()) {
      const g = this.grantsIssued.get(id)!;
      if (g.valid_until <= this.now || !g.keyScopes.some((sc) => scopes.has(sc))) continue;
      const next = this.grantIds.shift();
      if (next === undefined) throw new Error("context.presence_keys.grant_ids exhausted");
      this.grantsIssued.delete(id);
      this.issueGrant(id, g.grantee, next, g.scope, g.valid_until, g.presence_audience, [id, ...g.chain]);
    }
  }

  /**
   * P§12.5: a record of our own identity from a sibling, seen through our own watch: an epoch above ours is adopted and
   * the live grants carrying its scope re-granted. Anything else is ignored.
   */
  private recvOwnRecord(m: JsonObject): void {
    if (this.ctx.presence_keys === undefined || m["subject"] !== this.ctx.self.identity) return;
    const kid = parseKid(m["kid"]);
    if (kid === undefined) return;
    const [scope, epoch] = kid;
    const ours = this.epochs.get(scope);
    if (ours !== undefined && epoch <= ours) return;
    this.epochs.set(scope, epoch);
    this.emit.push({ keys: "seen", scope, epoch });
    this.regrant(new Set([scope]));
  }

  // ---- received messages

  private recv(m: JsonObject): void {
    const type = m["type"] as string;
    if (type === "invite") return this.recvInvite(m);
    if (type === "introduction") return this.recvIntroduction(m);
    if (type === "error") return this.recvError(m);
    if (type === "presence") return this.recvOwnRecord(m);
    const id = m["session"] as string;
    if (type === "grant" || (type === "reject" && this.pendingSent.has(id))) return this.recvIntroductionOutcome(m);

    const s = this.sessions.get(id);
    if (!s) {
      return this.send("error", m["from"] as string, { session: id, reason: "session.unknown-session", in_reply_to: m["id"]! });
    }
    if (s.state === "ENDED") {
      if (type === "answer" && s.role === "initiator" && !("in_reply_to" in m)) {
        // §12.5 rule 3 (after our cancel) / §12.7 rule 4 (the invite was answered, however the call then ended) /
        // §12.4 (an attempt that was never answered): never resurrect
        const reason = s.endedBy === "cancel" ? "session.cancelled" : s.answered ? "session.already-answered" : "session.failed";
        return this.send("bye", m["from"] as string, { session: id, reason });
      }
      return void this.emit.push({ drop: "ended-session" });
    }
    if (s.role === "initiator") this.recvAsInitiator(id, s, m);
    else this.recvAsResponder(id, s, m);
  }

  /**
   * A received `error` is surfaced and changes nothing — except the relay's own
   * `transport.no-response`, which is the attempt outcome when every leg stayed silent.
   * Spec: §12.7 rule 6 (spec-gap 76) — no `cancel` follows: the relay has closed every leg.
   */
  private recvError(m: JsonObject): void {
    const id = m["session"] as string | undefined;
    const s = id !== undefined ? this.sessions.get(id) : undefined;
    const attempt = s?.role === "initiator" && (s.state === "INVITING" || s.state === "PROCEEDING");
    if (m["reason"] !== "transport.no-response" || !s || !attempt) return void this.emit.push({ ui: "error", reason: m["reason"]! });
    this.stopAll(id!);
    s.endedBy = "other";
    this.end(id!, s, "transport.no-response");
  }

  /** Spec: §15.1 — what is surfaced is the effective reason: an unrecognized category reads as `session.failed`. */
  private reasonOf(m: JsonObject): string {
    return effectiveReason(m["reason"] as string, m["type"] as string).reason;
  }

  private recvAsInitiator(id: string, s: Session, m: JsonObject): void {
    const type = m["type"] as string;
    const pre = s.state === "INVITING" || s.state === "PROCEEDING";
    if (type === "progress" && pre) return this.recvProgress(id, s, m);
    if (type === "answer" && pre && !("in_reply_to" in m)) { // an answer naming an update is an update reply (§12.8), invalid before ACTIVE
      this.stopAll(id);
      s.state = "ACTIVE";
      s.answered = true;
      s.peer = m["from"] as string;
      s.media = true;
      this.emit.push({ media: "start" });
      this.emit.push({ ui: "answered", answered_by: effectiveAnsweredBy(m["answered_by"] as string) });
      // §12.7 rule 3: identity-addressed invite → cancel answered-elsewhere to the invite's `to`
      if (s.peer !== s.to) this.send("cancel", s.to, { session: id, reason: "session.answered-elsewhere" });
      return;
    }
    if (type === "reject" && pre && !("in_reply_to" in m)) { // likewise: a reject naming an update is an update reply
      this.stopAll(id);
      s.endedBy = "other";
      return this.end(id, s, this.reasonOf(m));
    }
    if (s.state === "ACTIVE") {
      if (type === "answer" && !("in_reply_to" in m) && m["from"] !== s.peer) {
        // §12.7 rule 4: exactly one answer is ever applied
        return this.send("bye", m["from"] as string, { session: id, reason: "session.already-answered" });
      }
      if (this.recvActive(id, s, m)) return;
    }
    this.invalidState(m);
  }

  /** §12.9 / §12.10 timer adjustments on `progress`. */
  private recvProgress(id: string, s: Session, m: JsonObject): void {
    const status = effectiveStatus(m["status"] as string);
    s.state = "PROCEEDING";
    this.stop("T-Establish", id);
    this.emit.push({ ui: "progress", status });
    if (status === "queued") {
      s.requeues += 1;
      if (s.requeues > MAX_REQUEUES) {
        // §12.10: a queued beyond the limit is treated as T-Queue expiry
        this.stopAll(id);
        return this.timeoutCancel(id, s);
      }
      this.stop("T-Ring", id);
      this.timers.stop("T-Queue", id); // a restart emits only `start`
      return this.start("T-Queue", id, Math.min(m["queue_timeout"] as number, T_QUEUE_CAP));
    }
    const ringRunning = this.timers.running("T-Ring", id);
    const queueRunning = this.timers.running("T-Queue", id);
    if (status === "ringing") {
      s.requeues = 0;
      this.stop("T-Queue", id);
      const restart = typeof m["ring_timeout"] === "number";
      if (restart) this.timers.stop("T-Ring", id);
      if (restart) this.start("T-Ring", id, clamp(m["ring_timeout"] as number, T_RING_BOUNDS));
      else if (!ringRunning) this.start("T-Ring", id, this.ctx.timers?.t_ring ?? T_RING);
      return;
    }
    // §12.9: trying/forwarded start T-Ring when nothing bounds PROCEEDING yet
    if (!ringRunning && !queueRunning) this.start("T-Ring", id, this.ctx.timers?.t_ring ?? T_RING);
  }

  private recvAsResponder(id: string, s: Session, m: JsonObject): void {
    const type = m["type"] as string;
    if (type === "cancel") {
      const reason = this.reasonOf(m);
      if (s.state === "OFFERED") return this.end(id, s, reason);
      if (s.state === "ALERTING") {
        this.stop("T-Ring-Local", id);
        // §12.11: answered-elsewhere MUST NOT surface as a missed call
        if (reason !== "session.answered-elsewhere") this.emit.push({ ui: "missed_call" });
        return this.end(id, s, reason);
      }
      // §12.5 rule 2: crossed if the initiator has not spoken since our answer; otherwise late
      // Impl: `session.answered-elsewhere` is for the legs that did not answer (§12.7 rule 3); at the
      // answering leg it is never a crossed withdrawal, so it is invalid for the state.
      if (s.state === "ACTIVE" && !s.initiatorSpoke && reason !== "session.answered-elsewhere") return this.end(id, s, reason);
      return this.invalidState(m);
    }
    if (s.state === "ACTIVE") {
      s.initiatorSpoke = true;
      if (this.recvActive(id, s, m)) return;
    }
    this.invalidState(m);
  }

  /** Messages valid in ACTIVE for either role: bye, update and its replies, info. */
  private recvActive(id: string, s: Session, m: JsonObject): boolean {
    const type = m["type"] as string;
    if (type === "bye") {
      this.end(id, s, this.reasonOf(m));
      return true;
    }
    if (type === "info") {
      // §12.12: an unrecognized `about` is ignored silently
      this.emit.push(KNOWN_ABOUT.includes(m["about"] as string) ? { info: { about: m["about"]! } } : { drop: "unknown-about" });
      return true;
    }
    if (type === "update") {
      const theirs = m["id"] as string;
      if (s.outstanding?.direction === "inbound") {
        // §12.8 rule 4: second update before the first resolves — process neither
        s.outstanding = null;
        this.send("error", m["from"] as string, { session: id, reason: "session.update-pending", in_reply_to: theirs });
      } else if (s.outstanding && s.outstanding.id < theirs) {
        // §12.8 rule 3: glare — the smaller id proceeds
        this.send("reject", m["from"] as string, { session: id, reason: "session.glare", in_reply_to: theirs });
      } else {
        if (s.outstanding) this.emit.push({ ui: "update_rejected", reason: "session.glare" });
        s.outstanding = { id: theirs, direction: "inbound" };
        // vectors README, "Update expiry": the trace's expires_at, or 30 s after its receipt
        s.updateExpires = typeof m["expires_at"] === "number" ? m["expires_at"] : this.now + 30;
        this.emit.push({ ui: "update_offered" });
        // §14.4: an update may escalate a screening answer; the new `answered_by` is surfaced
        if (typeof m["answered_by"] === "string") this.emit.push({ ui: "answered", answered_by: effectiveAnsweredBy(m["answered_by"]) });
      }
      return true;
    }
    if ((type === "answer" || type === "reject") && "in_reply_to" in m) {
      if (s.outstanding?.direction !== "outbound" || s.outstanding.id !== m["in_reply_to"]) {
        this.emit.push({ drop: "stale-update-reply" });
      } else {
        s.outstanding = null;
        this.emit.push(type === "answer" ? { media: "apply_update" } : { ui: "update_rejected", reason: this.reasonOf(m) });
      }
      return true;
    }
    return false;
  }

  private recvInvite(m: JsonObject): void {
    const id = m["id"] as string;
    const from = m["from"] as string;
    const fresh = (state: State): Session => ({
      role: "responder", state, to: from, peer: from, inviteExpires: m["expires_at"] as number | undefined,
      outstanding: null, media: false, requeues: 0, initiatorSpoke: false,
    });
    const existing = this.sessions.get(id);
    const ownAttempt = existing?.role === "initiator" && (existing.state === "INVITING" || existing.state === "PROCEEDING");
    if (existing && !ownAttempt) {
      // an invite names a new session; one for a session this endpoint already holds is invalid for its state
      // (§12.4) — or ignored when that session has ended. Our own live attempt under the same id is glare (§12.6).
      if (existing.state === "ENDED") return void this.emit.push({ drop: "ended-session" });
      return this.invalidState(m);
    }
    // §12.9 (spec-gap 141): an invite is expired when now >= expires_at
    if (typeof m["expires_at"] === "number" && m["expires_at"] <= this.now) {
      this.sessions.set(id, fresh("ENDED"));
      return this.send("reject", from, { session: id, reason: "session.expired" });
    }
    if (this.ctx.policy?.first_contact_required && !this.admitted(m)) {
      this.sessions.set(id, fresh("ENDED"));
      return this.send("reject", from, { session: id, reason: "policy.first-contact-required" });
    }
    // §12.6: glare with our own outstanding invites to the same identity. Every live attempt of ours to it is a
    // rival, and the smallest id among all the invites wins.
    const inviter = this.identityOf(from);
    const rivals = [...this.sessions.entries()]
      .filter(([, s]) => s.role === "initiator" && (s.state === "INVITING" || s.state === "PROCEEDING") && this.identityOf(s.to) === inviter)
      .sort(([a], [b]) => (a < b ? -1 : 1));
    if (rivals.length > 0) {
      const first = rivals[0]![0];
      if (first < id) {
        // ours wins: theirs is rejected, and we carry on as initiator
        this.sessions.set(id, fresh("ENDED"));
        return this.send("reject", from, { session: id, reason: "session.glare" });
      }
      // each of our invites lost, so each is withdrawn, in id order
      for (const [ours, s] of rivals) {
        this.stopAll(ours);
        this.send("cancel", s.to, { session: ours, reason: "session.glare" });
        s.endedBy = "cancel";
        this.end(ours, s, "session.glare");
      }
      if (first === id) {
        // Impl: equal ids share one session key; the outbound session is the one kept
        this.send("reject", from, { session: id, reason: "session.glare" });
        return void this.emit.push({ ui: "glare_retry" });
      }
    }
    this.sessions.set(id, fresh("OFFERED"));
    this.emit.push({ ui: "offered" });
  }

  /** §19.4: a live grant with `dsip.invite` issued to the inviting identity admits the invite. The invite's `grant`
   *  reference only helps find it: it never admits and never refuses on its own (spec-gap 151). */
  private admitted(invite: JsonObject): boolean {
    const identity = this.identityOf(invite["from"] as string);
    if ((this.ctx.policy?.allow ?? []).includes(identity)) return true;
    return [...this.grantsIssued.values()].some(
      (g) => g.grantee === identity && g.valid_until > this.now && g.scope.includes("dsip.invite"),
    );
  }

  private recvIntroduction(m: JsonObject): void {
    const id = m["id"] as string;
    const identity = this.identityOf(m["from"] as string);
    if (this.answered.has(id)) return void this.emit.push({ drop: "duplicate-introduction" });
    const token = m["contact_token"];
    const grantId = typeof token === "string" ? this.tokens.get(token) : undefined;
    if (grantId !== undefined) {
      // §19.4: tokens are single-use; the first introduction carrying one is auto-granted
      this.tokens.delete(token as string);
      this.answered.add(id);
      this.emit.push({ ui: "introduction_received", from: identity, token: true });
      return this.issueGrant(id, identity, grantId, ["dsip.invite"], this.now + 31536000);
    }
    this.requests.set(id, { device: m["from"] as string, identity });
    this.answered.add(id);
    // §19.4: a requests surface, never a ring
    this.emit.push({ ui: "introduction_received", from: identity });
  }

  private readonly answered = new Set<string>();

  private recvIntroductionOutcome(m: JsonObject): void {
    const intro = m["session"] as string;
    const by = this.identityOf(m["from"] as string);
    const followed = this.grantsHeld.get(intro);
    if (this.pendingSent.has(intro)) {
      this.pendingSent.delete(intro);
    } else if (m["type"] === "grant" && followed !== undefined && followed.by === by && followed.valid_until > this.now) {
      // §19.4 (spec-gap 150): a grant following a live grant we hold from the same identity replaces it
      this.grantsHeld.delete(intro);
    } else {
      return void this.emit.push({ drop: "unknown-introduction" });
    }
    if (m["type"] === "grant") {
      this.grantsHeld.set(m["id"] as string, { by, valid_until: m["valid_until"] as number, scope: (m["scope"] as string[] | undefined) ?? [] });
      // P§12.4: the keys it carried; per scope, those of the two highest epochs are kept
      for (const k of (m["presence_keys"] as Json[] | undefined) ?? []) {
        const kid = parseKid(k);
        if (kid === undefined) continue;
        const scopes = this.heldKeys.get(by) ?? new Map<string, Set<number>>();
        this.heldKeys.set(by, scopes);
        const epochs = scopes.get(kid[0]) ?? new Set<number>();
        scopes.set(kid[0], epochs);
        epochs.add(kid[1]);
        while (epochs.size > 2) epochs.delete(Math.min(...epochs));
      }
      this.emit.push({ ui: "granted", by: this.identityOf(m["from"] as string) });
    } else {
      this.emit.push({ ui: "introduction_rejected", reason: this.reasonOf(m) });
    }
  }
}
