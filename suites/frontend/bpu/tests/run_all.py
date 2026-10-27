"""Run the complete production regression, parallel by default.

The frozen owner delegates collection/merge/cleanup to toffee run. Use
--workers=1 for serial diagnosis and --select tests/<module> for isolated
iteration. Diagnostics never replace the published complete-regression reports.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    env = os.environ.copy()
    # Native dependencies are installed packages. Do not shadow them with an
    # old checkout or the ABI-1 bindings shipped by the previous picker install.
    paths = [str(ROOT)]
    if env.get('PYTHONPATH'):
        paths.append(env['PYTHONPATH'])
    env['PYTHONPATH'] = os.pathsep.join(paths)
    return subprocess.call(
        [sys.executable, str(ROOT / 'tools/refresh_coverage.py'),
         *(sys.argv[1:] if argv is None else argv)], cwd=ROOT, env=env,
    )


if __name__ == '__main__':
    raise SystemExit(main())
