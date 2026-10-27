#!/usr/bin/env python3
"""Raw Wrapper DA delta, each newly hit line bound to its earlier semantic gap.

Never imports independent leaf coverage, removes original DA denominators, or
uses coverage as evidence that a failing microarchitectural behavior passed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT, sha, verify_common
from coverage_audit import lcov


def sources(directory):
    raw = json.loads((directory / "line-audit-classified.json").read_text())
    assert len(raw["native"]) == 1 and raw["native"][0]["dut"] == "lsq_wrapper"
    top = raw["native"][0]
    tables = lcov(ROOT / top["lcov"])
    result = {}
    for entry in (top, *top["dependencies"]):
        source = entry["source"]
        assert sha(ROOT / source) == entry.get("source_sha256", entry.get("sha256"))
        result[source] = dict(counts=tables.get(str(ROOT / source), {}), gaps={g["line"]: g for g in entry["uncovered"]})
    assert len(result) == 53
    return result


def audit(name):
    assert name == "lsq-expanded-09", "exact frozen178-case delta scope; add a version for new scopes"
    directories = [ROOT / "results" / n for n in ("lsq-expanded-06", "lsq-expanded-08", name)]
    data, stages = [sources(d) for d in directories], []
    for directory in directories:
        verify_common(directory)
    for prior, current, before, after, expected in zip(directories, directories[1:], data, data[1:], (19893, 4533)):
        assert set(before) == set(after)
        added, counts, old_hit, new_hit, denominator = [], Counter(), 0, 0, 0
        for source in sorted(before):
            a, b = before[source], after[source]
            assert set(a["counts"]) == set(b["counts"])
            old, new = ({line for line, hits in entry["counts"].items() if hits} for entry in (a, b))
            assert not old - new, (source, "old hit lines lost", sorted(old - new))
            old_hit += len(old)
            new_hit += len(new)
            denominator += len(a["counts"])
            for line in sorted(new - old):
                gap = a["gaps"][line]
                assert gap["classification"] == "missing_scenario_of_existing_feature" and gap["features"]
                assert gap["reachability"] == "not_excluded"
                counts[Path(source).name] += 1
                added.append(dict(source=source, line=line, text=gap["text"], original_features=gap["features"],
                                  original_semantic_gap=gap["semantic_gap"], original_classification=gap["classification"],
                                  original_hits=a["counts"][line], current_hits=b["counts"][line]))
        assert denominator == 59602 and len(added) == expected == new_hit - old_hit
        stages.append(dict(prior=prior.name, current=current.name, prior_hit=old_hit, current_hit=new_hit,
                           original_denominator=denominator, actual_newly_hit_lines=len(added), lost_prior_hit_lines=0,
                           counts_by_original_file=dict(counts), newly_hit_original_semantic_gaps=added))
    run = directories[-1]
    dest = run / "evidence-auditors" / Path(__file__).name
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="original53_file_DA_delta_and_prior_per_line_semantic_mapping_verified", stages=stages,
                  total_newly_hit_lines=sum(stage["actual_newly_hit_lines"] for stage in stages), remaining_raw_DA=6122,
                  auditor_sha256=sha(dest),
                  limits="Only actual merged native coverage from each real53-file LsqWrapper run. Original59602 DA universe retained, no lost prior hit lines or independent leaf/branch merge. New hits retain each prior reviewed microarchitectural gap mapping, not new semantic acceptance; all36 FAIL and remaining6122 obligations are unchanged.")
    output = run / "coverage-delta-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({**{key: value for key, value in report.items() if key != "stages"},
                      "stages": [{key: value for key, value in stage.items() if key != "newly_hit_original_semantic_gaps"} for stage in stages]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
