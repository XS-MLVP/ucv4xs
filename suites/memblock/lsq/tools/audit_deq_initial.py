#!/usr/bin/env python3
"""Independent first-round public writeout checks and missing-line mapping.

This audits the limited 16-case directed round, NOT full Deq acceptance or a
complete PSQ/lifecycle model. No lsqverify/model/internal-register imports.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["tests"] == {"PASS": 13, "FAIL": 3}
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    end = json.loads((run / "end-source-check.json").read_text())
    assert end["all_current_launch_files_match_snapshot"] and end["files"] == source
    tests = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert len(tests) == 16 and all(case.find("skipped") is None and case.find("error") is None for case in tests)
    nodes = {case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]: case.find("failure") is not None for case in tests}
    assert len(nodes) == 16
    command = json.loads((run / "command.json").read_text())["command"]
    assert "tests/deq" in command and "-k" not in command
    paths = sorted((run / "cases").rglob("deq_module.jsonl"))
    assert len(paths) == 16
    cases, failures, observations, valid_bytes, actual_fires, credits = [], [], 0, 0, 0, 0
    for path in paths:
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        nodeid, tick = rows[0]["nodeid"], None
        assert nodeid in nodes
        by_tick, stores, pages = {}, {}, []
        sb_fires = credit_count = read_moves = 0
        for row in rows:
            assert row["nodeid"] == nodeid and row["input"] == row["post_input"]
            assert row["pre_tick"] + 1 == row["post_tick"] and (tick is None or tick + 2 == row["post_tick"])
            tick = row["post_tick"]
            by_tick[tick] = row
            observations += 1
            inp = row["input"]
            for store in inp["stores"]:
                if store["committed"] and not store["cache_operation"]:
                    stores[(store["vaddr"], store["page"], store["byte_mask"], store["data"])] = store
            if inp["second_page"]["valid"]:
                pages.append(inp["second_page"])
            for phase in ("before", "after"):
                pins = row[phase]
                for lane in range(2):
                    prefix = f"io_writeToSbuffer_req_{lane}_"
                    if not pins[prefix + "valid"]:
                        continue
                    word_pa, word_va = pins[prefix + "bits_addr"], pins[prefix + "bits_vaddr"]
                    expected = {}
                    for store in stores.values():
                        for index in range(16):
                            if not store["byte_mask"] >> index & 1:
                                continue
                            va = store["vaddr"] + index
                            pa = store["page"] * 4096 + store["vaddr"] % 4096 + index
                            if va // 4096 != store["vaddr"] // 4096:
                                assert pages
                                pa = pages[-1]["paddr"] + va % 4096
                            if va // 16 == word_va // 16 and pa // 16 == word_pa // 16:
                                expected[pa % 16] = store["data"] >> (8 * index) & 255
                    assert expected and pins[prefix + "bits_wline"] == 0
                    assert pins[prefix + "bits_mask"] == sum(1 << byte for byte in expected)
                    assert all(pins[prefix + "bits_data"] >> (8 * byte) & 255 == value for byte, value in expected.items())
                    valid_bytes += len(expected)
            if not inp["reset"]:
                sb_fires += sum(row["before"][f"io_writeToSbuffer_req_{lane}_valid"] and inp["sbuffer_ready"][lane] for lane in range(2))
                credit_count += row["before"]["io_sqDeqCnt"]
                read_moves += row["before"]["io_rdataPtrMoveCnt"]
        checks_path = path.with_name("deq_checks.jsonl")
        checks = [json.loads(line) for line in checks_path.read_text().splitlines()]
        failed = []
        for check in checks:
            assert check["nodeid"] == nodeid
            actual = by_tick[check["tick"]][check["phase"]]
            assert check["actual"] == {key: actual[key] for key in check["expected"]}
            differences = {key: [actual[key], value] for key, value in check["expected"].items() if (actual[key] ^ value) & check["bit_masks"].get(key, -1)}
            assert check["passed"] == (not differences)
            if differences:
                failed.append(check)
        assert bool(failed) == nodes[nodeid]
        if failed:
            assert len(failed) == 1 and failed[0] is checks[-1]
            arrivals = [row for row in rows if row["input"]["cache_response"] and row["before"]["io_toDCache_resp_ready"]]
            assert len(arrivals) == 1
            arrival = arrivals[0]
            bad = by_tick[failed[0]["tick"]]
            assert arrival["input"]["cache_denied"] or arrival["input"]["cache_corrupt"]
            assert bad["post_tick"] == arrival["post_tick"] + 2 and not bad["input"]["writeback_ready"]
            for row in (arrival, bad):
                assert row["after"]["io_writeBack_valid"] and row["after"]["io_exceptionInfo_valid"]
                assert row["input"]["stores"] == arrival["input"]["stores"]
            for bit, field in ((7, "cache_denied"), (19, "cache_corrupt")):
                want = int(arrival["input"][field])
                for prefix in ("io_writeBack_bits_exceptionVec_", "io_exceptionInfo_bits_exceptionVec_"):
                    assert arrival["after"][prefix + str(bit)] == want and bad["after"][prefix + str(bit)] == 0
            failures.append({"nodeid": nodeid, "journal": str(path.relative_to(run)), "sha256": sha(path), "response_tick": arrival["post_tick"],
                             "lost_fault_tick": bad["post_tick"], "denied": arrival["input"]["cache_denied"], "corrupt": arrival["input"]["cache_corrupt"],
                             "limits": "This case stops during stall; a later-fire case is still required to demonstrate actual consumption of cleared errors."})
        if "test_single_cacheable_store_" in nodeid:
            assert (sb_fires, credit_count, read_moves) == (1, 1, 1)
        elif "test_two_stores_" in nodeid:
            assert (sb_fires, credit_count, read_moves) == (2, 2, 2)
        elif "test_split_store_" in nodeid:
            assert (sb_fires, credit_count, read_moves) == (2, 1, 1)
        actual_fires += sb_fires
        credits += credit_count
        cases.append({"nodeid": nodeid, "journal": str(path.relative_to(run)), "sha256": sha(path), "checks_sha256": sha(checks_path),
                      "records": len(rows), "directed_checks": len(checks), "failed_checks": len(failed), "sbuffer_fires": sb_fires, "sq_credit_sum": credit_count})
    lines = json.loads((run / "line-audit.json").read_text())
    classified = copy.deepcopy(lines)
    native = classified["native"][0]
    assert (native["line_hit"], native["line_total"], native["closure_line_hit"], native["closure_line_total"]) == (34, 46, 101, 124)
    assert {gap["line"] for gap in native["uncovered"]} == {422, 424, 425, 426, 428, 429, 430, 432, 433, 434, 436, 437}
    for gap in native["uncovered"]:
        gap.update(features=["DEQ-NC", "DEQ-MMIO", "DEQ-CREDIT"], classification="missing_scenario_of_existing_feature",
                   semantic_gap="合同已定义但首轮尚未实现整条NC/MMIO请求、确认或响应及回写路径；补合法MemoryType、req背压、idResp方向、resp/WB和实际完成credit，不新增虚构端口或排除可达行")
    dep = native["dependencies"][0]
    assert len(dep["uncovered"]) == 11
    for gap in dep["uncovered"]:
        assert 131 <= gap["line"] <= 136 or 155 <= gap["line"] <= 159
        gap.update(features=["DEQ-BACKPRESSURE", "DEQ-CACHE", "DEQ-CREDIT"], classification="missing_scenario_of_existing_feature",
                   semantic_gap="真实下级内部尾位置为奇数时第二入口写slot0/第一入口写slot1未激活；补先单项消费再双入或连续单入及满池同拍出入，检查实际消费与credit，不借用已通过的独立叶子覆盖")
    output = run / "line-audit-classified.json"
    if output.exists():
        assert json.loads(output.read_text()) == classified
    else:
        with output.open("x") as stream:
            json.dump(classified, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = {"run": name, "status": "first_round_public_directed_checks_and_fault_loss_audited", "dut_acceptance": "NOT_PASS",
              "tests": manifest["tests"], "records": observations, "valid_byte_observations": valid_bytes, "sbuffer_fires": actual_fires, "sq_credit_sum": credits,
              "snapshot_files": len(source), "auditor_sha256": sha(dest), "manifest_sha256": sha(run / "execution/manifest.json"),
              "line_audit_sha256": sha(run / "line-audit.json"), "classified_line_audit_sha256": sha(output),
              "limits": "Only 16 initial directed cases and per-check public byte/response evidence; no complete lifecycle/PSQ agent, NC/MMIO/random/remaining semantic signoff or architecture-level outcome is claimed.",
              "failures": failures, "cases": cases}
    out = run / "initial-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        with out.open("x") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "failures")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
