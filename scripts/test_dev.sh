#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BUILD_DIR="${BPFEAT_BUILD_DIR:-$REPO_ROOT/build-dev}"

if [ ! -f "$BUILD_DIR/Makefile" ] && [ ! -f "$BUILD_DIR/build.ninja" ] && [ ! -f "$BUILD_DIR/CMakeCache.txt" ]; then
    echo "[BPFeat] Build directory $BUILD_DIR not configured. Running configure first..."
    bash "$REPO_ROOT/scripts/configure_dev.sh"
fi

echo "[BPFeat] Building in $BUILD_DIR..."
echo "$ cmake --build \"$BUILD_DIR\" --parallel 2"
cmake --build "$BUILD_DIR" --parallel 2

echo "[BPFeat] Running test suite..."
echo "$ ctest --test-dir \"$BUILD_DIR\" --output-on-failure $*"
ctest --test-dir "$BUILD_DIR" --output-on-failure "$@"
echo "[BPFeat] All CTest tests executed."
