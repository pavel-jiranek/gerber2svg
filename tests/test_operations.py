import math
from pathlib import Path

import pytest
from shapely.geometry import Point, box

from gerber2svg.models import ConversionConfig, Mode
from gerber2svg.operations import run_mode


def _config(**kwargs) -> ConversionConfig:
    values = {"copper": Path("copper.gbr"), "mode": Mode.COPPER}
    values.update(kwargs)
    return ConversionConfig(**values)


def test_copper_mode_keeps_geometry_outside_the_board():
    copper = box(0, 0, 12, 4)
    board = box(0, 0, 10, 4)
    result, warnings = run_mode(copper, board, _config(mode=Mode.COPPER))
    assert warnings == []
    assert abs(result.area - 48.0) <= 1e-6


def test_negative_mode_subtracts_copper_from_the_board():
    board = box(0, 0, 10, 10)
    copper = Point(5, 5).buffer(1.0, quad_segs=64)
    result, warnings = run_mode(copper, board, _config(mode=Mode.NEGATIVE))
    assert warnings == []
    assert abs(result.area - (100.0 - math.pi)) <= 1e-3
    assert len(list(result.interiors)) == 1


def test_clearance_shrinks_the_negative_region():
    board = box(0, 0, 10, 10)
    copper = Point(5, 5).buffer(1.0, quad_segs=64)
    result, _warnings = run_mode(
        copper, board, _config(mode=Mode.NEGATIVE, clearance_mm=0.5)
    )
    expected = 100.0 - math.pi * (1.5 ** 2)
    perimeter = 2 * math.pi * 1.5
    assert abs(result.area - expected) <= 0.005 * perimeter


from shapely.geometry import Polygon

from gerber2svg.operations import isolation_coverage_warnings


def test_isolation_band_area_of_a_rectangle():
    copper = box(0, 0, 10, 4)
    board = box(-5, -5, 20, 15)
    result, warnings = run_mode(
        copper,
        board,
        _config(mode=Mode.ISOLATION, width_mm=0.3),
    )
    expected = 28.0 * 0.3 + math.pi * 0.3 * 0.3
    allowance = 0.005 * (28.0 + 2 * math.pi * 0.3)
    assert abs(result.area - expected) <= allowance
    assert not any("does not fully surround" in warning for warning in warnings)


def test_empty_isolation_warns_that_the_band_is_missing():
    copper = box(0, 0, 2, 2)
    board = box(-1, -1, 4, 4)
    warnings = isolation_coverage_warnings(
        copper,
        board,
        Polygon(),
        curve_tolerance_mm=0.005,
        width_mm=0.3,
    )
    assert warnings == ["isolation band does not fully surround copper inside the board"]


from gerber2svg import convert
from gerber2svg.exceptions import OutlineError
from gerber2svg.models import Origin, SvgStrategy


def test_convert_negative_without_outline_uses_the_copper_bounds(tmp_path: Path):
    copper_path = tmp_path / "copper.gbr"
    copper_path.write_text(
        "%FSLAX36Y36*%\n%MOMM*%\n%ADD10C,1.000*%\nD10*\nX0Y0D03*\nM02*\n",
        encoding="utf-8",
    )
    result = convert(
        ConversionConfig(
            copper=copper_path,
            mode=Mode.NEGATIVE,
            origin=Origin.BOARD_MIN,
            svg_strategy=SvgStrategy.COMPOUND,
        )
    )
    assert "mm" in result.svg
    assert result.primitive_count >= 1
    assert result.geometry.area < result.board.area
    assert not result.geometry.is_empty


def test_convert_refuses_empty_copper_without_an_outline(tmp_path: Path):
    copper_path = tmp_path / "empty.gbr"
    copper_path.write_text("%FSLAX36Y36*%\n%MOMM*%\nM02*\n", encoding="utf-8")
    with pytest.raises(OutlineError, match="empty copper"):
        convert(ConversionConfig(copper=copper_path, mode=Mode.COPPER))


def test_convert_mirrors_about_the_gerber_origin(tmp_path: Path):
    copper_path = tmp_path / "copper.gbr"
    copper_path.write_text(
        "%FSLAX36Y36*%\n%MOMM*%\n%ADD10C,1.000*%\nD10*\nX5000000Y0D03*\nM02*\n",
        encoding="utf-8",
    )
    result = convert(ConversionConfig(copper=copper_path, mode=Mode.COPPER, mirror_x=True))
    minx, _miny, maxx, _maxy = result.copper.bounds
    assert abs(minx - -5.5) <= 0.02
    assert abs(maxx - -4.5) <= 0.02
    assert abs(result.copper.area - math.pi * 0.5 ** 2) <= 0.005 * (2 * math.pi * 0.5)
