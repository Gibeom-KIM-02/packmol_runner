#!/usr/bin/env bash
# run.sh
# Usage:
#   ./run.sh
#
# Notes:
# - The Python driver reads config from config/pack.yaml (fixed path).
# - Outputs go to work/: packmol.inp, <stem>.xyz, <stem>.cif, logs/packmol.log

set -euo pipefail

# Resolve repository root (this script lives at repo root)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="${PYTHON_BIN:-python3}"
DRIVER="$ROOT/scripts/build_packed_system.py"
CFG="$ROOT/config/pack.yaml"

# Simple preflight checks
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[ERROR] Python not found (tried: $PY). Set PYTHON_BIN env or install python3." >&2
  exit 1
fi

if [[ ! -f "$DRIVER" ]]; then
  echo "[ERROR] Driver not found: $DRIVER" >&2
  exit 1
fi

if [[ ! -f "$CFG" ]]; then
  echo "[ERROR] Config not found: $CFG" >&2
  exit 1
fi

# Show a tiny summary
echo "[INFO] Using config: $CFG"
echo "[INFO] Running driver: $DRIVER"
echo "[INFO] Python: $("$PY" -V 2>&1)"

# Run
"$PY" "$DRIVER"

