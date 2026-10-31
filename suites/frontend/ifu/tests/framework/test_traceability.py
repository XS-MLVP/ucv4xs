"""Plan/traceability gate: no orphan tests, no unimplemented functional points.

This test runs without any DUT.  It reads the verification plan and the test
sources as text, so it can run in a fresh checkout before native packages are
built.  It enforces the parts of the design method that are mechanically
checkable:

* every functional point has a unique ID and a semantic description;
* every point is referenced by at least one executable test;
* every feature marker names a declared point;
* every component carries at least one complete implementation record
  (requirement, independent oracle, observations, controls, tests, residual),
  and every path named there exists;
* environment points are declared as such and are not counted as hardware.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "verification_plan.json"
MARKER = re.compile(r"pytest\.mark\.feature\(\s*[\"'](IFU-[A-Z]+-[0-9]{3})[\"']")
TRACE_KEYS = ("requirement", "oracle", "observations", "controls", "tests", "residual")
RESIDUAL_KEYS = {"id", "behavior", "category", "evidence", "owner",
                 "next_action", "blocking", "acceptance"}
CATEGORIES = {"defect", "unproven-scope", "observation-limitation",
              "out-of-domain", "structural", "coverage-limit"}
ACCEPTANCE = {"open", "accepted-limited", "resolved"}
RESIDUAL_ID = re.compile(r"R-[0-9]{2}")
COMPONENTS = {"RvcExpander", "InstrBoundary", "PredChecker", "IfuUncacheUnit",
              "FrontendTrigger", "IfuPerfAnalysis", "Ifu", "IfuVerify"}


def plan():
    return json.loads(PLAN.read_text(encoding="utf-8"))


@pytest.mark.feature("IFU-ENV-003")
def test_plan_shape_is_semantic():
    data = plan()
    assert data["version"] == 1
    ids = [feature["id"] for feature in data["features"]]
    assert len(ids) == len(set(ids)), "duplicate functional-point IDs"
    for feature in data["features"]:
        assert feature["component"] in COMPONENTS, feature["id"]
        assert re.fullmatch(r"IFU-[A-Z]+-[0-9]{3}", feature["id"]), feature["id"]
        assert len(feature["title"]) >= 12, feature["id"]
        # A description must state behaviour, not restate a port name.
        assert len(feature["description"]) >= 80, feature["id"]


@pytest.mark.feature("IFU-ENV-003")
def test_every_point_has_a_test_and_every_test_has_a_point():
    data = plan()
    declared = {feature["id"] for feature in data["features"]}
    referenced: dict[str, set[str]] = {}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        for feature_id in MARKER.findall(text):
            referenced.setdefault(feature_id, set()).add(
                str(path.relative_to(ROOT)))
    unknown = set(referenced) - declared
    assert not unknown, f"tests reference undeclared points: {sorted(unknown)}"
    orphan = declared - set(referenced)
    assert not orphan, f"functional points without any test: {sorted(orphan)}"
    hardware = {feature["id"] for feature in data["features"]
                if not feature["id"].startswith("IFU-ENV-")}
    assert hardware - set(referenced) == set()


@pytest.mark.feature("IFU-ENV-003")
def test_each_component_has_a_complete_implementation_record():
    data = plan()
    by_component: dict[str, list[dict]] = {}
    for feature in data["features"]:
        trace = feature.get("metadata", {}).get("traceability")
        if trace is not None:
            by_component.setdefault(feature["component"], []).append(feature)
    missing = {component for component in COMPONENTS if component != "IfuVerify"} \
        - set(by_component)
    assert not missing, f"components without a traceability record: {sorted(missing)}"
    for component, features in by_component.items():
        for feature in features:
            trace = feature["metadata"]["traceability"]
            assert set(trace) == set(TRACE_KEYS), (feature["id"], sorted(trace))
            for key in ("requirement", "oracle", "residual"):
                assert isinstance(trace[key], str) and trace[key].strip(), (feature["id"], key)
            for key in ("observations", "controls", "tests"):
                values = trace[key]
                assert isinstance(values, list) and values, (feature["id"], key)
                assert all(isinstance(value, str) and value.strip() for value in values)
            for nodeid in trace["tests"]:
                path, _, name = nodeid.partition("::")
                source = ROOT / path
                assert source.is_file(), nodeid
                assert f"def {name}(" in source.read_text(encoding="utf-8"), nodeid


@pytest.mark.feature("IFU-ENV-003")
def test_residuals_are_registered_outside_the_pass_fail_statuses():
    """Unproven scope is not a test status; it needs its own register.

    PASS/FAIL/XFAIL/SKIP all describe *executed tests*.  "We did not build this
    input", "the port cannot express it" or "this is out of our boundary" have
    no test, so folding them into PASS would inflate the verdict and folding
    them into XFAIL would require a test that cannot fail.  They are therefore
    registered here, must carry an owner and a next action, and every
    reference from a functional point must resolve.
    """

    data = plan()
    residuals = data.get("residuals")
    assert isinstance(residuals, list) and residuals, "no residual register"
    ids = [row["id"] for row in residuals]
    assert len(ids) == len(set(ids)), "duplicate residual id"
    declared = {feature["id"] for feature in data["features"]}
    for row in residuals:
        assert RESIDUAL_KEYS <= set(row), (row.get("id"), sorted(row))
        assert set(row) <= RESIDUAL_KEYS | {"features"}, (row.get("id"), sorted(row))
        assert RESIDUAL_ID.fullmatch(row["id"]), row["id"]
        assert row["category"] in CATEGORIES, row["id"]
        assert row["acceptance"] in ACCEPTANCE, row["id"]
        assert isinstance(row["blocking"], bool), row["id"]
        for key in ("behavior", "evidence", "owner", "next_action"):
            assert row[key].strip(), (row["id"], key)
        for feature in row.get("features", []):
            assert feature in declared, (row["id"], feature)
        if row["blocking"]:
            assert row.get("features"), f'{row["id"]}: a blocking residual must name its point'

    # Every point that cites a residual must cite one that exists.
    for feature in data["features"]:
        trace = feature.get("metadata", {}).get("traceability")
        if not trace:
            continue
        for found in RESIDUAL_ID.findall(trace["residual"]):
            assert found in ids, (feature["id"], found)

    # The one blocking residual is the tdata2 width defect; its point is the
    # failing one.  Keeping the mapping explicit stops a FAIL from being
    # "explained away" by an unrelated residual.
    blocking = [row for row in residuals if row["blocking"]]
    assert [row["id"] for row in blocking] == ["R-13"], blocking
    assert "IFU-TR-002" in blocking[0]["features"]


@pytest.mark.feature("IFU-ENV-003")
def test_environment_points_are_partitioned_from_hardware():
    data = plan()
    for feature in data["features"]:
        is_env = feature["id"].startswith("IFU-ENV-")
        declared = feature.get("metadata", {}).get("domain",
                                                  "environment" if is_env else "hardware")
        assert declared == ("environment" if is_env else "hardware"), feature["id"]
