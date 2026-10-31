#!/usr/bin/env python3
"""Read-only exact2203/default-OFF preflight; not native run results."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from audit_progress_summary_v13 import BASELINES, nodes
from audit_sq_initial import ROOT


def main():
    expected={}
    for name in BASELINES:
        part=nodes(ROOT/"results"/name)
        assert not expected.keys()&part.keys()
        expected.update(part)
    assert len(expected)==2203 and sum(expected.values())==221
    p=subprocess.run([sys.executable,"-B","-m","pytest","--collect-only","-q","tests"],cwd=ROOT,capture_output=True,text=True,check=True)
    collected={line.strip() for line in p.stdout.splitlines() if line.startswith("tests/") and "::" in line}
    assert collected==set(expected)
    ast_count=0
    from ucv.runtime import suite_python_sources
    for file in suite_python_sources(ROOT):
        ast.parse(file.read_text(),filename=str(file));ast_count+=1
    source=json.loads((ROOT/"results/lsq-progress-regression-11/source-evidence.json").read_text())["files"]
    unchanged={k:v for k,v in source.items() if k.startswith('lsqverify/') and k!='lsqverify/native.py'}
    assert all(sha256((ROOT/k).read_bytes()).hexdigest()==h for k,h in unchanged.items())
    result=dict(status="READ_ONLY_PREFLIGHT_NOT_NATIVE_EXECUTION",exact_nodes=2203,baselines=list(BASELINES),
                expected_results_not_actual=dict(PASS=1982,FAIL=221),Python_AST_files=ast_count,
                unchanged_shared_reference_files=len(unchanged),default_policy="no per-cycle JSON, no waveforms; runtime checks retained",
                collector_SHA256=sha256(p.stdout.encode()).hexdigest())
    output=ROOT/"results/lsq-progress-regression-12-preflight-v1.json"
    with output.open("x") as out:out.write(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
