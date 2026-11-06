import xml.etree.ElementTree as ET

import pytest
from shapely.geometry import Polygon, box

from gerber2svg.models import Origin, SvgStrategy
from gerber2svg.svg import geometry_to_svg


SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


def _path_text(svg: str) -> str:
    root = ET.fromstring(svg)
    paths = root.findall("svg:path", SVG_NS)
    assert len(paths) == 1
    return paths[0].attrib["d"]


def test_compound_square_has_physical_size_and_a_closed_path():
    square = box(0, 0, 50, 30)
    svg, warnings = geometry_to_svg(
        square, square, origin=Origin.BOARD_MIN, strategy=SvgStrategy.COMPOUND
    )
    assert warnings == []
    root = ET.fromstring(svg)
    assert root.attrib["width"] == "50.000000mm"
    assert root.attrib["height"] == "30.000000mm"
    assert root.attrib["viewBox"] == "0.000000 0.000000 50.000000 30.000000"
    path = root.find("svg:path", SVG_NS)
    assert path is not None
    assert path.attrib["fill"] == "black"
    assert path.attrib["fill-rule"] == "evenodd"
    assert "stroke" not in path.attrib
    assert path.attrib["d"].strip().endswith("Z")
    assert "<image" not in svg
    assert "<style" not in svg


def test_compound_hole_is_a_second_subpath():
    outer = box(0, 0, 10, 10)
    hole = box(2, 2, 4, 4)
    shape = outer.difference(hole)
    svg, _warnings = geometry_to_svg(
        shape, outer, origin=Origin.BOARD_MIN, strategy=SvgStrategy.COMPOUND
    )
    data = _path_text(svg)
    assert data.count("M ") == 2
    assert data.count("Z") == 2


def test_empty_geometry_keeps_the_board_size():
    svg, warnings = geometry_to_svg(
        Polygon(), box(0, 0, 8, 3), origin=Origin.BOARD_MIN, strategy=SvgStrategy.COMPOUND
    )
    root = ET.fromstring(svg)
    assert root.attrib["width"] == "8.000000mm"
    assert root.attrib["height"] == "3.000000mm"
    assert root.find("svg:path", SVG_NS) is None
    assert warnings == []


def _rings_from_path(data: str) -> list[list[tuple[float, float]]]:
    tokens = data.replace(",", " ").split()
    rings: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    index = 0
    while index < len(tokens):
        command = tokens[index]
        if command == "M":
            current = [(float(tokens[index + 1]), float(tokens[index + 2]))]
            index += 3
        elif command == "L":
            current.append((float(tokens[index + 1]), float(tokens[index + 2])))
            index += 3
        elif command == "Z":
            rings.append(current)
            current = []
            index += 1
        else:
            raise AssertionError(command)
    return rings


def test_contours_emit_exterior_then_hole_as_separate_paths():
    outer = box(0, 0, 10, 10)
    shape = outer.difference(box(2, 2, 4, 4))
    svg, _warnings = geometry_to_svg(
        shape, outer, origin=Origin.BOARD_MIN, strategy=SvgStrategy.CONTOURS
    )
    root = ET.fromstring(svg)
    paths = root.findall("svg:path", SVG_NS)
    assert len(paths) == 2
    outer_ring = _rings_from_path(paths[0].attrib["d"])[0]
    hole_ring = _rings_from_path(paths[1].attrib["d"])[0]
    assert max(x for x, _y in outer_ring) == pytest.approx(10)
    assert max(x for x, _y in hole_ring) == pytest.approx(4)


def test_preserve_origin_keeps_gerber_x_and_negates_y():
    square = box(5, 7, 8, 9)
    svg, _warnings = geometry_to_svg(
        square, square, origin=Origin.PRESERVE, strategy=SvgStrategy.COMPOUND
    )
    root = ET.fromstring(svg)
    assert root.attrib["width"] == "3.000000mm"
    assert root.attrib["height"] == "2.000000mm"
    assert root.attrib["viewBox"] == "5.000000 -9.000000 3.000000 2.000000"
    data = _path_text(svg)
    assert "M 5.000000 -7.000000" in data or "M 5.000000 -9.000000" in data


def test_board_min_places_offset_square_at_the_svg_origin():
    square = box(5, 7, 8, 9)
    svg, _warnings = geometry_to_svg(
        square, square, origin=Origin.BOARD_MIN, strategy=SvgStrategy.COMPOUND
    )
    root = ET.fromstring(svg)
    assert root.attrib["viewBox"] == "0.000000 0.000000 3.000000 2.000000"
    data = _path_text(svg)
    assert "M 0.000000 " in data
