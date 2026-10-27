import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Summary-only runner: no copied source tree or persisted per-file inventory.

The existing toffee/native/checking path remains unchanged. Only source
retention is smaller: counts and aggregate fingerprints before/after the run.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT=Path(__file__).resolve().parents[1]


def aggregate(pairs):
    h=sha256();count=0
    for name,digest in sorted(pairs):
        h.update(name.encode()+b"\0"+digest.encode()+b"\n");count+=1
    return dict(file_count=count,aggregate_SHA256=h.hexdigest())


def source_summary():
    groups=defaultdict(list)
    paths=[ROOT/"pytest.ini",ROOT/"README.md"]
    for folder in("lsqverify","tests","tools","docs/contracts","manifest"):
        paths.extend(p for p in(ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix!=".pyc")
    pairs=[]
    for p in paths:
        name=str(p.relative_to(ROOT));digest=sha256(p.read_bytes()).hexdigest()
        pairs.append((name,digest));groups[name.split("/")[0]].append((name,digest))
    # Individual names/digests are intentionally not returned or persisted.
    return dict(format="lsq-source-aggregate-summary-v1",**aggregate(pairs),groups={k:aggregate(v) for k,v in sorted(groups.items())},
                retention="counts and aggregate fingerprints only; no complete per-file path/hash list, copied source contents, or verification-source tree",
                limits="Fingerprint equality identifies the source set used, but this run does not retain a complete new source snapshot. Reproduction depends on the workspace plus selected previously retained baseline/reproduction sources.")


def run(name,workers,pytest_args=None):
    assert Path(name).name==name and name not in(".","..")
    output=ROOT/"results"/name;output.mkdir(exist_ok=False)
    launch=source_summary()
    tests=list(pytest_args or [])
    if tests[:1]==["--"]:tests=tests[1:]
    if any(arg in ("--lsq-trace","--lsq-waves") for arg in tests):
        raise ValueError("summary-only runner does not enable per-cycle JSON or waveforms")
    command=[sys.executable,"-B","-m","toffee","run","--workers",str(workers),"--output",str(output/"execution"),
        "--native-coverage-tool",str(ucv_paths.project_root() / '.tools/verilator/bin/verilator_coverage'),"--export-coverage-json","--", "--basetemp",str(output/"cases"),
        "--junitxml",str(output/"pytest.xml"),"-q","--lsq-trace-max-mb","16",*(tests or ["tests"]),"--tb=short"]
    for filename,data in(("source-aggregate-launch.json",launch),("trace-policy.json",dict(per_cycle_JSON=False,waveforms=False,default="summary_only_no_per_cycle_JSON_no_waveforms",source_retention="aggregate_only_no_complete_file_inventory_or_source_copy")),
                          ("command.json",dict(cwd=str(ROOT),command=command))):
        with(output/filename).open("x") as f:f.write(json.dumps(data,indent=2)+"\n")
    env=dict(os.environ);env["PYTHONDONTWRITEBYTECODE"]="1"
    env["PYTHONPATH"]=str(ucv_paths.project_root() / '.tools/share/picker/python')+os.pathsep+str(ROOT)+os.pathsep+env.get("PYTHONPATH","")
    with(output/"console.log").open("x") as log:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    end=source_summary()
    with(output/"source-aggregate-end.json").open("x") as f:
        f.write(json.dumps(dict(**end,launch_and_end_equal=launch==end),indent=2)+"\n")
    assert launch==end,"aggregate source set changed during run; no signoff or complete per-file audit claimed"
    assert not(output/"verification-source").exists() and not(output/"source-evidence.json").exists() and not(output/"end-source-check.json").exists()
    print(json.dumps(dict(run=name,pytest_exitstatus=result.returncode,source_files=launch["file_count"],source_aggregate_launch_end_equal=True,
                         complete_source_inventory_persisted=False,complete_source_copy_created=False,per_cycle_JSON=False,waveforms=False)),flush=True)
    return result.returncode


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--name",required=True);p.add_argument("--workers",type=int,default=4)
    p.add_argument("pytest_args",nargs=argparse.REMAINDER,help="Optional directed node IDs after --; default remains the full tests tree")
    a=p.parse_args();raise SystemExit(run(a.name,a.workers,a.pytest_args))
