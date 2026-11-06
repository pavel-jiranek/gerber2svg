from pathlib import Path

from shapely.geometry import Polygon
from typer.testing import CliRunner

from gerber2svg import convert
from gerber2svg.cli import app
from gerber2svg.models import ConversionConfig, Mode

runner = CliRunner()
COPPER = "%FSLAX36Y36*%\n%MOMM*%\n%ADD10C,1.000*%\nD10*\nX0Y0D03*\nM02*\n"


def test_help_exits_zero():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--copper" in result.stdout
    assert "--mode" in result.stdout


def test_version_exits_zero():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_negative_mode_writes_svg(tmp_path: Path):
    copper = tmp_path / "copper.gbr"
    copper.write_text(COPPER, encoding="utf-8")
    output = tmp_path / "out.svg"
    result = runner.invoke(
        app,
        ["--copper", str(copper), "--mode", "negative", "--output", str(output)],
    )
    assert result.exit_code == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    assert "width=" in text
    assert "evenodd" in text


def test_isolation_without_width_exits_2(tmp_path: Path):
    copper = tmp_path / "copper.gbr"
    copper.write_text(COPPER, encoding="utf-8")
    result = runner.invoke(
        app,
        ["--copper", str(copper), "--mode", "isolation", "--output", str(tmp_path / "out.svg")],
    )
    assert result.exit_code == 2
    assert "width" in result.stderr.lower()


def test_width_on_copper_mode_exits_2(tmp_path: Path):
    copper = tmp_path / "copper.gbr"
    copper.write_text(COPPER, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "--copper",
            str(copper),
            "--mode",
            "copper",
            "--width",
            "0.3",
            "--output",
            str(tmp_path / "out.svg"),
        ],
    )
    assert result.exit_code == 2


def test_clearance_on_copper_mode_exits_2(tmp_path: Path):
    copper = tmp_path / "copper.gbr"
    copper.write_text(COPPER, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "--copper",
            str(copper),
            "--mode",
            "copper",
            "--clearance",
            "0.05",
            "--output",
            str(tmp_path / "out.svg"),
        ],
    )
    assert result.exit_code == 2


def test_missing_copper_file_exits_3(tmp_path: Path):
    result = runner.invoke(
        app,
        ["--copper", str(tmp_path / "missing.gbr"), "--mode", "copper", "--output", str(tmp_path / "out.svg")],
    )
    assert result.exit_code == 3


def test_verbose_prints_areas(tmp_path: Path):
    copper = tmp_path / "copper.gbr"
    copper.write_text(COPPER, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "--copper",
            str(copper),
            "--mode",
            "copper",
            "--output",
            str(tmp_path / "out.svg"),
            "--verbose",
        ],
    )
    assert result.exit_code == 0
    assert "primitives " in result.stderr
    assert "copper area " in result.stderr


def test_end_to_end_board():
    fixtures = Path(__file__).parent / "fixtures"
    result = convert(
        ConversionConfig(
            copper=fixtures / "board_e2e_copper.gbr",
            outline=fixtures / "board_e2e_outline.gbr",
            mode=Mode.NEGATIVE,
            width_mm=None,
        )
    )
    assert abs(result.board.area - 240.0) <= 1e-3
    assert result.copper.area > 20.0
    copper_holes = list(result.copper.interiors) if result.copper.geom_type == "Polygon" else []
    if result.copper.geom_type == "MultiPolygon":
        copper_holes = [ring for part in result.copper.geoms for ring in part.interiors]
    assert any(abs(Polygon(ring).area - 1.0) <= 1e-3 for ring in copper_holes)
    negative_holes = list(result.geometry.interiors) if result.geometry.geom_type == "Polygon" else []
    if result.geometry.geom_type == "MultiPolygon":
        negative_holes = [ring for part in result.geometry.geoms for ring in part.interiors]
    assert negative_holes
    isolation = convert(
        ConversionConfig(
            copper=fixtures / "board_e2e_copper.gbr",
            outline=fixtures / "board_e2e_outline.gbr",
            mode=Mode.ISOLATION,
            width_mm=0.3,
        )
    )
    assert isolation.geometry.area > 0
    assert isolation.geometry.area < result.board.area
    assert 'width="20.000000mm"' in result.svg
    assert 'height="12.000000mm"' in result.svg
