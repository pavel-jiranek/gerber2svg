from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import typer

from gerber2svg.exceptions import (
    ConfigError,
    GeometryError,
    GerberError,
    OutlineError,
    SvgExportError,
)
from gerber2svg.models import ConversionConfig, Mode, Origin, SvgStrategy
from gerber2svg import convert

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _version(ctx: typer.Context, value: bool) -> None:
    if not value or ctx.resilient_parsing:
        return
    try:
        print(version("gerber2svg"))
    except PackageNotFoundError:
        from gerber2svg import __version__

        print(__version__)
    raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    copper: Path = typer.Option(..., "--copper", help="Input copper Gerber file"),
    output: Path = typer.Option(..., "--output", help="Output SVG file"),
    mode: Mode = typer.Option(..., "--mode", help="copper, negative, or isolation"),
    outline: Path | None = typer.Option(None, "--outline", help="Optional board-outline Gerber"),
    clearance: float = typer.Option(0.0, "--clearance", help="Copper protection offset in mm"),
    width: float | None = typer.Option(None, "--width", help="Isolation band width in mm"),
    curve_tolerance: float = typer.Option(0.005, "--curve-tolerance", help="Maximum chord error in mm"),
    svg_strategy: SvgStrategy = typer.Option(SvgStrategy.COMPOUND, "--svg-strategy"),
    margin: float = typer.Option(0.0, "--margin", help="Margin for an automatic board rectangle, in mm"),
    origin: Origin = typer.Option(Origin.BOARD_MIN, "--origin"),
    mirror_x: bool = typer.Option(False, "--mirror-x"),
    mirror_y: bool = typer.Option(False, "--mirror-y"),
    verbose: bool = typer.Option(False, "--verbose"),
    version_flag: bool = typer.Option(False, "--version", callback=_version, is_eager=True),
) -> None:
    del version_flag
    config = ConversionConfig(
        copper=copper,
        outline=outline,
        mode=mode,
        clearance_mm=clearance,
        width_mm=width,
        curve_tolerance_mm=curve_tolerance,
        svg_strategy=svg_strategy,
        margin_mm=margin,
        origin=origin,
        mirror_x=mirror_x,
        mirror_y=mirror_y,
    )
    try:
        result = convert(config)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except (GerberError, OutlineError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    except GeometryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc
    for warning in result.warnings:
        typer.echo(f"warning: {warning}", err=True)
    if verbose:
        typer.echo(f"primitives {result.primitive_count}", err=True)
        typer.echo(f"copper area {result.copper.area:.6f} mm^2", err=True)
        typer.echo(f"board area {result.board.area:.6f} mm^2", err=True)
        typer.echo(f"output area {result.geometry.area:.6f} mm^2", err=True)
    try:
        output.write_text(result.svg, encoding="utf-8")
    except OSError as exc:
        typer.echo(str(SvgExportError(f"cannot write {output}: {exc}")), err=True)
        raise typer.Exit(code=5) from exc
