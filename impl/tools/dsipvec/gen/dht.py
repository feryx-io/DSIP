"""DHT reachability-hint record vectors (spec §8.1, §8.3, §8.5; plan §10.3).

A hint record is a DSIP-JOSE envelope whose payload is a `reachability-hint`.
It is never authoritative: verification is against the subject DID (or a
delegation), and §8.3 conflict rules decide between live records.
"""
from __future__ import annotations

from .. import fixtures as F
from .. import envelope as E
from ..crypto import b64url_decode, b64url_encode
from .common import NOW, signed, default_context, vector, accept, reject, uid

ALICE, APH = F.did("alice"), F.did("alice-phone")


def hint(label: str, subject: str, frm: str, seq: int, at: int = NOW, ttl: int = 3600, uri="wss://relay.example.com/dsip") -> dict:
    return {"dsip": F.VERSION_TRANSPORT, "type": "reachability-hint", "id": uid(label, at), "from": frm,
            "subject": subject, "endpoints": [{"uri": uri, "bindings": ["ws/1.0"]}], "seq": seq,
            "issued_at": at, "expires_at": at + ttl}


def dv(vid, desc, refs, env, expect, existing=None, ctx=None):
    context = ctx or default_context()
    if existing is not None:
        context["existing"] = existing
    return vector(f"dht/{vid}", "dht", desc, refs, context, {"envelope": env}, expect)


def vectors() -> list[dict]:
    out = []
    h1 = signed(hint("h1", ALICE, ALICE, 1), "alice")
    out.append(dv("valid-self-signed-did-key", "Hint for alice signed by alice's own did:key — zero external resolution.",
                  ["§8.3", "§8.5"], h1, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="input", conflict="none")))
    h1_dev = signed(hint("h1d", ALICE, ALICE, 1, at=NOW - 60), "alice-phone")
    out.append(dv("valid-delegated-device", "Hint for alice signed by alice-phone under a live delegation.", ["§8.3", "§7.4"],
                  h1_dev, accept(type="reachability-hint", signer=APH, identity=ALICE, winner="input", conflict="none")))
    raw = b64url_decode(h1["payload"]).decode().replace("relay.example.com", "evil.example.com")
    out.append(dv("tampered-endpoint", "Endpoint URI altered after signing.", ["§8.3"],
                  {**h1, "payload": b64url_encode(raw.encode())}, reject("signature-invalid")))
    out.append(dv("non-delegated-signer", "mallory publishes a hint for alice.", ["§8.3", "§7.4"],
                  signed(hint("hm", ALICE, ALICE, 5), "mallory"), reject("signer-mismatch")))
    out.append(dv("subject-not-signer-identity", "bob-phone (delegated by bob) publishes a hint whose subject is alice.", ["§8.3"],
                  signed(hint("hb", ALICE, F.did("bob"), 1), "bob-phone"), reject("hint-subject-mismatch")))
    out.append(dv("expired-record", "Record past expiration is invalid.", ["§8.3"],
                  signed(hint("hx", ALICE, ALICE, 1, at=NOW - 200, ttl=100), "alice"), reject("expired")))
    h2 = signed(hint("h2", ALICE, ALICE, 2, at=NOW - 30), "alice")
    out.append(dv("seq-newer-wins", "Input seq 2 vs existing seq 1: newer sequence wins.", ["§8.3"],
                  h2, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="input", conflict="newer-seq"), existing=h1))
    out.append(dv("seq-older-loses", "Input seq 1 vs existing seq 2: existing record kept.", ["§8.3"],
                  h1, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="existing", conflict="older-seq"), existing=h2))
    h1b = signed(hint("h1b", ALICE, ALICE, 1, uri="wss://other.example.com/dsip"), "alice")
    out.append(dv("same-seq-live-conflict", "Two live records, same key, same seq, different content → warn; existing kept.", ["§8.3"],
                  h1b, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="existing", conflict="same-seq-live"), existing=h1))
    out.append(dv("same-record-duplicate", "Identical record re-observed: no conflict.", ["§8.3"],
                  h1, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="existing", conflict="none"), existing=h1))
    stale_existing = signed(hint("hs", ALICE, ALICE, 9, at=NOW - 7200, ttl=3600), "alice")
    out.append(dv("existing-expired-ignored", "An expired existing record carries no authority; the live input wins regardless of seq.",
                  ["§8.3"], h1, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="input", conflict="none"),
                  existing=stale_existing))
    out.append(dv("schema-missing-seq", "Hint without seq fails the hint schema.", ["§8.3"],
                  signed({k: v for k, v in hint("hq", ALICE, ALICE, 1).items() if k != "seq"}, "alice"), reject("schema-invalid")))

    # Spec-gap 96 (§12.9 exception, DHT profile §2): a hint's age is bounded by its own expires_at,
    # not the 300 s replay window, under a 3,600 s cap; the future bound stays. The cap edge
    # (ttl exactly 3,600 s) is pinned by valid-self-signed-did-key.
    held = signed(hint("hh", ALICE, ALICE, 3, at=NOW - 1000), "alice")
    out.append(dv("hint-held-accepted", "Hint signed 1,000 s ago with an hour's validity: stored and read while now < expires_at.",
                  ["§12.9", "§8.3", "§8.5"], held, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="input", conflict="none")))
    out.append(dv("hint-held-expired", "Hint signed 4,000 s ago with an hour's validity: expired, not a replay-window rejection.",
                  ["§12.9", "§8.3"], signed(hint("hhx", ALICE, ALICE, 3, at=NOW - 4000), "alice"), reject("expired")))
    out.append(dv("hint-future-rejected", "Hint issued 400 s in the future: the future bound of the replay window still applies.",
                  ["§12.9"], signed(hint("hhf", ALICE, ALICE, 3, at=NOW + 400), "alice"), reject("replay-window")))
    out.append(dv("hint-validity-over-cap", "Hint whose expires_at − issued_at is 3,601 s: over the 3,600 s cap.",
                  ["§12.9", "§8.5"], signed(hint("hhc", ALICE, ALICE, 3, ttl=3601), "alice"), reject("hint-validity")))
    held_old = signed(hint("hho", ALICE, ALICE, 2, at=NOW - 2000), "alice")
    out.append(dv("hint-held-newer-wins", "Two held live hints (signed 2,000 s and 1,000 s ago): §8.3 still decides — the higher seq wins.",
                  ["§12.9", "§8.3"], held, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="input", conflict="newer-seq"),
                  existing=held_old))
    out.append(dv("hint-held-duplicate", "A held hint re-observed (replication re-puts it): a no-op under §8.3, not a duplicate-id rejection.",
                  ["§12.9", "§8.3"], held, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="existing", conflict="none"),
                  existing=held))
    # Spec-gap 141 (a): expires_at is the first instant a record is invalid, and a hint's id is not deduplicated
    out.append(dv("hint-at-expiry", "A hint received at exactly its expires_at is expired (§12.9: valid while now < expires_at, "
                  "spec-gap 141).", ["§12.9", "§8.3"], signed(hint("hhe", ALICE, ALICE, 3, at=NOW - 3600), "alice"), reject("expired")))
    edge_ok = signed(hint("hhl", ALICE, ALICE, 3, at=NOW - 3599), "alice")
    out.append(dv("hint-one-second-before-expiry", "A hint received one second before its expires_at is live.", ["§12.9", "§8.3"],
                  edge_ok, accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="input", conflict="none")))
    out.append(dv("existing-at-expiry-ignored", "An existing record at exactly its expires_at carries no authority: the live input "
                  "wins though its seq is lower (§8.3, §12.9, spec-gap 141).", ["§8.3", "§12.9"], h1,
                  accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="input", conflict="none"),
                  existing=signed(hint("hse", ALICE, ALICE, 9, at=NOW - 3600), "alice")))
    out.append(dv("hint-id-already-seen", "A hint whose id the receiver has already seen is not a duplicate-id rejection: hint ids are "
                  "not deduplicated, §8.3 decides a re-observed hint (§12.9, spec-gap 141).", ["§12.9", "§8.3"], held,
                  accept(type="reachability-hint", signer=ALICE, identity=ALICE, winner="input", conflict="none"),
                  ctx=default_context(seen_ids=[hint("hh", ALICE, ALICE, 3, at=NOW - 1000)["id"]])))
    from .key_agreement import hint_vectors
    out += hint_vectors(hint, dv, accept)
    return out
