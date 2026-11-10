# DSIP conformance: vectors, the reference harness, and the tools

**Tracks:** DSIP Core 1.0 + JSON Schema set 1.0 (`../v1.0/`), final at `poc-v1.0`. Earlier versions are final at
their tags (`poc-v0.6` … `poc-v0.17`). Companion profiles: Gateway 1.0, Messaging 1.0, and the drafts in `../v1.0/`.
**Conformance contract:** `vectors/` (see `vectors/README.md`). Spec-gap issues and their dispositions:
`docs/spec-gaps.md`.

The Rust implementation grew here as `impl/crates` and moved, with its history, to
**[dsip-rs](https://github.com/feryx-io/dsip-rs)** (2026-10-29, first release `v2026.10.29`): the crates, the
workspace, the demos and the browser client. dsip-rs takes this repository as its `spec/` submodule. DSIP measures it
at the commit pinned in `dsip-rs.rev`, against the vectors here, in three-way parity with the Python harness and
`../impl-ts`.

## Layout

```
vectors/        Language-neutral conformance vectors (generated; committed)
tools/          Python: vector generator, reference harness (dsipvec/), parity (Rust, TypeScript), differential
                fuzzing, spec lint, DHT testnet, wan/ testbed; dsip-rs.sh checks out the pinned dsip-rs
docs/           Plans, spec gaps, coverage cross-index (generated from dsip-rs), DHT and STIR findings
dsip-rs.rev     The dsip-rs commit DSIP's CI measures (now the v2026.10.29 release)
```

## Quick start

```bash
# Python side (needs: jsonschema, pynacl, cryptography)
python3 tools/generate_vectors.py          # regenerate vectors (deterministic)
python3 tools/run_vectors.py               # Python verdicts vs expect

# The Rust side: dsip-rs at the pinned commit, in ../dsip-rs (or $DSIP_RS), built on this checkout's spec
tools/dsip-rs.sh
(cd ../dsip-rs && DSIP_SPEC=$PWD/.. DSIP_VECTORS=$PWD/../impl/vectors cargo build -p dsip-cli -p dsip-dht)
python3 tools/parity.py                    # Rust vs Python, verdict by verdict
python3 tools/spec_lint.py                 # Spec: lint of the crates + docs/coverage.md

# The TypeScript side, and the three-way checks
(cd ../impl-ts && npm ci && npm run build && npm run vectors)
python3 tools/parity_ts.py --require-all
python3 tools/fuzz.py                      # Python, Rust and TypeScript on generated traces
python3 tools/dht_testnet.py --nodes 5     # dsip-rs's dsip-dht-node, integration
```

A vector change lands here first, with the Python harness and `impl-ts` agreeing on it. dsip-rs then implements it
(its `spec/` submodule at the DSIP commit with the change), and `dsip-rs.rev` moves to that dsip-rs commit, so the
parity job sees all three agree.
