#!/usr/bin/env python3
"""Exact194->210 Wrapper DA delta; prior v1/v2 gates stay unchanged."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_delta_v1 import sources
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name == "lsq-expanded-11", "exact210-case frozen delta scope"
    prior,current=(ROOT/"results"/n for n in ("lsq-expanded-10",name))
    old,_,_=verify_common(prior)
    new,_,_=verify_common(current)
    assert old["tests"] == {"PASS":157,"FAIL":37} and new["tests"] == {"PASS":173,"FAIL":37}
    before,after=sources(prior),sources(current)
    assert set(before) == set(after)
    added,counts,old_hit,new_hit,denominator=[],Counter(),0,0,0
    for source in sorted(before):
        a,b=before[source],after[source]
        assert set(a["counts"]) == set(b["counts"])
        old_lines,new_lines=({line for line,hits in entry["counts"].items() if hits} for entry in (a,b))
        assert not old_lines-new_lines
        old_hit+=len(old_lines)
        new_hit+=len(new_lines)
        denominator+=len(a["counts"])
        for line in sorted(new_lines-old_lines):
            gap=a["gaps"][line]
            assert gap["classification"] == "missing_scenario_of_existing_feature" and gap["features"] and gap["reachability"] == "not_excluded"
            counts[Path(source).name]+=1
            added.append(dict(source=source,line=line,text=gap["text"],original_features=gap["features"],
                              original_semantic_gap=gap["semantic_gap"],original_classification=gap["classification"],
                              original_hits=a["counts"][line],current_hits=b["counts"][line]))
    assert denominator == 59602 and len(added) == new_hit-old_hit == 1893
    assert (old_hit,new_hit) == (55502,57395)
    dest=current/"evidence-auditors"
    files=(Path(__file__),ROOT/"tools/audit_lsq_delta_v1.py")
    for file in files:
        copy_to=dest/file.name
        if copy_to.exists():
            assert sha(copy_to) == sha(file)
        else:
            shutil.copy2(file,copy_to)
    report=dict(run=name,status="210_case_raw_DA_delta_and_prior_per_line_semantics_verified",prior=prior.name,
                prior_hit=old_hit,current_hit=new_hit,original_denominator=denominator,actual_newly_hit_lines=len(added),
                lost_prior_hit_lines=0,remaining_raw_DA=denominator-new_hit,counts_by_original_file=dict(counts),
                newly_hit_original_semantic_gaps=added,auditor_sha256={file.name:sha(dest/file.name) for file in files},
                limits="Actual real53-file LsqWrapper native runs only. Original59602 DA universe/old hits retained, no leaf/branch merge or exclusion. New hits retain each prior microarchitectural semantic gap mapping, not evidence that all37 FAIL passed. Remaining2207 and complete reset/cancel/random/final audit obligations persist.")
    output=current/"coverage-delta-audit-v3.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({key:value for key,value in report.items() if key != "newly_hit_original_semantic_gaps"},indent=2,ensure_ascii=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
