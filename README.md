# gerber2svg

`gerber2svg` converts one PCB copper Gerber file into an SVG of the copper, the board surface outside the copper, or a narrow isolation band. It is a geometry converter. LightBurn and MillMage still generate laser scan lines, milling toolpaths, feeds, and cutter compensation.

## Supported Gerber

The converter reads RS-274X through Gerbonara 1.6.3, in millimeters or inches. It polygonizes circular, rectangular, and round-ended apertures, arcs, regions, aperture macros Gerbonara can render, and step-and-repeat blocks. Dark and clear polarity are applied in file order.

### Remarks

A standard aperture hole stays a hole. A file that contains `%IPNEG*%` is rejected. Negative image polarity needs a dark background that Gerbonara does not create. An unsupported primitive type is an error that names the type. Arcs are flattened with Gerbonara `approximate_arcs`, and the maximum sagitta is `--curve-tolerance` (default 0.005 mm). Outline files are read as centerlines. Endpoints within 0.01 mm are joined. A contained closed ring is a cutout. An open contour is an error that reports the gap.

## Installation

```bash
pip install -e ".[dev]"
```

Requires Python 3.11 or newer.

## CLI

```bash
gerber2svg --copper board-F_Cu.gbr --outline board-Edge_Cuts.gbr --mode negative --output removal.svg
```

| Flag | Meaning |
|---|---|
| `--copper` | Copper Gerber file. Required. |
| `--outline` | Board outline Gerber. Optional. |
| `--output` | SVG path. Required. |
| `--mode` | `copper`, `negative`, or `isolation`. Required. |
| `--clearance` | Millimeters added around copper before a negative subtraction. Default 0. Valid only in negative mode. |
| `--width` | Isolation band width in millimeters. Required for isolation mode and rejected otherwise. |
| `--curve-tolerance` | Maximum chord error in millimeters. Default 0.005. |
| `--svg-strategy` | `compound` (default) or `contours`. |
| `--margin` | Extra millimeters around the copper bounds when no outline is given. Default 0. Rejected when an outline is given. |
| `--origin` | `board-min` (default) or `preserve`. |
| `--mirror-x`, `--mirror-y` | Flip in Gerber millimeters about the origin, before SVG export. |
| `--verbose` | Print the primitive count and areas. |
| `--help`, `--version` | Usage and package version. |

Exit codes: 0 success, including warnings; 2 configuration; 3 Gerber or outline; 4 geometry; 5 SVG write.

## Examples

```bash
gerber2svg --copper tests/fixtures/board_e2e_copper.gbr --outline tests/fixtures/board_e2e_outline.gbr --mode copper --output examples/copper.svg
gerber2svg --copper tests/fixtures/board_e2e_copper.gbr --outline tests/fixtures/board_e2e_outline.gbr --mode negative --output examples/negative.svg
gerber2svg --copper tests/fixtures/board_e2e_copper.gbr --outline tests/fixtures/board_e2e_outline.gbr --mode isolation --width 0.3 --output examples/isolation.svg
```

## Copper and removal geometry

`copper` exports the interpreted copper, including any copper that extends outside the board. `negative` exports the board minus the copper. That is the paint the laser removes, or the region a pocketing operation clears. `isolation` exports a band of `--width` millimeters outside the copper and inside the board. Copper the Gerber file already joins stays joined. There is no netlist.

## Clearance and isolation width

`--clearance` expands the copper that negative mode protects. The painted or milled area gets smaller. It is not an electrical clearance, and it can reduce the gap between tracks.

`--width` is the width of the geometric removal band. It is not the cutter diameter. MillMage applies cutter compensation.

## Precision and coordinates

Geometry is calculated in millimeters. `--curve-tolerance` is the only intentional curve approximation. Boolean repairs that change the area by more than 0.001 mm² are errors. Smaller repairs are warnings.

Gerber Y points up. SVG Y points down. The exporter applies that flip for both origin modes. `--mirror-y` is a separate flip about the Gerber origin and happens before the SVG flip.

`--origin board-min` moves the minimum corner of the export bounds to the SVG origin. `--origin preserve` keeps Gerber X and writes Gerber Y as negative SVG Y. `width` and `height` are the physical size of those bounds in both modes. When a board exists, the bounds include the board, so a negative or isolation file stays board-sized.

With no outline, the board is the copper bounding box expanded by `--margin`. That rectangle is an approximation, not the manufactured PCB edge.

## Limitations

- One copper file and one optional outline per run.
- No Excellon drills, ZIP jobs, or multi-layer boards.
- `%IPNEG*%` is rejected.
- Isolation does not discover nets, so it cannot separate copper that the Gerber already connects.
- A missing isolation skin larger than 0.0001 mm² produces a warning.
