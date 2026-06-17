"""HTTP server package for BookwriterPro.

Imports of FastAPI live inside these server modules only (never in the core
package), so ``import bookwriter`` stays dependency-light. ``create_app`` builds
the FastAPI application implementing the JSON API + static frontend.
"""
from __future__ import annotations

from .api import create_app

__all__ = ["create_app"]
