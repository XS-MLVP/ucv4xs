#!/usr/bin/env python3
"""Independent178-case audit: old172 unchanged; six real RAW/RAR full pools.

This is a new exact-range gate, NOT a widened old172 auditor. Reconstructs
accepted/rejected queries and head reclamation from raw public histories.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, sq
from audit_lsq_memory_v1 import lq
from audit_lsq_population_v1 import events, inspect_replay, paths_by_node, same_raw
from audit_sq_initial import ROOT, sha, verify_common


def inspect_capacity(path):
    kind = "rar" if "test_real_cached_rar_" in next(events(path))["nodeid"] else "raw"
    limit = 96 if kind == "rar" else 56
    records, live, queries, packets = [], {}, [], {}
    public_head, rejected, peak = 0, None, 0
    counts, first_reclaim, first_replay = Counter(), None, None
    for row in events(path):
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["redirect"]["valid"] and not any(inp["rar_revoke_last"] + inp["rar_revoke_older"] + inp["raw_revoke_last"] + inp["raw_revoke_older"])
        if inp["reset"]:
            assert not records
            continue
        old_live = len(live)
        head = public_head if kind == "rar" else pointer(pre, "io_issuePtrExt_")
        live = {uid: q for uid, q in live.items() if (lq(q["lq"]) if kind == "rar" else sq(q["sq"])) > head}
        if len(live) != old_live:
            first_reclaim = first_reclaim or tick
            counts["actual_records_reclaimed_by_public_" + ("vlq_completion" if kind == "rar" else "sta_pointer")] += old_live - len(live)
        for d in inp["dispatch"]:
            if d["valid"] and d["need_alloc"] == 1:
                assert d["flows"] == 1 and lq(d["load_start"]) == len(records)
                records.append(dict(rob=d["rob"], position=len(records)))
        for lane, query in enumerate(inp[kind + "_queries"]):
            if not query["valid"]:
                continue
            owner = next(owner for owner in records if owner["rob"] == query["rob"])
            assert query["data_valid"]
            if kind == "rar":
                assert not query["nc"] and lq(query["lq"]) == owner["position"] and owner["position"] > public_head
            else:
                assert sq(query["sq"]) == 8 and pointer(pre, "io_issuePtrExt_") == 0
            prefix = f"io_ldu_{kind}NukeQuery_{lane}_req_"
            queries.append((owner, query))
            if pre[prefix + "ready"]:
                assert len(live) < limit
                live[owner["position"]] = query
                counts["actual_accepted_records"] += 1
                counts["actual_acceptance_lane_" + str(lane)] += 1
            else:
                assert len(live) == limit and rejected is None and owner["position"] == 119
                rejected = dict(tick=tick, lane=lane, original_rob=owner["rob"], query=query)
                counts["actual_capacity_rejected_target_queries"] += 1
        peak = max(peak, len(live))
        assert len(live) <= limit
        for packet in inp["loads"]:
            q = packet["execution"]
            if not q["valid"]:
                continue
            key = lq(q["uop"]["lq"])
            if q["need_replay"]:
                assert rejected is not None and key == 119 and q["uop"]["rob"] == rejected["original_rob"]
                assert q["causes"] == 1 << (9 if kind == "rar" else 10)
                counts["real_capacity_cause_enters_replay"] += 1
            packets[key] = packet
        if kind == "raw":
            for address in inp["addresses"]:
                if not address["valid"]:
                    continue
                assert all(not (((q["paddr"] ^ address["paddr"]) & ((1 << 28) - 1)) >> 4 == 0 and q["mask"] & address["mask"] and rob(q["rob"]) > rob(address["rob"])) for q in live.values())
            assert not post["io_nuke_rollback_0_valid"] and not post["io_nuke_rollback_1_valid"] and not post["io_mdpTrain_valid"]
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if post[p + "valid"]:
                assert rejected is not None and post[p + "bits_uop_lqIdx_value"] == 119 and not post[p + "bits_uop_lqIdx_flag"]
                assert first_reclaim is not None and len(live) < limit
                first_replay = first_replay or tick
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            public_head += post["io_toLsqEnqCtrl_lqDeq_bits"]
    for owner, query in queries:
        packet = packets[owner["position"]]
        q = packet["execution"]
        assert q["uop"]["rob"] == query["rob"] and packet["paddr"] == query["paddr"]
        if kind == "raw":
            assert q["uop"]["sq"] == query["sq"] and q["mask"] == query["mask"]
            assert q["uop"]["ftq"] == query["ftq"] and q["uop"]["offset"] == query["ftq_offset"] and q["uop"]["checkpoint"] == query["checkpoint"]
    assert peak == limit and not live and public_head == 120 and first_replay >= first_reclaim > rejected["tick"]
    assert counts["actual_accepted_records"] == limit and counts["actual_capacity_rejected_target_queries"] == counts["real_capacity_cause_enters_replay"] == 1
    lifecycle = inspect_replay(path, False)
    assert lifecycle["allocated"] == lifecycle["completed"] == (120 if kind == "rar" else 128)
    assert lifecycle["counts"]["actual_original_replay_grants"] == lifecycle["counts"]["actual_original_slot_feedbacks"] == 1
    return dict(kind=kind, actual_pool_peak=peak, actual_query_acceptances=counts["actual_accepted_records"],
                real_rejection=rejected, first_public_history_reclaim_tick=first_reclaim, first_replay_after_reclaim_tick=first_replay,
                actual_completed_original_uids=lifecycle["completed"], counts=dict(counts), lifecycle=lifecycle)


def audit(name):
    run, baseline = ROOT / "results" / name, ROOT / "results/lsq-expanded-08"
    manifest, source, nodes = verify_common(run)
    old, _, old_nodes = verify_common(baseline)
    assert manifest["tests"] == {"PASS": 142, "FAIL": 36} and len(nodes) == 178
    assert old["tests"] == {"PASS": 136, "FAIL": 36} and len(old_nodes) == 172
    paths, old_paths = paths_by_node(run), paths_by_node(baseline)
    assert set(paths) == set(nodes) and set(old_paths) == set(old_nodes) <= set(nodes)
    counts, cases = Counter(), []
    for node, path in sorted(paths.items()):
        if node in old_nodes:
            assert nodes[node] == old_nodes[node]
            records = same_raw(path, old_paths[node])
            counts["previous172_all_raw_samples_bitwise_rechecked"] += 1
            detail = dict(raw_samples_bitwise_equal_previous=records)
        else:
            assert node.startswith("tests/lsq_wrapper/test_nuke_population.py::") and not nodes[node]
            detail = inspect_capacity(path)
            counts[detail["kind"] + "_full_pool_actual_reclamation_cases"] += 1
            counts[detail["kind"] + "_actual_query_acceptances"] += detail["actual_query_acceptances"]
            counts["new_all_original_uids_completed"] += detail["actual_completed_original_uids"]
            records = sum(1 for _ in events(path))
        counts["all_continuous_raw_records"] += records
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), result="FAIL" if nodes[node] else "PASS", **detail))
    assert counts["previous172_all_raw_samples_bitwise_rechecked"] == 172
    assert counts["rar_full_pool_actual_reclamation_cases"] == counts["raw_full_pool_actual_reclamation_cases"] == 3
    assert counts["rar_actual_query_acceptances"] == 288 and counts["raw_actual_query_acceptances"] == 168
    assert counts["new_all_original_uids_completed"] == 744
    dest = run / "evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT / "tools/audit_lsq_population_v1.py", ROOT / "tools/audit_lsq_memory_v1.py",
             ROOT / "tools/audit_lsq_bus_v2.py", ROOT / "tools/audit_lsq_bus_v3.py")
    for file in files:
        copy_to = dest / file.name
        if copy_to.exists():
            assert sha(copy_to) == sha(file)
        else:
            shutil.copy2(file, copy_to)
    old_audit = baseline / "population-history-audit-v1.json"
    old_helper = baseline / "helper-correction-audit-v2.json"
    assert json.loads(old_audit.read_text())["tests"] == old["tests"] and json.loads(old_helper.read_text())["tests"] == old["tests"]
    report = dict(run=name, status="NOT_PASS_178_case_raw_rar_real_head_population_histories_audited", tests=manifest["tests"],
                  snapshot_files=len(source), counts=dict(counts), baseline_population_audit_sha256=sha(old_audit),
                  baseline_helper_correction_audit_sha256=sha(old_helper), auditor_sha256={f.name: sha(dest / f.name) for f in files}, cases=cases,
                  limits="Exact178 scope only. Old172 raw samples bitwise preserved, including16 explicit protocol probes and all36 FAIL. New6 use cached RAR queries, no fake NC tag; real96 RAR/56 RAW acceptance from each query lane, rejected real target, C_RAR/C_RAW blocked until actual VLQ/STA progress, grant/original-slot feedback and744 UID completion. Pool occupancy from public query identities and public deq/issue pointer, NOT observed private physical slot IDs. Not all physical selection groups/PA metadata/NC, active reset/shared recovery/random or Backend/elaboration acceptance; no DA exclusions or denominator edits.")
    output = run / "nuke-population-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
