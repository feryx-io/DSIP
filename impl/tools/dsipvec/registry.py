"""DSIP Core v1.0 registries (spec §15.4, §14.3, §12.10, §9.3, §19.4).

Registries govern *membership*; schemas govern *shape*. Unknown-but-well-formed
values never fail here — they resolve to the category/receiver fallback.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

REASON_RE = re.compile(r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*\Z")

CATEGORIES = ("user", "endpoint", "identity", "session", "media", "policy", "transport", "gateway",
              "mailbox",   # v0.8 (spec-gap 38): Messaging Profile mailbox conditions
              "presence")  # v0.17 (spec-gap 134): Presence Profile P§9

# token -> valid-on message types (spec §15.4 "Valid on" column)
REASONS: dict[str, tuple[str, ...]] = {
    "user.declined": ("reject", "bye"),
    "user.no-answer": ("reject",),
    "user.hangup": ("bye",),
    "user.cancelled": ("cancel",),
    "user.blocked": ("reject",),
    "endpoint.busy": ("reject",),
    "endpoint.unavailable": ("reject",),
    "endpoint.capability": ("reject",),
    "identity.not-in-service": ("reject", "error"),
    "identity.moved": ("reject",),
    "identity.suspended": ("reject",),
    "identity.unknown": ("reject", "error"),
    "session.expired": ("reject",),
    "session.timeout": ("cancel", "bye"),
    "session.glare": ("reject", "cancel"),
    "session.answered-elsewhere": ("cancel",),
    "session.already-answered": ("bye",),
    "session.cancelled": ("bye",),
    "session.invalid-state": ("error",),
    "session.unknown-session": ("error",),
    "session.update-pending": ("error",),
    "session.unsupported-core-version": ("reject", "error"),
    "session.unsupported-profile-version": ("reject", "error"),
    "session.unsupported-critical-extension": ("reject", "error"),
    "session.version-downgrade-detected": ("error",),
    "session.unsupported-wire-format": ("error",),
    "session.failed": ("reject", "bye", "error"),
    "media.unsupported": ("reject", "bye"),
    "media.offer-required": ("reject",),
    "media.encryption-required": ("reject",),
    "media.failed": ("bye",),
    "policy.trust-insufficient": ("reject",),
    "policy.first-contact-required": ("reject",),
    "policy.blocked": ("reject", "cancel"),
    "policy.terminated": ("bye",),
    "policy.recording-declined": ("reject", "bye"),      # Recording Profile C§4 (draft)
    "policy.rate-limited": ("reject", "error"),
    "policy.subscription-lifetime": ("error",),          # v0.7 (spec-gap 19): expires_in above the §9.3 cap
    "transport.envelope-too-large": ("error",),
    "transport.hello-required": ("error",),
    "transport.hello-rejected": ("error",),
    "transport.routing-refused": ("error",),
    "transport.unknown-recipient": ("error",),
    "transport.rate-limited": ("error",),
    "transport.no-response": ("error",),  # §12.7 rule 6 (spec-gap 76)
    "transport.replaced": ("error",),  # §13.2: the connection a newer hello replaced (spec-gap 158)
    "gateway.unreachable": ("reject", "bye", "error"),
    "gateway.downgraded": ("error",),
    "gateway.mapped": ("reject", "bye", "error"),
    # v0.8 (spec-gaps 38, 48): the Messaging Profile's mailbox conditions (M§16)
    "mailbox.commit-conflict": ("error",),
    "mailbox.stale-epoch": ("error",),
    "mailbox.unknown-group": ("error",),
    "mailbox.cursor-invalid": ("error",),
    "mailbox.object-too-large": ("error",),
    "mailbox.quota-exceeded": ("error",),
    "mailbox.no-key-packages": ("error",),
    "mailbox.unsupported-class": ("error",),
    "mailbox.unsupported-mode": ("error",),
    "mailbox.blob-mismatch": ("error",),
    "mailbox.hub-unreachable": ("error",),  # v0.8 (spec-gap 72): the mailbox could not reach the group's hub (M§9.4)
    "mailbox.not-served": ("error",),  # v0.16 (spec-gap 130): an owner operation the mailbox will not serve (M§4.1)
    "mailbox.not-enrolled": ("error",),  # v0.16 (spec-gap 130): a release for a configured identity (M§4.1)
    "mailbox.admission-required": ("error",),  # 1.0 (spec-gap 185): no admission code where one is required (M§4.1)
    "mailbox.admission-refused": ("error",),  # 1.0 (spec-gap 185): a code not issued, used up or expired (M§4.1)
    "presence.signer-mismatch": ("error",),  # v0.17 (spec-gap 134): the record's device/subject is not its signer's (P§3)
    "presence.sealed-invalid": ("error",),  # v0.17 (spec-gaps 152, 157): a sealed record without presence/0.2 or a kid for its audience (P§12.2)
    "presence.lifetime": ("error",),  # v0.17 (spec-gap 134): a record's lifetime outside 60–3,600 s (P§8)
    "presence.stale": ("error",),  # v0.17 (spec-gap 134): a record not newer than the one held for its device (P§3)
}

# §15.4 also lists reasons valid on `notify` in prose (§9.3: session.expired,
# policy.terminated on terminated notifies). The registry column does not name
# notify; we accept tokens on notify without the valid-on warning.
REASON_BEARING_TYPES = ("reject", "cancel", "bye", "error")

ANSWERED_BY = ("user", "service", "screening", "gateway")
ANSWERED_BY_FALLBACK = "service"          # §14.3
PROGRESS_STATUS = ("trying", "ringing", "queued", "forwarded")
PROGRESS_STATUS_FALLBACK = "trying"      # §12.10
SUBSCRIPTION_EVENTS = {"presence": 3600, "publication": 86400}  # §9.3 hard caps
GRANT_SCOPES = ("dsip.invite", "dsip.subscribe", "dsip.message")  # §19.4; dsip.message v0.8 (spec-gap 36)
DELEGATION_CAPABILITIES = ("dsip.signaling", "dsip.media.interactive", "dsip.messaging")  # §7.4, v0.8 (spec-gap 39)
REVOCATION_REASONS = ("lost", "compromised", "retired", "policy")  # dsip-revocation-reason (§7.4, v0.8, spec-gap 57)
MESSAGE_TYPES = (
    "invite", "progress", "answer", "reject", "cancel", "update", "info", "bye",
    "introduction", "grant", "publish", "subscribe", "notify", "unpublish", "error", "hello",
    "provenance", "key-rotation", "reachability-hint",   # v0.7: §22.3, §7.5, DHT Hints Profile
    "delegation-revocation",                             # v0.8: §7.4 (spec-gap 57)
    "alias-monitor",                                     # v0.14: Alias Transparency T§8 (spec-gap 124)
    "presence",                                          # v0.17: §9.4 / Presence Profile P§3 (spec-gap 134)
    "grant-revocation",                                  # v0.17: §19.4 / P§7 (spec-gap 147)
)
PRESENCE_STATES = ("available", "busy", "away", "dnd", "offline")  # dsip-presence-state (P§5, v0.17, spec-gap 136)
PRESENCE_STATE_FALLBACK = "available"                              # P§5: never makes a reachable person look unreachable
INTEGRITY_MODES = ("metadata-only", "derivative-bound")   # dsip-integrity-mode (§22.2); unknown → metadata-only
ROTATION_REASONS = ("scheduled", "compromised", "lost", "policy")   # dsip-rotation-reason (§7.5)
PROVENANCE_OPERATIONS = ("transcode", "relay", "repackage")         # dsip-provenance-operation (§22.3)


def effective_integrity(value) -> str:
    """Registry membership with fallback: an unknown or absent mode is the weaker claim, metadata-only."""
    return value if value in INTEGRITY_MODES else "metadata-only"
SESSION_SCOPED = ("progress", "answer", "reject", "cancel", "update", "info", "bye")


@dataclass(frozen=True)
class ReasonResolution:
    token: str
    effective: str
    fallback: str          # none | category | unknown-category
    valid_on_type: bool


def resolve_reason(token: str, msg_type: str) -> ReasonResolution:
    """§15.1 fallback rule. `msg_type` is the carrying message type."""
    category = token.split(".", 1)[0]
    if token in REASONS:
        valid = msg_type not in REASON_BEARING_TYPES or msg_type in REASONS[token]
        return ReasonResolution(token, token, "none", valid)
    if category in CATEGORIES:
        return ReasonResolution(token, token, "category", True)
    return ReasonResolution(token, "session.failed", "unknown-category", True)


def effective_answered_by(v: str) -> str:
    return v if v in ANSWERED_BY else ANSWERED_BY_FALLBACK


def effective_progress_status(v: str) -> str:
    return v if v in PROGRESS_STATUS else PROGRESS_STATUS_FALLBACK
