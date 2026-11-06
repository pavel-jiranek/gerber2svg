import math

import pytest
from shapely.geometry import Polygon, box

from gerber2svg.exceptions import GeometryError
from gerber2svg.geometry import (
    buffer_mm,
    buffer_resolution,
    difference_geometries,
    mirror_geometry,
    repair,
    union_geometries,
)


def test_union_of_two_squares():
    left = Polygon([(0, 0), (2, 0), (2, 1), (0, 1)])
    right = Polygon([(1, 0), (3, 0), (3, 1), (1, 1)])
    merged, warnings = union_geometries([left, right])
    assert warnings == []
    assert abs(merged.area - 3.0) <= 1e-6


def test_difference_cuts_a_hole():
    outer = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
    hole = Polygon([(1, 1), (2, 1), (2, 2), (1, 2)])
    result, warnings = difference_geometries(outer, hole)
    assert warnings == []
    assert abs(result.area - 15.0) <= 1e-6
    assert len(result.interiors) == 1


def test_repair_bowtie_is_valid_or_rejected():
    bowtie = Polygon([(0, 0), (1, 1), (0, 1), (1, 0)])
    assert not bowtie.is_valid
    try:
        fixed, warnings = repair(bowtie)
    except GeometryError as exc:
        assert "area" in str(exc)
        return
    assert fixed.is_valid
    assert warnings
    assert "repaired invalid geometry" in warnings[0]


def test_buffer_resolution_respects_sagitta():
    resolution = buffer_resolution(1.0, 0.005)
    assert resolution >= 8
    segment = math.pi / (2 * resolution)
    sagitta = 1.0 * (1 - math.cos(segment / 2))
    assert sagitta <= 0.005


def test_buffer_of_a_square_uses_round_corners():
    import math as math_mod

    square = box(0, 0, 10, 4)
    buffered, warnings = buffer_mm(square, 0.3, 0.005)
    assert warnings == []
    expected = 40.0 + 28.0 * 0.3 + math_mod.pi * 0.3 * 0.3
    assert abs(buffered.area - expected) <= 0.005 * (28.0 + 2 * math_mod.pi * 0.3)


def test_mirror_x_flips_about_the_origin():
    square = box(1, 2, 3, 4)
    flipped = mirror_geometry(square, True, False)
    minx, miny, maxx, maxy = flipped.bounds
    assert abs(minx - -3) <= 1e-6
    assert abs(maxx - -1) <= 1e-6
    assert abs(miny - 2) <= 1e-6
    assert abs(maxy - 4) <= 1e-6
    assert abs(flipped.area - square.area) <= 1e-6
