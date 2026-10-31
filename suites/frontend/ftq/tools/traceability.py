#!/usr/bin/env python3
"""Functional-point traceability audit and report.

The plan in ``docs/functional-points.md`` is the source of IDs.  Every test
function must name at least one plan point with ``@pytest.mark.feature`` and
every plan point must have at least one test; checker self-tests are marked
``selftest`` and are reported separately, never as hardware credit.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/functional-points.md"
ID = re.compile(r"\bFTQ-[A-Z]+-\d+\b")


def plan_ids() -> list[str]:
    return sorted(set(ID.findall(PLAN.read_text())))


def _decorators(nodes) -> tuple[list[str], bool]:
    """Collect feature IDs and selftest from any pytest marker expression."""

    features: list[str] = []
    selftest = False
    for node in nodes:
        for item in ast.walk(node):
            if not isinstance(item, ast.Attribute):
                continue
            if item.attr == "selftest":
                selftest = True
            if item.attr != "feature":
                continue
            parent = None
            for candidate in ast.walk(node):
                if isinstance(candidate, ast.Call) and candidate.func is item:
                    parent = candidate
                    break
            if parent is None or len(parent.args) != 1:
                raise ValueError("feature marker needs one string literal")
            if not isinstance(parent.args[0], ast.Constant):
                raise ValueError("feature marker needs one string literal")
            features.append(str(parent.args[0].value))
    return features, selftest


def _module_markers(tree: ast.Module) -> tuple[list[str], bool]:
    """Module-level ``pytestmark`` applies to every test in the file."""

    nodes = []
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if any(isinstance(target, ast.Name) and target.id == "pytestmark"
               for target in targets):
            nodes.append(statement.value)
    return _decorators(nodes)


def test_functions() -> list[dict[str, object]]:
    rows = []
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text())
        module_features, module_selftest = _module_markers(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            features, selftest = _decorators(node.decorator_list)
            merged = list(dict.fromkeys([*module_features, *features]))
            rows.append(dict(
                path=str(path.relative_to(ROOT)),
                name=node.name,
                nodeid=f"{path.relative_to(ROOT)}::{node.name}",
                features=merged,
                selftest=selftest or module_selftest,
            ))
    return rows


def audit() -> list[str]:
    plan = plan_ids()
    known = set(plan)
    errors = []
    if not plan:
        errors.append("functional-points.md defines no FTQ IDs")
    seen = set()
    for row in test_functions():
        if row["nodeid"] in seen:
            errors.append(f"duplicate nodeid: {row['nodeid']}")
        seen.add(row["nodeid"])
        if row["selftest"]:
            continue
        if not row["features"]:
            errors.append(f"{row['nodeid']}: test has no feature marker")
        for feature in row["features"]:
            if feature not in known:
                errors.append(f"{row['nodeid']}: unknown feature {feature}")
    covered = {feature for row in test_functions() for feature in row["features"]}
    for feature in plan:
        if feature not in covered:
            errors.append(f"{feature}: plan point has no test")
    return errors


def verdicts(xml: Path) -> dict[str, str]:
    if not xml.is_file():
        return {}
    result = {}
    root = ET.parse(xml).getroot()
    for case in root.iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        path = classname.replace(".", "/") + ".py"
        nodeid = f"{path}::{name}"
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if failure is not None:
            message = failure.get("message", "")
            state = "XPASS" if message.startswith("[XPASS(strict)]") else "FAIL"
        elif error is not None:
            state = "ERROR"
        elif skipped is not None and skipped.get("type") == "pytest.xfail":
            state = "XFAIL"
        elif skipped is not None:
            state = "SKIP"
        else:
            state = "PASS"
        result[nodeid] = state
    return result


def state_of(nodeid: str, states: dict[str, str]) -> str:
    """Aggregate a parametrized test's variants into one verdict."""

    if nodeid in states:
        return states[nodeid]
    variants = [value for key, value in states.items()
                if key.startswith(nodeid + "[")]
    if not variants:
        return "not-run"
    for state in ("FAIL", "ERROR", "XPASS", "SKIP", "XFAIL"):
        if state in variants:
            return state if len(set(variants)) == 1 else state + " (mixed)"
    return "PASS"


def report(xml: Path | None = None) -> str:
    rows = test_functions()
    states = verdicts(xml) if xml is not None else {}
    plan = plan_ids()
    lines = ["# FTQ 功能点追溯", ""]
    if xml is not None:
        lines.append(f"运行证据：`{xml}`")
        lines.append("")
    if xml is None:
        lines += ["| 功能点 | 用例 |", "|---|---|"]
    else:
        lines += ["| 功能点 | 用例 | 本次判定 |", "|---|---|---|"]
    for feature in plan:
        tests = [row for row in rows if feature in row["features"]]
        if not tests:
            lines.append(f"| {feature} | 无 | 缺口 |" if xml is not None
                         else f"| {feature} | 无 |")
            continue
        cells = []
        for row in tests:
            state = state_of(row["nodeid"], states)
            cells.append(f"`{row['nodeid']}` ({state})" if xml is not None
                         else f"`{row['nodeid']}`")
        line = f"| {feature} | " + "<br>".join(cells) + " |"
        lines.append(line if xml is None else line + " |")
    selftests = [row for row in rows if row["selftest"]]
    if selftests:
        lines += ["", "## 检查器与计划自检（不计硬件功能 credit）", ""]
        for row in selftests:
            state = state_of(row["nodeid"], states)
            lines.append(f"- `{row['nodeid']}` ({state})" if xml is not None
                         else f"- `{row['nodeid']}`")
    unmarked = [row for row in rows if not row["selftest"] and not row["features"]]
    if unmarked:
        lines += ["", "## 未标注功能点", ""]
        for row in unmarked:
            lines.append(f"- `{row['nodeid']}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/traceability.md")
    args = parser.parse_args()
    errors = audit()
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    args.output.write_text(report(args.xml))
    print(f"{len(plan_ids())} functional points traced to "
          f"{sum(1 for row in test_functions() if row['features'])} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
