#!/usr/bin/env python3
"""Strict three-owner/SID failure reconstruction; preserves the v2 scope gate.

No model/actor change dictionaries or issue manifest are used as an oracle.
The previously audited 49 cases must have identical raw samples. New20 cases
are independently rebuilt from dispatch, S3, bus, replay, bypass, WB and deq.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, record_checks, rob_matches, rows, sq, store_perf
from audit_sq_initial import ROOT, sha, verify_common


def differences(row):
    result = {}
    for phase in ("before", "after"):
        result[phase] = {pin: [row[phase][pin], want] for pin, want in row["expected_" + phase].items()
                         if (row[phase][pin] ^ want) & row["masks_" + phase].get(pin, -1)}
    return result


def inspect_new(trace, failed):
    owners, loads, requests, acks, responses, grants, by_mid = {}, {}, {}, {}, {}, {}, {}
    feedback, data_checked, bypass, completed = set(), set(), {}, set()
    serial, address, data, attributes, pending_attribute = None, None, None, None, None
    head = lq_head = wb = 0
    sid_live, returned_sids, violations, counts = {}, {}, [], Counter()
    for row in trace:
        inp, pins, pre, post, tick = row["input"], row["pins"], row["before"], row["after"], row["post_tick"]
        if inp["reset"]:
            assert not owners
            continue
        for dispatch in inp["dispatch"]:
            if not dispatch["valid"]:
                continue
            assert dispatch["flows"] == 1 and dispatch["need_alloc"] in (1, 2)
            role = "store" if dispatch["need_alloc"] == 2 else f"load{dispatch['load_start']['value']}"
            assert role not in owners
            owners[role] = dispatch
            if role == "store":
                assert sq(dispatch["store_end"]) == 1
        assert inp["pending"] == owners["store"]["rob"] if "store" in owners and not feedback else True
        for lane, current in enumerate(inp["addresses"]):
            if current["valid"]:
                assert "store" in owners and address is None and current["slot"] == 0 and current["rob"] == owners["store"]["rob"]
                address, pending_attribute = current, (tick + 2, lane)
        if pending_attribute is not None and pending_attribute[0] == tick:
            attributes = inp["attributes"][pending_attribute[1]]
        for current in inp["data"]:
            if current["valid"]:
                assert "store" in owners and data is None and sq(current["sq"]) == 0
                data = current
        for current in inp["loads"]:
            q = current["execution"]
            if not q["valid"]:
                continue
            role = f"load{q['uop']['lq']['value']}"
            assert role in owners and q["uop"]["rob"] == owners[role]["rob"]
            if q["replay_feedback"]:
                assert role in loads and role not in feedback and role in data_checked and q["slot"] == grants[role]
                assert not q["need_replay"] and not q["causes"] and q["uop"] == loads[role]["execution"]["uop"]
                feedback.add(role)
            else:
                assert role not in loads and q["nc"] and q["need_replay"] and q["causes"] == 1
                loads[role] = current
        if serial is not None:
            assert not pre["io_uncache_req_valid"], "all cases must obey exclusion before the failing edge"
        if pre["io_uncache_req_valid"] and inp["bus"]["ready"]:
            if pre["io_uncache_req_bits_cmd"] == 1:
                role = "store"
                assert address is not None and data is not None and attributes is not None
                assert pre["io_uncache_req_bits_addr"] == address["paddr"] and pre["io_uncache_req_bits_vaddr"] == address["vaddr"]
                assert pre["io_uncache_req_bits_data"] == data["data"] and pre["io_uncache_req_bits_nc"] == int(attributes["nc"])
            else:
                assert pre["io_uncache_req_bits_cmd"] == 0
                role = next(role for role, load in loads.items() if load["paddr"] == pre["io_uncache_req_bits_addr"])
                assert pre["io_uncache_req_bits_vaddr"] == loads[role]["execution"]["vaddr"] and pre["io_uncache_req_bits_nc"]
            assert serial is None and role not in requests and pre["io_uncache_req_bits_mask"] == 255
            rob_matches(pre, "io_uncache_req_bits_robIdx_", owners[role]["rob"])
            mid = pre["io_uncache_req_bits_id"]
            assert (role != "store", mid) not in by_mid
            by_mid[(role != "store", mid)] = role
            requests[role] = dict(tick=tick, mid=mid, nc=bool(pre["io_uncache_req_bits_nc"]))
            counts["new_original_bus_requests"] += 1
            if not (inp["bus"]["outstanding"] and requests[role]["nc"]):
                serial = role
        bus = inp["bus"]
        if bus["ack"]:
            role = by_mid[(bus["ack_to_load"], bus["mid"])]
            assert role not in acks and bus["sid"] not in sid_live
            assert pins["io_uncache_idResp_bits_is2lq"] == int(role != "store")
            if bus["sid"] in returned_sids:
                previous = returned_sids[bus["sid"]]
                assert previous["tick"] < tick and previous["role"] not in bypass
                counts["actual_sid_reuse_after_resp_before_old_bypass"] += 1
            acks[role] = dict(tick=tick, sid=bus["sid"])
            sid_live[bus["sid"]] = role
            counts["new_original_direction_acks"] += 1
        response_role = None
        if bus["response"]:
            response_role = sid_live.pop(bus["response_id"])
            assert response_role not in responses and bus["response_to_load"] == (response_role != "store")
            assert pins["io_uncache_resp_bits_is2lq"] == int(response_role != "store")
            responses[response_role] = dict(tick=tick, data=bus["data"], error=int(bus["error"]), nderr=int(bus["nderr"]))
            returned_sids[bus["response_id"]] = dict(tick=tick, role=response_role)
            counts["new_original_direction_responses"] += 1
            if serial == response_role:
                serial = None
        if serial is not None and post["io_uncache_req_valid"]:
            assert serial == "store" and response_role == "load0" and "store" not in responses
            assert "load1" in loads and "load1" not in requests
            assert not requests["store"]["nc"] and inp["bus"]["outstanding"]
            assert post["io_uncache_req_bits_cmd"] == 0 and post["io_uncache_req_bits_addr"] == loads["load1"]["paddr"]
            assert not pre["io_uncache_req_valid"] and not bus["ready"]
            violations.append(dict(issue="LSQ-BUS-OWNERSHIP-001", tick=tick, serial_owner="store", unrelated_response=response_role,
                                   original_store_request=requests["store"], original_store_ack=acks["store"],
                                   store_response_still_owed=True, next_original_load_pa=loads["load1"]["paddr"],
                                   expected_req_valid=0, actual_req_valid=post["io_uncache_req_valid"],
                                   evidence_limit="Premature visible request after unrelated response; no third actual req.fire or downstream effect observed before strict checker stops."))
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p + "valid"] and inp["replay_ready"][bank]:
                role = f"load{pre[p + 'bits_uop_lqIdx_value']}"
                assert role in responses and role not in grants
                rob_matches(pre, p + "bits_uop_robIdx_", owners[role]["rob"])
                assert pre[p + "bits_vaddr"] == loads[role]["execution"]["vaddr"]
                grants[role] = pre[p + "bits_replayQueueIdx"]
                assert grants[role] % 3 == bank
        for lane, query in enumerate(inp["bypass"]):
            if not query["valid"]:
                continue
            role = f"load{query['lq']['value']}"
            assert role in grants and role not in bypass and role in responses
            p = f"io_bypass_{lane}_s1Resp_"
            assert post[p + "valid"] and post[p + "bits_paddr"] == loads[role]["paddr"]
            assert post["io_ldExceptionInfo_valid"] and post["io_ldExceptionInfo_bits_vaddr"] == loads[role]["fullva"]
            rob_matches(post, "io_ldExceptionInfo_bits_robIdx_", owners[role]["rob"])
            expected = [responses[role]["error"], responses[role]["nderr"]]
            actual = [post["io_ldExceptionInfo_bits_exceptionVec_19"], post["io_ldExceptionInfo_bits_exceptionVec_5"]]
            if actual != expected:
                other = next(other for other in responses if other != role)
                assert role == "load0" and other == "load1" and acks[role]["sid"] == acks[other]["sid"]
                assert responses[role]["tick"] < acks[other]["tick"] and responses[other]["tick"] < tick
                assert actual == [responses[other]["error"], responses[other]["nderr"]]
                violations.append(dict(issue="LQU-SID-001", tick=tick, old_uid=role, new_uid=other, sid=acks[role]["sid"],
                                       old_response=responses[role], new_ack=acks[other], new_response=responses[other], bypass_lane=lane,
                                       old_original_pa=loads[role]["paddr"], original_expected_error_nderr=expected, actual_old_error_nderr=actual,
                                       evidence_limit="Actual old Load exception reports new Load error bits at s1; strict checker stops before this case's s2 data observation."))
            bypass[role] = dict(tick=tick, lane=lane)
        for role, query in bypass.items():
            if query["tick"] + 2 != tick:
                continue
            p = f"io_bypass_{query['lane']}_s2Resp_"
            assert post[p + "valid"] and post[p + "bits_data"] == responses[role]["data"] * ((1 << 64) + 1)
            assert post[p + "bits_derr"] == responses[role]["error"] and post[p + "bits_nderr"] == responses[role]["nderr"]
            assert role not in data_checked
            data_checked.add(role)
            counts["new_independent_original_load_data_errors_consumed"] += 1
        if pre["io_mmioStout_valid"] and inp["writeback_ready"]:
            assert "store" in responses and not requests["store"]["nc"] and not wb
            rob_matches(pre, "io_mmioStout_bits_robIdx_", owners["store"]["rob"])
            wb = tick
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            number = post["io_toLsqEnqCtrl_lqDeq_bits"]
            assert number and lq_head + number <= 2
            for pos in range(lq_head, lq_head + number):
                role = f"load{pos}"
                assert role in feedback and role in data_checked and role not in completed
                completed.add(role)
            lq_head += number
            counts["new_actual_original_loads_completed"] += number
        delta = (pointer(post, "io_sqDeqPtr_") - head) % 256
        assert delta <= 1 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert "store" in acks and "store" not in completed and post["io_toLsqEnqCtrl_sqDeq_bits"] == 1
            assert requests["store"]["nc"] or wb
            completed.add("store")
            counts["new_actual_original_stores_completed"] += 1
        head += delta
        assert not any(pre[f"io_sbuffer_req_{lane}_valid"] and inp["sbuffer_ready"][lane] for lane in range(2))
    assert set(loads) == {"load0", "load1"}
    if failed:
        assert len(violations) == 1 and not completed and trace[-1]["post_tick"] == violations[0]["tick"]
        difference = differences(trace[-1])
        assert not difference["before"]
        want = ({"io_uncache_req_valid"} if violations[0]["issue"] == "LSQ-BUS-OWNERSHIP-001" else
                {"io_ldExceptionInfo_bits_exceptionVec_19", "io_ldExceptionInfo_bits_exceptionVec_5"})
        assert set(difference["after"]) == want
        counts["independently_reproduced_" + violations[0]["issue"]] += 1
        counts["new_failure_retained_original_uids"] += len(owners)
    else:
        assert not violations and set(owners) == completed and not sid_live and serial is None
        assert data_checked == feedback == {"load0", "load1"}
        assert trace[-1]["after"]["io_lqEmpty"] and trace[-1]["after"]["io_sqEmpty"]
        assert set(requests) == set(acks) == set(responses) == set(owners)
        counts["new_control_cases_actually_drained"] += 1
    counts["new_allocated_original_uids"] += len(owners)
    return counts, dict(violations=violations, requests=requests, acks=acks, responses=responses,
                        allocated_original_uids=len(owners), completed_original_uids=len(completed),
                        remaining_bus_response_owners=list(sid_live.values()))


def audit(name):
    run, baseline = ROOT / "results" / name, ROOT / "results/lsq-expanded-03"
    manifest, source, nodes = verify_common(run)
    _, _, previous_nodes = verify_common(baseline)
    assert manifest["tests"] == {"PASS": 59, "FAIL": 10} and len(nodes) == 69
    previous_path = baseline / "bus-history-audit-v2.json"
    previous = json.loads(previous_path.read_text())
    assert previous["tests"] == {"PASS": 49} and sha(baseline / "evidence-auditors/audit_lsq_bus_v2.py") == previous["auditor_sha256"]
    old = {case["nodeid"]: baseline / case["journal"] for case in previous["cases"]}
    assert set(old) == set(previous_nodes)
    counts, cases, seen = Counter(), [], set()
    for path in sorted((run / "cases").rglob("lsq_wrapper.jsonl")):
        trace = rows(path)
        node = trace[0]["nodeid"]
        assert node in nodes and node not in seen and all(row["nodeid"] == node for row in trace)
        seen.add(node)
        last = None
        for index, row in enumerate(trace):
            tick = row["post_tick"]
            assert row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            assert len(row["pins"]) == 603 and row["pins"] == row["post_pins"] and len(row["before"]) == len(row["after"]) == 458
            assert not row["explicitly_unimplemented_outputs"] and not row["input"]["redirect"]["valid"]
            if not (nodes[node] and index == len(trace) - 1):
                assert row["checked"] and not any(differences(row).values())
            else:
                assert not row["checked"] and "AssertionError" in row["error"]
            last = tick
        counts["continuous_full_pin_records"] += len(trace)
        pc, _, _ = store_perf(trace)
        counts.update(pc)
        detail = {}
        if node in old:
            assert not nodes[node]
            base = rows(old[node])
            assert len(trace) == len(base)
            assert all(all(a[key] == b[key] for key in ("pre_tick", "post_tick", "input", "pins", "post_pins", "before", "after")) for a, b in zip(trace, base, strict=True))
            counts["previous_49_cases_all_raw_samples_bitwise_rechecked"] += 1
        else:
            assert node.startswith("tests/lsq_wrapper/test_bus_ownership.py::")
            if not nodes[node]:
                record_checks(trace, path)
            checked, detail = inspect_new(trace, nodes[node])
            counts.update(checked)
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), result="FAIL" if nodes[node] else "PASS", **detail))
    assert seen == set(nodes) and counts["previous_49_cases_all_raw_samples_bitwise_rechecked"] == 49
    assert counts["independently_reproduced_LSQ-BUS-OWNERSHIP-001"] == 4 and counts["independently_reproduced_LQU-SID-001"] == 6
    assert counts["new_allocated_original_uids"] == 48 and counts["new_failure_retained_original_uids"] == 24
    assert counts["new_actual_original_loads_completed"] == 20 and counts["new_actual_original_stores_completed"] == 4
    assert counts["new_control_cases_actually_drained"] == 10
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    for file in (Path(__file__), ROOT / "tools/audit_lsq_bus_v2.py"):
        copy = dest.parent / file.name
        if copy.exists():
            assert sha(copy) == sha(file)
        else:
            shutil.copy2(file, copy)
    report = dict(run=name, status="NOT_PASS_two_strict_bus_ownership_failures_independently_audited", tests=manifest["tests"],
                  counts=dict(counts), snapshot_files=len(source), previous_49_audit_sha256=sha(previous_path),
                  auditor_sha256={file: sha(dest.parent / file) for file in (Path(__file__).name, "audit_lsq_bus_v2.py")}, cases=cases,
                  limits="Original49 raw inputs/pre/post/ticks match audited v2. New20 normal public LSQ transactions: 10 controls drain24UID; 10 failures retain24UID. Ownership failure is premature visible req.valid, no third actual fire/architecture consequence claimed. SID failure observed at old exception s1 before this case's s2, not claimed as observed new s2 bytes. Store perf independent six-edge audit includes failing histories. No full Backend/elaboration/whole-LSQ acceptance; recovery/reset/complete RAW/RAR/Forward/random remain required.")
    output = run / "bus-history-audit-v3.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
