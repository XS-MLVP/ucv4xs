#!/usr/bin/env python3
"""Exact1908-node scope gate, not an assertion that the future run has finished.

09's real1882 plus normal-LDU directed18 and original-seed mixed8. Reuse the
unchanged exact raw/failure/LCOV-set helpers; never promote older interface flows.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil

from audit_progress_run_v10 import FAMILIES as PREVIOUS_FAMILIES, coverage_signature
from audit_progress_run_v7 import JOURNALS, failures, histories
from audit_sq_initial import ROOT, sha, verify_common


FAMILIES={**PREVIOUS_FAMILIES,"lsq_wrapper":397}


def audit(name):
    assert name=="lsq-progress-regression-10"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":1708,"FAIL":200} and len(nodes)==sum(FAMILIES.values())==1908
    command=json.loads((run/"command.json").read_text())["command"]
    assert "tests" in command and not any(a=="-k" or a.startswith("--deselect") for a in command)
    base=ROOT/"results/lsq-progress-regression-09"
    older=json.loads((base/"evidence-check-v10.json").read_text())
    assert older["tests"]=={"PASS":1691,"FAIL":191} and older["actual_raw_records_equal"]==346218
    extra=[ROOT/"results/lsq-ldu-rar-routing-03",ROOT/"results/lsq-ldu-mixed-02"]
    previous={d:verify_common(d) for d in(base,*extra)}
    reports=[]
    old_nodes,old_failures={},{}
    total=mapped=journals=0
    for family,expected_count in FAMILIES.items():
        dirs=(base,*extra) if family=="lsq_wrapper" else (base,)
        before=Counter()
        prior,mapping={},{}
        for d in dirs:
            part={n:v for n,v in previous[d][2].items() if n.startswith(f"tests/{family}/")}
            assert not prior.keys()&part.keys()
            prior.update(part)
            old_failures.update({n:m for n,m in failures(d).items() if n.startswith(f"tests/{family}/")})
            traces,per_node=histories(d,family)
            before.update(traces)
            assert not mapping.keys()&per_node.keys()
            mapping.update(per_node)
        current={n:v for n,v in nodes.items() if n.startswith(f"tests/{family}/")}
        assert current==prior and len(current)==expected_count
        old_nodes.update(prior)
        after,after_nodes=histories(run,family)
        assert before==after and mapping==after_nodes,(family,"raw public histories changed")
        count=sum(after.values())
        assert count==len(current) if family in JOURNALS else family in("age","cam","freelist") and not count
        records=sum(length*copies for (_,length),copies in after.items())
        total+=records
        mapped+=len(after_nodes)
        journals+=count
        reports.append(dict(family=family,prior=[d.name for d in dirs],cases=len(current),tests=dict(Counter("FAIL" if v else "PASS" for v in current.values())),
                            actual_raw_journals_equal=count,actual_raw_records_equal=records,exact_node_raw_mappings=len(after_nodes),
                            raw_trace_SHA256_multiset=[dict(sha256=digest,records=length,count=copies) for (digest,length),copies in sorted(after.items())]))
    assert nodes==old_nodes and failures(run)==old_failures and len(old_failures)==200
    assert (journals,total,mapped)==(1821,351451,1059)
    line_report=json.loads((run/"line-audit.json").read_text())
    native={r["dut"]:r for r in line_report["native"]}
    old_native={r["dut"]:r for r in json.loads((base/"line-audit.json").read_text())["native"]}
    builds={a["build"]["build_id"] for a in manifest["artifacts"] if a["kind"]=="native"}
    assert len(native)==len(old_native)==len(builds)==38 and native.keys()==old_native.keys()
    for dut,row in native.items():assert coverage_signature(row)==coverage_signature(old_native[dut]),(dut,"original DA universe/hits changed")
    groups={g["instance"]:g for g in json.loads((run/"execution/functional-coverage.json").read_text())["groups"]}
    old_groups={g["instance"]:g for g in json.loads((base/"execution/functional-coverage.json").read_text())["groups"]}
    assert groups.keys()==old_groups.keys() and len(groups)==76
    missing={}
    for instance,g in groups.items():
        p=g["points"][0]
        assert g["collection_complete"] and not p["unknown"] and not p["unmatched"]
        assert {k for k,c in p["counts"].items() if c}=={k for k,c in old_groups[instance]["points"][0]["counts"].items() if c}
        if instance.endswith("checked"):
            reached=groups[instance.removesuffix("checked")+"reached"]["points"][0]["counts"]
            assert all(c<=reached[k] for k,c in p["counts"].items())
        absent=[k for k,c in p["counts"].items() if not c]
        if absent:missing[instance]=absent
    for p in(run/"verification-source/tests").rglob("*.py"):assert not re.search(r"pytest\.(?:mark\.)?(?:xfail|skip)\b",p.read_text())
    domain_files=[ROOT/"results/lsq-serialized-mixed-01/ldu-rar-producer-audit-v3.json",
                  extra[0]/"ldu-rar-routing-audit-v2.json",extra[0]/"ldu-rar-coverage-audit-v1.json",
                  extra[1]/"ldu-mixed-audit-v1.json",extra[1]/"ldu-mixed-coverage-audit-v2.json"]
    assert all(p.is_file() for p in domain_files)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_progress_run_v10.py",ROOT/"tools/audit_progress_run_v7.py",ROOT/"tools/coverage_audit.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="NOT_PASS_1908_EXACT_NODES_RAW_FAILURES_AND_DA_RETAIN_DOMAIN_LIMITS",tests=manifest["tests"],source_snapshot_files=len(source),
                native_builds=38,functional_groups=76,actual_raw_journals_equal=journals,actual_raw_records_equal=total,exact_node_raw_mappings=mapped,
                basic87_without_persisted_cycle_journal=87,every_failure_primary_signature_equal=True,each_DUT_original_DA_universe_and_hits_equal=True,
                baseline_manifests={d.name:sha(d/"execution/manifest.json") for d in previous},producer_and_UID_reports={str(p.relative_to(ROOT)):sha(p) for p in domain_files},
                missing_semantic_scenarios=missing,families=reports,auditors=hashes,
                limits="Exact09+normalLDU18+newLDU8 union only; all200 ordinary FAIL kept. Two full mixed seeds with148 cancelled-slot witnesses do not finish all8 or STRESS. Necessary retained-LDU checks are not native DCache/LoadUnit/Backend proof; old interface CBO/RAR-as-C_NK streams stay restricted despite repeatability. Full legal joint capacity/CBO phases, other exact128, late local reset and final request/evidence audit remain. No final goal signoff.")
    out=run/"evidence-check-v11.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="families"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
