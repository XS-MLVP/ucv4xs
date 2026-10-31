#!/usr/bin/env python3
"""Check unchanged strict FAIL streams and additive normal-reuse cleanup."""
import ast
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT,sha,verify_common


def cases(run):
    return {d["seed"]:(d,p) for p in(run/"cases").rglob("normal-mixed-summary.json") for d in[json.loads(p.read_text())]}


def main():
    old,new=(ROOT/"results"/("lsq-normal-mixed-source-"+n) for n in("03","04"))
    _,a,_=verify_common(old);manifest,b,_=verify_common(new)
    assert manifest["tests"]=={"FAIL":6,"PASS":2}
    actor="tests/normal_mixed/owners.py"
    def methods(run):
        t=ast.parse((run/"verification-source"/actor).read_text())
        cls=next(n for n in t.body if isinstance(n,ast.ClassDef))
        return {n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    before,after=methods(old),methods(new)
    assert set(after)-set(before)=={"restore_cancelled_slots"} and not(set(before)-set(after))
    assert all(before[k]==after[k] for k in before),"normal random planner/source methods must not change"
    unchanged=[k for k,v in a.items() if (k.startswith('lsqverify/') or k.startswith("tests/lsq_wrapper/") or k=="tests/normal_mixed/sources.py")]
    assert all(a[k]==b[k] for k in unchanged)
    x,y=cases(old),cases(new);assert set(x)==set(y)==set(range(0x7100,0x7108))
    rows=[]
    for seed,(d,p) in y.items():
        previous,pp=x[seed]
        assert d["passed"]==previous["passed"] and d["error"]==previous["error"]
        assert d["independent_source_checks"]["last_source_error"] is None
        n,o=(json.loads(q.with_name("lsq_wrapper.summary.json").read_text()) for q in(p,pp))
        if not d["passed"]:
            assert n["streamed_SHA256"]==o["streamed_SHA256"] and n["records"]==o["records"]
            assert d["public_UIDs"]==previous["public_UIDs"]
            mode="actual_entire_original_strict_FAIL_input_pre_post_check_stream_SHA_equal"
        else:
            fields=("uid","order","kind","subtype","position","structure_complete","local_abort","fault","rob_cancelled")
            assert [{k:s[k] for k in fields} for s in d["public_UIDs"][:len(previous["public_UIDs"])]]==[{k:s[k] for k in fields} for s in previous["public_UIDs"]]
            assert len(d["public_UIDs"])>len(previous["public_UIDs"])
            assert d["random_steps_completed"]==previous["random_steps_completed"]==600
            assert d["counts"]["normal_same_slot_replacement_gate_completed"]==1
            mode="same_unchanged_random_source_methods_and_original_UID_prefix_plus_additional_normal_reuse; NOT an observed per-cycle prefix-SHA claim"
        rows.append(dict(seed=seed,result="PASS" if d["passed"] else "FAIL",evidence=mode,prior_UIDs=len(previous["public_UIDs"]),current_UIDs=len(d["public_UIDs"]),
                         prior_native_records=o["records"],current_native_records=n["records"],current_runtime_SHA256=n["streamed_SHA256"]))
    uids=json.loads((new/"normal-mixed-UID-audit-v2.json").read_text())
    assert uids["accepted_completed_seed_programs"]==[28929,28933] and not uids["rejected_native_pass_seed_programs"]
    dest=new/"evidence-auditors";dest.mkdir(exist_ok=True);target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="SIX_ORIGINAL_FAIL_STREAMS_EXACT_AND_ONLY_POST_RANDOM_REUSE_EXTENDED_NO_SIGNOFF",run=new.name,prior_run=old.name,tests=manifest["tests"],
                unchanged_shared_or_inherited_source_files=len(unchanged),unchanged_controller_methods=sorted(before),added_controller_methods=["restore_cancelled_slots"],
                all_original_six_FAIL_stream_SHA_equal=True,passed_seed_cleanup_extensions=2,normal_cancelled_slot_witnesses=sum(len(c["same_slot_normal_completion_witnesses"]) for c in uids["cases"] if c["terminal_evidence_accepted"]),
                cases=sorted(rows,key=lambda c:c["seed"]),auditor_SHA256=sha(Path(__file__)),
                limits="Failed seed streams are observed complete hashes, not unretained raw replay. Passing seeds prove frozen planner/source identity and original public UID prefix, not a retained/observed per-cycle prefix SHA. Original random source domain and six strict FAILs are not filtered. Initial vector QB route and full-goal boundaries remain unproven.")
    output=new/"normal-mixed-preserved-prefix-audit-v1.json"
    if output.exists():assert json.loads(output.read_text())==report
    else:output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2))


if __name__=="__main__":main()
