#!/usr/bin/env python3
"""Raw shared-bus lifecycles plus bitwise reuse of audited initial histories.

This audit deliberately does not accept mixed two-candidate bus competition,
cancel/reset, SID reuse, capacity or random scopes it has not implemented.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT, sha, verify_common


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert not any(nodes.values()) and all(node.startswith("tests/lsq_wrapper/") for node in nodes)
    old = ROOT / "results/lsq-initial-01"
    _, _, original_nodes = verify_common(old)
    previous_path = old / "mixed-history-audit-v2.json"
    previous = json.loads(previous_path.read_text())
    assert previous["tests"] == {"PASS": 22} and previous["counts"]["actual_load_uid_completed"] == 22
    for file, digest in previous["auditor_sha256"].items():
        assert sha(old / "evidence-auditors" / file) == digest
    original = {case["nodeid"]: old / case["journal"] for case in previous["cases"]}
    counts, cases, seen = Counter(), [], set()
    for path in sorted((run / "cases").rglob("lsq_wrapper.jsonl")):
        trace = rows(path)
        node = trace[0]["nodeid"]
        assert node in nodes and node not in seen
        seen.add(node)
        if node in original:
            base = rows(original[node])
            assert len(trace) == len(base)
            for a, b in zip(trace, base, strict=True):
                assert all(a[key] == b[key] for key in ("pre_tick", "post_tick", "input", "pins", "post_pins", "before", "after")), node
            counts["previously_audited_initial_cases_bitwise_rechecked"] += 1
            counts["initial_records_bitwise_rechecked"] += len(trace)
            cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), baseline_sha256=sha(original[node]),
                              scope="all_public_inputs_pre_post_and_ticks_match_independently_audited_initial_case"))
            continue
        assert node.startswith("tests/lsq_wrapper/test_bus.py::"), node
        owner = original_load = store = data = request = ack = response = replay = s3 = bypass = wb = deq = None
        last, checked_data, at_tick = None, 0, {}
        for row in trace:
            inp, pins, pre, post, tick = row["input"], row["pins"], row["before"], row["after"], row["post_tick"]
            assert row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick) and row["nodeid"] == node
            assert pins == row["post_pins"] and len(pins) == 603 and len(pre) == len(post) == 458 and row["checked"]
            for phase in ("before", "after"):
                assert all(not ((row[phase][key] ^ value) & row["masks_" + phase].get(key, -1)) for key, value in row["expected_" + phase].items())
            assert not inp["redirect"]["valid"]
            last, at_tick[tick] = tick, row
            counts["new_bus_continuous_records"] += 1
            if inp["reset"]:
                assert owner is None
                continue
            for dispatch in inp["dispatch"]:
                if dispatch["valid"]:
                    assert owner is None and dispatch["flows"] == 1 and dispatch["need_alloc"] in (1, 2)
                    owner = dispatch
                    to_load = owner["need_alloc"] == 1
            for address in inp["addresses"]:
                if address["valid"]:
                    assert not to_load and store is None and address["slot"] == 0 and address["rob"] == owner["rob"]
                    store = address
            for value in inp["data"]:
                if value["valid"]:
                    assert not to_load and data is None and value["sq"]["value"] == 0
                    data = value
            for packet in inp["loads"]:
                q = packet["execution"]
                if not q["valid"]:
                    continue
                assert to_load and q["uop"]["rob"] == owner["rob"] and q["uop"]["lq"]["value"] == 0
                if original_load is None:
                    assert q["causes"] == 1 and q["need_replay"] and not q["replay_feedback"]
                    original_load = packet
                else:
                    assert replay is not None and q["replay_feedback"] and q["slot"] == replay["slot"] and not q["need_replay"]
                    assert checked_data == 1 and s3 is None
                    s3 = tick
            if pre["io_uncache_req_valid"] and inp["bus"]["ready"]:
                assert owner is not None and request is None
                expected_pa = original_load["paddr"] if to_load else store["paddr"]
                expected_va = original_load["execution"]["vaddr"] if to_load else store["vaddr"]
                assert pre["io_uncache_req_bits_cmd"] == int(not to_load) and pre["io_uncache_req_bits_addr"] == expected_pa
                assert pre["io_uncache_req_bits_vaddr"] == expected_va and pre["io_uncache_req_bits_mask"] == 255
                for port, field in (("flag", "flag"), ("value", "value"), ("isFormer", "former")):
                    assert pre["io_uncache_req_bits_robIdx_" + port] == int(owner["rob"][field])
                if not to_load:
                    assert pre["io_uncache_req_bits_data"] == data["data"] % (1 << 64)
                request = dict(tick=tick, mid=pre["io_uncache_req_bits_id"], nc=bool(pre["io_uncache_req_bits_nc"]))
                counts["actual_original_load_bus_requests" if to_load else "actual_original_store_bus_requests"] += 1
            bus = inp["bus"]
            if bus["ack"]:
                assert request is not None and ack is None and bool(bus["ack_to_load"]) == to_load and bus["mid"] == request["mid"]
                assert pins["io_uncache_idResp_bits_is2lq"] == int(to_load)
                ack = dict(tick=tick, sid=bus["sid"])
                counts["actual_direction_correct_acks"] += 1
            if bus["response"]:
                assert ack is not None and response is None and bool(bus["response_to_load"]) == to_load and bus["response_id"] == ack["sid"]
                assert pins["io_uncache_resp_bits_is2lq"] == int(to_load)
                response = dict(tick=tick, data=bus["data"], error=int(bus["error"]), nderr=int(bus["nderr"]))
                counts["actual_direction_correct_responses"] += 1
            for bank in range(3):
                p = f"io_replay_{bank}_"
                if pre[p + "valid"] and inp["replay_ready"][bank]:
                    assert to_load and response is not None and replay is None and pre[p + "bits_vaddr"] == original_load["execution"]["vaddr"]
                    assert pre[p + "bits_uop_robIdx_value"] == owner["rob"]["value"] and pre[p + "bits_uop_lqIdx_value"] == 0
                    replay = dict(tick=tick, slot=pre[p + "bits_replayQueueIdx"])
                    assert replay["slot"] % 3 == bank
                    counts["actual_load_replay_after_real_shared_response"] += 1
            for lane, query in enumerate(inp["bypass"]):
                if not query["valid"]:
                    continue
                assert to_load and replay is not None and response is not None and bypass is None and query["lq"]["value"] == 0
                p = f"io_bypass_{lane}_"
                assert post[p + "s1Resp_valid"] and post[p + "s1Resp_bits_paddr"] == original_load["paddr"]
                assert post["io_ldExceptionInfo_valid"] and post["io_ldExceptionInfo_bits_vaddr"] == original_load["fullva"]
                assert post["io_ldExceptionInfo_bits_exceptionVec_19"] == response["error"]
                assert post["io_ldExceptionInfo_bits_exceptionVec_5"] == response["nderr"]
                bypass = dict(tick=tick, lane=lane)
            if bypass is not None and bypass["tick"] + 2 == tick:
                p = f"io_bypass_{bypass['lane']}_s2Resp_"
                assert post[p + "valid"] and post[p + "bits_data"] == response["data"] * ((1 << 64) + 1)
                assert post[p + "bits_derr"] == response["error"] and post[p + "bits_nderr"] == response["nderr"]
                checked_data += 1
                counts["independent_original_load_bytes_and_errors"] += 1
            if pre["io_mmioStout_valid"] and inp["writeback_ready"]:
                assert not to_load and response is not None and not request["nc"] and wb is None
                assert pre["io_mmioStout_bits_robIdx_value"] == owner["rob"]["value"]
                wb = tick
                counts["actual_original_io_writebacks"] += 1
            assert not any(pre[f"io_sbuffer_req_{lane}_valid"] and inp["sbuffer_ready"][lane] for lane in range(2))
            for kind in ("lq", "sq"):
                p = "io_toLsqEnqCtrl_" + kind + "Deq_"
                if not post[p + "valid"]:
                    continue
                assert post[p + "bits"] == 1 and deq is None and (kind == "lq") == to_load
                if to_load:
                    assert s3 is not None and s3 + 4 <= tick and checked_data == 1
                elif request["nc"]:
                    assert ack is not None and ack["tick"] < tick
                else:
                    assert wb is not None and wb < tick
                deq = tick
                counts["actual_load_owner_completed" if to_load else "actual_store_owner_completed"] += 1
        assert request is not None and ack is not None and response is not None and deq is not None
        assert (to_load and checked_data == 1) or (not to_load and checked_data == 0)
        assert trace[-1]["after"]["io_lqEmpty"] and trace[-1]["after"]["io_sqEmpty"]
        assert not trace[-1]["after"]["io_uncache_req_valid"] and not trace[-1]["after"]["io_replayAllocate"]
        for check in rows(path.with_name("lsq_checks.jsonl")):
            actual = at_tick[check["tick"]][check["phase"]]
            assert check["passed"] and check["actual"] == {key: actual[key] for key in check["expected"]}
            assert all(not ((actual[key] ^ value) & check["masks"].get(key, -1)) for key, value in check["expected"].items())
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), kind="load" if to_load else "store",
                          nc=request["nc"], request=request, ack=ack, response=response, deq_tick=deq))
    assert seen == set(nodes) and original_nodes.keys() <= seen and counts["previously_audited_initial_cases_bitwise_rechecked"] == 22
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="real_one_sided_shared_bus_and_original_initial_histories_audited_not_complete_wrapper", tests=manifest["tests"],
                  counts=dict(counts), previous_initial_audit_sha256=sha(previous_path), snapshot_files=len(source),
                  auditor_sha256=sha(dest), manifest_sha256=sha(run / "execution/manifest.json"), cases=cases,
                  limits="Original22 actual input/pre/post/ticks match audited baseline bitwise. New one-sided shared Load/Store requests, direction ack/response, Load data/errors/Replays/S3 and Store ack/WB/deq independently rebuilt. No two-candidate arbitration, concurrent NC, SID reuse, full pool, recovery/reset, full forward or random acceptance; Store perf12 unimplemented.")
    output = run / "bus-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
