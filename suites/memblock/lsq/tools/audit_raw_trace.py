#!/usr/bin/env python3
"""Recompute RAW conflicts/identity from public input history, without domain imports."""
import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rob_raw(pointer):
    assert 0 <= pointer["value"] < 160
    return 2 * (int(pointer["flag"]) * 160 + pointer["value"]) + int(not pointer["former"])


def younger(left, right):
    delta = (rob_raw(left) - rob_raw(right)) % 640
    assert delta != 320, "ambiguous ROB half-ring"
    return 0 < delta < 320


def flushed(query, redirect):
    return redirect["valid"] and (younger(query["rob"], redirect["rob"])
                                   or redirect["flush_self"] and query["rob"] == redirect["rob"])


def match(query, store):
    divisor = 64 if store["wline"] else 16
    # Compare truncated byte addresses, a different expression from the
    # domain model's XOR/mask implementation.
    return (query["paddr"] % (1 << 28)) // divisor == (store["paddr"] % (1 << 28)) // divisor and bool(query["mask"] & store["mask"])


def sq_raw(pointer):
    assert 0 <= pointer["value"] < 64
    return int(pointer["first"]) * 128 + int(pointer["second"]) * 64 + pointer["value"]


def expected_payload(query, store):
    return {"valid": True, "rob": query["rob"], "ftq": query["ftq"], "ftq_offset": query["ftq_offset"],
            "is_rvc": query["is_rvc"], "checkpoint": query["checkpoint"], "store_ftq_flag": store["ftq_flag"],
            "store_ftq_value": store["ftq_value"], "store_ftq_offset": store["ftq_offset"], "store_is_rvc": store["is_rvc"]}


def check_stored_outputs(actual, expected):
    for key in ("ready", "full", "perf_fire", "perf_rollback"):
        assert actual[key] == expected[key], (key, actual, expected)
    for got, want in zip(actual["rollbacks"], expected["rollbacks"], strict=True):
        assert got["valid"] == want["valid"] and (not want["valid"] or got == want)
    assert actual["training"]["valid"] == expected["training"]["valid"]
    if expected["training"]["valid"]:
        assert actual["training"] == expected["training"]


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    gate = json.loads((run / "evidence-check.json").read_text())
    assert manifest["state"] == "committed" and manifest["pytest_exitstatus"] == 0
    assert gate["status"] == "verified" and gate["required_line_complete"] and gate["required_semantic_complete"]
    assert gate["manifest_sha256"] == sha(run / "execution/manifest.json")
    files = sorted((run / "cases").rglob("load_queue_raw.jsonl"))
    assert len(files) == manifest["tests"]["PASS"] == 32
    pairs, rows = set(), []
    for path in files:
        counters = Counter(records=0, checked=0, reset_edges=0, query_inputs=0, query_fires=0, allocations=0, frees=0,
                           store_inputs=0, tlb_miss_inputs=0, rollbacks=0, training_outputs=0, unique_positive_jobs=0,
                           pending_jobs_canceled_by_reset=0)
        entries, jobs, locations, proven = {}, [], {}, set()
        sequence = head = previous_fire = 0
        history = deque(((), ()), maxlen=2)
        rollback_history = deque((False, False))
        last_tick, reset_length = None, 0
        for line in path.read_text().splitlines():
            record = json.loads(line)
            assert "error" not in record
            counters["records"] += 1
            edge = counters["records"]
            assert record["pre_tick"] + 1 == record["post_tick"]
            if last_tick is not None:
                assert record["post_tick"] == last_tick + 2, "globally observed cycle omitted"
            last_tick = record["post_tick"]
            inp, before, after = record["input"], record["before"], record["after"]
            assert inp == record["post_input"]
            if inp["reset"]:
                assert not record["checked"]
                counters["reset_edges"] += 1
                reset_length += 1
                counters["pending_jobs_canceled_by_reset"] += sum(job["winner"] is not None and not job["canceled"]
                                                                  and not job["store"]["tlb_miss"] for job in jobs)
                entries.clear()
                jobs.clear()
                head, previous_fire = 0, 0
                history = deque(((), ()), maxlen=2)
                rollback_history = deque((False, False))
                continue
            if reset_length:
                assert reset_length >= 6
                reset_length = 0
            assert record["checked"]
            counters["checked"] += 1
            check_stored_outputs(before, record["expected_before"])
            check_stored_outputs(after, record["expected_after"])
            assert after["perf_fire"] == previous_fire
            assert after["perf_rollback"] == rollback_history.popleft()
            fires = sum(q["valid"] and before["ready"][lane] for lane, q in enumerate(inp["queries"]))
            previous_fire = fires
            rollback_history.append(any(rb["valid"] for rb in after["rollbacks"]))
            distance = (sq_raw(inp["head"]) - head) % 256
            assert distance < 128
            head += distance
            prior = dict(entries)
            assert set(prior) == {item["uid"] for item in record["change"]["before"]}
            revoked = {uid for lane, uid in enumerate(history[-1]) if uid is not None and inp["revoke_last"][lane]}
            revoked.update(uid for lane, uid in enumerate(history[0]) if uid is not None and inp["revoke_older"][lane])
            removed = {uid for uid, item in prior.items() if item["sq"] <= head or flushed(item["query"], inp["redirect"]) or uid in revoked}
            assert removed == {item["item"]["uid"] for item in record["change"]["freed"]}
            for uid in removed:
                del entries[uid]
            for job in jobs:
                if job["winner"] is not None and flushed(job["winner"]["query"], inp["redirect"]):
                    job["canceled"] = True
            for lane, store in enumerate(inp["stores"]):
                if not store["valid"]:
                    continue
                # Independently recompute the complete conflict set from the
                # journal's accepted public load inputs, not change.matches,
                # model UopEntry, selected-group registers or actual payload.
                candidates = [item for uid, item in prior.items() if item["query"]["data_valid"]
                              and younger(item["query"]["rob"], store["rob"]) and match(item["query"], store)
                              and not flushed(item["query"], inp["redirect"]) and uid not in revoked]
                winner = min(candidates, key=lambda item: (rob_raw(item["query"]["rob"]) - rob_raw(store["rob"])) % 640, default=None)
                if winner is not None:
                    ties = [item for item in candidates if item["query"]["rob"] == winner["query"]["rob"]]
                    assert all(expected_payload(item["query"], store) == expected_payload(winner["query"], store) for item in ties), "ambiguous duplicate recovery identity"
                jobs.append({"due": edge + 2, "lane": lane, "store": store, "winner": winner,
                             "canceled": False, "unique": len(candidates) == 1})
                counters["store_inputs"] += 1
                counters["tlb_miss_inputs"] += store["tlb_miss"]
            due = [job for job in jobs if job["due"] == edge]
            jobs = [job for job in jobs if job["due"] > edge]
            assert len({job["lane"] for job in due}) == len(due)
            expected = {job["lane"]: job for job in due if job["winner"] is not None and not job["store"]["tlb_miss"] and not job["canceled"]}
            for lane, actual in enumerate(after["rollbacks"]):
                assert actual["valid"] == (lane in expected), (path, edge, lane, actual, expected)
                if lane in expected:
                    job = expected[lane]
                    assert actual == expected_payload(job["winner"]["query"], job["store"]), (path, edge, lane)
                    counters["rollbacks"] += 1
                    if job["unique"]:
                        uid = job["winner"]["uid"]
                        proven.add(uid)
                        pairs.add((*locations[uid], lane))
                        counters["unique_positive_jobs"] += 1
            valid_lanes = list(expected)
            train = after["training"]
            assert train["valid"] == bool(valid_lanes)
            if valid_lanes:
                chosen = min(valid_lanes)
                for lane in sorted(valid_lanes):
                    if younger(after["rollbacks"][chosen]["rob"], after["rollbacks"][lane]["rob"]):
                        chosen = lane
                rb = after["rollbacks"][chosen]
                assert train == {"valid": True, "ftq_value": rb["ftq"]["value"], "ftq_offset": rb["ftq_offset"],
                                 "is_rvc": rb["is_rvc"], "store_ftq_value": rb["store_ftq_value"],
                                 "store_ftq_offset": rb["store_ftq_offset"], "store_is_rvc": rb["store_is_rvc"]}
                counters["training_outputs"] += 1
            accepted = []
            for lane, query in enumerate(inp["queries"]):
                position = None
                need = False
                if query["valid"]:
                    delta = (sq_raw(query["sq"]) - head) % 256
                    assert delta != 128
                    position = head + (delta if delta < 128 else delta - 256)
                    need = position > head and not flushed(query, inp["redirect"])
                assert need == record["change"]["needed"][lane]
                if need and before["ready"][lane]:
                    sequence += 1
                    uid = sequence
                    accepted.append(uid)
                    entries[uid] = {"uid": uid, "query": query, "sq": position}
                    slot = next(item["slot"] for item in record["change"]["allocated"] if item["uid"] == uid)
                    locations[uid] = (lane, slot)
                    counters["allocations"] += 1
                else:
                    accepted.append(None)
                if not need:
                    assert before["ready"][lane]
            assert accepted == record["change"]["accepted"]
            history.append(tuple(accepted))
            # Reject a wrapped age window that would make the scalar oracle
            # ambiguous. Metadata does not get to redefine the legal domain.
            values = sorted({rob_raw(item["query"]["rob"]) for item in prior.values()}
                            | {rob_raw(q["rob"]) for q in inp["queries"] if q["valid"]}
                            | {rob_raw(s["rob"]) for s in inp["stores"] if s["valid"]})
            if len(values) > 1:
                gaps = [b - a for a, b in zip(values, values[1:])] + [640 + values[0] - values[-1]]
                assert 640 - max(gaps) < 320, "active RAW inputs outside legal ROB half-ring"
            counters["query_inputs"] += sum(q["valid"] for q in inp["queries"])
            counters["query_fires"] += fires
            counters["frees"] += len(removed)
        rows.append({"journal": str(path.relative_to(run)), "sha256": sha(path), "unique_proven_lifecycles": len(proven),
                     "remaining_records": len(entries), "pending_store_jobs": len(jobs), **dict(counters)})
    assert pairs == {(load, slot, store) for load in range(3) for slot in range(56) for store in range(2)}
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__)), "do not overwrite a historical auditor"
    else:
        shutil.copy2(__file__, dest)
    report = {"run": name, "status": "verified", "tests": len(files), "auditor_sha256": sha(dest),
              "scope": "continuous public-pin journals, independent input-history ownership/conflict/oldest/metadata/redirect/revoke/TLB/training/perf recomputation; no DUT internal reads",
              "slot_identity_boundary": "slot IDs only label the already-tested FreeList ledger mapping; independent conflict/selection computation uses accepted public queries and UID history, not those slot IDs",
              "totals": {key: sum(row[key] for row in rows) for key in counters},
              "uniquely_proven_load_lane_slot_store_lane_combinations": len(pairs), "cases": rows}
    output = run / "trace-audit.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))
    print("per-case evidence:", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
