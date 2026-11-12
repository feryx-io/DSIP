#!/usr/bin/env python3
"""Differential fuzzing: random traces through all three implementations, actual against actual.

Passing the conformance suite is not agreement (impl/docs/spec-gaps.md, spec-gaps 78, 80, 81): a
vector exercises one rule at a time, and two implementations can satisfy every vector and still
answer differently when two rules apply at once. This tool generates random, well-formed event
traces for the state machines and random rows for the table-shaped rules, runs them through the
Python harness, the Rust runner and `impl-ts`, and compares what each *computed* — there is no
expected value, only agreement.

    python3 impl/tools/fuzz.py                          # every target, seed 1, 200 probes each
    python3 impl/tools/fuzz.py --target hub,mailbox --seed 7 --count 500
    python3 impl/tools/fuzz.py --seed random --out /tmp/found   # keep reproducers

A divergence is shrunk (events are dropped while the three still disagree) and printed with what
each side answered at the first step that differs. It is never fixed here: it becomes a
hand-authored vector in `dsipvec/gen/`, with the expectation taken from the spec — or a spec-gap
when the spec does not say. Probes live in a temporary directory; nothing is written to
`impl/vectors`. Exit status 1 on any divergence or runner failure.

Build first: `impl/tools/dsip-rs.sh`, then `cargo build -p dsip-cli` in `dsip-rs/` (its environment from
`impl/tools/dsip_rs.py`: `DSIP_SPEC` and `DSIP_VECTORS` naming this checkout), `npm ci && npm run build` in `impl-ts/`.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "impl" / "tools"))

import dsip_rs  # noqa: E402
NOW = 1760000000

# ---------------------------------------------------------------- the cast

ALICE, BOB, CAROL, MALLORY = ("did:web:alice.example", "did:web:example.com:users:bob", "did:web:carol.example",
                              "did:web:mallory.example")
A1, A2, B1, B2, C1, M1 = ("did:key:z6MkA1", "did:key:z6MkA2", "did:key:z6MkB1", "did:key:z6MkB2", "did:key:z6MkC1",
                          "did:key:z6MkM1")
DEVICES = {ALICE: [A1, A2], BOB: [B1, B2], CAROL: [C1], MALLORY: [M1]}
IDENTITY = {d: i for i, ds in DEVICES.items() for d in ds}
HUB_A, HUB_B, ROGUE, RELAY = ("did:web:mbx.alice.example", "did:web:mbx.bob.example", "did:web:rogue.example",
                              "did:web:relay.example.com")
G1, G2 = "MDFLNzQyU0cwMEhBWlpDS0MxMzFFQzBQR1M", "MDFLNzQyU0cwMDVCWTdRQzVDQkg4MUdSUVQ"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid(n: int) -> str:
    """A well-formed ULID whose order follows `n` (what glare and update collisions compare)."""
    tail = ""
    for _ in range(16):
        tail = CROCKFORD[n % 32] + tail
        n //= 32
    return "01K742SG00" + tail


def cursor(n: int) -> str:
    return "c:%016x" % n


# ---------------------------------------------------------------- generators: (kind, check, context, events)
# Every generator returns well-formed events only: the question is what the machines *decide*, not
# how they fail on malformed input (that is the envelope pipeline's job, and the vectors cover it).


def gen_gap(r: random.Random):
    ev = []
    for _ in range(r.randint(3, 10)):
        if r.random() < 0.25:
            ev.append({"advance": r.choice([1, 100, 200, 299, 300])})
        else:
            ev.append({"item": {"seq": r.randint(1, 7), "class": r.choice(["application", "handshake"])}})
    ctx = {"component": "gap", "now": NOW, "contiguous": r.choice([0, 0, 2])}
    if r.random() < 0.3:
        ctx["gap_timeout"] = r.choice([5, 100])
    return "messaging", "gap-trace", ctx, ev


def gen_commit_retry(r: random.Random):
    """Only sequences a device can meet: an answer, then — when the machine would be syncing — a `synced`."""
    retried = ["mailbox.commit-conflict", "mailbox.stale-epoch", "mailbox.unknown-group", "mailbox.hub-draining", "mailbox.odd"]
    final = ["policy.blocked", "mailbox.quota-exceeded", "x-hubs.overloaded"]
    ev = []
    for _ in range(r.randint(1, 5)):
        reason = r.choice(retried + retried + final + [None])
        ev.append({"answer": {} if reason is None else {"reason": reason}})
        if reason is None or reason in final:
            break  # merged, or surfaced: the operation is over
        synced = {"still_needed": r.random() < 0.85}
        if reason == "mailbox.unknown-group" or r.random() < 0.2:
            synced["hub_moved"] = r.random() < 0.7
        ev.append({"synced": synced})
        if not synced["still_needed"] or (reason == "mailbox.unknown-group" and not synced.get("hub_moved")):
            break
    return "messaging", "commit-retry-trace", {"component": "commit-retry", "max_attempts": 3}, ev


def gen_hub_outage(r: random.Random):
    ids, ev, dep = [ulid(1), ulid(2), ulid(3)], [], []
    if r.random() < 0.3:
        # straight to an abandoned outbox, where the hand-over retries live (spec-gap 72)
        ev = [{"deposit": {"id": ids[0]}}, {"no_answer": {"id": ids[0]}}, {"advance": 60}]
        for _ in range(r.randint(2, 9)):
            x = r.random()
            ev.append({"handover_failed": {}} if x < 0.45 else {"advance": r.choice([1, 1, 2, 3, 4, 8, 30, 60])} if x < 0.9
                      else {"deposit": {"id": ids[1]}})
        return "messaging", "hub-outage-trace", {"component": "hub-outage", "now": NOW, "hub_timeout": 50}, ev
    for _ in range(r.randint(3, 10)):
        x = r.random()
        if x < 0.3 and len(dep) < 3:
            dep.append(ids[len(dep)])
            ev.append({"deposit": {"id": dep[-1]}})
        elif x < 0.55 or not dep:
            ev.append({"advance": r.choice([1, 2, 4, 30, 60, 100])})
        elif x < 0.67:
            ev.append({"handover_failed": {}})  # spec-gap 72: means something only once abandoned
        else:
            i, c = r.choice(dep), r.random()
            if c < 0.2:
                ev.append({"no_answer": {"id": i}})
            else:
                why = {"reason": r.choice(["mailbox.hub-unreachable", "mailbox.hub-unreachable", "policy.blocked"])} if c < 0.7 else {}
                ev.append({"answer": {"id": i, **why}})
    return "messaging", "hub-outage-trace", {"component": "hub-outage", "now": NOW, "hub_timeout": r.choice([50, 150, 86400])}, ev


def gen_move_arrival(r: random.Random):
    # spec-gap 129: moves, answers from the hubs involved (the new one, the old one, a third), and time across the bound
    hubs = ["did:web:mbx.alice.example", "did:web:mbx.bob.example", "did:web:mbx.carol.example"]
    reasons = ["mailbox.unknown-group"] * 4 + [None, "policy.blocked", "mailbox.hub-unreachable"]
    ev = [{"moved": {"hub": r.choice(hubs)}}] if r.random() < 0.9 else []
    for _ in range(r.randint(2, 14)):
        x = r.random()
        if x < 0.08:
            ev.append({"moved": {"hub": r.choice(hubs)}})
        elif x < 0.4:
            ev.append({"advance": r.choice([1, 2, 4, 9, 10, 11, 60, 299, 300])})
        else:
            reason = r.choice(reasons)
            ev.append({"answer": {"hub": r.choice(hubs), **({} if reason is None else {"reason": reason})}})
    ctx = {"component": "move-arrival", "now": NOW}
    if r.random() < 0.6:
        ctx["arrival_wait"] = r.choice([0, 1, 10, 30])
    return "messaging", "move-arrival-trace", ctx, ev

def gen_enrolment(r: random.Random):
    # spec-gap 130: owner operations, releases, operator releases (spec-gap 164) and hellos from configured, enrolled
    # and unknown identities, and time across the idle bound, with the bound and expiry varied
    ids = ["did:web:alice.example", "did:key:z6MkBob", "did:key:z6MkCarol", "did:key:z6MkDave", "did:key:z6MkErin"]
    ev = []
    for i in range(r.randint(2, 16)):
        x, who = r.random(), r.choice(ids)
        if x < 0.45:
            ev.append({"owner_op": {"identity": who, "device": who + "#d", "id": f"op{i}"}})
        elif x < 0.55:
            ev.append({"release": {"identity": who, "device": who + "#d", "id": f"rel{i}"}})
        elif x < 0.63:
            ev.append({"operator_release": {"identity": who}})
        elif x < 0.75:
            ev.append({"hello": {"identity": who}})
        else:
            ev.append({"advance": r.choice([1, 9, 10, 11, 50, 100, 101, 2592000])})
    ctx = {"component": "enrolment", "now": NOW, "configured": r.choice([[], [ids[0]], ids[:2]])}
    if r.random() < 0.85:
        ctx["serve_any"] = r.choice([0, 1, 2, 3])
    if r.random() < 0.6:
        ctx["expire_idle"] = r.choice([True, False])
    if r.random() < 0.7:
        ctx["mls_retention_s"] = r.choice([0, 10, 100])
    return "messaging", "enrolment-trace", ctx, ev

def gen_hub(r: random.Random):
    ev = []
    if r.random() < 0.35:   # spec-gap 128: start moved away, so what follows probes the return
        ev.append({"deposit": {"id": ulid(99), "device": B1, "identity": BOB, "class": "handshake", "digest": "mv", "epoch": 2,
                               "commit": {"adds": [], "removes": [], "moves_to": HUB_B}}})
    for n in range(r.randint(3, 9)):
        x = r.random()
        if x < 0.25:
            ev.append({"ack": {"identity": r.choice([ALICE, BOB, CAROL]), "seq": r.randint(1, 4),
                               **({"class": "welcome"} if r.random() < 0.25 else {})}})
        elif x < 0.3:
            ev.append({"restart": {}})
        elif x < 0.4:
            ev.append({"advance": r.choice([1, 5, 9, 10, 20])})   # spec-gap 119: the retention bound
        else:
            ident = r.choice([ALICE, ALICE, BOB, BOB, CAROL, MALLORY])
            d = r.choice(DEVICES[ident])
            cls = r.choice(["application", "application", "handshake", "handshake", "handshake", "group-info", "ephemeral", "archive"])
            dep = {"id": ulid(100 + n), "device": d, "identity": ident, "class": cls, "digest": r.choice(["dup", "d%d" % r.randint(0, 50)])}
            if cls in ("application", "handshake", "group-info"):
                dep["epoch"] = r.choice([1, 1, 2, 2, 3])
            if cls == "ephemeral":
                dep["expires_at"] = r.choice([NOW - 1, NOW + 10])
            if cls == "group-info" and r.random() < 0.6:   # spec-gap 128: a moved group coming back
                dep["handover_seq"] = r.randint(0, 6)
                dep["view"] = {"epoch": r.choice([3, 4, 5]),
                               "roster": r.choice([{ALICE: [A1, A2], BOB: [B1]}, {ALICE: [A1], CAROL: [C1]}, {BOB: [B1, B2]}])}
            if cls == "handshake" and r.random() < 0.8:
                c, y = {"adds": [], "removes": []}, r.random()
                if y < 0.2:
                    c["adds"] = [{"identity": CAROL, "device": C1}]
                elif y < 0.3:
                    c["adds"] = [{"identity": BOB, "device": B2}]
                elif y < 0.4:
                    c["removes"] = [{"identity": BOB, "device": B1}]
                elif y < 0.5:
                    c["removes"] = [{"identity": ALICE, "device": A1, **({"delegation_valid": False} if r.random() < 0.5 else {})}]
                elif y < 0.6:
                    c.update({"external": True, "adds": [{"identity": ident, "device": d}]})
                elif y < 0.72:
                    c["moves_to"] = HUB_B
                elif y < 0.77:
                    c["valid"] = False
                dep["commit"] = c
            ev.append({"deposit": dep})
    ctx = {"component": "hub", "hub": HUB_A, "group": G1, "kind": "group", "now": NOW, "epoch": 2,
           "roster": {ALICE: [A1, A2], BOB: [B1]}}
    if r.random() < 0.6:
        ctx["mls_retention_s"] = r.choice([10, 20])
    return "messaging", "hub-trace", ctx, ev


def gen_mailbox(r: random.Random):
    grant_id, sent = ulid(900), ulid(901)
    ev = []
    for n in range(r.randint(4, 12)):
        x, g, i = r.random(), r.choice([G1, G1, G2]), ulid(200 + n)
        if x < 0.30:
            cls = r.choice(["application", "application", "handshake", "group-info", "ephemeral"])
            d = {"id": i, "from": r.choice([HUB_A, HUB_A, HUB_A, HUB_B, ROGUE]), "recipient": BOB, "group": g,
                 "seq": None if cls in ("group-info", "ephemeral") else r.randint(1, 5), "class": cls}
            if cls == "ephemeral" and r.random() < 0.5:
                d["expires_at"] = r.choice([NOW - 1, NOW + 500])
            ev.append({"hub_deposit": d})
        elif x < 0.42:
            grant = r.choice([None, {"id": grant_id, "from": BOB, "to": r.choice([CAROL, ALICE]),
                                     "scope": r.choice([["dsip.message"], ["dsip.invite"], ["dsip.subscribe"]]),
                                     "valid_until": r.choice([NOW - 10000, NOW + 86400])}])
            ev.append({"welcome": {"id": i, "from": C1, "adder_identity": r.choice([CAROL, CAROL, BOB]),
                                   "recipient": r.choice([BOB, BOB, BOB, ALICE]), "group": g, "hub": HUB_A, "grant": grant,
                                   "digest": r.choice(["w1", "w2"])}})
        elif x < 0.52:
            y = r.random()
            if y < 0.2:
                c = {"id": i, "device": B1, "revoked_grants": [grant_id]}
            elif y < 0.35:
                c = {"id": i, "device": B1, "introductions_sent": [sent]}
            else:
                grp = {"group": g, "state": r.choice(["joined", "joined", "left"])}
                if r.random() < 0.5:
                    grp.update({"hub": HUB_B, "handover_seq": r.randint(1, 3)})
                c = {"id": i, "device": B1, "groups": [grp]}
            ev.append({"config": c})
        elif x < 0.64:
            s = {"id": i, "device": r.choice([B1, B2]), "since": r.choice([None, None, cursor(1), cursor(2), cursor(9)])}
            if r.random() < 0.5:
                s["live"] = True
            if r.random() < 0.4 and s["since"]:
                s["ack_through"] = s["since"]
            if r.random() < 0.2:
                s["limit"] = 1
            ev.append({"sync": s})
        elif x < 0.74:
            ev.append({"advance": r.choice([1, 100, 299, 300, 301, 604800])})
        elif x < 0.78:
            ev.append({"restart": {}})
        elif x < 0.84:
            ev.append({"archive": {"id": i, "device": r.choice([B1, B2]), "ref_group": G1, "ref_seq": r.randint(1, 2)}})
        elif x < 0.90:
            ev.append({"forward": {"id": i, "device": r.choice([B1, C1]), "identity": r.choice([BOB, BOB, CAROL]), "group": g,
                                   "to": r.choice([HUB_A, HUB_B])}})
        elif x < 0.94:
            ev.append({"kp_fetch": {"id": i, "from": C1, "from_identity": r.choice([CAROL, BOB]), "target": BOB, "grant": None,
                                    **({"successor_of": g} if r.random() < 0.4 else {})}})
        else:
            kind = r.choice(["introduction", "introduction", "grant", "grant"])
            fc = {"id": i, "from": C1, "sender_identity": r.choice([CAROL, ALICE]),
                  "recipient": r.choice([BOB, BOB, "did:web:nobody.example"]), "kind": kind, "expires_at": NOW + r.choice([30, 600])}
            if kind == "grant" and r.random() < 0.6:
                fc["session"] = r.choice([sent, ulid(999)])
            ev.append({"first_contact": fc})
    ctx = {"component": "mailbox", "mailbox": HUB_B, "owner": BOB, "serves": [BOB], "devices": [B2, B1], "now": NOW,
           "mode": r.choice(["sync", "sync", "queue"]), "admit": r.choice(["grant", "grant", "grant", "open"]),
           "pending_group_ttl": 604800, "pending_group_max_items": 2,
           "groups": r.choice([{}, {G1: {"hub": HUB_A, "state": "joined"}}, {G1: {"hub": HUB_A, "state": "joined"}}]),
           "key_packages": r.choice([{}, {B1: {"one_time": 1, "last_resort": True}, B2: {"one_time": 0, "last_resort": False}}]),
           "intro_limit": 2, "intro_window": 3600, "inbox_cap": 3}
    return "messaging", "mailbox-trace", ctx, ev


def gen_resume(r: random.Random):
    ev, n = [], 0
    limit = r.choice([None, None, 1, 2, 7, 200])  # the device's own limit (spec-gap 180); too_large needs one stated
    resyncs = ["sync", "restart", "cursor_invalid"] + (["too_large", "too_large"] if limit is not None else [])
    for _ in range(r.randint(2, 7)):
        x = r.random()
        if x < 0.55:
            items = []
            for _ in range(r.randint(1, 4)):
                n += 1
                cls = r.choice(["application", "application", "application", "welcome", "group-info"])
                it = {"cursor": cursor(n), "class": cls, "group": r.choice([G1, G1, G2])}
                if cls == "application":
                    it["seq"] = r.randint(1, 6)
                if cls == "welcome" and r.random() < 0.3:
                    it["sibling"] = True
                if cls == "welcome" and r.random() < 0.5:
                    it["seq"] = r.randint(1, 5)  # the adding commit's seq: where the device starts counting (spec-gap 83)
                items.append(it)
            body = {"items": items}
            if r.random() < 0.2:
                body["crash_at"] = r.choice(items)["cursor"]
            ev.append({"items": body})
        elif x < 0.65:
            ev.append({"sent": {"group": G1, "seq": r.randint(1, 6)}})
        elif x < 0.72:
            ev.append({"rejoined": {"group": G1, "seq": r.randint(1, 6)}})
        elif x < 0.78:
            ev.append({"removed": {"group": r.choice([G1, G2])}})  # spec-gap 127
        else:
            ev.append({r.choice(resyncs): {}})
    ctx = {"component": "resume", "cursor": None, "groups": {}, "joined": []}
    if limit is not None:
        ctx["limit"] = limit
    return "messaging", "resume-trace", ctx, ev


def gen_history(r: random.Random):
    keys, ev, n = [ulid(500), ulid(501)], [], 0
    for _ in range(r.randint(3, 9)):
        x, seq = r.random(), r.randint(1, 5)
        obj = r.choice([None, None, None, "receipt", "call-event"])
        ident = "%s%d" % ("m" if obj is None else obj[0], seq)
        extra = {} if obj is None else {"object": obj}
        if x < 0.35:
            n += 1
            ev.append({"archive": {"cursor": cursor(n), "akid": r.choice(keys), "group": G1, "seq": seq, "id": ident, **extra}})
        elif x < 0.5:
            k = r.choice(keys)
            ev.append({"archive_key": {"akid": k, "created_at": NOW + (60 if k == keys[1] else 0)}})
        elif x < 0.75:
            ev.append({"mls": {"group": G1, "seq": seq, "epoch": r.randint(1, 4), "id": "m%d" % seq}})  # content only (README)
        elif x < 0.9:
            ev.append({"sent": {"group": G1, "seq": seq, "id": ident, **extra}})
        else:
            ev.append({"joined": {"group": G1, "epoch": r.randint(1, 4)}})
    ctx = {"component": "history", "keys": r.choice([[], [{"akid": keys[0], "created_at": NOW}]]), "joined": {}}
    return "messaging", "history-trace", ctx, ev


def gen_successor(r: random.Random):
    import base64
    gid = lambda u: base64.urlsafe_b64encode(u.encode()).decode().rstrip("=")
    cands = [gid(ulid(n)) for n in (610, 620, 630)] + ["bm90LWEtdWxpZA"]
    pred, roster = G1, [ALICE, BOB, CAROL]
    member = r.random() < 0.75
    ev, created, seen = [], False, False
    for _ in range(r.randint(2, 6)):
        if r.random() < 0.7:
            w = {"group": r.choice(cands), "successor_of": r.choice([pred, pred, G2]), "creator": r.choice([BOB, CAROL, MALLORY]),
                 "roster": r.choice([roster, roster, [ALICE, BOB], [ALICE, BOB, MALLORY]])}
            seen = seen or (member and w["successor_of"] == pred and w["creator"] != MALLORY and MALLORY not in w["roster"]
                            and w["group"] != cands[3])
            ev.append({"welcome": w})
        else:
            ev.append({"create": {"predecessor": r.choice([pred, pred, G2])}})
            # the device creates the group only when the machine said `create`: a member, with no successor yet, once
            if ev[-1]["create"]["predecessor"] == pred and member and not seen and not created:
                created = True
                ev.append({"created": {"group": r.choice(cands[:3]), "successor_of": pred}})
                seen = True
    return "messaging", "successor-trace", {"component": "successor", "groups": {pred: roster} if member else {}}, ev


def gen_client(r: random.Random):
    ids = [ulid(700 + k) for k in range(4)]
    me = r.choice([ALICE, BOB])
    ev, seq = [], 0
    for _ in range(r.randint(3, 9)):
        x = r.random()
        if x < 0.45:
            items = []
            for _ in range(r.randint(1, 3)):
                seq += 1
                if r.random() < 0.55:
                    items.append({"seq": seq, "object": {"object": "content", "id": r.choice(ids), "sender": r.choice([ALICE, BOB]),
                                                        "kind": r.choice(["text", "text", "audio"])}})
                else:
                    kind = r.choice(["delivered", "read", "played"])
                    body = {"through": r.choice(ids)} if kind == "read" else {"targets": r.sample(ids, r.randint(1, 2))}
                    items.append({"seq": seq, "object": {"object": "receipt", "kind": kind, "sender": r.choice([ALICE, BOB, CAROL]),
                                                        "sent_at": NOW + seq, **body}})
            ev.append({r.choice(["sync", "sync", "sync", "restore"]): {"items": items}})
        elif x < 0.6:
            ev.append({"read": {"through": r.choice(ids)}})
        elif x < 0.7:
            ev.append({"play": {"id": r.choice(ids)}})
        elif x < 0.8:
            ev.append({"activity": {"activity": r.choice(["typing", "uploading"]), "state": r.choice(["active", "active", "stopped"])}})
        elif x < 0.9:
            ev.append({"activity_in": {"sender": r.choice([ALICE, CAROL]), "activity": r.choice(["typing", "uploading"]),
                                       "state": r.choice(["active", "active", "stopped"]), "expires_at": NOW + r.choice([-5, 5, 10, 20])}})
        else:
            ev.append({"advance": r.choice([1, 3, 5, 6, 11])})
    ctx = {"component": "client", "me": me, "device": DEVICES[me][0], "now": NOW, "member_identities": r.choice([2, 2, 33]),
           "policy": {k: r.random() < 0.6 for k in ("delivered", "read", "played", "activity")}}
    return "messaging", "client-trace", ctx, ev


REASONS = ["user.declined", "user.no-answer", "endpoint.busy", "endpoint.unavailable", "session.glare", "policy.blocked",
           "user.stepped-out", "x-cc.queue-full"]


def gen_endpoint(r: random.Random):
    """One endpoint (Alice's phone), two possible sessions each way, every local and remote event."""
    out_ids, in_ids, upd = [ulid(10), ulid(30)], [ulid(20), ulid(5)], [ulid(40 + k) for k in range(4)]
    intro_ids, grant_ids = [ulid(50), ulid(51)], [ulid(60), ulid(61)]
    sessions = out_ids + in_ids
    ev, clock, counter = [], NOW, [1000]
    fresh_in = list(in_ids)  # an invite id arrives once: the replay stage drops a repeated id before the engine sees it (§12.9)

    def mid() -> str:
        counter[0] += 1
        return ulid(counter[0])

    for _ in range(r.randint(3, 12)):
        x, sid = r.random(), r.choice(sessions)
        peer = r.choice([B1, B1, B2, C1])
        if x < 0.12:
            ev.append({"local": "place_call", "session": r.choice(out_ids), "to": r.choice([BOB, BOB, B1])})
        elif x < 0.22 and fresh_in:
            # a received message has passed the envelope pipeline, so an invite is never expired on arrival (README, `recv`);
            # it may expire later, before the user is alerted
            ev.append({"recv": {"type": "invite", "id": fresh_in.pop(r.randrange(len(fresh_in))), "from": peer, "to": ALICE,
                                "expires_at": clock + r.choice([3, 30, 30]), **({"grant": r.choice(grant_ids)} if r.random() < 0.2 else {})}})
        elif x < 0.32:
            st = r.choice(["ringing", "ringing", "trying", "queued", "forwarded", "levitating"])
            m = {"type": "progress", "id": mid(), "from": peer, "session": sid, "status": st}
            if st == "ringing" and r.random() < 0.5:
                m["ring_timeout"] = r.choice([10, 60, 500])
            if st == "queued":
                m["queue_timeout"] = r.choice([30, 5000])
            ev.append({"recv": m})
        elif x < 0.42:
            m = {"type": "answer", "id": mid(), "from": peer, "session": sid, "answered_by": r.choice(["user", "screening", "butler"])}
            if r.random() < 0.3:
                m["in_reply_to"] = r.choice(upd)
            ev.append({"recv": m})
        elif x < 0.50:
            m = {"type": "reject", "id": mid(), "from": peer, "session": r.choice(sessions + intro_ids), "reason": r.choice(REASONS)}
            if r.random() < 0.3:
                m["in_reply_to"] = r.choice(upd)
            ev.append({"recv": m})
        elif x < 0.57:
            ev.append({"recv": {"type": r.choice(["cancel", "bye"]), "id": mid(), "from": peer, "session": sid,
                                "reason": r.choice(["user.cancelled", "session.timeout", "session.answered-elsewhere", "user.hangup"])}})
        elif x < 0.62:
            ev.append({"recv": {"type": "error", "id": mid(), "from": r.choice([RELAY, peer]), "session": sid,
                                "reason": r.choice(["transport.no-response", "policy.rate-limited"])}})
        elif x < 0.67:
            upd.append(mid())  # a received update has an id of its own; later replies may name it
            ev.append({"recv": {"type": "update", "id": upd[-1], "from": peer, "session": sid,
                                **({"answered_by": "user"} if r.random() < 0.3 else {})}})
        elif x < 0.71:
            ev.append({"recv": {"type": "info", "id": mid(), "from": peer, "session": sid,
                                "about": r.choice(["transport:webrtc", "media:dtmf", "x-vendor:thing"])}})
        elif x < 0.76:
            ev.append({"local": r.choice(["cancel", "hangup", "decline", "info"]), "session": sid})
        elif x < 0.81:
            ev.append({"local": "alert", "session": sid, **({"ring_timeout": 45} if r.random() < 0.3 else {})})
        elif x < 0.85:
            ev.append({"local": "accept", "session": sid, "answered_by": r.choice(["user", "screening"])})
        elif x < 0.88:
            ev.append({"local": "auto_reject", "session": sid, "reason": r.choice(["endpoint.busy", "policy.blocked"])})
        elif x < 0.92:
            y = r.random()
            if y < 0.5:
                ev.append({"local": "update", "session": sid, "id": r.choice(upd)})
            elif y < 0.8:
                ev.append({"local": "answer_update", "session": sid, "in_reply_to": r.choice(upd)})
            else:
                ev.append({"local": "reject_update", "session": sid, "in_reply_to": r.choice(upd), "reason": "media.unsupported"})
        elif x < 0.96:
            y = r.random()
            if y < 0.3:
                ev.append({"recv": {"type": "introduction", "id": r.choice(intro_ids), "from": C1, "to": ALICE, "purpose": "hi",
                                    **({"contact_token": "tok"} if r.random() < 0.4 else {})}})
            elif y < 0.45:
                ev.append({"local": "issue_token", "token": "tok", "grant_id": grant_ids[1]})
            elif y < 0.6:
                ev.append({"local": "grant", "introduction": r.choice(intro_ids), "id": grant_ids[0], "scope": ["dsip.invite"],
                           "valid_until": NOW + r.choice([-10, 100000])})
            elif y < 0.7:
                ev.append({"local": "reject_introduction", "introduction": r.choice(intro_ids), "reason": "user.declined"})
            elif y < 0.8:
                ev.append({"local": "revoke", "grant": r.choice(grant_ids)})
            elif y < 0.85:
                ev.append({"local": "introduce", "id": intro_ids[0], "to": BOB, "purpose": "hello"})
            elif y < 0.92:
                # spec-gap 150: a grant that follows a grant; its session may name an introduction or a held grant
                ev.append({"recv": {"type": "grant", "id": r.choice(grant_ids), "from": r.choice([B1, B1, B2, C1]),
                                    "session": r.choice(intro_ids + grant_ids),
                                    # spec-gap 151: an invite names only a live dsip.invite grant held from the callee
                                    "scope": r.choice([["dsip.invite"], ["dsip.invite"], ["dsip.subscribe"]]),
                                    "valid_until": NOW + r.choice([60, 100000])}})
            else:
                ev.append({"local": "regrant", "grant": r.choice(grant_ids), "id": r.choice(grant_ids),
                           "scope": r.choice([["dsip.invite"], ["dsip.invite", "dsip.subscribe"]]),
                           "valid_until": NOW + r.choice([-10, 100000]),
                           **({"presence_audience": r.choice(["family", "Family"])} if r.random() < 0.3 else {})})
        else:
            ev.append({"advance": r.choice([1, 5, 15, 30, 120, 121])})
            clock += ev[-1]["advance"]
    ctx = {"component": "endpoint", "self": {"device": A1, "identity": ALICE}, "identities": dict(IDENTITY), "start": NOW}
    if r.random() < 0.3:
        ctx["policy"] = {"first_contact_required": True, "allow": r.choice([[], [BOB]])}
    snapshot = {"sessions": {s: {} for s in sessions}, "contacts": {}}
    return "state", None, ctx, [(e, snapshot) for e in ev]


def gen_presence_keys(r: random.Random):
    """Alice's phone issuing presence grants with keys, ending them by revocation, by a following grant and at their
    valid_until, rotating within T-Presence-Rotate, re-granting on a sibling's epoch; and holding keys from Bob's grants
    (P§12.3–P§12.5, spec-gaps 159, 161)."""
    tags = ["k-family", "k-work"]
    intro_ids, grant_ids = [ulid(50 + k) for k in range(4)], [ulid(60 + k) for k in range(5)]
    held_ids, sent_intro = [ulid(80 + k) for k in range(3)], ulid(90)
    pool = [ulid(200 + k) for k in range(60)]
    ev, counter = [{"local": "introduce", "id": sent_intro, "to": BOB, "purpose": "hi"}], [1000]

    def mid() -> str:
        counter[0] += 1
        return ulid(counter[0])

    def kid() -> str:
        return f"{r.choice(['main'] + tags)}.{r.choice([0, 1, 2, 3, 7])}"

    for _ in range(r.randint(6, 24)):
        x = r.random()
        scope = r.choice([["dsip.subscribe"], ["dsip.invite", "dsip.subscribe"], ["dsip.invite"]])
        audience = r.choice([None, None] + tags + ["k-other"])
        extra = {"presence_audience": audience} if audience else {}
        if x < 0.14:
            ev.append({"recv": {"type": "introduction", "id": r.choice(intro_ids), "from": r.choice([B1, C1, M1]), "to": ALICE,
                                "purpose": "hi"}})
        elif x < 0.34:
            # an introduction granted at once, so most grants find their request
            i = mid() if r.random() < 0.8 else r.choice(intro_ids)
            ev.append({"recv": {"type": "introduction", "id": i, "from": r.choice([B1, C1, M1]), "to": ALICE, "purpose": "hi"}})
            ev.append({"local": "grant", "introduction": i, "id": r.choice(grant_ids), "scope": scope,
                       "valid_until": NOW + r.choice([20, 60, 100, 100000, 100000]), **extra})
        elif x < 0.44:
            ev.append({"local": "revoke", "grant": r.choice(grant_ids + pool[:8])})
        elif x < 0.54:
            ev.append({"local": "regrant", "grant": r.choice(grant_ids + pool[:8]), "id": r.choice(grant_ids), "scope": scope,
                       "valid_until": NOW + r.choice([30, 100000]), **extra})
        elif x < 0.62:
            m = {"type": "presence", "id": mid(), "from": r.choice([A2, A2, B1]), "subject": r.choice([ALICE, ALICE, BOB])}
            if r.random() < 0.85:
                m["kid"] = kid()
            ev.append({"recv": m})
        elif x < 0.74:
            ev.append({"recv": {"type": "grant", "id": r.choice(held_ids), "from": B1, "session": r.choice([sent_intro] + held_ids),
                                "scope": ["dsip.subscribe"], "valid_until": NOW + 100000,
                                "presence_keys": [kid() for _ in range(r.randint(1, 2))]}})
        else:
            ev.append({"advance": r.choice([1, 5, 19, 20, 40, 59, 60, 61, 300])})
    ctx = {"component": "endpoint", "self": {"device": A1, "identity": ALICE}, "identities": dict(IDENTITY), "start": NOW}
    if r.random() < 0.9:
        ctx["presence_keys"] = {"sealed": r.sample(["main"] + tags, r.randint(0, 3)), "grant_ids": pool,
                                **({"t_rotate": r.choice([0, 1, 30, 60, 5000, -5])} if r.random() < 0.6 else {})}
    snapshot = {"contacts": {}, "presence_keys": {}}
    return "state", None, ctx, [(e, snapshot) for e in ev]


def gen_relay(r: random.Random):
    """Every message carries `to`, as every real envelope does (the schemas require it)."""
    sids = [ulid(10), ulid(11)]
    ev, counter, introduced = [], [1000], set()  # an invite id arrives once: the replay stage drops a repeated id (§12.9)

    def mid() -> str:
        counter[0] += 1
        return ulid(counter[0])

    for _ in range(r.randint(3, 10)):
        x, sid = r.random(), r.choice(sids)
        if x < 0.2:
            ev.append({"relay": r.choice(["bind", "bind", "unbind"]), "device": r.choice([B1, B2, A1]), "identity": None})
            ev[-1]["identity"] = IDENTITY[ev[-1]["device"]]
        elif x < 0.42 and sid in introduced:
            ev.append({"advance": r.choice([1, 5])})
        elif x < 0.35:
            introduced.add(sid)
            ev.append({"recv": {"type": "invite", "id": sid, "from": A1, "to": r.choice([BOB, BOB, "did:web:nobody.example"]),
                                "expires_at": NOW + r.choice([30, 30, 2])}})
        elif x < 0.42:
            introduced.add(sid)
            ev.append({"relay": "invite", "session": sid, "from": A1, "to": BOB, "legs": [B1, B2]})
        elif x < 0.52:
            ev.append({"recv": {"type": "progress", "id": mid(), "from": r.choice([B1, B2]), "session": sid, "to": A1, "status": "ringing"}})
        elif x < 0.62:
            ev.append({"recv": {"type": "answer", "id": mid(), "from": r.choice([B1, B2]), "session": sid, "to": A1, "answered_by": "user"}})
        elif x < 0.72:
            ev.append({"recv": {"type": "reject", "id": mid(), "from": r.choice([B1, B2]), "session": sid, "to": A1,
                                "reason": r.choice(REASONS)}})
        elif x < 0.8:
            ev.append({"recv": {"type": "cancel", "id": mid(), "from": A1, "session": sid,
                                "reason": r.choice(["user.cancelled", "session.answered-elsewhere"]),
                                "to": r.choice([BOB, BOB, B1])}})
        elif x < 0.86:
            ev.append({"relay": "leg_expired", "session": sid, "leg": r.choice([B1, B2])})
        elif x < 0.92:
            ev.append({"recv": {"type": "introduction", "id": mid(), "from": C1,
                                "to": r.choice([BOB, "did:web:nobody.example"]), "purpose": "hi", "expires_at": NOW + 600}})
        elif x < 0.96:
            ev.append({"recv": {"type": r.choice(["bye", "info", "update"]), "id": mid(), "from": A1, "session": sid,
                                "to": r.choice([B1, B2]), "reason": "user.hangup", "about": "transport:webrtc", "expires_at": NOW + 60}})
        else:
            ev.append({"advance": r.choice([1, 5, 31, 700, 1800, 1801])})  # 1800/1801: the attempt idle cap (spec-gap 131)
    ctx = {"component": "relay", "start": NOW}
    if r.random() < 0.3:
        ctx["offline_retention_s"] = 10
    snapshot = {"attempts": {s: {} for s in sids}, "inbox": {}}
    return "state", None, ctx, [(e, snapshot) for e in ev]


def gen_deposit_fields(r: random.Random):
    """One table row: a deposit class with one extra field (spec-gap 80)."""
    mls, blob = "bWxz", {"uri": "https://mbx.alice.example/blobs/" + "9f" * 32, "sha256": "9f" * 32, "size": 10}
    base = {"dsip": {"core": "1.0", "min_core": "1.0", "profiles": ["messaging/1.0"], "extensions": [], "critical": []},
            "type": "deposit", "id": ulid(1), "from": A1, "to": HUB_A, "issued_at": NOW, "expires_at": NOW + 30}
    classes = {
        "handshake": {"group": G1, "mls": mls}, "application": {"group": G1, "mls": mls},
        "welcome": {"group": G1, "mls": mls, "hub": {"did": HUB_A, "uri": "wss://mbx.alice.example/dsip"}},
        "group-info": {"group": G1, "mls": mls}, "ephemeral": {"group": G1, "sealed": "c2VhbGVk"},
        "archive": {"group": G1, "archive": "YXJj", "akid": ulid(2), "ref_group": G1, "ref_seq": 1},
    }
    extras = {"welcome": mls, "group_info": mls, "ratchet_tree_blob": blob, "grants": ["eyJ.g.s"], "seq": 5, "blobs": [blob],
              "recipient": BOB, "hub": {"did": HUB_A, "uri": "wss://mbx.alice.example/dsip"}, "origin": "eyJ.o.s", "successor_of": G2,
              "handover_seq": 3, "sealed": "c2VhbGVk", "archive": "YXJj", "akid": ulid(2), "ref_group": G1, "ref_seq": 1, "mls": mls}
    cls = r.choice(list(classes))
    p = {**base, "class": cls, **classes[cls]}
    for f in r.sample(list(extras), r.randint(0, 2)):
        p.setdefault(f, extras[f])
    return "messaging", "message", {}, {"payload": p}


def gen_gateway_reason(r: random.Random):
    if r.random() < 0.5:
        inp = {"check": "reason-inbound", "phase": r.choice(["pre-answer", "active", "transport"])}
        if r.random() < 0.7:
            inp["sip_status"] = r.choice([403, 404, 408, 410, 415, 480, 484, 486, 487, 488, 500, 502, 503, 504, 600, 603, 604, 606, 699])
        if r.random() < 0.6:
            inp["q850"] = r.choice([1, 16, 17, 18, 19, 20, 21, 22, 28, 31, 34, 38, 41, 42, 47, 63, 65, 79, 99, 102])
        if r.random() < 0.15:
            inp["moved_to"] = "tel:+15557654321"
        return "gateway", None, {}, inp
    tokens = ["user.declined", "user.blocked", "user.no-answer", "user.cancelled", "user.hangup", "endpoint.busy", "endpoint.unavailable",
              "endpoint.capability", "identity.not-in-service", "identity.moved", "identity.suspended", "identity.unknown",
              "session.expired", "session.timeout", "session.failed", "session.cancelled", "media.unsupported", "media.failed",
              "policy.blocked", "policy.rate-limited", "policy.terminated", "transport.unknown-recipient", "transport.no-response",
              "gateway.unreachable", "gateway.mapped", "mailbox.quota-exceeded", "user.stepped-out", "endpoint.on-fire",
              "identity.odd", "media.odd", "policy.odd", "transport.odd", "gateway.odd", "x-cc.queue-full"]
    return "gateway", None, {}, {"check": "reason-outbound", "reason": r.choice(tokens), "phase": r.choice(["pre-answer", "active"])}


SYSLOG_SEEDS = [
    b"<34>1 2003-10-11T22:14:15.003Z mymachine.example.com su - ID47 - \xef\xbb\xbf'su root' failed",
    b'<165>1 2003-10-11T22:14:15.003Z host evntslog - ID47 [exampleSDID@32473 iut="3" eventSource="App\\"x\\]"] msg',
    b"<14>1 - - - - - -", b"<13>Oct  5 12:00:00 host sshd[1234]: hello\r\n", b"<189>123: *Mar  1 18:46:11: %LINK-3-UPDOWN: x",
    b"<34>Oct 11 22:14:15 mymachine su: 'su root' failed", b"<0>", b"<191>app: m",
]


def mutate(r: random.Random, b: bytes, alphabet: bytes) -> bytes:
    b = bytearray(b)
    for _ in range(r.randint(1, 3)):
        op = r.random()
        i = r.randint(0, len(b)) if b else 0
        if op < 0.35 and b:
            b[min(i, len(b) - 1)] = r.choice(alphabet)
        elif op < 0.6:
            b[i:i] = bytes([r.choice(alphabet)])
        elif op < 0.85 and b:
            del b[min(i, len(b) - 1)]
        else:
            b = b[:i]
    return bytes(b)


def gen_syslog(r: random.Random):
    """One syslog datagram, a mutation of a real-world shape (E§3; the README grammar)."""
    alphabet = b' <>-[]="\\:0123456789abcAZ\t\r\n\x00\xff\xc3\xef\xbb\xbf@.'
    d = mutate(r, r.choice(SYSLOG_SEEDS), alphabet) if r.random() < 0.9 else r.choice(SYSLOG_SEEDS)
    return "device-events", "syslog", {}, {"datagram": d.hex()}


def gen_snmpv3(r: random.Random):
    """A USM receiver trace: valid, tampered and replayed v3 messages with clock advances (E§3, RFC 3414 §3.2)."""
    from dsipvec.gen import events_v3 as g
    users = [g.user(), g.user("p", "sha256", "aes128"), g.user("k", engine=g.DEV, keys=True)]
    ctx = g.ctx(users, local_boots=r.choice([1, 7]), local_time=500)
    steps, sent = [], []
    for _ in range(r.randint(2, 8)):
        x = r.random()
        if x < 0.15:
            steps.append({"advance": r.choice([1, 60, 149, 150, 151, 400])})
            continue
        if x < 0.25 and sent:
            d = r.choice(sent)
        else:
            engine = r.choice([g.DEV, g.DEV2, g.LOCAL])
            uname, auth, priv = r.choice([("ops", "sha", False), ("p", "sha256", True), ("k", "sha", False), ("nobody", "md5", False)])
            pdu = g.scoped(tag=r.choice([0xA7, 0xA7, 0xA6, 0xA0]), rid=r.randint(-3, 99))
            d = g.v3(engine=engine, boots=r.choice([0, 1, 5, 7, 2**31 - 1]), time=r.choice([0, 100, 350, 500, 651, 1000]),
                     user=uname, auth=auth, key=g.key(auth, engine), priv_key=g.pkey(auth, engine) if priv else None,
                     pdu=pdu, flags=r.choice([None, None, 0x05, 0x04, 0x02]))
            if r.random() < 0.35:
                d = mutate(r, bytes.fromhex(d), bytes(range(256))).hex()
            sent.append(d)
        steps.append({"receive": {"from": "192.0.2.7:161", "datagram": d}})
    return "device-events", None, ctx, steps


def gen_tsm(r: random.Random):
    """One message from a TLS connection: mutations of real TSM traps, informs and discovery (E§3, v0.10)."""
    from dsipvec.gen import events_v3 as g
    seeds = [bytes.fromhex(x) for x in (g.tsm(), g.tsm(g.scoped(tag=0xA6, rid=9)), g.NETSNMP_TRAP, g.NETSNMP_DISCOVERY,
                                          g.tsm(model=3), g.tsm(flags=0x02))]
    d = r.choice(seeds)
    if r.random() < 0.85:
        d = mutate(r, d, bytes(range(256)))
    return "device-events", "tsm", {}, {"message": d.hex()}


def gen_tls_frames(r: random.Random):
    """A TLS byte stream: whole, cut and corrupted TSM messages back to back (E§3 framing)."""
    from dsipvec.gen import events_v3 as g
    parts = [bytes.fromhex(g.tsm()), bytes.fromhex(g.NETSNMP_DISCOVERY), b"\x30\x82\xff\xfc", b"\x30\x82\xff\xfd",
             b"\x30\x80\x00", b"\x30\x84\x00\x00\x00\x01\x05", b"\x30\x85", b"\xff", b"\x30"]
    s = b"".join(r.choice(parts) for _ in range(r.randint(0, 4)))
    if r.random() < 0.5 and s:
        s = s[:r.randint(0, len(s))]
    return "device-events", "tls-frames", {}, {"stream": s.hex()}


def gen_tsm_name(r: random.Random):
    """RFC 6353's certificate-to-name table: random rows against a random certificate (E§3, v0.10)."""
    leaf, ca, other = "ab" * 32, "cd" * 32, "ef" * 32
    values = {"rfc822": ["Ops@NOC.Example", "a@b@EX.com", "nobody", "x" * 30 + "@E.com", ""],
              "dns": ["SW1.Example.NET", "x" * 33, "ÉX.org", "", "a" * 32],
              "ip": ["c0000207", "0A000001", "20010db8000000000000000000000001", "c00002", "zz", ""],
              "uri": ["https://x.example"]}
    san = [{"type": t, "value": r.choice(values[t])} for t in r.choices(list(values), k=r.randint(0, 4))]
    if r.random() < 0.1 and san:
        san[0]["value"] = 7
    cert = {"sha256": leaf, "chain": r.choice([[ca], [], [ca, other]]), "san": san,
            "cn": r.choice([[], ["sw1"], ["é" * 17, "b"], [7], ["x" * 32]])}
    maps = ["specified", "san-rfc822", "san-dns", "san-ip", "san-any", "common-name", "san-uri"]
    ids = r.sample(range(1, 50), r.randint(0, 5))
    table = []
    for i in ids:
        row = {"id": i, "fingerprint": r.choice([leaf, leaf.upper(), ca, other]), "map": r.choice(maps)}
        if row["map"] == "specified" or r.random() < 0.2:
            v = r.choice(["sw1-core", "", "n" * 32, "n" * 33, "é" * 16, 7, None])
            if v is not None:
                row["data"] = v
        table.append(row)
    return "device-events", "tsm-name", {}, {"certificate": cert, "table": table}


def gen_syslog_sign(r: random.Random):
    """A syslog-sign collector trace: fragments, messages, overlapping/tampered/foreign blocks, clock advances (E§3)."""
    from dsipvec.gen import syslog_sign as g
    msgs = [g.msg(f"port {i} down") for i in range(5)] + [g.msg("x", host="pc.example")]
    # the signer: a K key, or (v0.11) its OpenPGP certificate (P), sometimes one that does not read
    key = r.choice([g.K1] * 6 + [g.KP, g.KP, g.KeyP(g.K1, new_format=True), g.KeyP(g.K1, keyid=b"\x00" * 8)])
    pay = g.payload(key)
    steps = []
    for _ in range(r.randint(3, 12)):
        x = r.random()
        rsid = r.choice([0, 1, 1, 1, 2])
        if x < 0.2:
            cut = r.randint(1, len(pay) - 1)
            idx, fl = r.choice([(1, None), (1, cut), (cut + 1, None)])
            other = r.choice([g.payload(key, ts="2026-10-06T13:00:00Z"), "2026-10-06T12:00:00Z N", "2026-10-06T12:00:00Z U",
                              g.payload(key, kind="U"), g.payload(key, kind=r.choice(["K", "P", "C", "X", "n"])),
                              "2026-10-06T12:00:00Z N x"])
            m = g.cert(key, rsid=rsid, pay=pay if r.random() < 0.8 else other,
                       index=idx, flen=fl, procid=r.choice(["77", "77", "99"]), sign_with=g.K2 if r.random() < 0.1 else None)
        elif x < 0.45:
            m = r.choice(msgs)
        elif x < 0.75:
            k = r.randint(1, 4)
            m = g.sig(key, [r.choice(msgs) for _ in range(k)], rsid=rsid, fmn=r.randint(1, 4), sg=r.choice([0, 0, 1]),
                      spri=r.choice([0, 13]), ver=r.choice(["0111", "0111", "0121"]), sign_with=g.K2 if r.random() < 0.1 else None)
        else:
            steps.append({"advance": r.choice([1, 5, 9, 10, 11])})
            continue
        if r.random() < 0.15:
            m = mutate(r, m, b' "=[]0123456789ABab+/')
        steps.append({"receive": {"message": m.hex()}})
    ctx = {"component": "syslog-sign", "now": 1000, "hold_s": 10, "signers": [key.signer("sw1.example", gaps=r.random() < 0.6)]}
    return "device-events", None, ctx, steps


def gen_recording(r: random.Random):
    """A counterparty's consent trace (Recording Profile C§4): declarations, accepts, declines, answers in any order."""
    recs = ["did:web:rec.acme.example", "did:web:rec2.acme.example"]

    def decl():
        x = r.random()
        if x < 0.2:
            return None
        d = {"state": r.choice(["on", "on", "paused", "off", "streaming"])}
        if d["state"] != "off":
            d["recorder"] = r.choice(recs)
            if r.random() < 0.6:
                d["purpose"] = r.choice(["compliance", "quality"])
        return d
    role = r.choice(["caller", "callee"])
    ctx = {"role": role, "accept": r.choice(["ask", "ask", "always", "never"])}
    steps = []
    first = "invite" if role == "callee" else "answer"
    d = decl()
    steps.append({"received": {"type": first, **({"recording": d} if d else {})}})
    for _ in range(r.randint(1, 8)):
        x = r.random()
        if x < 0.4:
            d = decl()
            steps.append({"received": {"type": "update", **({"recording": d} if d else {})}})
        else:
            steps.append({"local": r.choice(["accept", "accept", "decline", "answer"])})
    return "recording", None, ctx, steps


def gen_call_record(r: random.Random):
    """A call record at the record-keeper (Recording Profile C§9; README `check: "object"`): devices, conversation
    kinds, outcomes and times in every order, some fields missing or malformed."""
    dev, other = "did:key:z6MkAlicePhone", "did:key:z6MkAliceLaptop"
    t = [NOW + r.choice([0, 0, 1, 5, -3]) for _ in range(3)]
    o = {"object": "call-record", "session": ulid(1), "device": r.choice([dev, dev, dev, other]),
         "direction": r.choice(["inbound", "outbound", "outbound", "sideways"]), "peer": BOB,
         "invited_at": t[0], "ended_at": t[2], "outcome": r.choice(["answered", "missed", "cancelled", "forwarded", "Bad"]),
         "ended_by": r.choice(["local", "remote", "transport"])}
    if r.random() < 0.5:
        o["answered_at"] = t[1]
    for f, v in (("reason", r.choice(["user.hangup", "user.declined", "hangup"])), ("relay", "did:web:relay.example"),
                 ("media", ["audio"]), ("recording", {"state": "off"}),
                 ("evidence", [r.choice(["ab" * 32, "AB" * 32, "ab"])])):
        if r.random() < 0.3:
            o[f] = v
    if r.random() < 0.1:
        del o[r.choice(["session", "device", "ended_at", "outcome"])]
    ctx = {"conversation": ulid(9), "conversation_kind": r.choice(["direct", "direct", "personal", "group"]),
           "leaf_identity": ALICE, "leaf_device": dev}
    return "messaging", "object", ctx, {"object": o}


def gen_call_record_outcome(r: random.Random):
    """A leg's outcome (Recording Profile C§9; README `check: "call-record-outcome"`)."""
    return "recording", "call-record-outcome", {}, {
        "direction": r.choice(["inbound", "outbound"]), "answered": r.random() < 0.3,
        "ended_by": r.choice(["local", "remote", "transport"]),
        "reason": r.choice(["user.hangup", "user.declined", "session.answered-elsewhere", "session.cancelled",
                            "session.timeout", "endpoint.busy", "transport.no-response", "transport.x", "policy.y"])}


ALIASES = ["alice@example.com", "alice@EXAMPLE.com", "alice", "@example.com", "a@b", "tel:+15551234567", "tel:+0155",
           "bob@ex-ample.co", "x@-bad.com", "", "a b@example.com", "alice@example.com."]


def gen_alias_query(r: random.Random):
    """The provider's answer (Alias Transparency T§7; README `check: "alias-query"`)."""
    return "alias-transparency", "alias-query", {}, {
        "request": r.choice(["search", "monitor", "search", "monitor", "audit", ""]), "over_limit": r.random() < 0.2,
        "alias": r.choice(ALIASES), "exists": r.random() < 0.6, "visible": r.random() < 0.6, "authorized": r.random() < 0.5}


def gen_alias_monitor(r: random.Random):
    """Who may monitor (T§8; README `check: "alias-monitor"`)."""
    dids = ["did:web:alice.example", "did:web:mallory.example", "did:web:carol.example", "did:key:z6MkAlice"]
    prov = "did:web:example.com"
    payload = {"dsip": {"core": "1.0", "min_core": "1.0", "profiles": [], "extensions": [], "critical": []}, "type": "alias-monitor",
               "id": "01K742SG00ALIASMQN1T0R0001", "from": r.choice(dids), "issued_at": 1790000000, "expires_at": 1790000060,
               "to": prov if r.random() < 0.8 else r.choice(["did:web:other.example", "did:web:EXAMPLE.com"]), "alias": r.choice(ALIASES)}
    return "alias-transparency", "alias-monitor", {}, {"payload": payload, "provider": prov,
                                                      "values": r.sample(dids, r.randint(0, 3))}


def gen_alias_head(r: random.Random):
    """A tree head from a peer (T§9; README `check: "alias-head"`): signed heads, then field and byte mutations."""
    sys.path.insert(0, str(REPO / "impl/tools"))
    from dsipvec import kt
    from dsipvec.crypto import keypair_from_seed_name, b64url_encode as b64
    from dsipvec.gen.kt import VRF_PK
    sig = keypair_from_seed_name("kt-provider")
    cfg = bytes.fromhex("0002" + "01" + "0020" + sig.public.hex() + "0020" + VRF_PK
                        + "%016x" % 60000 + "%016x" % 86400000 + "%016x" % 3600000 + "00")
    roots = [kt.sha(bytes([n])) for n in range(4)]
    size = r.choice([0, 1, 5, 5, 7, 2**53 - 1, 2**53, 2**64 - 1])
    root = r.choice(roots)
    signer = sig if r.random() < 0.85 else keypair_from_seed_name("kt-impostor")
    sgn = signer.sign(cfg + kt.u64(r.choice([size, size, size, 6])) + r.choice([root, root, root, roots[0]]))
    if r.random() < 0.1:
        sgn = sgn[:r.randint(0, 64)]
    th = kt.u64(size) + kt.u16(len(sgn)) + sgn
    if r.random() < 0.1:
        th = r.choice([th[:-1], th + b"\x00", th[:r.randint(0, 12)]])
    rb = root if r.random() < 0.9 else root[:r.randint(0, 33)]
    claim = {"type": "alias-log-head", "provider": "did:web:example.com", "tree_head": b64(th), "root": b64(rb)}
    if r.random() < 0.15:
        k = r.choice(["type", "provider", "tree_head", "root"])
        claim[k] = r.choice([None, 5, "", "alias-log-heads", "example.com", claim[k] + "=", claim[k] + "AA", claim[k][:-1],
                             claim[k][:-1] + r.choice("AQgw_-+/")])
    if r.random() < 0.05:
        claim.pop(r.choice(list(claim)))
    held = [{"tree_size": n, "root": b64(r.choice(roots))} for n in r.sample([0, 1, 5, 7, 2**53 - 1], r.randint(0, 3))]
    return "alias-transparency", "alias-head", {}, {"claim": claim, "configuration": cfg.hex() if r.random() < 0.9 else None,
                                                     "held": held}


def gen_alias_lookup(r: random.Random):
    """What a lookup counts as (T§10; README `check: "alias-lookup-result"`)."""
    return "alias-transparency", "alias-lookup-result", {}, {
        "answer": r.choice(["found", "found", "not-found"]), "proof": r.choice(["verified", "verified", "unverifiable"]),
        "terminal_entry": r.randint(0, 20), "rightmost_distinguished": r.choice([None, 0, 5, 10, 15, 20]), "fork": r.random() < 0.15}


def gen_leave(r: random.Random):
    """An identity's pending Remove proposals at a member's device (M§7.3 "Leaving"; README `check: "leave-proposals"`)."""
    ids = ["did:web:alice.example", "did:web:bob.example", "did:web:carol.example"]
    devs = {i: [f"did:key:z6Mk{i[8:13]}Dev{n}" for n in range(3)] for i in ids}
    roster = [{"identity": i, "device": d} for i in ids for d in devs[i][:r.randint(1, 3)]]
    who = r.choice(ids)
    pool = [x for x in roster if x["identity"] == who] * 2 + [{"identity": who, "device": f"did:key:z6Mk{who[8:13]}Gone"}] + roster
    removes = [r.choice(pool) for _ in range(r.randint(0, 4))]
    return "messaging", "leave-proposals", {}, {"me": r.choice(ids), "proposer": {"identity": who, "device": devs[who][0]},
                                                "removes": removes, "others": r.choice([0, 0, 0, 1, 2]), "roster": roster}


def gen_roster_change(r: random.Random):
    """A commit's adds and removes against a roster, from a member's view (M§7.3; README `check: "roster-change"`)."""
    ids = ["did:web:alice.example", "did:web:bob.example", "did:web:carol.example", "did:web:dave.example"]
    devs = {i: [f"did:key:z6Mk{i[8:13]}Dev{n}" for n in range(4)] for i in ids}
    roster = [{"identity": i, "device": d} for i in ids[:3] for d in devs[i][:r.randint(1, 3)]]
    committer = r.choice(ids[:3] + [""])
    leaf = lambda: {"identity": (i := r.choice(ids)), "device": r.choice(devs[i])}
    adds = [leaf() for _ in range(r.choice([0, 0, 1, 2]))]
    pool = roster * 2 + [leaf()]
    removes = []
    for _ in range(r.choice([0, 1, 2, 3, 4])):
        x = dict(r.choice(pool))
        if r.random() < 0.3:
            x["delegation_valid"] = r.choice([False, False, True])
        removes.append(x)
    return "messaging", "roster-change", {}, {"committer": committer, "roster": roster, "adds": adds, "removes": removes}


def gen_presence_aggregate(r: random.Random):
    """A subscriber's held records and the body's assertion (P§4, P§5; README kind `presence`, check `aggregate`)."""
    states = ["available", "busy", "away", "dnd", "offline", "in-transit", "zz-later", "a"]
    records = []
    for _ in range(r.randint(0, 4)):
        rec = {"state": r.choice(states), "expires_at": NOW + r.choice([-1, 0, 0, 1, 100])}
        if r.random() < 0.8:
            rec["device"] = r.choice([A1, A2, B1, B2])
        records.append(rec)
    body = {"records": records}
    if r.random() < 0.8:
        body["asserted"] = r.choice(["available", "offline"])
    return "presence", "aggregate", {"now": NOW}, body


def gen_presence_sealed(r: random.Random):
    """A sealed record or a grant's keys, opened (P§12.3, P§12.4; README kind `presence`, `open-record`,
    `grant-keys-open`, `view`): real ciphertexts, then field, key and byte mutations, so the checks' order is probed."""
    sys.path.insert(0, str(REPO / "impl/tools"))
    from dsipvec.gen import presence_sealed as S
    kids = ["main.0", "main.1", f"{S.FAMILY}.0", f"{S.FAMILY}.3"]
    keys = lambda: {k: S.key(S.BOB_S, S.BOB, k).hex() for k in r.sample(kids, r.randint(0, 3))}
    if r.random() < 0.35:
        held = {k: S.key(S.BOB_S, S.BOB, k) for k in r.sample(kids, r.randint(0, 3))}
        audience = r.choice([None, S.FAMILY, "work"])
        pt = None
        if r.random() < 0.3:
            pt = r.choice([b'{"keys": []}', b'{"keys": [1]}', b'{"keys": [], "x": 1}', b"[]", b"\xff"]).ljust(r.choice([200, 256, 512]), b" ")
        g = S.grant_with_keys(f"fz{r.randint(0, 9999)}", held, audience=audience, plaintext=pt,
                              alg=r.choice(["hpke-base-x25519-sha256-aes128gcm"] * 5 + ["x"]))
        if r.random() < 0.2:
            g[r.choice(["id", "from", "to"])] = S.CAROL
        if r.random() < 0.2:
            g["presence_keys"]["ct"] = g["presence_keys"]["ct"][:-r.randint(1, 8)]
        return "presence", "grant-keys-open", {"now": NOW}, {"grant": g, "recipient_secret_hex": r.choice([S.ALICE_S, S.ALICE_S, S.CAROL_S]).hex()}

    def record():
        kid = r.choice(kids)
        audience = S.FAMILY if not kid.startswith("main") and r.random() < 0.8 else r.choice([None, "work"])
        pt = None
        if r.random() < 0.25:
            pt = r.choice(['{"state": "busy"}', '{"state": "Busy"}', '{"state": 1}', '{"state": "busy", "a": 1}', "busy",
                           '{"state": "' + "a" * 65 + '"}', '{"state": "in-transit"}']).encode().ljust(128, b" ")
        rec = S.sealed_fields(f"fz{r.randint(0, 9999)}", device=r.choice([S.BPH, S.BLA]), seq=r.choice([1, 2]),
                              audience=audience, kid=kid, state=r.choice(["busy", "dnd", "away", "in-transit"]), plaintext=pt,
                              at=NOW - r.choice([0, 0, 400]))
        x = r.random()
        if x < 0.1:
            rec["seq"] += 1
        elif x < 0.2:
            rec["sealed_state"] = rec["sealed_state"][:-r.randint(1, 6)]
        elif x < 0.25:
            rec["device"] = S.CPH
        return rec

    if r.random() < 0.5:
        return "presence", "open-record", {"now": NOW}, {"record": record(), "keys": keys()}
    recs = [record() if r.random() < 0.6 else {"subject": S.BOB, "device": r.choice([S.BPH, S.BLA]), "seq": 1,
                                               "state": r.choice(["busy", "away"]), "expires_at": NOW + 100}
            for _ in range(r.randint(0, 4))]
    body = {"records": recs, "keys": keys()}
    if r.random() < 0.8:
        body["asserted"] = r.choice(["available", "offline"])
    return "presence", "view", {"now": NOW}, body


def gen_presence_authority(r: random.Random):
    """Records, bindings and the clock at a subject's authority (P§3, P§4, P§8; README authority "Presence records")."""
    sub = ulid(20)
    ev = [{"local": "policy", "target": BOB, "mode": "public"},
          {"recv": {"type": "subscribe", "id": sub, "from": A1, "to": RELAY, "target": BOB, "events": ["presence"],
                    "expires_in": 3600}}]
    counter, clock = [2000], [NOW]
    for _ in range(r.randint(3, 12)):
        x = r.random()
        if x < 0.25:
            d = r.choice([B1, B2])
            ev.append({"relay": r.choice(["bind", "bind", "unbind"]), "device": d, "identity": BOB})
        elif x < 0.7:
            counter[0] += 1
            d = r.choice([B1, B1, B2])
            m = {"type": "presence", "id": ulid(counter[0]), "from": d, "to": RELAY,
                 "subject": r.choice([BOB] * 8 + [ALICE]), "state": r.choice(["busy", "away", "available", "dnd", "offline", "x-new"]),
                 "seq": r.choice([1, 2, 3, 3, 5, 9]), "issued_at": clock[0],
                 "expires_at": clock[0] + r.choice([59, 60, 61, 120, 300, 3600, 3601])}
            if r.random() < 0.9:
                m["device"] = r.choice([d] * 8 + [B2 if d == B1 else B1])
            ev.append({"recv": m})
        else:
            step = r.choice([1, 2, 4, 5, 6, 59, 60, 61, 120, 300])
            clock[0] += step
            ev.append({"advance": step})
    ctx = {"component": "authority", "start": NOW, "identities": IDENTITY}
    if r.random() < 0.4:
        ctx["presence_grace"] = r.choice([0, 0, 1, 30, 300])
    snapshot = {"presence": {}, "subscriptions": {}}
    return "state", None, ctx, [(e, snapshot) for e in ev]


def gen_presence_admission(r: random.Random):
    """Who may watch, audiences, shares at a subject's authority (P§6, P§7; README authority "Who may watch, audiences,
    shares"): grants presented and revoked, policies with audiences, capabilities, records per audience, bindings and
    the clock. DAVE never binds and is in no device map: only a policy or a capability makes him seen (spec-gap 149).
    Records are sometimes sealed and subscribers sometimes list presence/0.2 (P§12.6): the authority never opens a
    seal, so `sealed_state` is any string."""
    DAVE = "did:web:dave.example"
    audiences = [None, None, "family", "work"]
    grants = []
    for i in range(r.randint(1, 4)):
        g = {"id": ulid(3000 + i), "from": B1, "identity": r.choice([BOB] * 6 + [CAROL]), "to": r.choice([ALICE, CAROL, MALLORY]),
             "scope": r.choice([["dsip.subscribe"], ["dsip.invite", "dsip.subscribe"], ["dsip.invite"]]),
             "valid_until": NOW + r.choice([0, 5, 60, 300, 3600, 86400])}
        if (a := r.choice(audiences)) is not None:
            g["presence_audience"] = a
        if r.random() < 0.1:
            g["verified"] = False
        grants.append(g)
    ev = []
    if r.random() < 0.4:
        pol = {"local": "policy", "target": r.choice([BOB, BOB, DAVE]), "mode": r.choice(["public", "allow"]),
               "allow": r.sample([ALICE, CAROL, MALLORY], r.randint(0, 2))}
        if (a := r.choice(audiences)) is not None:
            pol["audience"] = a
        ev.append(pol)
    counter, clock = [4000], [NOW]
    for _ in range(r.randint(4, 16)):
        x = r.random()
        counter[0] += 1
        if x < 0.12:
            ev.append({"relay": r.choice(["bind", "bind", "unbind"]), "device": r.choice([B1, B2]), "identity": BOB})
        elif x < 0.15:
            ev.append({"local": "issue_capability", "token": r.choice(["t1", "t2"]), "target": r.choice([BOB, DAVE, DAVE])})
        elif x < 0.4:
            frm = r.choice([A1, A2, C1, M1, B2])
            m = {"type": "subscribe", "id": ulid(counter[0]), "from": frm, "to": RELAY, "target": r.choice([BOB, BOB, BOB, DAVE]),
                 "events": ["presence"], "expires_in": r.choice([0, 60, 600, 3600])}
            if r.random() < 0.8:
                m["claims"] = [{"type": "dsip-grant", "grant": g} for g in r.sample(grants, r.randint(1, len(grants)))]
            if r.random() < 0.3:
                m["capability"] = r.choice(["t1", "t2", "nope"])
            if r.random() < 0.5:
                m["profiles"] = r.choice([["presence/0.2"], ["presence/0.1", "presence/0.2"], ["presence/0.1"], []])
            ev.append({"recv": m})
        elif x < 0.7:
            d = r.choice([B1, B1, B2])
            m = {"type": "presence", "id": ulid(counter[0]), "from": d, "to": RELAY, "subject": BOB, "device": d,
                 "state": r.choice(["busy", "away", "available", "dnd"]), "seq": r.choice([1, 2, 3, 5]), "issued_at": clock[0],
                 "expires_at": clock[0] + r.choice([60, 120, 300])}
            if (a := r.choice(audiences)) is not None:
                m["audience"] = a
            if r.random() < 0.4:
                del m["state"]
                m["kid"] = f"{a or 'main'}.{r.choice([0, 1])}"
                m["sealed_state"] = r.choice(["c2VhbGVk", "b3RoZXI"])
            ev.append({"recv": m})
        elif x < 0.8:
            g = r.choice(grants)
            ev.append({"recv": {"type": "grant-revocation", "id": ulid(counter[0]), "from": r.choice([B1, B2, C1]), "to": RELAY,
                                "grant": g["id"], "grantee": g["to"], "valid_until": g["valid_until"]}})
        else:
            step = r.choice([1, 4, 5, 59, 60, 300, 600])
            clock[0] += step
            ev.append({"advance": step})
    ctx = {"component": "authority", "start": NOW, "identities": IDENTITY}
    if r.random() < 0.4:
        ctx["presence_grace"] = r.choice([0, 1, 30])
    snapshot = {"presence": {}, "subscriptions": {}}
    return "state", None, ctx, [(e, snapshot) for e in ev]


def gen_tnbinding(r: random.Random):
    """A number binding (N§3.4): random TNAuthLists, CA constraints, chains, clocks, claims and byte mutations."""
    sys.path.insert(0, str(REPO / "impl/tools"))
    from dsipvec.gen import tnbinding as G
    pool = ["15551234567", "15552000000", "15552000999", "15552001000", "1555200099", "155520000005", "15553330000",
            "15553330001", "15551234500", "15551234599", "15551234600", "1555*00", "1#", "1555123456789012", ""]

    tn = "+" + r.choice(pool[:11]) if r.random() < 0.95 else r.choice(["+0155", "+1", "15551234567", "+1555123456789012"])

    def tnauth():
        if r.random() < 0.1:
            return None
        entries = [G.tn_one(tn[1:])] if r.random() < 0.5 and tn[1:].isdigit() and len(tn) <= 16 else []
        for _ in range(r.randint(0 if entries or r.random() < 0.03 else 1, 3)):
            x = r.random()
            bad = r.random() < 0.03
            number = r.choice(pool[13:] if bad else pool[:13])
            if x < 0.4:
                entries.append(G.tn_one(number) if r.random() < 0.97 else G.tlv(0x82, b"15551234567"))
            elif x < 0.8:
                count = r.choice([0, 1, -3] if r.random() < 0.08 else [2, 10, 100, 1000, 2 ** 64 + 5, 10 ** 20])
                entries.append(G.explicit(1, G.seq(G.ia5(number), G.integer(count))))
            else:
                entries.append(G.tn_spc(r.choice(["709J", "709J", "OTHR", "709j"] if r.random() < 0.97 else [""])))
        raw = G.seq(*entries)
        if r.random() < 0.08:
            raw = mutate(r, raw, bytes(range(0, 256, 7)) + b"\x30\xa0\xa1\xa2\x16\x02\x80\x81")
        return G.tnauth(raw=raw)

    def window():
        return r.choice([(NOW - 86400, NOW + 86400)] * 6 + [(NOW - 86400, NOW), (NOW, NOW + 1), (NOW + 1, NOW + 9),
                         (NOW - 9, NOW - 1)])

    def exts(ca: bool):
        e = []
        if ca:
            x = r.random()
            if x < 0.95:
                e.append(G.bc(r.random() < 0.95, r.choice([None, None, None, 0, 1, 2])))
            e.append(r.choice([G.CA_KU] * 6 + [G.ku(0), G.ku(5)]) if r.random() < 0.8 else b"")
        else:
            e.append(r.choice([G.LEAF_KU] * 6 + [G.ku(5), G.ku(0, 5)]) if r.random() < 0.8 else b"")
            if r.random() < 0.05:
                e.append(G.bc(r.random() < 0.5, r.choice([None, 0, 3])))
        if r.random() < 0.02 and e:
            e.append(e[0])  # a duplicate extension
        t = tnauth() if (not ca or r.random() < 0.3) else None
        if t:
            e.append(t)
        if r.random() < 0.05:
            e.append(G.ext("1.3.6.1.4.1.99999.1", b"\x05\x00", critical=r.random() < 0.5))
        return [x for x in e if x]

    inter = G.INTER if r.random() < 0.6 else G.cert(G.INTER.subject, G.key("inter"), G.ROOT, exts(True), 90,
                                                    *(lambda w: (w[0] - 99, w[1] + 99))(window()))
    mid = G.cert(G.name((G.O, "Mid CA")), G.key("mid"), inter, exts(True), 91) if r.random() < 0.25 else None
    issuer = mid or inter
    nb, na = window() if r.random() < 0.1 else (NOW - 86400, NOW + 86400)
    leaf = G.cert(G.name((G.O, r.choice(["Carrier Example", "Other"])), (G.CN, "x")), G.key("sp-fuzz"), issuer,
                  exts(False), 92, nb, na)
    chain = [leaf] + ([mid] if mid else []) + [inter]
    x = r.random()
    if x < 0.04:
        chain = chain[::-1]
    elif x < 0.15:
        chain = chain + [G.ROOT]
    elif x < 0.18:
        chain = chain[:1]
    anchors = r.choice([[G.ROOT]] * 18 + [[], [G.cert(G.ROOT.subject, G.key("rogue"), None, [G.bc(True)], 1)]])
    iat = NOW + r.choice([-3600] * 5 + [-604800, 0, 300, 301, -1])
    exp = iat + r.choice([86400] * 12 + [604800, 604801, 1, 0, 3600])
    p = {"tn": tn, "did": r.choice([G.DID, G.DID, "did:web:bob.example"]), "iat": iat, "exp": exp, "jti": G.JTI}
    st = "https://status.example/x"
    if r.random() < 0.3:
        p["status"] = st
    h = G.header(**({"crit": ["x"]} if r.random() < 0.02 else {}))
    pj = json.dumps(p, separators=(",", ":")).encode()
    if r.random() < 0.04:
        pj = mutate(r, pj, b'{}[]":,.-0123456789eE\\u ')
    k = leaf.key if r.random() < 0.95 else G.key("mallory")
    binding = G.jws(h, pj, k)
    if r.random() < 0.04:
        binding = mutate(r, binding.encode(), b"AZaz09-_.=+/").decode("latin-1")
    text = G.pem(*chain)
    if r.random() < 0.03:
        text = mutate(r, text.encode(), b"-ABC \n\r=+/").decode("latin-1")
    doc = r.choice([G.doc(f"tel:{tn}"), G.doc(f"tel:{tn}"), G.doc("tel:+15550000000"), None, G.doc(f"tel:{tn}", id_="did:x:y")])
    ctx = {"trust_anchors": [c.b64() for c in anchors], "certificates": {G.X5U: text},
           "spc_numbers": r.choice([{"709J": ["15553330000"]}, {}]), "require_status": r.random() < 0.3,
           "status": r.choice([{}, {st: "good"}, {st: "revoked"}])}
    return "tn-binding", None, ctx, {"binding": binding, "did": G.DID, "did_document": doc,
                                     "now": NOW + r.choice([0] * 8 + [-1, 1, 3600, 86400, 604800])}


def _tn_pool():
    """A fixed pool of bindings for the store and select targets: DIDs, iats and numbers that collide on purpose."""
    sys.path.insert(0, str(REPO / "impl/tools"))
    from dsipvec.gen import tnbinding as G
    if not hasattr(_tn_pool, "pool"):
        dids = ["did:web:alice.example", "did:web:mallory.example", "did:web:x.example", "did:web:y.example",
                "did:web:z.example"]
        pool = []
        for i, did in enumerate(dids):
            for d_iat in (-7200, -3600, -3600, 0):
                jti = G.JTI[:-2] + f"{(i * 7 + len(pool)) % 100:02d}"
                pool.append(G.jws(p=G.claims(did=did, iat=G.IAT + d_iat, exp=G.IAT + d_iat + 86400, jti=jti)))
        pool.append(G.jws(p=G.claims(tn="+15552000000")))
        pool.append(G.jws(k=G.key("mallory")))
        pool.append(G.jws(p=G.claims(did="did:web:old.example", iat=G.NOW - 90000, exp=G.NOW - 5)))
        _tn_pool.pool, _tn_pool.G = pool, G
    return _tn_pool.pool, _tn_pool.G


def gen_tn_store(r: random.Random):
    """A node's PUT against a random held set (N§6; README `check: "store"`)."""
    pool, G = _tn_pool()
    # a node never holds two bindings for one DID (outside the README contract): one per DID, the pool is 4 per DID
    held = [r.choice(pool[4 * i:4 * i + 4]) for i in r.sample(range(5), r.randint(0, 5))]
    tn = r.choice([G.TN] * 8 + ["+15552000000", "15551234567"])
    return "tn-binding", "store", G.ctx(), {"tn": tn, "binding": r.choice(pool), "held": held,
                                            "now": G.NOW + r.choice([0, 0, 0, 3600, 80000])}


def gen_tn_select(r: random.Random):
    """A reader's choice among returned bindings (N§6–N§7; README `check: "select"`)."""
    pool, G = _tn_pool()
    dids = ["did:web:alice.example", "did:web:mallory.example", "did:web:x.example", "did:web:y.example"]
    docs = {d: G.doc(r.choice([f"tel:{G.TN}"] * 3 + ["tel:+15550000000"]), id_=d) for d in dids if r.random() < 0.8}
    return "tn-binding", "select", G.ctx(), {"tn": r.choice([G.TN] * 9 + ["+15552000000"]),
                                             "bindings": r.sample(pool, r.randint(0, 6)), "documents": docs,
                                             "now": G.NOW + r.choice([0, 0, 3600, 80000])}


def gen_tn_authority(r: random.Random):
    """A client pooling authorities' .well-known answers (N§6 route 2; README `check: "authority"`)."""
    pool, G = _tn_pool()
    dids = ["did:web:alice.example", "did:web:mallory.example", "did:web:x.example", "did:web:y.example"]
    docs = {d: G.doc(r.choice([f"tel:{G.TN}"] * 3 + ["tel:+15550000000"]), id_=d) for d in dids if r.random() < 0.8}

    def answer():
        auth = r.choice(["carrier-a.example", "carrier-b.example", "carrier-a.example", "x.example"])
        status = r.choice([200] * 6 + [404, None, "200", 500])
        bs = r.sample(pool, r.randint(0, 4)) + ([5, None] if r.random() < 0.1 else [])
        body = r.choice([{"bindings": bs}] * 6 + [None, [bs], {"bindings": "x"}, {}])
        return {"authority": auth, "status": status, "body": body}
    answers = [answer() for _ in range(r.randint(0, 4))] if r.random() < 0.97 else "x"
    return "tn-binding", "authority", G.ctx(), {"tn": r.choice([G.TN] * 9 + ["+15552000000"]), "answers": answers,
                                                "documents": docs, "now": G.NOW + r.choice([0, 0, 3600, 80000])}


def gen_tn_passport(r: random.Random):
    """A gateway's Identity header check (G§5; README `check: "passport"`): mutated PASSporTs, parameters, From/To, clocks."""
    pool, G = _tn_pool()
    numbers = [G.TN, G.TO, "+15559990000", "+" + G.SPC_NUMBER, "+15552000500"]
    tn, to = r.choice(numbers), r.choice(numbers)
    fmt = r.choice([lambda n: n, lambda n: n, lambda n: n[1:], lambda n: f"+1 ({n[2:5]}) {n[5:8]}-{n[8:]}", lambda n: "anonymous"])
    h = G.pp_header(**r.choice([{}, {}, {}, {"x5u": G.GW_X5U}, {"ppt": "div"}, {"typ": "JWT"}, {"x5u": "https://nowhere.example/x.pem"}]))
    dest = r.choice([[to[1:]], [to[1:]], [to, "15550000000"], ["15550000000"], [], "x"])
    p = G.pp_claims(attest=r.choice(["A", "A", "B", "C", "D"]), orig={"tn": r.choice([tn[1:], tn, "anon"])}, dest={"tn": dest},
                    iat=G.NOW + r.choice([0, 0, -30, 60, -61, 61, 400]), **({} if r.random() < 0.7 else {"origid": G.DROP}))
    k = r.choice([G.LEAF.key] * 4 + [G.DEL.key, G.key("mallory")])
    params = r.choice([";alg=ES256;ppt=shaken"] * 4 + ["", ";ppt=div", ";alg=es256", ";alg=ES256;", "; Alg = ES256 ", ";x"])
    identity = G.passport(h, p, k, info=r.choice([None] * 5 + ["", "https://other.example/x.pem"]), params=params)
    if r.random() < 0.08:
        identity = r.choice([None, "x.y;info=<a>", identity.split(";")[0], identity.replace(".", ",", 1)])
    ctx = G.gw_ctx(anchors=r.choice([[G.ROOT]] * 6 + [[], [G.INTER]]), require_status=r.random() < 0.2)
    return "tn-binding", "passport", ctx, {"identity": identity, "from_tn": fmt(tn), "to_tn": fmt(to), "now": G.NOW + r.choice([0, 0, 0, 30, -40, 100])}


def gen_tn_route(r: random.Random):
    """A gateway resolving a dialled number (N§6.1; README `check: "route"`): tables and lookups that collide."""
    pool, G = _tn_pool()
    dids = ["did:web:alice.example", "did:web:mallory.example", "did:web:x.example", "did:web:y.example"]
    to = r.choice([G.TN] * 6 + ["+15552000000", "bob", "15551234567"])
    conf = r.choice([{}, {}, {G.TN: "did:web:bob.example"}, {"bob": "did:web:bob.example"}, {G.TN: 5}, None, "x"])
    docs = {d: G.doc(r.choice([f"tel:{G.TN}"] * 3 + ["tel:+15550000000"]), id_=d) for d in dids if r.random() < 0.8}
    return "tn-binding", "route", G.ctx(), {"to_tn": to, "configured": conf, "bindings": r.choice([r.sample(pool, r.randint(0, 5))] * 5 + [None]),
                                            "documents": docs, "now": G.NOW + r.choice([0, 0, 3600, 80000])}


def gen_tn_assert(r: random.Random):
    """A gateway asserting a bound number (N§4.1; README `check: "assert"`): claims, destinations, certificates, keys."""
    pool, G = _tn_pool()
    def claim():
        x = r.random()
        if x < 0.5:
            return {"type": "tel", "number": r.choice([G.TN] * 4 + ["+15552000500", "+15552000000"]), "binding": r.choice(pool + [G.jws(), G.jws()])}
        if x < 0.7:
            return {"type": "tel", "number": G.TN, "binding": G.jws(), "verifier": "did:web:gw.example"}
        if x < 0.85:
            return {"type": "display_name", "value": "Alice"}
        return {"type": "tel", "number": "+15552000500", "binding": G.jws(p=G.claims(tn="+15552000500"))}
    claims = [claim() for _ in range(r.randint(0, 3))]
    gw = r.choice([None] * 2 + [{"x5u": G.GW_X5U, "key": G.key_pem(G.DEL.key)}] * 5 + [{"x5u": G.X5U, "key": G.key_pem(G.LEAF.key)},
                  {"x5u": G.GW_X5U, "key": G.key_pem(G.LEAF.key)}, {"x5u": "https://nowhere.example/x.pem", "key": G.key_pem(G.DEL.key)},
                  {"x5u": G.GW_X5U, "key": "junk"}])
    ctx = G.gw_ctx(gateway=gw, anchors=r.choice([[G.ROOT]] * 8 + [[]]))
    if gw is None:
        del ctx["gateway"]
    doc = G.doc(*r.choice([(f"tel:{G.TN}",), (f"tel:{G.TN}", "tel:+15552000500"), ("tel:+15550000000",)]))
    return "tn-binding", "assert", ctx, {"claims": claims, "identity": r.choice([G.DID] * 5 + ["did:web:mallory.example"]), "did_document": doc,
                                         "to_tn": r.choice([G.TO] * 5 + ["911", "+447700900123"]), "now": G.NOW + r.choice([0, 0, 3600]), "origid": G.ORIGID}


def gen_wake_trace(r: random.Random):
    """A relay's or a mailbox's wake state (W§4.3, W§5.1; README kind `wake`): registrations, bindings, held invites,
    stored items, gateway answers and the clock, in any order and at colliding instants."""
    component = r.choice(["relay", "mailbox"])
    devices = [B1, B2, A1]
    sessions = [ulid(40), ulid(41), ulid(42)]
    t, ev = NOW, []
    for _ in range(r.randint(3, 16)):
        t += r.choice([0, 0, 1, 5, 29, 30, 59, 60, 61, 120])
        x, d = r.random(), r.choice(devices)
        if x < 0.2:
            reg = {"device": d, "identity": IDENTITY[d], "expires_at": t + r.choice([0, 1, 30, 60, 90, 3600])}
            if r.random() < 0.3:
                reg["kinds"] = r.sample(["call", "call-ended", "message", "typing"], r.randint(0, 3))
            e = {"register": reg}
        elif x < 0.35:
            e = {r.choice(["bind", "bind", "unbind", "unbind"]): d}
        elif x < 0.45:
            e = {r.choice(["remove", "revoke", "forget"]): d}
        elif x < 0.52:
            e = {"answer": {"device": d, "reason": r.choice(["wake.registration-ended", "wake.not-authorized", "wake.x-new",
                                                             "transport.rate-limited", "session.failed"])}}
        elif x < 0.85 and component == "relay":
            if r.random() < 0.65:
                e = {"hold": {"session": r.choice(sessions), "devices": r.sample(devices, r.randint(1, 3)),
                              "expires_at": t + r.choice([0, 1, 15, 30, 60])}}
            else:
                e = {"drop": r.choice(sessions)}
        elif x < 0.85:
            e = {"store": {"identity": r.choice([BOB, BOB, ALICE]), "class": r.choice(["application", "welcome", "ephemeral"])}}
        else:
            e = {"tick": True}
        ev.append({"at": t, **e})
    return "wake", None, {"component": component}, ev


def gen_wake_register(r: random.Random):
    """A waker's checks on a `wake-register` (W§4.2; README kind `wake`, check `register`): registrations whose
    signer, waker, gateway, lifetime and clock collide, so that the checks' order decides."""
    from dsipvec import envelope as E
    from dsipvec.crypto import keypair_from_seed_name
    keys = [keypair_from_seed_name("wake-key-bob-phone"), keypair_from_seed_name("wake-key-mallory")]
    key, signer = r.choice(keys), r.choice(keys + [keys[0]] * 2)
    issued = NOW + r.choice([-3600, -60, 0, 299, 300, 301])
    life = r.choice([-1, 0, 1, 60, 3600, 2_592_000, 2_592_001])
    reg = {"type": r.choice(["WakeRegistration"] * 9 + ["DeviceDelegation"]), "key": key.did,
           "waker": r.choice([RELAY, RELAY, HUB_B]), "gateway": r.choice(["did:web:push.dsip.example", ROGUE]),
           "handle": "h-fuzz-0001", "issued_at": issued, "expires_at": issued + life}
    if r.random() < 0.1:
        reg["extra"] = 1
    env = E.sign(reg, signer, signer.kid)
    p = {"dsip": {"core": "1.0", "min_core": "1.0", "profiles": ["wake/0.1"], "extensions": [], "critical": []},
         "type": "wake-register", "id": ulid(50), "from": B1, "to": RELAY, "registration": env,
         "issued_at": NOW, "expires_at": NOW + 30}
    if r.random() < 0.3:
        p["kinds"] = r.sample(["call", "message", "call-ended", "call"], r.randint(0, 4))
    if r.random() < 0.1:
        p["remove"] = True
    ctx = {"waker": RELAY, "now": NOW}
    if r.random() < 0.6:
        ctx["gateways"] = ["did:web:push.dsip.example"]
    return "wake", "register", ctx, {"register": p, "device": B1}


TARGETS = {
    "syslog": gen_syslog, "snmpv3": gen_snmpv3, "recording": gen_recording, "tn-binding": gen_tnbinding, "tn-store": gen_tn_store, "tn-select": gen_tn_select,
    "tn-passport": gen_tn_passport, "tn-route": gen_tn_route, "tn-assert": gen_tn_assert, "tn-authority": gen_tn_authority,
    "tsm": gen_tsm, "tls-frames": gen_tls_frames, "tsm-name": gen_tsm_name, "syslog-sign": gen_syslog_sign,
    "gap": gen_gap, "commit-retry": gen_commit_retry, "hub-outage": gen_hub_outage, "move-arrival": gen_move_arrival, "enrolment": gen_enrolment, "resume": gen_resume, "history": gen_history,
    "successor": gen_successor, "client": gen_client, "hub": gen_hub, "mailbox": gen_mailbox, "endpoint": gen_endpoint,
    "relay": gen_relay, "deposit-fields": gen_deposit_fields, "gateway-reason": gen_gateway_reason,
    "call-record": gen_call_record, "call-record-outcome": gen_call_record_outcome,
    "alias-query": gen_alias_query, "alias-monitor": gen_alias_monitor, "alias-head": gen_alias_head,
    "alias-lookup": gen_alias_lookup, "leave-proposals": gen_leave, "roster-change": gen_roster_change,
    "presence-aggregate": gen_presence_aggregate, "presence-authority": gen_presence_authority,
    "presence-admission": gen_presence_admission, "presence-sealed": gen_presence_sealed,
    "presence-keys": gen_presence_keys, "wake-trace": gen_wake_trace, "wake-register": gen_wake_register,
}

# Targets where the implementations are known to differ and the difference is a protocol decision, not a bug
# (impl/docs/spec-gaps.md). `--target all` leaves them out so CI stays meaningful; name them to run them.
# Empty since spec-gaps 82 (relay) and 83 (resume) were decided: a new open question goes here with its gap number.
OPEN: dict[str, str] = {}

# ---------------------------------------------------------------- probes


def probe(name: str, kind: str, check, ctx: dict, body) -> dict:
    """A probe is an ordinary vector whose `expect` is a placeholder: only the runners' actual results are compared."""
    v = {"vector": f"{kind}/{name}", "format": 1, "kind": kind, "description": "generated probe", "spec_ref": ["—"], "context": ctx}
    if isinstance(body, dict):  # a table row
        v["input"] = {**({"check": check} if check else {}), **body}
        v["expect"] = {}
    elif kind == "state":  # per-step expectations, which also name the snapshot members to report
        v["input"] = {"steps": [{"event": e, "expect": {"emit": [], **snap}} for e, snap in body]}
        v["expect"] = {}
    else:
        v["input"] = {**({"check": check} if check else {}), "steps": [{"event": e} for e in body]}
        v["expect"] = {"steps": [{"emit": [], "state": {}} for _ in body]}
    return v


def events_of(v: dict) -> list:
    return v["input"].get("steps", [])


def without(v: dict, i: int) -> dict:
    w = json.loads(json.dumps(v))
    del w["input"]["steps"][i]
    if "steps" in w["expect"]:
        del w["expect"]["steps"][i]
    return w


# ---------------------------------------------------------------- runners

RUNNERS = {
    "python": lambda d, out: [sys.executable, str(REPO / "impl/tools/run_vectors.py"), "--dir", str(d), "--json", str(out)],
    "rust": lambda d, out: ["cargo", "run", "-q", "-p", "dsip-cli", "--", "vectors", "run", "--dir", str(d), "--json", str(out)],
    "typescript": lambda d, out: ["node", str(REPO / "impl-ts/dist/run-vectors.js"), "--dir", str(d), "--json", str(out)],
}


def prune(x):
    """Snapshots of things that do not exist are reported as null by one runner and left out by another."""
    if isinstance(x, dict):
        return {k: prune(v) for k, v in x.items() if v is not None or k in ("cursor", "current_akid", "down_for", "moved_to",
                                                                             "outstanding_update", "next", "since", "selected",
                                                                             "source", "winner", "outcome")}
    return [prune(v) for v in x] if isinstance(x, list) else x


def run_all(vectors: list[dict], which: list[str]) -> dict[str, dict]:
    """Every probe through every runner: {runner: {vector id: what it computed}}."""
    with tempfile.TemporaryDirectory(prefix="dsip-fuzz-") as td:
        root = Path(td) / "vectors"
        for v in vectors:
            kind, name = v["vector"].split("/")
            (root / kind).mkdir(parents=True, exist_ok=True)
            (root / kind / f"{name}.json").write_text(json.dumps(v))
        results = {}
        for name in which:
            out = Path(td) / f"{name}.json"
            p = subprocess.run(RUNNERS[name](root, out), cwd=dsip_rs.RS if name == "rust" else REPO / "impl", env=dsip_rs.env(),
                               capture_output=True, text=True)
            if not out.exists():
                raise SystemExit(f"{name} runner produced no results:\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
            raw = json.loads(out.read_text())
            results[name] = {k: prune(r.get("steps", r.get("actual"))) for k, r in raw.items()}
            for k, a in results[name].items():
                if isinstance(a, dict) and "steps" in a:
                    results[name][k] = a["steps"]
        return results


def disagreement(results: dict[str, dict], vid: str):
    answers = {n: r.get(vid) for n, r in results.items()}
    first = next(iter(answers.values()))
    return None if all(a == first for a in answers.values()) else answers


# Targets whose traces are a strict dialogue (answer, then synced): dropping one event makes a trace no device can meet.
NO_SHRINK = ("probe-commit-retry-",)


def shrink(v: dict, which: list[str], budget: int = 40) -> dict:
    """Drop events while the runners still disagree (greedy, one at a time)."""
    if any(tag in v["vector"] for tag in NO_SHRINK):
        return v
    i = len(events_of(v)) - 1
    while i >= 0 and budget > 0 and len(events_of(v)) > 1:
        w = without(v, i)
        budget -= 1
        if disagreement(run_all([w], which), w["vector"]):
            v = w
        i -= 1
    return v


def report(v: dict, answers: dict) -> None:
    print(f"\n[DIVERGE] {v['vector']}   context: {json.dumps(v['context'])[:400]}")
    seqs = [a for a in answers.values() if isinstance(a, list)]
    if len(seqs) == len(answers) and events_of(v):
        n = next((k for k in range(min(map(len, seqs))) if len({json.dumps(a[k], sort_keys=True) for a in seqs}) > 1), 0)
        for k, step in enumerate(events_of(v)[: n + 1]):
            print(f"   {'→' if k == n else ' '} {json.dumps(step['event'])[:300]}")
        for name, a in answers.items():
            print(f"     {name:11s}{json.dumps(a[n] if n < len(a) else None)[:600]}")
    else:
        print(f"     input      {json.dumps(v['input'])[:500]}")
        for name, a in answers.items():
            print(f"     {name:11s}{json.dumps(a)[:500]}")


def summarize(bad: list) -> None:
    """Group divergences by the kind of event they occur at and the head of what each runner emitted there."""
    groups: dict[tuple, list] = {}
    for v, answers in bad:
        seqs = list(answers.values())
        if not all(isinstance(a, list) for a in seqs) or not events_of(v):
            key = (json.dumps(v["input"])[:80],) + tuple(json.dumps(a)[:70] for a in seqs)
        else:
            n = next((k for k in range(min(map(len, seqs))) if len({json.dumps(a[k], sort_keys=True) for a in seqs}) > 1), 0)
            e = events_of(v)[n]["event"]
            verb = next(iter(e))
            body = e[verb]
            what = body.get("type", "") if isinstance(body, dict) else (body if isinstance(body, str) else "")
            head = lambda a: json.dumps((a[n].get("emit") or [{}])[0])[:90] + (" +state" if len({json.dumps(x[n].get("emit")) for x in seqs}) == 1 else "")
            key = (f"{verb} {what}",) + tuple(head(a) for a in seqs)
        groups.setdefault(key, []).append(v["vector"])
    for key, ids in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:25]:
        print(f"  {len(ids):4d} × at `{key[0]}`   e.g. {ids[0]}")
        for name, ans in zip(("python", "rust", "typescript"), key[1:]):
            print(f"           {name:11s}{ans}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--target", default="all", help="comma-separated: " + ", ".join(TARGETS) +
                    " (default: all, which leaves out the open decisions: " + ", ".join(OPEN) + ")")
    ap.add_argument("--seed", default="1", help="integer, or `random`")
    ap.add_argument("--count", type=int, default=200, help="probes per target")
    ap.add_argument("--runners", default="python,rust,typescript")
    ap.add_argument("--out", help="directory to keep shrunk reproducers in")
    ap.add_argument("--max-reports", type=int, default=5, help="divergences to shrink and print per target")
    ap.add_argument("--summary", action="store_true",
                    help="do not shrink: group the divergences by the event they happen at and what each side answered")
    args = ap.parse_args()

    seed = random.SystemRandom().randrange(1 << 31) if args.seed == "random" else int(args.seed)
    targets = [t for t in TARGETS if t not in OPEN] if args.target == "all" else args.target.split(",")
    for t in targets:
        if t not in TARGETS:
            raise SystemExit(f"unknown target {t}; choose from: {', '.join(TARGETS)}")
        if t in OPEN:
            print(f"note: {t} is an open decision — {OPEN[t]}")
    which = args.runners.split(",")
    print(f"fuzz: seed {seed}, {args.count} probes per target, runners {', '.join(which)}")

    probes, by_target = [], {}
    for t in targets:
        r = random.Random(f"{seed}/{t}")
        for k in range(args.count):
            kind, check, ctx, body = TARGETS[t](r)
            if isinstance(body, list) and not body:
                continue
            v = probe(f"probe-{t}-{k}", kind, check, ctx, body)
            probes.append(v)
            by_target.setdefault(t, []).append(v)
    results = run_all(probes, which)

    total = 0
    for t in targets:
        bad = [(v, a) for v in by_target.get(t, []) if (a := disagreement(results, v["vector"]))]
        total += len(bad)
        print(f"{t:15s}{len(by_target.get(t, [])):5d} probes, {len(bad)} divergences")
        if args.summary:
            summarize(bad)
            continue
        for v, _ in bad[: args.max_reports]:
            small = shrink(v, which) if events_of(v) else v
            report(small, disagreement(run_all([small], which), small["vector"]) or {})
            if args.out:
                Path(args.out).mkdir(parents=True, exist_ok=True)
                (Path(args.out) / (small["vector"].replace("/", "-") + ".json")).write_text(json.dumps(small, indent=1))
    print(f"\n{len(probes)} probes, {total} divergences" + (f" — reproduce with --seed {seed}" if total else ""))
    return 1 if total else 0


if __name__ == "__main__":
    if shutil.which("node") is None or shutil.which("cargo") is None:
        print("fuzz.py needs node and cargo on PATH", file=sys.stderr)
        sys.exit(2)
    dsip_rs.require()
    sys.exit(main())
