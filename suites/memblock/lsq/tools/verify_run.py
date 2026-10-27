#!/usr/bin/env python3
"""Check real committed evidence, identities and source snapshots before sign-off."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(name, line_audit, semantic_complete, line_complete):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"]
    assert manifest["pytest_exitstatus"] == 0 and manifest["cleanup_complete"]
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"], artifact["path"]
        if artifact["kind"] == "native":
            for path, digest in artifact["build"]["files"].items():
                assert sha(Path(path)) == digest, path
    source = json.loads((run / "source-evidence.json").read_text())
    for path, digest in source["files"].items():
        assert sha(run / "verification-source" / path) == digest, path
    functional = json.loads((run / "execution/functional-coverage.json").read_text())
    missing = {}
    by_name = {g["instance"]: g for g in functional["groups"]}
    for group in functional["groups"]:
        assert group["collection_complete"]
        point = group["points"][0]
        assert not point["unknown"] and not point["unmatched"]
        absent = [key for key, count in point["counts"].items() if not count]
        if absent:
            missing[group["instance"]] = absent
        if group["instance"].endswith("checked"):
            reached = by_name[group["instance"].removesuffix("checked") + "reached"]["points"][0]["counts"]
            for key, count in point["counts"].items():
                assert reached[key] >= count, (group["instance"], key, reached[key], count)
    if semantic_complete:
        assert not missing, missing
    audit_path = run / line_audit
    audit = json.loads(audit_path.read_text())
    assert audit["run"] == name and audit["tests"] == manifest["tests"]
    native_ids = {a["build"]["build_id"] for a in manifest["artifacts"] if a["kind"] == "native"}
    assert {row["build_id"] for row in audit["native"]} == native_ids
    if line_complete:
        for row in audit["native"]:
            assert row["line_total"] and row["line_hit"] == row["line_total"] and not row["uncovered"], row["dut"]
            for dep in row.get("dependencies", []):
                assert dep["line_hit"] == dep["line_total"] and not dep["uncovered"], dep["source"]
    # The evidence auditor is frozen separately when it was added after a run.
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/coverage_audit.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool), "do not overwrite a historical evidence auditor"
        else:
            shutil.copy2(tool, dest)
        auditors[str(dest.relative_to(run))] = sha(dest)
    result = {"schema_version": 1, "run": name, "status": "verified", "tests": manifest["tests"],
              "manifest_sha256": sha(run / "execution/manifest.json"), "line_audit": line_audit,
              "line_audit_sha256": sha(audit_path), "builds": len(native_ids),
              "functional_groups": len(functional["groups"]), "missing_semantic_scenarios": missing,
              "required_semantic_complete": semantic_complete, "required_line_complete": line_complete,
              "verification_snapshot_files": len(source["files"]), "auditors": auditors}
    out = run / "evidence-check.json"
    if out.exists():
        assert json.loads(out.read_text()) == result, "refusing to overwrite a different historical evidence check"
    else:
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--line-audit", default="line-audit.json")
    parser.add_argument("--require-semantic-complete", action="store_true")
    parser.add_argument("--require-line-complete", action="store_true")
    args = parser.parse_args()
    verify(args.name, args.line_audit, args.require_semantic_complete, args.require_line_complete)
