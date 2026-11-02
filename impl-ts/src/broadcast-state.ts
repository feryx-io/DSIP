/**
 * The two stateful sides of the subscription protocol: the authority that holds publication
 * records and presence for its targets, and the subscriber.
 *
 * Spec: §9.3 (subscribe/notify, soft state, seq-ordered notifies, anti-enumeration; v0.17: presence is private by
 * default), §19.4 (v0.17: `presence_audience` on a grant, `grant-revocation`), §22.1
 * (publication records: publisher binding, stream-id namespace, newer ULID replaces), §22.3
 * (provenance statements attach to a record and never replace its publisher); Presence Profile P§3 (a device's
 * signed record published to its authority: refusals in order, the body with `records`, expiry, the unbind grace,
 * notifying on body changes), P§4 (`seq` per `(subject, device)`), P§6 (admission order, audiences, the body per
 * subscription), P§7 (a share's `valid_until`, revocation), P§8 (lifetime bounds, T-Presence-Grace, the
 * publish interval), P§12.6 (sealed records kept and routed as plain ones, given only to subscriptions that
 * listed `presence/0.2`).
 */
import type { Json, JsonObject } from "./did.js";
import { byCodePoint } from "./recording/recording.js";

interface Publication {
  id: string;
  publisher: string;
  state: string;
  variants: string[];
  expires?: number;
  provenance: string[];
}

/** One presence record, as the authority holds it: the current record of a `(subject, device, audience)`. Spec: P§3, P§6 */
interface PresenceRecord {
  id: string;
  device: string;
  /** Absent: the record names no audience, which counts as an audience of its own. Spec: P§6 */
  audience?: string;
  /** A plain record's state. A sealed one carries `kid` and `sealed_state` instead, which the authority never opens. Spec: P§12.2, P§12.6 */
  state?: string;
  kid?: string;
  sealed_state?: string;
  seq: number;
  expires_at: number;
}

/** Spec: P§8 — T-Presence-Grace default, seconds. */
export const PRESENCE_GRACE_DEFAULT_S = 60;
/** Spec: P§8 — record lifetime bounds (`expires_at − issued_at`), seconds. */
export const PRESENCE_LIFETIME_MIN_S = 60;
/** Spec: P§8 — record lifetime upper bound, seconds. */
export const PRESENCE_LIFETIME_MAX_S = 3600;
/** Spec: P§8 — least interval between two accepted records of one device and audience, seconds. */
export const PRESENCE_PUBLISH_INTERVAL_S = 5;

interface Subscription {
  id: string;
  device: string;
  subscriber: string;
  target: string;
  events: string[];
  seq: number;
  expires_at: number;
  /** Admitted as one of the subject's own devices: sees every record. Spec: P§6 rule 1 */
  own?: boolean;
  /** The admitting grant, under P§6 rule 2. Spec: P§6, P§7 */
  grant?: { id: string; valid_until: number };
  /** The audience fixed at admission. Spec: P§6 */
  audience?: string;
  /** Its `subscribe` listed `presence/0.2` in `profiles`: it is given sealed records. Spec: P§12.6 */
  sealed?: boolean;
  /** The last presence body sent, for "notified exactly when its own body changes". Spec: P§6 */
  lastBody?: string;
}

/** Trace context shared by both components. */
export interface BroadcastContext {
  start: number;
  identities?: Record<string, string>;
  /** T-Presence-Grace, seconds (default 60). Spec: P§8 */
  presence_grace?: number;
}

/** The key a record is held under, and its key in the `presence` snapshot: `device` or `device/audience`. */
function recordKey(device: string, audience: string | undefined): string {
  return audience === undefined ? device : `${device}/${audience}`;
}

/** P§6 order: by device, then by audience, a record without one first. */
function recordOrder(a: PresenceRecord, b: PresenceRecord): number {
  const d = byCodePoint(a.device, b.device);
  if (d !== 0) return d;
  if (a.audience === b.audience) return 0;
  if (a.audience === undefined) return -1;
  if (b.audience === undefined) return 1;
  return byCodePoint(a.audience, b.audience);
}

/** A target's authority: its relay or domain endpoint. */
export class Authority {
  private now: number;
  private emit: Json[] = [];
  private readonly policy = new Map<string, { mode: string; allow: string[]; audience?: string }>();
  private readonly capabilities = new Map<string, string>(); // token → target
  private readonly publications = new Map<string, Publication>();
  private subscriptions: Subscription[] = [];
  private readonly bound = new Map<string, string>(); // device → identity
  /** Identities this authority has seen bind. Spec: §9.3 — targets never seen get the uniform reject. */
  private readonly seen = new Set<string>();
  private readonly records = new Map<string, Map<string, PresenceRecord>>(); // subject → recordKey → record
  /** device → when its unbind grace runs out. Spec: P§3, P§6 — the grace is per device. */
  private readonly graceUntil = new Map<string, number>();
  private readonly lastAccepted = new Map<string, number>(); // recordKey → when its last record was accepted
  /** `target identity \n grant id` → the grant's `valid_until`. Spec: P§7 */
  private readonly revoked = new Map<string, number>();

  constructor(private readonly ctx: BroadcastContext) {
    this.now = ctx.start;
  }

  /** Apply one trace event; returns the ordered emissions. */
  step(e: JsonObject): Json[] {
    this.emit = [];
    if ("advance" in e) this.advance(e["advance"] as number);
    else if ("recv" in e) this.recv(e["recv"] as JsonObject);
    else if (e["local"] === "policy") {
      this.policy.set(e["target"] as string, {
        mode: e["mode"] as string, allow: (e["allow"] ?? []) as string[],
        ...(typeof e["audience"] === "string" ? { audience: e["audience"] } : {}),
      });
    } else if (e["local"] === "issue_capability") this.capabilities.set(e["token"] as string, e["target"] as string);
    else if (e["relay"] === "bind" || e["relay"] === "unbind") this.bindingChange(e);
    else throw new Error(`unknown authority event ${JSON.stringify(e)}`);
    return this.emit;
  }

  /** The snapshot members a step's `expect` names, in full. */
  snapshot(expect: JsonObject): JsonObject {
    const out: JsonObject = {};
    if ("publications" in expect) {
      out["publications"] = Object.fromEntries(
        [...this.publications].map(([stream, p]) => [stream, { publication: p.id, publisher: p.publisher, state: p.state }]),
      );
    }
    if ("subscriptions" in expect) {
      out["subscriptions"] = Object.fromEntries(
        this.subscriptions.map((s) => [s.id, {
          subscriber: s.subscriber, target: s.target, events: s.events, seq: s.seq, expires_at: s.expires_at,
          ...(s.own ? { own: true } : {}),
          ...(s.grant ? { grant: s.grant.id } : {}),
          ...(s.audience !== undefined ? { audience: s.audience } : {}),
          ...(s.sealed ? { sealed: true } : {}),
        }]),
      );
    }
    if ("presence" in expect) {
      const presence: JsonObject = {};
      for (const [subject, held] of this.records) {
        if (held.size === 0) continue;
        presence[subject] = Object.fromEntries(
          [...held].map(([key, r]) => {
            const grace = this.graceUntil.get(r.device);
            const form: JsonObject = r.state !== undefined ? { state: r.state } : { kid: r.kid! };
            return [key, { seq: r.seq, ...form, expires_at: r.expires_at, ...(grace !== undefined ? { grace_until: grace } : {}) }];
          }),
        );
      }
      out["presence"] = presence;
    }
    return out;
  }

  private identityOf(did: string): string {
    return this.ctx.identities?.[did] ?? did;
  }

  private body(s: Subscription, event: string): JsonObject {
    if (event === "presence") return this.presenceBody(s);
    const p = this.publications.get(s.target)!;
    return { event, state: p.state, publication: p.id, ...(p.provenance.length ? { provenance: p.provenance } : {}) };
  }

  /** §9.3: notifies are seq-ordered per subscription. */
  private notify(s: Subscription, event: string, terminal?: string): void {
    s.seq += 1;
    const body = this.body(s, event);
    if (event === "presence") s.lastBody = JSON.stringify(body);
    this.emit.push({
      send: {
        type: "notify", to: s.device, subscription: s.id, seq: s.seq,
        state: terminal ? "terminated" : "active", ...(terminal ? { reason: terminal } : {}),
        body,
      },
    });
  }

  /**
   * Spec: P§6 — a subscription sees the records with no audience, those of its own audience, and, when own, all.
   * Spec: P§12.6 — but no sealed record unless its `subscribe` listed `presence/0.2`, own or not.
   */
  private sees(s: Subscription, r: PresenceRecord): boolean {
    if (r.sealed_state !== undefined && s.sealed !== true) return false;
    return s.own === true || r.audience === undefined || r.audience === s.audience;
  }

  /**
   * The presence body for one subscription. Spec: §9.3, P§3, P§6 — computed over what the subscription sees: the
   * state is the authority's assertion, `available` when any bound device of the subject holds no record the
   * subscription sees; `records`, ordered by device then audience (none first), when it sees any.
   * Impl: device and audience order is code-point order; a record is carried as the vectors README's
   * `{id, device, state, seq, expires_at, audience?}` summary of the signed envelope.
   */
  private presenceBody(s: Subscription): JsonObject {
    const visible = [...(this.records.get(s.target)?.values() ?? [])].filter((r) => this.sees(s, r)).sort(recordOrder);
    const asserted = [...this.bound].some(([device, identity]) => identity === s.target && !visible.some((r) => r.device === device));
    const body: JsonObject = { event: "presence", state: asserted ? "available" : "offline" };
    if (visible.length > 0) {
      body["records"] = visible.map((r) => ({
        id: r.id, device: r.device, seq: r.seq, expires_at: r.expires_at,
        ...(r.state !== undefined ? { state: r.state } : { kid: r.kid!, sealed_state: r.sealed_state! }),
        ...(r.audience !== undefined ? { audience: r.audience } : {}),
      }));
    }
    return body;
  }

  /**
   * Spec: P§3, P§6 — after an event that may change presence, every presence subscription whose own body changed
   * since its last notify gets one.
   * Impl: subjects in order (P§3), then subscription order within a subject, read as subscription-id code-point
   * order (the order `state/presence-audiences` expects).
   */
  private notifyChanged(): void {
    const order = this.subscriptions
      .filter((s) => s.events.includes("presence"))
      .sort((a, b) => byCodePoint(a.target, b.target) || byCodePoint(a.id, b.id));
    for (const s of order) {
      if (s.lastBody !== JSON.stringify(this.presenceBody(s))) this.notify(s, "presence");
    }
  }

  private notifyAll(target: string, event: string): void {
    for (const s of this.subscriptions) if (s.target === target && s.events.includes(event)) this.notify(s, event);
  }

  private setState(stream: string, p: Publication, state: string): void {
    p.state = state;
    this.emit.push({ publication: { stream, state } });
    this.notifyAll(stream, "publication");
  }

  /** Ends subscriptions with a terminal notify, in subscription (id) order. Spec: §9.3, P§7 */
  private terminate(ended: Subscription[], reason: string): void {
    for (const s of [...ended].sort((a, b) => byCodePoint(a.id, b.id))) {
      this.notify(s, s.events[0]!, reason);
      this.subscriptions = this.subscriptions.filter((x) => x !== s);
    }
  }


  private advance(seconds: number): void {
    this.now += seconds;
    for (const [stream, p] of this.publications) {
      // §8.3 / §22.1: a record past expiration is invalid — subscribers are told
      if (p.state === "live" && p.expires !== undefined && p.expires <= this.now) this.setState(stream, p, "expired");
    }
    // §9.3: subscriptions are soft state; a lapsed one ends with a terminal notify. P§7: a subscription admitted
    // by a grant ends when the clock reaches its valid_until (§12.9, exclusive), with policy.terminated; one that
    // lapses at the same instant ends with session.expired instead.
    // Impl: one pass over the subscriptions in subscription-id order, each ending by the first of the two that
    // applies to it (not every lapse before every share end), before record drops; the order the Python harness
    // was observed to take through probe vectors, where the README says only "after lapses (which win)".
    for (const s of [...this.subscriptions].sort((a, b) => byCodePoint(a.id, b.id))) {
      const reason = s.expires_at <= this.now ? "session.expired"
        : s.grant !== undefined && s.grant.valid_until <= this.now ? "policy.terminated" : undefined;
      if (reason === undefined) continue;
      this.notify(s, s.events[0]!, reason);
      this.subscriptions = this.subscriptions.filter((x) => x !== s);
    }
    // P§7: a revocation is kept until the grant's valid_until.
    for (const [key, until] of this.revoked) if (until <= this.now) this.revoked.delete(key);
    // P§3, P§6: each record past its expires_at, and every record of a device whose unbind grace has run out,
    // is dropped and its seq forgotten.
    for (const held of this.records.values()) {
      for (const [key, r] of [...held]) {
        const grace = this.graceUntil.get(r.device);
        if (r.expires_at <= this.now || (grace !== undefined && grace <= this.now)) held.delete(key);
      }
    }
    // P§3: the grace is the device's, from its first unbind; it outlives a record that expires meanwhile, so a record
    // accepted within it is still dropped when it runs out.
    for (const [device, until] of this.graceUntil) if (until <= this.now) this.graceUntil.delete(device);
    this.notifyChanged();
  }

  /**
   * A device binds to or unbinds from this relay, the source of the authority's assertion (§9.3).
   * Spec: P§3, P§6 — an unbound device keeps its records for T-Presence-Grace (0 drops them at the unbind),
   * counted from the first unbind; a bind within the grace keeps them as if the device had never left. The grace
   * is per device and covers all of its records. Subscribers hear only a changed body.
   */
  private bindingChange(e: JsonObject): void {
    const identity = e["identity"] as string;
    const device = e["device"] as string;
    const held = this.records.get(identity);
    const holds = held !== undefined && [...held.values()].some((r) => r.device === device);
    if (e["relay"] === "bind") {
      this.bound.set(device, identity);
      this.seen.add(identity);
      this.graceUntil.delete(device);
    } else {
      this.bound.delete(device);
      // P§3: the grace runs from the first unbind; a further unbind while it runs changes nothing.
      if (holds && !this.graceUntil.has(device)) {
        const grace = this.ctx.presence_grace ?? PRESENCE_GRACE_DEFAULT_S;
        if (grace === 0) {
          for (const [key, r] of [...held!]) if (r.device === device) held!.delete(key);
        } else this.graceUntil.set(device, this.now + grace);
      }
    }
    this.notifyChanged();
  }

  /**
   * A device publishes its record. Spec: P§3 — refused with `error`, the first that applies:
   * `presence.signer-mismatch` → `presence.lifetime` → `presence.stale` → `policy.rate-limited`; otherwise
   * it replaces the record of its `(subject, device, audience)` (P§6), unacknowledged, and every subscription whose
   * body it changes is notified.
   * Spec: P§3 rule 4, P§6 — the publish interval runs per device and audience from the last accepted record,
   * whether or not that record is still held.
   */
  private presence(m: JsonObject): void {
    const from = m["from"] as string;
    const subject = m["subject"] as string;
    const audience = typeof m["audience"] === "string" ? m["audience"] : undefined;
    const refuse = (reason: string, extra: JsonObject = {}): void =>
      void this.emit.push({ send: { type: "error", to: from, in_reply_to: m["id"]!, reason, ...extra } });
    // P§3 rule 1: the record names its signing device, for the identity that device is delegated by
    // (`context.identities`, the identity its delegation names).
    if (typeof m["device"] !== "string" || m["device"] !== from || subject !== this.identityOf(from)) {
      return refuse("presence.signer-mismatch");
    }
    // P§3 rule 2, P§8: lifetime 60–3,600 s.
    const lifetime = (m["expires_at"] as number) - (m["issued_at"] as number);
    if (lifetime < PRESENCE_LIFETIME_MIN_S || lifetime > PRESENCE_LIFETIME_MAX_S) return refuse("presence.lifetime");
    // P§3 rule 3, P§4, P§6: seq is ordered per (subject, device, audience).
    const key = recordKey(from, audience);
    const held = this.records.get(subject) ?? new Map<string, PresenceRecord>();
    const current = held.get(key);
    if (current && current.seq >= (m["seq"] as number)) return refuse("presence.stale");
    // P§3 rule 4, P§6, P§8: at most one accepted record per device and audience every 5 s; retry_after is the
    // whole seconds left.
    const last = this.lastAccepted.get(key);
    if (last !== undefined && this.now - last < PRESENCE_PUBLISH_INTERVAL_S) {
      return refuse("policy.rate-limited", { retry_after: PRESENCE_PUBLISH_INTERVAL_S - (this.now - last) });
    }
    // P§3: a record accepted from a device in its grace keeps the grace running (the grace is the device's).
    held.set(key, {
      id: m["id"] as string, device: from, ...(audience !== undefined ? { audience } : {}),
      // P§12.6: a sealed record is checked and kept as any other; its state stays sealed.
      ...(typeof m["state"] === "string" ? { state: m["state"] } : { kid: m["kid"] as string, sealed_state: m["sealed_state"] as string }),
      seq: m["seq"] as number, expires_at: m["expires_at"] as number,
    });
    this.records.set(subject, held);
    this.lastAccepted.set(key, this.now);
    this.notifyChanged();
  }

  /**
   * A device of the granting identity withdraws a grant. Spec: P§7, §19.4 — not answered; kept until the grant's
   * `valid_until`; every subscription that grant admitted, the grant issued by the revocation signer's identity,
   * ends at once with `terminated` `policy.terminated`, in subscription order.
   * Impl: `grantee` is not checked against the subscriptions the grant admitted (the vectors README's rule names
   * only the signer's identity and the grant id).
   */
  private grantRevocation(m: JsonObject): void {
    const identity = this.identityOf(m["from"] as string);
    const grant = m["grant"] as string;
    const validUntil = m["valid_until"] as number;
    // §12.9: a revocation whose grant has already ended has nothing left to keep.
    if (validUntil > this.now) this.revoked.set(`${identity}\n${grant}`, validUntil);
    this.terminate(this.subscriptions.filter((s) => s.grant?.id === grant && s.target === identity), "policy.terminated");
  }

  private recv(m: JsonObject): void {
    const sender = this.identityOf(m["from"] as string);
    switch (m["type"]) {
      case "publish": {
        const stream = m["stream_id"] as string;
        // §22.1: `publisher` MUST equal the verified identity; stream ids live under the publisher's DID
        if (m["publisher"] !== sender) return void this.emit.push({ drop: "publisher-mismatch" });
        if (!stream.startsWith(`${sender}:`)) return void this.emit.push({ drop: "stream-id-namespace" });
        const current = this.publications.get(stream);
        if (current && (m["id"] as string) <= current.id) return void this.emit.push({ drop: "stale-publication" });
        const record: Publication = {
          id: m["id"] as string, publisher: sender, state: "", provenance: [],
          variants: ((m["variants"] ?? []) as JsonObject[]).map((v) => v["id"] as string),
          expires: m["expires_at"] as number | undefined,
        };
        this.publications.set(stream, record);
        return this.setState(stream, record, m["state"] as string);
      }
      case "unpublish": {
        const stream = m["stream_id"] as string;
        const p = this.publications.get(stream);
        if (m["publisher"] !== sender || (p && p.publisher !== sender)) return void this.emit.push({ drop: "publisher-mismatch" });
        if (!p || p.id !== m["publication"]) return void this.emit.push({ drop: "unknown-publication" });
        return this.setState(stream, p, "withdrawn");
      }
      case "provenance": {
        const stream = m["original_stream"] as string;
        const found = [...this.publications].find(([, p]) => p.id === m["original_publication"]);
        if (!found) return void this.emit.push({ drop: "provenance-unknown-publication" });
        const [recordStream, p] = found;
        if (recordStream !== stream) return void this.emit.push({ drop: "provenance-stream-mismatch" });
        if (m["processor"] !== sender) return void this.emit.push({ drop: "provenance-processor-mismatch" });
        // §22.3: `input_variant` MUST be one the publication advertises (the output is the processor's own)
        for (const k of ["input_variant"]) {
          if (k in m && !p.variants.includes(m[k] as string)) return void this.emit.push({ drop: "provenance-variant-unknown" });
        }
        // §22.3: the statement is attached; the publisher stays the publisher
        p.provenance.push(sender);
        this.emit.push({ provenance: { stream, processor: sender } });
        return this.notifyAll(stream, "publication");
      }
      case "subscribe":
        return this.subscribe(m, sender);
      case "presence":
        return this.presence(m);
      case "grant-revocation":
        return this.grantRevocation(m);
      default:
        throw new Error(`authority cannot receive ${String(m["type"])}`);
    }
  }

  /**
   * P§6 rule 2: the first `dsip-grant` claim that admits, in `claims` order. Spec: P§6, §9.3, §12.9 — it verifies,
   * its signer acts for the target, it is to the subscriber's identity, its scope includes `dsip.subscribe`, its
   * `valid_until` is after now, and the target has not revoked it (P§7). Its delivery expiry is not applied.
   */
  private admittingGrant(m: JsonObject, subscriber: string, target: string): JsonObject | undefined {
    const claims = Array.isArray(m["claims"]) ? (m["claims"] as Json[]) : [];
    for (const c of claims) {
      if (c === null || typeof c !== "object" || Array.isArray(c) || c["type"] !== "dsip-grant") continue;
      const g = c["grant"];
      if (g === null || typeof g !== "object" || Array.isArray(g)) continue;
      const scope = Array.isArray(g["scope"]) ? (g["scope"] as Json[]) : [];
      if (
        g["verified"] !== false &&
        g["identity"] === target &&
        g["to"] === subscriber &&
        scope.includes("dsip.subscribe") &&
        typeof g["valid_until"] === "number" && g["valid_until"] > this.now &&
        !this.revoked.has(`${target}\n${String(g["id"])}`)
      ) return g;
    }
    return undefined;
  }

  /**
   * Admission. Spec: §9.3 — a target never seen and an unauthorized subscriber get the identical reject. For
   * `presence`, P§6 — the first that applies: (1) the subject's own devices (every audience), (2) a presented
   * grant (its `presence_audience`), (3) a capability issued for the target, (4) the authority's policy (its
   * audience); with no policy, only (1)–(3) admit. A `subscribe` naming only `publication` keeps the publication
   * rules: a policy (public or allow) or a capability, under a policy.
   * Spec: §9.3 (spec-gap 149 (a)) — a target is "seen" when a policy or an issued capability names it, a device of it
   * has bound here, or it is an identity of `context.identities` (the identities the authority knows its devices by);
   * a publication target must also be published.
   * Impl: a `subscribe` naming `presence` together with other events is admitted by the presence rules.
   */
  private admit(m: JsonObject, subscriber: string, target: string, events: string[]):
    Pick<Subscription, "own" | "grant" | "audience"> | undefined {
    const policy = this.policy.get(target);
    const capability = this.capabilities.get(m["capability"] as string) === target;
    const known = policy !== undefined || this.seen.has(target) || Object.values(this.ctx.identities ?? {}).includes(target)
      || [...this.capabilities.values()].includes(target);
    if (!known || (events.includes("publication") && !this.publications.has(target))) return undefined;
    const byPolicy = policy !== undefined && (policy.mode === "public" || policy.allow.includes(subscriber));
    if (!events.includes("presence")) return policy !== undefined && (byPolicy || capability) ? {} : undefined;
    if (subscriber === target) return { own: true };
    const g = this.admittingGrant(m, subscriber, target);
    if (g) {
      return {
        grant: { id: g["id"] as string, valid_until: g["valid_until"] as number },
        ...(typeof g["presence_audience"] === "string" ? { audience: g["presence_audience"] } : {}),
      };
    }
    if (capability) return {};
    if (byPolicy) return policy.audience !== undefined ? { audience: policy.audience } : {};
    return undefined;
  }

  private subscribe(m: JsonObject, subscriber: string): void {
    const target = m["target"] as string;
    const events = m["events"] as string[];
    // §9.3 (spec-gap 177): a subscription is the subscribing device's; renewal and termination match its device
    const same = (s: Subscription): boolean =>
      s.device === m["from"] && s.target === target && JSON.stringify(s.events) === JSON.stringify(events);
    const prior = this.subscriptions.find(same);
    if (m["expires_in"] === 0) {
      // §9.3: `expires_in: 0` terminates a matching subscription
      if (!prior) return void this.emit.push({ drop: "no-matching-subscription" });
      this.subscriptions = this.subscriptions.filter((s) => s !== prior);
      return void this.emit.push({ subscription: { id: prior.id, state: "terminated" } });
    }
    const admitted = this.admit(m, subscriber, target, events);
    if (!admitted) {
      // §9.3 anti-enumeration: unauthorized and nonexistent get the identical response. A refused renewal leaves
      // the earlier subscription as it was.
      return void this.emit.push({ send: { type: "reject", to: m["from"]!, session: m["id"]!, reason: "policy.blocked" } });
    }
    if (prior) {
      // §9.3: a fresh subscribe from the same device for the same target+events replaces the prior subscription
      this.subscriptions = this.subscriptions.filter((s) => s !== prior);
      this.emit.push({ subscription: { id: prior.id, state: "replaced" } });
    }
    const s: Subscription = {
      id: m["id"] as string, device: m["from"] as string, subscriber, target, events, seq: 0,
      expires_at: this.now + (m["expires_in"] as number), ...admitted,
      ...(Array.isArray(m["profiles"]) && m["profiles"].includes("presence/0.2") ? { sealed: true } : {}),
    };
    this.subscriptions.push(s);
    // §9.3: the first notify carries current state
    for (const event of events) this.notify(s, event);
  }
}

interface Held {
  target: string;
  state: "pending" | "active" | "rejected" | "terminated" | "lapsed";
  seq: number;
  expires_at: number;
}

/** The subscribing side. */
export class Subscriber {
  private now: number;
  private emit: Json[] = [];
  private readonly held = new Map<string, Held>();

  constructor(ctx: BroadcastContext) {
    this.now = ctx.start;
  }

  /** Apply one trace event; returns the ordered emissions. */
  step(e: JsonObject): Json[] {
    this.emit = [];
    if ("advance" in e) {
      this.now += e["advance"] as number;
      for (const [id, s] of this.held) {
        // §9.3: soft state — not renewed means lapsed, without waiting to be told
        if ((s.state === "active" || s.state === "pending") && s.expires_at <= this.now) {
          s.state = "lapsed";
          this.emit.push({ ui: "subscription_lapsed", subscription: id });
        }
      }
    } else if (e["local"] === "subscribe") {
      const { id, to, target, events, expires_in } = e;
      this.held.set(id as string, { target: target as string, state: "pending", seq: 0, expires_at: this.now + (expires_in as number) });
      this.emit.push({ send: { type: "subscribe", to: to!, id: id!, target: target!, events: events!, expires_in: expires_in! } });
    } else {
      this.recv(e["recv"] as JsonObject);
    }
    return this.emit;
  }

  /** The snapshot members a step's `expect` names, in full. */
  snapshot(expect: JsonObject): JsonObject {
    if (!("subscriptions" in expect)) return {};
    return {
      subscriptions: Object.fromEntries([...this.held].map(([id, s]) => [id, { target: s.target, state: s.state, seq: s.seq }])),
    };
  }

  private recv(m: JsonObject): void {
    if (m["type"] === "reject") {
      const s = this.held.get(m["session"] as string);
      if (!s) return void this.emit.push({ drop: "unknown-subscription" });
      s.state = "rejected";
      return void this.emit.push({ ui: "subscription_rejected", reason: m["reason"]! });
    }
    const s = this.held.get(m["subscription"] as string);
    if (!s) return void this.emit.push({ drop: "unknown-subscription" });
    // §9.3: a terminated notify is final
    if (s.state === "terminated") return void this.emit.push({ drop: "terminated-subscription" });
    const seq = m["seq"] as number;
    if (seq <= s.seq) return void this.emit.push({ drop: "stale-seq" });
    s.seq = seq;
    if (m["state"] === "terminated") {
      s.state = "terminated";
      return void this.emit.push({ ui: "subscription_terminated", reason: m["reason"] ?? null });
    }
    s.state = "active";
    const body = m["body"] as JsonObject;
    this.emit.push({ ui: "notify", event: body["event"]!, state: body["state"]! });
  }
}
