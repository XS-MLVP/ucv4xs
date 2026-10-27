#!/usr/bin/env python3
"""Versioned line classification with exact parent-scope narrow proof links."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil

from audit_lq_gaps import locate
from audit_sq_initial import ROOT, sha


def audit(name):
    run = ROOT / "results" / name
    raw, proof_path = run / "line-audit.json", run / "static-gap-proof.json"
    report = copy.deepcopy(json.loads(raw.read_text()))
    proof = json.loads(proof_path.read_text())
    assert proof["raw_line_audit_sha256"] == sha(raw)
    proven = {(row["source"], row["line"]): row for row in proof["rows"]}
    native = report["native"][0]
    assert len(report["native"]) == 1 and native["dut"] == "load_queue" and not native["uncovered"]
    counts, kinds = Counter(), Counter()
    for dep in native["dependencies"]:
        name = Path(dep["source"]).name
        assert sha(ROOT / dep["source"]) == dep["sha256"]
        for gap in dep["uncovered"]:
            key = (name, gap["line"])
            features, why = locate(name, gap)
            gap.update(features=features, classification="missing_scenario_of_existing_feature", semantic_gap=why,
                       reachability="not_excluded", scope="real_LoadQueue_closure_not_leaf_substitution")
            if key in proven:
                row = proven[key]
                gap.update(classification=row["classification"], reachability="narrow_evidence_provided_not_counted_hit",
                           semantic_gap=row["proof"], proof_file="static-gap-proof.json", proof_sha256=sha(proof_path))
                if name == "VirtualLoadQueue.sv":
                    gap["features"] = ["LQ-RECOVER.concurrent"]
                    gap["scope"] = "normal_upstream_producer_only_not_arbitrary_direct_interface"
            elif name == "LoadQueueReplay.sv" and gap["text"].startswith("strict_"):
                gap["semantic_gap"] = "三路混合原因保存优先级：lane2和lane1是真实地址等待，而lane0是非地址原因；补两个不同实际分配位置，检查已有strict owner仍阻塞、匹配STA后原UID实际完成；不能豁免已保留的无效反馈解除strict失败"
            kinds[gap["classification"]] += 1
            counts[name] += 1
    missing = sum(counts.values())
    assert missing == native["closure_line_total"] - native["closure_line_hit"]
    assert set(proven) == {(Path(dep["source"]).name, gap["line"]) for dep in native["dependencies"] for gap in dep["uncovered"] if gap.get("proof_file")}
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report.update(raw_line_audit_sha256=sha(raw), missing_lines=missing, classification_counts=dict(counts),
                  classification_kinds=dict(kinds), static_gap_proof_sha256=sha(proof_path), auditor_sha256=sha(dest),
                  note="Every raw DA row and denominator retained; six mux contradictions and one normal-producer exclusion are NOT dynamic hits. All other gaps are existing semantic features missing cases, not silently omitted whole functions. Not functional acceptance or branch/expression proof.")
    out = run / "line-audit-classified-v2.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in ("run", "tests", "missing_lines", "classification_counts", "classification_kinds", "note")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
