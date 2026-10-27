#!/usr/bin/env python3
"""Retire bulky, completed LSQ intermediates; stage exact evidence on demand.

Repeated JSONL/coverage files become one SHA-addressed zstd object. Original
large paths are removed, not kept as another uncompressed copy. Reproducible
waveforms are discarded. Tests, RTL, reports, FAILs and source snapshots stay.
"""
import argparse
from contextlib import contextmanager, ExitStack
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"results"
STORE=RESULTS/"evidence-store-v1"
INDEX="storage-index-v1.json"


def digest(path):
    h=sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(4*1024*1024),b""):h.update(part)
    return h.hexdigest()


def decoded(path):
    h=sha256();size=0
    with subprocess.Popen(["zstd","-q","-d","-c",str(path)],stdout=subprocess.PIPE) as p:
        for part in iter(lambda:p.stdout.read(4*1024*1024),b""):h.update(part);size+=len(part)
        assert p.wait()==0
    return h.hexdigest(),size


def relative_file(run,relative):
    p=run/relative
    assert p.is_relative_to(run) and ".." not in p.parts and not p.is_symlink()
    assert (p.is_relative_to(run/"cases") or p.name=="coverage.dat" and p.is_relative_to(run/"execution/native") or
            p.parent==run and p.suffix==".json")
    return p


@contextmanager
def lock(run):
    with (run/".storage.lock").open("a") as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def archive(output,only):
    assert not output.exists()
    STORE.mkdir(exist_ok=True)
    report=dict(format="lsq-evidence-retention-v1",policy="explicitly selected audit baselines ONLY: discard reproducible waves; remove uncompressed logs/coverage; retain one verified zstd object per unique selected payload, plus compact per-run index",selected_runs=sorted(only),runs=[])
    before=shutil.disk_usage(ROOT).free
    inode_hash={};verified={}
    for run in sorted(RESULTS.iterdir()):
        m=run/"execution/manifest.json"
        if run.name not in only or not m.is_file() or (run/INDEX).exists():continue
        manifest=json.loads(m.read_text())
        if manifest.get("state")!="committed" or not manifest.get("cleanup_complete"):continue
        files=sorted((run/"cases").rglob("*.jsonl"))+sorted((run/"execution/native").rglob("coverage.dat"))
        waves=sorted((run/"cases").rglob("*.fst"))+sorted((run/"cases").rglob("*.vcd"))
        if not files and not waves:continue
        with lock(run):
            index=dict(format="lsq-evidence-storage-index-v1",run=run.name,manifest_SHA256=digest(m),files=[],discarded_reproducible_waveforms=[])
            pending=run/"storage-index-v1.pending.jsonl"
            with pending.open("x") as journal:
                for p in files:
                    assert not p.is_symlink() and p.is_file()
                    s=p.stat();key=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
                    h=inode_hash.get(key)
                    if h is None:h=inode_hash[key]=digest(p)
                    obj=STORE/(h+".zst")
                    if h not in verified:
                        if not obj.exists():
                            tmp=STORE/(".tmp-"+uuid.uuid4().hex)
                            try:
                                with tmp.open("xb") as out:subprocess.run(["zstd","-q","-9","--long=27","-c",str(p)],stdout=out,check=True)
                                assert decoded(tmp)==(h,s.st_size)
                                os.replace(tmp,obj)
                            finally:
                                if tmp.exists():tmp.unlink()
                        else:assert decoded(obj)==(h,s.st_size)
                        verified[h]=(digest(obj),obj.stat().st_size)
                    entry=dict(path=str(p.relative_to(run)),SHA256=h,bytes=s.st_size,object=str(obj.relative_to(ROOT)),
                               object_SHA256=verified[h][0],compressed_bytes=verified[h][1])
                    journal.write(json.dumps(entry)+"\n");journal.flush();os.fsync(journal.fileno())
                    assert p.stat().st_size==s.st_size and p.stat().st_mtime_ns==s.st_mtime_ns
                    p.unlink()
                    index["files"].append(entry)
                for p in waves:
                    assert not p.is_symlink() and p.is_file()
                    entry=dict(path=str(p.relative_to(run)),SHA256=digest(p),bytes=p.stat().st_size,reason="reproducible waveform redundant with preserved inputs/source/raw actual pins; rerun native test if wave is needed")
                    journal.write(json.dumps(entry)+"\n");journal.flush();os.fsync(journal.fileno())
                    p.unlink()
                    index["discarded_reproducible_waveforms"].append(entry)
            (run/INDEX).write_text(json.dumps(index,indent=2)+"\n")
            pending.unlink()
            for directory in sorted((d for d in (run/"cases").rglob("*") if d.is_dir() and not d.is_symlink()),key=lambda d:len(d.parts),reverse=True):
                if not any(directory.iterdir()):directory.rmdir()
            if (run/"cases").is_dir() and not any((run/"cases").iterdir()):(run/"cases").rmdir()
            report["runs"].append(dict(name=run.name,index_SHA256=digest(run/INDEX),removed_large_paths=len(files),discarded_waves=len(waves),
                                       old_uncompressed_bytes=sum(e["bytes"] for e in index["files"])))
    objects=list(STORE.glob("*.zst"))
    report.update(disk_free_before=before,disk_free_after=shutil.disk_usage(ROOT).free,unique_compressed_objects=len(objects),
                  unique_compressed_bytes=sum(p.stat().st_size for p in objects),removed_uncompressed_paths=sum(r["removed_large_paths"] for r in report["runs"]),
                  discarded_reproducible_waves=sum(r["discarded_waves"] for r in report["runs"]),
                  all_new_objects_decompressed_SHA256_and_size_checked=True,
                  restore_command="python3 -B tools/lsq_evidence_archive_v1.py audit RUN1 [RUN2 ...] -- python3 -B tools/EXISTING_AUDITOR.py ARGUMENTS")
    with output.open("x") as f:f.write(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:(len(v) if k=="runs" else v) for k,v in report.items()},indent=2))


@contextmanager
def staged(run):
    indices=[json.loads(p.read_text()) for p in(run/INDEX,run/"reports-storage-index-v1.json") if p.exists()]
    if not indices:yield;return
    created=[]
    with lock(run):
        assert all(index["manifest_SHA256"]==digest(run/"execution/manifest.json") for index in indices)
        try:
            for e in(e for index in indices for e in index["files"]):
                dest=relative_file(run,e["path"])
                if dest.exists():assert digest(dest)==e["SHA256"];continue
                obj=ROOT/e["object"]
                assert obj.is_relative_to(STORE) and digest(obj)==e["object_SHA256"]
                dest.parent.mkdir(parents=True,exist_ok=True)
                tmp=dest.with_name(".restore-"+uuid.uuid4().hex)
                try:
                    with tmp.open("xb") as out:subprocess.run(["zstd","-q","-d","-c",str(obj)],stdout=out,check=True)
                    assert tmp.stat().st_size==e["bytes"] and digest(tmp)==e["SHA256"]
                    os.replace(tmp,dest);created.append((dest,e["SHA256"]))
                finally:
                    if tmp.exists():tmp.unlink()
            yield
        finally:
            for dest,h in reversed(created):
                assert digest(dest)==h,"auditor modified immutable evidence; refuse to discard it"
                dest.unlink()


if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="audit":
        split=sys.argv.index("--")
        names,command=sys.argv[2:split],sys.argv[split+1:]
        assert names and command
        with ExitStack() as stack:
            for name in sorted(set(names)):
                assert Path(name).name==name
                stack.enter_context(staged(RESULTS/name))
            result=subprocess.run(command,cwd=ROOT)
        raise SystemExit(result.returncode)
    else:
        p=argparse.ArgumentParser()
        p.add_argument("action",choices=("archive",))
        p.add_argument("output",type=Path)
        p.add_argument("--run",action="append",required=True,help="Explicit audit baseline to retain, NOT every historical run")
        a=p.parse_args()
        archive(a.output,set(a.run))
