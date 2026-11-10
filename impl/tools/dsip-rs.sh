#!/usr/bin/env bash
# Check out dsip-rs, the Rust implementation, at the commit DSIP is measured against (impl/dsip-rs.rev), into
# dsip-rs/ at the repository root or into $DSIP_RS. Its spec/ submodule is not needed: DSIP's tools build it against
# this checkout (impl/tools/dsip_rs.py). Usage: impl/tools/dsip-rs.sh [commit]  (default: the pinned one)
# Spec: none (infrastructure).
set -euo pipefail
cd "$(dirname "$0")/../.."
REV=${1:-$(cat impl/dsip-rs.rev)}
DIR=${DSIP_RS:-dsip-rs}
URL=${DSIP_RS_URL:-https://github.com/feryx-io/dsip-rs.git}
[ -d "$DIR/.git" ] || git clone -q --no-checkout "$URL" "$DIR"
git -C "$DIR" cat-file -e "$REV^{commit}" 2>/dev/null || git -C "$DIR" fetch -q origin
git -C "$DIR" checkout -q --detach "$REV"
echo "dsip-rs at $(git -C "$DIR" rev-parse --short HEAD) in $DIR"
