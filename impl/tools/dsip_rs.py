"""Where the Rust implementation is: a dsip-rs checkout, built against this repository's spec and vectors.

dsip-rs (github.com/feryx-io/dsip-rs) holds the Rust crates; DSIP measures them at the commit pinned in
`impl/dsip-rs.rev`. `impl/tools/dsip-rs.sh` checks that commit out into `dsip-rs/` at the repository root, or into
`DSIP_RS` if set. The crates normally take the spec from their `spec/` submodule; `env()` points them at this
checkout instead (`DSIP_SPEC`, `DSIP_VECTORS`), so a vector or schema change here is what they are measured on.

Spec: none (infrastructure).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RS = Path(os.environ.get("DSIP_RS", REPO / "dsip-rs")).resolve()


def env() -> dict[str, str]:
    """The environment for a cargo command in `RS`: this checkout's spec and vectors."""
    e = dict(os.environ)
    e["DSIP_SPEC"] = str(REPO)
    e["DSIP_VECTORS"] = str(REPO / "impl" / "vectors")
    return e


def require() -> Path:
    """`RS`, or exit with how to get it."""
    if not (RS / "Cargo.toml").is_file():
        sys.exit(f"no dsip-rs checkout at {RS}: run impl/tools/dsip-rs.sh (or set DSIP_RS)")
    return RS
