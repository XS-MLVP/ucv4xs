#!/usr/bin/env python3
"""Check the new semantic auditor rejects poisoned public effects/identities.

Poison only an in-memory copy. Matching expected output is poisoned as well,
so rejection must come from the independent identity/effect ledger, not merely
from the staged-reference comparison. No original evidence is ever changed.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil

import audit_lsq_remaining_history_v1 as core
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name == "lsq-expanded-14"
    run = ROOT/"results"/name
    verify_common(run)
    paths = core.paths_by_node(run)
    original = core.events
    trials = (("original_slot_feedback", "issued_full_replay_pool", "input", "slot"),
              ("original_cbo_cache_opcode", "each_physical_slot_all_cbo", "before", "io_cmoOpReq_bits_opcode"),
              ("original_zero_actual_bytes", "each_physical_slot_all_cbo", "before", "io_sbuffer_req_0_bits_data"))
    rejected = []
    for label, match, phase, key in trials:
        node = next(n for n in paths if match in n)
        path = paths[node]
        rows = list(original(path))
        change = None
        for row in rows:
            if phase == "input":
                dest = next((q["execution"] for q in row["input"]["loads"] if q["execution"]["valid"] and q["execution"]["replay_feedback"]), None)
            elif key == "io_cmoOpReq_bits_opcode":
                dest = row["before"] if row["before"]["io_cmoOpReq_valid"] and row["input"]["cache_ready"] else None
            else:
                dest = row["before"] if row["before"]["io_sbuffer_req_0_valid"] and row["input"]["sbuffer_ready"][0] else None
            if dest is not None:
                old = dest[key]
                dest[key] ^= 1
                if phase != "input" and key in row.get("expected_"+phase, {}):
                    row["expected_"+phase][key] = dest[key]
                change = dict(post_tick=row["post_tick"], phase=phase, key=key, original=old, poisoned=dest[key])
                break
        assert change is not None
        digest = sha(path)
        core.events = lambda p, rows=rows, path=path: iter(copy.deepcopy(rows)) if p == path else original(p)
        try:
            (core.inspect_cbo if "cbo" in match else core.inspect_memory)(path)
        except AssertionError:
            rejected.append(dict(nodeid=node, obligation=label, journal_sha256=digest, mutation=change, semantic_audit_rejected=True))
        else:
            raise AssertionError(("independent semantic audit accepted a poisoned public history", label))
        finally:
            core.events = original
        assert sha(path) == digest
    node = next(n for n in paths if "entry_zero_cancel" in n)
    rows = list(original(paths[node]))
    first = next(i for i, r in enumerate(rows) if any(p["execution"]["valid"] for p in r["input"]["loads"]))
    red = next(i for i, r in enumerate(rows) if r["input"]["redirect"]["valid"])
    assert rows[red]["post_tick"]-rows[first]["post_tick"] == 6
    assert not any(r["before"]["io_uncache_req_valid"] for r in rows[first:red+1])
    assert not any(r["before"]["io_uncache_req_valid"] and r["input"]["bus"]["ready"] for r in rows[:red+1])
    entry = dict(nodeid=node, original_s3_tick=rows[first]["post_tick"], cancel_tick=rows[red]["post_tick"],
                 elapsed_cycles=3, top_elastic_request_not_visible=True, original_external_jobs=0,
                 boundary="Public fixed pipeline contract: S3 -> next-edge entry holding -> next-edge NC request -> redirect before elastic accepts. No private entry-state read. Original entry0 request-cancel DA witness is counted by the native coverage gate, not invented here.")
    dest = run/"evidence-auditors"/Path(__file__).name
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="three_poisoned_identity_effect_histories_rejected_and_exact_entry0_cancel_timing_verified",
                  negatives=rejected, precise_request_cancel=entry, auditor_sha256=sha(dest),
                  limits="Negative controls validate these three independent ledger obligations only, not all checker correctness. Only in-memory copies were poisoned; the source journals, expected traces, DUT and normal FAIL/PASS outcomes remain unchanged.")
    output = run/"remaining-negative-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
