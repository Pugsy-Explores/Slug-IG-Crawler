"""Instagram profile scraper package (distribution name on PyPI: ``slug-ig-crawler``)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("slug-ig-crawler")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
