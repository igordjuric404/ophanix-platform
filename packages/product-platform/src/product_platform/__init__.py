"""Ophanix product platform control plane."""

from __future__ import annotations

__version__ = "0.1.0"

from product_platform.api.app import create_app

__all__ = ["__version__", "create_app"]

