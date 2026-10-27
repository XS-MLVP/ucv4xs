#!/usr/bin/env python3
"""New semantic failure evidence need not increase already closed raw DA hits."""
import argparse
import json
from pathlib import Path
import shutil

from audit_progress_run_v8 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name == "lsq-expanded-15"
    prior, run = ROOT/"results/lsq-expanded-14", ROOT/"results"/name
    old, _, _ = verify_common(prior)
    new, source, _ = verify_common(run)
    assert old["tests"] == {"PASS": 260, "FAIL": 37} and new["tests"] == {"PASS": 263, "FAIL": 48}
    a, b = (json.loads((p/"line-audit.json").read_text())["native"] for p in (prior, run))
    assert len(a) == len(b) == 1 and a[0]["dut"] == b[0]["dut"] == "lsq_wrapper"
    assert coverage_signature(a[0]) == coverage_signature(b[0])
    assert b[0]["closure_line_hit"] == 59595 and b[0]["closure_line_total"] == 59602 and b[0]["line_hit"] == b[0]["line_total"] == 114
    proof = json.loads((run/"static-gap-proof-wrapper-v1.json").read_text())
    assert proof["raw_missing"] == proof["proven_line_count"] == 7 and not proof["remaining_not_proven"]
    groups = {g["instance"]: g for g in json.loads((run/"execution/functional-coverage.json").read_text())["groups"]}
    reached, checked = (groups["lsq.lsq_wrapper."+k]["points"][0]["counts"] for k in ("reached", "checked"))
    assert sum(bool(n) for n in reached.values()) == 81 and sum(bool(n) for n in checked.values()) == 76
    assert reached["LSQ-STRESS.seeded"] and not reached["LSQ-STRESS.fair_drain"] and not any(checked[k] for k in ("LSQ-STRESS.seeded", "LSQ-STRESS.capacity", "LSQ-STRESS.fair_drain"))
    dest = run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT/"tools/audit_progress_run_v8.py")
    for file in files:
        target = dest/file.name
        if target.exists():
            assert sha(target) == sha(file)
        else:
            shutil.copy2(file, target)
    report = dict(run=name, status="311_case_actual_DA_sets_unchanged_new_semantic_failures_not_waived", prior=prior.name, tests=new["tests"], snapshot_files=len(source),
                  original_DA_total=59602, prior_hit=59595, current_hit=59595, new_hit=0, lost_hit=0, sources=53, remaining_raw_DA=7,
                  reached=81, checked=76, required_semantic_bins=82, actual_new_s2_data_counterexamples=3,
                  proof_sha256=sha(run/"static-gap-proof-wrapper-v1.json"), auditors={f.name: sha(dest/f.name) for f in files},
                  limits="Exact per-source DA universe/hit sets of the actual53-file native Wrapper closure equal14. No leaf merge, denominator reduction or fake dynamic proof hit. New14 cases add8 full-domain first-failure prefixes and3 real s2 SID byte counterexamples+3 fully completed controls even though raw DA cannot improve. Only seeded reached is newly true; fair phase did not execute, all three STRESS bins remain unchecked and all48FAIL retained. No overall acceptance claim.")
    output = run/"coverage-semantic-audit-v6.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
