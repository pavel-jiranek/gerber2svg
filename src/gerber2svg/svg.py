import xml.etree.ElementTree as ET

from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from gerber2svg.models import Origin, SvgStrategy

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def export_bounds(geometry: BaseGeometry, board: BaseGeometry) -> tuple[float, float, float, float]:
    parts = [geom for geom in (geometry, board) if geom is not None and not geom.is_empty]
    if not parts:
        return (0.0, 0.0, 0.0, 0.0)
    merged = parts[0] if len(parts) == 1 else unary_union(parts)
    minx, miny, maxx, maxy = merged.bounds
    return (float(minx), float(miny), float(maxx), float(maxy))


def _polygons(geom: BaseGeometry) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return [part for part in geom.geoms if isinstance(part, Polygon) and not part.is_empty]
    return []


def _format_pair(x: float, y: float) -> str:
    return f"{x:.6f} {y:.6f}"


def _ring_path(ring, transform) -> str:
    coords = list(ring.coords)
    if len(coords) >= 2 and coords[0] == coords[-1]:
        coords = coords[:-1]
    if len(coords) < 3:
        return ""
    # Shapely ring start is arbitrary; begin at leftmost (then lowest) vertex.
    start = min(range(len(coords)), key=lambda i: (coords[i][0], coords[i][1]))
    coords = coords[start:] + coords[:start]
    parts = [f"M {_format_pair(*transform(*coords[0]))}"]
    for x, y in coords[1:]:
        parts.append(f"L {_format_pair(*transform(x, y))}")
    parts.append("Z")
    return " ".join(parts)


def _transform_for(origin: Origin, minx: float, maxy: float):
    if origin is Origin.BOARD_MIN:
        return lambda x, y: (x - minx, maxy - y)
    return lambda x, y: (x, -y)


def _view_box(origin: Origin, minx: float, miny: float, maxx: float, maxy: float) -> str:
    width = maxx - minx
    height = maxy - miny
    if origin is Origin.BOARD_MIN:
        vx, vy = 0.0, 0.0
    else:
        vx, vy = minx, -maxy
    return f"{vx:.6f} {vy:.6f} {width:.6f} {height:.6f}"


def geometry_to_svg(
    geometry: BaseGeometry,
    board: BaseGeometry,
    *,
    origin: Origin,
    strategy: SvgStrategy,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    minx, miny, maxx, maxy = export_bounds(geometry, board)
    width = maxx - minx
    height = maxy - miny
    if width == 0 and height == 0:
        warnings.append("exported geometry and board are empty")
    transform = _transform_for(origin, minx, maxy)
    polygons = _polygons(geometry)
    paths: list[str] = []
    if strategy is SvgStrategy.CONTOURS:
        for polygon in polygons:
            for ring in (polygon.exterior, *polygon.interiors):
                data = _ring_path(ring, transform)
                if data:
                    paths.append(data)
    else:
        subpaths = []
        for polygon in polygons:
            for ring in (polygon.exterior, *polygon.interiors):
                data = _ring_path(ring, transform)
                if data:
                    subpaths.append(data)
        if subpaths:
            paths.append(" ".join(subpaths))

    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": f"{width:.6f}mm",
            "height": f"{height:.6f}mm",
            "viewBox": _view_box(origin, minx, miny, maxx, maxy),
        },
    )
    for data in paths:
        ET.SubElement(
            root,
            f"{{{SVG_NS}}}path",
            {"fill": "black", "fill-rule": "evenodd", "d": data},
        )
    xml = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return xml, warnings
