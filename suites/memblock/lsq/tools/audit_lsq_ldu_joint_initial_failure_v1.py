#!/usr/bin/env python3
"""Retain first6 driver timeouts: missing service for real repeated NC jobs."""
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_joint_pools_v1 import PhasedPools
from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def audit():
    run=ROOT/"results/lsq-ldu-joint-phases-01"
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"FAIL":6}
    cases=[]
    totals=Counter()
    for node,path in sorted(paths_by_node(run).items()):
        pools=PhasedPools()
        tail=[]
        for row in events(path):
            pools.step(row)
            tail.append(row)
            tail=tail[-300:]
        detail=pools.finish(passed=False)
        owed=[s for s in pools.history if pools.live(s) and s["kind"]=="load" and s["last"] and
              s["last"]["execution"]["replay_feedback"] and s["last"]["execution"]["causes"]==1 and
              s["attempts"] and s["attempts"][-1]["consumed"]]
        assert len(owed)==15 and all(r["checked"] and not r["input"]["bus"]["ready"] for r in tail)
        assert all(r["before"]["io_uncache_req_valid"] for r in tail)
        assert detail["snapshots"] and detail["counts"]["completed"]==1
        totals.update(detail["counts"])
        cases.append(dict(nodeid=node,raw_SHA256=sha(path),journal=str(path.relative_to(run)),counts=detail["counts"],
                          first_actual_snapshot=detail["snapshots"][0],terminal_expected_repeat_NC_UIDs=[s["uid"] for s in owed],
                          blocked_public_request_ticks=[tail[0]["post_tick"],tail[-1]["post_tick"]],
                          classification="DRIVER_ACCEPT_DISABLED_FOR_REAL_NEW_NC_OBLIGATIONS_NOT_RTL_DEADLOCK"))
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(run=run.name,status="SIX_DRIVER_SERVICE_FAILURES_RETAINED_FIRST_CAPACITY_PEAK_REAL_NO_FAIR_COMPLETION",tests=manifest["tests"],snapshot_files=len(source),counts=dict(totals),cases=cases,
                auditor_SHA256=sha(Path(__file__)),limits="All checked public cycles retain strict comparison. Last300 cycles hold a valid new external request with ready0;15 original NC owners consumed a job and replayed cause0 again. Fixing acceptance is external producer repair, not an RTL change or retroactive PASS. v1 pool deduplication is only used for the first original snapshot, not all post-redirect generations.")
    out=run/"ldu-joint-initial-failure-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
