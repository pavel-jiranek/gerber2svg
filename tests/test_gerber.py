import math

import pytest
from gerbonara.graphic_primitives import Arc, Circle, Line, Rectangle
from shapely.geometry import box

from gerber2svg.exceptions import UnsupportedGerberError
from gerber2svg.gerber import Painted, composite_painted, primitive_to_polygon


class UnknownPrimitive:
    polarity_dark = True


def test_gerbonara_keeps_clear_polarity_on_arc_poly():
    circle = Circle(0, 0, 1, polarity_dark=False)
    assert circle.to_arc_poly().polarity_dark is False


def test_circle_area_stays_within_chord_error():
    polygon = primitive_to_polygon(Circle(0, 0, 1, polarity_dark=True), 0.005)
    assert polygon is not None
    perimeter = 2 * math.pi
    assert abs(polygon.area - math.pi) <= 0.005 * perimeter


def test_zero_length_line_becomes_a_circle():
    polygon = primitive_to_polygon(Line(0, 0, 0, 0, 0.5, polarity_dark=True), 0.005)
    assert polygon is not None
    expected = math.pi * (0.25 ** 2)
    assert abs(polygon.area - expected) <= 0.005 * (2 * math.pi * 0.25)


def test_rectangle_area_is_exact():
    polygon = primitive_to_polygon(Rectangle(0, 0, 2, 1, 0, polarity_dark=True), 0.005)
    assert polygon is not None
    assert abs(polygon.area - 2.0) <= 1e-6


def test_arc_stroke_area_matches_length_times_width_plus_caps():
    arc = Arc(10, 0, 0, 10, 0, 0, False, 0.2, polarity_dark=True)
    polygon = primitive_to_polygon(arc, 0.005)
    assert polygon is not None
    arc_length = math.pi / 2 * 10
    expected = arc_length * 0.2 + math.pi * (0.1 ** 2)
    allowance = 0.005 * (arc_length + 2 * math.pi * 0.1)
    assert abs(polygon.area - expected) <= allowance


def test_unknown_primitive_is_rejected():
    with pytest.raises(UnsupportedGerberError, match="UnknownPrimitive"):
        primitive_to_polygon(UnknownPrimitive(), 0.005)


def test_zero_radius_circle_is_omitted():
    assert primitive_to_polygon(Circle(0, 0, 0, polarity_dark=True), 0.005) is None


def test_clear_then_dark_keeps_the_later_copper():
    dark = Painted(box(0, 0, 4, 2), True)
    clear = Painted(box(0, 0, 4, 2), False)
    later = Painted(box(1, 0.5, 2, 1.5), True)
    result, warnings = composite_painted([dark, clear, later])
    assert abs(result.area - 1.0) <= 1e-6
    assert warnings == []


def test_clear_on_empty_warns():
    result, warnings = composite_painted([Painted(box(0, 0, 1, 1), False)])
    assert result.is_empty
    assert warnings == ["clear polarity applied to empty copper"]


from pathlib import Path

from gerber2svg.exceptions import GerberError, UnsupportedGerberError
from gerber2svg.gerber import load_copper

FIXTURES = Path(__file__).parent / "fixtures"


def _area(name: str) -> float:
    geometry, _warnings, _count = load_copper(FIXTURES / name, 0.005)
    return float(geometry.area)


def test_flash_circle_mm():
    expected = math.pi * 0.5 ** 2
    assert abs(_area("flash_circle_mm.gbr") - expected) <= 0.005 * (2 * math.pi * 0.5)


def test_flash_rect_mm():
    assert abs(_area("flash_rect_mm.gbr") - 2.0) <= 1e-6


def test_round_track_area():
    expected = 10.0 * 0.5 + math.pi * (0.25 ** 2)
    allowance = 0.005 * (10.0 + 2 * math.pi * 0.25)
    assert abs(_area("track_0_5mm.gbr") - expected) <= allowance


def test_arc_file_area():
    arc_length = math.pi / 2 * 10
    expected = arc_length * 0.2 + math.pi * (0.1 ** 2)
    allowance = 0.005 * (arc_length + 2 * math.pi * 0.1)
    assert abs(_area("arc_mm.gbr") - expected) <= allowance


def test_region_area():
    assert abs(_area("region_mm.gbr") - 50.0) <= 1e-6


def test_inch_flash_is_converted_to_millimeters():
    radius_mm = 0.05 * 25.4
    expected = math.pi * radius_mm ** 2
    assert abs(_area("flash_circle_inch.gbr") - expected) <= 0.005 * (2 * math.pi * radius_mm)


def test_dark_then_clear_punches_a_hole():
    assert abs(_area("dark_then_clear.gbr") - 48.0) <= 1e-4


def test_clear_then_dark_keeps_only_the_later_rectangle():
    geometry, warnings, _count = load_copper(FIXTURES / "clear_then_dark.gbr", 0.005)
    assert abs(geometry.area - 2.0) <= 1e-4
    assert any("clear polarity applied to empty copper" in warning for warning in warnings)


def test_aperture_hole_is_an_annulus():
    expected = math.pi * (0.5 ** 2 - 0.2 ** 2)
    assert abs(_area("aperture_hole.gbr") - expected) <= 0.005 * (2 * math.pi * 0.5)


def test_aperture_macro_circle():
    expected = math.pi * 0.5 ** 2
    assert abs(_area("aperture_macro.gbr") - expected) <= 0.005 * (2 * math.pi * 0.5)


def test_step_repeat_makes_two_circles():
    expected = 2 * math.pi * 0.5 ** 2
    assert abs(_area("step_repeat.gbr") - expected) <= 0.005 * (2 * 2 * math.pi * 0.5)


def test_ipneg_is_rejected():
    with pytest.raises(UnsupportedGerberError, match="IPNEG"):
        load_copper(FIXTURES / "ipneg.gbr", 0.005)


def test_missing_file_is_a_gerber_error(tmp_path: Path):
    with pytest.raises(GerberError, match="not found"):
        load_copper(tmp_path / "missing.gbr", 0.005)


from gerber2svg.exceptions import OutlineError
from gerber2svg.gerber import load_outline


def test_outline_rectangle_uses_centerlines():
    board, warnings = load_outline(FIXTURES / "outline_rect.gbr", 0.005)
    assert warnings == []
    assert abs(board.area - 200.0) <= 1e-4


def test_outline_rounded_corner():
    board, _warnings = load_outline(FIXTURES / "outline_rounded.gbr", 0.005)
    expected = 100.0 - (4.0 - math.pi)
    assert abs(board.area - expected) <= 0.005 * (40.0 + 2 * math.pi)


def test_outline_cutout_is_a_hole():
    board, _warnings = load_outline(FIXTURES / "outline_cutout.gbr", 0.005)
    assert abs(board.area - 192.0) <= 1e-3
    polygons = list(board.geoms) if board.geom_type == "MultiPolygon" else [board]
    assert sum(len(polygon.interiors) for polygon in polygons) == 1


def test_open_outline_reports_the_gap():
    with pytest.raises(OutlineError, match=r"10\.0"):
        load_outline(FIXTURES / "outline_open.gbr", 0.005)


def test_closed_region_outline_has_rectangle_area():
    board, _warnings = load_outline(FIXTURES / "outline_region.gbr", 0.005)
    assert abs(board.area - 200.0) <= 1e-6


def _assert_bowtie_repair_warning(warnings: list[str]) -> None:
    assert any(
        "repaired invalid geometry" in warning and "0.000200" in warning
        for warning in warnings
    )


def test_bowtie_region_outline_keeps_repair_warning():
    board, warnings = load_outline(FIXTURES / "bowtie_region.gbr", 0.005)
    assert board.area > 0
    _assert_bowtie_repair_warning(warnings)


def test_bowtie_region_copper_keeps_repair_warning():
    copper, warnings, _count = load_copper(FIXTURES / "bowtie_region.gbr", 0.005)
    assert copper.area > 0
    _assert_bowtie_repair_warning(warnings)
