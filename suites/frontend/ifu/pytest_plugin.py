"""IFU verification-plan attachment: feature markers become per-feature verdicts."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from toffee.outcomes import case_status, phase_record, uncertain_declaration

pytest_plugins = ("toffee._pytest_outcomes",)

STATES = ("ERROR", "FAIL", "XPASS", "INCOMPLETE", "UNCERTAIN", "PASS", "XFAIL", "SKIP", "NOT_RUN")
DOMAINS = ("hardware", "environment")
# A residual is "not a status": PASS/FAIL/XFAIL/SKIP describe executed tests.
# Unproven scope has no test, so it is registered here and cross-checked
# against the verdict instead of being silently folded into "PASS".
CATEGORIES = ("defect", "unproven-scope", "observation-limitation",
              "out-of-domain", "structural", "coverage-limit")
ACCEPTANCE = ("open", "accepted-limited", "resolved")
RESIDUAL_KEYS = ("id", "behavior", "category", "evidence", "owner",
                 "next_action", "blocking", "acceptance")

_config = None


def domain(feature: dict) -> str:
    """Hardware behaviour vs verification-environment contract.

    ``IFU-ENV-*`` points describe the harness itself (interface constants,
    checker discrimination, traceability, stimulus legality).  They must not
    inflate the hardware pass rate, so the report partitions them exactly like
    the ICache suite does.
    """

    inferred = "environment" if feature["id"].startswith("IFU-ENV-") else "hardware"
    declared = feature.get("metadata", {}).get("domain", inferred)
    if declared != inferred or declared not in DOMAINS:
        raise ValueError(f"{feature['id']}: domain {declared!r} contradicts its ID")
    return inferred


def summarize(features: list[dict]) -> dict:
    counts = Counter(feature["status"] for feature in features)
    executed = len(features) - counts["NOT_RUN"] - counts["SKIP"]
    passed = counts["PASS"]
    return dict(
        planned=len(features), executed=executed, passed=passed,
        status_counts={state: counts[state] for state in STATES},
        execution_rate=100 * executed / len(features) if features else 100.0,
        pass_rate=100 * passed / executed if executed else 0.0,
        completion_rate=100 * passed / len(features) if features else 100.0,
    )


def _load_residuals(path: Path, plan: dict) -> list[dict]:
    residuals = plan.get("residuals", [])
    if not isinstance(residuals, list):
        raise pytest.UsageError(f"{path}: residuals must be a list")
    seen = set()
    for row in residuals:
        for key in RESIDUAL_KEYS:
            if key not in row:
                raise pytest.UsageError(f"{path}: residual missing {key}: {row.get('id')}")
        if row["id"] in seen:
            raise pytest.UsageError(f"{path}: duplicate residual {row['id']}")
        seen.add(row["id"])
        if row["category"] not in CATEGORIES:
            raise pytest.UsageError(f"{path}: {row['id']} bad category {row['category']!r}")
        if row["acceptance"] not in ACCEPTANCE:
            raise pytest.UsageError(f"{path}: {row['id']} bad acceptance {row['acceptance']!r}")
        for key in ("behavior", "evidence", "owner", "next_action"):
            if not isinstance(row[key], str) or not row[key].strip():
                raise pytest.UsageError(f"{path}: {row['id']} empty {key}")
        if not isinstance(row["blocking"], bool):
            raise pytest.UsageError(f"{path}: {row['id']} blocking must be boolean")
    return residuals


def _load_plan(root: Path, name: str) -> list[dict]:
    path = root / name
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("version") != 1 or not isinstance(plan.get("features"), list):
        raise pytest.UsageError(f"{path}: unsupported verification plan")
    seen = set()
    for feature in plan["features"]:
        for key in ("id", "component", "title", "description"):
            if not isinstance(feature.get(key), str) or not feature[key].strip():
                raise pytest.UsageError(f"{path}: feature missing {key}")
        if feature["id"] in seen:
            raise pytest.UsageError(f"{path}: duplicate feature {feature['id']}")
        seen.add(feature["id"])
    return plan["features"]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini("toffee_feature_plan", "IFU functional-point plan", default="verification_plan.json")
    parser.addini("toffee_feature_report", "IFU functional-point report", default="results/feature-points.json")


def pytest_configure(config: pytest.Config) -> None:
    global _config
    config.addinivalue_line("markers", "feature(id): functional point exercised by the test")
    root = Path(config.rootpath)
    config._ifu_plan = _load_plan(root, config.getini("toffee_feature_plan"))
    plan_path = root / config.getini("toffee_feature_plan")
    config._ifu_residuals = _load_residuals(
        plan_path, json.loads(plan_path.read_text(encoding="utf-8")))
    for feature in config._ifu_plan:
        feature.setdefault("metadata", {})
        feature["metadata"].setdefault("domain", domain(feature))
        domain(feature)  # reject a declared domain that contradicts the ID
    config._ifu_ids = {feature["id"] for feature in config._ifu_plan}
    config._ifu_nodes: dict[str, list[str]] = {}
    config._ifu_phases: dict[str, dict] = {}
    config._ifu_declared: dict[str, dict] = {}
    config._ifu_results: dict[str, dict[str, str]] = defaultdict(dict)
    _config = config


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        ids = []
        for marker in item.iter_markers("feature"):
            if len(marker.args) != 1 or not isinstance(marker.args[0], str):
                raise pytest.UsageError(f"{item.nodeid}: feature marker takes one id")
            if marker.args[0] not in config._ifu_ids:
                raise pytest.UsageError(f"{item.nodeid}: unknown feature {marker.args[0]}")
            ids.append(marker.args[0])
        if not ids:
            raise pytest.UsageError(f"{item.nodeid}: no functional point attached")
        declaration = item.get_closest_marker("uncertain")
        if declaration is not None:
            residual = declaration.kwargs.get("reference")
            known = {row["id"]: row for row in config._ifu_residuals}
            if residual not in known:
                raise pytest.UsageError(
                    f"{item.nodeid}: uncertain references unknown residual {residual!r}")
            if known[residual]["acceptance"] == "resolved":
                raise pytest.UsageError(
                    f"{item.nodeid}: residual {residual} is resolved; drop the declaration")
            reason = declaration.kwargs.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise pytest.UsageError(f"{item.nodeid}: uncertain needs a reason")
            config._ifu_declared[item.nodeid] = {
                "reason": declaration.kwargs["reason"].strip(),
                "reference": residual,
            }
        config._ifu_nodes[item.nodeid] = ids
        # Reports carry the project attachment to the xdist controller, where
        # collection hooks do not run. Toffee owns the outcome metadata.
        item.user_properties.append(("ifu_features", ids))


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    config = _config
    if config is None:
        return
    config._ifu_phases.setdefault(report.nodeid, {})[report.when] = phase_record(report)
    ids = dict(report.user_properties).get("ifu_features")
    if ids is not None:
        config._ifu_nodes[report.nodeid] = ids
    declaration = uncertain_declaration(report)
    if declaration is not None:
        config._ifu_declared[report.nodeid] = declaration


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    if config.option.collectonly or hasattr(config, "workerinput"):
        return
    for node, ids in config._ifu_nodes.items():
        # A call's provisional U is not a final result: teardown may fail or
        # never arrive. Use the same complete-case classifier as Toffee/ucv.
        state = case_status(config._ifu_phases.get(node, {}))
        for feature in ids:
            config._ifu_results[feature][node] = state
    features = []
    for planned in config._ifu_plan:
        results = config._ifu_results[planned["id"]]
        statuses = set(results.values())
        status = next((state for state in STATES if state in statuses), "NOT_RUN")
        row = dict(planned)
        row.update(status=status,
                   tests=[dict(nodeid=node, status=result,
                               **({"uncertain": config._ifu_declared[node]}
                                  if result == "UNCERTAIN" else {}))
                          for node, result in sorted(results.items())])
        features.append(row)
    counts = Counter(row["status"] for row in features)
    by_component: dict[str, Counter] = defaultdict(Counter)
    for row in features:
        by_component[row["component"]][row["status"]] += 1
    partitions = {name: summarize([row for row in features if domain(row) == name])
                  for name in DOMAINS}
    partitions["all"] = summarize(features)
    summary = partitions["hardware"]
    errors = []
    hardware = partitions["hardware"]
    blocking_open = [row["id"] for row in config._ifu_residuals
                     if row["blocking"] and row["acceptance"] == "open"]
    if blocking_open and hardware["pass_rate"] >= 100.0:
        errors.append(
            "blocking residual(s) " + ", ".join(blocking_open)
            + " open but every hardware point PASS: a residual cannot close itself")
    failing = [row["id"] for row in features if row["status"] == "FAIL"]
    if failing and not any(row["blocking"] for row in config._ifu_residuals):
        errors.append("failing point(s) " + ", ".join(failing)
                      + " have no blocking residual: register the defect")
    report = dict(format="ifu-feature-report", version=3,
                  generated_at=datetime.now(timezone.utc).isoformat(),
                  summary_domain="hardware",
                  summary=summary,
                  summaries=partitions,
                  components={name: dict(value) for name, value in sorted(by_component.items())},
                  residuals=config._ifu_residuals,
                  residual_summary=dict(
                      total=len(config._ifu_residuals),
                      blocking=sum(1 for row in config._ifu_residuals if row["blocking"]),
                      open=sum(1 for row in config._ifu_residuals if row["acceptance"] == "open"),
                      by_category=dict(Counter(row["category"] for row in config._ifu_residuals)),
                  ),
                  consistency_errors=errors,
                  features=features)
    path = Path(config.rootpath) / config.getini("toffee_feature_report")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    config._ifu_residual_summary = report["residual_summary"]
    config._ifu_summary = summary
    config._ifu_partitions = partitions
    config._ifu_residual_errors = errors


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    if config.option.collectonly:
        return
    summary = getattr(config, "_ifu_summary", None)
    if summary is None:
        return
    partitions = getattr(config, "_ifu_partitions", None) or {"hardware": summary}
    terminalreporter.write_sep("=", "IFU functional points")
    for name in DOMAINS:
        part = partitions.get(name)
        if part is None:
            continue
        uncertain = part["status_counts"].get("UNCERTAIN", 0)
        terminalreporter.write_line(
            f"{name}: planned {part['planned']}, executed {part['executed']}, "
            f"PASS {part['passed']}, UNCERTAIN {uncertain}, "
            f"execution {part['execution_rate']:.1f}% "
            f"pass {part['pass_rate']:.1f}% completion {part['completion_rate']:.1f}%")
    residual_summary = getattr(config, "_ifu_residual_summary", None)
    if residual_summary is not None:
        terminalreporter.write_line(
            "residuals (not a status): total {total}, blocking {blocking}, open {open}, "
            "categories {by_category}".format(**residual_summary))
    errors = getattr(config, "_ifu_residual_errors", None) or []
    for error in errors:
        terminalreporter.write_line(f"RESIDUAL CONSISTENCY ERROR: {error}")
