#!/bin/bash

set -euo pipefail

# ==============================
# Software Factory Bootstrap
# ==============================

FACTORY_REPO="git@github.com:AdiShrestha/software-factory.git"

# Usage:
# ./bootstrap.sh            -> latest main
# ./bootstrap.sh v1.0.1     -> specific version/tag
# ./bootstrap.sh develop    -> specific branch
# ./bootstrap.sh <commit>   -> specific commit

FACTORY_REF="${1:-main}"

TEMP_DIR=".factory_temp"

FACTORY_DIR="factory"
PROJECT_DIR="project"
SOURCE_DIR="source"

cleanup_on_exit() {
    EXIT_CODE=$?

    rm -rf "$TEMP_DIR"

    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        echo "================================="
        echo " Bootstrap Failed"
        echo " Rolling back changes..."
        echo "================================="

        rm -rf "$FACTORY_DIR"
        rm -rf "$PROJECT_DIR"
        rm -rf "$SOURCE_DIR"
    fi

    exit $EXIT_CODE
}

trap cleanup_on_exit EXIT

echo "================================="
echo " Software Factory Bootstrap"
echo "================================="
echo ""

echo "Factory Repository:"
echo "$FACTORY_REPO"

echo ""

echo "Requested Version:"
echo "$FACTORY_REF"

echo ""

# ==============================
# Validate empty directory
# ==============================

for d in "$FACTORY_DIR" "$PROJECT_DIR" "$SOURCE_DIR" "$TEMP_DIR"; do
    if [ -e "$d" ]; then
        echo "ERROR: '$d' already exists."
        echo "Run bootstrap inside a clean project directory."
        exit 1
    fi
done

read -r -p "Bootstrap into $(pwd)? [y/N] " CONFIRM

if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "Cancelled."
    exit 0
fi

# ==============================
# Clone Factory
# ==============================

echo ""
echo "[1/7] Cloning Factory..."

git clone \
    "$FACTORY_REPO" \
    "$TEMP_DIR"

echo ""
echo "Checking out:"
echo "$FACTORY_REF"

git -C "$TEMP_DIR" checkout "$FACTORY_REF"

# ==============================
# Validate Factory
# ==============================

echo ""
echo "[2/7] Validating Factory..."

if [ ! -d "$TEMP_DIR/factory" ]; then
    echo "ERROR: Invalid Factory repository."
    echo "Missing factory/ directory."
    exit 1
fi

if [ ! -f "$TEMP_DIR/factory/VERSION" ]; then
    echo "ERROR: Invalid Factory repository."
    echo "Missing factory/VERSION."
    exit 1
fi

VERSION=$(cat "$TEMP_DIR/factory/VERSION")

COMMIT=$(git -C "$TEMP_DIR" rev-parse HEAD)

SHORT_COMMIT=$(git -C "$TEMP_DIR" rev-parse --short HEAD)

echo "Factory Version : $VERSION"
echo "Factory Commit  : $SHORT_COMMIT"

# ==============================
# Copy Factory
# ==============================

echo ""
echo "[3/7] Copying Factory..."

cp -R "$TEMP_DIR/factory" "$FACTORY_DIR"

# ==============================
# Create Project Structure
# ==============================

echo ""
echo "[4/7] Creating Project Structure..."

mkdir -p "$PROJECT_DIR/chunks"
mkdir -p "$SOURCE_DIR"

# ==============================
# Create .gitignore
# ==============================

echo ""
echo "[5/7] Updating .gitignore..."

touch .gitignore

grep -qxF "factory/" .gitignore || echo "factory/" >> .gitignore
grep -qxF "project/" .gitignore || echo "project/" >> .gitignore
grep -qxF "bootstrap.sh" .gitignore || echo "bootstrap.sh" >> .gitignore

# ==============================
# Record Provenance
# ==============================

echo ""
echo "[6/7] Recording Factory Information..."

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > "$PROJECT_DIR/factory_info.json" <<EOF
{
  "factory_version": "$VERSION",
  "factory_reference": "$FACTORY_REF",
  "factory_commit": "$COMMIT",
  "factory_repository": "$FACTORY_REPO",
  "bootstrapped_on": "$TIMESTAMP",
  "bootstrap_command": "$0 $*"
}
EOF

cat > "$PROJECT_DIR/factory_info.md" <<EOF
# Factory Information

Factory Version

$VERSION

Factory Reference

$FACTORY_REF

Factory Commit

$COMMIT

Bootstrapped On

$TIMESTAMP

Factory Repository

$FACTORY_REPO

Bootstrap Command

$0 $*
EOF

# ==============================
# Finish
# ==============================

echo ""
echo "[7/7] Finalizing..."

echo ""
echo "================================="
echo " Bootstrap Complete"
echo "================================="
echo ""

echo "Created"

echo "  factory/"
echo "  project/"
echo "  project/chunks/"
echo "  project/factory_info.md"
echo "  project/factory_info.json"
echo "  source/"
echo "  .gitignore"

echo ""
echo "Factory Version:"
echo "$VERSION"

echo ""
echo "Factory Commit:"
echo "$SHORT_COMMIT"

echo ""
echo "Next Step:"
echo ""
echo "Bootstrap this project according to Factory $VERSION"