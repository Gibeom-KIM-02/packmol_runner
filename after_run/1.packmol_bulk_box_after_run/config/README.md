# Config guide for `pack.yaml` (bulk box example)

This folder contains the YAML configuration file used by the bulk-box PACKMOL example.

## File

- `pack.yaml`  
  Main configuration file for the bulk-box workflow

## Purpose

This example packs molecules into a fully open periodic box.

The file `input_box/empty_box.cif` is used as a box metadata file.  
It is **not** inserted into the PACKMOL input as a fixed structure.

## Main keys

### `mode`

```yaml
mode: bulk
```
Selects bulk-box mode.

### `packmol`

```yaml
packmol:
  cmd: "packmol"
  tolerance: 2.2
  seed: 1234567
```
Controls how PACKMOL is executed.
- `cmd`: PACKMOL executable name or command
- `tolerance`: minimum intermolecular distance used by PACKMOL
- `seed`: random seed for reproducible packing

### `input`

```yaml
input:
  box_file: "input_box/empty_box.cif"
  include_slab_stanza: false
```
Input structure settings.
- `box_file`: box metadata file used for this bulk example
- `include_slab_stanza`: should remain `false` in bulk mode

### `cell`

```yaml
cell:
  x: 30.0
  y: 30.0
  z: 30.0
```
Periodic box lengths in Å.
These values are also used when writing CIF output.

### `pack_region`

```yaml
pack_region:
  x_min: 0.0
  x_max: 30.0
  y_min: 0.0
  y_max: 30.0
  z_min: 0.0
  z_max: 30.0
```
Cartesian region where molecules are placed.
In this example, the full box is filled.

### `species`

```yaml
species:
  - name: cl
    file: "input_files/cl.xyz"
    count: 16
```
List of species to pack.
Each entry includes:
- `name`: label used in log output
- `file`: XYZ file for the molecular template
- `count`: number of copies to place

### `output`

```yaml
output:
  stem: "bulk"
  xyz: true
  cif: true
```
Output file settings.
- `stem`: base filename written into `work/`
- `xyz`: write XYZ output
- `cif`: write CIF output

## Result

With the current settings, this example generates:
- `work/bulk.xyz`
- `work/bulk.cif`
- `work/packmol.inp`
- `work/logs/packmol.log`

## Notes

- This config uses the unified schema shared with the slab example.
- In bulk mode, `include_slab_stanza` should normally be `false`.
- The molecule placement region is explicitly controlled by `pack_region`.
