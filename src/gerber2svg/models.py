from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from shapely.geometry.base import BaseGeometry

from gerber2svg.exceptions import ConfigError


class Mode(str, Enum):
    COPPER = "copper"
    NEGATIVE = "negative"
    ISOLATION = "isolation"


class Origin(str, Enum):
    PRESERVE = "preserve"
    BOARD_MIN = "board-min"


class SvgStrategy(str, Enum):
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


def validate_config(config: ConversionConfig) -> None:
    if config.curve_tolerance_mm <= 0:
        raise ConfigError("curve tolerance must be greater than zero")
    if config.margin_mm < 0:
        raise ConfigError("margin must be zero or positive")
    if config.clearance_mm < 0:
        raise ConfigError("clearance must be zero or positive")
    if config.clearance_mm != 0 and config.mode is not Mode.NEGATIVE:
        raise ConfigError("clearance is only valid in negative mode")
    if config.mode is Mode.ISOLATION:
        if config.width_mm is None:
            raise ConfigError("isolation mode requires --width")
        if config.width_mm <= 0:
            raise ConfigError("isolation width must be greater than zero")
    elif config.width_mm is not None:
        raise ConfigError("width is only valid in isolation mode")
    if config.outline is not None and config.margin_mm != 0:
        raise ConfigError("margin cannot be combined with an outline file")
