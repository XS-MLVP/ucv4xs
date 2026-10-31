from pathlib import Path

import pytest

from suites.frontend.bpu.coverage.phase_audit import POINTS
from suites.frontend.bpu.coverage.phase_audit import expected_counts
from suites.frontend.bpu.coverage.phase_audit import read_counts


@pytest.mark.parametrize("mode,updates,holds", [
    ("single", 1, 0), ("adjacent", 2, 0), ("spaced", 2, 0),
    ("retarget", 1, 0), ("saturating", 2, 1),
])
def test_phase_audit_checks_both_selected_updates_and_saturation(mode, updates, holds):
    assert expected_counts(mode) == {
        "cross_row_counter": updates, "provider_hit": updates,
        "saturation_hold": holds, "counter_step": updates - holds,
        "cross_row_identity": updates,
    }


def _data(path: Path, *, duplicate=False, omit=None):
    records = []
    for name, (kind, line, arm) in POINTS.items():
        if name == omit:
            continue
        meta = f"\x01page\x02{kind}/WriteBuffer\x01l\x02{line}\x01o\x02{arm}"
        record = f"C '{meta}' 7"
        records.append(record)
        if duplicate and name == "cross_row_counter":
            records.append(record)
    # A toggle at the same source location must never mask a missing line arm.
    records.append("C '\x01page\x02v_toggle/WriteBuffer\x01l\x021424\x01o\x02elsif' 999")
    path.write_text("\n".join(records), encoding="utf-8")


def test_phase_audit_reads_raw_points_without_blending_toggles(tmp_path):
    data = tmp_path / "probe.dat"
    _data(data)
    assert read_counts(data) == dict.fromkeys(POINTS, 7)


def test_phase_audit_rejects_missing_point_instead_of_assuming_zero(tmp_path):
    data = tmp_path / "probe.dat"
    _data(data, omit="cross_row_counter")
    with pytest.raises(ValueError, match="missing diagnostic coverage"):
        read_counts(data)


def test_phase_audit_rejects_ambiguous_duplicate_points(tmp_path):
    data = tmp_path / "probe.dat"
    _data(data, duplicate=True)
    with pytest.raises(ValueError, match="duplicate diagnostic coverage"):
        read_counts(data)


def test_phase_audit_rejects_unknown_sequences():
    with pytest.raises(ValueError, match="unknown diagnostic sequence"):
        expected_counts("hold-valid-to-inflate-counts")


def test_prefix_check_detects_wrong_phase_even_if_final_total_is_correct():
    first = expected_counts("retarget", through=0)
    second = expected_counts("retarget", through=1)
    assert first == second == expected_counts("single")
    assert expected_counts("saturating", through=0)["saturation_hold"] == 0
    assert expected_counts("saturating", through=1)["saturation_hold"] == 1


@pytest.mark.parametrize("mode,through", [("single", 1), ("adjacent", -1), ("spaced", 2)])
def test_phase_audit_rejects_invalid_prefixes(mode, through):
    with pytest.raises(ValueError, match="invalid diagnostic prefix"):
        expected_counts(mode, through=through)
