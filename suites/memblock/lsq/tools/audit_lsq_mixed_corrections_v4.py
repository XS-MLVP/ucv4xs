#!/usr/bin/env python3
"""Corrected14-case gate and exact fullVA-only original-input correction proof.

The original v3 strict SID semantic helper remains unchanged and still rejects
04. No relaxing Replay metadata checks to accommodate an invalid producer.
"""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import shutil

from audit_lsq_mixed_history_v2 import inspect as inspect_mixed
from audit_lsq_mixed_history_v3 import inspect_sid
from audit_lsq_population_v1 import events, paths_by_node, same_raw
from audit_sq_initial import ROOT, sha, verify_common


def differences(a, b, path=()):
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys()
        return [d for k in a for d in differences(a[k], b[k], (*path, k))]
    if isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b)
        return [d for n, (x, y) in enumerate(zip(a, b)) for d in differences(x, y, (*path, n))]
    return [] if a == b else [dict(path=list(path), old=a, new=b)]


def fullva_proof(old_path, new_path):
    changes, count = [], 0
    for old, new in itertools.zip_longest(events(old_path), events(new_path)):
        assert old is not None and new is not None
        assert old["pre_tick"] == new["pre_tick"] and old["post_tick"] == new["post_tick"]
        for field in ("input", "pins", "post_pins", "before", "after"):
            for change in differences(old[field], new[field]):
                path = change["path"]
                if field == "input":
                    assert len(path) == 3 and path[0] == "loads" and path[2] == "fullva"
                    lane = path[1]
                    assert new["input"]["loads"][lane]["fullva"] == new["input"]["loads"][lane]["execution"]["vaddr"]
                elif field in ("pins", "post_pins"):
                    assert len(path) == 1 and path[0].startswith("io_ldu_ldin_") and path[0].endswith("_bits_fullva")
                else:
                    assert path == ["io_ldExceptionInfo_bits_vaddr"]
                changes.append(dict(tick=new["post_tick"], field=field, **change))
        count += 1
    assert changes
    return dict(old_sha256=sha(old_path), new_sha256=sha(new_path), equal_record_count=count, only_fullva_input_and_corresponding_exception_VA_output_changed=True, changes=changes)


def audit(name):
    assert name == "lsq-mixed-data-05"
    run = ROOT/"results"/name
    manifest, source, nodes = verify_common(run)
    assert manifest["tests"] == {"PASS": 3, "FAIL": 11} and len(source) == 360 and len(nodes) == 14
    paths, old04, old03 = (paths_by_node(ROOT/"results"/n) for n in (name, "lsq-mixed-data-04", "lsq-seeded-mixed-03"))
    assert set(paths) == set(nodes) == set(old04)
    counts, cases = Counter(), []
    for node, path in sorted(paths.items()):
        if "test_seeded_mixed.py::" in node:
            detail = inspect_mixed(path)
            assert same_raw(path, old03[node]) == same_raw(path, old04[node]) == detail["counts"]["raw_records"]
            detail["same_raw_as_corrected03_and04"] = True
        else:
            detail = inspect_sid(path, nodes[node])
            detail["fullva_correction_proof"] = fullva_proof(old04[node], path)
        counts.update(detail["counts"])
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), **detail))
    groups = {g["instance"]: g for g in json.loads((run/"execution/functional-coverage.json").read_text())["groups"]}
    reached, checked = (groups["lsq.lsq_wrapper."+kind]["points"][0]["counts"] for kind in ("reached", "checked"))
    assert reached["LSQ-STRESS.seeded"] and not reached["LSQ-STRESS.fair_drain"] and not any(checked[k] for k in ("LSQ-STRESS.seeded", "LSQ-STRESS.capacity", "LSQ-STRESS.fair_drain"))
    dest = run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT/"tools/audit_lsq_mixed_history_v1.py", ROOT/"tools/audit_lsq_mixed_history_v2.py", ROOT/"tools/audit_lsq_mixed_history_v3.py")
    for file in files:
        target = dest/file.name
        if target.exists():
            assert sha(target) == sha(file)
        else:
            shutil.copy2(file, target)
    report = dict(run=name, status="NOT_PASS_14_case_mixed_and_original_s2_SID_bytes_with_exact_fullVA_correction_audited", tests=manifest["tests"],
                  snapshot_files=len(source), counts=dict(counts), cases=cases, auditors={f.name: sha(dest/f.name) for f in files},
                  limits="All eight corrected mixed raw histories are identical to03/04; no fair phase executed or claimed reached. Six new normal-producer SID cases differ from rejected04 only in each original fullVA input and its exact corresponding exception VA output; original bus timing/SID/data/ROB/PA and all other actual pins unchanged. Three genuine s2 SID corruptions and three controls that really complete both original Loads. The unchanged v3 semantic SID core is used, not relaxed to bless04. Failed/cancelled original obligations remain unfinished, no full random/fair/coupled-capacity/reset/whole-LSQ acceptance.")
    out = run/"mixed-correction-audit-v4.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
