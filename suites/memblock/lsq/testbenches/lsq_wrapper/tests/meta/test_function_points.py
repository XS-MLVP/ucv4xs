"""The LSQ functional-point ledger must stay complete across iterations.

Adding a transaction kind, a response outcome or an instruction family without
declaring what covers it is exactly how the MMIO Store fault path stayed
unnoticed.  This gate makes that omission a test failure instead of a prose
reminder, so it runs in the ordinary suite regression.
"""
from pathlib import Path

import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper.coverage import function_points as fp

pytestmark = pytest.mark.selftest

CONTRACTS = __import__('suites.memblock.lsq', fromlist=['ROOT']).ROOT / "docs/spec/design/contracts"


def test_ledger_is_structurally_complete():
    assert fp.validate() == []


def test_every_kind_and_outcome_is_enumerated():
    assert set(fp.CELLS) == set(fp.KINDS)
    for kind, row in fp.CELLS.items():
        assert set(row) == set(fp.OUTCOMES), kind


def test_instruction_families_are_classified():
    for name in fp.REQUIRED_INSTRUCTIONS:
        item = fp.INSTRUCTIONS[name]
        assert item["domain"] in ("in-layer", "out-of-domain") or item["domain"].startswith(("in-layer", "out-of-domain")), name
        if not item["reaches"]:
            assert item["reason"], name


def test_gaps_are_actionable():
    for kind, row in fp.CELLS.items():
        for outcome, cell in row.items():
            if cell.status == fp.GAP:
                assert cell.missing and cell.next, (kind, outcome)
                assert cell.next.lower().startswith(("add", "extend", "build", "drive", "split", "model", "belongs")), (
                    kind, outcome, cell.next)


def test_declared_failures_point_at_real_tests():
    """A cell that claims a true FAIL must name a test file that exists."""
    root = __import__('suites.memblock.lsq', fromlist=['ROOT']).ROOT
    for kind, row in fp.CELLS.items():
        for outcome, cell in row.items():
            if cell.status != fp.FAIL:
                continue
            for locator in cell.evidence:
                if "/" in locator:
                    assert (root / locator).exists() or (root / (locator + ".py")).exists(), (
                        kind, outcome, locator)


def test_contracts_exist_and_name_the_ledger():
    mapping = CONTRACTS / "instruction-source-mapping.md"
    matrix = CONTRACTS / "kind-outcome-matrix.md"
    assert mapping.exists() and matrix.exists()
    text = mapping.read_text() + matrix.read_text()
    for kind in fp.KINDS:
        assert f"`{kind}`" in text or f"| `{kind}`" in text, kind
    assert "function_points" in matrix.read_text() or "kind-outcome-matrix" in mapping.read_text()


def test_interaction_windows_are_declared_and_evidenced():
    """Cross-module windows must be enumerated, not discovered by accident."""
    from pathlib import Path as _Path
    root = __import__('suites.memblock.lsq', fromlist=['ROOT']).ROOT
    assert fp.INTERACTION_WINDOWS, "no interaction windows declared"
    for wid, window in fp.INTERACTION_WINDOWS.items():
        assert window["status"] in fp.STATUSES, wid
        if window["status"] in (fp.PASS, fp.FAIL):
            for locator in window["evidence"].split(", "):
                assert (root / locator).exists(), (wid, locator)
        else:
            assert window.get("missing") and window.get("next"), wid


def test_interaction_contract_names_every_window():
    from pathlib import Path as _Path
    doc = __import__('suites.memblock.lsq', fromlist=['ROOT']).ROOT / "docs/spec/design/contracts/interaction-semantics.md"
    assert doc.exists()
    text = doc.read_text()
    for wid in fp.INTERACTION_WINDOWS:
        assert wid in text, f"{wid} missing from the interaction contract"


def test_failing_windows_have_a_probe_file():
    from pathlib import Path as _Path
    root = __import__('suites.memblock.lsq', fromlist=['ROOT']).ROOT
    for wid, window in fp.INTERACTION_WINDOWS.items():
        if window["status"] != fp.FAIL:
            continue
        probe = root / "testbenches/lsq_wrapper/tests/test_interaction_windows.py"
        assert probe.exists(), wid
        assert window["note"], wid
