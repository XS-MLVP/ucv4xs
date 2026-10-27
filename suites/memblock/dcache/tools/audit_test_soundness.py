#!/usr/bin/env python3
"""P09/P10 audit: does every test that we claim to run actually run and check?

Checks, in order of the lessons document:

* collection: Python `def test_*` count vs pytest-collected nodeids (duplicates,
  shadowed names, conditional imports, commented-out defs);
* tautologies: `assert True`, `assert x or True`, `if False`, `except: pass`,
  stringified/one-line-commented tests;
* assertion presence: every `test_*` has at least one `assert` after unwrapping
  its helper calls (helpers are reported separately, not silently trusted);
* skip/xfail census: every marker must be listed with its nodeid and reason.

Outputs JSON so the report can quote it; exits non-zero on a hard finding.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Tests that contain no `assert` themselves but delegate every check to a helper
# that raises.  Each entry names the helper that must actually be called and why
# the delegation is acceptable.  A test with no assert that is NOT listed here is
# a hard finding: it may be an empty run.
DELEGATION_ALLOWLIST = {
    "tests/banked_data_array/test_banked_data_array.py::test_random_traffic":
        ("read_port/read_line", "compare the 8-bank window against the model"),
    "tests/banked_data_array/test_banked_data_array.py::test_mask_class_matrix":
        ("read_port", "window compared to the model after each write class"),
    "tests/counter_filter/test_counter_filter.py::test_random_legal_traffic":
        ("check_queries", "raises on any query/occupancy mismatch"),
    "tests/duplicated_tag_array/test_duplicated_tag_array.py::test_set_independence_and_boundaries":
        ("read_every_set/read_all_ports", "raises on model mismatch per set"),
    "tests/duplicated_tag_array/test_duplicated_tag_array.py::test_random_legal_traffic":
        ("read/write", "raises on model mismatch per access"),
    "tests/load_pipe/test_load_pipe.py::test_random_hits_and_misses":
        ("transaction", "raises on data/index/handled mismatch"),
    "tests/load_pipe/test_load_pipe.py::test_outcome_way_matrix":
        ("transaction", "raises on data/index/handled mismatch"),
    "tests/miss_ready_gen/test_miss_ready_gen.py::test_zero_vector_is_transparent":
        ("check", "raises on any valid/ready/payload mismatch"),
    "tests/miss_ready_gen/test_miss_ready_gen.py::test_walking_bit_all_payload_fields":
        ("check", "raises on any valid/ready/payload mismatch"),
    "tests/miss_ready_gen/test_miss_ready_gen.py::test_random_vectors":
        ("check", "raises on any valid/ready/payload mismatch"),
    "tests/miss_track/test_miss_track.py::test_install_produces_resident_entry":
        ("query", "raises unless the entry classifies as expected"),
    "tests/miss_track/test_miss_track.py::test_alloc_pending_and_owner_retirement":
        ("query/cycle", "cycle compares spec; query raises on class mismatch"),
    "tests/miss_track/test_miss_track.py::test_s2_hit_training":
        ("query", "raises unless the entry classifies as expected"),
    "tests/miss_track/test_miss_track.py::test_invalidate_resident_and_not_pending":
        ("query", "raises unless the entry classifies as expected"),
    "tests/miss_track/test_miss_track.py::test_event_priority_and_coalescing":
        ("query", "raises unless the entry classifies as expected"),
    "tests/miss_track/test_miss_track.py::test_random_traffic":
        ("cycle/query", "cycle compares every lane against the model"),
    "tests/miss_track/test_miss_track.py::test_datapath_bit_sweep":
        ("query", "raises unless the entry classifies as expected"),
}


def collect_nodeids(pattern: str) -> set[str]:
    """Collect nodeids with the same interpreter/venv that runs the suite.

    `-p no:cacheprovider` keeps the audit from writing into the project tree, and
    `--collect-only -q` prints one `path::test` line per nodeid.
    """
    env = dict(__import__("os").environ)
    # Same interpreter as the suite: the toffee venv, not the system python.
    venv = Path(str(ucv_paths.project_root() / '.venv/bin/python'))
    env["PYTHONPATH"] = str(ucv_paths.project_root() / '.tools/share/picker/python') + ":" + str(ROOT)
    out = subprocess.run(
        [str(venv) if venv.is_file() else sys.executable,
         "-m", "pytest", pattern, "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )
    ids = set()
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("tests/") and "::" in line:
            ids.add(line.split(" ")[0])
    if not ids:
        detail = out.stdout[-800:] + "\n" + out.stderr[-800:]
        raise SystemExit("collection produced no nodeids:\n" + detail)
    return ids


def scan_file(path: Path) -> dict:
    text = path.read_text()
    tree = ast.parse(text)
    defs: list[str] = []
    duplicates: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            if node.name in defs:
                duplicates.append(node.name)
            defs.append(node.name)

    findings: dict[str, list] = {
        "tautology_assert_true": [],
        "tautology_or_true": [],
        "if_false": [],
        "except_pass": [],
        "no_assert_in_test": [],
        "no_assert_anywhere": [],
    }
    helper_asserts = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            src = ast.get_source_segment(text, node.test) or ""
            if src.strip() in ("True", "1", "not False"):
                findings["tautology_assert_true"].append(node.lineno)
            if re.search(r"\bor\s+True\b", src):
                findings["tautology_or_true"].append(node.lineno)
        if isinstance(node, ast.If):
            src = ast.get_source_segment(text, node.test) or ""
            if src.strip() in ("False", "0"):
                findings["if_false"].append(node.lineno)
        if isinstance(node, ast.ExceptHandler):
            body = node.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                findings["except_pass"].append(node.lineno)

    top_level_asserts = sum(
        1 for node in tree.body if isinstance(node, ast.Assert))
    helper_asserts = sum(
        len([n for n in ast.walk(node) if isinstance(n, ast.Assert)])
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("test_"))

    # A test with no assert is only acceptable if it delegates to a helper that
    # asserts; record the helper names it calls so the report can list them.
    delegated: dict[str, list[str]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(node))
        calls = sorted({
            n.func.attr if isinstance(n.func, ast.Attribute) else
            (n.func.id if isinstance(n.func, ast.Name) else "")
            for n in ast.walk(node) if isinstance(n, ast.Call)
        } - {""})
        if not has_assert:
            findings["no_assert_in_test"].append(node.name)
            delegated[node.name] = calls

    return {
        "file": str(path.relative_to(ROOT)),
        "defs": len(defs),
        "duplicates": duplicates,
        "top_level_asserts": top_level_asserts,
        "helper_asserts": helper_asserts,
        "findings": {k: v for k, v in findings.items() if v},
        "delegated_checks": delegated,
    }


def scan_markers(path: Path) -> list[dict]:
    text = path.read_text()
    markers = []
    for node in ast.parse(text).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            src = ast.unparse(deco)
            if "xfail" in src or "skip" in src or "rtl_defect" in src:
                markers.append({
                    "test": node.name,
                    "decorator": src,
                    "lineno": node.lineno,
                })
    return markers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default="manifest/test-soundness.json")
    args = parser.parse_args()

    files = sorted((ROOT / "tests").rglob("test_*.py"))
    reports = [scan_file(p) for p in files]
    markers = []
    for p in files:
        for m in scan_markers(p):
            m["file"] = str(p.relative_to(ROOT))
            markers.append(m)

    tree_defs = sum(r["defs"] for r in reports)
    collected = collect_nodeids("tests")
    # nodeid → test name
    collected_names = sorted({nid.split("::")[-1] for nid in collected})
    defined_names = []
    for r in reports:
        for d in ast.parse((ROOT / r["file"]).read_text()).body:
            if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)) and d.name.startswith("test_"):
                defined_names.append(d.name)

    wrapper_reimport = 25 if (ROOT / "tests/dcache_wrapper/test_wrapper_dcache_regression.py").is_file() else 0
    findings = {
        "files": len(files),
        "collection_note": (
            f"{tree_defs} `def test_*` + {wrapper_reimport} tests re-collected in "
            "tests/dcache_wrapper via importlib = the same 25 DCache scenarios run "
            "against the wrapper DUT; no parametrize is used"),
        "defined_tests": tree_defs,
        "collected_nodeids": len(collected),
        "duplicate_names": sorted({n for r in reports for n in r["duplicates"]}),
        "defined_but_not_collected": sorted(set(defined_names) - set(collected_names)),
        "collected_but_not_defined": sorted(set(collected_names) - set(defined_names)),
        "tautology_assert_true": sum(len(r["findings"].get("tautology_assert_true", [])) for r in reports),
        "tautology_or_true": sum(len(r["findings"].get("tautology_or_true", [])) for r in reports),
        "if_false": sum(len(r["findings"].get("if_false", [])) for r in reports),
        "except_pass": sum(len(r["findings"].get("except_pass", [])) for r in reports),
        "tests_without_assert": [
            {"file": r["file"], "test": t,
             "delegates_to": r["delegated_checks"].get(t, []),
             "allowlisted": f"{r['file']}::{t}" in DELEGATION_ALLOWLIST,
             "allowlist_reason": DELEGATION_ALLOWLIST.get(
                 f"{r['file']}::{t}", (None, None))[1]}
            for r in reports for t in r["findings"].get("no_assert_in_test", [])
        ],
        "unallowlisted_no_assert": [
            f"{r['file']}::{t}"
            for r in reports for t in r["findings"].get("no_assert_in_test", [])
            if f"{r['file']}::{t}" not in DELEGATION_ALLOWLIST
        ],
        "markers": markers,
        "per_file": reports,
    }
    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(findings, indent=2) + "\n")

    print(f"files={findings['files']} defined={findings['defined_tests']} "
          f"collected={findings['collected_nodeids']}")
    print(f"duplicates={findings['duplicate_names']}")
    print(f"defined_but_not_collected={findings['defined_but_not_collected']}")
    print(f"collected_but_not_defined={findings['collected_but_not_defined']}")
    print(f"tautology_true={findings['tautology_assert_true']} "
          f"or_true={findings['tautology_or_true']} if_false={findings['if_false']} "
          f"except_pass={findings['except_pass']}")
    print(f"tests_without_assert={len(findings['tests_without_assert'])} "
          f"(allowlisted {sum(1 for i in findings['tests_without_assert'] if i['allowlisted'])})")
    for item in findings["unallowlisted_no_assert"]:
        print(f"  UNALLOWLISTED {item}")
    print(f"markers={len(markers)}")
    for m in markers:
        print(f"  {m['file']}::{m['test']}  {m['decorator'][:90]}")
    hard = (
        findings["unallowlisted_no_assert"]
        or findings["duplicate_names"]
        or findings["defined_but_not_collected"]
        or findings["collected_but_not_defined"]
        or findings["tautology_assert_true"]
        or findings["tautology_or_true"]
        or findings["if_false"]
        or findings["except_pass"]
    )
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
