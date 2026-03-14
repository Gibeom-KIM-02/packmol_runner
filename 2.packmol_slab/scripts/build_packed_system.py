#!/usr/bin/env python3
"""
Unified PACKMOL driver for both slab mode and bulk-box mode.

Supported use cases
-------------------
1. Slab mode
   - Reads a slab structure with ASE
   - Computes XY bounds from the slab coordinates
   - Packs molecules only within the requested Z region
   - Includes the slab as a fixed structure in the PACKMOL input

2. Bulk mode
   - Uses an empty box / target cell definition
   - Packs molecules into a bulk box without requiring a real slab
   - Can keep an empty_box.cif for compatibility and cell metadata
   - By default, does not include the empty box as a fixed PACKMOL structure

This script is intentionally designed to be compatible with both:
- the existing slab-style config
- the existing bulk-style config with empty_box.cif
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml
from ase import Atoms
from ase.io import read, write


@dataclass
class SpeciesSpec:
    """Single molecular species specification."""

    name: str
    file: Path
    count: int


@dataclass
class BoxBounds:
    """Cartesian packing region used for PACKMOL inside box."""

    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float

    def validate(self) -> None:
        """Validate that the box dimensions are physically meaningful."""
        if not (self.x1 > self.x0):
            raise ValueError("Invalid packing box: x1 must be greater than x0.")
        if not (self.y1 > self.y0):
            raise ValueError("Invalid packing box: y1 must be greater than y0.")
        if not (self.z1 > self.z0):
            raise ValueError("Invalid packing box: z1 must be greater than z0.")

    def as_packmol_inside_box(self) -> str:
        """Return PACKMOL inside box string."""
        return (
            f"{self.x0:.3f} {self.y0:.3f} {self.z0:.3f}  "
            f"{self.x1:.3f} {self.y1:.3f} {self.z1:.3f}"
        )


@dataclass
class OutputSpec:
    """Output file options."""

    stem: str
    write_xyz: bool
    write_cif: bool


@dataclass
class ParsedConfig:
    """Fully parsed and normalized configuration."""

    mode: str
    packmol_cmd: str
    tolerance: float
    seed: Optional[int]
    slab_path: Optional[Path]
    include_slab_stanza: bool
    species: list[SpeciesSpec]
    pack_region: BoxBounds
    output: OutputSpec
    cell_lengths: Optional[tuple[float, float, float]]


class ConfigLoader:
    """Load, normalize, and validate YAML configuration."""

    def __init__(self, root_dir: Path, config_path: Path) -> None:
        self.root_dir = root_dir
        self.config_path = config_path
        self.cfg = self._load_yaml()

    def _load_yaml(self) -> dict[str, Any]:
        """Load YAML config file."""
        if not self.config_path.exists():
            sys.exit(f"[ERROR] Config not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        if not isinstance(data, dict):
            sys.exit("[ERROR] Top-level YAML structure must be a mapping.")
        return data

    def parse(self) -> ParsedConfig:
        """Parse all config sections into a normalized config object."""
        mode = self._infer_mode()
        packmol_cmd = self._get_packmol_cmd()
        tolerance = self._get_tolerance()
        seed = self._get_seed()
        slab_path = self._get_slab_path(mode)
        include_slab_stanza = self._get_include_slab_stanza(mode)
        species = self._parse_species()
        pack_region = self._build_pack_region(mode, slab_path)
        output = self._parse_output()
        cell_lengths = self._determine_cell_lengths(mode, slab_path, pack_region)

        return ParsedConfig(
            mode=mode,
            packmol_cmd=packmol_cmd,
            tolerance=tolerance,
            seed=seed,
            slab_path=slab_path,
            include_slab_stanza=include_slab_stanza,
            species=species,
            pack_region=pack_region,
            output=output,
            cell_lengths=cell_lengths,
        )

    def _infer_mode(self) -> str:
        """
        Infer packing mode.

        Priority:
        1. Explicit top-level 'mode'
        2. Legacy bulk config: box_mode.enabled == true
        3. Otherwise default to slab mode
        """
        explicit_mode = self.cfg.get("mode")
        if explicit_mode is not None:
            mode = str(explicit_mode).strip().lower()
            if mode not in {"bulk", "slab"}:
                sys.exit("[ERROR] 'mode' must be either 'bulk' or 'slab'.")
            return mode

        box_mode = self.cfg.get("box_mode", {}) or {}
        if bool(box_mode.get("enabled", False)):
            return "bulk"

        return "slab"

    def _get_packmol_cmd(self) -> str:
        """Get PACKMOL executable command."""
        packmol_cfg = self.cfg.get("packmol", {}) or {}
        cmd = str(packmol_cfg.get("cmd", "packmol")).strip()
        if not cmd:
            sys.exit("[ERROR] PACKMOL command is empty.")
        return cmd

    def _get_tolerance(self) -> float:
        """Get PACKMOL tolerance from either packmol or packing section."""
        packmol_cfg = self.cfg.get("packmol", {}) or {}
        packing_cfg = self.cfg.get("packing", {}) or {}
        return float(packmol_cfg.get("tolerance", packing_cfg.get("tolerance", 2.0)))

    def _get_seed(self) -> Optional[int]:
        """Get optional PACKMOL random seed."""
        packmol_cfg = self.cfg.get("packmol", {}) or {}
        packing_cfg = self.cfg.get("packing", {}) or {}
        raw_seed = packmol_cfg.get("seed", packing_cfg.get("seed", None))
        return None if raw_seed is None else int(raw_seed)

    def _get_include_slab_stanza(self, mode: str) -> bool:
        """
        Decide whether to include a fixed slab structure in the PACKMOL input.
    
        Priority:
        1. input.include_slab_stanza
        2. legacy bulk config: box_mode.include_slab_stanza
        3. default: True for slab mode, False for bulk mode
        """
        input_cfg = self.cfg.get("input", {}) or {}
        if "include_slab_stanza" in input_cfg:
            return bool(input_cfg.get("include_slab_stanza"))
    
        box_mode = self.cfg.get("box_mode", {}) or {}
        if "include_slab_stanza" in box_mode:
            return bool(box_mode.get("include_slab_stanza"))
    
        return mode == "slab"

    def _get_slab_path(self, mode: str) -> Optional[Path]:
        """
        Resolve structure path from multiple supported config styles.
    
        Supported keys
        --------------
        Slab mode:
        - input.slab_file
        - system.slab_file
        - slab.file
    
        Bulk mode:
        - input.box_file
        - box.file
        - input.slab_file      (legacy compatibility)
        - slab.file            (legacy compatibility)
        """
        input_cfg = self.cfg.get("input", {}) or {}
        system_cfg = self.cfg.get("system", {}) or {}
        slab_cfg = self.cfg.get("slab", {}) or {}
        box_cfg = self.cfg.get("box", {}) or {}
    
        if mode == "bulk":
            raw_path = (
                input_cfg.get("box_file")
                or box_cfg.get("file")
                or input_cfg.get("slab_file")
                or slab_cfg.get("file")
            )
        else:
            raw_path = (
                input_cfg.get("slab_file")
                or system_cfg.get("slab_file")
                or slab_cfg.get("file")
            )
    
        if raw_path is None:
            if mode == "slab":
                sys.exit("[ERROR] A slab file is required in slab mode.")
            return None
    
        slab_path = (self.root_dir / str(raw_path)).resolve()
        if not slab_path.exists():
            sys.exit(f"[ERROR] Structure file not found: {slab_path}")
        return slab_path

    def _parse_species(self) -> list[SpeciesSpec]:
        """
        Parse species from either:
        - system.species (list style)
        - top-level species (list style)
        - top-level species (dict style)
        """
        system_cfg = self.cfg.get("system", {}) or {}

        if "species" in system_cfg:
            raw_species = system_cfg.get("species", [])
        else:
            raw_species = self.cfg.get("species", [])

        if not raw_species:
            sys.exit("[ERROR] No species were defined in the config.")

        species_list: list[SpeciesSpec] = []

        if isinstance(raw_species, list):
            for item in raw_species:
                if not isinstance(item, dict):
                    sys.exit("[ERROR] Each species entry must be a mapping.")
                species_list.append(self._build_species_from_item(item))
            return species_list

        if isinstance(raw_species, dict):
            ordered_items = self._ordered_species_items(raw_species)
            for name, item in ordered_items:
                if not isinstance(item, dict):
                    sys.exit(f"[ERROR] Species '{name}' must be a mapping.")
                merged = {"name": name, **item}
                species_list.append(self._build_species_from_item(merged))
            return species_list

        sys.exit("[ERROR] 'species' must be either a list or a mapping.")

    def _parse_output(self) -> OutputSpec:
        """
        Parse output settings from either:
        - output
        - legacy outputs
        """
        output_cfg = self.cfg.get("output", self.cfg.get("outputs", {})) or {}
    
        stem = str(output_cfg.get("stem", "packed_system")).strip()
        if not stem:
            stem = "packed_system"
    
        write_xyz = bool(output_cfg.get("xyz", True))
        write_cif = bool(output_cfg.get("cif", False))
    
        return OutputSpec(
            stem=stem,
            write_xyz=write_xyz,
            write_cif=write_cif,
        )

    def _ordered_species_items(
        self, raw_species: dict[str, Any]
    ) -> list[tuple[str, dict[str, Any]]]:
        """
        Preserve user-defined PACKMOL order for dict-style species configs.

        If packing.order exists, it is applied first.
        Remaining species are appended in YAML insertion order.
        """
        packing_cfg = self.cfg.get("packing", {}) or {}
        requested_order = packing_cfg.get("order", []) or []

        ordered: list[tuple[str, dict[str, Any]]] = []
        used: set[str] = set()

        for name in requested_order:
            if name in raw_species:
                ordered.append((name, raw_species[name] or {}))
                used.add(name)

        for name, item in raw_species.items():
            if name not in used:
                ordered.append((name, item or {}))

        return ordered

    def _build_species_from_item(self, item: dict[str, Any]) -> SpeciesSpec:
        """Build a SpeciesSpec from a single config item."""
        if "file" not in item:
            sys.exit("[ERROR] Each species entry must include 'file'.")
        if "count" not in item:
            sys.exit("[ERROR] Each species entry must include 'count'.")

        name = str(item.get("name", "")).strip() or "(unnamed)"
        file_path = (self.root_dir / str(item["file"])).resolve()
        count = int(item.get("count", 0))

        if not file_path.exists():
            sys.exit(f"[ERROR] Species file not found: {file_path}")
        if count < 0:
            sys.exit(f"[ERROR] Species count must be non-negative for '{name}'.")

        return SpeciesSpec(name=name, file=file_path, count=count)

    def _build_pack_region(self, mode: str, slab_path: Optional[Path]) -> BoxBounds:
        """
        Build the final packing region.

        Priority:
        1. Explicit top-level pack_region
        2. Legacy bulk/slab config fallback
        """
        explicit_region = self.cfg.get("pack_region", None)
        if explicit_region is not None:
            region = self._parse_explicit_pack_region(explicit_region)
            region.validate()
            return region

        if mode == "bulk":
            region = self._build_bulk_region_legacy(slab_path)
        else:
            region = self._build_slab_region_legacy(slab_path)

        region.validate()
        return region

    def _parse_explicit_pack_region(self, region_cfg: dict[str, Any]) -> BoxBounds:
        """Parse explicit top-level pack_region."""
        required = ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]
        missing = [key for key in required if key not in region_cfg]
        if missing:
            sys.exit(
                "[ERROR] Missing keys in pack_region: " + ", ".join(missing)
            )

        return BoxBounds(
            x0=float(region_cfg["x_min"]),
            x1=float(region_cfg["x_max"]),
            y0=float(region_cfg["y_min"]),
            y1=float(region_cfg["y_max"]),
            z0=float(region_cfg["z_min"]),
            z1=float(region_cfg["z_max"]),
        )

    def _build_bulk_region_legacy(self, slab_path: Optional[Path]) -> BoxBounds:
        """
        Build region from legacy bulk config.

        Supported keys:
        - target_cell.x/y/z
        - solvent_region.margin
        - solvent_region.z_start
        - solvent_region.z_limit
        """
        target_cell = self.cfg.get("target_cell", {}) or {}
        solvent_region = self.cfg.get("solvent_region", {}) or {}

        cell_lengths = self._parse_cell_like(target_cell)
        if cell_lengths is None and slab_path is not None:
            cell_lengths = self._read_cell_lengths_from_structure(slab_path)

        if cell_lengths is None:
            sys.exit(
                "[ERROR] Bulk mode requires target_cell or a slab/box structure with cell information."
            )

        cell_x, cell_y, cell_z = cell_lengths
        margin = float(solvent_region.get("margin", 0.0))

        x0 = float(solvent_region.get("x_start", margin))
        y0 = float(solvent_region.get("y_start", margin))
        z0 = float(solvent_region.get("z_start", margin))

        x1 = float(solvent_region.get("x_end", cell_x - margin))
        y1 = float(solvent_region.get("y_end", cell_y - margin))
        z1 = float(solvent_region.get("z_limit", cell_z - margin))

        return BoxBounds(x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1)

    def _build_slab_region_legacy(self, slab_path: Optional[Path]) -> BoxBounds:
        """
        Build region from legacy slab config.

        Supported keys:
        - region.xy_margin
        - region.z_start
        - region.z_end
        """
        if slab_path is None:
            sys.exit("[ERROR] A slab file is required to compute slab bounds.")

        region_cfg = self.cfg.get("region", {}) or {}
        xmin, xmax, ymin, ymax, zmin, zmax = self._read_coordinate_bounds(slab_path)

        xy_margin = float(region_cfg.get("xy_margin", 0.0))
        z_start = float(region_cfg.get("z_start", zmin))
        z_end = float(region_cfg.get("z_end", zmax))

        if not (z_start < z_end):
            sys.exit("[ERROR] region.z_start must be smaller than region.z_end.")

        return BoxBounds(
            x0=xmin + xy_margin,
            x1=xmax - xy_margin,
            y0=ymin + xy_margin,
            y1=ymax - xy_margin,
            z0=z_start,
            z1=z_end,
        )

    def _determine_cell_lengths(
        self,
        mode: str,
        slab_path: Optional[Path],
        pack_region: BoxBounds,
    ) -> Optional[tuple[float, float, float]]:
        """
        Determine cell lengths for optional CIF writing.

        Priority:
        1. top-level cell
        2. target_cell
        3. slab file cell (if ASE structure has a valid cell)
        4. bulk-mode fallback: use pack region lengths
        """
        explicit_cell = self.cfg.get("cell", None)
        parsed_explicit = self._parse_cell_like(explicit_cell)
        if parsed_explicit is not None:
            return parsed_explicit

        target_cell = self.cfg.get("target_cell", None)
        parsed_target = self._parse_cell_like(target_cell)
        if parsed_target is not None:
            return parsed_target

        if slab_path is not None:
            slab_cell = self._read_cell_lengths_from_structure(slab_path)
            if slab_cell is not None:
                return slab_cell

        if mode == "bulk":
            return (
                float(pack_region.x1 - pack_region.x0),
                float(pack_region.y1 - pack_region.y0),
                float(pack_region.z1 - pack_region.z0),
            )

        return None

    def _parse_cell_like(
        self, raw_cell: Any
    ) -> Optional[tuple[float, float, float]]:
        """Parse a cell-like object from either dict or 3-element list/tuple."""
        if raw_cell is None:
            return None

        if isinstance(raw_cell, dict):
            if all(key in raw_cell for key in ("x", "y", "z")):
                return (
                    float(raw_cell["x"]),
                    float(raw_cell["y"]),
                    float(raw_cell["z"]),
                )
            return None

        if isinstance(raw_cell, (list, tuple)) and len(raw_cell) == 3:
            return (float(raw_cell[0]), float(raw_cell[1]), float(raw_cell[2]))

        return None

    def _read_coordinate_bounds(
        self, structure_path: Path
    ) -> tuple[float, float, float, float, float, float]:
        """Read coordinate bounds from a structure file using ASE."""
        atoms = read(structure_path)
        positions = atoms.get_positions()
        xmin, ymin, zmin = positions.min(axis=0)
        xmax, ymax, zmax = positions.max(axis=0)
        return (
            float(xmin),
            float(xmax),
            float(ymin),
            float(ymax),
            float(zmin),
            float(zmax),
        )

    def _read_cell_lengths_from_structure(
        self, structure_path: Path
    ) -> Optional[tuple[float, float, float]]:
        """Read cell lengths from a structure file if valid nonzero cell information exists."""
        atoms = read(structure_path)
        a, b, c = atoms.cell.lengths()
        if a > 0.0 and b > 0.0 and c > 0.0:
            return (float(a), float(b), float(c))
        return None


class PackmolInputBuilder:
    """Build PACKMOL input and any temporary structure files needed by PACKMOL."""

    def __init__(self, parsed: ParsedConfig, work_dir: Path) -> None:
        self.parsed = parsed
        self.work_dir = work_dir

    def prepare_fixed_slab_xyz(self) -> Optional[Path]:
        """
        Prepare a fixed slab file for PACKMOL.

        PACKMOL is most reliably used with XYZ structures here, so the slab
        is converted to a temporary XYZ file when needed.
        """
        if not self.parsed.include_slab_stanza:
            return None

        if self.parsed.slab_path is None:
            sys.exit("[ERROR] Slab stanza was requested, but no slab path is available.")

        slab_atoms = read(self.parsed.slab_path)
        slab_xyz_path = self.work_dir / "fixed_slab_for_packmol.xyz"
        write(slab_xyz_path, slab_atoms)
        return slab_xyz_path.resolve()

    def write_input(
        self,
        input_path: Path,
        output_xyz_name: str,
        fixed_slab_xyz: Optional[Path],
    ) -> None:
        """Write final PACKMOL input file."""
        lines: list[str] = []
        lines.append(f"tolerance {self.parsed.tolerance:.6f}")
        lines.append("filetype xyz")
        lines.append(f"output {output_xyz_name}")

        if self.parsed.seed is not None:
            lines.append(f"seed {self.parsed.seed}")

        lines.append("")

        if fixed_slab_xyz is not None:
            lines.extend(
                [
                    f"structure {fixed_slab_xyz}",
                    "  number 1",
                    "  fixed 0. 0. 0. 0. 0. 0.",
                    "end structure",
                    "",
                ]
            )

        box_string = self.parsed.pack_region.as_packmol_inside_box()
        for species in self.parsed.species:
            if species.count <= 0:
                continue

            lines.extend(
                [
                    f"structure {species.file}",
                    f"  number {species.count}",
                    f"  inside box {box_string}",
                    "end structure",
                    "",
                ]
            )

        input_path.write_text("\n".join(lines), encoding="utf-8")


class PackmolRunner:
    """Run PACKMOL and manage logging."""

    def __init__(self, packmol_cmd: str) -> None:
        self.packmol_cmd = packmol_cmd

    def _resolve_command(self) -> list[str]:
        """Resolve PACKMOL command into an executable argument list."""
        cmd_parts = shlex.split(self.packmol_cmd)
        if not cmd_parts:
            sys.exit("[ERROR] PACKMOL command is empty.")

        executable = cmd_parts[0]
        if shutil.which(executable) is None:
            sys.exit(f"[ERROR] PACKMOL not found in PATH: {executable}")

        return cmd_parts

    def run(self, input_path: Path, log_path: Path, work_dir: Path) -> None:
        """Run PACKMOL with stdin redirected from input file."""
        cmd_parts = self._resolve_command()

        with open(input_path, "r", encoding="utf-8") as fin, open(
            log_path, "w", encoding="utf-8"
        ) as flog:
            proc = subprocess.run(
                cmd_parts,
                stdin=fin,
                stdout=flog,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=work_dir,
            )

        if proc.returncode != 0:
            sys.exit(f"[ERROR] PACKMOL failed. See log: {log_path}")


class OutputWriter:
    """Write optional post-processed outputs such as CIF."""

    def __init__(self, parsed: ParsedConfig) -> None:
        self.parsed = parsed

    def normalize_xyz_header(self, xyz_path: Path) -> None:
        """
        Normalize the XYZ header written by PACKMOL.

        PACKMOL may write the atom count with leading spaces.
        This method rewrites the first line as a plain integer string.
        """
        lines = xyz_path.read_text(encoding="utf-8").splitlines()
        if len(lines) < 2:
            raise ValueError(f"Invalid XYZ file: {xyz_path}")

        atom_count = lines[0].strip()
        comment = lines[1].rstrip()

        normalized_lines = [atom_count, comment]
        normalized_lines.extend(line.rstrip() for line in lines[2:])

        xyz_path.write_text("\n".join(normalized_lines) + "\n", encoding="utf-8")

    def write_optional_cif(self, xyz_path: Path) -> Optional[Path]:
        """Write CIF if requested and if cell information is available."""
        if not self.parsed.output.write_cif:
            return None

        if self.parsed.cell_lengths is None:
            print(
                "[WARN] CIF output was requested, but no valid cell information is available. Skipping CIF."
            )
            return None

        atoms = read(xyz_path)
        cell_x, cell_y, cell_z = self.parsed.cell_lengths
        atoms.set_cell([cell_x, cell_y, cell_z])
        atoms.set_pbc([True, True, True])

        cif_path = xyz_path.with_suffix(".cif")
        write(cif_path, atoms)
        return cif_path


class PackedSystemBuilder:
    """Top-level orchestration class."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.config_path = self.root_dir / "config" / "pack.yaml"
        self.work_dir = self.root_dir / "work"
        self.logs_dir = self.work_dir / "logs"

    def ensure_dirs(self) -> None:
        """Create output directories."""
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> None:
        """Run the full workflow."""
        self.ensure_dirs()

        loader = ConfigLoader(self.root_dir, self.config_path)
        parsed = loader.parse()

        self._print_summary(parsed)

        input_builder = PackmolInputBuilder(parsed, self.work_dir)
        fixed_slab_xyz = input_builder.prepare_fixed_slab_xyz()

        input_path = self.work_dir / "packmol.inp"
        log_path = self.logs_dir / "packmol.log"
        output_xyz_name = f"{parsed.output.stem}.xyz"
        output_xyz_path = self.work_dir / output_xyz_name

        input_builder.write_input(
            input_path=input_path,
            output_xyz_name=output_xyz_name,
            fixed_slab_xyz=fixed_slab_xyz,
        )

        print(f"[INFO] PACKMOL input written to: {input_path}")
        print(f"[INFO] Running PACKMOL in: {self.work_dir}")

        runner = PackmolRunner(parsed.packmol_cmd)
        runner.run(input_path=input_path, log_path=log_path, work_dir=self.work_dir)

        if not output_xyz_path.exists():
            sys.exit("[ERROR] PACKMOL finished, but the output XYZ file was not found.")

        output_writer = OutputWriter(parsed)
        output_writer.normalize_xyz_header(output_xyz_path)
        
        print(f"[OK] XYZ output written: {output_xyz_path}")
        print(f"[OK] PACKMOL log written: {log_path}")
        
        cif_path = output_writer.write_optional_cif(output_xyz_path)
        if cif_path is not None:
            print(f"[OK] CIF output written: {cif_path}")

        if not parsed.output.write_xyz and output_xyz_path.exists():
            output_xyz_path.unlink()
            print("[INFO] XYZ output was removed because output.xyz was set to false.")

    def _print_summary(self, parsed: ParsedConfig) -> None:
        """Print a concise runtime summary."""
        region = parsed.pack_region

        print(f"[INFO] Mode: {parsed.mode}")
        print(f"[INFO] PACKMOL command: {parsed.packmol_cmd}")
        print(f"[INFO] Tolerance: {parsed.tolerance:.6f}")
        if parsed.seed is not None:
            print(f"[INFO] Seed: {parsed.seed}")

        if parsed.slab_path is not None:
            print(f"[INFO] Slab path: {parsed.slab_path}")
        print(f"[INFO] Include slab stanza: {parsed.include_slab_stanza}")

        print("[INFO] Packing region:")
        print(f"  X: [{region.x0:.3f}, {region.x1:.3f}]")
        print(f"  Y: [{region.y0:.3f}, {region.y1:.3f}]")
        print(f"  Z: [{region.z0:.3f}, {region.z1:.3f}]")

        print("[INFO] Species:")
        for species in parsed.species:
            print(f"  - {species.name}: {species.file} x {species.count}")

        print("[INFO] Outputs:")
        print(f"  stem: {parsed.output.stem}")
        print(f"  xyz : {parsed.output.write_xyz}")
        print(f"  cif : {parsed.output.write_cif}")


def main() -> None:
    """Entry point."""
    script_path = Path(__file__).resolve()
    root_dir = script_path.parents[1]
    builder = PackedSystemBuilder(root_dir)
    builder.run()


if __name__ == "__main__":
    main()
