#!/usr/bin/env bash
set -euo pipefail

trap 'echo "[ERR] line ${LINENO}: ${BASH_COMMAND}" >&2' ERR

YML="${1:-packmol_ase.yml}"

if ! command -v conda >/dev/null 2>&1; then
  echo "[ERR] conda command not found. Install/enable Miniconda or Anaconda first." >&2
  exit 1
fi

CONDA_BASE="$(conda info --base)"
export PS1="${PS1-}"

set +u
source "${CONDA_BASE}/etc/profile.d/conda.sh"
set -u

if [[ ! -f "${YML}" ]]; then
  echo "[ERR] YAML file not found: ${YML}" >&2
  exit 2
fi

ENV_NAME="$(awk -F': *' '$1=="name"{print $2; exit}' "${YML}")"
if [[ -z "${ENV_NAME}" ]]; then
  echo "[ERR] No 'name:' found in ${YML}" >&2
  exit 3
fi

echo "[INFO] YAML: ${YML}"
echo "[INFO] ENV : ${ENV_NAME}"

if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  echo "[INFO] Env exists -> update"
  conda env update -n "${ENV_NAME}" -f "${YML}" --prune
else
  echo "[INFO] Create env"
  conda env create -f "${YML}"
fi

set +u
conda activate "${ENV_NAME}"
set -u

echo "[INFO] Active python : $(which python)"
echo "[INFO] Active pip    : $(which pip)"

python -m pip install --upgrade pip setuptools wheel

echo "[TEST] python version"
python -V

echo "[TEST] ASE import"
python - <<'PY'
import ase
from ase import Atoms
print("OK: import ase")
print("ASE version:", ase.__version__)
atoms = Atoms("H2O")
print("OK: ASE Atoms object created:", atoms)
PY

echo "[TEST] packmol command"
if command -v packmol >/dev/null 2>&1; then
  echo "OK: packmol found at $(command -v packmol)"
else
  echo "[ERR] packmol not in PATH after installation" >&2
  exit 4
fi

echo "[TEST] PACKMOL smoke test"
TMPDIR_TEST="$(mktemp -d)"
cleanup() {
  rm -rf "${TMPDIR_TEST}"
}
trap cleanup EXIT

cat > "${TMPDIR_TEST}/water.xyz" <<'EOF'
3
water
O  0.000  0.000  0.000
H  0.757  0.586  0.000
H -0.757  0.586  0.000
EOF

cat > "${TMPDIR_TEST}/packmol.inp" <<EOF
tolerance 2.0
filetype xyz
output ${TMPDIR_TEST}/out.xyz

structure ${TMPDIR_TEST}/water.xyz
  number 1
  inside box 0. 0. 0. 5. 5. 5.
end structure
EOF

packmol < "${TMPDIR_TEST}/packmol.inp" >/dev/null

if [[ -f "${TMPDIR_TEST}/out.xyz" ]]; then
  echo "OK: PACKMOL smoke test passed"
else
  echo "[ERR] PACKMOL smoke test failed: output not created" >&2
  exit 5
fi

echo
echo "[DONE] To use it later:"
echo "       conda activate ${ENV_NAME}"
echo "       python -c 'import ase; print(ase.__version__)'"
echo "       packmol < some_input.inp"
