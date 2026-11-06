#!/usr/bin/env python3
"""Regenerate impl/vectors/ from the generator modules. Deterministic: re-running yields identical bytes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dsipvec import fixtures  # noqa: E402
from dsipvec.gen import envelope, payload, semantic, state, transport, dht, broadcast, binding, gateway, trust, messaging, webvh, events, kt, pkarr, recording, tnbinding, presence, wake, key_agreement  # noqa: E402

VECTOR_DIR = Path(__file__).resolve().parents[1] / "vectors"
KINDS = {"envelope": envelope, "payload": payload, "semantic": semantic, "state": state, "transport": transport, "dht": dht,
         "broadcast": broadcast, "media-binding": binding, "gateway": gateway, "trust": trust, "messaging": messaging,
         "did-webvh": webvh, "device-events": events,
         "alias-transparency": kt, "pkarr": pkarr, "recording": recording, "tn-binding": tnbinding,
         "presence": presence, "wake": wake, "key-agreement": key_agreement}


def main() -> int:
    written, seen = 0, set()
    for kind, mod in KINDS.items():
        d = VECTOR_DIR / kind
        d.mkdir(parents=True, exist_ok=True)
        for v in mod.vectors():
            assert v["vector"].startswith(kind + "/"), v["vector"]
            assert v["vector"] not in seen, f"duplicate vector id {v['vector']}"
            assert v["spec_ref"], f"{v['vector']} lacks spec_ref"
            seen.add(v["vector"])
            path = VECTOR_DIR / (v["vector"] + ".json")
            path.write_text(json.dumps(v, indent=2, ensure_ascii=False) + "\n")
            written += 1
        for stale in d.glob("*.json"):
            if f"{kind}/{stale.stem}" not in seen:
                stale.unlink()
                print(f"removed stale {stale}")
    (VECTOR_DIR / "fixtures.json").write_text(json.dumps(fixtures.public_fixtures(), indent=2) + "\n")
    print(f"wrote {written} vectors + fixtures.json to {VECTOR_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
