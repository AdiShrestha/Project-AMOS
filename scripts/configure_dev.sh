#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BUILD_DIR="${BPFEAT_BUILD_DIR:-$REPO_ROOT/build-dev}"
BUILD_TYPE="${BPFEAT_BUILD_TYPE:-Debug}"

echo "[BPFeat] Configuring build in $BUILD_DIR (Type: $BUILD_TYPE)..."
echo "$ cmake -S \"$REPO_ROOT\" -B \"$BUILD_DIR\" -DCMAKE_BUILD_TYPE=\"$BUILD_TYPE\" $*"
cmake -S "$REPO_ROOT" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE="$BUILD_TYPE" "$@"
echo "[BPFeat] Configuration complete."
