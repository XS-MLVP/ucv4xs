#!/usr/bin/env python3
"""Inventory and lossless hard-link deduplication of committed LSQ evidence.

Never delete an evidence path, truncate content, compress a live journal or
touch another subsystem. Scan/apply are separate, hash-pinned operations.
"""
import argparse
from collections import defaultdict
import filecmp
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import stat
import uuid


ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"results"


def digest(path):
    h=sha256()
    with path.open("rb") as stream:
        for part in iter(lambda:stream.read(4*1024*1024),b""):h.update(part)
    return h.hexdigest()


def write_new(path,data):
    with path.open("x") as out:out.write(json.dumps(data,indent=2,ensure_ascii=False)+"\n")


def scan(output,excluded):
    groups=defaultdict(list)
    manifests={}
    logical=allocated=files=0
    for run in sorted(RESULTS.iterdir()):
        manifest=run/"execution/manifest.json"
        if not run.is_dir() or run.name in excluded or not manifest.is_file():continue
        m=json.loads(manifest.read_text())
        if m.get("state")!="committed" or not m.get("cleanup_complete"):continue
        manifests[run.name]=digest(manifest)
        for path in (run/"cases").rglob("*"):
            if path.suffix not in (".jsonl",".fst") or path.is_symlink() or not path.is_file():continue
            s=path.stat()
            logical+=s.st_size;allocated+=s.st_blocks*512;files+=1
            if s.st_size<1024*1024 or not stat.S_ISREG(s.st_mode):continue
            groups[(path.name,s.st_size,stat.S_IMODE(s.st_mode))].append(path)
    duplicates=[]
    hashed=0
    for (_,size,mode),paths in sorted(groups.items()):
        if len(paths)<2:continue
        by_hash=defaultdict(list)
        for path in paths:
            by_hash[digest(path)].append(path)
            hashed+=size
        for h,identical in by_hash.items():
            if len(identical)<2:continue
            by_inode=defaultdict(list)
            for path in identical:
                s=path.stat()
                by_inode[(s.st_dev,s.st_ino)].append(path)
            if len(by_inode)<2:continue
            canonical=identical[0]
            cs=canonical.stat()
            targets=[]
            for path in identical[1:]:
                s=path.stat()
                if (s.st_dev,s.st_ino)==(cs.st_dev,cs.st_ino):continue
                # Initially only independent single-link copies are replaced;
                # do not guess what other external hardlinks might depend on.
                if s.st_nlink!=1:continue
                targets.append(dict(path=str(path.relative_to(ROOT)),size=s.st_size,device=s.st_dev,inode=s.st_ino,
                                    mode=mode,mtime_ns=s.st_mtime_ns,blocks=s.st_blocks))
            if targets:duplicates.append(dict(canonical=str(canonical.relative_to(ROOT)),SHA256=h,size=size,targets=targets))
    report=dict(format="lsq-evidence-storage-scan-v1",root=str(ROOT),excluded_runs=sorted(excluded),committed_manifests=manifests,
                evidence_files=files,evidence_logical_bytes=logical,evidence_counted_allocated_bytes=allocated,hashed_bytes=hashed,
                duplicate_groups=duplicates,duplicate_physical_copies=sum(len(d["targets"]) for d in duplicates),
                reclaimable_bytes=sum(t["blocks"]*512 for d in duplicates for t in d["targets"]),
                disk_free_before=shutil.disk_usage(ROOT).free,
                safety="Only committed cleanup-complete LSQ cases JSONL/FST >=1MiB, exact SHA256 then direct byte compare before each replacement. All paths/contents/FAIL/coverage/snapshots retained. Inactive raw evidence must never be edited in place after dedup. File mtime becomes canonical mtime; original metadata recorded. No other subsystem or active run touched.")
    write_new(output,report)
    print(json.dumps({k:v for k,v in report.items() if k not in ("duplicate_groups","committed_manifests")},indent=2,ensure_ascii=False))


def apply(scan_path,output):
    plan=json.loads(scan_path.read_text())
    assert plan["root"]==str(ROOT) and plan["format"]=="lsq-evidence-storage-scan-v1"
    for name,h in plan["committed_manifests"].items():
        path=RESULTS/name/"execution/manifest.json"
        assert digest(path)==h and json.loads(path.read_text())["state"]=="committed"
    before=shutil.disk_usage(ROOT).free
    operations=[]
    # Persist each operation with fsync; interruption cannot lose the content
    # hash/canonical path needed to audit an already-replaced duplicate.
    journal=output.with_suffix(".operations.jsonl")
    with journal.open("x") as log:
        for group in plan["duplicate_groups"]:
            canonical=ROOT/group["canonical"]
            assert canonical.is_relative_to(RESULTS) and digest(canonical)==group["SHA256"]
            for target in group["targets"]:
                path=ROOT/target["path"]
                assert path.is_relative_to(RESULTS) and "cases" in path.parts and not path.is_symlink()
                s=path.stat()
                assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_nlink)==(target["device"],target["inode"],target["size"],target["mtime_ns"],1)
                assert digest(path)==group["SHA256"] and filecmp.cmp(canonical,path,shallow=False)
                temporary=path.with_name(".lsq-dedup-"+uuid.uuid4().hex)
                os.link(canonical,temporary)
                try:os.replace(temporary,path)
                finally:
                    if temporary.exists():temporary.unlink()
                assert path.stat().st_ino==canonical.stat().st_ino and digest(path)==group["SHA256"]
                op=dict(path=target["path"],canonical=group["canonical"],SHA256=group["SHA256"],retained_bytes=target["size"],
                        reclaimed_blocks_bytes=target["blocks"]*512,original_metadata=target,operation="exact_immutable_bytes_shared_inode_all_paths_retained")
                log.write(json.dumps(op,ensure_ascii=False)+"\n");log.flush();os.fsync(log.fileno())
                operations.append(op)
    report=dict(format="lsq-evidence-storage-applied-v1",scan=str(scan_path.resolve().relative_to(ROOT)),scan_SHA256=digest(scan_path),
                operations=str(journal.resolve().relative_to(ROOT)),operations_SHA256=digest(journal),deduplicated_copies=len(operations),
                all_replaced_paths_SHA256_checked_after=True,freed_duplicate_blocks_bytes=sum(o["reclaimed_blocks_bytes"] for o in operations),
                disk_free_before=before,disk_free_after=shutil.disk_usage(ROOT).free,deleted_evidence_paths=0,
                raw_evidence_content_or_failure_changes=0,excluded_runs=plan["excluded_runs"])
    write_new(output,report)
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("scan","apply"))
    p.add_argument("output",type=Path)
    p.add_argument("--scan",type=Path)
    p.add_argument("--exclude",action="append",default=["lsq-progress-regression-11"])
    a=p.parse_args()
    if a.action=="scan":scan(a.output,set(a.exclude))
    else:
        assert a.scan is not None
        apply(a.scan,a.output)
