#!/usr/bin/env python3
"""516 actual cases: reference correction, exact old510 + new6, unchanged DA."""
import ast
import copy
import json
from pathlib import Path
import shutil

from audit_lsq_population_v1 import paths_by_node, same_raw
from audit_progress_run_v7 import failures, histories
from audit_progress_run_v8 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


def correction_ast(prior,current):
    relative = "lsqverify/load_queue/model.py"
    old,new = (ast.parse((r/"verification-source"/relative).read_text()) for r in (prior,current))
    targets = [n for n in ast.walk(new) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="mask" for t in n.targets)]
    originals = [n for n in ast.walk(old) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="mask" for t in n.targets)]
    assert len(targets)==len(originals)==1
    value = targets[0].value
    assert isinstance(value,ast.IfExp) and ast.dump(value.test)==ast.dump(ast.parse("inp.reset",mode="eval").body)
    assert isinstance(value.body,ast.Constant) and value.body.value==0
    assert ast.dump(value.orelse)==ast.dump(originals[0].value)
    targets[0].value = value.orelse
    assert ast.dump(old)==ast.dump(new), "only reset full-mask sampling may change semantic AST"
    return dict(file=relative,prior_sha256=sha(prior/"verification-source"/relative),current_sha256=sha(current/"verification-source"/relative),
                only_semantic_AST_change="mask = 0 if inp.reset else original_full_predicates",resetless_history_and_knownness_unchanged=True)


def audit():
    wrapper = ROOT/"results/lsq-expanded-16"
    load = ROOT/"results/lq-joint-impact-02"
    oldw,oldl = ROOT/"results/lsq-expanded-15",ROOT/"results/lq-expanded-06"
    joint = ROOT/"results/lsq-joint-capacity-04"
    metadata = {r:verify_common(r) for r in (wrapper,load,oldw,oldl,joint)}
    assert metadata[wrapper][0]["tests"]=={"PASS":269,"FAIL":48} and metadata[load][0]["tests"]=={"PASS":187,"FAIL":12}
    assert len(metadata[wrapper][2])==317 and len(metadata[load][2])==199
    assert failures(wrapper)==failures(oldw) and failures(load)==failures(oldl)
    wp,op,jp = (paths_by_node(r) for r in (wrapper,oldw,joint))
    assert set(metadata[oldw][2])==set(op) and set(wp)==set(op)|set(jp) and not set(op)&set(jp)
    records,case_evidence = 0,[]
    for node,path in sorted(wp.items()):
        old = op[node] if node in op else jp[node]
        assert metadata[wrapper][2][node]==metadata[oldw if node in op else joint][2][node]
        n = same_raw(path,old)
        records += n
        case_evidence.append(dict(nodeid=node,original=str(old.relative_to(ROOT)),current=str(path.relative_to(ROOT)),actual_raw_records_equal=n,current_sha256=sha(path)))
    lold,lnodes_old = histories(oldl,"load_queue")
    lnew,lnodes_new = histories(load,"load_queue")
    assert metadata[load][2]==metadata[oldl][2] and lold==lnew and lnodes_old==lnodes_new and sum(lnew.values())==199
    lrecords = sum(length*copies for (digest,length),copies in lnew.items())
    assert records==72918 and lrecords==28820
    native_evidence = []
    for before,after in ((oldw,wrapper),(oldl,load)):
        a,b = (json.loads((r/"line-audit.json").read_text())["native"] for r in (before,after))
        assert len(a)==len(b)==1 and a[0]["dut"]==b[0]["dut"]
        assert coverage_signature(a[0])==coverage_signature(b[0])
        native_evidence.append(dict(dut=b[0]["dut"],original_DA_total=b[0]["closure_line_total"],actual_DA_hit=b[0]["closure_line_hit"],new_hit=0,lost_hit=0,whole_original_universe_and_hit_set_equal=True))
    proof = json.loads((wrapper/"static-gap-proof-wrapper-v1.json").read_text())
    assert proof["raw_missing"]==proof["proven_line_count"]==7 and not proof["remaining_not_proven"]
    groups = {g["instance"]:g for g in json.loads((wrapper/"execution/functional-coverage.json").read_text())["groups"]}
    reached,checked = (groups["lsq.lsq_wrapper."+k]["points"][0]["counts"] for k in ("reached","checked"))
    assert len(reached)==len(checked)==82 and all(reached.values()) and sum(bool(v) for v in checked.values())==76
    assert not any(checked[k] for k in ("LSQ-STRESS.seeded","LSQ-STRESS.capacity","LSQ-STRESS.fair_drain"))
    ast_change = correction_ast(oldw,wrapper)
    assert sha(load/"verification-source/lsqverify/load_queue/model.py")==ast_change["current_sha256"]
    report = dict(run=wrapper.name,load_impact_run=load.name,status="NOT_PASS_516_cases_exact_old510_histories_plus_six_joint_cases_reference_AST_and_DA_verified",
                  tests={"PASS":456,"FAIL":60},wrapper_tests=metadata[wrapper][0]["tests"],load_tests=metadata[load][0]["tests"],
                  snapshot_files={r.name:len(metadata[r][1]) for r in (wrapper,load)},wrapper_raw_records=records,load_raw_records=lrecords,
                  all_510_original_raw_histories_and_60_failure_signatures_unchanged=True,six_new_joint_cases_same_as_frozen04=True,
                  total_raw_records=records+lrecords,correction=ast_change,native_DA=native_evidence,reached=82,checked=76,required=82,
                  cases=case_evidence,
                  limits="Original311 Wrapper and199 LoadQueue outcomes/raw input/pre/post/tick and primary failures equal prior frozen runs; six extra joint cases equal04. Only new reference semantic AST is reset?0:old_mask; resetless pipelines/startup knownness/compare masks not weakened. Exact per-source native DA sets/hits unchanged, seven Wrapper gaps reproved without denominator reduction. AllSTRESS reached now through real supplemental directed fairness, none checked; eight full-domain random failures and unfinished original obligations persist. Not whole38-DUT new regression or final signoff; timed-out lq-joint-impact-01 retained but not used as a complete run.")
    dest = wrapper/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__),ROOT/"tools/audit_progress_run_v7.py",ROOT/"tools/audit_progress_run_v8.py",ROOT/"tools/audit_lsq_population_v1.py",ROOT/"tools/audit_sq_initial.py")
    for f in files:
        target = dest/f.name
        if target.exists():
            assert sha(f)==sha(target)
        else:
            shutil.copy2(f,target)
    report["auditors"]={f.name:sha(dest/f.name) for f in files}
    out = wrapper/"joint-impact-audit-v1.json"
    if out.exists():
        assert json.loads(out.read_text())==report
    else:
        out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    audit()
