import math

from shapely import make_valid, union_all
from shapely.affinity import scale
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from gerber2svg.exceptions import GeometryError

REPAIR_AREA_LIMIT_MM2 = 0.001


def as_polygonal(geom: BaseGeometry) -> BaseGeometry:
    if geom.is_empty:
        return Polygon()
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    polygons = [part for part in getattr(geom, "geoms", []) if isinstance(part, Polygon) and not part.is_empty]
    if not polygons:
        return Polygon()
    if len(polygons) == 1:
        return polygons[0]
    return MultiPolygon(polygons)


def repair(geom: BaseGeometry) -> tuple[BaseGeometry, list[str]]:
    if geom.is_empty:
        return Polygon(), []
    if geom.is_valid and isinstance(geom, (Polygon, MultiPolygon)):
        return geom, []
    before = float(geom.area)
    fixed = as_polygonal(make_valid(geom))
    after = float(fixed.area)
    warnings = [f"repaired invalid geometry: area {before:.6f} -> {after:.6f} mm^2"]
    if abs(after - before) > REPAIR_AREA_LIMIT_MM2:
        raise GeometryError(
            f"geometry repair changed area by {abs(after - before):.6f} mm^2 "
            f"({before:.6f} -> {after:.6f})"
        )
    return fixed, warnings


def union_geometries(geoms: list[BaseGeometry]) -> tuple[BaseGeometry, list[str]]:
    present = [geom for geom in geoms if not geom.is_empty]
    if not present:
        return Polygon(), []
    if len(present) == 1:
        return repair(present[0])
    return repair(union_all(present))


def difference_geometries(left: BaseGeometry, right: BaseGeometry) -> tuple[BaseGeometry, list[str]]:
    if left.is_empty or right.is_empty:
        return repair(left)
    return repair(left.difference(right))


def intersection_geometries(left: BaseGeometry, right: BaseGeometry) -> tuple[BaseGeometry, list[str]]:
    if left.is_empty or right.is_empty:
        return Polygon(), []
    return repair(left.intersection(right))


def buffer_resolution(radius_mm: float, curve_tolerance_mm: float) -> int:
    if radius_mm <= 0 or curve_tolerance_mm >= radius_mm:
        return 8
    theta = 2 * math.acos(1 - (curve_tolerance_mm / radius_mm))
    quarter = math.pi / 2
    return max(8, math.ceil(quarter / theta))


def buffer_mm(
    geom: BaseGeometry, distance_mm: float, curve_tolerance_mm: float
) -> tuple[BaseGeometry, list[str]]:
    if distance_mm == 0 or geom.is_empty:
        return geom, []
    resolution = buffer_resolution(abs(distance_mm), curve_tolerance_mm)
    buffered = geom.buffer(
        distance_mm,
        quad_segs=resolution,
        cap_style="round",
        join_style="round",
    )
    return repair(buffered)


def mirror_geometry(geom: BaseGeometry, mirror_x: bool, mirror_y: bool) -> BaseGeometry:
    if geom.is_empty or (not mirror_x and not mirror_y):
        return geom
    return scale(
        geom,
        xfact=-1.0 if mirror_x else 1.0,
        yfact=-1.0 if mirror_y else 1.0,
        origin=(0.0, 0.0),
    )
