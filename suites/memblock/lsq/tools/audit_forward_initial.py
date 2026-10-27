#!/usr/bin/env python3
"""Independent public-byte reproduction and first line-gap classification.

NOT a ForwardModule acceptance gate or complete arbitration model.
"""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    run = ROOT / "results/forward-initial-01"
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["pytest_exitstatus"] == 1 and manifest["tests"] == {"PASS": 10, "FAIL": 3}
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    cases = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert len(cases) == 13 and not any(case.find("skipped") is not None or case.find("error") is not None for case in cases)
    failed = [case for case in cases if case.find("failure") is not None]
    assert {case.attrib["name"] for case in failed} == {f"test_cross_word_physical_alias_never_accepts_older_word_value[{lane}]" for lane in range(3)}
    native = json.loads((run / "line-audit.json").read_text())["native"]
    assert len(native) == 1 and native[0]["dut"] == "forward_module" and (native[0]["line_hit"], native[0]["line_total"]) == (250, 253)
    assert {gap["line"] for gap in native[0]["uncovered"]} == {4675, 6736, 8797}
    gaps = [{**gap, "classification": "missing_scenario_of_existing_feature", "features": ["FWD-AGE.wrap", "FWD-AGE.all_slots", "FWD-SELECT.youngest"],
             "semantic_gap": "三个查询lane的回绕低年龄段优先树反向索引低16位分支未激活；补deq60、SQ112(slot48)和load114、再补64槽×3入口真实输出，不排除行",
             "reachability": "not_excluded"} for gap in native[0]["uncovered"]]
    reproductions = []
    for path in (run / "cases").rglob("forward_module.jsonl"):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if "error" not in rows[-1]:
            continue
        assert all(row["post_tick"] == rows[index - 1]["post_tick"] + 2 for index, row in enumerate(rows) if index)
        first = next(row for row in rows if any(query["valid"] for query in row["input"]["queries"]))
        lane = next(lane for lane, query in enumerate(first["input"]["queries"]) if query["valid"])
        query = first["input"]["queries"][lane]
        row, inp = rows[-1], rows[-1]["input"]
        bank = inp["stores"]
        assert all(record["input"]["stores"] == bank for record in rows if record["post_tick"] >= first["post_tick"])
        assert query["sq"] == {"first": False, "second": False, "value": 2}
        assert inp["dequeue"] == {"first": False, "second": False, "value": 0} and inp["upper"] == {"first": False, "second": True, "value": 0}
        assert all(bank[slot]["address_ready"] and bank[slot]["data_ready"] and not bank[slot]["cache_operation"] for slot in (0, 1))
        assert bank[0]["size"] == 2 and bank[0]["mask"] == 15 and not bank[0]["cross_word"]
        assert bank[1]["size"] == 3 and bank[1]["mask"] == 255 and bank[1]["cross_word"]
        paddr = inp["translations"][lane]["paddr"]
        assert not inp["translations"][lane]["kill"]
        addresses = [store["page"] * 4096 + store["vaddr"] % 4096 for store in bank[:2]]
        assert query["vaddr"] == bank[0]["vaddr"] and bank[0]["vaddr"] // 4096 != bank[1]["vaddr"] // 4096
        assert paddr == addresses[0] and addresses[1] + 4 == paddr
        prefix = f"io_query_{lane}_s2Resp_"
        out = row["after"]
        assert out[prefix + "valid"] == 1
        assert not any(out[prefix + suffix] for suffix in ("bits_forwardInvalid", "bits_matchInvalid", "bits_addrInvalid_valid", "bits_dataInvalid_valid"))
        mask = sum(out[prefix + f"bits_forwardMask_{byte}"] << byte for byte in range(16))
        data = sum(out[prefix + f"bits_forwardData_{byte}"] << (8 * byte) for byte in range(4))
        expected = bank[1]["data"] >> 32 & 0xFFFFFFFF
        assert mask == 15 and data == 0x11111111 and expected == 0x22222222
        assert not row["checked"] and "forward-physical-byte-safety" in row["error"]
        reproductions.append({"lane": lane, "journal": str(path.relative_to(run)), "sha256": sha(path), "s0_tick": first["post_tick"], "s2_tick": row["post_tick"],
                              "load_paddr": paddr, "store_paddr": addresses, "actual_data": data, "required_youngest_data": expected,
                              "actual_mask": mask, "replay_or_dependency_flags": [0, 0, 0, 0]})
    assert {item["lane"] for item in reproductions} == {0, 1, 2}
    destination = run / "evidence-auditors" / Path(__file__).name
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        assert sha(destination) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), destination)
    result = {"run": run.name, "status": "initial_evidence_audited_with_failures", "dut_acceptance": "NOT_PASS", "issue": "FWD-ALIAS-001",
              "tests": manifest["tests"], "source_snapshot_files": len(source), "body_da": [250, 253], "uncovered_line_mapping": gaps,
              "scope": "13 initial native cases only; independently reconstructs stable-bank PA byte ranges for three concrete failures, not full forwarding/arbitration/liveness acceptance",
              "source_basis": "NewStoreQueue.scala:462-476,487-511,606-625; scalar mask generation1934-1949 permits offset-free8B mask and cross16 store",
              "manifest_sha256": sha(run / "execution/manifest.json"), "line_audit_sha256": sha(run / "line-audit.json"), "auditor_sha256": sha(destination),
              "reproductions": sorted(reproductions, key=lambda item: item["lane"])}
    out = run / "initial-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == result
    else:
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "uncovered_line_mapping"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
