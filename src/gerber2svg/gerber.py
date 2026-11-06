from dataclasses import dataclass
from pathlib import Path

from gerbonara import GerberFile
from gerbonara.rs274x import GerberParser
from gerbonara.utils import MM
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from gerber2svg.exceptions import GerberError, UnsupportedGerberError
from gerber2svg.geometry import difference_geometries, repair, union_geometries


@dataclass
class Painted:
    polygon: BaseGeometry
    polarity_dark: bool


def primitive_to_polygon(
    primitive, curve_tolerance_mm: float, warnings: list[str] | None = None
) -> BaseGeometry | None:
    from gerbonara.graphic_primitives import Arc, ArcPoly, Circle, Line, Rectangle

    if not isinstance(primitive, (Circle, Rectangle, Line, Arc, ArcPoly)):
        raise UnsupportedGerberError(
            f"unsupported primitive {type(primitive).__name__}"
        )
    try:
        flat = primitive.to_arc_poly().approximate_arcs(
            max_error=curve_tolerance_mm, clip_max_error=True
        )
    except ZeroDivisionError:
        return None
    if len(flat.outline) < 3:
        return None
    polygon, repair_warnings = repair(Polygon(flat.outline))
    if warnings is not None:
        warnings.extend(repair_warnings)
    if polygon.is_empty or polygon.area == 0:
        return None
    return polygon


def composite_painted(painted: list[Painted]) -> tuple[BaseGeometry, list[str]]:
    warnings: list[str] = []
    image: BaseGeometry = Polygon()
    group: list[BaseGeometry] = []
    group_dark: bool | None = None

    def flush() -> None:
        nonlocal image, group, group_dark
        if not group or group_dark is None:
            group = []
            group_dark = None
            return
        merged, union_warnings = union_geometries(group)
        warnings.extend(union_warnings)
        if group_dark:
            if image.is_empty:
                image = merged
            else:
                image, more = union_geometries([image, merged])
                warnings.extend(more)
        elif image.is_empty:
            warnings.append("clear polarity applied to empty copper")
        else:
            image, more = difference_geometries(image, merged)
            warnings.extend(more)
        group = []
        group_dark = None

    for item in painted:
        if group_dark is None:
            group_dark = item.polarity_dark
        elif item.polarity_dark != group_dark:
            flush()
            group_dark = item.polarity_dark
        group.append(item.polygon)
    flush()
    return image, warnings


class _OpenStepRepeat(list):
    """Gerbonara 1.6.3 uses `if step_repeat_objects`, so an empty list never collects repeats."""

    def __bool__(self) -> bool:
        return True


class _StepRepeatParser(GerberParser):
    def _parse_step_repeat(self, match):
        super()._parse_step_repeat(match)
        objects = self.step_repeat_objects
        if type(objects) is list:
            self.step_repeat_objects = _OpenStepRepeat(objects)


def _primitive_position(primitive) -> str:
    if hasattr(primitive, "x") and hasattr(primitive, "y"):
        return f"{float(primitive.x):.4f},{float(primitive.y):.4f}"
    if hasattr(primitive, "x1") and hasattr(primitive, "y1"):
        return f"{float(primitive.x1):.4f},{float(primitive.y1):.4f}"
    return "unknown"


def load_copper(
    path: Path, curve_tolerance_mm: float
) -> tuple[BaseGeometry, list[str], int]:
    if not path.is_file():
        raise GerberError(f"copper file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if "IPNEG" in text:
        raise UnsupportedGerberError(
            "negative image polarity (%IPNEG*%) is not supported"
        )
    try:
        gerber = GerberFile()
        _StepRepeatParser(gerber).parse(text, filename=str(path))
    except Exception as exc:
        raise GerberError(f"invalid Gerber file {path}: {exc}") from exc

    painted: list[Painted] = []
    warnings: list[str] = []
    primitive_count = 0
    for index, obj in enumerate(gerber.objects):
        try:
            primitives = list(obj.to_primitives(MM))
        except Exception as exc:
            raise GerberError(f"cannot render object {index} in {path}: {exc}") from exc
        for primitive in primitives:
            primitive_count += 1
            polygon = primitive_to_polygon(primitive, curve_tolerance_mm, warnings)
            if polygon is None:
                warnings.append(
                    f"omitted zero-area {type(primitive).__name__} at {_primitive_position(primitive)}"
                )
                continue
            painted.append(Painted(polygon, bool(primitive.polarity_dark)))
    copper, composite_warnings = composite_painted(painted)
    warnings.extend(composite_warnings)
    return copper, warnings, primitive_count


import math

from shapely.geometry import MultiPolygon, Polygon

from gerber2svg.exceptions import OutlineError
from gerber2svg.geometry import repair

SNAP_MM = 0.01


def _close_enough(start: tuple[float, float], end: tuple[float, float]) -> bool:
    return math.hypot(start[0] - end[0], start[1] - end[1]) <= SNAP_MM


def _outline_polylines(
    path: Path, curve_tolerance_mm: float
) -> list[list[tuple[float, float]]]:
    from gerbonara.graphic_objects import Arc, Flash, Line, Region
    from gerbonara.utils import approximate_arc

    if not path.is_file():
        raise OutlineError(f"outline file not found: {path}")
    try:
        gerber = GerberFile.open(path)
    except Exception as exc:
        raise OutlineError(f"invalid outline file {path}: {exc}") from exc

    polylines: list[list[tuple[float, float]]] = []
    for obj in gerber.objects:
        if isinstance(obj, Line):
            converted = obj.converted(MM)
            polylines.append(
                [
                    (float(converted.x1), float(converted.y1)),
                    (float(converted.x2), float(converted.y2)),
                ]
            )
        elif isinstance(obj, Arc):
            converted = obj.converted(MM)
            # graphic_objects.Arc stores cx/cy relative to the start point.
            points = [
                (float(x), float(y))
                for x, y in approximate_arc(
                    float(converted.cx) + float(converted.x1),
                    float(converted.cy) + float(converted.y1),
                    float(converted.x1),
                    float(converted.y1),
                    float(converted.x2),
                    float(converted.y2),
                    converted.clockwise,
                    max_error=curve_tolerance_mm,
                )
            ]
            if len(points) >= 2:
                polylines.append(points)
        elif isinstance(obj, Region):
            primitive = next(obj.to_primitives(MM))
            flat = primitive.approximate_arcs(max_error=curve_tolerance_mm)
            outline = [(float(x), float(y)) for x, y in flat.outline]
            if outline and not _close_enough(outline[0], outline[-1]):
                outline.append(outline[0])
            polylines.append(outline)
        elif isinstance(obj, Flash):
            raise OutlineError("outline contains a flash, which has no centerline")
        else:
            raise OutlineError(f"unsupported outline object {type(obj).__name__}")
    return polylines


def _chain_rings(
    polylines: list[list[tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    unused = [list(line) for line in polylines if len(line) >= 2]
    rings: list[list[tuple[float, float]]] = []
    while unused:
        chain = unused.pop(0)
        progressed = True
        while progressed and not _close_enough(chain[0], chain[-1]):
            progressed = False
            for index, other in enumerate(unused):
                if _close_enough(chain[-1], other[0]):
                    chain.extend(other[1:])
                    unused.pop(index)
                    progressed = True
                    break
                if _close_enough(chain[-1], other[-1]):
                    chain.extend(list(reversed(other[:-1])))
                    unused.pop(index)
                    progressed = True
                    break
        if not _close_enough(chain[0], chain[-1]):
            gap = math.hypot(chain[0][0] - chain[-1][0], chain[0][1] - chain[-1][1])
            raise OutlineError(f"outline contour is open by {gap:.4f} mm")
        rings.append(chain)
    if not rings:
        raise OutlineError("outline contains no contours")
    return rings


def _rings_to_board(
    rings: list[list[tuple[float, float]]],
) -> tuple[BaseGeometry, list[str]]:
    warnings: list[str] = []
    shapes = []
    for ring in rings:
        polygon, ring_warnings = repair(Polygon(ring))
        warnings.extend(ring_warnings)
        if isinstance(polygon, MultiPolygon):
            shapes.extend(part for part in polygon.geoms if part.area > 0)
        elif not polygon.is_empty and polygon.area > 0:
            shapes.append(polygon)
    if not shapes:
        raise OutlineError("outline produced empty geometry")

    def depth(shape: Polygon) -> int:
        point = shape.representative_point()
        return sum(
            1
            for other in shapes
            if other is not shape and other.area > shape.area and other.contains(point)
        )

    outers = [shape for shape in shapes if depth(shape) % 2 == 0]
    holes = [shape for shape in shapes if depth(shape) % 2 == 1]
    built: list[Polygon] = []
    for outer in outers:
        own_holes = [
            hole.exterior
            for hole in holes
            if depth(hole) == depth(outer) + 1
            and outer.contains(hole.representative_point())
        ]
        built.append(Polygon(outer.exterior, own_holes))
    board: BaseGeometry = built[0] if len(built) == 1 else MultiPolygon(built)
    board, board_warnings = repair(board)
    warnings.extend(board_warnings)
    if board.is_empty or board.area <= 0:
        raise OutlineError("outline has no positive area")
    return board, warnings


def load_outline(
    path: Path, curve_tolerance_mm: float
) -> tuple[BaseGeometry, list[str]]:
    rings = _chain_rings(_outline_polylines(path, curve_tolerance_mm))
    return _rings_to_board(rings)
