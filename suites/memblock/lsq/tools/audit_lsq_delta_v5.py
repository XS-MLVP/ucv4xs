#!/usr/bin/env python3
"""253->297 actual Wrapper DA: preserve all original denominators and failures."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_delta_v1 import sources
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name == "lsq-expanded-14", "frozen297-case range; add a version for new scopes"
    prior, current = (ROOT / "results" / n for n in ("lsq-expanded-13", name))
    old, _, _ = verify_common(prior)
    new, _, _ = verify_common(current)
    assert old["tests"] == {"PASS": 216, "FAIL": 37} and new["tests"] == {"PASS": 260, "FAIL": 37}
    before, after = sources(prior), sources(current)
    assert set(before) == set(after)
    added, counts, old_hit, new_hit, total = [], Counter(), 0, 0, 0
    for source in sorted(before):
        a, b = before[source], after[source]
        assert set(a["counts"]) == set(b["counts"])
        old_lines, new_lines = ({line for line, hits in entry["counts"].items() if hits} for entry in (a, b))
        assert not old_lines - new_lines
        old_hit += len(old_lines)
        new_hit += len(new_lines)
        total += len(a["counts"])
        for line in sorted(new_lines - old_lines):
            gap = a["gaps"][line]
            assert gap["classification"] == "missing_scenario_of_existing_feature" and gap["features"] and gap["reachability"] == "not_excluded"
            counts[Path(source).name] += 1
            added.append(dict(source=source, line=line, text=gap["text"], original_features=gap["features"],
                              original_semantic_gap=gap["semantic_gap"], original_classification=gap["classification"],
                              original_hits=a["counts"][line], current_hits=b["counts"][line]))
    assert total == 59602 and len(added) == new_hit-old_hit == 1124 and (old_hit, new_hit) == (58471, 59595)
    assert counts == Counter({"FreeList_2.sv": 138, "FreeList_3.sv": 4, "LoadQueueRAW.sv": 192,
                              "LoadQueueReplay.sv": 406, "PhysicalStoreQueue.sv": 382, "UncacheEntry.sv": 2})
    proof = current / "static-gap-proof-wrapper-v1.json"
    narrow = json.loads(proof.read_text())
    assert narrow["raw_hit"] == new_hit and narrow["raw_total"] == total and narrow["raw_missing"] == narrow["proven_line_count"] == 7 and not narrow["remaining_not_proven"]
    dest = current / "evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT / "tools/audit_lsq_delta_v1.py")
    for file in files:
        target = dest / file.name
        if target.exists():
            assert sha(target) == sha(file)
        else:
            shutil.copy2(file, target)
    report = dict(run=name, status="297_case_raw_DA_delta_prior_semantics_and_seven_narrow_proofs_verified", prior=prior.name,
                  prior_hit=old_hit, current_hit=new_hit, original_denominator=total, actual_newly_hit_lines=len(added),
                  lost_prior_hit_lines=0, remaining_raw_DA=total-new_hit, counts_by_original_file=dict(counts),
                  newly_hit_original_semantic_gaps=added, narrow_proof_sha256=sha(proof),
                  auditors={file.name: sha(dest/file.name) for file in files},
                  limits="Actual53-file native Wrapper closure and same59602 DA universe. All1124 previously unproven rows now dynamically hit by this full297-case run, not by a cross-leaf merge. Remaining6 LQU guarded defaults and1 VLQ ordinary-producer exclusion re-proved on this exact hierarchy, retained in denominator and never counted as hits. This closes current row inventory, NOT37FAIL, six unchecked semantic bins, full mixed seeded/coupled-capacity/fair-drain or final complete LSQ acceptance.")
    output = current / "coverage-delta-audit-v5.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({k: v for k, v in report.items() if k != "newly_hit_original_semantic_gaps"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
