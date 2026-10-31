import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Read-only baseline/node/source audit before next full native regression."""
import ast
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys

from audit_progress_run_v12 import BASELINES, FAMILIES
from audit_sq_initial import ROOT, sha, verify_common


def audit():
    baseline_nodes={}
    baseline_reports={}
    for name in BASELINES:
        run=ROOT/"results"/name
        manifest,source,nodes=verify_common(run)
        assert not baseline_nodes.keys()&nodes.keys()
        baseline_nodes.update(nodes)
        baseline_reports[name]=dict(tests=manifest["tests"],source_files=len(source),manifest_SHA256=sha(run/"execution/manifest.json"))
    result=subprocess.run([sys.executable,"-B","-m","pytest","--collect-only","-q","tests"],cwd=ROOT,capture_output=True,text=True)
    assert not result.returncode,result.stderr
    nodes=[n for n in result.stdout.splitlines() if n.startswith("tests/") and "::" in n]
    assert len(nodes)==len(set(nodes))==2036 and set(nodes)==baseline_nodes.keys()
    assert Counter(n.split("/")[1] for n in nodes)==Counter(FAMILIES)
    python_files=ucv_paths.suite_python_sources(ROOT)
    for p in python_files:ast.parse(p.read_text(),filename=str(p))
    base=json.loads((ROOT/"results/lsq-progress-regression-10/source-evidence.json").read_text())["files"]
    shared={k:v for k,v in base.items() if k.startswith('lsqverify/')}
    assert shared and all(sha(ROOT/k)==v for k,v in shared.items())
    repo=ucv_paths.source_path_for(ROOT)
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    assert head=="893e1580b705d81f113c30c7a05734e09a08050e"
    assert not subprocess.check_output(["git","status","--porcelain=v1","--untracked-files=no"],cwd=repo,text=True)
    rtl=ucv_paths.soc_rtl_for(ROOT)
    files={line.split()[1]:line.split()[0] for line in (ROOT/"manifest/lsq-rtl.sha256").read_text().splitlines()}
    assert len(files)==53 and all(sha(rtl/name)==value for name,value in files.items())
    for p in(ROOT/"rtl/lsq_wrapper").rglob("*.sv"):
        if p.name in files:assert sha(p)==files[p.name]
    report=dict(status="READ_ONLY_2036_EXACT_COLLECTED_NODE_UNION_SOURCE_PREFLIGHT_NOT_NATIVE_RUN_RESULT",baseline_runs=baseline_reports,
                collected_nodes=2036,baseline_outcomes=dict(Counter("FAIL" if v else "PASS" for v in baseline_nodes.values())),
                pytest_families=dict(Counter(n.split("/")[1] for n in nodes)),Python_AST_files=len(python_files),shared_reference_files_unchanged=len(shared),
                open_HEAD=head,open_tracked_tree_clean=True,original_RTL_files_SHA256_verified=53,auditor_SHA256=sha(Path(__file__)),
                limits="Collection/source/native-artifact baseline checks only. Does not claim regression11 has started/finished or its future1821/215 expected outcomes are actual measurements. Old source-domain rejections and every ordinary failure remain.")
    out=ROOT/"results/lsq-progress-regression-11-preflight-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
