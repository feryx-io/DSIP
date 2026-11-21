"""Envelope vectors — stages 1–11 (spec §10.2, §7.4, §8.1, §12.9, §20.6; schema README checks 1–3)."""
from __future__ import annotations

import json

from .. import fixtures as F
from .. import envelope as E
from ..crypto import b64url_encode, b64url_decode
from .common import (NOW, invite, hello_client, hello_relay, signed, default_context, vector, accept, reject,
                     session_msg, uid)

APH, ALA, BPH, BLA = F.did("alice-phone"), F.did("alice-laptop"), F.did("bob-phone"), F.did("bob-laptop")
ALICE, BOB = F.did("alice"), F.did("bob")


def env_vector(vid, desc, refs, env, expect, ctx=None, frame=None):
    inp = {"envelope": env}
    if frame is not None:
        inp["frame"] = frame
    return vector(f"envelope/{vid}", "envelope", desc, refs, ctx or default_context(), inp, expect)


def tamper_payload(env: dict) -> dict:
    raw = b64url_decode(env["payload"]).decode()
    raw = raw.replace('"intent":"interactive"', '"intent":"tampered"')
    return {**env, "payload": b64url_encode(raw.encode())}


def vectors() -> list[dict]:
    out = []
    ctx = default_context()
    inv = invite()
    good = signed(inv, "alice-phone")

    # --- signature and header
    out.append(env_vector("valid-ed25519", "Well-formed invite signed by alice-phone's own did:key; kid resolves to from.",
                          ["§10.2"], good, accept(type="invite", signer=APH, identity=APH)))
    out.append(env_vector("tampered-payload", "One payload byte changed after signing; signature must fail over the exact bytes.",
                          ["§10.2"], tamper_payload(good), reject("signature-invalid")))
    out.append(env_vector("wrong-signature-bytes", "Signature from a different key substituted into an otherwise valid envelope.",
                          ["§10.2"], {**good, "signature": signed(inv, "mallory")["signature"]}, reject("signature-invalid")))
    out.append(env_vector("alg-es256-rejected", "ES256 is MAY in §10.2; this implementation rejects anything but EdDSA.",
                          ["§10.2"], signed(inv, "alice-phone", alg="ES256"), reject("alg-unsupported")))
    out.append(env_vector("alg-none-rejected", "alg=none must be rejected.", ["§10.2"],
                          signed(inv, "alice-phone", alg="none"), reject("alg-unsupported")))
    out.append(env_vector("header-missing-kid", "Protected header without kid.", ["§10.2"],
                          _custom_header(inv, "alice-phone", {"alg": "EdDSA"}), reject("header-invalid")))
    out.append(env_vector("kid-not-did-url", "kid is not a DID URL with a fragment.", ["§10.2"],
                          signed(inv, "alice-phone", kid="not-a-did"), reject("kid-invalid")))
    out.append(env_vector("kid-did-key-wrong-fragment", "did:key kid whose fragment does not name the key itself.",
                          ["§10.2", "§7.2"], signed(inv, "alice-phone", kid=f"{APH}#other"), reject("kid-unresolvable")))
    out.append(env_vector("kid-unknown-did-web", "did:web kid for a domain with no DID document available.",
                          ["§8.1"], signed(inv, "alice-phone", kid="did:web:nowhere.example#key-1"), reject("kid-unresolvable")))
    out.append(env_vector("envelope-extra-member", "Envelope object with a fourth member is not the §10.2 shape.",
                          ["§10.2"], {**good, "extra": 1}, reject("envelope-shape")))
    out.append(env_vector("envelope-bad-base64url", "payload member contains characters outside the base64url alphabet.",
                          ["§10.2"], {**good, "payload": good["payload"] + "+/="}, reject("envelope-shape")))

    # --- wire format at parse (§10.3)
    out.append(env_vector("payload-float-timestamp", "issued_at is 1760000000.0: floats are forbidden even when integral.",
                          ["§10.3"], _raw_signed(json.dumps(inv).replace(f'"issued_at": {NOW}', f'"issued_at": {NOW}.0'), "alice-phone"),
                          reject("payload-float")))
    out.append(env_vector("payload-float-nested", "A float deep inside the media offer is still a wire-format violation.",
                          ["§10.3"], _raw_signed(json.dumps(inv).replace('"channels": [1, 2]', '"channels": [1.5, 2]'), "alice-phone"),
                          reject("payload-float")))
    out.append(env_vector("payload-not-utf8", "Payload bytes are not valid UTF-8.", ["§10.3"],
                          E.sign_bytes(b'{"type":"invite","x":"\xff\xfe"}', F.KEYS["alice-phone"], F.kid("alice-phone")),
                          reject("payload-not-utf8")))
    out.append(env_vector("payload-not-json", "Payload is UTF-8 but not JSON.", ["§10.3"],
                          E.sign_bytes(b"this is not json", F.KEYS["alice-phone"], F.kid("alice-phone")),
                          reject("payload-not-json")))
    out.append(env_vector("payload-json-array", "Payload is a JSON array, not an object.", ["§10.3"],
                          E.sign_bytes(b'[1,2,3]', F.KEYS["alice-phone"], F.kid("alice-phone")), reject("payload-not-json")))
    out.append(env_vector("payload-missing-core-fields", "Payload object lacks id/from/timestamps.", ["§10.3"],
                          signed({"dsip": F.VERSION, "type": "invite"}, "alice-phone"), reject("payload-shape")))
    out.append(env_vector("payload-prose-ulid", "Spec-prose illustrative id 01HZINVITEABC is not a valid ULID.", ["§10.3"],
                          signed({**inv, "id": "01HZINVITEABC"}, "alice-phone"), reject("payload-shape")))

    # --- delegation binding (§7.4, check 3)
    inv_identity = {**inv, "from": ALICE}
    out.append(env_vector("delegated-device-signs-for-identity",
                          "from is alice's identity DID; kid is alice-phone; a live delegation links them.",
                          ["§7.4", "§10.2"], signed(inv_identity, "alice-phone"), accept(type="invite", signer=APH, identity=ALICE)))
    out.append(env_vector("delegated-did-web-identity",
                          "from is bob's did:web identity; kid is bob-phone; delegation signed by the did:web key-1.",
                          ["§7.4", "§7.2"], signed(session_msg("progress", "prog", inv["id"], F.BOB_WEB, APH, NOW + 1, status="ringing"), "bob-phone"),
                          accept(type="progress", signer=BPH, identity=F.BOB_WEB, effective={"status": "ringing"})))
    out.append(env_vector("signer-no-delegation", "mallory signs a message claiming from=alice; no delegation exists.",
                          ["§7.4"], signed(inv_identity, "mallory"), reject("signer-mismatch")))
    out.append(env_vector("delegation-in-header", "Delegation presented only in the protected header `delegations` array (Impl, spec-gap 8).",
                          ["§7.4"], signed(inv_identity, "alice-phone", header_extra={"delegations": [F.standard_delegations()[0]]}),
                          accept(type="invite", signer=APH, identity=ALICE), ctx=default_context(delegations=[])))
    expired_dlg = F.make_delegation(F.KEYS["alice"], ALICE, APH, issued_at=NOW - 200000, expires_at=NOW - 100)
    out.append(env_vector("delegation-expired", "The only delegation for alice-phone expired before receipt.", ["§7.4"],
                          signed(inv_identity, "alice-phone"), reject("delegation-expired"), ctx=default_context(delegations=[expired_dlg])))
    future_dlg = F.make_delegation(F.KEYS["alice"], ALICE, APH, issued_at=NOW + 100, expires_at=NOW + 100000)
    out.append(env_vector("delegation-not-yet-valid", "Delegation issued_at is in the future.", ["§7.4"],
                          signed(inv_identity, "alice-phone"), reject("delegation-expired"), ctx=default_context(delegations=[future_dlg])))
    nocap_dlg = F.make_delegation(F.KEYS["alice"], ALICE, APH, capabilities=("dsip.media.interactive",))
    out.append(env_vector("delegation-lacks-signaling", "Delegation exists but does not grant dsip.signaling.", ["§7.4"],
                          signed(inv_identity, "alice-phone"), reject("delegation-capability"), ctx=default_context(delegations=[nocap_dlg])))
    forged_dlg = F.make_delegation(F.KEYS["mallory"], ALICE, APH)  # signed by mallory, claims subject alice
    out.append(env_vector("delegation-forged-issuer", "Delegation for alice→alice-phone signed by mallory, not alice's controller.", ["§7.4"],
                          signed(inv_identity, "alice-phone"), reject("delegation-invalid"), ctx=default_context(delegations=[forged_dlg])))
    out.append(env_vector("delegation-wrong-device", "Only alice→alice-laptop delegation is known; alice-phone signs.", ["§7.4"],
                          signed(inv_identity, "alice-phone"), reject("signer-mismatch"),
                          ctx=default_context(delegations=[F.standard_delegations()[1]])))
    out.append(env_vector("delegation-chain-not-allowed", "bob-phone 'delegates' bob-laptop to act for bob; only the controller may delegate.", ["§7.4"],
                          signed({**inv, "from": BOB, "to": ALICE}, "bob-laptop"), reject("delegation-invalid"),
                          ctx=default_context(delegations=[F.make_delegation(F.KEYS["bob-phone"], BOB, BLA)])))

    # --- key rotation (§7.5): the DID document after rotation is what a verifier sees (§8.1)
    rotated_docs = {**F.did_documents(), F.BOB_WEB: F.did_web_document_rotated(F.BOB_WEB, "bob-next")}
    new_kid = f"{F.BOB_WEB}#key-2"
    prog_web = session_msg("progress", "prog", inv["id"], F.BOB_WEB, APH, NOW + 1, status="ringing")
    new_dlg = F.make_delegation(F.KEYS["bob-next"], F.BOB_WEB, BPH, signer_kid=new_kid)
    old_dlg = F.make_delegation(F.KEYS["bob"], F.BOB_WEB, BPH, signer_kid=F.web_kid(F.BOB_WEB))
    out.append(env_vector("rotated-did-web-new-key-signs",
                          "bob's did:web identity rotated key-1 → key-2 (§7.5); the identity signs directly under the new kid.",
                          ["§7.5", "§8.1", "§10.2"], signed(prog_web, "bob-next", kid=new_kid),
                          accept(type="progress", signer=F.BOB_WEB, identity=F.BOB_WEB, effective={"status": "ringing"}),
                          ctx=default_context(did_documents=rotated_docs)))
    out.append(env_vector("rotated-did-web-retired-kid-rejected",
                          "After rotation the retired fragment #key-1 names no verification method; a signature under it cannot be verified.",
                          ["§7.5", "§8.1"], signed(prog_web, "bob", kid=F.web_kid(F.BOB_WEB)), reject("kid-unresolvable"),
                          ctx=default_context(did_documents=rotated_docs)))
    out.append(env_vector("rotated-did-web-new-key-delegation",
                          "Device delegation re-issued by the rotated identity key (#key-2) admits bob-phone for the did:web identity.",
                          ["§7.5", "§7.4"], signed(prog_web, "bob-phone"),
                          accept(type="progress", signer=BPH, identity=F.BOB_WEB, effective={"status": "ringing"}),
                          ctx=default_context(did_documents=rotated_docs, delegations=[new_dlg])))
    out.append(env_vector("rotated-did-web-old-key-delegation-rejected",
                          "A delegation signed by the retired key-1 is invalid once the document no longer lists it — rotation revokes the device list (§7.5).",
                          ["§7.5", "§7.4"], signed(prog_web, "bob-phone"), reject("delegation-invalid"),
                          ctx=default_context(did_documents=rotated_docs, delegations=[old_dlg])))

    rot = {"dsip": F.VERSION, "type": "key-rotation", "id": uid("rot"), "from": F.BOB_WEB, "subject": F.BOB_WEB,
           "previous": F.web_kid(F.BOB_WEB), "next": new_kid, "next_public_key_multibase": F.multibase_pub("bob-next"),
           "reason": "scheduled", "devices": [BPH], "issued_at": NOW, "expires_at": NOW + 86400}
    out.append(env_vector("key-rotation-signed-by-previous-key",
                          "A rotation record (v0.7, §7.5) verifies under the pre-rotation document the receiver still holds: the retiring key signs it.",
                          ["§7.5", "§8.1"], signed(rot, "bob", kid=F.web_kid(F.BOB_WEB)),
                          accept(type="key-rotation", signer=F.BOB_WEB, identity=F.BOB_WEB)))

    # --- delegation revocation (§7.4, v0.8, spec-gap 57): a verification stage inside delegation checking
    web_dlg = lambda device, ia=NOW - 86400: F.make_delegation(F.KEYS["bob"], F.BOB_WEB, device, issued_at=ia,
                                                                signer_kid=F.web_kid(F.BOB_WEB))
    def revocation(device=BLA, revoked_at=NOW - 60, signer="bob", kid=None, label="rev"):
        p = {"dsip": F.VERSION, "type": "delegation-revocation", "id": uid(label, revoked_at), "from": F.BOB_WEB, "subject": F.BOB_WEB,
             "device": device, "revoked_at": revoked_at, "reason": "lost", "issued_at": revoked_at, "expires_at": revoked_at + 300}
        return signed(p, signer, kid=kid or (F.web_kid(F.BOB_WEB) if signer == "bob" else None))
    def docs_with(*revs):
        docs = F.did_documents()
        docs[F.BOB_WEB] = {**docs[F.BOB_WEB], "dsipDelegationRevocations": [f"{r['protected']}.{r['payload']}.{r['signature']}" for r in revs]}
        return docs
    prog_laptop = session_msg("progress", "prog-bla", inv["id"], F.BOB_WEB, APH, NOW + 1, status="ringing")
    ok_laptop = accept(type="progress", signer=BLA, identity=F.BOB_WEB, effective={"status": "ringing"})
    R = ["§7.4", "§8.1"]
    out.append(env_vector("delegation-revoked-in-document", "A revocation published in the subject's DID document (dsipDelegationRevocations, "
                          "authoritative) revokes the device's delegation: its envelopes no longer bind to the identity (v0.8).", R,
                          signed(prog_laptop, "bob-laptop"), reject("delegation-revoked"),
                          ctx=default_context(did_documents=docs_with(revocation()), delegations=[web_dlg(BLA)])))
    out.append(env_vector("delegation-revoked-held-by-verifier", "A validly signed revocation the verifier holds revokes too: it can only remove authority.",
                          R, signed(prog_laptop, "bob-laptop"), reject("delegation-revoked"),
                          ctx=default_context(delegations=[web_dlg(BLA)], revocations=[revocation()])))
    out.append(env_vector("delegation-not-revoked", "The same device and delegation with no revocation in sight binds.", R,
                          signed(prog_laptop, "bob-laptop"), ok_laptop, ctx=default_context(delegations=[web_dlg(BLA)])))
    out.append(env_vector("delegation-revoked-at-boundary", "A delegation issued exactly at revoked_at is revoked.", R,
                          signed(prog_laptop, "bob-laptop"), reject("delegation-revoked"),
                          ctx=default_context(delegations=[web_dlg(BLA, ia=NOW - 60)], revocations=[revocation(revoked_at=NOW - 60)])))
    out.append(env_vector("delegation-reenrolled-after-revocation", "A delegation issued after revoked_at re-enrolls the device.", R,
                          signed(prog_laptop, "bob-laptop"), ok_laptop,
                          ctx=default_context(delegations=[web_dlg(BLA, ia=NOW - 30)], revocations=[revocation(revoked_at=NOW - 60)])))
    out.append(env_vector("delegation-revocation-other-device-unaffected", "A revocation names one device; its siblings keep their delegations.", R,
                          signed(session_msg("progress", "prog-bph", inv["id"], F.BOB_WEB, APH, NOW + 1, status="ringing"), "bob-phone"),
                          accept(type="progress", signer=BPH, identity=F.BOB_WEB, effective={"status": "ringing"}),
                          ctx=default_context(delegations=[web_dlg(BPH)], revocations=[revocation(device=BLA)])))
    out.append(env_vector("delegation-revocation-not-by-subject-ignored", "A revocation signed by any key but the subject's is ignored.", R,
                          signed(prog_laptop, "bob-laptop"), ok_laptop,
                          ctx=default_context(delegations=[web_dlg(BLA)], revocations=[revocation(signer="mallory")])))
    out.append(env_vector("delegation-revocation-by-device-ignored", "Nor may a device revoke itself or a sibling with its own key.", R,
                          signed(prog_laptop, "bob-laptop"), ok_laptop,
                          ctx=default_context(delegations=[web_dlg(BLA)], revocations=[revocation(signer="bob-laptop")])))
    out.append(env_vector("hello-revoked-device-rejected", "A revoked device's hello on behalf of the identity is refused (transport.hello-rejected): "
                          "a service stops serving it at its next binding.", R + ["§13.2"],
                          signed(hello_client(frm=BLA, on_behalf_of=F.BOB_WEB), "bob-laptop"), reject("delegation-revoked", "transport.hello-rejected"),
                          ctx=default_context(did_documents=docs_with(revocation()), delegations=[web_dlg(BLA)])))
    out.append(env_vector("delegation-revocation-record-verifies", "The record itself is an envelope signed by the subject's key.", R,
                          revocation(), accept(type="delegation-revocation", signer=F.BOB_WEB, identity=F.BOB_WEB)))
    # spec-gap 56 disposition (b): the binding capability stays dsip.signaling for every envelope, so a device delegated
    # for messaging only cannot bind — messaging devices carry dsip.signaling as well.
    msg_only = F.make_delegation(F.KEYS["bob"], F.BOB_WEB, BLA, capabilities=("dsip.messaging",), signer_kid=F.web_kid(F.BOB_WEB))
    out.append(env_vector("hello-messaging-only-delegation-rejected", "Binding requires dsip.signaling for every envelope, hello included; a "
                          "delegation for dsip.messaging alone does not bind (v0.8, spec-gap 56).", ["§7.4", "§13.2"],
                          signed(hello_client(frm=BLA, on_behalf_of=F.BOB_WEB), "bob-laptop"),
                          reject("delegation-capability", "transport.hello-rejected"),
                          ctx=default_context(delegations=[msg_only])))

    # --- hello on_behalf_of (check 3)
    h = hello_client(on_behalf_of=F.BOB_WEB)
    out.append(env_vector("hello-on-behalf-of-valid", "bob-phone hello on behalf of bob's did:web identity with a valid delegation.",
                          ["§13.2", "§7.4"], signed(h, "bob-phone"), accept(type="hello", signer=BPH, identity=F.BOB_WEB)))
    out.append(env_vector("hello-on-behalf-of-no-delegation", "carol-phone claims to act for bob; no delegation → transport.hello-rejected.",
                          ["§13.2", "§7.4"], signed(hello_client(frm=F.did("carol-phone"), on_behalf_of=F.BOB_WEB), "carol-phone"),
                          reject("signer-mismatch", "transport.hello-rejected")))
    out.append(env_vector("hello-relay-did-web", "Relay hello signed by did:web:relay.example.com#key-1 resolved from its DID document.",
                          ["§13.2", "§8.1"], signed(hello_relay(h["id"]), "relay", kid=F.web_kid(F.RELAY_WEB)),
                          accept(type="hello", signer=F.RELAY_WEB, identity=F.RELAY_WEB)))
    out.append(env_vector("hello-relay-did-web-wrong-key", "Relay hello signed by mallory under the relay's kid.",
                          ["§13.2"], signed(hello_relay(h["id"]), "mallory", kid=F.web_kid(F.RELAY_WEB)), reject("signature-invalid")))

    # --- timing (§12.9, check 1)
    out.append(env_vector("expiry-before-issued", "expires_at earlier than issued_at.", ["§12.9"],
                          signed({**inv, "expires_at": NOW - 1}, "alice-phone"), reject("expiry-order")))
    out.append(env_vector("expiry-equals-issued", "expires_at equal to issued_at (must be strictly greater).", ["§12.9"],
                          signed({**inv, "expires_at": NOW}, "alice-phone"), reject("expiry-order")))
    old = invite("inv-old", at=NOW - 301, ttl=3600)
    out.append(env_vector("replay-window-too-old", "issued_at 301 s before receipt, outside the 300 s replay window.", ["§12.9"],
                          signed(old, "alice-phone"), reject("replay-window")))
    edge = invite("inv-edge", at=NOW - 300, ttl=3600)
    out.append(env_vector("replay-window-edge-accepted", "issued_at exactly 300 s before receipt is inside the window.", ["§12.9"],
                          signed(edge, "alice-phone"), accept(type="invite", signer=APH, identity=APH)))
    fut = invite("inv-future", at=NOW + 301)
    out.append(env_vector("replay-window-future", "issued_at 301 s in the future (Impl: symmetric window, spec-gap 7).", ["§12.9"],
                          signed(fut, "alice-phone"), reject("replay-window")))
    expired_inv = invite("inv-exp", at=NOW - 100, ttl=30)
    out.append(env_vector("invite-expired", "Invite received after expires_at → session.expired.", ["§12.9"],
                          signed(expired_inv, "alice-phone"), reject("expired", "session.expired")))
    expired_prog = session_msg("progress", "prog-exp", inv["id"], BPH, APH, NOW - 100, status="ringing")
    out.append(env_vector("non-invite-expired", "Expired non-invite envelope: rejected without a reason token.", ["§12.9"],
                          signed(expired_prog, "bob-phone"), reject("expired")))
    # spec-gap 141 (a): expires_at is the first instant the message is no longer valid
    edge_inv = invite("inv-exp-edge", at=NOW - 30, ttl=30)
    out.append(env_vector("invite-at-expiry", "Invite received at exactly its expires_at: expired, session.expired (§12.9: valid "
                          "while now < expires_at, spec-gap 141).", ["§12.9"],
                          signed(edge_inv, "alice-phone"), reject("expired", "session.expired")))
    live_inv = invite("inv-live-edge", at=NOW - 29, ttl=30)
    out.append(env_vector("invite-one-second-before-expiry", "Invite received one second before its expires_at is accepted.",
                          ["§12.9"], signed(live_inv, "alice-phone"), accept(type="invite", signer=APH, identity=APH)))
    out.append(env_vector("duplicate-id", "id already seen within the replay window.", ["§12.9"],
                          good, reject("duplicate-id"), ctx=default_context(seen_ids=[inv["id"]])))
    backdated = {**inv, "id": uid("backdated", NOW - 3600)}
    out.append(env_vector("ulid-backdated", "ULID timestamp one hour before signed issued_at (glare-backdating guard).", ["§20.6", "§12.6"],
                          signed(backdated, "alice-phone"), reject("ulid-issued-at-mismatch")))
    tol = {**inv, "id": uid("tol", NOW - 300)}
    out.append(env_vector("ulid-within-tolerance", "ULID timestamp 300 s before issued_at is within tolerance (Impl, spec-gap 6).", ["§20.6"],
                          signed(tol, "alice-phone"), accept(type="invite", signer=APH, identity=APH)))

    # --- first contact (§19.4) sizes
    intro = {"dsip": F.VERSION, "type": "introduction", "id": uid("intro"), "from": F.did("carol-phone"), "to": F.BOB_WEB,
             "identity": {"display_name": "Carol Nguyen", "claims": []},
             "purpose": "We met at the mesh-networking meetup; following up about the antenna group buy.",
             "issued_at": NOW, "expires_at": NOW + 604800}
    out.append(env_vector("introduction-valid-7-day", "Introduction with the maximum 7-day validity.", ["§19.4"],
                          signed(intro, "carol-phone"), accept(type="introduction", signer=F.did("carol-phone"), identity=F.did("carol-phone"))))
    # --- held introductions (§19.4 validity vs §12.9 window; Impl: spec-gap 31)
    held_at = NOW - 172800  # held two days by the recipient's relay (§13.3)
    held = {**intro, "id": uid("intro-held", held_at), "issued_at": held_at, "expires_at": held_at + 604800}
    carol = F.did("carol-phone")
    out.append(env_vector("introduction-held-accepted",
                          "Introduction delivered two days after signing, inside its 7-day validity: the 300 s age bound "
                          "does not apply to introductions (Impl: spec-gap 31).", ["§19.4", "§12.9", "§13.3"],
                          signed(held, "carol-phone"), accept(type="introduction", signer=carol, identity=carol)))
    out.append(env_vector("introduction-held-replayed",
                          "A held introduction whose id was already seen is a duplicate: introduction ids are tracked "
                          "until expires_at, not for 300 s (Impl: spec-gap 31).", ["§19.4", "§12.9"],
                          signed(held, "carol-phone"), reject("duplicate-id"), ctx=default_context(seen_ids=[held["id"]])))
    stale_at = NOW - 604900
    stale = {**intro, "id": uid("intro-stale", stale_at), "issued_at": stale_at, "expires_at": stale_at + 604800}
    out.append(env_vector("introduction-held-expired",
                          "Held introduction delivered after its expires_at is rejected as expired.", ["§19.4", "§12.9"],
                          signed(stale, "carol-phone"), reject("expired")))
    edge_at = NOW - 604800
    edge_intro = {**intro, "id": uid("intro-edge", edge_at), "issued_at": edge_at, "expires_at": NOW}
    out.append(env_vector("introduction-held-at-expiry",
                          "Held introduction delivered at exactly its expires_at is expired (§12.9, spec-gap 141).",
                          ["§19.4", "§12.9"], signed(edge_intro, "carol-phone"), reject("expired")))
    fut_intro = {**intro, "id": uid("intro-future", NOW + 301), "issued_at": NOW + 301, "expires_at": NOW + 301 + 604800}
    out.append(env_vector("introduction-future-rejected",
                          "The future bound of the replay window still applies to introductions (Impl: spec-gap 31).",
                          ["§19.4", "§12.9"], signed(fut_intro, "carol-phone"), reject("replay-window")))
    over = {**intro, "id": uid("intro-over"), "expires_at": NOW + 604801}
    out.append(env_vector("introduction-validity-over-cap",
                          "Introduction validity one second over the 604,800 s cap is rejected: the cap bounds how long "
                          "its id stays replay-tracked (Impl: spec-gap 31).", ["§19.4", "§12.9"],
                          signed(over, "carol-phone"), reject("introduction-validity")))
    big = {**intro, "identity": {"display_name": "Carol", "claims": [{"blob": "x" * 4000}]}}
    out.append(env_vector("introduction-too-large", "Encoded introduction envelope exceeds the 4,096-byte core constant.", ["§19.4"],
                          signed(big, "carol-phone"), reject("introduction-too-large")))
    # profile-card/1.0 (spec-gap 186): a sealed introduction listing the extension, up to 16,384 bytes
    carded = lambda n: {**{k: v for k, v in intro.items() if k != "purpose"}, "id": uid(f"intro-card-{n}"),
                        "dsip": {**F.VERSION, "extensions": ["profile-card/1.0"]},
                        "sealed": {"alg": "hpke-base-x25519-sha256-aes128gcm", "enc": "N_2jVnvb1ijohmjDyNfpfR0SU7bU6m1EwVD3QfG_RDE",
                                   "ct": "c" * n}}
    out.append(env_vector("introduction-card-over-4096-accepted",
                          "A sealed introduction that lists profile-card/1.0 is accepted over 4,096 bytes: about 10,000 here.", ["§19.4"],
                          signed(carded(6800), "carol-phone"), accept(type="introduction", signer=F.did("carol-phone"), identity=F.did("carol-phone"))))
    out.append(env_vector("introduction-card-too-large", "Over 16,384 bytes it is refused, extension or not.", ["§19.4"],
                          signed(carded(12300), "carol-phone"), reject("introduction-too-large")))
    out.append(env_vector("introduction-sealed-unlisted-too-large", "The same sealed body without the extension is held to 4,096.", ["§19.4"],
                          signed({**carded(6800), "id": uid("intro-card-unlisted"), "dsip": F.VERSION}, "carol-phone"),
                          reject("introduction-too-large")))
    from .presence_vectors import envelope_vectors
    from . import presence_sealed
    out.extend(envelope_vectors())
    out.extend(presence_sealed.envelope_vectors())
    return out


def _custom_header(payload, signer_name, header):
    k = F.KEYS[signer_name]
    prot = b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    pay = b64url_encode(E.encode_payload(payload))
    sig = k.sign(f"{prot}.{pay}".encode())
    return {"protected": prot, "payload": pay, "signature": b64url_encode(sig)}


def _raw_signed(text: str, signer_name: str):
    k = F.KEYS[signer_name]
    return E.sign_bytes(text.encode("utf-8"), k, k.kid)
