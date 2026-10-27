#!/usr/bin/env python3
"""Preserve v1's import-path failure; run its unchanged gates with explicit root."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from audit_sq_exclusive_model_v1 import audit
from audit_sq_initial import sha


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    name=p.parse_args().name
    audit(name)
    report=dict(status="PASS_UNCHANGED_V1_GATES_WITH_EXPLICIT_PROJECT_IMPORT_ROOT",run=name,
                preserved_v1_failure="Direct tools/script execution had no repository root on sys.path and raised ModuleNotFoundError:lsqverify before any audit gate. v1 source and failure kept; v2 bootstraps root only.",
                bootstrap_SHA256=sha(Path(__file__)),original_v1_SHA256=sha(ROOT/"tools/audit_sq_exclusive_model_v1.py"),
                real_v1_report_SHA256=sha(ROOT/"results"/name/"exclusive-reference-impact-v1.json"))
    out=ROOT/"results"/name/"exclusive-reference-impact-bootstrap-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))
