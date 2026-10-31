#!/usr/bin/env python3
"""Expanded default-OFF regression: old2203 plus real S4/reset/mixed attempts.

Compare actual outcomes, streamed hashes, compact terminal witnesses and each
original DUT DA universe; never call a failed mixed prefix complete stress.
"""
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_progress_run_v7 import JOURNALS,failures
from audit_progress_run_v10 import coverage_signature
from audit_progress_summary_v13 import baseline_metadata,payload,nodes
from audit_sq_initial import ROOT,sha
from run_summary import aggregate


BASELINES=("lsq-progress-regression-12","lsq-s4-precise-03","lsq-local-reset-retained-02","lsq-normal-mixed-source-04")
SUPPORT={f"tests/normal_mixed/test_source_ledger.py::test_external_jobs_keep_refused_miss_merge_and_repay_before_tag_reuse[{kind}]":False for kind in("cache","tlb")}


def witnesses(run):
    out={}
    for pattern in("s4-precise*summary.json","local-reset*summary.json","normal-mixed-summary.json"):
        for path in(run/"cases").rglob(pattern):
            d=json.loads(path.read_text());node=d["nodeid"]
            assert node not in out;out[node]=(path.name,sha(path))
    return out


def audit():
    run=ROOT/"results/lsq-progress-regression-13"
    manifest=json.loads((run/"execution/manifest.json").read_text())
    assert manifest["state"]=="committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"]))==artifact["sha256"]
        if artifact["kind"]=="native":assert all(sha(Path(p))==h for p,h in artifact["build"]["files"].items())
    current=nodes(run)
    launch=json.loads((run/"source-aggregate-launch.json").read_text());end=json.loads((run/"source-aggregate-end.json").read_text())
    assert end.pop("launch_and_end_equal") and launch==end
    assert not(run/"verification-source").exists() and not(run/"source-evidence.json").exists() and not(run/"end-source-check.json").exists()
    assert len(current)==2312
    collection=json.loads((ROOT/"results/lsq-progress-regression-13-collection-v1.json").read_text())
    assert collection["total_collected"]==2312 and collection["prior_nodes"]==2203 and collection["added_nodes"]==109 and not collection["removed_prior_nodes"]
    cmd=json.loads((run/"command.json").read_text())["command"]
    assert "tests" in cmd and not any(a in("-k","--lsq-trace","--lsq-waves") or a.startswith("--deselect") for a in cmd)
    policy=json.loads((run/"trace-policy.json").read_text())
    assert not policy["per_cycle_JSON"] and not policy["waveforms"]
    assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst")) and not list((run/"cases").rglob("*.vcd"))
    expected_nodes={};expected_failures={};expected_streams={k:Counter() for k in JOURNALS};prior_lines={};old_points={};expected_witnesses={}
    expected_sources={};baseline_tests={}
    for name in BASELINES:
        prior=ROOT/"results"/name;m,files,ns=baseline_metadata(prior)
        assert not(expected_nodes.keys()&ns.keys());expected_nodes.update(ns);expected_failures.update(failures(prior));baseline_tests[name]=m["tests"]
        for k,v in files.items():
            if k.startswith('lsqverify/'):expected_sources.setdefault(k,set()).add(v)
        for family,names in JOURNALS.items():
            for filename in names:
                for p in(prior/"cases").rglob(Path(filename).with_suffix(".summary.json").name):
                    s=json.loads(p.read_text());assert not s["trace_enabled"] and not s["trace_truncated"] and not s["saved_trace_bytes"]
                    expected_streams[family][(s["streamed_SHA256"],s["serialized_bytes"])]+=1
        for row in json.loads(payload(prior,"line-audit.json"))["native"]:
            for file,(h,lines) in coverage_signature(row).items():
                group=prior_lines.setdefault(row["dut"],{})
                if file in group:assert group[file][0]==h and group[file][1].keys()==dict(lines).keys()
                dst=group.setdefault(file,(h,{}))[1]
                for n,hit in lines:dst[n]=dst.get(n,False) or hit
        for group in json.loads((prior/"execution/functional-coverage.json").read_text())["groups"]:
            old_points.setdefault(group["instance"],set()).update(k for k,n in group["points"][0]["counts"].items() if n)
        for node,w in witnesses(prior).items():assert node not in expected_witnesses;expected_witnesses[node]=w
    assert len(expected_nodes)==2310 and not(expected_nodes.keys()&SUPPORT.keys())
    expected_nodes.update(SUPPORT)
    assert current==expected_nodes and failures(run)==expected_failures and len(expected_failures)==227
    assert manifest["tests"]==dict(Counter("FAIL" if x else "PASS" for x in current.values()))=={"PASS":2085,"FAIL":227}
    assert len(expected_sources)==149 and all(len(v)==1 for v in expected_sources.values())
    assert aggregate((k,next(iter(v))) for k,v in expected_sources.items())==launch["groups"]['lsqverify']
    matched=records=avoided=summary_bytes=0;families=[]
    for family,names in JOURNALS.items():
        actual=Counter();n=0
        for filename in names:
            for p in(run/"cases").rglob(Path(filename).with_suffix(".summary.json").name):
                d=json.loads(p.read_text());assert not d["trace_enabled"] and not d["trace_truncated"] and not d["saved_trace_bytes"]
                actual[(d["streamed_SHA256"],d["serialized_bytes"])]+=1;n+=1;records+=d["records"];avoided+=d["serialized_bytes"];summary_bytes+=p.stat().st_size
        assert actual==expected_streams[family],(family,"serialized runtime stream changed; investigate without weakening the gate")
        matched+=n;families.append(dict(journal_family=family,matching_streams=n))
    assert matched==2223==2312-87-2
    actual_lines={r["dut"]:coverage_signature(r) for r in json.loads((run/"line-audit.json").read_text())["native"]}
    assert actual_lines.keys()==prior_lines.keys() and len(actual_lines)==38
    for dut,files in actual_lines.items():
        assert files.keys()==prior_lines[dut].keys()
        for file,(h,lines) in files.items():assert(h,dict(lines))==prior_lines[dut][file]
    groups=json.loads((run/"execution/functional-coverage.json").read_text())["groups"]
    assert len(groups)==76
    for group in groups:
        p=group["points"][0]
        assert group["collection_complete"] and not p["unknown"] and not p["unmatched"]
        assert {k for k,n in p["counts"].items() if n}==old_points[group["instance"]]
    actual_witnesses=witnesses(run)
    assert actual_witnesses==expected_witnesses and len(actual_witnesses)==107
    accepted_mixed=[]
    for p in(run/"cases").rglob("normal-mixed-summary.json"):
        d=json.loads(p.read_text())
        if d["passed"]:
            assert d["random_steps_completed"]==600 and d["counts"]["normal_same_slot_replacement_gate_completed"]==1
            accepted_mixed.append(d["seed"])
    assert set(accepted_mixed)=={28929,28933}
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True)
    for file in(Path(__file__),):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
    report=dict(status="ACTUAL2312_DEFAULT_OFF_REPEATABILITY_NOT_PASS_227_FAILURES_RETAINED",run=run.name,tests=manifest["tests"],source_file_count=launch["file_count"],
                source_aggregate_launch_end_equal=True,complete_new_source_inventory_persisted=False,complete_new_source_snapshot_retained=False,
                native_builds=38,functional_groups=76,original2203_nodes_retained=2203,added_nodes=109,pure_source_fixture_tests_not_native=2,
                actual_equal_stream_digests=matched,actual_stream_records=records,compact_terminal_witnesses_SHA_equal=107,
                per_cycle_JSON_files=0,waveform_files=0,avoided_raw_bytes=avoided,summary_bytes=summary_bytes,unchanged_shared_reference_files=149,
                each_DUT_original_DA_universe_and_actual_hit_union_equal=True,every_failure_primary_equal=True,
                baselines=list(BASELINES),baseline_tests=baseline_tests,families=families,accepted_mixed_profile_seeds=sorted(accepted_mixed),auditor_SHA256=sha(Path(__file__)),
                limits="Actual committed outcomes only. New source retention is counts/aggregate fingerprints, not a complete per-file path/hash inventory or copied source tree; reproduction relies on workspace and selected retained baseline sources. Complete streamed hashes and compact terminal witnesses prove rerun/diagnostic equivalence, NOT independent offline replay of unretained per-cycle raw. Historical87 basic cases have no per-case journal, and two pure source-fixture tests have no native DUT: neither is counted as a matched stream. Mixed six strict FAILs, initial vector QB upstream-route admission, other128/old generations, local serial reset/late ack and full-request final audit remain. No whole-goal signoff or change of historical source-domain restrictions.")
    output=run/"evidence-check-summary-v15.json"
    if output.exists():assert json.loads(output.read_text())==report
    else:output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":audit()
