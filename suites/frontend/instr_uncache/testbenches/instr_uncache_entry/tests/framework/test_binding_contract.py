"""InstrUncacheEntry structural binding and pruned-port evidence."""

from __future__ import annotations

import pytest


@pytest.mark.feature("INC-ENV-001")
async def test_entry_binding_and_pruned_ports(instr_uncache_entry_agent):
    audit = instr_uncache_entry_agent.audit()
    assert audit["top"] == "InstrUncacheEntry"
    assert audit["flush"].startswith("pruned constant false")
    for name in ("io_flush", "io_id", "io_mmioGrant_ready", "io_resp_ready"):
        assert name in audit["absent"], name
    assert "Frontend.scala:266" in audit["absent"]["io_flush"]
    assert "InstrUncacheImp.scala:88" in audit["absent"]["io_mmioGrant_ready"]
