#!/usr/bin/env python3
"""Independent exclusive-tail raw history, no DUT/reference/actor-state oracle."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from audit_lsq_bus_v2 import pointer, rob, sq
from audit_lsq_ldu_mixed_history_v1 import inspect as effect_history
from audit_lsq_ldu_mixed_pipeline_v1 import inspect as pipeline_history
from audit_lsq_population_v1 import events, paths_by_node, replay_metadata
from audit_progress_run_v7 import RAW, failures
from audit_raw_trace import expected_payload, match, sq_raw, younger
from audit_sq_initial import ROOT, sha, verify_common


def checked_rows(path):
    rows=list(events(path))
    last=None
    for r in rows:
        assert r["input"]==r["post_input"] and r["pre_tick"]+1==r["post_tick"]
        assert last is None or last+2==r["post_tick"]
        assert "error" not in r and r["checked"]==(True if "nodeid" in r else not_reset(r))
        last=r["post_tick"]
    return rows


def not_reset(row):return not row["input"]["reset"]


def raw_signature(rows):
    first=next(r for r in rows if any(q["valid"] for q in r["input"]["queries"]))
    lane,q=next((n,q) for n,q in enumerate(first["input"]["queries"]) if q["valid"])
    full=q["paddr"]==0xB00000
    start=sq_raw(first["input"]["head"])
    return ("full56" if full else "boundary",lane,start,(sq_raw(q["sq"])-start)%256)


def inspect_raw(path):
    rows=checked_rows(path)
    signature=raw_signature(rows)
    head=sequence=0
    entries={}
    jobs=[]
    positives=set()
    counts=Counter(raw_records=len(rows))
    for edge,r in enumerate(rows):
        i,pre,post=r["input"],r["before"],r["after"]
        if i["reset"]:
            assert not entries and not jobs
            continue
        assert not i["redirect"]["valid"] and not any((*i["revoke_last"],*i["revoke_older"]))
        delta=(sq_raw(i["head"])-head)%256
        assert delta<=8
        head+=delta
        before=dict(entries)
        removed=[uid for uid,s in entries.items() if s["end"]<=head]
        for uid in removed:
            assert uid in positives,"record was released without any original matching rollback"
            del entries[uid]
        counts["address_prefix_original_record_releases"]+=len(removed)
        for lane,store in enumerate(i["stores"]):
            if not store["valid"]:continue
            eligible=[s for s in before.values() if s["query"]["data_valid"] and younger(s["query"]["rob"],store["rob"]) and match(s["query"],store)]
            winner=min(eligible,key=lambda s:(rob(s["query"]["rob"])-rob(store["rob"]))%640,default=None)
            jobs.append(dict(due=edge+2,lane=lane,query=winner,store=store))
            counts["original_STA_inputs"]+=1
        due=[job for job in jobs if job["due"]==edge]
        jobs=[job for job in jobs if job["due"]>edge]
        expected={job["lane"]:job for job in due if job["query"] is not None}
        for lane,got in enumerate(post["rollbacks"]):
            assert got["valid"]==(lane in expected)
            if lane in expected:
                job=expected[lane]
                assert got==expected_payload(job["query"]["query"],job["store"])
                positives.add(job["query"]["uid"])
                counts["original_delayed_identity_rollbacks"]+=1
        if due:counts["negative_original_STA_results"]+=sum(job["query"] is None for job in due)
        assert post["training"]["valid"]==bool(expected)
        if expected:
            job=min(expected.values(),key=lambda j:(rob(j["query"]["query"]["rob"]),j["lane"]))
            q,s=job["query"]["query"],job["store"]
            assert post["training"]==dict(valid=True,ftq_value=q["ftq"]["value"],ftq_offset=q["ftq_offset"],is_rvc=q["is_rvc"],
                                           store_ftq_value=s["ftq_value"],store_ftq_offset=s["ftq_offset"],store_is_rvc=s["is_rvc"])
            counts["original_MDP_training_outputs"]+=1
        for lane,q in enumerate(i["queries"]):
            if not q["valid"]:continue
            d=(sq_raw(q["sq"])-head)%256
            assert 0<d<=128
            if not pre["ready"][lane]:
                assert len(before)==56
                counts["actual_full56_query_rejections"]+=1
                continue
            sequence+=1
            entries[sequence]=dict(uid=sequence,query=q,end=head+d)
            assert len(entries)<=56
            counts["accepted_original_RAW_records"]+=1
            counts["accepted_exact128_records"]+=d==128
            if len(entries)==56:
                assert post["full"]
                counts["full56_original_record_epochs"]+=1
    assert not entries and not jobs and len(positives)==sequence
    assert not rows[-1]["after"]["full"] and all(rows[-1]["after"]["ready"])
    if signature[0]=="full56":assert sequence==112 and counts["actual_full56_query_rejections"]==2 and counts["full56_original_record_epochs"]==2
    else:assert sequence==1
    counts["original_records_individually_witnessed_and_head_released"]=sequence
    return dict(signature=signature,counts=dict(counts),identity_reuse_scope="full56 old and new generations each individually observed; no public RAW slot index, so no invented per-UID physical-slot map" if signature[0]=="full56" else "original Load identity retained until exact exclusive address prefix")


def replay_signature(rows,*,with_wake=True):
    first=next(r for r in rows if any(q["valid"] for q in r["input"]["enqueues"]))
    lane,q=next((n,q) for n,q in enumerate(first["input"]["enqueues"]) if q["valid"])
    start=sq_raw(first["input"]["address_ready"])
    wake="pool_credit" if any(not r["input"]["raw_full"] for r in rows[rows.index(first):]) else "address_prefix"
    return ("Replay",lane,start,(sq_raw(q["uop"]["sq"])-start)%256,*((wake,) if with_wake else ()))


def inspect_replay(path):
    rows=checked_rows(path)
    signature=replay_signature(rows)
    req=slot=None
    awake=fired=feedback=False
    unlock_tick=None
    counts=Counter(raw_records=len(rows))
    for r in rows:
        i,pre,post,t=r["input"],r["before"],r["after"],r["post_tick"]
        if i["reset"]:
            assert req is None
            continue
        assert not i["redirect"]["valid"] and not i["sq_empty"]
        for q in i["enqueues"]:
            if not q["valid"]:continue
            if not q["replay_feedback"]:
                assert req is None and q["causes"]==1<<10
                req=q
                counts["original_cause10_allocations"]+=1
            else:
                assert fired and not feedback and q["slot"]==slot and not q["need_replay"] and not q["causes"]
                assert q["uop"]==req["uop"] and q["vaddr"]==req["vaddr"]
                feedback=True
                counts["original_slot_feedbacks"]+=1
        if req is not None:
            d=(sq_raw(req["uop"]["sq"])-sq_raw(i["address_ready"]))%256
            assert d<=128
            unlock=not i["raw_full"] or d==0
            if unlock and not awake:
                awake=True
                unlock_tick=t
                counts["wake_by_actual_external_credit" if not i["raw_full"] else "wake_by_actual_address_prefix"]+=1
            if not awake:
                assert not any(post[f"io_replay_{b}_valid"] for b in range(3))
                counts["blocked_edges_with_original_pending_addresses"]+=1
            for phase,pins in(("before",pre),("after",post)):
                for b in range(3):
                    p=f"io_replay_{b}_"
                    if not pins[p+"valid"]:continue
                    assert awake and t>=unlock_tick+2 and not feedback
                    mask=((1<<(1<<((req["uop"]["operation"]>>1&7)&3)))-1)<<(req["vaddr"]%16)&65535
                    replay_metadata(pins,p+"bits_",dict(fullva=req["vaddr"],execution={**req,"mask":mask}))
                    current=pins[p+"bits_replayQueueIdx"]
                    assert slot is None or slot==current
                    slot=current
                    assert slot%3==b and pins[p+"bits_entrance"]==8 and not pins[p+"bits_uncacheReplay"]
                    if phase=="before" and i["ready"][b]:
                        assert not fired
                        fired=True
                        counts["actual_original_grants"]+=1
                    if i["raw_full"] and d>0:counts["already_unblocked_not_relocked_by_rawFull"]+=1
    assert req is not None and fired and feedback and not rows[-1]["after"]["io_replayAllocate"]
    assert counts["original_cause10_allocations"]==counts["actual_original_grants"]==counts["original_slot_feedbacks"]==1
    return dict(signature=signature,counts=dict(counts),original_actual_slot=slot,unlock_tick=unlock_tick)


def inspect_wrapper(path):
    rows=checked_rows(path)
    effects=effect_history(path,passed=True)
    stages=pipeline_history(path,passed=True)
    records={}
    loads={}
    end=0
    last=None
    head=0
    counts=Counter()
    grant_tick=feedback_tick=last_STA_tick=None
    second_half_fires=[]
    stores={}
    pending_s2=[]
    for r in rows:
        i,pre,post,t=r["input"],r["before"],r["after"],r["post_tick"]
        if i["reset"]:continue
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert d["flows"]==1
            if d["need_alloc"]==2:
                stores[len(stores)]=dict(rob=d["rob"])
                end+=1
            else:
                k=120*int(d["load_start"]["flag"])+d["load_start"]["value"]
                loads[k]=dict(rob=d["rob"],end=end,executions=0)
        ready=pointer(pre,"io_issuePtrExt_")
        delta=(ready-head)%256
        assert delta<=2
        head+=delta
        for k in list(records):
            if records[k]["end"]<=head:
                del records[k]
                counts["real_address_prefix_RAW_record_releases"]+=1
        for lane,q in enumerate(i["raw_queries"]):
            if not q["valid"]:continue
            k=next(k for k,s in loads.items() if s["rob"]==q["rob"])
            owner=loads[k]
            assert q["data_valid"] and sq(q["sq"])==owner["end"]%256
            if owner["end"]>head:
                if pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"]:
                    assert k not in records
                    records[k]=owner
                    counts["real_RAW_record_allocations"]+=1
                    counts["real_exact128_RAW_record_allocations"]+=owner["end"]-head==128
                else:
                    assert len(records)==56 and k==56
                    counts["real_RAW_full57th_query_rejections"]+=1
            else:counts["retry_no_pending_older_address_no_RAW_allocation"]+=1
        for s,lane in pending_s2:
            a=i["attributes"][lane]
            assert a["memory"] and not a["nc"] and not a["mmio"] and a["last"]
            s["s2"]=t
        pending_s2=[]
        for lane,a in enumerate(i["addresses"]):
            if not a["valid"]:continue
            s=next(s for s in stores.values() if s["rob"]==a["rob"])
            s["address"]=a
            pending_s2.append((s,lane))
            if s is stores[127]:last_STA_tick=t
        for q in i["loads"]:
            e=q["execution"]
            if not e["valid"]:continue
            k=120*int(e["uop"]["lq"]["flag"])+e["uop"]["lq"]["value"]
            loads[k]["executions"]+=1
            if e["need_replay"]:
                assert k==56 and e["causes"]==1<<10
                counts["original_S3_RAW_CAPACITY_feedbacks"]+=1
            elif e["replay_feedback"]:
                assert k==56
                feedback_tick=t
        for b in range(3):
            p=f"io_replay_{b}_"
            if pre[p+"valid"]:
                assert len(records)<56 or head>=128
                if i["replay_ready"][b]:
                    assert grant_tick is None
                    grant_tick=t
                    counts["real_original_RAW_CAPACITY_grants"]+=1
        sq_head=pointer(pre,"io_sqDeqPtr_")
        for b in range(2):
            if pre[f"io_sbuffer_req_{b}_valid"] and i["sbuffer_ready"][b] and sq_head>=64:second_half_fires.append(t)
        assert not any(post[f"io_nuke_rollback_{b}_valid"] for b in range(2)) and not post["io_mdpTrain_valid"]
        last=t
    assert len(stores)==128 and len(loads)==57 and not records
    assert counts["real_RAW_record_allocations"]==counts["real_address_prefix_RAW_record_releases"]==56
    assert counts["real_RAW_full57th_query_rejections"]==counts["original_S3_RAW_CAPACITY_feedbacks"]==counts["real_original_RAW_CAPACITY_grants"]==1
    assert loads[56]["executions"]==2 and all(s["executions"]==1 for k,s in loads.items() if k!=56)
    wake="pool_credit" if loads[0]["end"]==127 else "address_prefix"
    assert (grant_tick<last_STA_tick)==(wake=="pool_credit")
    assert feedback_tick is not None and second_half_fires and feedback_tick<min(second_half_fires)
    assert effects["counts"]["allocated"]==effects["counts"]["completed"]==185 and not effects["counts"]["cancelled"]
    assert effects["counts"]["Sbuffer_fragment_fires"]==128 and not effects["independent_terminal_counterexamples"]
    assert stages["counts"]["native_next_edge_same_lane_feedbacks"]==58 and stages["counts"]["checked_actual_S3_cause_10"]==1
    return dict(wake=wake,counts=dict(counts),original_effects=effects,retained_LDU_pipeline=stages,
                actual_grant_tick=grant_tick,last_original_STA_tick=last_STA_tick,original_S3_feedback_tick=feedback_tick,
                first_second_half_Sbuffer_fire=min(second_half_fires),scope="full128 SQ and full56 RAW only; not joint all-pool/CBO/full-random signoff")


def raw_prefix(old,new):
    a,b=list(events(old)),list(events(new))
    assert len(a)<=len(b)
    assert all({k:r[k] for k in RAW if k in r}=={k:s[k] for k in RAW if k in s} for r,s in zip(a,b))
    return len(a)


def audit(name):
    assert name=="lsq-raw-exclusive-04"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":63} and len(nodes)==63 and not any(nodes.values())
    prior=ROOT/"results/lsq-raw-exclusive-02"
    old,old_sources,old_nodes=verify_common(prior)
    assert old["tests"]=={"PASS":27,"FAIL":36} and old_nodes.keys()==nodes.keys()
    failed=failures(prior)
    assert len(failed)==36 and all(m in("ValueError: query SQ pointer outside unambiguous legal half-ring","ValueError: ambiguous half-ring SQ age") for m in failed.values())
    diffs={k for k in old_sources if source[k]!=old_sources[k]}
    assert diffs=={"tests/sq_endpoint/conftest.py"}
    for f in("test_raw_boundary.py","test_replay_raw_boundary.py","test_wrapper_raw_boundary.py"):
        assert source["tests/sq_endpoint/"+f]==old_sources["tests/sq_endpoint/"+f]
    totals=Counter()
    leaves=[]
    for filename,inspect,signature in(("load_queue_raw.jsonl",inspect_raw,raw_signature),("load_queue_replay.jsonl",inspect_replay,replay_signature)):
        files=sorted((run/"cases").rglob(filename))
        assert len(files)==(21 if filename.startswith("load_queue_raw") else 36)
        old_paths=sorted((prior/"cases").rglob(filename))
        for path in files:
            result=inspect(path)
            totals.update(result["counts"])
            key=signature(list(events(path)))
            matches=[p for p in old_paths if signature(list(events(p)),**({"with_wake":False} if filename=="load_queue_replay.jsonl" else {}))==
                     (key[:-1] if filename=="load_queue_replay.jsonl" else key)]
            assert matches
            prefixes=[raw_prefix(p,path) for p in matches if any("error" in r for r in events(p))] if any("error" in r for r in events(matches[0])) else []
            if not prefixes:
                matches=[p for p in matches if signature(list(events(p)))==key]
                assert len(matches)==1 and len(list(events(matches[0])))==raw_prefix(matches[0],path)
            leaves.append(dict(journal=str(path.relative_to(run)),sha256=sha(path),input_bound_identity=result,
                               old_prefix_records=prefixes,exact_leaf_node_mapping_claim=False,
                               mapping_limit="early leaf journals have no nodeid; complete public-input signature/multiset, not invented exact pytest node association"))
    parents=[]
    old_paths=paths_by_node(prior)
    for node,path in sorted(paths_by_node(run).items()):
        result=inspect_wrapper(path)
        totals.update(result["counts"])
        parents.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),old_stopped_prefix_records=raw_prefix(old_paths[node],path),details=result))
    assert len(parents)==6 and totals["accepted_original_RAW_records"]==354 and totals["original_delayed_identity_rollbacks"]==378
    assert totals["actual_original_grants"]==totals["original_slot_feedbacks"]==36
    assert totals["real_RAW_record_allocations"]==336 and totals["real_RAW_full57th_query_rejections"]==6
    # Keep the failed setup iterations without feeding them to the strict no-error common gate.
    rejected=[]
    for old_name,reason in(("lsq-raw-exclusive-01","collection import-path ModuleNotFoundError; no native functional result"),("lsq-raw-exclusive-03","21 RAW fixture setup TypeError from extra RawCoverage spec argument;42 other real PASS, no RAW functional signoff")):
        p=ROOT/"results"/old_name
        end=json.loads((p/"end-source-check.json").read_text())
        assert end["all_current_launch_files_match_snapshot"]
        rejected.append(dict(run=old_name,reason=reason,console_sha256=sha(p/"console.log"),frozen_sources=len(end["files"])))
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_raw_trace.py",ROOT/"tools/audit_lsq_ldu_mixed_history_v1.py",ROOT/"tools/audit_lsq_ldu_mixed_pipeline_v1.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="63_REAL_ENDPOINT_PASSES_INDEPENDENT_ORIGINAL_HISTORY_NOT_WHOLE_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),counts=dict(totals),
                parents_original_UID_completed=1110,leaf_cases=leaves,wrapper_cases=parents,retained_legacy=dict(run=prior.name,tests=old["tests"],all36_failures_are_reference_half_ring_rejections=True),
                retained_setup_errors=rejected,auditors=hashes,limits="Native63 endpoint scope only. Legacy36 reference FAILs and setup failures kept. Three leaf/Wrapper DUTs use explicit opt-in endpoint models; all shared references, RTL, normal masks/knownness/safety stay frozen. Leaf public records have no slot index/nodeid, so no invented physical-slot UID bijection or exact leaf node map. Wrapper185 original UIDs/case complete, real Store/Sbuffer/SQ/Load/slot distinct; normal full LDU producer necessary retained contracts only, no native LoadUnit/DCache/Backend claim. All-pool capacity/CBO phases, other failure domains and full random/final audit remain.")
    out=run/"exclusive-history-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("leaf_cases","wrapper_cases")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
