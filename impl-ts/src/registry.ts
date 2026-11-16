/**
 * Registries with receiver fallback: membership never rejects a well-formed token.
 *
 * Spec: §15.1 (fallback rule), §15.3 (categories), §15.4 (`dsip-reason`), §12.10 (`dsip-progress-status`),
 * §14.3 (`dsip-answered-by`), P§5 (`dsip-presence-state`), P§9 (the `presence` reason category).
 */

/** `dsip-reason`: token → message types it is valid on. Spec: §15.4 */
const REASONS: Record<string, string[]> = {
  "user.declined": ["reject", "bye"],
  "user.no-answer": ["reject"],
  "user.hangup": ["bye"],
  "user.cancelled": ["cancel"],
  "user.blocked": ["reject"],
  "endpoint.busy": ["reject"],
  "endpoint.unavailable": ["reject"],
  "endpoint.capability": ["reject"],
  "identity.not-in-service": ["reject", "error"],
  "identity.moved": ["reject"],
  "identity.suspended": ["reject"],
  "identity.unknown": ["reject", "error"],
  "session.expired": ["reject"],
  "session.timeout": ["cancel", "bye"],
  "session.glare": ["reject", "cancel"],
  "session.answered-elsewhere": ["cancel"],
  "session.already-answered": ["bye"],
  "session.cancelled": ["bye"],
  "session.invalid-state": ["error"],
  "session.unknown-session": ["error"],
  "session.update-pending": ["error"],
  "session.unsupported-core-version": ["reject", "error"],
  "session.unsupported-profile-version": ["reject", "error"],
  "session.unsupported-critical-extension": ["reject", "error"],
  "session.version-downgrade-detected": ["error"],
  "session.unsupported-wire-format": ["error"],
  "session.failed": ["reject", "bye", "error"],
  "media.unsupported": ["reject", "bye"],
  "media.offer-required": ["reject"],
  "media.encryption-required": ["reject"],
  "media.failed": ["bye"],
  "policy.trust-insufficient": ["reject"],
  "policy.first-contact-required": ["reject"],
  "policy.blocked": ["reject", "cancel"],
  "policy.terminated": ["bye"],
  "policy.recording-declined": ["reject", "bye"], // Recording Profile C§4 (draft)
  "policy.rate-limited": ["reject", "error"],
  "policy.subscription-lifetime": ["error"],
  "transport.envelope-too-large": ["error"],
  "transport.hello-required": ["error"],
  "transport.hello-rejected": ["error"],
  "transport.routing-refused": ["error"],
  "transport.unknown-recipient": ["error"],
  "transport.rate-limited": ["error"],
  "transport.no-response": ["error"], // §12.7 rule 6 (spec-gap 76)
  "transport.replaced": ["error"], // §13.2: the connection a newer hello replaced (spec-gap 158)
  "gateway.unreachable": ["reject", "bye", "error"],
  "gateway.downgraded": ["error"],
  "gateway.mapped": ["reject", "bye", "error"],
  "mailbox.commit-conflict": ["error"],
  "mailbox.stale-epoch": ["error"],
  "mailbox.unknown-group": ["error"],
  "mailbox.cursor-invalid": ["error"],
  "mailbox.object-too-large": ["error"],
  "mailbox.quota-exceeded": ["error"],
  "mailbox.no-key-packages": ["error"],
  "mailbox.unsupported-class": ["error"],
  "mailbox.unsupported-mode": ["error"],
  "mailbox.blob-mismatch": ["error"],
  "mailbox.hub-unreachable": ["error"], // M§16 (spec-gap 72); not yet in the core §15.4 table
  "mailbox.not-served": ["error"], // M§16 (v0.16, spec-gap 130): unserved and cannot enrol, or a release from one not served
  "mailbox.not-enrolled": ["error"], // M§16 (v0.16, spec-gap 130): a release for a configured identity
  "mailbox.admission-required": ["error"], // M§16 (1.0, spec-gap 185): no admission code where one is required
  "mailbox.admission-refused": ["error"], // M§16 (1.0, spec-gap 185): a code not issued, used up or expired
  "presence.signer-mismatch": ["error"], // P§9 (v0.17, spec-gap 134); not in the core §15.4 table
  "presence.sealed-invalid": ["error"], // P§9, P§12.2 (v0.17, spec-gaps 152, 157)
  "presence.lifetime": ["error"], // P§9
  "presence.stale": ["error"], // P§9
};

/** Reason categories. Spec: §15.1 token grammar */
const CATEGORIES = ["user", "endpoint", "identity", "session", "media", "policy", "transport", "gateway", "mailbox", "presence"];

/** True when `token` is in the `dsip-reason` registry. Spec: §15.4 */
export function isRegisteredReason(token: string): boolean {
  return token in REASONS;
}

/** How a received reason token is to be read. */
export interface EffectiveReason {
  /** The token whose behavior applies. */
  reason: string;
  /** `none` registered, `category` unregistered condition, `unknown-category` → `session.failed`. */
  fallback: "none" | "category" | "unknown-category";
  /** False for a registered token the registry does not list on the carrying type. */
  validOnType: boolean;
}

/** Spec: §15.1 — unregistered condition falls back to its category; unrecognized category is `session.failed`. */
export function effectiveReason(token: string, messageType: string): EffectiveReason {
  const on = REASONS[token];
  if (on) return { reason: token, fallback: "none", validOnType: on.includes(messageType) };
  const category = token.split(".")[0]!;
  if (CATEGORIES.includes(category)) return { reason: token, fallback: "category", validOnType: true };
  return { reason: "session.failed", fallback: "unknown-category", validOnType: true };
}

/** Spec: §14.3 — unknown `answered_by` values MUST be treated as `service`. */
export function effectiveAnsweredBy(value: string): string {
  return ["user", "service", "screening", "gateway"].includes(value) ? value : "service";
}

/** Spec: §12.10 — unknown `progress.status` values are treated as `trying`. */
export function effectiveStatus(value: string): string {
  return ["trying", "ringing", "queued", "forwarded"].includes(value) ? value : "trying";
}

/** Spec: P§5 — the initial values of `dsip-presence-state`, ranked for P§4 (higher wins). */
export const PRESENCE_STATE_RANK: Readonly<Record<string, number>> = { dnd: 4, busy: 3, available: 2, away: 1, offline: 0 };

/** True when `token` is a registered `dsip-presence-state` value. Spec: P§5 */
export function isRegisteredPresenceState(token: string): boolean {
  return Object.prototype.hasOwnProperty.call(PRESENCE_STATE_RANK, token);
}

/** Spec: P§5 — the registry is open; an unknown state is shown (and ranked) as `available`. */
export function effectivePresenceState(token: string): string {
  return isRegisteredPresenceState(token) ? token : "available";
}
