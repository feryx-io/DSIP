#!/usr/bin/env python3
"""
DSIP JSON Schema generator.

Generates the DSIP Core v1.0 message schema set (draft 2020-12) from one
source of truth. Errata since the v0.8 snapshot: the `sealed-body/1.0` extension (10.4, spec-gap 97) adds an optional
`sealed` body to invite, answer, update, info, reject, cancel and bye. Spec revision v0.8 (Appendix A.5) adds the optional `sealed` introduction body
(19.4, Messaging Profile M§14.1), the `delegation-revocation` message (7.4) and the `dsip.message`
grant scope. Spec revision v0.7 added `provenance` (22.3), `key-rotation`
(7.5), `reachability-hint` (DHT Hints Profile), the record-level `integrity`
field on `publish` (22.2), and the WebRTC Media Binding's `info.data` schema
(`webrtc-info-data` and `dtmf-info-data`, validated when `info.about` is `transport:webrtc` or `media:dtmf`). Shared definitions are embedded into every schema file so
each file validates standalone in any conforming validator, with no $ref
resolution setup required.

Usage: python3 generate_schemas.py <output_dir>
v0.14 adds `alias-monitor` (Alias Transparency Profile T§8, spec-gap 124).
v0.17 adds `presence` (core 9.4 with the Presence Profile P§3-P§5, spec-gaps 134-136), and sealed presence records
(`kid`, `sealed_state`) with a grant's `presence_keys` (P§12, spec-gaps 152-157).
"""
import json
import sys
import copy
from pathlib import Path

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
NS = "https://dsip.org/schema/1.0/"  # placeholder; final $id base pends registry governance (spec section 24)

# ---------------------------------------------------------------- shared defs

COMMON_DEFS = {
    "ulid": {
        "type": "string",
        "pattern": "^[0-7][0-9A-HJKMNP-TV-Z]{25}$",
        "description": "ULID (Crockford base32, 26 chars). Note: illustrative ids in spec prose (e.g. 01HZINVITEABC) are NOT valid ULIDs; conformant messages and test vectors use real ULIDs.",
    },
    "did": {
        "type": "string",
        "pattern": "^did:[a-z0-9]+:[A-Za-z0-9.%_:-]+$",
        "description": "Decentralized Identifier (DID Core syntax, method-specific validation out of scope here).",
    },
    "timestamp": {
        "type": "integer",
        "minimum": 0,
        "description": "Integer Unix timestamp, seconds (payload rules, spec 11.3: no floating point).",
    },
    "versionToken": {"type": "string", "pattern": "^\\d+\\.\\d+$"},
    "profileId": {
        "type": "string",
        "pattern": "^[a-z][a-z0-9-]*/\\d+\\.\\d+$",
        "description": "Registered profile or extension identifier with version, e.g. interactive-media/1.0",
    },
    "versionBlock": {
        "type": "object",
        "properties": {
            "core": {"$ref": "#/$defs/versionToken"},
            "min_core": {"$ref": "#/$defs/versionToken"},
            "profiles": {"type": "array", "items": {"$ref": "#/$defs/profileId"}},
            "extensions": {"type": "array", "items": {"$ref": "#/$defs/profileId"}},
            "critical": {"type": "array", "items": {"$ref": "#/$defs/profileId"}},
        },
        "required": ["core", "min_core", "profiles", "extensions", "critical"],
        "additionalProperties": False,
    },
    "reasonToken": {
        "type": "string",
        "pattern": "^[a-z][a-z0-9-]*\\.[a-z][a-z0-9-]*$",
        "description": "Namespaced reason token, category.condition (spec 13C). Registry membership is a semantic check, not a schema check; unknown conditions fall back per category.",
    },
    "codecId": {
        "type": "string",
        "pattern": "^codec:(audio|video|text|application)/[a-z0-9.+-]+$",
    },
    "codec": {
        "type": "object",
        "properties": {"id": {"$ref": "#/$defs/codecId"}},
        "required": ["id"],
        "additionalProperties": True,
        "description": "Codec descriptor. Normative form is an object with registered id plus codec-specific parameters (resolves the 14.2/15.3 draft inconsistency in favor of 14.2 objects).",
    },
    "transportId": {"type": "string", "pattern": "^transport:[a-z0-9-]+$"},
    "transportDescriptor": {
        "type": "object",
        "properties": {"id": {"$ref": "#/$defs/transportId"}},
        "required": ["id"],
        "additionalProperties": True,
    },
    "mediaDescriptor": {
        "type": "object",
        "properties": {
            "type": {"enum": ["audio", "video", "text", "application"]},
            "purpose": {
                "type": "string",
                "pattern": "^[a-z][a-z0-9-]*$",
                "description": "Registered media purpose, e.g. sign-language, caption (spec 20).",
            },
            "direction": {"enum": ["sendrecv", "sendonly", "recvonly", "inactive"]},
            "codecs": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/codec"}},
        },
        "required": ["type", "direction", "codecs"],
        "additionalProperties": True,
    },
    "policy": {
        "type": "object",
        "propertyNames": {"pattern": "^[a-z][a-z0-9_]*$"},
        "additionalProperties": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
        "description": "Registered policy keys to registered policy values (spec 14.4). Registry membership is a semantic check.",
    },
    "recording": {
        "type": "object",
        "properties": {
            "state": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$",
                      "description": "Registered (dsip-recording-state): on, paused, off. Membership is a semantic check."},
            "recorder": {"$ref": "#/$defs/did", "description": "The recorder's identity (Recording Profile C§3, C§6); a claim, rendered."},
            "purpose": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$",
                        "description": "Registered (dsip-recording-purpose): compliance, quality, personal; open."},
        },
        "required": ["state"],
        "additionalProperties": False,
        "if": {"properties": {"state": {"not": {"const": "off"}}}},
        "then": {"required": ["state", "recorder"]},
        "description": "The sender's recording declaration (Recording Profile C§3, draft): shaped like SIPREC a=record.",
    },
    "recordingSession": {
        "type": "object",
        "properties": {
            "of": {"$ref": "#/$defs/ulid", "description": "The recorded session's id."},
            "participants": {"type": "array", "minItems": 1, "items": {
                "type": "object",
                "properties": {"identity": {"$ref": "#/$defs/did"},
                               "role": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$", "description": "self or peer."}},
                "required": ["identity", "role"], "additionalProperties": False}},
            "streams": {"type": "array", "minItems": 1, "items": {
                "type": "object",
                "properties": {"media": {"type": "integer", "minimum": 0}, "participant": {"$ref": "#/$defs/did"}},
                "required": ["media", "participant"], "additionalProperties": False}},
        },
        "required": ["of", "participants", "streams"],
        "additionalProperties": False,
        "description": "Metadata of a recording session (Recording Profile C§6, draft): shaped like RFC 7865.",
    },
    "identityInfo": {
        "type": "object",
        "properties": {
            "display_name": {"type": "string", "maxLength": 256},
            "claims": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": False,
        "description": "Unverified-by-default identity presentation; claims carry VC presentations (spec 17). Display fields are claims, not truth.",
    },
}

def base(msg_type, *, session_scoped, has_to=True, extra_props=None,
         extra_required=None, description="", no_additional=True):
    props = {
        "dsip": {"$ref": "#/$defs/versionBlock"},
        "type": {"const": msg_type},
        "id": {"$ref": "#/$defs/ulid"},
        "from": {"$ref": "#/$defs/did"},
        "issued_at": {"$ref": "#/$defs/timestamp"},
        "expires_at": {"$ref": "#/$defs/timestamp"},
    }
    required = ["dsip", "type", "id", "from", "issued_at", "expires_at"]
    if has_to:
        props["to"] = {"$ref": "#/$defs/did"}
        required.append("to")
    if session_scoped:
        props["session"] = {"$ref": "#/$defs/ulid"}
        required.append("session")
    if extra_props:
        props.update(extra_props)
    if extra_required:
        required.extend(extra_required)
    schema = {
        "$schema": SCHEMA_DIALECT,
        "$id": f"{NS}{msg_type}.schema.json",
        "title": f"DSIP {msg_type} payload",
        "description": description,
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": not no_additional,
        "$defs": copy.deepcopy(COMMON_DEFS),
    }
    return schema

REASON_FIELDS = {
    "reason": {"$ref": "#/$defs/reasonToken"},
    "detail": {
        "anyOf": [{"type": "string", "maxLength": 1024}, {"type": "object", "maxProperties": 16}],
        "description": "Free-text elaboration, or an object the profile registering the reason defines (Gateway Profile G\u00a77: {losses: [...]} on gateway.downgraded; spec-gap 112). A claim by the signer; clients must not render as independently verified (spec 13C.3.2).",
    },
    "retry_after": {"type": "integer", "minimum": 0},
}

# ---------------------------------------------------------------- messages

schemas = {}

schemas["invite"] = base(
    "invite", session_scoped=False,
    description="Start an interactive session. MUST carry a media offer and at least one transport; offerless invites are rejected with media.offer-required (spec 13C.2.2).",
    extra_props={
        "intent": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
        "grant": {"$ref": "#/$defs/ulid",
                  "description": "Optional id of a contact grant (spec 19.4) authorizing this invite, to aid stateless relays."},
        "identity": {"$ref": "#/$defs/identityInfo"},
        "media": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/mediaDescriptor"}},
        "transports": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/transportDescriptor"}},
        "policy": {"$ref": "#/$defs/policy"},
        "recording": {"$ref": "#/$defs/recording"},
        "recording_session": {"$ref": "#/$defs/recordingSession"},
        "destination": {"type": "string", "pattern": "^tel:\\+[1-9][0-9]{1,14}$",
                        "description": "v0.11 (Number Attestation Profile draft, N\u00a74.1): the PSTN number a caller asks a gateway to reach, a tel URI (E.164). Meaningful only when `to` is a gateway; any other callee ignores it (spec-gap 111)."},
    },
    extra_required=["media", "transports"],
)

schemas["progress"] = base(
    "progress", session_scoped=True,
    description="Pre-answer handling status. queued REQUIRES queue_timeout (spec 13A.6.1). Commits no media.",
    extra_props={
        "status": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9-]*$",
            "description": "Registered: trying, ringing, queued, forwarded. Unknown values are treated as trying by receivers.",
        },
        "ring_timeout": {"type": "integer", "minimum": 30, "maximum": 300},
        "queue_timeout": {"type": "integer", "minimum": 1, "maximum": 1800},
    },
    extra_required=["status"],
)
schemas["progress"]["if"] = {"properties": {"status": {"const": "queued"}}}
schemas["progress"]["then"] = {"required": ["queue_timeout"]}

schemas["answer"] = base(
    "answer", session_scoped=True,
    description="Commit to the negotiated session. Means a verified delegated endpoint commits to media, NOT that a human accepted; answered_by distinguishes (spec 13C.2). Valid for initial establishment and for update renegotiation responses.",
    extra_props={
        "answered_by": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9-]*$",
            "description": "Registered: user, service, screening, gateway. Unknown values render as service.",
        },
        "media": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/mediaDescriptor"}},
        "transports": {"type": "array", "minItems": 1, "maxItems": 1, "items": {"$ref": "#/$defs/transportDescriptor"}},
        "policy": {"$ref": "#/$defs/policy"},
        "recording": {"$ref": "#/$defs/recording"},
        "in_reply_to": {"$ref": "#/$defs/ulid", "description": "id of the update being answered, when responding to renegotiation (spec 13A.4.8). Absent on initial answer."},
    },
    extra_required=["answered_by", "media", "transports"],
)

schemas["reject"] = base(
    "reject", session_scoped=True,
    description="Decline a session or an update. reason is a namespaced token from the unified registry (spec 13C).",
    extra_props={**copy.deepcopy(REASON_FIELDS),
                 "in_reply_to": {"$ref": "#/$defs/ulid", "description": "id of the update being rejected, when rejecting renegotiation. Absent when rejecting the invite itself."}},
    extra_required=["reason"],
)

schemas["cancel"] = base(
    "cancel", session_scoped=True,
    description="Withdraw an invite before answer. Only valid pre-ACTIVE; must be signed by the inviting identity or its delegate (spec 13A.6.2).",
    extra_props=copy.deepcopy(REASON_FIELDS),
    extra_required=["reason"],
)

schemas["update"] = base(
    "update", session_scoped=True,
    description="Renegotiate an established session. Always carries a media offer from its sender; one outstanding per session across both directions (spec 13A.4.8).",
    extra_props={
        "media": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/mediaDescriptor"}},
        "transports": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/transportDescriptor"}},
        "answered_by": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$",
                        "description": "Optional on update: signals role transition, e.g. screening -> user escalation (spec 13C.2.4)."},
        "policy": {"$ref": "#/$defs/policy"},
        "recording": {"$ref": "#/$defs/recording"},
    },
    extra_required=["media"],
)

schemas["bye"] = base(
    "bye", session_scoped=True,
    description="End an established session. reason from the unified registry; normal hangup is user.hangup.",
    extra_props=copy.deepcopy(REASON_FIELDS),
    extra_required=["reason"],
)

schemas["error"] = base(
    "error", session_scoped=False,
    description="Protocol/policy failure report. session present only when the error is session-scoped; transport-scoped errors (transport.*) omit it.",
    extra_props={
        **copy.deepcopy(REASON_FIELDS),
        "session": {"$ref": "#/$defs/ulid"},
        "in_reply_to": {"$ref": "#/$defs/ulid", "description": "id of the envelope that provoked the error, when known."},
    },
    extra_required=["reason"],
)

schemas["hello"] = base(
    "hello", session_scoped=False, has_to=False,
    description="Transport connection binding (spec 13B.2.4). Client form: bindings required. Relay form: in_reply_to + capabilities required (mutually entailed).",
    extra_props={
        "on_behalf_of": {"$ref": "#/$defs/did"},
        "bindings": {"type": "array", "minItems": 1,
                     "items": {"type": "string", "pattern": "^[a-z0-9]+/\\d+\\.\\d+$"}},
        "in_reply_to": {"$ref": "#/$defs/ulid"},
        "capabilities": {
            "type": "object",
            "properties": {
                "max_envelope_bytes": {"const": 65536,
                                       "description": "Fixed binding constant of ws/1.0."},
                "store_and_forward": {"type": "boolean"},
                "offline_retention_s": {"type": "integer", "minimum": 0},
                "rate_limit": {
                    "type": "object",
                    "properties": {
                        "envelopes_per_minute": {"type": "integer", "minimum": 1},
                        "invites_per_minute": {"type": "integer", "minimum": 1},
                    },
                    "additionalProperties": True,
                },
                "push_wake": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["max_envelope_bytes"],
            "additionalProperties": True,
        },
    },
)
schemas["hello"]["allOf"] = [
    {"if": {"required": ["in_reply_to"]}, "then": {"required": ["capabilities"]}},
    {"if": {"required": ["capabilities"]}, "then": {"required": ["in_reply_to"]}},
    {"if": {"not": {"required": ["in_reply_to"]}}, "then": {"required": ["bindings"]}},
]

# Broadcast profile. publish follows spec 16.1; subscribe/notify/unpublish are
# PROVISIONAL pending the broadcast profile's own subscription protocol section.
schemas["publish"] = base(
    "publish", session_scoped=False, has_to=False,
    description="Signed broadcast publication record (spec 16.1).",
    extra_props={
        "publisher": {"$ref": "#/$defs/did"},
        "stream_id": {"type": "string", "minLength": 1},
        "title": {"type": "string", "maxLength": 512},
        "state": {"enum": ["live", "scheduled", "ended"]},
        "variants": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "media": {"type": "array", "minItems": 1,
                              "items": {"enum": ["audio", "video", "text"]}},
                    "codec": {"$ref": "#/$defs/codecId"},
                    "transport": {"$ref": "#/$defs/transportId"},
                    "uri": {"type": "string", "format": "uri"},
                },
                "required": ["id", "media", "codec", "transport", "uri"],
                "additionalProperties": True,
            },
        },
        "integrity": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$",
                      "description": "Integrity mode the publisher commits to for this record (registry dsip-integrity-mode: metadata-only, derivative-bound; spec 22.2). Absent = metadata-only. A variant MAY carry its own integrity to override the record-level value."},
        "policy": {"$ref": "#/$defs/policy"},
    },
    extra_required=["publisher", "stream_id", "state", "variants"],
)

schemas["provenance"] = base(
    "provenance", session_scoped=False, has_to=False,
    description="Provenance statement by a relay or transcoder referencing the original publication it processed (spec 22.3). Signed by the processor; it never replaces the publisher's record. Receivers verify it against the publication it names.",
    extra_props={
        "original_stream": {"type": "string", "minLength": 1},
        "original_publication": {"$ref": "#/$defs/ulid"},
        "processor": {"$ref": "#/$defs/did"},
        "operation": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$",
                      "description": "Registry dsip-provenance-operation: transcode, relay, repackage."},
        "input_variant": {"type": "string", "minLength": 1},
        "output_variant": {"type": "string", "minLength": 1},
        "output_uri": {"type": "string", "format": "uri"},
    },
    extra_required=["original_stream", "original_publication", "processor", "operation", "input_variant", "output_variant"],
)

schemas["delegation-revocation"] = base(
    "delegation-revocation", session_scoped=False, has_to=False,
    description="Delegation revocation record (spec 7.4, v0.8): revokes every delegation of one device for the subject issued at or before revoked_at. Signed directly by a verification key of the subject; from equals subject (semantic check). Verifiers find it in the subject's DID document (dsipDelegationRevocations) or in any store they hold; it can only remove authority.",
    extra_props={
        "subject": {"$ref": "#/$defs/did"},
        "device": {"$ref": "#/$defs/did"},
        "revoked_at": {"$ref": "#/$defs/timestamp",
                       "description": "Delegations of device issued at or before this instant are revoked; a later delegation re-enrolls it."},
        "reason": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$",
                   "description": "Registry dsip-revocation-reason: lost, compromised, retired, policy."},
    },
    extra_required=["subject", "device", "revoked_at", "reason"],
)

schemas["key-rotation"] = base(
    "key-rotation", session_scoped=False, has_to=False,
    description="Key rotation record (spec 7.5): the artifact an identity publishes when a verification key changes. Signed by the key being retired, or by a recovery key of the subject when that key is lost (recovery: true). The DID document stays authoritative for verification (spec 8.1); this record is what transparency logs (7.7) keep and clients show as trust metadata.",
    extra_props={
        "subject": {"$ref": "#/$defs/did"},
        "previous": {"type": "string", "pattern": "^did:[a-z0-9]+:[A-Za-z0-9.%_:-]+#[A-Za-z0-9._-]+$",
                     "description": "Verification method id being retired."},
        "next": {"type": "string", "pattern": "^did:[a-z0-9]+:[A-Za-z0-9.%_:-]+#[A-Za-z0-9._-]+$",
                 "description": "Verification method id that replaces it."},
        "next_public_key_multibase": {"type": "string", "pattern": "^z[1-9A-HJ-NP-Za-km-z]+$",
                                      "description": "Public key of next, so the record is self-contained for logs and caches."},
        "reason": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$",
                   "description": "Registry dsip-rotation-reason: scheduled, compromised, lost, policy."},
        "recovery": {"type": "boolean",
                     "description": "True when the record is signed by a recovery key rather than by previous."},
        "devices": {"type": "array", "items": {"$ref": "#/$defs/did"},
                    "description": "Device DIDs whose delegations are re-issued under next (the device-list update of 7.5)."},
    },
    extra_required=["subject", "previous", "next", "next_public_key_multibase", "reason"],
)

schemas["reachability-hint"] = base(
    "reachability-hint", session_scoped=False, has_to=False,
    description="Signed, expiring reachability hint distributed through the DHT hints tier (DHT Hints Profile; spec 8.3, 8.5). Never authoritative: verified against the subject DID or a delegation before use; higher seq wins; expired records are invalid.",
    extra_props={
        "subject": {"$ref": "#/$defs/did"},
        "endpoints": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "uri": {"type": "string", "pattern": "^wss://"},
                    "bindings": {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^[a-z0-9]+/\\d+\\.\\d+$"}},
                    "service": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9]*$",
                                "description": "v0.8: the DID service type this endpoint stands in for (DSIPSignaling when absent; DSIPMailbox for a Messaging Profile mailbox)."},
                },
                "required": ["uri", "bindings"],
                "additionalProperties": True,
            },
        },
        "seq": {"type": "integer", "minimum": 0},
        "key_agreement": {"type": "object",
                          "properties": {k: {"type": "string"} for k in ("protected", "payload", "signature")},
                          "required": ["protected", "payload", "signature"], "additionalProperties": False,
                          "description": "1.x, spec-gap 179: the subject's current key agreement delegation (spec 7.3), an envelope object as the delegations header carries them; verified against the subject, and a hint whose member does not verify is refused."},
    },
    extra_required=["subject", "endpoints", "seq"],
)

schemas["alias-monitor"] = base(
    "alias-monitor", session_scoped=False,
    description="Authorizes an alias owner's KEYTRANS monitor request at the alias provider's log endpoint (Alias Transparency Profile T§8, v0.14); carried over HTTPS as Authorization: DSIP beside the raw request. `to` is the provider; `from` must be an identity that is or was the alias's value.",
    extra_props={
        "alias": {"type": "string", "minLength": 1, "maxLength": 255,
                  "description": "The alias, normalized by the provider before its checks (T§3)."},
    },
    extra_required=["alias"],
)

schemas["presence"] = base(
    "presence", session_scoped=False,
    description="A device's signed presence record (spec 9.4), published to its authority and carried in notify bodies (Presence Profile P3, v0.17). device, when present, must equal from (semantic check); its age is bounded by expires_at, capped at 3600 s (spec 12.9). state is from the open registry dsip-presence-state: unknown tokens are accepted and shown as available (P5). A sealed record (presence/0.2, P12) carries kid and sealed_state in place of state.",
    extra_props={
        "subject": {"$ref": "#/$defs/did", "description": "The identity whose presence this is."},
        "device": {"$ref": "#/$defs/did", "description": "The device the record describes; the signer (P4). Absent in a v0.16-form record."},
        "state": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$", "maxLength": 64,
                  "description": "dsip-presence-state token (P5): available, busy, away, dnd, offline; open."},
        "seq": {"type": "integer", "minimum": 0, "description": "Ordered per (subject, device) (P4)."},
        "audience": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$", "maxLength": 64,
                     "description": "The audience this record is for, a token the subject chooses (P6, spec-gap 145); absent: every admitted subscriber."},
        "kid": {"type": "string", "pattern": "^(main|[a-z][a-z0-9-]*)\\.(0|[1-9][0-9]*)$", "maxLength": 86,
                "description": "A sealed record's key: scope (main, or the audience tag) . epoch (P12.1; spec-gaps 152, 157). Its scope matches audience (semantic check)."},
        "sealed_state": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$", "minLength": 1,
                         "description": "base64url nonce || AES-256-GCM ciphertext || tag of {\"state\": S} padded to 128 bytes (P12.2)."},
        "profiles": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "endpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"transport": {"type": "string"}, "uri": {"type": "string"}},
                "required": ["uri"],
                "additionalProperties": True,
            },
        },
    },
    extra_required=["subject", "seq"],
)
# P12.2: a record carries state in clear, or kid and sealed_state, never both
schemas["presence"]["oneOf"] = [
    {"required": ["state"], "not": {"anyOf": [{"required": ["sealed_state"]}, {"required": ["kid"]}]}},
    {"required": ["kid", "sealed_state"], "not": {"required": ["state"]}},
]

schemas["subscribe"] = base(
    "subscribe", session_scoped=False,
    description="Soft-state subscription to presence or publication events (spec 9.3). expires_in 0 terminates; renewal is a fresh subscribe. Per-event lifetime caps (presence 3600, publication 86400) are semantic checks.",
    extra_props={
        "target": {"type": "string", "minLength": 1,
                   "description": "Subject DID or stream_id being subscribed to. to= the authority answering for it."},
        "events": {"type": "array", "minItems": 1,
                   "items": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
                   "description": "Registered event classes (dsip-subscription-event): presence, publication."},
        "expires_in": {"type": "integer", "minimum": 0, "maximum": 86400},
        "claims": {"type": "array", "items": {"type": "object"},
                   "description": "Optional authorization evidence: VC presentations, or {type: dsip-grant, grant: <signed grant envelope>} presenting a grant from the target with dsip.subscribe (spec 9.3, P6; v0.17, spec-gap 144)."},
        "capability": {"type": "string", "maxLength": 2048,
                       "description": "Optional opaque authorization token previously issued by the target authority."},
    },
    extra_required=["target", "events", "expires_in"],
)

schemas["notify"] = base(
    "notify", session_scoped=False,
    description="Subscription update (spec 9.3). First notify carries current state; state=terminated is final and SHOULD carry reason. seq orders notifies within a subscription.",
    extra_props={
        "subscription": {"$ref": "#/$defs/ulid",
                         "description": "id of the subscribe this notify serves."},
        "seq": {"type": "integer", "minimum": 1},
        "state": {"enum": ["active", "terminated"]},
        "reason": {"$ref": "#/$defs/reasonToken"},
        "body": {"type": "object",
                 "description": "Event record; MAY be a full signed envelope for third-party verifiability (RECOMMENDED when notifier is not the subject)."},
    },
    extra_required=["subscription", "seq", "state", "body"],
)

schemas["unpublish"] = base(
    "unpublish", session_scoped=False, has_to=False,
    description="Withdraw a publication.",
    extra_props={
        "publisher": {"$ref": "#/$defs/did"},
        "stream_id": {"type": "string", "minLength": 1},
        "publication": {"$ref": "#/$defs/ulid",
                        "description": "id of the publish being withdrawn."},
    },
    extra_required=["publisher", "stream_id", "publication"],
)


schemas["info"] = base(
    "info", session_scoped=True,
    description="Transport-binding data within an established session, e.g. trickle ICE candidates (spec 12.12). ACTIVE-only, never critical, no reply, must not alter negotiated parameters. Unknown about values are ignored silently.",
    extra_props={
        "about": {"type": "string", "pattern": "^[a-z][a-z0-9-]*:[a-z0-9.-]+$",
                  "description": "Registered namespace the data belongs to (dsip-info-about), e.g. transport:webrtc."},
        "data": {"type": "object",
                 "description": "Structure defined by the binding named in about."},
    },
    extra_required=["about", "data"],
)

schemas["introduction"] = base(
    "introduction", session_scoped=False,
    description="First-contact request (spec 19.4): media-less, session-less, encoded envelope capped at 4096 bytes (semantic check), validity up to 7 days. purpose and identity fields are claims. Never rendered as a call.",
    extra_props={
        "identity": {"$ref": "#/$defs/identityInfo"},
        "purpose": {"type": "string", "maxLength": 280,
                    "description": "Short stated purpose; a claim, rendered attributed and unverified."},
        "contact_token": {"type": "string", "maxLength": 2048,
                          "description": "Optional out-of-band token from the recipient authority; valid tokens SHOULD bypass rate limits."},
        "sealed": {
            "type": "object",
            "description": "v0.8: purpose sealed to the recipient's key agreement key with HPKE (spec 19.4; Messaging Profile M§6.9, M§14.1). The plaintext is {\"purpose\": ...}. purpose and sealed never both appear (semantic check).",
            "properties": {
                "alg": {"type": "string", "minLength": 1, "description": "Sealing algorithm; hpke-base-x25519-sha256-aes128gcm in 1.0."},
                "enc": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z0-9_-]+$", "description": "HPKE encapsulated key, base64url."},
                "ct": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z0-9_-]+$", "description": "HPKE ciphertext, base64url."},
            },
            "required": ["alg", "enc", "ct"],
            "additionalProperties": False,
        },
    },
    extra_required=["identity"],
)

schemas["grant"] = base(
    "grant", session_scoped=True,
    description="Signed contact grant answering an introduction (spec 19.4); session references the introduction id, or (v0.17, spec-gap 150) the live grant from the same grantor that this grant replaces. The consent receipt in message form: scoped, time-bounded via valid_until, revocable at the granting side.",
    extra_props={
        "scope": {"type": "array", "minItems": 1,
                  "items": {"type": "string", "pattern": "^dsip\\.[a-z][a-z0-9.-]*$"},
                  "description": "Registered grant scopes (dsip-grant-scope): dsip.invite, dsip.subscribe, dsip.message (v0.8)."},
        "valid_until": {"$ref": "#/$defs/timestamp",
                        "description": "Grant lifetime, independent of the envelope delivery expiry."},
        "presence_audience": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$", "maxLength": 64,
                              "description": "The presence audience a subscriber admitted by this grant sees (P6; v0.17, spec-gap 145)."},
        "presence_keys": {
            "type": "object",
            "description": "The grantor's sealed-presence keys the grantee may read, HPKE-sealed to the grantee identity's key agreement key (P12.3; v0.17, spec-gaps 152, 157). The plaintext is {\"keys\": [{\"kid\", \"key\"}]} padded to a multiple of 256 bytes.",
            "properties": {
                "alg": {"type": "string", "minLength": 1, "description": "Sealing algorithm; hpke-base-x25519-sha256-aes128gcm."},
                "enc": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z0-9_-]+$", "description": "HPKE encapsulated key, base64url."},
                "ct": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z0-9_-]+$", "description": "HPKE ciphertext, base64url."},
            },
            "required": ["alg", "enc", "ct"],
            "additionalProperties": False,
        },
    },
    extra_required=["scope", "valid_until"],
)

schemas["grant-revocation"] = base(
    "grant-revocation", session_scoped=False,
    description="Withdraws a grant before its valid_until (spec 19.4; v0.17, spec-gap 147). Signed by a device of the granting identity and sent to its authority, which keeps it until valid_until; it ends the presence subscriptions the grant admitted (P7) and admits nothing further. Not answered.",
    extra_props={
        "grant": {"$ref": "#/$defs/ulid", "description": "The revoked grant's id."},
        "grantee": {"$ref": "#/$defs/did", "description": "The grant's grantee identity."},
        "valid_until": {"$ref": "#/$defs/timestamp", "description": "The revoked grant's valid_until: how long the authority keeps the revocation."},
    },
    extra_required=["grant", "grantee", "valid_until"],
)

# ---------------------------------------------------------------- envelope & dispatcher

envelope = {
    "$schema": SCHEMA_DIALECT,
    "$id": f"{NS}envelope.schema.json",
    "title": "DSIP-JOSE signed envelope",
    "description": "JWS envelope (spec 11.2). The payload member is the base64url-encoded DSIP JSON payload validated by the per-message schemas.",
    "type": "object",
    "properties": {
        "protected": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$"},
        "payload": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$"},
        "signature": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$"},
    },
    "required": ["protected", "payload", "signature"],
    "additionalProperties": False,
}

# ---------------------------------------------------------------- binding data schemas
# Not message types: `info.data` shapes named by `info.about` (spec 12.12). A receiver validates
# `data` against the schema of a binding it implements and ignores `info` for unknown `about`.

bindings = {
    "dtmf-info-data": {
        "$schema": SCHEMA_DIALECT,
        "$id": f"{NS}binding/dtmf/info-data.schema.json",
        "title": "media:dtmf info.data",
        "description": "DTMF digits within an established session (spec 12.12, spec-gap 70). digits are RFC 4733 events 0-9, *, #, A-D, in the order pressed; duration_ms applies to each digit in this message. Like any info it changes nothing about the negotiated session.",
        "type": "object",
        "properties": {
            "digits": {"type": "string", "pattern": "^[0-9A-D*#]{1,32}$",
                       "description": "One or more DTMF events, in order."},
            "duration_ms": {"type": "integer", "minimum": 40, "maximum": 10000,
                            "description": "Tone length of each digit; RFC 4733 events are at least 40 ms."},
        },
        "required": ["digits"],
        "additionalProperties": False,
    },
    "webrtc-info-data": {
        "$schema": SCHEMA_DIALECT,
        "$id": f"{NS}binding/webrtc/info-data.schema.json",
        "title": "transport:webrtc info.data",
        "description": "WebRTC Media Binding 1.0, Appendix A: trickle ICE candidates carried in signed info envelopes. sdp_mid is required (BUNDLE still needs the mid to disambiguate); end_of_candidates is sent true exactly once per local description.",
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array", "maxItems": 64,
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate": {"type": "string", "pattern": "^candidate:", "maxLength": 512},
                        "sdp_mid": {"type": "string", "maxLength": 64},
                        "sdp_m_line_index": {"type": "integer", "minimum": 0},
                    },
                    "required": ["candidate", "sdp_mid"],
                    "additionalProperties": False,
                },
            },
            "end_of_candidates": {"type": "boolean"},
        },
        "required": ["candidates", "end_of_candidates"],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------- sealed bodies (10.4, extension sealed-body/1.0; spec-gap 97)

# The fields no routing rule reads, per type: they may travel inside `sealed` instead of in clear. Everything
# else — type, id, from, to, session, in_reply_to, timestamps, reason, retry_after, status, grant — stays clear.
SEALABLE = {
    "invite": ["identity", "intent", "policy", "media", "transports"],
    "answer": ["answered_by", "media", "policy", "transports"],
    "update": ["answered_by", "media", "policy", "transports"],
    "info": ["about", "data"],
    "reject": ["detail"],
    "cancel": ["detail"],
    "bye": ["detail"],
}
SEALED_BODY = {
    "type": "object",
    "description": "Extension sealed-body/1.0 (spec 10.4): the type's sealable fields, sealed with HPKE to the addressee identity's X25519 key agreement key. The plaintext is a JSON object of sealable fields only, padded with spaces to a multiple of 256 bytes. A payload with sealed lists sealed-body/1.0 in dsip.extensions and dsip.critical. A sealed field never also appears in clear (receiver check after opening).",
    "properties": {
        "alg": {"type": "string", "minLength": 1, "description": "Sealing algorithm; hpke-base-x25519-sha256-aes128gcm in 1.0."},
        "enc": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z0-9_-]+$", "description": "HPKE encapsulated key, base64url."},
        "ct": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z0-9_-]+$", "description": "HPKE ciphertext, base64url."},
    },
    "required": ["alg", "enc", "ct"],
    "additionalProperties": False,
}
for _t, _fields in SEALABLE.items():
    _s = schemas[_t]
    _s["properties"]["sealed"] = copy.deepcopy(SEALED_BODY)
    _req = [f for f in _s["required"] if f in _fields]
    _s["required"] = [f for f in _s["required"] if f not in _fields]
    if _req:
        # in clear, the type's required fields are required; sealed, they travel inside the seal
        _s["anyOf"] = [{"required": ["sealed"]}, {"required": _req}]

dispatcher = {
    "$schema": SCHEMA_DIALECT,
    "$id": f"{NS}message.schema.json",
    "title": "DSIP payload dispatcher",
    "description": "Validates any DSIP payload by dispatching on type. Relative $refs require a resolver configured with this directory as base; individual schemas are standalone.",
    "oneOf": [
        {"allOf": [
            {"properties": {"type": {"const": t}}, "required": ["type"]},
            {"$ref": f"{t}.schema.json"},
        ]}
        for t in sorted(schemas)
    ],
}

# ---------------------------------------------------------------- credential payloads
# Not message types: the payloads of credentials carried as compact envelopes (spec 7.3).

credentials = {
    "key-agreement-delegation": {
        "$schema": SCHEMA_DIALECT,
        "$id": f"{NS}key-agreement-delegation.schema.json",
        "title": "DSIP KeyAgreementDelegation credential payload",
        "description": "1.x, spec-gap 179 (spec 7.3): an independent X25519 key agreement key named by the identity, signed directly by a verification key of the subject. key is multibase base58btc of multicodec x25519-pub (0xec 0x01) and the 32-byte key, as did:key encodes it. The lifetime cap (issued_at < expires_at <= issued_at + 31,536,000) and the signer are semantic checks.",
        "type": "object",
        "properties": {
            "type": {"const": "KeyAgreementDelegation"},
            "subject": {"$ref": "#/$defs/did"},
            "key": {"type": "string", "pattern": "^z6LS[1-9A-HJ-NP-Za-km-z]{44}$"},
            "issued_at": {"$ref": "#/$defs/timestamp"},
            "expires_at": {"$ref": "#/$defs/timestamp"},
        },
        "required": ["type", "subject", "key", "issued_at", "expires_at"],
        "additionalProperties": False,
        "$defs": {k: COMMON_DEFS[k] for k in ("did", "timestamp")},
    },
}

# ---------------------------------------------------------------- write

def main(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas.items():
        (out / f"{name}.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    (out / "envelope.schema.json").write_text(json.dumps(envelope, indent=2) + "\n")
    (out / "message.schema.json").write_text(json.dumps(dispatcher, indent=2) + "\n")
    for name, schema in {**bindings, **credentials}.items():
        (out / f"{name}.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {len(schemas) + 2 + len(bindings) + len(credentials)} schemas to {out}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "schemas")
