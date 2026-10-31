#!/usr/bin/env python3
"""Rebuild the write FIFO and consumption credits using only public journals."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected(queue, inp):
    consumed = min(len(queue), sum(inp["ready"]))
    capacity = 2 - len(queue) + consumed
    out = {"io_empty": int(not queue)}
    for lane in range(2):
        prefix = f"io_toSbuffer_req_{lane}_"
        out[prefix + "valid"] = int(len(queue) > lane)
        out[f"io_fromDeqModule_{lane}_ready"] = int(capacity > lane)
        out[f"io_deqPtrMove_{lane}"] = int(len(queue) > lane and inp["ready"][lane] and queue[lane]["write"]["credit"])
        if len(queue) > lane:
            for signal, field in (("addr", "paddr"), ("vaddr", "vaddr"), ("data", "data"), ("mask", "mask"), ("wline", "wline")):
                out[prefix + "bits_" + signal] = int(queue[lane]["write"][field])
    return out


def compare(actual, want):
    assert all(actual[key] == value for key, value in want.items()), {key: (actual[key], value) for key, value in want.items() if actual[key] != value}


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["pytest_exitstatus"] == 0 and manifest["tests"] == {"PASS": 26}
    cases = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert len(cases) == 26 and not any(len(case) for case in cases)
    command = json.loads((run / "command.json").read_text())["command"]
    assert "tests/enter_sbuffer" in command and "-k" not in command and not any(arg.startswith("--deselect") for arg in command)
    assert len({(case.attrib["classname"], case.attrib["name"]) for case in cases}) == 26
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            for path, digest in artifact["build"]["files"].items():
                assert sha(Path(path)) == digest
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    evidence = json.loads((run / "evidence-check.json").read_text())
    assert evidence["tests"] == manifest["tests"] and evidence["required_semantic_complete"] and evidence["required_line_complete"]
    line = json.loads((run / "line-audit.json").read_text())["native"]
    assert len(line) == 1 and line[0]["dut"] == "enter_sbuffer_queue" and line[0]["line_hit"] == line[0]["line_total"] == 78
    groups = json.loads((run / "execution/functional-coverage.json").read_text())["groups"]
    assert len(groups) == 2
    for group in groups:
        counts = group["points"][0]["counts"]
        assert group["collection_complete"] and len(counts) == 34 and all(counts.values())
    widths = {"data": 128, "mask": 16, "paddr": 48, "vaddr": 50}
    bit_coverage = {field: {"one": set(), "zero": set()} for field in widths}
    tuples, rows, credits = {}, [], Counter()
    files = sorted((run / "cases").rglob("enter_sbuffer_queue.jsonl"))
    assert len(files) == 26
    for path in files:
        journal_sha = sha(path)
        queue, sequence, done, tick = [], 0, set(), None
        counts = Counter(records=0, reset_edges=0, checked=0, accepted=0, consumed=0, reset_aborted=0,
                         sq_credits=0, accepted_without_flowthrough=0, double_consumption=0, full_stall=0,
                         simultaneous_reuse=0, blocked_output_cycles=0)
        for text in path.read_text().splitlines():
            row = json.loads(text)
            counts["records"] += 1
            assert row["pre_tick"] + 1 == row["post_tick"]
            if tick is not None:
                assert row["post_tick"] == tick + 2
            tick = row["post_tick"]
            inp, pre, post = row["input"], row["before"], row["after"]
            assert inp == row["post_input"] and "error" not in row
            assert not inp["offers"][1]["valid"] or inp["offers"][0]["valid"]
            assert not inp["ready"][1] or inp["ready"][0]
            assert inp["offers"][1]["write"]["credit"]
            change = row["change"]
            assert change["before"] == queue
            if inp["reset"]:
                counts["reset_edges"] += 1
                counts["reset_aborted"] += len(queue)
                assert not row["checked"] and change["reset"]
                queue = []
                compare(post, expected(queue, inp))
                continue
            assert row["checked"] and not change["reset"]
            counts["checked"] += 1
            want = expected(queue, inp)
            compare(pre, want)
            assert row["expected_before"] == want
            number = min(len(queue), sum(inp["ready"]))
            consumed = queue[:number]
            counts["blocked_output_cycles"] += bool(queue) and not inp["ready"][0]
            counts["double_consumption"] += number == 2
            counts["full_stall"] += len(queue) == 2 and not number
            for lane, owner in enumerate(consumed):
                assert owner["uid"] not in done
                done.add(owner["uid"])
                credit = int(owner["write"]["credit"])
                assert pre[f"io_deqPtrMove_{lane}"] == credit
                counts["consumed"] += 1
                counts["sq_credits"] += credit
                credits[str(credit)] += 1
                key = f"{owner['input_lane']}:{lane}"
                tuples.setdefault(key, {"uid": owner["uid"], "consume_tick": tick, "journal": str(path.relative_to(run)), "sha256": journal_sha})
                for field, width in widths.items():
                    value = owner["write"][field]
                    for mode, candidate in (("one", value), ("zero", value ^ ((1 << width) - 1))):
                        if candidate > 0 and candidate.bit_count() == 1:
                            bit_coverage[field][mode].add(candidate.bit_length() - 1)
            del queue[:number]
            accepted = []
            empty_before = not queue and not consumed
            for lane, offer in enumerate(inp["offers"]):
                if not offer["valid"] or not want[f"io_fromDeqModule_{lane}_ready"]:
                    continue
                for field, width in widths.items():
                    assert 0 <= offer["write"][field] < 1 << width
                sequence += 1
                owner = {"uid": sequence, "input_lane": lane, "write": offer["write"]}
                queue.append(owner)
                accepted.append(owner)
                counts["accepted"] += 1
            assert len(queue) <= 2
            counts["accepted_without_flowthrough"] += bool(accepted) and empty_before
            counts["simultaneous_reuse"] += bool(accepted and consumed)
            assert change["accepted"] == accepted and change["consumed"] == consumed
            want = expected(queue, inp)
            compare(post, want)
            assert row["expected_after"] == want
        assert not queue and counts["accepted"] == counts["consumed"] + counts["reset_aborted"]
        rows.append({"journal": str(path.relative_to(run)), "sha256": journal_sha, **dict(counts)})
    for field, width in widths.items():
        assert all(bits == set(range(width)) for bits in bit_coverage[field].values())
    assert set(tuples) == {f"{a}:{b}" for a in range(2) for b in range(2)} and set(credits) == {"0", "1"}
    auditors = {}
    for tool in (Path(__file__),):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool)
        else:
            shutil.copy2(tool, dest)
        auditors[str(dest.relative_to(run))] = sha(dest)
    report = {"run": name, "status": "verified_public_fifo_history", "tests": manifest["tests"], "scope": 'independent ordered accepted-request ledger, no lsqverify imports or internal register oracle',
              "manifest_sha256": sha(run / "execution/manifest.json"), "evidence_check_sha256": sha(run / "evidence-check.json"),
              "snapshot_files": len(source), "totals": {key: sum(row[key] for row in rows) for key in counts},
              "consumed_credit_values": dict(credits), "input_to_output_lane_witnesses": tuples,
              "completed_walking_bits": {field: {mode: sorted(bits) for mode, bits in values.items()} for field, values in bit_coverage.items()},
              "auditors": auditors, "cases": rows}
    out = run / "trace-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "completed_walking_bits")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
