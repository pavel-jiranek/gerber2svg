from shapely.geometry.base import BaseGeometry

from gerber2svg.geometry import buffer_mm, difference_geometries, intersection_geometries
from gerber2svg.models import ConversionConfig, Mode

COVERAGE_AREA_MM2 = 0.0001


def isolation_coverage_warnings(
    copper: BaseGeometry,
    board: BaseGeometry,
    isolation: BaseGeometry,
    *,
    curve_tolerance_mm: float,
    width_mm: float,
) -> list[str]:
    if copper.is_empty or width_mm <= 0:
        return []
    warnings: list[str] = []
    skin_distance = min(curve_tolerance_mm, width_mm / 2)
    skin, buffer_warnings = buffer_mm(copper, skin_distance, curve_tolerance_mm)
    warnings.extend(buffer_warnings)
    skin, difference_warnings = difference_geometries(skin, copper)
    warnings.extend(difference_warnings)
    skin, intersection_warnings = intersection_geometries(skin, board)
    warnings.extend(intersection_warnings)
    outside, outside_warnings = difference_geometries(skin, isolation)
    warnings.extend(outside_warnings)
    if outside.area > COVERAGE_AREA_MM2:
        warnings.append("isolation band does not fully surround copper inside the board")
    return warnings


def run_mode(
    copper: BaseGeometry, board: BaseGeometry, config: ConversionConfig
) -> tuple[BaseGeometry, list[str]]:
    warnings: list[str] = []
    if config.mode is Mode.COPPER:
        return copper, warnings
    if config.mode is Mode.NEGATIVE:
        protected = copper
        if config.clearance_mm > 0:
            protected, buffer_warnings = buffer_mm(
                copper, config.clearance_mm, config.curve_tolerance_mm
            )
            warnings.extend(buffer_warnings)
        result, difference_warnings = difference_geometries(board, protected)
        warnings.extend(difference_warnings)
        return result, warnings

    assert config.width_mm is not None
    expanded, buffer_warnings = buffer_mm(copper, config.width_mm, config.curve_tolerance_mm)
    warnings.extend(buffer_warnings)
    band, difference_warnings = difference_geometries(expanded, copper)
    warnings.extend(difference_warnings)
    result, clip_warnings = intersection_geometries(band, board)
    warnings.extend(clip_warnings)
    warnings.extend(
        isolation_coverage_warnings(
            copper,
            board,
            result,
            curve_tolerance_mm=config.curve_tolerance_mm,
            width_mm=config.width_mm,
        )
    )
    return result, warnings
