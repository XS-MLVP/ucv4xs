#!/usr/bin/env python3
"""Preserve v1 schema/producer rejection; use strict source-correct S3 gate.

Reuse v1 unchanged independent RAW/Replay/Store effect cores. Dependencies are
adapted explicitly, never rewrite a raw input or observed DUT value to pass.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import json
from pathlib import Path
import shutil

import audit_sq_exclusive_history_v1 as cores
from audit_sq_exclusive_pipeline_v1 import inspect as strict_pipeline
from audit_lsq_population_v1 import events, paths_by_node
from audit_progress_run_v7 import RAW, failures
from audit_sq_initial import ROOT, sha, verify_common


def checked_wrapper_rows(path):
    rows=list(events(path))
    last=None
    for row in rows:
        assert "nodeid" in row and row["pins"]==row["post_pins"]
        assert row["pre_tick"]+1==row["post_tick"] and (last is None or last+2==row["post_tick"])
        assert row["checked"] and "error" not in row and not row["explicitly_unimplemented_outputs"]
        last=row["post_tick"]
    return rows


@contextmanager
def wrapper_dependencies():
    previous_rows,previous_pipeline=cores.checked_rows,cores.pipeline_history
    cores.checked_rows,cores.pipeline_history=checked_wrapper_rows,strict_pipeline
    try:yield
    finally:cores.checked_rows,cores.pipeline_history=previous_rows,previous_pipeline


def audit(name):
    assert name=="lsq-raw-exclusive-05"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":63} and len(nodes)==63 and not any(nodes.values())
    prior=ROOT/"results/lsq-raw-exclusive-02"
    old,old_sources,old_nodes=verify_common(prior)
    assert old["tests"]=={"PASS":27,"FAIL":36} and old_nodes.keys()==nodes.keys()
    failed=failures(prior)
    assert len(failed)==36 and all(m in("ValueError: query SQ pointer outside unambiguous legal half-ring","ValueError: ambiguous half-ring SQ age") for m in failed.values())
    changed={k for k in old_sources if source[k]!=old_sources[k]}
    assert changed=={"tests/sq_endpoint/conftest.py","tests/sq_endpoint/test_wrapper_raw_boundary.py"}
    frozen04=ROOT/"results/lsq-raw-exclusive-04"
    _,source04,nodes04=verify_common(frozen04)
    assert nodes04==nodes and {k for k in source04 if source[k]!=source04[k]}=={"tests/sq_endpoint/test_wrapper_raw_boundary.py"}
    totals=Counter()
    leaves=[]
    for filename,inspect,signature in(("load_queue_raw.jsonl",cores.inspect_raw,cores.raw_signature),("load_queue_replay.jsonl",cores.inspect_replay,cores.replay_signature)):
        files=sorted((run/"cases").rglob(filename))
        assert len(files)==(21 if filename=="load_queue_raw.jsonl" else 36)
        old_paths=sorted((prior/"cases").rglob(filename))
        paths04=sorted((frozen04/"cases").rglob(filename))
        for path in files:
            result=inspect(path)
            totals.update(result["counts"])
            key=signature(list(events(path)))
            matches=[p for p in old_paths if signature(list(events(p)),**({"with_wake":False} if filename=="load_queue_replay.jsonl" else {}))==
                     (key[:-1] if filename=="load_queue_replay.jsonl" else key)]
            assert matches
            prefixes=[cores.raw_prefix(p,path) for p in matches if any("error" in r for r in events(p))]
            if not prefixes:
                matches=[p for p in matches if signature(list(events(p)))==key]
                assert len(matches)==1 and len(list(events(matches[0])))==cores.raw_prefix(matches[0],path)
            same04=[p for p in paths04 if signature(list(events(p)))==key]
            assert len(same04)==1 and len(list(events(same04[0])))==cores.raw_prefix(same04[0],path)
            leaves.append(dict(journal=str(path.relative_to(run)),sha256=sha(path),input_signature=result,old02_stopped_prefix_records=prefixes,
                               raw04_complete_history_equal=True,exact_leaf_node_mapping_claim=False))
    parents=[]
    before04=paths_by_node(frozen04)
    for node,path in sorted(paths_by_node(run).items()):
        with wrapper_dependencies():result=cores.inspect_wrapper(path)
        totals.update(result["counts"])
        a,b=list(events(before04[node])),list(events(path))
        assert len(a)==len(b)
        input_changes=Counter()
        changed_observations=Counter()
        for oldrow,newrow in zip(a,b):
            assert oldrow["post_tick"]==newrow["post_tick"]
            x=json.loads(json.dumps(oldrow["input"]))
            y=newrow["input"]
            for lane,packet in enumerate(x["loads"]):
                e=packet["execution"]
                if not e["valid"]:continue
                for field in("aligned_type","last_beat"):
                    target=y["loads"][lane]["execution"][field]
                    input_changes[field]+=e[field]!=target
                    e[field]=target
                target=y["loads"][lane]["update_address"]
                input_changes["update_address"]+=packet["update_address"]!=target
                packet["update_address"]=target
            assert x==y,"stimulus changed beyond the three source-required S3 fields"
            for phase in("before","after"):
                assert oldrow[phase].keys()==newrow[phase].keys()
                changed_observations.update(pin for pin in oldrow[phase] if oldrow[phase][pin]!=newrow[phase][pin])
        assert input_changes["aligned_type"]==58 and input_changes["update_address"]==1
        parents.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),S3_only_input_changes_from04=dict(input_changes),
                            actual_output_field_changes_from04=dict(changed_observations),details=result))
    assert len(parents)==6 and totals["accepted_original_RAW_records"]==354 and totals["original_delayed_identity_rollbacks"]==378
    assert totals["actual_original_grants"]==totals["original_slot_feedbacks"]==36
    assert totals["real_RAW_record_allocations"]==336 and totals["real_RAW_full57th_query_rejections"]==6
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_sq_exclusive_history_v1.py",ROOT/"tools/audit_sq_exclusive_pipeline_v1.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="63_REAL_ENDPOINT_PASSES_ORIGINAL_UIDS_AND_SOURCE_S3_CHECKED_NOT_FULL_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),counts=dict(totals),
                parents_original_UID_completed=1110,leaf_cases=leaves,wrapper_cases=parents,auditors=hashes,
                retained_legacy=dict(run=prior.name,tests=old["tests"],all36_reference_rejections=True),
                retained_failures=["01 collection import-path ModuleNotFoundError,436 frozen sources; no native functional result",
                                   "03 had42 real PASS/21 RAW fixture setup TypeErrors due extra spec argument,439 frozen sources; no RAW signoff",
                                   "04 actual63 PASS/441 frozen sources; six Wrapper normal-producer claims rejected for default size/lastBeat and Replay updateAddrValid. Only those three fields changed for05; raw before/after differences enumerated, not hidden",
                                   "history-v1 first rejected Wrapper's schema (no post_input); exploration then also rejected its default S3 metadata through prior pipeline-v1. v2 adapts only row schema and uses new strict aligned source S3 gate, preserving all independent RAW/Replay/Store cores"],
                limits="57 leaf logs have no nodeid/public RAW record slot; complete public-input signatures/raw prefixes checked, no invented exact leaf-node or per-UID slot map. Wrapper6x185 original UIDs complete with real Store effects and original capacity Replay slots. New S3 gate is aligned nonalias cached hit/cause10 only, not full mixed/NC/MMIO/S4 or native LDU/DCache. Shared references/RTL/knownness/masks/safety unchanged; all-pool capacity/CBO, complete random and final audit remain.")
    report=json.loads(json.dumps(report))
    out=run/"exclusive-history-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("leaf_cases","wrapper_cases")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
