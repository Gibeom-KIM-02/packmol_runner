# packmol_runner

Minimal PACKMOL + ASE starter workflows for building molecular simulation input structures.

This repository provides small, example-driven workflows for two common use cases:
1. building a bulk molecular box
2. packing molecules into the gap region between fixed slab layers

The goal is to keep the workflows simple, readable, and easy to modify.

---

## Repository structure

```text
packmol_runner/
├─ 0.create_conda_env/
│  ├─ install_packmol_ase.sh
│  ├─ packmol_ase.yml
│  └─ README.md
├─ 1.packmol_bulk_box/
│  ├─ config/
│  ├─ input_box/
│  ├─ input_files/
│  ├─ scripts/
│  ├─ run.sh
│  └─ README.md
├─ 2.packmol_slab/
│  ├─ config/
│  ├─ input_files/
│  ├─ input_slab/
│  ├─ scripts/
│  ├─ run.sh
│  └─ README.md
└─ after_run/
   ├─ 1.packmol_bulk_box_after_run/
   └─ 2.packmol_slab_after_run/
```

---

## What is included

### `0.create_conda_env`
Creates or updates a Conda environment for the workflows in this repository.
This setup installs:
- Python
- ASE
- PACKMOL
- basic Python utilities used by the example scripts

See: `0.create_conda_env/README.md`

### `1.packmol_bulk_box`
A minimal example for packing molecules into a fully open periodic box.
This example:
- uses an empty box metadata file
- packs multiple molecular species into a user-defined Cartesian region
- writes XYZ and optional CIF output

See: `1.packmol_bulk_box/README.md`

### `2.packmol_slab`
A minimal example for packing molecules into the gap region between fixed slab layers.
This example:
- reads a slab structure
- inserts the slab into the PACKMOL input as a fixed structure
- packs molecules only inside the requested gap region
- writes packed XYZ output

See: `2.packmol_slab/README.md`

### `after_run`
Reference folders containing example outputs produced after running the workflows.
These folders are included only as examples of the generated files and output layout.

---

## Quick start

**1. Create the Conda environment**
```bash
cd 0.create_conda_env
bash install_packmol_ase.sh
conda activate packmol_ase
```

**2. Run the bulk example**
```bash
cd ../1.packmol_bulk_box
bash run.sh
```

**3. Run the slab example**
```bash
cd ../2.packmol_slab
bash run.sh
```

---

## Workflow design

Both examples use the same overall pattern:
- configuration is stored in `config/pack.yaml`
- molecular templates are stored in `input_files/`
- the Python driver lives in `scripts/build_packed_system.py`
- generated files are written to `work/`

The examples share a unified YAML schema, but they differ in `mode`:
- `mode: bulk`
- `mode: slab`

---

## Notes

- These workflows are intentionally minimal.
- They are meant to be easy starting points, not a full production workflow framework.
- The examples can be extended for larger boxes, additional species, or different slab systems.

---

## Third-party software

This repository uses or depends on third-party software, including:
- PACKMOL
- ASE (Atomic Simulation Environment)

Please consult the original projects for complete documentation, licensing details, and updates.

---

## Citation

If PACKMOL was useful in your work, please cite one of the references recommended by the PACKMOL project:

> L. Martínez, R. Andrade, E. G. Birgin, J. M. Martínez.  
> **Packmol: A package for building initial configurations for molecular dynamics simulations.** > *Journal of Computational Chemistry*, 30, 2157–2164, 2009.

> J. M. Martínez, L. Martínez.  
> **Packing optimization for the automated generation of complex system's initial configurations for molecular dynamics and docking.** > *Journal of Computational Chemistry*, 24, 819–825, 2003.

---

## License

The original workflow assembly and example scripts in this repository are distributed under the **MIT License**.

This repository relies on third-party software distributed under their own licenses.

### Third-party software licenses
- **PACKMOL** — MIT License
- **ASE (Atomic Simulation Environment)** — GNU Lesser General Public License (LGPL)

Those third-party components remain the property of their respective authors and are governed by their original license terms.
