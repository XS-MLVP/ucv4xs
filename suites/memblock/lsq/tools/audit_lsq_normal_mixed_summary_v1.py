#!/usr/bin/env python3
"""Audit frozen normal-mixed attempts without promoting FAIL prefixes to signoff.

Native I/O checks execute online. Compact windows, UIDs and external job
witnesses are independently cross-checked here, not unretained raw replay.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT,sha,verify_common


def audit(name):
    assert name.startswith("lsq-normal-mixed-source-")
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert len(nodes)==8 and all(node.startswith("tests/normal_mixed/test_original_seeds.py::") for node in nodes)
    checker=run/"verification-source/tests/normal_mixed/check.py"
    tree=ast.parse(checker.read_text())
    assert not any(isinstance(n,ast.Attribute) and n.attr in("model","last_change","expected_before","expected_after","dut","_instances") for n in ast.walk(tree))
    assert not any(isinstance(n,ast.ImportFrom) and n.module and (n.module.startswith("lsqverify") or n.module.startswith("tests")) for n in ast.walk(tree))
    baseline=json.loads((ROOT/"results/lsq-progress-regression-12/source-evidence.json").read_text())["files"]
    refs={k:v for k,v in baseline.items() if k.startswith("lsqverify/")}
    assert len(refs)==149 and all(source[k]==v for k,v in refs.items())
    assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst")) and not list((run/"cases").rglob("*.vcd"))
    cases=[];seen=set();seeds=set();counts=Counter();native_records=0;bytes_total=0;completed=0
    for path in sorted((run/"cases").rglob("normal-mixed-summary.json")):
        d=json.loads(path.read_text());node=d["nodeid"];seed=d["seed"]
        assert node in nodes and node not in seen and seed in range(0x7100,0x7108) and seed not in seeds
        seen.add(node);seeds.add(seed)
        assert d["passed"]==bool(not nodes[node])
        assert d["original_types"]==["cached","nc_load","mmio_load","io_load","store","nc_store","io_store","cbo"]
        assert d["original_weights"]==[30,12,3,2,36,6,4,7] and 0<=d["random_steps_completed"]<=600
        native=json.loads(path.with_name("lsq_wrapper.summary.json").read_text())
        assert native["nodeid"]==node and not native["trace_enabled"] and not native["trace_truncated"] and not native["saved_trace_bytes"]
        online=d["independent_source_checks"];c=online["counts"];window=online["window"]
        assert window["last_tick"]-window["first_tick"]==2*(c["program_requests"]-1)
        assert native["terminal"]["post_tick"]==window["last_tick"] and native["records"]==c["program_requests"]+11
        assert len(d["public_UIDs"])==d["counts"]["allocated"]==sum(d["kinds"].values())
        assert [s["uid"] for s in d["public_UIDs"]]==list(range(1,len(d["public_UIDs"])+1))
        assert len({s["uid"] for s in online["observed_UIDs"]})==len(online["observed_UIDs"])
        job_counts={}
        for kind in("cache","tlb"):
            pool=d[kind+"_sources"];jobs=pool["jobs"];pc=pool["counts"]
            assert [j["job"] for j in jobs]==list(range(1,len(jobs)+1))
            assert pc.get("accepted_external_jobs",0)==len(jobs)
            returned=sum(j["returned_edge"] is not None for j in jobs)
            assert pc.get("actual_interface_returns",0)==returned and len(pool["pending_job_IDs"])+returned==len(jobs)
            assert all(j["accepted_edge"]<j["returned_edge"] for j in jobs if j["returned_edge"] is not None)
            assert pc.get("peak_live",0)<=16
            for j in jobs:
                assert j["identity"] in range(16) and j["UIDs"] and len(j["UIDs"])==len(set(j["UIDs"]))
                assert all(uid in range(1,len(d["public_UIDs"])+1) for uid in j["UIDs"])
            assert c.get(kind+"_declared_jobs",0)-c.get(kind+"_actual_returns",0)==online["pending_external_jobs"][kind]
            if d["passed"]:
                assert len(jobs)==returned==c.get(kind+"_declared_jobs",0)==c.get(kind+"_actual_returns",0)
            job_counts[kind]=dict(declared=len(jobs),returned=returned,pending=len(pool["pending_job_IDs"]))
        if d["passed"]:
            completed+=1
            assert d["random_steps_completed"]==600 and online["last_source_error"] is None and online["original_full_output_error"] is None
            assert not any(online["pending_external_jobs"].values())
            assert d["counts"]["allocated"]==d["counts"].get("completed",0)+d["counts"].get("cancelled",0)
            assert all(s["structure_complete"] or s["local_abort"] is not None for s in d["public_UIDs"])
        counts.update(c);native_records+=native["records"];bytes_total+=path.stat().st_size
        cases.append(dict(seed=seed,nodeid=node,result="FAIL" if nodes[node] else "PASS",random_steps=d["random_steps_completed"],
                          summary=str(path.relative_to(run)),summary_SHA256=sha(path),summary_bytes=path.stat().st_size,
                          native_records=native["records"],runtime_stream_SHA256=native["streamed_SHA256"],source_error_tick=(online["last_source_error"] or {}).get("tick"),
                          original_full_output_error=online["original_full_output_error"],error=d["error"],external_jobs=job_counts))
    assert seen==set(nodes) and seeds==set(range(0x7100,0x7108))
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="ACTUAL_EIGHT_SEEDS_AUDITED_WITH_RETAINED_FAILS_NO_SIGNOFF" if any(nodes.values()) else "ACTUAL_EIGHT_SEEDS_COMPLETED_UPSTREAM_VECTOR_ROUTE_STILL_UNPROVEN_NOT_GOAL_SIGNOFF",
                run=name,tests=manifest["tests"],source_files=len(source),unchanged_shared_reference_files=len(refs),
                fully_completed_seed_programs=completed,native_records=native_records,online_counts=dict(counts),
                per_cycle_JSON=0,waveforms=0,case_summary_bytes=bytes_total,cases=cases,failures=failures(run),auditor_SHA256=sha(Path(__file__)),
                limits="Only completed seed programs have terminal signoff within this profile. Failed prefixes are not full 600/fair or full normal producer admission. Declared external Cache/TLB/ROB events and initial QB vector route assumptions are not native upstream proofs. Digests and compact failure edges do not permit offline per-cycle replay. Original 82-feature table, all historical FAILs and final whole-goal audit remain required.")
    output=run/"normal-mixed-summary-audit-v1.json"
    if output.exists():assert json.loads(output.read_text())==report
    else:output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("cases","failures")},ensure_ascii=False,indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");audit(p.parse_args().name)
