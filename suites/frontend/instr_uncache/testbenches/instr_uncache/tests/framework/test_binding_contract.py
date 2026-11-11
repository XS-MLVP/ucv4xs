"""Structural binding and pruned-port evidence for the three DUTs."""

from __future__ import annotations

import pytest


@pytest.mark.feature("INC-ENV-001")
async def test_top_binding_and_pruned_ports(instr_uncache_agent):
    audit = instr_uncache_agent.audit()
    assert audit["top"] == "InstrUncache"
    assert audit["d_ready"].startswith("pruned constant true")
    for name in ("io_flush", "auto_client_out_d_ready", "io_toIfu_resp_ready"):
        assert name in audit["absent"], name
    assert "IfuUncacheUnit.scala:133" in audit["absent"]["io_toIfu_resp_ready"]
    assert "auto_client_out_a_bits_opcode" in audit["absent"]
