"""Convert Gerber copper artwork into SVG geometry."""

from shapely.geometry import box

from gerber2svg.exceptions import OutlineError
from gerber2svg.geometry import mirror_geometry
from gerber2svg.gerber import load_copper, load_outline
from gerber2svg.models import ConversionConfig, ConversionResult, validate_config
from gerber2svg.operations import run_mode
from gerber2svg.svg import geometry_to_svg

__version__ = "0.1.0"


def convert(config: ConversionConfig) -> ConversionResult:
    validate_config(config)
    copper, warnings, primitive_count = load_copper(config.copper, config.curve_tolerance_mm)
    if config.outline is not None:
        board, outline_warnings = load_outline(config.outline, config.curve_tolerance_mm)
        warnings.extend(outline_warnings)
    elif copper.is_empty:
        raise OutlineError("cannot build a board rectangle from empty copper")
    else:
        minx, miny, maxx, maxy = copper.bounds
        margin = config.margin_mm
        board = box(minx - margin, miny - margin, maxx + margin, maxy + margin)
    if copper.is_empty:
        warnings.append("copper geometry is empty")
    copper = mirror_geometry(copper, config.mirror_x, config.mirror_y)
    board = mirror_geometry(board, config.mirror_x, config.mirror_y)
    geometry, mode_warnings = run_mode(copper, board, config)
    warnings.extend(mode_warnings)
    svg, svg_warnings = geometry_to_svg(
        geometry,
        board,
        origin=config.origin,
        strategy=config.svg_strategy,
    )
    warnings.extend(svg_warnings)
    return ConversionResult(
        copper=copper,
        board=board,
        geometry=geometry,
        svg=svg,
        warnings=warnings,
        primitive_count=primitive_count,
    )
