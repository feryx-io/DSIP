#!/usr/bin/env python3
"""
DSIP Messaging Profile 1.0 JSON Schema generator (draft 2020-12).

Profile schema set for `v1.0/dsip-messaging-profile-v1.0.md` (cited M§n):
the eight profile message payloads (M§5) and the content objects carried inside MLS
application messages (M§8, M§10, M§11, M§12, M§13), plus the `dsip_conversation`
GroupContext extension (M§6.3).

This set is staged beside the frozen v0.7 core set rather than inside it; core-schema
changes the profile implies (e.g. `introduction.sealed`, M§14.1) wait for the v0.8 core
set. Shared definitions are embedded into every file so each validates standalone.

Registry-governed values (deposit class, content kind and purpose, receipt kind, activity,
mailbox mode, conversation kind) are shape-validated here with a token pattern; membership
and fallback are semantic checks, never schema enums.

Usage: python3 generate_schemas.py <output_dir>
"""
import copy
import json
import sys
from pathlib import Path

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
NS = "https://dsip.org/schema/messaging/1.0/"  # placeholder; final $id base pends registry governance (core §24)

DEFS = {
    "ulid": {"type": "string", "pattern": "^[0-7][0-9A-HJKMNP-TV-Z]{25}$"},
    "did": {"type": "string", "pattern": "^did:[a-z0-9]+:[A-Za-z0-9.%_:-]+$"},
    "timestamp": {"type": "integer", "minimum": 0},
    "versionToken": {"type": "string", "pattern": "^\\d+\\.\\d+$"},
    "profileId": {"type": "string", "pattern": "^[a-z][a-z0-9-]*/\\d+\\.\\d+$"},
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
    "b64url": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z0-9_-]+$",
               "description": "Unpadded base64url."},
    "token": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$",
              "description": "Registry token; membership is a semantic check with a stated fallback."},
    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$", "description": "Lowercase hex SHA-256."},
    "cursor": {"type": "string", "minLength": 1, "maxLength": 64, "description": "Opaque mailbox cursor (M§5.4)."},
    "httpsUri": {"type": "string", "pattern": "^https://"},
    "wssUri": {"type": "string", "pattern": "^wss://"},
    "blobRef": {
        "type": "object",
        "properties": {"uri": {"$ref": "#/$defs/httpsUri"}, "sha256": {"$ref": "#/$defs/sha256"},
                       "size": {"type": "integer", "minimum": 1}},
        "required": ["uri", "sha256", "size"],
        "additionalProperties": False,
        "description": "Ciphertext manifest entry (M§5.2, M§8.4): never carries a key.",
    },
    "identityInfo": {
        "type": "object",
        "properties": {"display_name": {"type": "string", "maxLength": 256}, "claims": {"type": "array", "items": {"type": "object"}}},
        "additionalProperties": False,
        "description": "As core §19.4 / §17: unverified-by-default presentation.",
    },
    "hubRef": {
        "type": "object",
        "properties": {"did": {"$ref": "#/$defs/did"}, "uri": {"$ref": "#/$defs/wssUri"}},
        "required": ["did"],
        "additionalProperties": False,
    },
}


def envelope_payload(msg_type, props, required, description):
    base_props = {
        "dsip": {"$ref": "#/$defs/versionBlock"},
        "type": {"const": msg_type},
        "id": {"$ref": "#/$defs/ulid"},
        "from": {"$ref": "#/$defs/did"},
        "to": {"$ref": "#/$defs/did"},
        "issued_at": {"$ref": "#/$defs/timestamp"},
        "expires_at": {"$ref": "#/$defs/timestamp"},
    }
    base_props.update(props)
    return {
        "title": f"DSIP messaging/1.0 {msg_type} payload",
        "description": description,
        "type": "object",
        "properties": base_props,
        "required": ["dsip", "type", "id", "from", "to", "issued_at", "expires_at"] + required,
        "additionalProperties": False,
    }


def content_object(obj, props, required, description, additional=False):
    base_props = {"object": {"const": obj}}
    base_props.update(props)
    return {
        "title": f"DSIP messaging/1.0 {obj} object",
        "description": description,
        "type": "object",
        "properties": base_props,
        "required": ["object"] + required,
        "additionalProperties": additional,
    }


FIRST_CONTACT = {"properties": {"class": {"enum": ["introduction", "grant"]}}, "required": ["class"]}


def group_unless_first_contact(schema, extra_then=None):
    """First-contact items (spec-gap 54) name no group; every other deposit or stored item does."""
    then = {"not": {"required": ["group"]}}
    if extra_then:
        then["required"] = extra_then
    schema["if"] = FIRST_CONTACT
    schema["then"] = then
    schema["else"] = {"required": ["group"]}
    return schema


MESSAGES = {
    "deposit": envelope_payload("deposit", {
        "recipient": {"$ref": "#/$defs/did"},
        "group": {"$ref": "#/$defs/b64url"},
        "class": {"$ref": "#/$defs/token"},
        "seq": {"type": "integer", "minimum": 1},
        "mls": {"$ref": "#/$defs/b64url"},
        "welcome": {"$ref": "#/$defs/b64url"},
        "group_info": {"$ref": "#/$defs/b64url"},
        "ratchet_tree_blob": {"$ref": "#/$defs/blobRef"},
        "sealed": {"$ref": "#/$defs/b64url"},
        "archive": {"$ref": "#/$defs/b64url"},
        "akid": {"$ref": "#/$defs/ulid"},
        "ref_group": {"$ref": "#/$defs/b64url"},
        "ref_seq": {"type": "integer", "minimum": 1},
        "blobs": {"type": "array", "items": {"$ref": "#/$defs/blobRef"}},
        "hub": {"$ref": "#/$defs/hubRef"},
        "grants": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "origin": {"type": "string", "minLength": 1},
        "successor_of": {"$ref": "#/$defs/b64url"},
        "handover_seq": {"type": "integer", "minimum": 1,
                         "description": "On a group-info deposit to a group's new hub: the seq the previous hub gave the commit that "
                                        "moved the group; the new hub continues from the next (M§7.4, spec-gap 60)."},
        "envelope": {"type": "string", "minLength": 1, "description": "A compact signed core envelope (introduction or grant, spec-gap 54)."},
    }, ["class"], "Place one item into a mailbox or submit it to a hub (M§5.2). Class-dependent field rules are semantic (M§5.2 table)."),
    "accepted": envelope_payload("accepted", {
        "in_reply_to": {"$ref": "#/$defs/ulid"},
        "group": {"$ref": "#/$defs/b64url"},
        "seq": {"type": "integer", "minimum": 1},
        "cursor": {"$ref": "#/$defs/cursor"},
        "duplicate": {"type": "boolean"},
    }, ["in_reply_to"], "Signed acknowledgement from a hub or mailbox (M§5.3); the service's claim, not the recipient's."),
    "sync": envelope_payload("sync", {
        "since": {"anyOf": [{"$ref": "#/$defs/cursor"}, {"type": "null"}]},
        "ack_through": {"$ref": "#/$defs/cursor"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
        "live": {"type": "boolean"},
    }, ["since"], "Owner device reads its mailbox (M§5.4)."),
    "items": envelope_payload("items", {
        "in_reply_to": {"$ref": "#/$defs/ulid"},
        "items": {"type": "array", "items": {"oneOf": [
            {
                "description": "A stored item, behind a cursor.",
                "type": "object",
                "properties": {
                    "cursor": {"$ref": "#/$defs/cursor"},
                    "stored_at": {"$ref": "#/$defs/timestamp"},
                    "class": {"$ref": "#/$defs/token", "not": {"const": "ephemeral"}},
                    "source": {"$ref": "#/$defs/did"},
                    "group": {"$ref": "#/$defs/b64url"},
                    "seq": {"type": "integer", "minimum": 1},
                    "mls": {"$ref": "#/$defs/b64url"},
                    "archive": {"$ref": "#/$defs/b64url"},
                    "akid": {"$ref": "#/$defs/ulid"},
                    "hub": {"$ref": "#/$defs/hubRef"},
                    "blobs": {"type": "array", "items": {"$ref": "#/$defs/blobRef"}},
                    "envelope": {"type": "string", "minLength": 1},
                },
                "required": ["cursor", "stored_at", "class"],
                "additionalProperties": False,
                **{k: v for k, v in group_unless_first_contact({}, ["envelope"]).items()},
            },
            {
                "description": "A pushed ephemeral item (M§11.2, spec-gap 49): never stored, so no cursor; "
                               "expires_at is the originating deposit's, carried unchanged by every hop.",
                "type": "object",
                "properties": {
                    "class": {"const": "ephemeral"},
                    "source": {"$ref": "#/$defs/did"},
                    "group": {"$ref": "#/$defs/b64url"},
                    "sealed": {"$ref": "#/$defs/b64url"},
                    "expires_at": {"$ref": "#/$defs/timestamp"},
                },
                "required": ["class", "group", "sealed", "expires_at"],
                "additionalProperties": False,
            },
        ]}},
        "next": {"anyOf": [{"$ref": "#/$defs/cursor"}, {"type": "null"}]},
    }, ["items", "next"], "Stored items delivered to an owner device, as a sync response or a live push (M§5.4)."),
    "key-packages": envelope_payload("key-packages", {
        "in_reply_to": {"$ref": "#/$defs/ulid"},
        "subject": {"$ref": "#/$defs/did"},
        "key_packages": {"type": "array", "items": {"$ref": "#/$defs/b64url"}},
        "last_resort": {"$ref": "#/$defs/b64url"},
    }, ["subject"], "KeyPackage upload by an owner device, or fetch response from a mailbox (M§5.5)."),
    "key-package-fetch": envelope_payload("key-package-fetch", {
        "target": {"$ref": "#/$defs/did"},
        "grant": {"type": "string", "minLength": 1},
        "successor_of": {"$ref": "#/$defs/b64url",
                         "description": "The dead group a successor is being created for: authorizes the fetch when that group is "
                                        "registered for the target (M§7.5, spec-gap 61)."},
    }, ["target"], "Request a target identity's KeyPackages (M§5.5); authorization per M§14.2."),
    "blob-put": envelope_payload("blob-put", {
        "sha256": {"$ref": "#/$defs/sha256"},
        "size": {"type": "integer", "minimum": 1},
    }, ["sha256", "size"], "Authorizes one blob upload; carried over HTTPS as Authorization: DSIP (M§5.6)."),
    "mailbox-config": envelope_payload("mailbox-config", {
        "subject": {"$ref": "#/$defs/did"},
        "mode": {"$ref": "#/$defs/token"},
        "retention_s": {"type": "integer", "minimum": 0},
        "admit": {"enum": ["grant", "open"]},
        "groups": {"type": "array", "items": {
            "type": "object",
            "properties": {"group": {"$ref": "#/$defs/b64url"}, "hub": {"$ref": "#/$defs/did"},
                           "hub_uri": {"$ref": "#/$defs/wssUri"},
                           "handover_seq": {"type": "integer", "minimum": 1,
                                            "description": "With a hub other than the registered one: the seq of the commit that "
                                                           "moved the group (M§7.4, spec-gap 60)."},
                           "state": {"enum": ["joined", "left"]}},
            "required": ["group", "state"],
            "additionalProperties": False,
        }},
        "revoked_grants": {"type": "array", "items": {"$ref": "#/$defs/ulid"}},
        "introductions_sent": {"type": "array", "items": {"$ref": "#/$defs/ulid"}, "maxItems": 256,
                               "description": "Ids of introductions the owner has sent (M§14.1, spec-gap 81): a grant "
                                              "deposit answering one is not rate-limited."},
        "release": {"type": "boolean",
                    "description": "true ends the identity's enrolment at this mailbox (M§4.1, spec-gap 130); the "
                                   "other fields are not applied. false is the same as absent."},
        "admission": {"type": "string", "minLength": 1, "maxLength": 256,
                      "description": "An admission code from the mailbox's operator, which enrols an identity the mailbox "
                                     "does not serve where it admits by code (M§4.1, spec-gap 185); sent only to a mailbox "
                                     "whose hello says enrolment: admission."},
    }, ["subject"], "Owner device configures its own mailbox (M§5.7)."),
}

BLOB_CONTENT = {
    "type": "object",
    "properties": {
        "uri": {"$ref": "#/$defs/httpsUri"},
        "sha256": {"$ref": "#/$defs/sha256"},
        "size": {"type": "integer", "minimum": 1},
        "key": {"type": "string", "pattern": "^[A-Za-z0-9_-]{43}$", "description": "base64url of a 32-byte AES-256-GCM key"},
        "alg": {"const": "A256GCM"},
        "content_type": {"type": "string", "minLength": 1},
        "name": {"type": "string"},
    },
    "required": ["uri", "sha256", "size", "key", "alg", "content_type"],
    "additionalProperties": False,
}

group_unless_first_contact(MESSAGES["deposit"], ["recipient", "envelope"])

# The profile's introduction (with `sealed`) and the `delegation-revocation` record moved to the v0.8 core schema set.
MESSAGES["mailbox-config"]["properties"]["revoked_delegations"] = {
    "type": "array", "items": {"type": "string", "minLength": 1},
    "description": "Compact delegation-revocation records from the owner identity (spec-gap 57)."}

OBJECTS = {
    "content": content_object("content", {
        "id": {"$ref": "#/$defs/ulid"},
        "conversation": {"$ref": "#/$defs/ulid"},
        "sender": {"$ref": "#/$defs/did"},
        "sent_at": {"$ref": "#/$defs/timestamp"},
        "kind": {"$ref": "#/$defs/token"},
        "purpose": {"$ref": "#/$defs/token"},
        "content_type": {"type": "string", "minLength": 1},
        "text": {"type": "string"},
        "reply_to": {"anyOf": [{"$ref": "#/$defs/ulid"}, {"type": "null"}]},
        "blob": BLOB_CONTENT,
        "duration_ms": {"type": "integer", "minimum": 0},
        "width": {"type": "integer", "minimum": 1},
        "height": {"type": "integer", "minimum": 1},
        "thumbnail": {"type": "string", "pattern": "^[A-Za-z0-9_-]*$", "maxLength": 10924},
        "name": {"type": "string"},
        "did": {"$ref": "#/$defs/did"},
        "display_name": {"type": "string", "maxLength": 256},
        "contact_token": {"type": "string", "minLength": 1},
        "lat_e7": {"type": "integer", "minimum": -900000000, "maximum": 900000000},
        "lon_e7": {"type": "integer", "minimum": -1800000000, "maximum": 1800000000},
        "accuracy_m": {"type": "integer", "minimum": 0},
        "session": {"$ref": "#/$defs/ulid"},
    }, ["id", "conversation", "sender", "sent_at", "kind", "purpose"],
        "A message inside an MLS application message (M§8.1–M§8.4). Kind-dependent body rules are semantic.",
        additional=True),
    "receipt": content_object("receipt", {
        "id": {"$ref": "#/$defs/ulid"},
        "conversation": {"$ref": "#/$defs/ulid"},
        "sender": {"$ref": "#/$defs/did"},
        "sent_at": {"$ref": "#/$defs/timestamp"},
        "kind": {"$ref": "#/$defs/token"},
        "targets": {"type": "array", "minItems": 1, "maxItems": 256, "items": {"$ref": "#/$defs/ulid"}},
        "through": {"$ref": "#/$defs/ulid"},
    }, ["id", "conversation", "sender", "sent_at", "kind"], "Identity-level receipt or read watermark (M§10)."),
    "activity": content_object("activity", {
        "conversation": {"$ref": "#/$defs/ulid"},
        "sender": {"$ref": "#/$defs/did"},
        "activity": {"$ref": "#/$defs/token"},
        "state": {"enum": ["active", "stopped"]},
    }, ["conversation", "sender", "activity", "state"], "Ephemeral activity, sealed under the exporter key (M§11)."),
    "archive-key": content_object("archive-key", {
        "akid": {"$ref": "#/$defs/ulid"},
        "key": {"type": "string", "pattern": "^[A-Za-z0-9_-]{43}$"},
        "created_at": {"$ref": "#/$defs/timestamp"},
    }, ["akid", "key", "created_at"], "Identity archive key, personal group only (M§12.1)."),
    "call-event": content_object("call-event", {
        "session": {"$ref": "#/$defs/ulid"},
        "peer": {"$ref": "#/$defs/did"},
        "direction": {"enum": ["inbound", "outbound"]},
        "outcome": {"$ref": "#/$defs/token"},
        "at": {"$ref": "#/$defs/timestamp"},
    }, ["session", "peer", "direction", "outcome", "at"], "Call history synchronized across own devices (M§13.3)."),
    "recording-acceptance": content_object("recording-acceptance", {
        "conversation": {"$ref": "#/$defs/ulid"},
        "recorders": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"$ref": "#/$defs/did"}},
        "accepted_at": {"$ref": "#/$defs/timestamp"},
    }, ["conversation", "recorders", "accepted_at"],
        "The user's acceptance of a recorded conversation, personal group only (Recording Profile C§5, v0.10)."),
    "call-record": content_object("call-record", {
        "session": {"$ref": "#/$defs/ulid"},
        "device": {"$ref": "#/$defs/did"},
        "direction": {"enum": ["inbound", "outbound"]},
        "peer": {"$ref": "#/$defs/did"},
        "relay": {"$ref": "#/$defs/did"},
        "invited_at": {"$ref": "#/$defs/timestamp"},
        "answered_at": {"$ref": "#/$defs/timestamp"},
        "ended_at": {"$ref": "#/$defs/timestamp"},
        "outcome": {"$ref": "#/$defs/token"},
        "ended_by": {"enum": ["local", "remote", "transport"]},
        "reason": {"type": "string", "pattern": "^[a-z][a-z0-9-]*\\.[a-z][a-z0-9-]*$",
                   "description": "The reason token that ended the leg (core §15), as received."},
        "media": {"type": "array", "items": {"$ref": "#/$defs/token"}},
        "recording": {
            "type": "object",
            "properties": {"state": {"$ref": "#/$defs/token"}, "recorder": {"$ref": "#/$defs/did"},
                           "purpose": {"$ref": "#/$defs/token"}},
            "required": ["state"],
            "additionalProperties": False,
            "description": "The party's last recording declaration in the session (C§3).",
        },
        "evidence": {"type": "array", "items": {"$ref": "#/$defs/sha256"}},
    }, ["session", "device", "direction", "peer", "invited_at", "ended_at", "outcome", "ended_by"],
        "One call leg's record for the organisation's record-keeper, direct conversations only (Recording Profile C§9, v0.13)."),
    "archive-record": content_object("archive-record", {
        "conversation": {"$ref": "#/$defs/ulid"},
        "group": {"$ref": "#/$defs/b64url"},
        "seq": {"type": "integer", "minimum": 1},
        "sender": {"$ref": "#/$defs/did"},
        "sender_device": {"$ref": "#/$defs/did"},
        "received_at": {"$ref": "#/$defs/timestamp"},
        "payload": {"type": "object", "required": ["object"]},
    }, ["conversation", "group", "seq", "sender", "sender_device", "received_at", "payload"],
        "Plaintext of an archive item before archive-key encryption (M§12.2)."),
    "mailbox-service": {
        "title": "DSIP messaging/1.0 DSIPMailbox serviceEndpoint",
        "description": "The serviceEndpoint object of a DSIPMailbox DID service entry, or the equivalent DHT hint endpoint (M§4.2).",
        "type": "object",
        "properties": {
            "uri": {"$ref": "#/$defs/wssUri"},
            "bindings": {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^[a-z0-9]+/\\d+\\.\\d+$"}},
            "mailbox": {"$ref": "#/$defs/did"},
            "priority": {"type": "integer", "minimum": 0},
            "profiles": {"type": "array", "items": {"$ref": "#/$defs/profileId"}},
            "accepts": {"type": "array", "items": {"$ref": "#/$defs/token"}},
            "service": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9-]*$",
                        "description": "DID service type this endpoint stands for in a DHT hint, e.g. DSIPMailbox (M§4.2)."},
            "voicemail": {
                "type": "object",
                "properties": {
                    "max_duration_s": {"type": "integer", "minimum": 1},
                    "greeting": {"$ref": "#/$defs/blobRef"},
                },
                "additionalProperties": False,
            },
        },
        "required": ["uri", "bindings", "mailbox"],
        "additionalProperties": False,
    },
    "dsip-conversation": {
        "title": "DSIP messaging/1.0 dsip_conversation GroupContext extension",
        "description": "UTF-8 JSON extension data naming the conversation and its hub (M§6.3).",
        "type": "object",
        "properties": {
            "conversation": {"$ref": "#/$defs/ulid"},
            "kind": {"$ref": "#/$defs/token"},
            "hub": {"$ref": "#/$defs/hubRef"},
            "successor_of": {"anyOf": [{"$ref": "#/$defs/b64url"}, {"type": "null"}]},
        },
        "required": ["conversation", "kind", "hub"],
        "additionalProperties": False,
    },
}


def finish(name, schema):
    s = {"$schema": SCHEMA_DIALECT, "$id": f"{NS}{name}.schema.json"}
    s.update(schema)
    s["$defs"] = copy.deepcopy(DEFS)
    return s


def main(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for name, schema in {**MESSAGES, **OBJECTS}.items():
        (out / f"{name}.schema.json").write_text(json.dumps(finish(name, schema), indent=2) + "\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "schemas")
