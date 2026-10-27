#!/usr/bin/env python3
"""Recheck public-pin journals and input-history timing, not DUT internal state."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_outputs(actual, expected):
    for key in ("head", "empty", "dequeue_valid", "recovery_valid", "recovery_stall"):
        assert actual[key] == expected[key], (key, actual, expected)
    if expected["dequeue_valid"]:
        assert actual["dequeue_count"] == expected["dequeue_count"]
    if expected["recovery_valid"]:
        assert actual["recovery_ptr"] == expected["recovery_ptr"]


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["pytest_exitstatus"] == 0
    files = sorted((run / "cases").rglob("virtual_load_queue.jsonl"))
    assert len(files) == manifest["tests"]["PASS"], "this audit expects a VLQ-only successful run"
    rows = []
    for path in files:
        counters = dict(records=0, checked=0, reset_edges=0, dispatch_flows=0, writebacks=0,
                        redirect_inputs=0, recovery_responses=0, dequeue_reports=0, released_flows=0)
        history = deque((False, False))
        last_tick, reset_length, previous_head = None, 0, None
        for line in path.read_text().splitlines():
            record = json.loads(line)
            assert "error" not in record
            assert record["pre_tick"] + 1 == record["post_tick"]
            if last_tick is not None:
                assert record["post_tick"] == last_tick + 2, "a globally observed cycle was omitted"
            last_tick = record["post_tick"]
            counters["records"] += 1
            inp = record["before"]["inputs"]
            before, after = record["before"]["outputs"], record["after"]["outputs"]
            if inp["reset"]:
                counters["reset_edges"] += 1
                reset_length += 1
                assert not record["checked"]
                history = deque((False, False))
                previous_head = None
                continue
            if reset_length:
                assert reset_length >= 6, "reset shorter than the declared unit contract"
                reset_length = 0
            assert record["checked"]
            check_outputs(before, record["expected_before"])
            check_outputs(after, record["expected_after"])
            counters["checked"] += 1
            for output in (before, after):
                assert 0 <= output["head"]["value"] < 120
            if previous_head is not None:
                assert before["head"] == previous_head
            previous_head = after["head"]
            old = int(before["head"]["flag"]) * 120 + before["head"]["value"]
            new = int(after["head"]["flag"]) * 120 + after["head"]["value"]
            count = after["dequeue_count"] if after["dequeue_valid"] else 0
            assert 0 <= count <= 8 and (not after["dequeue_valid"] or count > 0)
            assert (new - old) % 240 == count, "public release count/head conservation failed"
            # Independent of the ledger's stored recovery objects: compare the
            # actual input history against real valid/stall output timing.
            due = history.popleft()
            assert after["recovery_valid"] == due
            assert after["recovery_stall"] == (inp["redirect"]["valid"] or due or any(history))
            history.append(inp["redirect"]["valid"])
            counters["dispatch_flows"] += sum(d["flows"] for d in inp["dispatch"] if d["valid"])
            counters["writebacks"] += sum(w["valid"] for w in inp["writebacks"])
            counters["redirect_inputs"] += inp["redirect"]["valid"]
            counters["recovery_responses"] += after["recovery_valid"]
            counters["dequeue_reports"] += after["dequeue_valid"]
            counters["released_flows"] += count
        assert counters["checked"] > 0
        rows.append({"journal": str(path.relative_to(run)), "sha256": sha(path), **counters})
    auditor = run / "evidence-auditors" / Path(__file__).name
    auditor.parent.mkdir(parents=True, exist_ok=True)
    if auditor.exists():
        assert sha(auditor) == sha(Path(__file__)), "refusing to overwrite a historical trace auditor"
    else:
        shutil.copy2(__file__, auditor)
    report = {"run": name, "status": "verified", "tests": len(rows), "auditor_sha256": sha(auditor),
              "scope": "complete_public_pin_journals_output_comparisons_head_count_conservation_and_redirect_input_history",
              "totals": {key: sum(row[key] for row in rows) for key in counters}, "cases": rows}
    output = run / "trace-audit.json"
    if output.exists():
        assert json.loads(output.read_text()) == report, "refusing to overwrite a different historical trace audit"
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
    print("per-case evidence:", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
