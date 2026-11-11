"""Machine-checked structural evidence for the out-of-domain flush residual.

This test does **not** drive flush and does not verify cancellation behaviour.
It proves that the recorded closure facts still hold: DefaultConfig ties
``instrUncache.io.flush`` to ``false.B``, the generated Entry/Top modules have
no flush port or ``needFlush`` register, and the full-chip Frontend instance
has no flush connection.  If a later baseline or configuration changes any of
these facts, this test fails and forces the R-FLUSH classification to be
re-reviewed before the old conclusion is reused.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from suites.frontend.instr_uncache import ROOT


def _evidence_tool():
    path = ROOT / "tools/audit_flush_closure.py"
    spec = importlib.util.spec_from_file_location(
        "instr_uncache_flush_closure", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.feature("INC-FLUSH-012")
def test_flush_closure_recorded_evidence_matches_active_design():
    recorded = json.loads(
        (ROOT / "docs/spec/verification/evidence/flush-closure.json").read_text(encoding="utf-8"))
    current = _evidence_tool().facts()
    assert current == recorded, (
        "recorded flush-closure evidence no longer matches the active design; "
        "re-review R-FLUSH rather than reusing the old classification")

    scope = recorded["scope"]
    assert scope["suite"] == "instr_uncache"
    assert scope["baseline"] == "public-a0c2a26cb"
    assert scope["design"] == "DefaultConfig"
    assert "不验证 flush 行为" in scope["conclusion"]

    generation = recorded["generation"]
    assert generation["command_has_default_config"] is True
    assert generation["baseline_commit"] == "a0c2a26cbe3c862175174bad03a1a23c406315ed"

    scala = recorded["scala"]
    assert scala["flush_tie"]["text"] == "instrUncache.io.flush := false.B"
    assert scala["flush_tie"]["line"] == 266
    assert scala["instantiation"]["text"].startswith(
        "val instrUncache: InstrUncache = LazyModule(new InstrUncache)")
    assert scala["entry_capture"]["text"].startswith("when(io.flush")
    assert scala["enable_sim_frontend_default"]["text"] == "EnableSimFrontend: Boolean = false"
    assert scala["sim_frontend_tie"]["text"].startswith(
        "instrUncache.io <> WireDefault(0.U.asTypeOf(instrUncache.io))")


@pytest.mark.feature("INC-FLUSH-012")
def test_generated_closure_has_no_flush_port_or_register():
    recorded = json.loads(
        (ROOT / "docs/spec/verification/evidence/flush-closure.json").read_text(encoding="utf-8"))
    top = recorded["rtl"]["InstrUncache.sv"]
    entry = recorded["rtl"]["InstrUncacheEntry.sv"]
    for row in (top, entry):
        assert row["has_flush"] is False
        assert row["has_needFlush"] is False
        assert all(port[1] != "io_flush" for port in row["ports"])
        assert all(port[1] != "needFlush" for port in row["ports"])
    assert top["port_count"] == 24
    assert entry["port_count"] == 23

    instance = recorded["rtl"]["Frontend.sv"]["instance"]
    assert instance["instance"] == "inner_instrUncache"
    assert instance["has_flush_connection"] is False
