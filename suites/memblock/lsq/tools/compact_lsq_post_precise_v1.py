#!/usr/bin/env python3
"""Explicit post-audit retention, not blanket retention of every old native run.

Keep three selected baseline native payloads compressed; discard superseded
native .dat only for three named completed predecessors. FAILs/LCOV/snapshots/
commands/UID summaries stay. Large line inventories are small lossless objects.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from audit_sq_initial import verify_common
from lsq_evidence_archive_v1 import ROOT, RESULTS, STORE, archive, decoded, digest, lock


BASELINES=("lsq-progress-regression-12","lsq-s4-precise-03","lsq-local-reset-retained-02")
OBSOLETE=("lsq-s4-precise-01","lsq-s4-precise-02","lsq-local-reset-retained-01")


def pack_report(run,path):
    with lock(run):
        assert not (run/"reports-storage-index-v1.json").exists()
        h=digest(path);size=path.stat().st_size;obj=STORE/(h+".zst")
        if not obj.exists():
            tmp=STORE/(".report-"+uuid.uuid4().hex)
            try:
                with tmp.open("xb") as f:subprocess.run(["zstd","-q","-9","--long=27","-c",str(path)],stdout=f,check=True)
                assert decoded(tmp)==(h,size);os.replace(tmp,obj)
            finally:
                if tmp.exists():tmp.unlink()
        else:assert decoded(obj)==(h,size)
        entry=dict(path=path.name,SHA256=h,bytes=size,object=str(obj.relative_to(ROOT)),object_SHA256=digest(obj),compressed_bytes=obj.stat().st_size)
        index=dict(format="lsq-reports-storage-index-v1",run=run.name,manifest_SHA256=digest(run/"execution/manifest.json"),files=[entry])
        with (run/"reports-storage-index-v1.json").open("x") as f:f.write(json.dumps(index,indent=2)+"\n")
        assert digest(path)==h;path.unlink()
        return dict(run=run.name,**entry)


def main():
    output=RESULTS/"storage-post-precise-v1.json";assert not output.exists()
    before=shutil.disk_usage(ROOT).free
    gates={"lsq-progress-regression-12":"evidence-check-summary-v13.json","lsq-s4-precise-03":"s4-precise-summary-audit-v3.json",
           "lsq-local-reset-retained-02":"local-reset-audit-v2.json"}
    manifests={};protected={};candidates=[]
    for name in(*BASELINES,*OBSOLETE):
        run=RESULTS/name
        manifest,_,_=verify_common(run);manifests[name]=manifest
        assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst")) and not list((run/"cases").rglob("*.vcd"))
        protected[name]={str(p.relative_to(run)):digest(p) for p in(run/"pytest.xml",run/"source-evidence.json",run/"end-source-check.json",run/"execution/manifest.json")}
        if name in BASELINES:assert (run/gates[name]).is_file()
        else:
            for a in manifest["artifacts"]:
                if a["kind"]!="native":continue
                path=Path(a["path"])
                assert path.is_relative_to(run/"execution/native") and path.name=="coverage.dat" and not path.is_symlink() and digest(path)==a["sha256"]
                candidates.append(dict(run=name,path=str(path.relative_to(ROOT)),SHA256=a["sha256"],bytes=path.stat().st_size))
    # Select final baselines only; no new cycle trace is generated or archived.
    archive(RESULTS/"evidence-native-baselines-post-precise-v1.json",set(BASELINES))
    reports=[]
    for name in(*BASELINES,*OBSOLETE):
        run=RESULTS/name;path=run/"line-audit.json"
        if path.stat().st_size>1024*1024:reports.append(pack_report(run,path))
    retirement=RESULTS/"retire-native-predecessors-post-precise-v1.json"
    plan=dict(status="DISCARD_ONLY_NAMED_SUPERSEDED_NATIVE_DAT_KEEP_RESULTS_LCOV_FAILS_SOURCES",files=candidates,
              original_paths_restorable=False,kept="original manifest/JUnit/FAIL/source/command/LCOV/semantic summary and lossless line inventory remain; regenerate native .dat with frozen run if needed")
    with retirement.open("x") as f:f.write(json.dumps(plan,indent=2)+"\n")
    for entry in candidates:
        path=ROOT/entry["path"];assert digest(path)==entry["SHA256"];path.unlink()
    for name,files in protected.items():
        assert all(digest(RESULTS/name/relative)==h for relative,h in files.items())
    result=dict(status="EXPLICIT_ENDED_RUN_NATIVE_BASELINES_COMPRESSED_PREDECESSORS_DAT_DISCARDED",selected_native_baselines=list(BASELINES),
                discarded_native_predecessors=list(OBSOLETE),native_dat_discarded_files=len(candidates),native_dat_discarded_bytes=sum(e["bytes"] for e in candidates),
                line_inventories_compacted=len(reports),original_line_inventory_bytes=sum(e["bytes"] for e in reports),compressed_line_inventory_bytes=sum(e["compressed_bytes"] for e in reports),
                all_new_objects_decompressed_SHA256_and_size_checked=True,uncompressed_cycle_JSON_created=0,waveforms_created=0,
                FAIL_JUnit_source_end_evidence_manifest_unchanged=True,active_runs_touched=0,disk_free_before=before,disk_free_after=shutil.disk_usage(ROOT).free,
                report_indices=reports,retirement_report=str(retirement.relative_to(ROOT)),auditor_SHA256=digest(Path(__file__)))
    with output.open("x") as f:f.write(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="report_indices"},indent=2))


if __name__=="__main__":main()
