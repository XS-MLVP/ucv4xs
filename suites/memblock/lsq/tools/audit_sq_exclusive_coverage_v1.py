#!/usr/bin/env python3
"""Each DUT's own complete DA inventory and endpoint-loop set deltas, no merges."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_mixed_coverage_v2 import classify as classify_wrapper
from audit_progress_run_v10 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


def classify(native):
    result=copy.deepcopy(native)
    if result["dut"]=="lsq_wrapper":
        top=result["uncovered"]
        result["uncovered"]=[]
        result,_=classify_wrapper(result)
        result["uncovered"]=top
        for gap in top:
            assert gap["line"] in(1502,1504,1505,1507,1508)
            gap.update(features=["LSQ-BUS.serial","LSQ-BUS.resp_route"],classification="missing_scenario_of_existing_feature",
                       semantic_gap="本cached/RAW容量端点无外部Uncache事务；原总线串行请求选择/待返回/响应清忙状态缺情形。需NC/MMIO/IO原UID、真实ack/resp/fire和原SID复用；不是本体不可达，也不拿本体满行等同业务验收")
    counts=Counter()
    for entry in(result,*result.get("dependencies",[])):
        lines=(ROOT/entry["source"]).read_text().splitlines()
        for gap in entry["uncovered"]:
            n=gap["line"]
            assert lines[n-1].strip()==gap["text"]
            assert gap["classification"]=="missing_scenario_of_existing_feature" and gap["features"] and gap["semantic_gap"]
            gap.update(original_context=[dict(line=k,text=lines[k-1]) for k in range(max(1,n-2),min(len(lines),n+2)+1)],
                       reachability="not_excluded",scope="THIS_DUT_AND_RUN_OWN_NATIVE_DA_NO_LEAF_OR_PRIOR_INTERFACE_NUMERATOR")
            counts[Path(entry["source"]).name]+=1
    assert sum(counts.values())==result["closure_line_total"]-result["closure_line_hit"]
    return result,counts


def audit(name):
    assert name in("lsq-raw-exclusive-05","lsq-raw-exclusive-06")
    dirs=[ROOT/"results/lsq-raw-exclusive-02",ROOT/"results/lsq-raw-exclusive-05"]
    if name.endswith("06"):dirs.append(ROOT/"results"/name)
    rounds=[]
    previous=None
    for run in dirs:
        manifest,source,_=verify_common(run)
        report=json.loads((run/"line-audit.json").read_text())
        natives={n["dut"]:n for n in report["native"]}
        assert set(natives)=={"load_queue_raw","load_queue_replay","lsq_wrapper"}
        current={}
        details=[]
        for dut,native in sorted(natives.items()):
            sig=coverage_signature(native)
            current[dut]=sig
            mapped,counts=classify(native)
            added=lost=0
            added_lines=[]
            if previous is not None:
                old=previous[dut]
                assert sig.keys()==old.keys()
                for path,(digest,now) in sig.items():
                    before_digest,before=old[path]
                    assert digest==before_digest and dict(before).keys()==dict(now).keys()
                    a,b=dict(before),dict(now)
                    source_lines=(ROOT/path).read_text().splitlines()
                    for line,hit in b.items():
                        if hit and not a[line]:
                            added+=1
                            added_lines.append(dict(source=path,line=line,text=source_lines[line-1].strip()))
                        lost+=int(a[line] and not hit)
                assert not lost,(run.name,dut,"old actual DA hit lost")
            details.append(dict(dut=dut,top_hit=native["line_hit"],top_total=native["line_total"],closure_hit=native["closure_line_hit"],closure_total=native["closure_line_total"],
                                own_remaining=sum(counts.values()),missing_by_source=dict(counts),new_hits=added,old_hit_loss=lost,added_lines=added_lines,native_classified=mapped))
        previous=current
        rounds.append(dict(run=run.name,tests=manifest["tests"],snapshot_files=len(source),DUTs=details))
    assert rounds[1]["tests"]=={"PASS":63}
    if name.endswith("06"):assert rounds[2]["tests"]=={"PASS":75}
    outdir=ROOT/"results"/name
    dest=outdir/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_lsq_ldu_mixed_coverage_v2.py",ROOT/"tools/audit_progress_run_v10.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    result=dict(run=name,status="EACH_OWN_DA_GAP_CLASSIFIED_AND_ACTUAL_LOOP_DELTA_NO_DENOMINATOR_REMOVAL",rounds=rounds,auditors=hashes,
                limits="Endpoint scope only.02 retains36 reference FAILs;05 parent S3 fields corrected and independently checked. Native set deltas are exact per DUT, no leaf/Wrapper merge or semantic signoff from a line hit.06 if present adds independent Replay120 capacity owners from3 input lanes, not a real Wrapper all-pool/CBO proof. Shared sources and old RTL failures remain; full random, S3-complete mixed producer, legal joint capacity/CBO and final audit still required.")
    out=outdir/"exclusive-coverage-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==result
    else:out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(dict(run=name,status=result["status"],rounds=[dict(run=r["run"],tests=r["tests"],DUTs=[{k:v for k,v in d.items() if k not in("native_classified","added_lines")} for d in r["DUTs"]]) for r in rounds]),indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
