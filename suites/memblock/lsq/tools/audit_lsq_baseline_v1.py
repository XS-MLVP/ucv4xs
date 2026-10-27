#!/usr/bin/env python3
"""Recheck original53 RTL, native closure and clean pinned OPEN source tree."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    run = ROOT / "results" / name
    manifest, source, _ = verify_common(run)
    workspace = ROOT.parents[1]
    checkout, original = workspace / "XiangShan", workspace / "soc-split/rtl"
    pinned = {}
    for line in (ROOT / "manifest/lsq-rtl.sha256").read_text().splitlines():
        digest, file = line.split()
        assert Path(file).name == file
        pinned[file] = digest
    assert len(pinned) == 53
    closure = json.loads((ROOT / "rtl/lsq_wrapper/source.json").read_text())["files"]
    assert closure == pinned
    assert all(sha(original / file) == digest for file, digest in pinned.items())
    assert all(sha(ROOT / "rtl/lsq_wrapper" / file) == digest for file, digest in pinned.items())
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=checkout, text=True)
    assert commit == "893e1580b705d81f113c30c7a05734e09a08050e" and not status
    native = [a for a in manifest["artifacts"] if a["kind"] == "native"]
    assert len(native) == 1 and native[0]["build"]["name"] == "DUTLsqWrapperDut"
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="original53_native_closure_and_clean_pinned_open_source_rechecked", tests=manifest["tests"],
                  checkout=str(checkout), commit=commit, git_porcelain=status, original_rtl=str(original), files=pinned,
                  snapshot_files=len(source), auditor_sha256=sha(dest),
                  limits="No target RTL or Chisel edits. This is hash/checkout/native-artifact provenance, not fresh Chisel elaboration, arbitrary-parameter equivalence, private source use, full Backend/ISA verification or functional acceptance.")
    output = run / "baseline-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "files"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
