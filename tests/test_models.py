from pathlib import Path

import pytest

from gerber2svg.exceptions import ConfigError
from gerber2svg.models import ConversionConfig, Mode, validate_config


def _config(**kwargs) -> ConversionConfig:
    values = {"copper": Path("copper.gbr"), "mode": Mode.NEGATIVE}
    values.update(kwargs)
    return ConversionConfig(**values)


def test_negative_defaults_pass():
    validate_config(_config())


def test_curve_tolerance_must_be_positive():
    with pytest.raises(ConfigError, match="curve tolerance"):
        validate_config(_config(curve_tolerance_mm=0))


def test_negative_clearance_is_rejected():
    with pytest.raises(ConfigError, match="clearance"):
        validate_config(_config(clearance_mm=-0.1))


def test_clearance_only_in_negative_mode():
    with pytest.raises(ConfigError, match="clearance is only valid"):
        validate_config(_config(mode=Mode.COPPER, clearance_mm=0.05))


def test_isolation_requires_positive_width():
    with pytest.raises(ConfigError, match="requires --width"):
        validate_config(_config(mode=Mode.ISOLATION))
    with pytest.raises(ConfigError, match="greater than zero"):
        validate_config(_config(mode=Mode.ISOLATION, width_mm=0))


def test_width_only_in_isolation_mode():
    with pytest.raises(ConfigError, match="width is only valid"):
        validate_config(_config(mode=Mode.COPPER, width_mm=0.3))


def test_margin_cannot_combine_with_outline():
    with pytest.raises(ConfigError, match="margin cannot"):
        validate_config(_config(outline=Path("edge.gbr"), margin_mm=1))
