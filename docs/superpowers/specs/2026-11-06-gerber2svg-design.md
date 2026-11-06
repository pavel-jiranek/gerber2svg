# gerber2svg design

Date: 2026-11-06

## Decisions

- Build the Python package and CLI `gerber2svg` described in `docs/specs.md`.
- Parse Gerber with Gerbonara. Polygonize each primitive and composite dark and clear polarity in file order. Do not union every dark shape and subtract every clear shape at the end.
- Acceptance for this version is automated geometry, Gerber, SVG, and CLI tests on synthetic files. LightBurn and MillMage workflows are documented and not claimed as verified.
- No real customer board is available. Fixtures are hand-written RS-274X files. A real board can be added later as a regression fixture.
- Drills, batch conversion, ZIP input, multi-layer boards, preview images, and the other phase 6 items in section 14 of the product spec are out of this version.
- SVG is written with the standard-library XML library. `svgwrite` is not a dependency.

## Result

`convert(config)` reads one copper Gerber file and an optional outline file, builds copper geometry `C` and board geometry `B` in millimeters, and returns one of:

| Mode | Result |
|---|---|
| `copper` | `C`, including copper that extends outside `B` |
| `negative` | `B.difference(protected)`, where `protected` is `C` expanded by clearance |
| `isolation` | A band of the requested width around `C`, clipped to `B` |

The SVG describes those regions as closed filled paths. LightBurn and MillMage still own scan lines, toolpaths, feeds, and cutter compensation.

## Package

```text
src/gerber2svg/
├── __init__.py          # convert()
├── cli.py
├── models.py
├── gerber.py
├── geometry.py
├── operations.py
├── svg.py
└── exceptions.py
tests/
├── test_gerber.py
├── test_geometry.py
├── test_operations.py
├── test_svg.py
├── test_cli.py
└── fixtures/
```

Python 3.11 or newer. Runtime dependencies: Gerbonara, Shapely, Typer. Tests use pytest. Type annotations throughout.

`operations.py` does not import the SVG writer. `svg.py` does not import the Gerber parser. `cli.py` only parses arguments, calls `convert`, prints diagnostics, and writes the output file.

## Public API

```python
class Mode(enum.Enum):
    COPPER = "copper"
    NEGATIVE = "negative"
    ISOLATION = "isolation"

class Origin(enum.Enum):
    PRESERVE = "preserve"
    BOARD_MIN = "board-min"

class SvgStrategy(enum.Enum):
    COMPOUND = "compound"
    CONTOURS = "contours"

@dataclass
class ConversionConfig:
    copper: Path
    outline: Path | None = None
    mode: Mode = Mode.NEGATIVE
    clearance_mm: float = 0.0
    width_mm: float | None = None
    curve_tolerance_mm: float = 0.005
    svg_strategy: SvgStrategy = SvgStrategy.COMPOUND
    margin_mm: float = 0.0
    origin: Origin = Origin.BOARD_MIN
    mirror_x: bool = False
    mirror_y: bool = False

@dataclass
class ConversionResult:
    copper: BaseGeometry
    board: BaseGeometry
    geometry: BaseGeometry
    svg: str
    warnings: list[str]
    primitive_count: int

def convert(config: ConversionConfig) -> ConversionResult: ...
```

`geometry` is the mode output in Gerber millimeters, Y upward, after mirroring and before the SVG Y-axis mapping. `warnings` is also printed by the CLI. `primitive_count` is the number of graphic primitives rendered from the copper file. `--verbose` prints that count and the copper, board, and output areas. Warnings are printed even without `--verbose`.

The CLI requires `--copper`, `--output`, and `--mode`. The library default of `Mode.NEGATIVE` applies only when a caller constructs `ConversionConfig` without setting it. `convert()` runs the same configuration checks as the CLI and raises `ConfigError` before reading files.

## Pipeline

1. Open the copper file with `GerberFile.open` and render primitives in millimeters.
2. Polygonize each primitive. Keep `polarity_dark` from that primitive.
3. Composite in file order to produce `C`.
4. Build `B` from the outline file, or from the copper bounds plus margin.
5. Apply `--mirror-x` and `--mirror-y` in millimeter space, Y upward.
6. Run the selected mode.
7. Map coordinates into the SVG document and write the file.

## Gerber copper

Gerbonara resolves apertures, macros, units, transforms, and step-and-repeat into graphic primitives. This version polygonizes `Circle`, `Rectangle`, `Line`, `Arc`, and `ArcPoly`.

Some Gerbonara 1.6.x builds reset `polarity_dark` to true inside `to_arc_poly`, and some builds have a broken `approximate_arcs`. The project pins a Gerbonara release in `pyproject.toml` only after a unit test shows that those five primitive types keep `polarity_dark` through `to_arc_poly`. Polarity is still read from the source primitive. If `approximate_arcs` on that release fails a chord-error check, arc flattening is implemented from the arc center, radius, and endpoints, and the README records that workaround.

A circular arc of radius `R` and angle `θ` uses the smallest segment count whose sagitta is at most `curve_tolerance_mm`:

```text
sagitta = R * (1 - cos(θ / (2 * n)))
```

A full circle uses at least 4 segments. A zero-length draw with a positive aperture width becomes a circle of that diameter. A primitive that still has area is composited. A primitive that polygonizes to zero area is omitted and produces a warning that names its type and position. Any other primitive type raises `UnsupportedGerberError` and names the type.

A standard aperture hole (`hole_dia`) must survive as an interior ring or as a clear primitive. A fixture covers a circular aperture with a hole. If the pinned Gerbonara release emits that aperture as a solid disk, holed apertures raise `UnsupportedGerberError` instead of filling the hole.

If the file sets negative image polarity (`%IPNEG*%`) and the rendered primitives are not already inverted, raise `UnsupportedGerberError`. X2 attributes that carry no geometry are ignored. A Gerbonara parse failure, an unreadable file, or a file that is not Gerber becomes `GerberError`.

## Polarity compositing

Start from an empty image. Group consecutive primitives that share a polarity. `union_all` each group once.

- A dark group is unioned into the image.
- A clear group is subtracted from the image.
- A clear group applied to an empty image leaves the image empty and adds a warning.

This is the whole copper image `C`. A single union of every dark primitive is not the copper image.

After each boolean operation, invalid Shapely geometry is passed through `make_valid`. Each repair appends a warning with the area before and after. If the absolute area change is greater than `0.001 mm²`, raise `GeometryError`. Features are not discarded for being small. Coordinates are not rounded between operations. There is no multiprocessing and no spatial index in this version. Consecutive same-polarity primitives are the batching strategy.

## Board outline

Outline geometry uses centerlines, not the stroked aperture width. `Line` and `Arc` objects contribute their endpoints and arc centers. `Region` objects contribute their contours. Arcs on the outline use the same chord error as copper.

Endpoints join when they are within `0.01 mm`. A larger gap raises `OutlineError` and includes the gap distance. A ring contained in another ring is a cutout. Disjoint outer rings become a `MultiPolygon`. The result must be a valid polygonal board with positive area. An open contour raises `OutlineError`.

When no outline file is given, `B` is the axis-aligned bounds of `C` expanded by `--margin` on every side. The default margin is `0`. The README describes this rectangle as an approximation of the PCB, not a reconstruction of the manufactured outline. Margin must be zero or positive. Passing a nonzero `--margin` together with an outline file raises `ConfigError`. If the copper geometry is empty and no outline file is given, raise `OutlineError`, because the approximate board is undefined. Empty copper with a valid outline produces a warning and continues.

## Modes

Mirroring is applied to `C` and `B` before the mode runs.

**Copper.** Output is `C`. It is not clipped to `B`.

**Negative.** Clearance must be zero or positive. A nonzero clearance is valid only in this mode. Clearance `0` does not buffer. A positive clearance replaces `C` with `C.buffer(clearance_mm)` before the difference. Output is `B.difference(protected)`. Buffer quadrant segments use the same sagitta limit as curve flattening, with a minimum of 8 segments per quarter circle. Join and cap style are round.

**Isolation.** `--width` is required and must be greater than zero. Passing `--width` in copper or negative mode raises `ConfigError`. Output is:

```text
expanded = C.buffer(width_mm)
isolation = expanded.difference(C).intersection(B)
```

The same buffer segment rule and round joins apply. Coverage check: build a skin just outside `C` and inside `B` by buffering `C` by `min(curve_tolerance_mm, width_mm / 2)`, subtracting `C`, and intersecting with `B`. Any part of that skin that lies outside the isolation band by more than `0.0001 mm²` adds a warning. The area floor ignores chord-error slivers on a correct band. The check looks outward from the copper, so the interior of `C` is not required to be inside the band. Copper that the Gerber file already connects stays connected. There is no netlist in this version.

With a valid outline and empty copper, negative mode yields `B` and isolation mode yields an empty result. The CLI still exits 0 when the only problems are warnings.

## SVG

`svg.py` builds the document with `xml.etree.ElementTree`.

Let the export bounds be the axis-aligned bounds of the union of the mode geometry and `B`. Negative and isolation graphics stay board-sized when the removal region does not touch every edge. Copper mode includes the board, and also grows the document if `C` extends past `B`. If both the geometry and the board are empty, write a `0mm` by `0mm` document and add a warning. If the geometry is empty and `B` exists, the document size follows `B`.

`W` and `H` are those bounds’ width and height. `width` and `height` are `{W}mm` and `{H}mm`.

**`--origin board-min`** (default). Gerber point `(x, y)` maps to SVG `(x - minx, maxy - y)`. The view box is `0 0 W H`.

**`--origin preserve`.** Gerber point `(x, y)` maps to SVG `(x, -y)`. The view box is `{minx} {-maxy} {W} {H}`. Physical `width` and `height` stay `W` and `H` millimeters, so a board far from the Gerber origin keeps its real size.

Path data uses absolute `M`, `L`, and `Z` only. Coordinates are printed to 6 decimal places, never in scientific notation. Every ring is closed. Fill is black. There is no stroke, style sheet, text, image, mask, or clip path. A fill-color flag is deferred.

**`compound`** (default). One `<path>` for the whole result. Every exterior and every hole is a subpath. `fill-rule="evenodd"`.

**`contours`.** One `<path>` per ring, each ring once. For each polygon, the exterior path comes first and its holes follow. `fill-rule="evenodd"` on each path. Tests check ring geometry and this order. Application behavior for nested contours is unverified.

## Errors and exit codes

| Exception | Exit | When |
|---|---|---|
| `ConfigError` | 2 | Incompatible flags, negative clearance, bad width, negative margin, non-positive curve tolerance |
| `GerberError` | 3 | Unreadable or invalid copper file |
| `UnsupportedGerberError` | 3 | Primitive or polarity this version refuses |
| `OutlineError` | 3 | Open, empty, or unjoinable outline |
| `GeometryError` | 4 | A repair changes area by more than `0.001 mm²`, or another boolean failure |
| `SvgExportError` | 5 | The document cannot be built or written |

`UnsupportedGerberError` is a subclass of `GerberError`. Typer’s own usage errors also exit 2. Success, including a run that only produced warnings, exits 0. The CLI provides `--help` and `--version`. `--version` reads the package version.

Curve tolerance must be greater than zero.

## Testing

Comparisons use symmetric-difference area. Exact Shapely cases allow at most `1e-6 mm²`. Arc fixtures whose ideal area is known analytically allow at most `curve_tolerance_mm` times the ideal perimeter, in square millimeters.

**Geometry and modes**, with no Gerber files: round pad, rectangular pad, round-ended track, connected pad and track, separate islands, pour with a hole, narrow gap, nested rings, board with a cutout. Checks cover union, negative, isolation, holes, clipping, multipolygons, and buffer distance. One fixture draws copper, clears it, then draws copper again, and expects the later copper to remain. Clearance shrinks the negative region. Isolation width is checked on a shape with a known band area. Mirror and origin changes keep the area and change the placement as specified.

**Gerber fixtures** under `tests/fixtures/`: millimeter and inch files, circle and rectangle flashes, a straight track drawn with a 0.5 mm round aperture, an arc, a filled region, dark-then-clear, clear-then-dark, one aperture macro, and one step-and-repeat. Outline fixtures: a rectangle, a rounded corner, an interior cutout, and an open contour that must fail. One copper file is a circular flash with an aperture hole. One copper file sets `%IPNEG*%` and must fail. Expected areas are computed from the dimensions written in each fixture.

**SVG:** the document is well-formed XML with the expected `width`, `height`, and `viewBox`. Paths are closed, holes are present, and `fill-rule` is `evenodd`. A test parser reads path data back into rings and compares the area. Cases cover mirroring, both origins, and a multipolygon. The document contains no image and no style sheet.

**CLI:** Typer’s test runner covers all three modes, missing `--width`, `--width` outside isolation, nonzero `--clearance` outside negative mode, `--help`, `--version`, and the exit codes above.

**End to end:** one fixture with a pad, a track, a pour with a hole, and a closed outline. The test checks board size, copper area, a hole in the negative geometry, and an isolation band. SVG examples rendered from that fixture are stored in the repository.

## Documentation

The README covers the twelve topics in section 13 of `docs/specs.md`: purpose, supported Gerber, installation, CLI, an example of each mode, the LightBurn workflow, the MillMage workflow, copper versus removal geometry, clearance versus isolation width, precision and coordinates, limitations, and troubleshooting.

It states plainly:

- Application import is not yet verified.
- The automatic board rectangle is an approximation.
- Clearance expands protected copper and reduces the painted or milled area. It is not an electrical clearance.
- Isolation width is a geometric band, not a cutter diameter, and it does not split copper the Gerber file already joined.
- The SVG Y axis points down. `--mirror-y` is a separate transform applied before that mapping.
- Known Gerbonara workarounds, including any arc-flattening replacement, are listed.

## Implementation order

Follow the product spec’s phases, with phase 5 limited to documentation:

1. SVG export and negative geometry on synthetic Shapely shapes.
2. Gerber loading, polygonization, and ordered polarity compositing, with fixture tests.
3. Copper, negative, and isolation modes, including clearance, width, and the isolation-coverage warning.
4. The Typer CLI, validation, exit codes, and CLI tests.
5. README workflows and example SVGs. No manual LightBurn or MillMage pass in this version.
