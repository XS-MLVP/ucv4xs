#!/usr/bin/env python3
"""Discard obsolete full traces, NOT source/tests/FAIL reports or active runs.

User-requested retention correction. A compact SHA inventory records what was
retired; these intermediate full traces are deliberately NOT all archived.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"results"


def digest(path):
    h=sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(4*1024*1024),b""):h.update(part)
    return h.hexdigest()


def retire(keep,report,execute):
    assert not report.exists()
    inventory=report.with_suffix(".files.jsonl")
    before=shutil.disk_usage(ROOT).free
    runs=[];inode_hash={}
    with inventory.open("x") as out:
        for run in sorted(RESULTS.iterdir()):
            manifest=run/"execution/manifest.json"
            if run.name in keep or not manifest.is_file():continue
            m=json.loads(manifest.read_text())
            if m.get("state")!="committed" or not m.get("cleanup_complete"):continue
            assert not (run/"storage-index-v1.json").exists(),"explicit baseline must be in --keep"
            candidates=sorted(p for p in (run/"cases").rglob("*") if p.is_file() and p.suffix in (".jsonl",".fst",".vcd"))
            candidates+=sorted((run/"execution/native").rglob("coverage.dat"))
            if not candidates:continue
            failed=[]
            if (run/"pytest.xml").exists():
                for t in ET.parse(run/"pytest.xml").iter("testcase"):
                    failure=t.find("failure")
                    if failure is not None:failed.append(dict(nodeid=t.attrib.get("classname","")+"::"+t.attrib.get("name",""),failure=(failure.text or "")[:16384]))
            count=size=0
            for path in candidates:
                assert path.is_relative_to(run) and not path.is_symlink()
                s=path.stat();key=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
                h=inode_hash.get(key)
                if h is None:h=inode_hash[key]=digest(path)
                row=dict(path=str(path.relative_to(ROOT)),SHA256=h,bytes=s.st_size,action="discard_obsolete_uncompressed_trace_or_rebuildable_coverage",compressed_archive_created=False)
                out.write(json.dumps(row)+"\n")
                if execute:path.unlink()
                count+=1;size+=s.st_size
            if execute:
                for directory in sorted((d for d in (run/"cases").rglob("*") if d.is_dir() and not d.is_symlink()),key=lambda p:len(p.parts),reverse=True):
                    if not any(directory.iterdir()):directory.rmdir()
                if (run/"cases").is_dir() and not any((run/"cases").iterdir()):(run/"cases").rmdir()
                with (run/"retired-intermediates-v1.json").open("x") as f:
                    f.write(json.dumps(dict(status="OLD_FULL_TRACES_DISCARDED_PER_USER_RETENTION_POLICY_NOT_RESTORABLE_FROM_THIS_DIRECTORY",
                        retained="pytest.xml/console/source snapshot/commands/semantic reports/LCOV and original line denominators",
                        full_baseline="lsq-progress-regression-11 (exact2036-node audit completed before cleanup)",
                        files=count,uncompressed_bytes=size,FAIL_count=len(failed),failures=failed,
                        limits="Historical independent audit was performed before cleanup. Do not claim retired full raw traces remain available; reproduce using frozen source/command or inspect the selected unified baseline. No FAIL result is changed or skipped."),indent=2)+"\n")
            runs.append(dict(run=run.name,files=count,uncompressed_bytes=size,retained_FAILs=len(failed)))
    result=dict(status="RETIRED_OBSOLETE_FULL_LOGS" if execute else "DRY_RUN_ONLY",runs=runs,kept_runs=sorted(keep),
                removed_files=sum(r["files"] for r in runs) if execute else 0,logical_bytes=sum(r["uncompressed_bytes"] for r in runs),
                inventory=str(inventory.relative_to(ROOT)),inventory_SHA256=digest(inventory),disk_free_before=before,disk_free_after=shutil.disk_usage(ROOT).free,
                active_runs_touched=0,source_tests_RTL_or_FAIL_reports_deleted=0,obsolete_payloads_archived=0)
    with report.open("x") as f:f.write(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:(len(v) if k=="runs" else v) for k,v in result.items()},indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("report",type=Path)
    p.add_argument("--keep",action="append",required=True)
    p.add_argument("--execute",action="store_true")
    a=p.parse_args()
    retire(set(a.keep),a.report.resolve(),a.execute)
