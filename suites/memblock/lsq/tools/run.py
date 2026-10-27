import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Run through toffee with an exclusively owned evidence directory."""
import argparse
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import subprocess
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]

parser = argparse.ArgumentParser()
parser.add_argument("--name", default=None)
parser.add_argument("--workers", type=int, default=1)
parser.add_argument("--trace",action="store_true",help="Opt-in per-cycle JSON debug (default OFF)")
parser.add_argument("--trace-max-mb",type=int,default=16,help="Per journal debug cap (default16MiB)")
parser.add_argument("--waves",action="store_true",help="Opt-in native waveforms (default OFF)")
parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
args = parser.parse_args()
if args.trace_max_mb<1:parser.error("--trace-max-mb must be positive")
name = args.name or datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
if not name or Path(name).name != name or name in (".", ".."):
    raise SystemExit("run name must be one fresh directory name")
output = ROOT / "results" / name
output.mkdir(parents=True, exist_ok=False)
# Freeze the verification implementation used by this run, not just the DUT.
# Never overwrite an earlier source snapshot when iterating on a test/model.
snapshot = output / "verification-source"
files = [ROOT / "pytest.ini", ROOT / "README.md"]
for folder in ("lsqverify", "tests", "tools", "docs/contracts", "manifest"):
    files.extend(p for p in (ROOT / folder).rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
source_hashes = {}
for path in sorted(files):
    relative = path.relative_to(ROOT)
    copy = snapshot / relative
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, copy)
    source_hashes[str(relative)] = hashlib.sha256(copy.read_bytes()).hexdigest()
(output / "source-evidence.json").write_text(json.dumps({"schema_version": 1, "files": source_hashes}, indent=2) + "\n")
tests = args.pytest_args
if tests[:1] == ["--"]:
    tests = tests[1:]
cmd = [sys.executable, "-m", "toffee", "run", "--workers", str(args.workers),
       "--output", str(output / "execution"),
       "--native-coverage-tool", str(ucv_paths.project_root() / '.tools/verilator/bin/verilator_coverage'),
       "--export-coverage-json", "--", "--basetemp", str(output / "cases"),
        "--junitxml", str(output / "pytest.xml"), "-q", "--lsq-trace-max-mb",str(args.trace_max_mb),
        *(["--lsq-trace"] if args.trace else []),*(["--lsq-waves"] if args.waves else []),*(tests or ["tests"])]
env = dict(os.environ)
env["PYTHONPATH"] = str(ucv_paths.project_root() / '.tools/share/picker/python') + os.pathsep + str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
(output / "command.json").write_text(json.dumps({"cwd": str(ROOT), "command": cmd}, indent=2) + "\n")
(output / "trace-policy.json").write_text(json.dumps(dict(per_cycle_JSON=args.trace,waveforms=args.waves,
    per_journal_debug_cap_MiB=args.trace_max_mb,default="summary_only_no_per_cycle_JSON_no_waveforms"),indent=2)+"\n")
with (output / "console.log").open("w") as log:
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        print(line, end="", flush=True)
        log.write(line)
    result = proc.wait()
print("evidence:", output, flush=True)
raise SystemExit(result)
