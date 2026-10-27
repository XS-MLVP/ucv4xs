#!/usr/bin/env python3
"""Compact already-generated large coverage reports, never generate trace.

Keep human result summaries/FAILs/commands directly readable. Large repetitive
per-line classifications remain lossless zstd objects and stage on demand.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from lsq_evidence_archive_v1 import ROOT, RESULTS, STORE, decoded, digest, lock


PROTECTED={"storage-index-v1.json","reports-storage-index-v1.json","retired-intermediates-v1.json",
           "evidence-check-v12.json","ldu-s3-audit-v1.json","ldu-joint-audit-v3.json","ldu-joint-coverage-audit-v2.json",
           "joint-producer-audit-v1.json","exclusive-pool-audit-v1.json"}


def main():
    output=RESULTS/"evidence-reports-compacted-v1.json"
    assert not output.exists()
    STORE.mkdir(exist_ok=True)
    before=shutil.disk_usage(ROOT).free
    reports=[];original=0;packed=0
    for run in sorted(RESULTS.iterdir()):
        manifest=run/"execution/manifest.json"
        if not manifest.is_file() or (run/"reports-storage-index-v1.json").exists():continue
        m=json.loads(manifest.read_text())
        if m.get("state")!="committed" or not m.get("cleanup_complete"):continue
        candidates=[p for p in run.glob("*.json") if p.name not in PROTECTED and p.stat().st_size>1024*1024]
        if not candidates:continue
        with lock(run):
            index=dict(format="lsq-reports-storage-index-v1",run=run.name,manifest_SHA256=digest(manifest),files=[])
            for path in sorted(candidates):
                assert not path.is_symlink()
                h=digest(path);size=path.stat().st_size
                obj=STORE/(h+".zst")
                if not obj.exists():
                    tmp=STORE/(".report-"+uuid.uuid4().hex)
                    try:
                        with tmp.open("xb") as f:subprocess.run(["zstd","-q","-9","--long=27","-c",str(path)],stdout=f,check=True)
                        assert decoded(tmp)==(h,size)
                        os.replace(tmp,obj)
                    finally:
                        if tmp.exists():tmp.unlink()
                else:assert decoded(obj)==(h,size)
                entry=dict(path=path.name,SHA256=h,bytes=size,object=str(obj.relative_to(ROOT)),object_SHA256=digest(obj),compressed_bytes=obj.stat().st_size)
                index["files"].append(entry)
                # Write recoverable metadata before removing a report path.
                (run/"reports-storage-index-v1.json").write_text(json.dumps(index,indent=2)+"\n")
                path.unlink()
                original+=size;packed+=obj.stat().st_size
                reports.append(dict(run=run.name,report=path.name,original_bytes=size,compressed_bytes=obj.stat().st_size))
    result=dict(status="LARGE_COVERAGE_REPORTS_COMPACTED_NO_NEW_PER_CYCLE_TRACE",reports=len(reports),original_bytes=original,compressed_bytes=packed,
                disk_free_before=before,disk_free_after=shutil.disk_usage(ROOT).free,all_decompressed_SHA256_and_size_checked=True,files=reports)
    with output.open("x") as f:f.write(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="files"},indent=2))


if __name__=="__main__":main()
