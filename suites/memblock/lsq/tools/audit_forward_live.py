#!/usr/bin/env python3
"""Supplemental S2 pre-edge live-input audit, without model/internal imports.

The complete staged audit checks both phases, but its live_bank_observations
counter counted post-edge only. These directed live changes happen pre-edge;
preserve that report and provide explicit public-input witnesses separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(name):
    run = ROOT / "results" / name
    trace = json.loads((run / "trace-audit.json").read_text())
    assert trace["required_semantic_obligations"] and trace["tests"] == {"PASS": 165, "FAIL": 19}
    witnesses = []
    for case in trace["cases"]:
        nodeid = case["nodeid"]
        mdp = "test_s2_mdp_uses_current_address_ready_not_old_snapshot" in nodeid
        reuse = "test_retirement_reuse_keeps_s1_data_but_s2_physical_cam_is_live" in nodeid
        if not (mdp or reuse):
            continue
        assert not case["has_error"]
        path = run / case["journal"]
        assert sha(path) == case["sha256"]
        records = [json.loads(line) for line in path.read_text().splitlines()]
        found = []
        for prior, row in zip(records, records[1:]):
            lane = int(nodeid.rsplit("[", 1)[1][:-1])
            prefix = f"io_query_{lane}_s2Resp_"
            before, previous = row["before"], prior["after"]
            if not before[prefix + "valid"] or prior["input"]["stores"] == row["input"]["stores"]:
                continue
            assert previous[prefix + "valid"] and row["checked"] and prior["checked"]
            if mdp:
                assert not prior["input"]["stores"][1]["address_ready"] and row["input"]["stores"][1]["address_ready"]
                assert previous[prefix + "bits_addrInvalid_valid"] == 1 and before[prefix + "bits_addrInvalid_valid"] == 0
                assert prior["input"]["dequeue"] == row["input"]["dequeue"] and prior["input"]["upper"] == row["input"]["upper"]
                kind = "S2-live-MDP-ready"
            else:
                old, new = prior["input"]["stores"][63], row["input"]["stores"][63]
                assert old["data"] == 0xAAAAAAAAAAAAAAAA and new["data"] == 0xBBBBBBBBBBBBBBBB
                assert old["page"] != new["page"] and old["vaddr"] != new["vaddr"]
                assert previous[prefix + "bits_matchInvalid"] == 0 and before[prefix + "bits_matchInvalid"] == 1
                assert sum(before[prefix + f"bits_forwardMask_{i}"] << i for i in range(16)) == 0xFF
                assert sum(before[prefix + f"bits_forwardData_{i}"] << (8 * i) for i in range(8)) == old["data"]
                assert prior["input"]["dequeue"]["value"] == 63 and row["input"]["dequeue"]["value"] == 0
                assert row["input"]["dequeue"]["second"] and not row["input"]["upper"]["second"] and row["input"]["upper"]["first"]
                later = [answer for other in records if other["post_tick"] > row["post_tick"] for answer in other["change"]["responses"]]
                assert len(later) == 1 and later[0]["source"]["data"] == new["data"] and later[0]["uid"] > prior["change"]["responses"][0]["uid"]
                kind = "S1-data-snapshot-S2-live-PA-and-boundary-new-UID"
            found.append({"nodeid": nodeid, "lane": lane, "kind": kind, "pre_tick": row["pre_tick"], "previous_post_tick": prior["post_tick"],
                          "journal": case["journal"], "sha256": case["sha256"]})
        assert len(found) == 1
        witnesses.extend(found)
    assert len(witnesses) == 6
    end = json.loads((run / "end-source-check.json").read_text())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert end["all_current_launch_files_match_snapshot"] and end["files"] == source and end["verification_snapshot_files"] == len(source)
    dest = run / "evidence-auditors" / Path(__file__).name
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = {"run": name, "status": "six_pre_edge_live_boundaries_verified", "dut_acceptance": "NOT_PASS",
              "note": "trace-audit.live_bank_observations=0 is a post-edge-only count, not absence of pre-edge live checking; original audit preserved unchanged",
              "trace_audit_sha256": sha(run / "trace-audit.json"), "end_source_check_sha256": sha(run / "end-source-check.json"),
              "auditor_sha256": sha(dest), "pre_edge_live_witnesses": witnesses}
    out = run / "live-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        with out.open("x") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
