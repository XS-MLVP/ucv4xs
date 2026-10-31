"""MicroRAS cycle transaction owns every control field."""

from __future__ import annotations

from dataclasses import asdict

from suites.frontend.bpu.uras.transaction.types import UrasCycle


async def test_cycle_transaction_has_complete_idle_defaults(uras_agent):
    del uras_agent
    values = asdict(UrasCycle())
    assert values["enable"] == 1
    assert all(
        value == 0 for name, value in values.items() if name != "enable"
    )
