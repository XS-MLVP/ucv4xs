#!/usr/bin/env python3
"""Retain one explicitly selected mixed baseline, not every attempt's native."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from audit_sq_initial import verify_common
from lsq_evidence_archive_v1 import ROOT,RESULTS,STORE,archive,decoded,digest,lock


def main(latest,predecessors):
    assert latest.startswith("lsq-normal-mixed-source-") and predecessors and latest not in predecessors
    assert all(n.startswith("lsq-normal-mixed-source-") and Path(n).name==n for n in predecessors+[latest])
    output=RESULTS/(latest+"-storage-v1.json")
    assert not output.exists()
    before=shutil.disk_usage(ROOT).free
    retained={};checked={}
    for name in predecessors+[latest]:
        run=RESULTS/name;manifest,_,_=verify_common(run)
        assert not(run/"storage-index-v1.json").exists() and not(run/"retired-intermediates-v1.json").exists()
        semantic=json.loads((run/"normal-mixed-summary-audit-v1.json").read_text())
        coverage=json.loads((run/"normal-mixed-coverage-audit-v1.json").read_text())
        assert semantic["tests"]==coverage["tests"]==manifest["tests"]
        if name==latest:
            uids=json.loads((run/"normal-mixed-UID-audit-v2.json").read_text())
            assert not uids["rejected_native_pass_seed_programs"] and len(uids["accepted_completed_seed_programs"])==2
        retained[name]={str(p.relative_to(run)):digest(p) for p in run.rglob("*") if p.is_file() and
                        (p.name in("pytest.xml","source-evidence.json","end-source-check.json","manifest.json") or
                         p.name.startswith("normal-mixed-") or p.suffix==".info" or p.name.endswith(".summary.json"))}
        checked[name]=manifest
    retired=[]
    for name in predecessors:
        run=RESULTS/name;rows=[]
        with lock(run):
            for artifact in checked[name]["artifacts"]:
                if artifact["kind"]!="native":continue
                path=Path(artifact["path"])
                assert path.is_relative_to(run/"execution/native") and path.name=="coverage.dat" and not path.is_symlink()
                assert digest(path)==artifact["sha256"]
                rows.append(dict(path=str(path.relative_to(ROOT)),SHA256=artifact["sha256"],bytes=path.stat().st_size,
                                 operation="discard_rebuildable_predecessor_native_no_archive_created"))
            index=dict(status="PREDECESSOR_NATIVE_DISCARDED_AFTER_AUDIT_NOT_ARCHIVED",run=name,selected_current_baseline=latest,files=rows,
                       retained="JUnit/FAILs/commands/frozen sources/stream summaries/UID rejections/LCOV/per-line rationale and denominator",
                       limits="The listed old native artifacts no longer exist and are deliberately not archived. Historical verify_common audits were performed before retirement; do not claim those full artifacts remain available. Reproduce the frozen attempt if needed. No result/FAIL/check is removed or changed.")
            with (run/"retired-intermediates-v1.json").open("x") as f:f.write(json.dumps(index,indent=2)+"\n")
            for row in rows:(ROOT/row["path"]).unlink()
            retired.extend(rows)
    native_archive=RESULTS/(latest+"-selected-native-v1.json")
    archive(native_archive,{latest})
    compressed=[]
    for name in predecessors+[latest]:
        run=RESULTS/name;path=run/"line-audit.json"
        assert path.is_file() and not path.is_symlink() and not(run/"reports-storage-index-v1.json").exists()
        with lock(run):
            h=digest(path);size=path.stat().st_size;obj=STORE/(h+".zst")
            if not obj.exists():
                temp=STORE/(".mixed-report-"+uuid.uuid4().hex)
                try:
                    with temp.open("xb") as f:subprocess.run(["zstd","-q","-9","--long=27","-c",str(path)],stdout=f,check=True)
                    assert decoded(temp)==(h,size);os.replace(temp,obj)
                finally:
                    if temp.exists():temp.unlink()
            else:assert decoded(obj)==(h,size)
            entry=dict(path=path.name,SHA256=h,bytes=size,object=str(obj.relative_to(ROOT)),object_SHA256=digest(obj),compressed_bytes=obj.stat().st_size)
            index=dict(format="lsq-reports-storage-index-v1",run=name,manifest_SHA256=digest(run/"execution/manifest.json"),files=[entry])
            with (run/"reports-storage-index-v1.json").open("x") as f:f.write(json.dumps(index,indent=2)+"\n")
            path.unlink();compressed.append(dict(run=name,**entry))
    for name,files in retained.items():
        assert all(digest(RESULTS/name/p)==h for p,h in files.items())
    # The predecessor comparison needs only its line inventory, NOT its
    # deliberately discarded native. Stage both report indices for the DA gate.
    recheck=subprocess.run([sys.executable,"-B","tools/lsq_evidence_archive_v1.py","audit",latest,predecessors[-1],"--",
        sys.executable,"-B","-c","import sys;sys.path.insert(0,'tools');from audit_lsq_normal_mixed_summary_v1 import audit;from audit_lsq_normal_mixed_uids_v2 import audit as uid;from audit_lsq_normal_mixed_coverage_v1 import audit as cov;audit(sys.argv[1]);assert uid(sys.argv[1]);cov(sys.argv[1],sys.argv[2])",latest,predecessors[-1]],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    gate_log=RESULTS/latest/"post-storage-gates-v1.txt"
    with gate_log.open("x") as f:f.write(recheck.stdout)
    assert recheck.returncode==0
    assert all(not(RESULTS/n/"line-audit.json").exists() for n in predecessors+[latest])
    assert all(not p.exists() for n in predecessors+[latest] for p in(RESULTS/n/"execution/native").rglob("coverage.dat"))
    seen=set();allocated=0
    for p in RESULTS.rglob("*"):
        if p.is_file():
            s=p.stat();key=(s.st_dev,s.st_ino)
            if key not in seen:seen.add(key);allocated+=s.st_blocks*512
    report=dict(status="SELECTED_MIXED_NATIVE_AND_REPORTS_COMPACTED_PREDECESSOR_NATIVE_DISCARDED",latest=latest,predecessors=predecessors,
                discarded_predecessor_native=retired,discarded_native_bytes=sum(r["bytes"] for r in retired),predecessor_native_archived=0,
                compressed_line_reports=compressed,selected_native_archive_report=native_archive.name,
                retained_metadata_files_SHA_checked=sum(len(x) for x in retained.values()),post_cleanup_semantic_UID_DA_gates_exit=0,
                post_cleanup_gate_log=str(gate_log.relative_to(ROOT)),post_cleanup_gate_log_SHA256=digest(gate_log),
                restored_temporary_native_or_line_report_paths_left=0,case_per_cycle_JSON=sum(1 for n in predecessors+[latest] for p in(RESULTS/n/"cases").rglob("*.jsonl")),
                case_waveforms=sum(1 for n in predecessors+[latest] for p in(RESULTS/n/"cases").rglob("*") if p.suffix in(".fst",".vcd")),
                results_unique_allocated_bytes=allocated,disk_free_before=before,disk_free_after=shutil.disk_usage(ROOT).free,
                limits="Explicit four/five-run selection only; no active run or other subsystem touched. Predecessor native artifacts were deleted, not archived; their JUnit/FAILs/summaries/source/LCOV remain. Latest complete checks restaged and rerun, then temporary raw removed. No claim that unretained per-cycle streams can be replayed offline.")
    with output.open("x") as f:f.write(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("discarded_predecessor_native","compressed_line_reports")},indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("latest");p.add_argument("--prior",action="append",required=True);a=p.parse_args();main(a.latest,a.prior)
