class Gerber2SvgError(Exception):
    """Base error for gerber2svg."""


class ConfigError(Gerber2SvgError):
    """Incompatible or out-of-range conversion settings."""


class GerberError(Gerber2SvgError):
    """The copper file cannot be read or parsed."""


class UnsupportedGerberError(GerberError):
    """The copper file uses a construct this version refuses."""


class OutlineError(Gerber2SvgError):
    """The board outline is missing, open, or empty."""


class GeometryError(Gerber2SvgError):
    """A boolean operation or repair changed the geometry too much."""


class SvgExportError(Gerber2SvgError):
    """The SVG document cannot be built or written."""
