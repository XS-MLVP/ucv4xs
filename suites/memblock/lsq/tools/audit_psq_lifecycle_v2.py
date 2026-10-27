#!/usr/bin/env python3
"""66-case PSQ audit: exact replay of 63 audited histories plus new order proof.

The old 63-case independent UID/byte audit is not silently reused for changed
traffic: EVERY raw input/output/tick in those histories must match bit for bit.
The three new cases get a fresh proof from actual bus completion and zero old
Sbuffer transfers. No reference model imports and no issue-list oracle.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT, sha, verify_common


def traces(run):
    result = {}
    for name in ("physical_store_queue.jsonl", "psq_full.jsonl"):
        for path in (run / "cases").rglob(name):
            rows = [json.loads(row) for row in path.read_text().splitlines()]
            node = rows[0]["nodeid"]
            assert node not in result
            result[node] = path, rows
    return result


def public(rows):
    return [{k: row[k] for k in ("input", "post_input", "before", "after", "pre_tick", "post_tick")} for row in rows]


def order_proof(rows):
    def pointer(pins):
        return 128 * pins["io_sqDeqPtr_first_flag"] + 64 * pins["io_sqDeqPtr_second_flag"] + pins["io_sqDeqPtr_value"]
    requests, finishes = [], []
    old_fires = []
    for row in rows:
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        for lane in range(2):
            prefix = f"io_writeToSbuffer_req_{lane}_"
            assert not inp[prefix + "ready"], "the old ordinary request stays stalled for the whole proof"
            if pre[prefix + "valid"] and inp[prefix + "ready"]:
                old_fires.append(tick)
        if pre["io_toUncacheBuffer_req_valid"] and inp["io_toUncacheBuffer_req_ready"]:
            assert pre["io_toUncacheBuffer_req_bits_id"] == 1 and pre["io_toUncacheBuffer_req_bits_addr"] == 0xDEF000
            requests.append(tick)
        if (inp["io_toUncacheBuffer_idResp_valid"] and not inp["io_toUncacheBuffer_idResp_bits_is2lq"] or
                pre["io_writeBack_valid"] and inp["io_writeBack_ready"]):
            assert requests and pointer(pre) == 0
            finishes.append(tick)
    final = rows[-1]
    assert len(requests) == len(finishes) == 1 and not old_fires
    assert final["post_tick"] > finishes[0] and pointer(final["before"]) == 0 and pointer(final["after"]) == 1
    assert final["after"]["io_writeToSbuffer_req_0_valid"] and final["after"]["io_writeToSbuffer_req_0_bits_vaddr"] == 0x30000
    return dict(issue="DEQ-FINISH-ORDER-001", request_tick=requests[0], young_finish_tick=finishes[0],
                bad_release_tick=final["post_tick"], old_sbuffer_fires=0, head_before=0, head_after=1, old_write_still_valid=True)


def audit(name):
    run, old_run = ROOT / "results" / name, ROOT / "results/psq-expanded-05"
    manifest, source, all_nodes = verify_common(run)
    _, _, old_nodes = verify_common(old_run)
    nodes = {n: failed for n, failed in all_nodes.items() if n.startswith("tests/psq/")}
    old_report_path = old_run / "lifecycle-audit.json"
    old = json.loads(old_report_path.read_text())
    assert old["tests"] == {"PASS": 45, "FAIL": 18} and len(old_nodes) == 63 and len(nodes) == 66
    for name, digest in old["auditors"].items():
        assert sha(old_run / "evidence-auditors" / name) == digest
    previous, current = traces(old_run), traces(run)
    assert set(previous) == set(old_nodes) and set(current) == set(nodes)
    counts, cases, issues = Counter(), [], Counter()
    old_cases = {case["nodeid"]: case for case in old["cases"]}
    for node, (path, rows) in current.items():
        last = None
        for row in rows:
            tick = row["post_tick"]
            assert row["input"] == row["post_input"] and row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            assert len(row["input"]) == 119 and len(row["before"]) == len(row["after"]) == 333
            last = tick
            counts["continuous_records"] += 1
            if path.name == "psq_full.jsonl":
                bad = {}
                for phase in ("before", "after"):
                    bad.update({key: [row[phase][key], value] for key, value in row.get("expected_" + phase, {}).items()
                                if (row[phase][key] ^ value) & row.get("masks_" + phase, {}).get(key, -1)})
                assert not row["checked"] or not bad and not row.get("error")
                counts["full_reference_records"] += 1
        if node in previous:
            old_path, old_rows = previous[node]
            assert public(rows) == public(old_rows), ("changed public history requires fresh independent replay, not inherited acceptance", node)
            assert nodes[node] == old_nodes[node]
            proof = dict(kind="bit_exact_public_history_revalidated", old_journal=str(old_path.relative_to(old_run)),
                         old_journal_sha256=sha(old_path), old_case_independent_violations=old_cases[node]["violations"])
            counts["bit_exact_revalidated_cases"] += 1
            if nodes[node]:
                issue = {w["issue"] for w in old_cases[node]["violations"]}
                assert len(issue) == 1
                issues.update(issue)
        else:
            assert "test_special_order.py::" in node and nodes[node]
            proof = order_proof(rows)
            issues[proof["issue"]] += 1
            counts["new_independently_proven_order_failures"] += 1
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), journal_sha256=sha(path), records=len(rows), proof=proof))
    assert counts["bit_exact_revalidated_cases"] == 63 and counts["new_independently_proven_order_failures"] == 3
    assert sum(issues.values()) == sum(nodes.values()) == 21
    groups = {g["instance"]: g["points"][0]["counts"] for g in json.loads((run / "execution/functional-coverage.json").read_text())["groups"]}
    reached, checked = (groups["lsq.physical_store_queue." + kind] for kind in ("reached", "checked"))
    assert len(checked) == 46 and all(reached.values()) and all(reached[k] >= value for k, value in checked.items())
    dest = run / "evidence-auditors" / Path(__file__).name
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=run.name, status="66_case_public_history_revalidated_plus_new_independent_order_proofs", dut_acceptance="NOT_PASS",
                  tests=dict(Counter("FAIL" if v else "PASS" for v in nodes.values())), counts=dict(counts), failure_cases_by_issue=dict(issues),
                  inherited_unchanged_uid_counts=old["counts"], checked=sum(bool(c) for c in checked.values()), reached=sum(bool(c) for c in reached.values()),
                  total_scenarios=len(checked), snapshot_files=len(source), previous_independent_audit_sha256=sha(old_report_path),
                  auditor_sha256=sha(dest), manifest_sha256=sha(run / "execution/manifest.json"), cases=cases,
                  limits="63 histories revalidated bit-for-bit including ALL raw input and pre/post output pins/ticks against the independently audited frozen PSQ run, not just pass/fail signatures. Three added special-order probes have separate public transfer/age proofs. No architecture proof or complete LSQ acceptance.")
    out = run / "psq-lifecycle-audit-v2.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("cases", "inherited_unchanged_uid_counts")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
