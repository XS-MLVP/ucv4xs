import ucv.runtime as ucv_paths
"""Native replay of ALL 2278 failures, with durable, independently closed shards."""
from collections import Counter
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.run_vagq_exhaustive import atomic_json, digest

REVIEW = ROOT / 'results/vagq-exhaustive-review-20261020-v1'
SOURCES = (
    'tools/run_vagq_failure_review.py', 'tools/analyze_vagq_failures.py',
    'vagqverify/vagq/failure_review.py', 'tests/vagq/test_failure_review.py',
)


def audit(attempt, expected):
    path = attempt / 'execution/manifest.json'
    if not path.is_file() or not (attempt / 'review/receipts.json').is_file():
        return None
    manifest = json.loads(path.read_text())
    if manifest.get('state') != 'committed' or not manifest.get('coverage_complete'):
        return None
    rows = json.loads((attempt / 'review/receipts.json').read_text())
    if [r['ordinal'] for r in rows] != expected:
        return None
    for row in rows:
        assert digest(Path(row['path'])) == row['sha256']
    for artifact in manifest['artifacts']:
        target = Path(artifact['path'])
        assert digest(target) == artifact['sha256']
        assert target.stat().st_size == artifact['size']
    assert any(p.stat().st_size for p in (attempt / 'cases').rglob('VAGQ.fst'))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=REVIEW / 'native')
    parser.add_argument('--shard-size', type=int, default=256)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((ROOT / 'results/vagq-exhaustive-20261020-v1/full/source-hashes.json').read_text())
    frozen.update({name: digest(ROOT / name) for name in SOURCES})
    frozen[str((REVIEW / 'case-review.json').relative_to(ROOT))] = digest(REVIEW / 'case-review.json')
    frozen_path = out / 'source-hashes.json'
    if frozen_path.exists():
        assert json.loads(frozen_path.read_text()) == frozen, 'use a new run for changed sources'
    else:
        atomic_json(frozen_path, frozen)
        for name in SOURCES:
            target = out / 'sources' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
    cases = json.loads((REVIEW / 'case-review.json').read_text())
    assert len(cases) == 2278
    receipts, manifests = [], []
    start_time = time.monotonic()
    for start in range(0, len(cases), args.shard_size):
        stop = min(len(cases), start + args.shard_size)
        expected = [r['ordinal'] for r in cases[start:stop]]
        base = out / f'shard-{start:04d}-{stop - 1:04d}'
        base.mkdir(exist_ok=True)
        attempts = sorted(base.glob('attempt-*'))
        rows, attempt = None, None
        for candidate in attempts:
            rows = audit(candidate, expected)
            if rows is not None:
                attempt = candidate
                break
        if rows is None:
            assert all(digest(ROOT / name) == value for name, value in frozen.items()), 'review source epoch changed'
            attempt = base / f'attempt-{len(attempts) + 1:02d}'
            attempt.mkdir()
            env = dict(os.environ, RUN_VAGQ_FAILURE_REVIEW='1', REVIEW_START=str(start),
                REVIEW_LIMIT=str(stop - start), REVIEW_LOG=str(attempt / 'review'))
            env.pop('REVIEW_ORDINALS', None)
            cmd = [sys.executable, '-m', 'toffee', 'run', '--workers', '1',
                '--output', str(attempt / 'execution'), '--native-coverage-tool',
                str(ucv_paths.project_root() / '.tools/verilator/bin/verilator_coverage'), '--export-coverage-json', '--',
                '--basetemp=' + str(attempt / 'cases'), '--junitxml=' + str(attempt / 'pytest.xml'),
                '-q', '-rs', 'tests/vagq/test_failure_review.py']
            atomic_json(attempt / 'command.json', dict(argv=cmd,
                start=start, stop=stop, ordinals=expected,
                env={k: env[k] for k in ('RUN_VAGQ_FAILURE_REVIEW', 'REVIEW_START', 'REVIEW_LIMIT', 'REVIEW_LOG')}))
            print(f'Replay failures {start}:{stop}', flush=True)
            with (attempt / 'output.log').open('w') as log:
                process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                atomic_json(attempt / 'process.json', dict(pid=process.pid))
                code = process.wait()
            atomic_json(attempt / 'exit.json', dict(returncode=code))
            rows = audit(attempt, expected)
            if rows is None:
                raise RuntimeError(f'uncommitted review shard, not credited: {attempt}')
        receipts.extend(rows)
        manifests.append(str(attempt / 'execution/manifest.json'))
        summary = dict(state='complete' if stop == len(cases) else 'running',
            requested=2278, reviewed=len(receipts),
            baseline_reproduced=sum(r['checks']['baseline_failure_reproduced'] for r in receipts),
            outcomes=dict(Counter(r['review_status'] for r in receipts)),
            by_family=dict(Counter(r['family'] for r in receipts)),
            manifests=manifests, elapsed_seconds=time.monotonic() - start_time)
        atomic_json(out / 'summary.json', summary)
        atomic_json(out / 'completed-reviews.json', receipts)
        print(f'COMMITTED {len(receipts)}/2278 {summary["outcomes"]}', flush=True)
    if any(r['review_status'] != 'VERIFIED' for r in receipts):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
