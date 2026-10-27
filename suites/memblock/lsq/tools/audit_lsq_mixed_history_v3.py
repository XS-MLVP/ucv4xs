#!/usr/bin/env python3
"""311-case gate: old297 unchanged, eight mixed prefixes, six s2 SID cases."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import rob, rob_matches
from audit_lsq_mixed_history_v2 import inspect as inspect_mixed
from audit_lsq_population_v1 import events, paths_by_node, replay_metadata, same_raw, validate_row
from audit_sq_initial import ROOT, sha, verify_common


def inspect_sid(path, failed):
    owners, requests, acks, responses, grants, bypass, data, feedback, completed = {}, {}, {}, {}, {}, {}, set(), set(), set()
    previous, sid_live, counts, violations = None, {}, Counter(), []
    for row in events(path):
        validate_row(row, previous, False)
        i, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        counts["raw_records"] += 1
        assert not i["redirect"]["valid"] and not any(a["valid"] for a in i["addresses"])
        assert not pre["io_mmioStout_valid"] and not pre["io_cmoOpReq_valid"]
        if i["reset"]:
            assert not owners
            previous = row
            continue
        for d in i["dispatch"]:
            if d["valid"]:
                pos = d["load_start"]["value"]
                assert d["need_alloc"] == d["flows"] == 1 and not d["load_start"]["flag"] and pos == len(owners)
                owners[pos] = dict(rob=d["rob"], packet=None)
        for packet in i["loads"]:
            q = packet["execution"]
            if q["valid"]:
                pos = q["uop"]["lq"]["value"]
                s = owners[pos]
                assert q["uop"]["rob"] == s["rob"] and not q["uop"]["lq"]["flag"] and q["nc"]
                if q["replay_feedback"]:
                    assert pos in data and pos not in feedback and q["slot"] == grants[pos] and not q["need_replay"] and not q["causes"]
                    feedback.add(pos)
                else:
                    assert s["packet"] is None and q["need_replay"] and q["causes"] == 1
                    s["packet"] = packet
        for pos, s in owners.items():
            if rob(s["rob"]) < rob(i["pending"]):
                assert pos in feedback and pos in data
        if pre["io_uncache_req_valid"] and i["bus"]["ready"]:
            assert pre["io_uncache_req_bits_cmd"] == 0 and i["bus"]["outstanding"]
            pos = next(pos for pos, s in owners.items() if s["packet"] is not None and s["packet"]["paddr"] == pre["io_uncache_req_bits_addr"])
            s = owners[pos]
            assert pos not in requests and pre["io_uncache_req_bits_vaddr"] == s["packet"]["execution"]["vaddr"] and pre["io_uncache_req_bits_mask"] == 255
            rob_matches(pre, "io_uncache_req_bits_robIdx_", s["rob"])
            requests[pos] = dict(mid=pre["io_uncache_req_bits_id"], tick=tick)
            counts["original_load_requests"] += 1
        b = i["bus"]
        if b["ack"]:
            assert b["ack_to_load"] and b["sid"] not in sid_live
            pos = next(pos for pos, req in requests.items() if req["mid"] == b["mid"] and pos not in acks)
            acks[pos] = dict(sid=b["sid"], tick=tick)
            sid_live[b["sid"]] = pos
            counts["original_direction_acks"] += 1
        if b["response"]:
            assert b["response_to_load"] and not b["error"] and not b["nderr"]
            pos = sid_live.pop(b["response_id"])
            assert pos not in responses
            responses[pos] = dict(data=b["data"], tick=tick)
            counts["original_sid_responses"] += 1
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p+"valid"] and i["replay_ready"][bank]:
                pos = pre[p+"bits_uop_lqIdx_value"]
                assert pos in responses and pos not in grants
                replay_metadata(pre, p+"bits_", owners[pos]["packet"])
                grants[pos] = pre[p+"bits_replayQueueIdx"]
                assert grants[pos] % 3 == bank
        for lane, q in enumerate(i["bypass"]):
            if q["valid"]:
                pos = q["lq"]["value"]
                assert pos in grants and pos not in bypass and q["nc"] and not q["mmio"]
                p = f"io_bypass_{lane}_s1Resp_"
                assert post[p+"valid"] and post[p+"bits_paddr"] == owners[pos]["packet"]["paddr"]
                assert post["io_ldExceptionInfo_valid"] and not post["io_ldExceptionInfo_bits_exceptionVec_19"] and not post["io_ldExceptionInfo_bits_exceptionVec_5"]
                rob_matches(post, "io_ldExceptionInfo_bits_robIdx_", owners[pos]["rob"])
                bypass[pos] = dict(tick=tick, lane=lane)
                counts["actual_clean_original_s1_metadata"] += 1
        for pos, q in bypass.items():
            if q["tick"]+2 != tick:
                continue
            p = f"io_bypass_{q['lane']}_s2Resp_"
            expected, actual = responses[pos]["data"]*((1 << 64)+1), post[p+"bits_data"]
            assert post[p+"valid"] and not post[p+"bits_derr"] and not post[p+"bits_nderr"]
            if actual != expected:
                assert pos == 0 and acks[0]["sid"] == acks[1]["sid"] and responses[0]["tick"] < acks[1]["tick"] < responses[1]["tick"] < tick
                assert actual == responses[1]["data"]*((1 << 64)+1)
                violations.append(dict(issue="LQU-SID-001", phase="s2_original_data", tick=tick, bypass_lane=q["lane"], sid=acks[0]["sid"],
                                       old_response=responses[0], new_ack=acks[1], new_response=responses[1], original_expected_s2_data=expected,
                                       actual_s2_data=actual, s1_original_metadata_clean_and_checked=True,
                                       boundary="Actual original old Load s2 contains the new original Load's bytes. No original S3 feedback/VLQ completion or architecture consequence is claimed for the failed owner."))
            else:
                data.add(pos)
                counts["actual_original_s2_bytes_consumed"] += 1
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            for pos in range(len(completed), len(completed)+post["io_toLsqEnqCtrl_lqDeq_bits"]):
                assert pos in data and pos in feedback
                completed.add(pos)
        previous = row
    assert set(owners) == set(requests) == set(acks) == set(responses) == {0, 1} and not sid_live
    if failed:
        assert len(violations) == 1 and not completed and not previous["checked"] and previous["post_tick"] == violations[0]["tick"] == 80
    else:
        assert not violations and completed == data == feedback == {0, 1} and previous["checked"] and previous["after"]["io_lqEmpty"] and previous["after"]["io_sqEmpty"]
    counts.update(allocated=2, completed=len(completed), cancelled=0, failed_live=2-len(completed))
    return dict(counts=dict(counts), violations=violations, requests=requests, acks=acks, responses=responses)


def audit(name):
    assert name in ("lsq-expanded-15", "lsq-mixed-data-04"), "exact full311 or its14-case addition"
    run = ROOT/"results"/name
    manifest, source, nodes = verify_common(run)
    full = name == "lsq-expanded-15"
    assert manifest["tests"] == ({"PASS": 263, "FAIL": 48} if full else {"PASS": 3, "FAIL": 11})
    assert len(nodes) == (311 if full else 14)
    prior = ROOT/"results/lsq-expanded-14"
    old_nodes = verify_common(prior)[2] if full else {}
    old_paths = paths_by_node(prior) if full else {}
    paths, mixed03 = paths_by_node(run), paths_by_node(ROOT/"results/lsq-seeded-mixed-03")
    assert set(paths) == set(nodes)
    counts, cases = Counter(), []
    for node, path in sorted(paths.items()):
        if node in old_nodes:
            assert nodes[node] == old_nodes[node]
            records = same_raw(path, old_paths[node])
            detail = dict(prior297_original_records_unchanged=records)
            counts["prior297_all_raw_case_histories_unchanged"] += 1
        elif "test_seeded_mixed.py::" in node:
            assert nodes[node]
            detail = inspect_mixed(path)
            records = same_raw(path, mixed03[node])
            assert records == detail["counts"]["raw_records"]
            counts.update(detail["counts"])
            counts["eight_mixed_corrected_histories_unchanged_from03"] += 1
        else:
            assert "test_sid_data.py::" in node
            detail = inspect_sid(path, nodes[node])
            records = detail["counts"]["raw_records"]
            counts.update(detail["counts"])
            counts["actual_sid_s2_counterexamples" if nodes[node] else "actual_different_sid_controls_fully_completed"] += 1
        counts["all_raw_records"] += records
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), result="FAIL" if nodes[node] else "PASS", **detail))
    assert counts["eight_mixed_corrected_histories_unchanged_from03"] == 8 and counts["actual_sid_s2_counterexamples"] == counts["actual_different_sid_controls_fully_completed"] == 3
    assert not full or counts["prior297_all_raw_case_histories_unchanged"] == 297
    groups = {g["instance"]: g for g in json.loads((run/"execution/functional-coverage.json").read_text())["groups"]}
    reached = groups["lsq.lsq_wrapper.reached"]["points"][0]["counts"]
    checked = groups["lsq.lsq_wrapper.checked"]["points"][0]["counts"]
    assert reached["LSQ-STRESS.seeded"] and not reached["LSQ-STRESS.fair_drain"]
    assert not any(checked[name] for name in ("LSQ-STRESS.seeded", "LSQ-STRESS.capacity", "LSQ-STRESS.fair_drain"))
    dest = run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT/"tools/audit_lsq_mixed_history_v1.py", ROOT/"tools/audit_lsq_mixed_history_v2.py", ROOT/"tools/audit_lsq_population_v1.py", ROOT/"tools/audit_lsq_bus_v2.py", ROOT/"tools/audit_sq_initial.py")
    for file in files:
        target = dest/file.name
        if target.exists():
            assert sha(target) == sha(file)
        else:
            shutil.copy2(file, target)
    result = dict(run=name, status="NOT_PASS_mixed_prefixes_and_three_actual_s2_SID_data_counterexamples_audited", tests=manifest["tests"], snapshot_files=len(source),
                  counts=dict(counts), auditors={f.name: sha(dest/f.name) for f in files}, cases=cases,
                  fair_reached_correction="03 mistakenly marked fair reached at run entry; corrected to actual drain entry. All eight raw input/pre/post/tick histories and failures identical, fair still not executed and not counted reached/checked.",
                  limits="Old297 exact raw histories/failures preserved in full311. Eight full-domain seed attempts remain incomplete first-failure prefixes with all original obligations visible; three clean-error minimal same-SID examples now reach and independently check actual corrupted s2 bytes, while three different-SID controls complete both original Loads. All new cases use strict all-output fixture, never protocol probes. No full legal random/fair-drain/coupled-capacity/mixed-reset/full ROB ring or cancelled same-slot restoration acceptance; no Backend/ISA consequence, DUT edits, exclusions or denominator change.")
    out = run/"mixed-history-audit-v3.json"
    if out.exists():
        assert json.loads(out.read_text()) == result
    else:
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
