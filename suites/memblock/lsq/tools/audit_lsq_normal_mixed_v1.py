#!/usr/bin/env python3
"""New normal-CBO mixed prefixes: original obligations, exact128 ref boundary.

No private/actor/model-state/expected/change oracle. Keep every actual FAIL;
reference-domain exceptions are not misreported as observed RTL mismatches.
"""
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer,rob,sq
from audit_lsq_mixed_history_v2 import inspect as inspect_prefix
from audit_lsq_mixed_terminal_v3 import History,describe,zero
from audit_lsq_population_v1 import events,paths_by_node
from audit_sq_initial import ROOT,sha,verify_common


def reference_boundary(path):
    st=sh=0
    loads={}
    for r in events(path):
        i,p,o=r["input"],r["before"],r["after"]
        if i["reset"]:continue
        for d in i["dispatch"]:
            if not d["valid"]:continue
            if d["need_alloc"]==2:st+=1
            else:loads[rob(d["rob"])]=dict(exclusive_sq=st,dispatch_tick=r["post_tick"],rob=d["rob"])
        if "error" in r:
            assert "query and physical window outside documented SQ age domain" in r["error"]
            candidates=[]
            for lane,q in enumerate(i["queries"]):
                if not q["valid"]:continue
                code=sq(q["sq"])
                if (code-sh)%256!=128:continue
                rq=i["rar_queries"][lane]
                load=loads[rob(rq["rob"])]
                assert load["exclusive_sq"]==st==sh+128 and code==st%256
                candidates.append(dict(lane=lane,load=load,absolute_SQ_dequeue=sh,absolute_SQ_tail=st,
                                       original_exclusive_boundary=load["exclusive_sq"],raw_query_pointer=code,virtual_occupancy=128,
                                       physical_issue_window=[sh,sh+64],post_tick=r["post_tick"]))
            assert len(candidates)==1
            return dict(observed="reference rejects exact128 virtual-boundary query before comparing a new response",witness=candidates[0],
                        scope="original allocation obeys the explicit0..128 queue-count contract, but Forward reference only accepts distance<128. Normal end-to-end enqueue admission and exact-half-ring expected behavior still require a narrow source/producer check and a real minimal case. This is NOT an observed bad RTL Forward response, and no existing strict comparison is suppressed.")
        sh+=(pointer(o,"io_sqDeqPtr_")-sh)%256
        if o["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:st=sh+(pointer(o,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")-sh)%256
    raise AssertionError("reference-boundary case had no retained terminal exception")


def data_invalid_identity(path):
    h=History()
    for r in events(path):h.step(r)
    f=h.final
    r=f["row"]
    pre,post=r["before"],r["after"]
    p="io_forward_0_s2Resp_bits_dataInvalid_"
    assert post[p+"valid"]
    actual=pointer(post,p+"bits_")
    slot=post[p+"bits_value"]
    delta=(pointer(post,"io_sqDeqPtr_")-pointer(pre,"io_sqDeqPtr_"))%256
    head=h.sh-delta
    expected=head+(slot-head)%64
    source=next(s for s in f["eligible_stores"] if s["pos"]==expected)
    old=f["previous"]
    load=h.owner(old["input"]["rar_queries"][0]["rob"],"load")
    assert expected<load["bound"] and source["order"]<load["order"] and actual!=expected%256
    return dict(issue="FWD-SQID-001",actual_dependency_pointer=actual,expected_current_original_pointer=expected%256,
                original_source=describe(source),load=describe(load),post_tick=r["post_tick"],physical_dequeue=head,
                scope="actual missing-data response names the wrong full SQ generation for its selected current physical slot. No following replay or ISA consequence is fabricated.")


def audit():
    run=ROOT/"results/lsq-normal-cbo-01"
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":6,"FAIL":8} and len(nodes)==14
    producer=json.loads((run/"cbo-producer-audit-v2.json").read_text())
    assert producer["counts"]["required_normal_cases_admitted"]==14 and not producer["counts"]["non_normal_CBO_STA_writes"]
    paths=paths_by_node(run)
    counts,cases=Counter(),[]
    for seed in range(28928,28936):
        node=next(n for n in paths if "::test_normal_cbo_full_domain_" in n and n.endswith(f"[{seed}]"))
        path=paths[node]
        assert nodes[node]
        detail=inspect_prefix(path)
        assert detail["counts"]["raw_records"]<610
        counts.update(detail["counts"])
        extra=None
        if seed==28934:extra=reference_boundary(path)
        elif seed==28930:extra=data_invalid_identity(path)
        elif seed==28932:
            h=History()
            for row in events(path):h.step(row)
            extra=zero(h)
            assert extra["zero"]["address"]["size"]==4 and extra["zero"]["address"]["mask"]==65535 and extra["zero"]["address"]["wline"]
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),**detail,additional_original_observation=extra,
                          classification="reference_exact128_domain_gap_not_RTL_response_failure" if seed==28934 else "retained_strict_staged_or_original_effect_FAIL"))
    assert counts["raw_records"]==1686 and counts["allocated"]==2619 and counts["completed"]==166 and counts["cancelled"]==1651 and counts["failed_live"]==802
    assert counts["load_bus_fires"]+counts["store_bus_fires"]==196==counts["sid_responses"]+counts["pending_external_responses"]
    joint=json.loads((run/"joint-history-audit-v4.json").read_text())
    assert joint["actual_fair_complete_stages"]==18
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files=(Path(__file__),ROOT/"tools/audit_lsq_mixed_history_v2.py",ROOT/"tools/audit_lsq_mixed_terminal_v3.py")
    for f in files:
        target=dest/f.name
        if target.exists():assert sha(target)==sha(f)
        else:shutil.copy2(f,target)
    report=dict(run=run.name,status="eight_NEW_normal_CBO_mixed_prefixes_original_obligations_audited_NOT_PASS_one_reference_domain_gap",tests=manifest["tests"],snapshot_files=len(source),
                counts=dict(counts),cases=cases,joint_normal_directed_report_sha256=sha(run/"joint-history-audit-v4.json"),normal_CBO_producer_report_sha256=sha(run/"cbo-producer-audit-v2.json"),
                auditors={f.name:sha(dest/f.name) for f in files},
                limits="CBO197 actual packages in all14 use normal aligned16/QB/fullmask/wline. Eight mixed seeds still stop before600 random edges, NONE reaches fair/drain or full cancelled-slot restoration. Their2619 UIDs=166 complete+1651 cancel+802 failed-live and196 real bus requests=189 real responses+7 pending remain explicit. Four SID/Cache counterexamples plus current-generation SQID and phase-only zero observations are retained; one exact128 reference-domain exception is not counted as a bad RTL response. Metadata admission is not whole Backend legal-domain proof. Six clean normal joint positives are separately audited, not replacements for failing full-domain seeds. No RTL edits, hidden FAIL or STRESS checked acceptance.")
    out=run/"normal-mixed-history-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
