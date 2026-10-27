import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Actual original8 LDU-mixed outcomes, retained source contracts and UID effects.

Never equate two passing seeds with the required all-seed/STRESS signoff.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_cbo_serialization_v2 import inspect as serialization
from audit_lsq_ldu_mixed_history_v1 import inspect as history
from audit_lsq_ldu_mixed_pipeline_v1 import inspect as pipeline
from audit_lsq_normal_cbo_v3 import packages, prefix
from audit_lsq_population_v1 import paths_by_node
from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name=="lsq-ldu-mixed-02"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":2,"FAIL":6} and len(nodes)==8
    prior=ROOT/"results/lsq-ldu-mixed-01"
    old,old_source,old_nodes=verify_common(prior)
    assert old["tests"]=={"FAIL":8} and old_nodes.keys()==nodes.keys()
    old_failures=failures(prior)
    assert all("multiple values for keyword argument 'tick'" in f for f in old_failures.values())
    differences={k for k in source if source[k]!=old_source[k]}
    assert source.keys()==old_source.keys() and differences=={"tests/lsq_wrapper/ldu_mixed_owners.py"}
    old_tree=ast.parse((prior/"verification-source/tests/lsq_wrapper/ldu_mixed_owners.py").read_text())
    new_tree=ast.parse((run/"verification-source/tests/lsq_wrapper/ldu_mixed_owners.py").read_text())
    stripped=0
    for call in ast.walk(old_tree):
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=="emit":
            removed=[k for k in call.keywords if k.arg=="tick"]
            stripped+=len(removed)
            call.keywords=[k for k in call.keywords if k.arg!="tick"]
    assert stripped==2 and ast.dump(old_tree,include_attributes=False)==ast.dump(new_tree,include_attributes=False)
    frozen=run/"verification-source"
    constants={target.id:ast.literal_eval(n.value) for n in ast.walk(ast.parse((frozen/"tests/lsq_wrapper/mixed_owners.py").read_text()))
               if isinstance(n,ast.Assign) for target in n.targets if isinstance(target,ast.Name) and target.id in("KINDS","WEIGHTS")}
    assert constants==dict(KINDS=("cached","nc_load","mmio_load","io_load","store","nc_store","io_store","cbo"),WEIGHTS=(30,12,3,2,36,6,4,7))
    assert "range(0x7100,0x7108)" in (frozen/"tests/lsq_wrapper/test_ldu_mixed.py").read_text()
    assert all(not(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="run") for n in ast.walk(new_tree))
    command=json.loads((run/"command.json").read_text())["command"]
    assert not any(a=="-k" or a.startswith("--deselect") for a in command)
    totals,stage_counts,producer=Counter(),Counter(),Counter()
    cases=[]
    paths,old_paths=paths_by_node(run),paths_by_node(prior)
    actual_failures=failures(run)
    assert set(paths)==set(nodes)
    for seed in range(28928,28936):
        node=next(n for n in nodes if n.endswith(f"[{seed}]"))
        path=paths[node]
        legal=serialization(path)
        assert not legal["violations"]
        producer.update(legal["counts"])
        producer["actual_CBO_STA_packages_bound_to603_pins"]+=packages(path)
        detail=history(path,passed=not nodes[node])
        stages=pipeline(path,passed=not nodes[node])
        totals.update(detail["counts"])
        stage_counts.update(stages["counts"])
        assert detail["counts"]["raw_records"]==stages["counts"]["raw_records"]
        same=prefix(old_paths[node],path)
        if not nodes[node]:
            assert seed in(28929,28933) and detail["counts"]["raw_records"]>=610
        elif seed in(28928,28931,28932):
            assert len(detail["independent_terminal_counterexamples"])==1
            assert detail["independent_terminal_counterexamples"][0]["obligation"]=="original_Cache_error_held_WB"
            assert detail["independent_terminal_counterexamples"][0]["ready"] is False
        elif seed==28935:
            assert detail["counts"]["invalid_SQ_release_not_semantic_completion"]==1
            assert detail["independent_terminal_counterexamples"][0]["obligation"]=="original_complete_SQ_prefix"
        else:
            assert seed in(28930,28934) and not detail["independent_terminal_counterexamples"]
            assert "io_flushSbuffer_valid" in detail["terminal_runtime_error"]
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),pytest_result="FAIL" if nodes[node] else "PASS",
                          original01_driver_error_prefix_equal_records=same,actual_JUnit_failure=actual_failures.get(node),
                          CBO_permission_gate=legal,retained_LDU_pipeline_contract=stages,original_effects=detail))
    assert totals["raw_records"]==3397 and totals["allocated"]==746==totals["completed"]+totals["cancelled"]+totals["failed_live"]
    assert (totals["completed"],totals["cancelled"],totals["failed_live"])==(359,374,13)
    assert not totals["pending_external_responses"] and totals["sid_responses"]==111
    assert stage_counts["actual_MMIO_replay_S2_no_query"]==25 and stage_counts["C_NK_bound_to_real_STA"]==3
    full=[c for c in cases if c["pytest_result"]=="PASS"]
    assert sum(c["original_effects"]["counts"]["cancelled_same_slot_new_UID_completed"] for c in full)==148
    native=json.loads((run/"line-audit.json").read_text())
    assert all(not g["hit"] for g in native["functional"] if g["instance"].endswith("checked"))
    repo=ucv_paths.source_path_for(ROOT) / 'src/main/scala/xiangshan'
    source_files=[repo/"mem/pipeline/NewLoadUnit.scala",repo/"mem/pipeline/NewStoreUnit.scala",repo/"mem/MemBlock.scala",repo/"backend/rob/RobBundles.scala"]
    ldu=source_files[0].read_text()
    assert all(binding in ldu for binding in("val canNukeQuery = !isMMIOReplay && !isPrefetch","cause(C_WF) := false.B",
               "val s3RevokeReplay = causeOrR","val rollbackLevel = Mux(matchInvalid, RedirectLevel.flush, RedirectLevel.flushAfter)"))
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    auditor_hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_lsq_ldu_mixed_history_v1.py",ROOT/"tools/audit_lsq_ldu_mixed_pipeline_v1.py",ROOT/"tools/audit_lsq_cbo_serialization_v2.py"):
        copy=dest/file.name
        if copy.exists():assert sha(copy)==sha(file)
        else:shutil.copy2(file,copy)
        auditor_hashes[file.name]=sha(file)
    report=dict(run=name,status="TWO_REAL_FULL_SEED_PASSES_SIX_STRICT_FAILS_RETAINED_NOT_ALL_SEED_STRESS_OR_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),
                original_eight_type_weights={k:list(v) for k,v in constants.items()},counts=dict(totals),retained_pipeline_counts=dict(stage_counts),CBO_producer_counts=dict(producer),cases=cases,
                actually_complete_seeds=[28929,28933],complete_seed_cancelled_same_slot_new_UID_witnesses=148,
                verification_01_rejection=dict(run=prior.name,tests=old["tests"],kind="driver_emit_duplicate_tick_TypeError_NOT_RTL_FAIL",
                                               repair="only remove 2 duplicate emit tick kwargs; AST gate proves all other code identical, original raw prefixes preserved"),
                open_producer_sources=[dict(path=str(p.relative_to(repo)),sha256=sha(p)) for p in source_files],auditors=auditor_hashes,
                own_native=dict(top=native["native"][0]["line_hit"],top_total=114,closure=native["native"][0]["closure_line_hit"],closure_total=59602),
                limits="Actual600-random/fair/restore PASS only for seeds28929/28933;148 cancelled original UIDs have real same-physical-slot new UID completions. Six other required seeds retain strict stopped prefixes, including 3 held-WB Cache faults,2 flush-phase mismatches and1 invalid SQ release that is NOT counted as semantic completion. Necessary retained LDU timing/revoke/NC/MMIO/cause/rollback gates plus real CBO NoSpec/BlockBack/package checks are not native LoadUnit/DCache/Backend verification; external event bits absent at Wrapper are checked only for allowed retained consequences. No8-seed/STRESS checked, complete capacity, late local reset, original09 scope expansion or goal completion claim.")
    out=run/"ldu-mixed-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
