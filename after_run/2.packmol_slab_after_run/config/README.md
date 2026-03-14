# Config guide for `pack.yaml` (slab gap example)

This folder contains the YAML configuration file used by the slab-gap PACKMOL example.

## File

- `pack.yaml`  
  Main configuration file for the slab-gap workflow

## Purpose

This example packs molecules into the gap region between fixed slab layers.

The slab structure is inserted into the PACKMOL input as a fixed structure so that molecules are placed around the slab atoms rather than overlapping them.

## Main keys

### `mode`

```yaml
mode: slab
```
Selects slab mode.

### `packmol`

```yaml
packmol:
  cmd: "packmol"
  tolerance: 2.0
  seed: 7777777
```
Controls how PACKMOL is executed.
- `cmd`: PACKMOL executable name or command
- `tolerance`: minimum intermolecular distance used by PACKMOL
- `seed`: random seed for reproducible packing

### `input`

```yaml
input:
  slab_file: "input_slab/graphene_slab_gap_6.0nm.xyz"
  include_slab_stanza: true
```
Input slab settings.
- `slab_file`: slab structure used for confined packing
- `include_slab_stanza`: should normally be `true` in slab mode

### `pack_region`

```yaml
pack_region:
  x_min: 0.618
  x_max: 11.732
  y_min: 0.356
  y_max: 12.477
  z_min: 2.0
  z_max: 58.0
```
Cartesian region where molecules are placed.
This region should match the physically open slab gap where packing is allowed.

### `species`

```yaml
species:
  - name: cl
    file: "input_files/cl.xyz"
    count: 8
```
List of species to pack.
Each entry includes:
- `name`: label used in log output
- `file`: XYZ file for the molecular template
- `count`: number of copies to place

### `output`

```yaml
output:
  stem: "graphene_slab_water_pack"
  xyz: true
  cif: false
```
Output file settings.
- `stem`: base filename written into `work/`
- `xyz`: write XYZ output
- `cif`: write CIF output

## Optional cell section

If you later want CIF output, you can define the cell lengths explicitly:

```yaml
cell:
  x: 12.350
  y: 12.833
  z: 60.000
```
This is useful when the slab input file does not already contain reliable cell information.

## Result

With the current settings, this example generates:
- `work/graphene_slab_water_pack.xyz`
- `work/packmol.inp`
- `work/fixed_slab_for_packmol.xyz`
- `work/logs/packmol.log`

## Notes

- This config uses the unified schema shared with the bulk example.
- In slab mode, `include_slab_stanza` is usually `true`.
- The packing region should be chosen carefully to match the accessible gap volume.
