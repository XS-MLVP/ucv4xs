#!/usr/bin/env python3
"""Independent SQ/page FIFO and same-slot recovery reuse audit; no model imports."""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def serial(ptr):
    assert 0 <= ptr["value"] < 64
    return int(ptr["first"]) * 128 + int(ptr["second"]) * 64 + ptr["value"]


def cancel(owner, redirect):
    if not redirect["valid"]:
        return False
    delta = (serial(owner["request"]["sq"]) - serial(redirect["sq"])) % 256
    assert delta != 128
    return delta < 128


def expected(owners, inp):
    out = {"io_toDeqModule_valid": int(bool(owners))}
    for lane, req in enumerate(inp["requests"]):
        out[f"io_fromStaS1_{lane}_ready"] = int(len(owners) < 2 and not inp["redirect"]["valid"] and req["sq"] == inp["address_ready"])
    def packet(prefix, owner):
        req = owner["request"]
        out.update({prefix + "paddr": req["paddr"] // 4096 * 4096, prefix + "sqIdx_first_flag": int(req["sq"]["first"]),
                    prefix + "sqIdx_second_flag": int(req["sq"]["second"]), prefix + "sqIdx_value": req["sq"]["value"]})
    if owners:
        packet("io_toDeqModule_bits_", owners[0])
    for slot in range(2):
        owner = next((item for item in owners if item["slot"] == slot), None)
        out[f"io_forwardValid_{slot}"] = int(owner is not None)
        if owner:
            packet(f"io_forwardEntries_{slot}_", owner)
    return out


def compare(actual, want):
    assert all(actual[key] == value for key, value in want.items()), {key: (actual[key], value) for key, value in want.items() if actual[key] != value}


def frozen_tests(snapshot):
    result = Counter()
    for path in (snapshot / "tests/unalign").glob("*.py"):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            count = 1
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute) or decorator.func.attr != "parametrize":
                    continue
                count *= len(ast.literal_eval(decorator.args[1]))
            result[f"tests/unalign/{path.name}::{node.name}"] = count
    return result


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"] and manifest["pytest_exitstatus"] == 0
    cases = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert not any(len(case) for case in cases)
    actual = Counter((case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]).split("[", 1)[0] for case in cases)
    assert actual == frozen_tests(run / "verification-source") and manifest["tests"] == {"PASS": sum(actual.values())}
    command = json.loads((run / "command.json").read_text())["command"]
    assert "tests/unalign" in command and "-k" not in command and not any(arg.startswith("--deselect") for arg in command)
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            for path, digest in artifact["build"]["files"].items():
                assert sha(Path(path)) == digest
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    verification = json.loads((run / "evidence-check.json").read_text())
    assert verification["tests"] == manifest["tests"] and verification["required_line_complete"] and verification["required_semantic_complete"]
    native = json.loads((run / "line-audit.json").read_text())["native"]
    assert len(native) == 1 and native[0]["dut"] == "unalign_queue" and native[0]["line_hit"] == native[0]["line_total"] == 44
    groups = json.loads((run / "execution/functional-coverage.json").read_text())["groups"]
    assert len(groups) == 2 and all(group["collection_complete"] and len(group["points"][0]["counts"]) == 40 and all(group["points"][0]["counts"].values()) for group in groups)
    files = sorted((run / "cases").rglob("unalign_queue.jsonl"))
    assert len(files) == len(cases)
    rows, witnesses, reuse_witnesses, one_bits, zero_bits, sq_completed = [], {}, [], set(), set(), set()
    for path in files:
        journal_sha = sha(path)
        owners, tail, sequence, tick = [], 0, 0, None
        completed, reuse = {}, []
        counts = Counter(records=0, reset_edges=0, checked=0, allocations=0, consumed=0, canceled=0, reset_aborted=0,
                         full_stalls=0, full_pop_no_accept=0, simultaneous_pop_allocate=0, redirect_edges=0,
                         consume_survivor_cancel_tail=0, matched_inputs_blocked_by_redirect=0)
        for line in path.read_text().splitlines():
            row = json.loads(line)
            counts["records"] += 1
            assert row["pre_tick"] + 1 == row["post_tick"]
            if tick is not None:
                assert row["post_tick"] == tick + 2
            tick = row["post_tick"]
            inp, pre, post = row["input"], row["before"], row["after"]
            assert inp == row["post_input"] and "error" not in row
            change = row["change"]
            assert change["before"] == owners
            if inp["reset"]:
                counts["reset_edges"] += 1
                counts["reset_aborted"] += len(owners)
                owners, tail, reuse = [], 0, []
                assert not row["checked"] and change["reset"]
                compare(post, expected(owners, inp))
                continue
            counts["checked"] += 1
            assert row["checked"] and not change["reset"]
            want = expected(owners, inp)
            assert row["expected_before"] == want
            compare(pre, want)
            before_count = len(owners)
            consumed = owners[:1] if owners and inp["ready"] else []
            removed = [owner for owner in owners if cancel(owner, inp["redirect"])]
            assert not any(owner in removed for owner in consumed)
            positions = [i for i, owner in enumerate(owners) if owner in removed]
            assert not positions or positions == list(range(positions[0], len(owners)))
            counts["full_stalls"] += before_count == 2 and not consumed
            counts["full_pop_no_accept"] += before_count == 2 and bool(consumed)
            counts["redirect_edges"] += inp["redirect"]["valid"]
            counts["consume_survivor_cancel_tail"] += bool(consumed and removed)
            counts["matched_inputs_blocked_by_redirect"] += sum(req["valid"] and req["sq"] == inp["address_ready"] and inp["redirect"]["valid"] for req in inp["requests"])
            for owner in consumed:
                assert owner["uid"] not in completed
                completed[owner["uid"]] = (owner["slot"], tick)
                req = owner["request"]
                sq_completed.add(serial(req["sq"]))
                page = req["paddr"] // 4096
                for bits, candidate in ((one_bits, page), (zero_bits, page ^ ((1 << 36) - 1))):
                    if candidate > 0 and candidate.bit_count() == 1:
                        bits.add(candidate.bit_length() - 1)
                key = f"{owner['input_lane']}:{owner['slot']}"
                witnesses.setdefault(key, {"uid": owner["uid"], "tick": tick, "journal": str(path.relative_to(run)), "sha256": journal_sha})
            for owner in removed:
                reuse.append((owner["uid"], owner["slot"], sequence, tick))
            counts["consumed"] += len(consumed)
            counts["canceled"] += len(removed)
            owners = [owner for owner in owners if owner not in consumed and owner not in removed]
            tail -= len(removed)
            accepted = []
            for lane, req in enumerate(inp["requests"]):
                if not req["valid"] or not want[f"io_fromStaS1_{lane}_ready"]:
                    continue
                assert not accepted and 0 <= req["paddr"] < 1 << 48
                if owners:
                    assert 0 < (serial(req["sq"]) - serial(owners[-1]["request"]["sq"])) % 256 < 128
                sequence += 1
                owner = {"uid": sequence, "slot": tail % 2, "input_lane": lane, "request": req}
                assert all(item["slot"] != owner["slot"] for item in owners)
                owners.append(owner)
                accepted.append(owner)
                tail += 1
            counts["allocations"] += len(accepted)
            counts["simultaneous_pop_allocate"] += bool(consumed and accepted)
            assert len(owners) <= 2
            assert change["accepted"] == accepted and change["consumed"] == consumed and change["canceled"] == removed
            want = expected(owners, inp)
            assert row["expected_after"] == want
            compare(post, want)
        assert not owners and counts["allocations"] == counts["consumed"] + counts["canceled"] + counts["reset_aborted"]
        for old_uid, slot, since, cancel_tick in reuse:
            new_uid = next((uid for uid, (new_slot, _) in completed.items() if uid > since and slot == new_slot), None)
            assert new_uid is not None, "a canceled slot lacks later actual new-UID completion"
            reuse_witnesses.append({"journal": str(path.relative_to(run)), "sha256": journal_sha, "old_uid": old_uid, "slot": slot,
                                    "cancel_tick": cancel_tick, "new_uid": new_uid, "consume_tick": completed[new_uid][1]})
        rows.append({"journal": str(path.relative_to(run)), "sha256": journal_sha, **dict(counts)})
    assert one_bits == zero_bits == set(range(36)) and sq_completed == set(range(256))
    assert set(witnesses) == {f"{lane}:{slot}" for lane in range(2) for slot in range(2)}
    dest = run / "evidence-auditors" / Path(__file__).name
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = {"run": name, "status": "verified_public_sq_page_history", "scope": "independent public ordered requests, SQ age, page extraction, forward visibility and same-slot canceled-UID reuse; no model imports or internal oracle",
              "tests": manifest["tests"], "snapshot_files": len(source), "manifest_sha256": sha(run / "execution/manifest.json"),
              "evidence_check_sha256": sha(run / "evidence-check.json"), "auditor_sha256": sha(dest),
              "totals": {key: sum(row[key] for row in rows) for key in counts}, "completed_sq_encodings": sorted(sq_completed),
              "page_walking_one_bits": sorted(one_bits), "page_walking_zero_bits": sorted(zero_bits), "lane_slot_witnesses": witnesses,
              "cancel_reuse_witnesses": reuse_witnesses, "cases": rows}
    out = run / "trace-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "cancel_reuse_witnesses", "completed_sq_encodings", "page_walking_one_bits", "page_walking_zero_bits")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
