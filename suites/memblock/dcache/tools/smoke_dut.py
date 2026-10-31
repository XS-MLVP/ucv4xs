#!/usr/bin/env python3
"""Post-build native smoke test for already-built Picker DUTs.

Builds are only accepted after the generated package can be instantiated, all
inputs driven to zero, and either reset+clock advanced (sequential DUT) or a
stable combinational evaluation observed (pure combinational DUT).
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from suites.memblock.dcache.inventory import DUTS, dut_dir, export_name  # noqa: E402

SMOKE = '''
import importlib.util, sys
from pathlib import Path
p = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location("dut_smoke", p / "__init__.py",
                                              submodule_search_locations=[str(p)])
m = importlib.util.module_from_spec(spec); sys.modules["dut_smoke"] = m
spec.loader.exec_module(m)
d = getattr(m, "DUT" + sys.argv[2])()
pins = set(d.xport.GetKeys())
for s in list(vars(d).values()):
    if callable(getattr(s, "IsInIO", None)) and s.IsInIO() and not s.IsOutIO():
        s.AsImmWrite(); s.Set(0)
if "clock" in pins:
    d.InitClock("clock")
    if "reset" in pins:
        d.reset.Set(1); d.Step(4); d.reset.Set(0); d.Step(4)
    else:
        d.Step(4)
else:
    d.Step(1)
d.Finish()
print("NATIVE_SMOKE_PASS")
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("keys", nargs="*", default=[])
    args = parser.parse_args()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ucv_paths.project_root() / '.tools/share/picker/python') + os.pathsep + env.get("PYTHONPATH", "")
    ok = True
    (ROOT / "results/builds").mkdir(parents=True, exist_ok=True)
    for key in args.keys or list(DUTS):
        directory = dut_dir(key)
        if not (directory / "__init__.py").is_file():
            print(f"{key}: no DUT package")
            ok = False
            continue
        with tempfile.TemporaryDirectory(prefix=f"dcache-{key}-smoke-",
                                         dir=None) as tmp:
            run = subprocess.run(
                [sys.executable, "-c", SMOKE, str(directory), export_name(key)],
                cwd=tmp, env=env, capture_output=True, text=True)
        passed = run.returncode == 0 and "NATIVE_SMOKE_PASS" in run.stdout
        (ROOT / "results/builds" / f"smoke-{key}.log").write_text(run.stdout + run.stderr)
        print(f"{key}: {'PASS' if passed else 'FAILED'}")
        ok = ok and passed
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
