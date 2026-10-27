#!/usr/bin/env python3
"""Reconstruct entry protocol event histories from public pins, not model phases."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def after(left, right):
    a = 2 * (int(left["flag"]) * 160 + left["value"]) + (not left["former"])
    b = 2 * (int(right["flag"]) * 160 + right["value"]) + (not right["former"])
    assert 0 <= left["value"] < 160 and 0 <= right["value"] < 160
    age = (a - b) % 640
    assert age != 320
    return 0 < age < 320


def cancellation(owner, inp):
    red = inp["redirect"]
    return owner is not None and red["valid"] and (after(owner["q"]["rob"], red["rob"])
                                                    or red["flush_self"] and owner["q"]["rob"] == red["rob"])


def make_report(owner):
    q, response = owner["q"], owner["response"]
    assert response is not None
    return {"valid": True, "rob": q["rob"], "fullva": q["fullva"], "gpaddr": q["gpaddr"], "hyper": q["hyper"],
            "nonleaf": q["nonleaf"], "exceptions": q["exceptions"] + (int(response["nderr"]) << 5) + (int(response["error"]) << 19)}


def check(actual, inp, owner, report, entry_id):
    cancel = cancellation(owner, inp)
    announced = owner is not None and owner["announced"] is not None
    issued = owner is not None and owner["issued"] is not None
    returned = owner is not None and owner["response"] is not None
    woke = owner is not None and owner["woke"] is not None
    q = owner["q"] if owner else None
    assert actual["mmio_select"] == bool(announced and q["mmio"])
    assert actual["slave_valid"] == (owner is not None and owner["sid"] is not None)
    if actual["slave_valid"]:
        assert actual["slave_id"] == owner["sid"]
    bus = actual["bus"]
    assert bus["valid"] == bool(announced and not issued and not cancel)
    if bus["valid"]:
        byte_mask = (q["mask"] // (256 if q["paddr"] % 16 >= 8 else 1)) % 256
        assert bus == {"valid": True, "rob": q["rob"], "paddr": q["paddr"], "vaddr": q["vaddr"],
                       "mask": byte_mask, "nc": q["nc"], "memory_backed": q["memory_backed"]}
    for kind in ("mmio", "nc"):
        wake = actual[kind + "_wakeup"]
        assert wake["valid"] == bool(returned and not woke and not owner["deferred"] and q[kind])
        if wake["valid"]:
            assert wake["lq"] == q["lq"]
        output = actual[kind]
        assert output["valid"] == bool(woke and (kind == "nc") == q["nc"])
        if output["valid"]:
            response = owner["response"]
            assert output == {"valid": True, "lq": q["lq"], "paddr": q["paddr"], "data": response["data"],
                              "error": response["error"], "nderr": response["nderr"]}
    consume = bool(woke and (inp["nc_ready"] if q["nc"] else inp["mmio_ready"]))
    flush = False
    if owner:
        if not issued:
            flush = cancel
        elif not returned:
            flush = inp["response"]["valid"] and (cancel or owner["deferred"])
        elif not woke:
            flush = cancel or owner["deferred"]
        else:
            flush = cancel or consume
    assert actual["flush"] == bool(flush)
    assert actual["exception"]["valid"] == (report is not None)
    if report:
        assert actual["exception"] == report
    return bool(flush), consume


def audit(name):
    run = ROOT / "results" / name
    manifest_path = run / "execution/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    gate = json.loads((run / "evidence-check.json").read_text())
    assert manifest["state"] == "committed" and manifest["pytest_exitstatus"] == 0
    assert gate["status"] == "verified" and gate["required_line_complete"] and gate["required_semantic_complete"]
    assert gate["manifest_sha256"] == sha(manifest_path) and gate["builds"] == 16 and gate["functional_groups"] == 32
    files = sorted((run / "cases").rglob("uncache_entry_*.jsonl"))
    assert len(files) == manifest["tests"]["PASS"] == 384
    rows, cases_by_id = [], Counter()
    positive_sids, negative_mids = defaultdict(set), defaultdict(set)
    data_bits, masks, errors = defaultdict(set), defaultdict(set), defaultdict(set)
    for path in files:
        entry_id = int(path.stem.rsplit("_", 1)[1])
        assert 0 <= entry_id < 16
        cases_by_id[entry_id] += 1
        counters = Counter(records=0, checked=0, reset_edges=0, allocations=0, bus_accepts=0, id_accepts=0, wrong_mid_inputs=0,
                           responses=0, wakeups=0, consumptions=0, canceled_releases=0, reset_canceled_owners=0,
                           exception_reports=0, deferred_cancel_edges=0)
        owner, report = None, None
        pending = {"flag": False, "value": 0, "former": True}
        sequence = reset_length = 0
        last_tick = None
        for line in path.read_text().splitlines():
            row = json.loads(line)
            assert "error" not in row
            counters["records"] += 1
            edge = counters["records"]
            assert row["pre_tick"] + 1 == row["post_tick"]
            if last_tick is not None:
                assert row["post_tick"] == last_tick + 2, "a globally observed edge was omitted"
            last_tick = row["post_tick"]
            inp, before, actual_after = row["input"], row["before"], row["after"]
            assert inp == row["post_input"]
            if inp["reset"]:
                assert not row["checked"]
                counters["reset_edges"] += 1
                counters["reset_canceled_owners"] += owner is not None
                owner, report = None, None
                pending = {"flag": False, "value": 0, "former": True}
                reset_length += 1
                continue
            if reset_length:
                assert reset_length >= 6
                reset_length = 0
            assert row["checked"]
            counters["checked"] += 1
            flush, consume = check(before, inp, owner, report, entry_id)
            cancel = cancellation(owner, inp)
            next_report = make_report(owner) if consume else None
            request_fire = before["bus"]["valid"] and inp["bus_ready"]
            ack = owner is not None and inp["id_response"]["valid"] and inp["id_response"]["mid"] == entry_id
            mmio_ready = True if entry_id == 0 else inp["mmio_wake_ready"]
            nc_ready = True if entry_id == 0 else inp["nc_wake_ready"]
            if entry_id == 0:
                assert inp["mmio_wake_ready"] and inp["nc_wake_ready"]
            wake = before["mmio_wakeup"]["valid"] and mmio_ready or before["nc_wakeup"]["valid"] and nc_ready
            if inp["id_response"]["valid"] and inp["id_response"]["mid"] != entry_id and owner:
                owner["wrong_mids"].add(inp["id_response"]["mid"])
                counters["wrong_mid_inputs"] += 1
            if inp["response"]["valid"]:
                assert owner is not None and owner["issued"] is not None and owner["sid"] is not None and owner["response"] is None
                counters["responses"] += 1
                response = inp["response"]
            if request_fire:
                counters["bus_accepts"] += 1
            if wake:
                counters["wakeups"] += 1
            if consume:
                assert owner["response"] is not None and owner["woke"] is not None
                counters["consumptions"] += 1
                positive_sids[entry_id].add(owner["sid"])
                negative_mids[entry_id].update(owner["wrong_mids"])
                data = owner["response"]["data"]
                errors[entry_id].add((owner["response"]["error"], owner["response"]["nderr"]))
                if data and data.bit_count() == 1:
                    data_bits[entry_id].add(data.bit_length() - 1)
                q = owner["q"]
                byte_mask = (q["mask"] // (256 if q["paddr"] % 16 >= 8 else 1)) % 256
                if byte_mask.bit_count() == 1:
                    masks[entry_id].add((bool(q["paddr"] & 8), byte_mask.bit_length() - 1))
            if flush:
                assert owner is not None
                counters["canceled_releases"] += not consume
                owner = None
            elif owner:
                # Advance event timestamps strictly from oldest phase to
                # newest. No domain-model Change or internal phase is used.
                if owner["announced"] is None:
                    if owner["q"]["nc"] or not after(owner["q"]["rob"], pending):
                        owner["announced"] = edge
                elif owner["issued"] is None:
                    if request_fire:
                        owner["issued"] = edge
                elif owner["response"] is None:
                    if inp["response"]["valid"]:
                        owner["response"] = inp["response"]
                elif owner["woke"] is None and wake:
                    owner["woke"] = edge
                owner["deferred"] |= cancel
                counters["deferred_cancel_edges"] += owner["deferred"]
                if ack:
                    assert owner["issued"] is not None
                    owner["sid"] = inp["id_response"]["sid"]
                    counters["id_accepts"] += 1
            if inp["request"]["valid"]:
                assert owner is None and not flush
                sequence += 1
                q = inp["request"]
                assert q["nc"] != q["mmio"] and 0 <= q["lq"]["value"] < 120
                owner = {"uid": sequence, "q": q, "saved": edge, "announced": None, "issued": None,
                         "response": None, "woke": None, "sid": None, "deferred": False, "wrong_mids": set()}
                counters["allocations"] += 1
            pending, report = inp["pending"], next_report
            check(actual_after, inp, owner, report, entry_id)
            counters["exception_reports"] += actual_after["exception"]["valid"]
        assert owner is None and report is None, "test ended with an uncompleted owner/report"
        assert counters["consumptions"] == counters["exception_reports"]
        assert counters["allocations"] == counters["consumptions"] + counters["canceled_releases"] + counters["reset_canceled_owners"]
        rows.append({"entry_id": entry_id, "journal": str(path.relative_to(run)), "sha256": sha(path), **dict(counters)})
    assert cases_by_id == Counter({entry_id: 24 for entry_id in range(16)})
    for entry_id in range(16):
        assert positive_sids[entry_id] == set(range(16))
        assert negative_mids[entry_id] == set(range(128)) - {entry_id}
        assert data_bits[entry_id] == set(range(64))
        assert masks[entry_id] == {(half, bit) for half in (False, True) for bit in range(8)}
        assert errors[entry_id] == {(error, nderr) for error in (False, True) for nderr in (False, True)}
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__)), "do not overwrite historical auditor"
    else:
        shutil.copy2(__file__, dest)
    result = {"run": name, "status": "verified", "tests": len(files), "ids": 16, "auditor_sha256": sha(dest),
              "scope": "continuous public inputs/outputs; independent owner/event timestamps and pending history, bus/id/response/wakeup/data/exception, redirect defer and lifecycle conservation; no model or DUT internal reads",
              "per_id_exhaustive_sets": {"accepted_sids": 16, "rejected_other_mids": 127, "single_data_bits": 64,
                                          "mask_half_byte_positions": 16, "response_error_combinations": 4},
              "totals": {key: sum(row[key] for row in rows) for key in counters}, "cases": rows}
    output = run / "trace-audit.json"
    if output.exists():
        assert json.loads(output.read_text()) == result
    else:
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2, ensure_ascii=False))
    print("per-case evidence:", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
