#!/usr/bin/env python3
"""Preserved logger/elapsed-head helper errors, not RTL-failure waivers."""
import argparse
import itertools
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from audit_lsq_population_v1 import RAW, events, paths_by_node, same_raw
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    run, logger, timer = (ROOT / "results" / n for n in (name, "lsq-expanded-07", "lsq-replay-expanded-02"))
    manifest, _, nodes = verify_common(run)
    lm, _, ln = verify_common(logger)
    tm, _, tn = verify_common(timer)
    assert manifest["tests"] == {"PASS": 136, "FAIL": 36} and len(nodes) == 172
    assert lm["tests"] == {"PASS": 107, "FAIL": 45} and tm["tests"] == {"PASS": 15, "FAIL": 5}
    paths, lp, tp = paths_by_node(run), paths_by_node(logger), paths_by_node(timer)
    rejected = []
    for case in ET.parse(logger / "pytest.xml").iter("testcase"):
        failure = case.find("failure")
        if failure is None or "TypeError: dict() got multiple values for keyword argument 'tick'" not in (failure.text or ""):
            continue
        node = case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
        old, new, count = events(lp[node]), events(paths[node]), 0
        for a, b in zip(old, new):
            assert all(a[key] == b[key] for key in RAW)
            count += 1
        assert count == sum(1 for _ in events(lp[node]))
        rejected.append(dict(nodeid=node, old_raw_samples_exact_prefix=count, now_result="FAIL" if nodes[node] else "PASS",
                             old_trace_sha256=sha(lp[node]), corrected_trace_sha256=sha(paths[node])))
    assert len(rejected) == 19
    timers = []
    for node in sorted(tn):
        if "test_special_mode_2048_" not in node or not tn[node]:
            continue
        assert not nodes[node]
        prior = list(events(tp[node]))
        trigger = next(i for i, row in enumerate(prior) if any(p["execution"]["valid"] and p["execution"]["special_eligible"] for p in row["input"]["loads"]))
        assert prior[trigger - 1]["input"]["pending_next"] != prior[trigger]["input"]["pending_next"]
        assert not any(row["after"]["io_specialMode"] for row in prior)
        assert prior[-1]["checked"] and "error" not in prior[-1]
        current = list(events(paths[node]))
        start = next(i for i, row in enumerate(current) if any(p["execution"]["valid"] and p["execution"]["special_eligible"] for p in row["input"]["loads"]))
        assert current[start - 1]["input"]["pending_next"] == current[start]["input"]["pending_next"]
        first_high = next(row["post_tick"] for row in current if row["after"]["io_specialMode"])
        assert (first_high - current[start]["post_tick"]) // 2 == 2048
        timers.append(dict(nodeid=node, old_trigger_also_moved_head=True, old_model_and_dut_agreed=True,
                           corrected_head_stable_before_trigger=True, first_high_elapsed_cycles=2048,
                           old_trace_sha256=sha(tp[node]), corrected_trace_sha256=sha(paths[node])))
    assert len(timers) == 2
    for node in tn:
        if "test_special_mode_2048_" not in node:
            assert tn[node] == nodes[node]
            same_raw(tp[node], paths[node])
    audit_path = run / "population-history-audit-v1.json"
    independent = json.loads(audit_path.read_text())
    assert independent["tests"] == manifest["tests"]
    dest = run / "evidence-auditors" / Path(__file__).name
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="logger_and_head_trigger_helper_errors_corrected_not_RTL_waivers", tests=manifest["tests"],
                  old_logger_tests=lm["tests"], old_timer_tests=tm["tests"], logger_rejections=rejected, timer_rejections=timers,
                  independent_population_audit_sha256=sha(audit_path), auditor_sha256=sha(dest),
                  limits="Old152 logger run and20 timer run/source/failures retained. Nineteen actual raw traces are exact corrected prefixes; two same-edge head movement helper assertions rejected by original public contract and original model/DUT agreement, stabilized-head repeats retain exact2048 threshold and original completion. Other17 Replay results/raw samples unchanged, including three strict FAIL. Not a DUT fix or skipped stimulus.")
    output = run / "helper-correction-audit-v2.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("logger_rejections", "timer_rejections")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
