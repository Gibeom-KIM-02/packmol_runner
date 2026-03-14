# 0.create_conda_env — `packmol_ase` Conda Environment

Create or update a Conda environment for the PACKMOL + ASE workflows in this repository.

This installer is intended to provide a simple, reproducible starting environment for:
- PACKMOL-based structure generation
- ASE-based structure reading, writing, and post-processing

---

## What this installer does

The installer:
1. locates your Conda installation
2. creates or updates the Conda environment from `packmol_ase.yml`
3. activates the environment
4. upgrades basic Python packaging tools
5. verifies that ASE can be imported
6. verifies that the `packmol` executable is available
7. runs a minimal PACKMOL smoke test

---

## Files

- `packmol_ase.yml`  
  Conda environment specification for the PACKMOL + ASE workflows
- `install_packmol_ase.sh`  
  One-shot installer and validation script
- `README.md`  
  This file

---

## Requirements

Before running the installer, make sure that:
- Conda is installed and available in your shell
- you can run `conda info --base`
- your shell can source `conda.sh`

---

## Environment contents

The environment currently includes:
- Python 3.10
- NumPy
- PyYAML
- ASE
- PACKMOL
- pip / setuptools / wheel

---

## Usage

From this directory, run:

```bash
bash install_packmol_ase.sh
```

If you want to use a different YAML file:

```bash
bash install_packmol_ase.sh some_other_env.yml
```

---

## What is checked during installation

The script performs the following checks:
- Python is available inside the environment
- `import ase` works
- a simple ASE `Atoms` object can be created
- `packmol` is available in `PATH`
- PACKMOL can generate a minimal output structure from a temporary test input

---

## Expected result

If everything works, you should see messages similar to:

```text
OK: import ase
OK: packmol found at ...
OK: PACKMOL smoke test passed
```

At the end, the script prints:

```bash
conda activate packmol_ase
python -c 'import ase; print(ase.__version__)'
packmol < some_input.inp
```

---

## Notes

- This installer is intentionally minimal.
- It is meant to support the example workflows in this repository, not to provide a full molecular simulation stack.
- If you later add more workflow features, you can extend `packmol_ase.yml` with additional packages.

---

## PACKMOL reference

If PACKMOL is useful in your work, please cite the original reference recommended by the PACKMOL project:

> L. Martínez, R. Andrade, E. G. Birgin, J. M. Martínez.  
> **Packmol: A package for building initial configurations for molecular dynamics simulations.** > *Journal of Computational Chemistry*, 30(13), 2157–2164, 2009.

