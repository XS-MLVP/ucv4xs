#!/usr/bin/env python3
"""Static case inventory; a risk review, NOT proof of semantic correctness."""
import ast
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/reports/evidence/soundness-20261025/case-audit.json"


def audit(root=ROOT):
    cases, failures = [], []
    for path in sorted((root / "tests").rglob("test_*.py")):
        source = path.read_text()
        tree = ast.parse(source)
        defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        counts = collections.Counter(n.name for n in defs)
        for name, count in counts.items():
            if count > 1:
                failures.append(f"{path.relative_to(root)} duplicate {name}")
        for line, text in enumerate(source.splitlines(), 1):
            if text.lstrip().startswith("#") and chr(92) + "nasync def test_" in text:
                failures.append(f"{path.relative_to(root)}:{line} commented-out test")
        for node in defs:
            if not node.name.startswith("test_"):
                continue
            nodes = list(ast.walk(node))
            assertions = [ast.unparse(n.test) for n in nodes if isinstance(n, ast.Assert)]
            calls = [ast.unparse(n.func) for n in nodes if isinstance(n, ast.Call)]
            decorators = [ast.unparse(d) for d in node.decorator_list]
            for n in nodes:
                if isinstance(n, ast.Assert) and isinstance(n.test, ast.Constant):
                    failures.append(f"{path.relative_to(root)}:{n.lineno} constant assertion")
                if isinstance(n, ast.Assert) and isinstance(n.test, ast.IfExp):
                    if isinstance(n.test.orelse, ast.Constant) and n.test.orelse.value is True:
                        failures.append(f"{path.relative_to(root)}:{n.lineno} optional-true assertion")
                if isinstance(n, ast.ExceptHandler) and (n.type is None or ast.unparse(n.type) in ("Exception", "BaseException")):
                    failures.append(f"{path.relative_to(root)}:{n.lineno} broad exception")
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Await):
                    if any(k in ast.unparse(n.value) for k in ("wait_resp(", "wait_response(", "wait_out(")):
                        failures.append(f"{path.relative_to(root)}:{n.lineno} discarded response")
            cases.append(dict(file=str(path.relative_to(root)), name=node.name, line=node.lineno,
                              assertions=assertions, helper_calls=calls, decorators=decorators,
                              category="checker-selftest" if path.name == "test_verification_checks.py" else
                              "structural-stress" if any("structural_stress" in x for x in decorators) else
                              "characterization" if any("characterization" in x for x in decorators) else "functional",
                              review="static inventory only; helper presence does not prove semantic completeness"))
    return dict(format="mmu-case-soundness-audit-v1", cases=cases,
                case_definitions=len(cases), failures=failures,
                status="PASS" if not failures else "FAIL",
                limits=["Static checks do not prove oracle correctness or exhaustive semantic coverage.",
                        "Functional coverage bins are sampled marginals, not full functional-point acceptance."])


if __name__ == "__main__":
    result = audit()
    OUT.write_text(json.dumps(result, indent=2) + chr(10))
    print(result["status"], result["case_definitions"], "definitions", len(result["failures"]), "failures")
    for failure in result["failures"]:
        print(failure)
    raise SystemExit(bool(result["failures"]))
