"""InstrUncache feature-marker attachments and complete-case verdict aggregation."""

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
SCOPE = "collected-test-markers"
_config = None


def domain(feature: dict) -> str:
    metadata = feature.get("metadata", {})
    inferred = "environment" if feature["id"].startswith("INC-ENV-") else "hardware"
    declared = metadata.get("domain", inferred)
    if declared not in DOMAINS or (declared != inferred and not (
            declared == "environment" and (metadata.get("selftest_only") is True
                                            or metadata.get("structure_only") is True))):
        raise ValueError(f"{feature['id']}: domain {declared!r} contradicts its ID")
    return declared


def summarize(features: list[dict]) -> dict:
    """Legacy count/rate keys refer only to this run's collected marker labels."""
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


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini("toffee_feature_report", "InstrUncache feature-marker report", default="results/feature-points.json")


def pytest_configure(config: pytest.Config) -> None:
    global _config
    config.addinivalue_line("markers", "feature(id): feature label exercised by the test")
    config._instr_uncache_nodes = {}
    config._instr_uncache_phases = {}
    config._instr_uncache_declared = {}
    config._instr_uncache_results = defaultdict(dict)
    config._instr_uncache_selftests = set()
    config._instr_uncache_collected = None
    config._instr_uncache_errors = []
    _config = config


def _attach(config, nodes):
    if not isinstance(nodes, dict):
        config._instr_uncache_errors.append("missing or invalid worker feature attachments")
        return
    for node, ids in nodes.items():
        if (not isinstance(node, str) or not isinstance(ids, list)
                or any(not isinstance(identity, str) or not identity.strip() for identity in ids)
                or ids != sorted(set(ids))):
            config._instr_uncache_errors.append(f"invalid feature attachment: {node}")
        elif node in config._instr_uncache_nodes and config._instr_uncache_nodes[node] != ids:
            config._instr_uncache_errors.append(f"feature attachment changed: {node}")
        else:
            config._instr_uncache_nodes[node] = ids


def pytest_collection_finish(session: pytest.Session) -> None:
    config = session.config
    config._instr_uncache_collected = [item.nodeid for item in session.items]
    for item in session.items:
        ids = set()
        for marker in item.iter_markers("feature"):
            if (len(marker.args) != 1 or not isinstance(marker.args[0], str)
                    or not marker.args[0].strip()):
                raise pytest.UsageError(f"{item.nodeid}: feature marker takes one non-empty id")
            ids.add(marker.args[0])
        attached = sorted(ids)
        config._instr_uncache_nodes[item.nodeid] = attached
        selftest = item.get_closest_marker("selftest") is not None
        if selftest:
            config._instr_uncache_selftests.add(item.nodeid)
        # Final selection only. Toffee owns uncertain reason/reference validation.
        item.user_properties.extend((("instr_uncache_features", attached), ("instr_uncache_selftest", selftest)))


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_node_collection_finished(node, ids):
    config = node.config
    if config._instr_uncache_collected is None:
        config._instr_uncache_collected = list(ids)
    elif config._instr_uncache_collected != list(ids):
        config._instr_uncache_errors.append(f"worker collection differs: {node.gateway.id}")


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    config = node.config
    if error is not None:
        config._instr_uncache_errors.append(f"worker crashed: {node.gateway.id}: {error}")
        return
    attachments = node.workeroutput.get("instr_uncache_feature_nodes")
    _attach(config, attachments)
    if isinstance(attachments, dict) and set(attachments) != set(config._instr_uncache_collected or ()):
        config._instr_uncache_errors.append(f"worker feature collection differs: {node.gateway.id}")
    config._instr_uncache_selftests.update(node.workeroutput.get("instr_uncache_selftests", []))


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    config = _config
    if config is None:
        return
    phases = config._instr_uncache_phases.setdefault(report.nodeid, {})
    if report.when in phases:
        config._instr_uncache_errors.append(f"duplicate phase: {report.nodeid}/{report.when}")
    if phases.get(report.when, {}).get("outcome") != "failed":
        phases[report.when] = phase_record(report)
    properties = dict(report.user_properties)
    _attach(config, {report.nodeid: properties.get("instr_uncache_features")})
    if properties.get("instr_uncache_selftest") is True:
        config._instr_uncache_selftests.add(report.nodeid)
    declaration = uncertain_declaration(report)
    if declaration is not None:
        config._instr_uncache_declared[report.nodeid] = declaration


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    if config.option.collectonly:
        return
    if hasattr(config, "workerinput"):
        config.workeroutput["instr_uncache_feature_nodes"] = config._instr_uncache_nodes
        config.workeroutput["instr_uncache_selftests"] = sorted(config._instr_uncache_selftests)
        return
    if set(config._instr_uncache_nodes) != set(config._instr_uncache_collected or ()):
        config._instr_uncache_errors.append("feature attachments do not match collection")
    for node, ids in config._instr_uncache_nodes.items():
        phases = config._instr_uncache_phases.get(node, {})
        state = case_status(phases) if phases else "NOT_RUN"
        for identity in ids:
            config._instr_uncache_results[identity][node] = state
    features = []
    for identity, results in sorted(config._instr_uncache_results.items()):
        statuses = set(results.values())
        row = dict(id=identity, title=identity, component=identity.rsplit("-", 1)[0],
                   status=next((state for state in STATES if state in statuses), "NOT_RUN"),
                   tests=[dict(nodeid=node, status=result,
                               **({"uncertain": config._instr_uncache_declared[node]}
                                  if result == "UNCERTAIN" else {}))
                          for node, result in sorted(results.items())])
        if set(results) <= config._instr_uncache_selftests:
            row["metadata"] = dict(domain="environment", selftest_only=True)
        features.append(row)
    by_component = defaultdict(Counter)
    for row in features:
        by_component[row["component"]][row["status"]] += 1
    partitions = {name: summarize([row for row in features if domain(row) == name])
                  for name in DOMAINS}
    partitions["all"] = summarize(features)
    report = dict(format="instr-uncache-feature-report", version=1, scope=SCOPE,
                  generated_at=datetime.now(timezone.utc).isoformat(),
                  summary_domain="hardware", summary=partitions["hardware"], summaries=partitions,
                  components={name: dict(value) for name, value in sorted(by_component.items())},
                  consistency_errors=config._instr_uncache_errors, features=features)
    path = Path(config.rootpath) / config.getini("toffee_feature_report")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    config._instr_uncache_partitions = partitions
    if config._instr_uncache_errors and not session.exitstatus:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    if config.option.collectonly:
        return
    partitions = getattr(config, "_instr_uncache_partitions", None)
    if partitions is None:
        return
    terminalreporter.write_sep("=", f"InstrUncache feature markers (scope={SCOPE})")
    for name in DOMAINS:
        part = partitions[name]
        terminalreporter.write_line(
            f"{name}: {part['planned']} collected labels, {part['executed']} executed, "
            f"PASS {part['passed']}; {part['status_counts']}")
    for error in config._instr_uncache_errors:
        terminalreporter.write_line(f"ATTACHMENT ERROR: {error}")
