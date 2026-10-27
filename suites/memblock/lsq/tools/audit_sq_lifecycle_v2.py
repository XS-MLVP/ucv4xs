#!/usr/bin/env python3
"""Strengthen cancellation coverage: EVERY canceled UID needs same-slot reuse.

Keep v1 and its historical 7/10 evidence unchanged; this gate additionally
binds the canceled UQ owner to a new second page in the very same SQ slot.
"""
import argparse
import json
from pathlib import Path
import shutil

from audit_sq_lifecycle import audit, ROOT, rows, sha


def main(name):
    assert name != "sq-expanded-02", "historical weak binding is not rewritten"
    audit(name)
    run = ROOT / "results" / name
    report = json.loads((run / "lifecycle-audit.json").read_text())
    counts = report["counts"]
    assert counts["actor_cancel_same_slot_reuse"] == counts["actor_cancelled_flow_uids"] == 10
    assert counts["actor_reset_same_slot_reuse"] == counts["actor_reset_aborted_flow_uids"] == 4
    bindings = []
    for case in report["cases"]:
        path = run / case["journal"]
        events = rows(path.with_name("sq_actor.jsonl"))
        if not events:
            continue
        cancelled = {uid for event in events if event["event"] == "cancel" for uid in event["cancelled"]}
        reused = {item["old_uid"] for item in case["same_slot_reuse"] if item["kind"] == "cancel"}
        assert cancelled == reused
        owners = {owner["uid"]: owner for event in events if event["event"] == "allocate" for owner in event["owners"]}
        for item in case["same_slot_reuse"]:
            old, new = owners[item["old_uid"]], owners[item["new_uid"]]
            assert old["position"] % 64 == new["position"] % 64 == item["slot"] and old["uid"] != new["uid"]
            if old["second_page"] is not None:
                assert new["second_page"] is not None and old["second_page"] != new["second_page"]
                trace = rows(path)
                accepts = [row["post_tick"] for row in trace for lane in range(2) if row["input"][f"io_fromStoreUnit_unalignQueueReq_{lane}_valid"] and
                           row["before"][f"io_fromStoreUnit_unalignQueueReq_{lane}_ready"] and row["input"][f"io_fromStoreUnit_unalignQueueReq_{lane}_bits_paddr"] == new["second_page"]]
                assert accepts and max(accepts) < item["tick"]
                bindings.append({"nodeid": case["nodeid"], **item, "new_page_actual_uq_accept_ticks": accepts})
    assert len(bindings) == 1
    auditor = run / "evidence-auditors" / Path(__file__).name
    if auditor.exists():
        assert sha(auditor) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), auditor)
    result = {"run": name, "status": "all_cancelled_and_reset_UIDs_have_actual_same_slot_new_completion", "dut_acceptance": "NOT_PASS",
              "cancel_bindings": 10, "reset_bindings": 4, "same_slot_new_page_bindings": bindings, "lifecycle_audit_sha256": sha(run / "lifecycle-audit.json"), "auditor_sha256": sha(auditor)}
    output = run / "reuse-audit-v2.json"
    if output.exists():
        assert json.loads(output.read_text()) == result
    else:
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    main(parser.parse_args().name)
