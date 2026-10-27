#!/usr/bin/env python3
"""Independent accepted-Cache-response to actual-WB-fire fault-loss audit."""
import argparse
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
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    end = json.loads((run / "end-source-check.json").read_text())
    assert end["all_current_launch_files_match_snapshot"] and end["files"] == source
    tests = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert len(tests) in (19, 28) and all(case.find("error") is None and case.find("skipped") is None for case in tests)
    nodes = [case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"] for case in tests]
    failed = {node for node, case in zip(nodes, tests, strict=True) if case.find("failure") is not None}
    expected = {f"tests/deq/test_cbo_fault_consumption.py::test_delayed_writeback_fire_consumes_original_cache_error[{values}]" for values in ("True-False", "False-True", "True-True")}
    expected |= {f"tests/deq/test_initial.py::test_cache_cbo_response_errors_survive_writeback_backpressure[3-{values}]" for values in ("True-False", "False-True", "True-True")}
    assert failed == expected and manifest["tests"] == {"PASS": len(tests) - 6, "FAIL": 6}
    witnesses = []
    for path in sorted((run / "cases").rglob("deq_module.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        nodeid = rows[0]["nodeid"]
        if nodeid not in failed:
            continue
        requests = [row for row in rows if row["before"]["io_toDCache_req_valid"] and row["input"]["cache_ready"]]
        responses = [row for row in rows if row["before"]["io_toDCache_resp_ready"] and row["input"]["cache_response"]]
        assert len(requests) == len(responses) == 1
        request, response = requests[0], responses[0]
        assert request["post_tick"] < response["post_tick"]
        store = response["input"]["stores"][0]
        assert store["committed"] and store["data_valid"] and store["address_valid"] and not store["exception"]
        assert store["cache_operation"] and store["cbo"] == 0 and store["memory_type"] == 0
        assert request["before"]["io_toDCache_req_bits_address"] == store["page"] * 4096 + store["vaddr"] % 4096
        denied, corrupt = response["input"]["cache_denied"], response["input"]["cache_corrupt"]
        assert denied or corrupt
        for bit, value in ((7, denied), (19, corrupt)):
            assert response["after"][f"io_writeBack_bits_exceptionVec_{bit}"] == value
        last = rows[-1]
        actual_fire = "test_delayed_writeback_fire_" in nodeid
        assert all(row["input"]["stores"][0] == store and not row["input"]["reset"] for row in rows if row["post_tick"] >= request["post_tick"])
        if actual_fire:
            assert last["input"]["writeback_ready"] and last["before"]["io_writeBack_valid"]
            assert last["before"]["io_rdataPtrMoveCnt"] == 1 and last["after"]["io_writeBack_valid"] == 0
            observed = last["before"]
            stalls = [row for row in rows if response["post_tick"] < row["post_tick"] < last["post_tick"]]
            assert stalls and all(not row["input"]["writeback_ready"] and row["after"]["io_writeBack_valid"] for row in stalls)
        else:
            assert not last["input"]["writeback_ready"] and last["after"]["io_writeBack_valid"]
            observed = last["after"]
        assert observed["io_writeBack_bits_exceptionVec_7"] == observed["io_writeBack_bits_exceptionVec_19"] == 0
        assert observed["io_exceptionInfo_bits_exceptionVec_7"] == observed["io_exceptionInfo_bits_exceptionVec_19"] == 0
        checks = [json.loads(line) for line in path.with_name("deq_checks.jsonl").read_text().splitlines()]
        assert len([check for check in checks if not check["passed"]]) == 1 and not checks[-1]["passed"]
        assert checks[-1]["tick"] == last["post_tick"]
        witnesses.append({"nodeid": nodeid, "journal": str(path.relative_to(run)), "sha256": sha(path), "request_tick": request["post_tick"],
                          "response_tick": response["post_tick"], "failure_tick": last["post_tick"], "denied": denied, "corrupt": corrupt,
                          "actual_wb_fire": actual_fire, "actual_exception7": 0, "actual_exception19": 0})
    assert len(witnesses) == 6 and sum(witness["actual_wb_fire"] for witness in witnesses) == 3
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = {"run": name, "status": "accepted_cache_error_lost_at_three_actual_wb_fires", "dut_acceptance": "NOT_PASS", "issue": "DEQ-WB-001",
              "tests": manifest["tests"], "domain": "public Deq producer-valid CBO operation with ordinary writeBack ready backpressure",
              "snapshot_files": len(source), "manifest_sha256": sha(run / "execution/manifest.json"), "auditor_sha256": sha(dest),
              "limits": "Independent leaf public request/response/WB transfer evidence; real PSQ and architecture-level consequences still require parent integration. Does not establish full Deq functional or lifecycle coverage.",
              "witnesses": witnesses}
    out = run / "fault-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        with out.open("x") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key != "witnesses"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
