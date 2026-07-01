"""Inscription compiler."""

from .compiler import compile_source
from .version import INSCRIPTION_VERSION

__version__ = INSCRIPTION_VERSION

__all__ = ["compile_source", "__version__"]
