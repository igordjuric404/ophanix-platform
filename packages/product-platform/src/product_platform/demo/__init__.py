"""Demo Lab scenario catalog and runner primitives."""

from __future__ import annotations

from product_platform.demo.catalog import CUSTOMER_SUPPORT_REFUND_SCENARIO, seed_demo_scenarios
from product_platform.demo.repository import DemoScenarioRepository

__all__ = [
    "CUSTOMER_SUPPORT_REFUND_SCENARIO",
    "DemoScenarioRepository",
    "seed_demo_scenarios",
]
