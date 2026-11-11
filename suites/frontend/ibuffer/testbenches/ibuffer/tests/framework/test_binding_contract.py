"""Structural binding, ownership and real-submodule evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from suites.frontend.ibuffer import ROOT
from suites.frontend.ibuffer.testbenches.ibuffer.model import ENQUEUE_WIDTH


@pytest.mark.feature("IBUF-ENV-001")
async def test_ibuffer_binds_every_port(ibuffer_agent):
    audit = ibuffer_agent.audit()
    assert audit["top"] == "IBuffer"
    assert "enq_enable" in audit["inputs"]
    assert "exception_mask" in audit["inputs"]
    assert "commit_has_vsetvl" in audit["inputs"]
    assert "pred_taken_35" not in audit["inputs"]
    assert "pred_taken_34" in audit["inputs"]
    assert "out_0_vtype_vlmul" in audit["outputs"]
    assert "out_7_specvtype_illegal" in audit["outputs"]
    assert "perf_0" in audit["outputs"]
    assert "perf_0..8" in audit["not_compared"]
    # 8 lanes * 27 fields, plus in_ready, empty, 8 stall reasons and 9 perf.
    assert len(audit["outputs"]) == 8 * 27 + 2 + 8 + 9


@pytest.mark.feature("IBUF-ENV-001")
async def test_ibuffer_closure_retains_the_real_vtype_gen(ibuffer_agent):
    """The top DUT must be the real IBuffer/VTypeGen RTL, not a Python stand-in."""
    package = (ROOT / "dut" / "ibuffer").resolve()
    assert package.is_dir(), f"missing built DUT package {package}"
    rtl = package.parent / "rtl"
    receipt = json.loads((rtl / "source.json").read_text(encoding="utf-8"))
    assert receipt["top"] == "IBuffer"
    assert "IBuffer.sv" in receipt["files"]
    assert "VTypeGen.sv" in receipt["files"], sorted(receipt["files"])
    assert receipt["files"]["VTypeGen.sv"]
    top = (rtl / "IBuffer.sv").read_text(encoding="utf-8")
    assert "VTypeGen vtypeGen" in top
    assert (package / "IBufferDut.v").is_file()


@pytest.mark.feature("IBUF-ENV-001")
async def test_ibuffer_enqueue_width_matches_the_ifu_contract(ibuffer_agent):
    audit = ibuffer_agent.audit()
    assert ENQUEUE_WIDTH == 36
    assert audit["staging"].startswith("8-entry")
