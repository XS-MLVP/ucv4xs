import ucv.runtime as ucv_paths
"""Run/recover the 8352-case native campaign in independently closed shards.

Each completed shape has an fsynced input, result and journal receipt. Each
shard closes its own FST/native coverage and toffee manifest, even when
functional assertions fail. Re-running the same command reuses only audited
committed shards; interrupted attempts are kept and retried in a new directory.
"""
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from suites.vector.vagq.vagq.exhaustive import build_shape_sequence
from suites.vector.vagq.vagq.scenario_matrix import feature_case_id, legal_public_feature_cases


SOURCES = (
    'tools/run_vagq_exhaustive.py',
    'tests/vagq/test_isa_exhaustive_shape.py',
    'tests/vagq/test_exhaustive_checker.py',
    'vagq/exhaustive.py',
    'vagq/scenario_matrix.py',
    'vagq/isa_reference.py',
    'maskgen/reference.py',
    'vagq/probe.py',
    'vagq/driver.py',
    'native.py',
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path, value):
    temp = path.with_suffix('.json.partial')
    with temp.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def audit_attempt(attempt, expected, frozen):
    manifest_path = attempt / 'execution/manifest.json'
    progress_path = attempt / 'shapes/progress.jsonl'
    if not manifest_path.is_file() or not progress_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('state') != 'committed' or not manifest.get('coverage_complete'):
        return None
    if json.loads((attempt / 'source-hashes.json').read_text()) != frozen:
        raise RuntimeError(f'source epoch mismatch in {attempt}')
    receipts = [row for line in progress_path.read_text().splitlines()
                if (row := json.loads(line))['event'] == 'finished']
    if [row['ordinal'] for row in receipts] != list(expected):
        return None
    for row in receipts:
        path = Path(row['path'])
        if not path.is_file() or digest(path) != row['sha256']:
            raise RuntimeError(f'corrupt shape receipt: {path}')
    for artifact in manifest['artifacts']:
        path = Path(artifact['path'])
        if path.stat().st_size != artifact['size'] or digest(path) != artifact['sha256']:
            raise RuntimeError(f'corrupt managed artifact: {path}')
    waveforms = list((attempt / 'cases').rglob('VAGQ.fst'))
    if not waveforms or any(path.stat().st_size == 0 for path in waveforms):
        raise RuntimeError(f'no finalized native waveform in {attempt}')
    return receipts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--shard-size', type=int, default=256)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.shard_size <= 0:
        raise ValueError('shard size must be positive')
    files = {name: digest(ROOT / name) for name in SOURCES}
    files.update({str(path.relative_to(ROOT)): digest(path) for path in (ROOT / 'rtl').glob('*.sv')})
    files.update({str(path.relative_to(ROOT)): digest(path) for path in (ROOT / 'dut/VAGQ').glob('*.so')})
    frozen_path = out / 'source-hashes.json'
    if frozen_path.exists():
        if json.loads(frozen_path.read_text()) != files:
            raise RuntimeError('Sources changed: preserve this run and use a new output directory')
    else:
        for name in SOURCES:
            target = out / 'sources' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        atomic_json(frozen_path, files)
    cases = tuple(legal_public_feature_cases())
    inventory = [dict(ordinal=i, shape_id=feature_case_id(case),
                      actual_sequence_uops=len(build_shape_sequence(case, i).packets))
                 for i, case in enumerate(cases)]
    atomic_json(out / 'inventory.json', inventory)
    assert len(cases) == 8352
    completed = []
    shard_receipts = []
    started = time.monotonic()
    for start in range(0, len(cases), args.shard_size):
        stop = min(len(cases), start + args.shard_size)
        base = out / f'shard-{start:05d}-{stop - 1:05d}'
        base.mkdir(exist_ok=True)
        rows = None
        attempt = None
        attempts = sorted(base.glob('attempt-*'))
        for candidate in attempts:
            rows = audit_attempt(candidate, range(start, stop), files)
            if rows is not None:
                attempt = candidate
                print(f'Reuse audited shard {start}:{stop}', flush=True)
                break
        if rows is None:
            if any(digest(ROOT / name) != value for name, value in files.items()):
                raise RuntimeError('Source epoch changed during execution; not continuing')
            attempt = base / f'attempt-{len(attempts) + 1:02d}'
            attempt.mkdir()
            atomic_json(attempt / 'source-hashes.json', files)
            env = dict(os.environ, RUN_VAGQ_EXHAUSTIVE='1',
                EXHAUSTIVE_START=str(start), EXHAUSTIVE_LIMIT=str(stop - start),
                VAGQ_SHAPE_LOG=str(attempt / 'shapes'))
            env.pop('EXHAUSTIVE_ORDINALS', None)
            cmd = [sys.executable, '-m', 'toffee', 'run', '--workers', '1',
                '--output', str(attempt / 'execution'),
                '--native-coverage-tool', str(ucv_paths.project_root() / '.tools/verilator/bin/verilator_coverage'),
                '--export-coverage-json', '--', '--basetemp=' + str(attempt / 'cases'),
                '--junitxml=' + str(attempt / 'pytest.xml'),
                '-q', '-rs', 'tests/vagq/test_isa_exhaustive_shape.py']
            atomic_json(attempt / 'command.json', dict(argv=cmd,
                env={key: env[key] for key in ('RUN_VAGQ_EXHAUSTIVE', 'EXHAUSTIVE_START',
                                             'EXHAUSTIVE_LIMIT', 'VAGQ_SHAPE_LOG')}))
            print(f'Run shard {start}:{stop} in {attempt}', flush=True)
            with (attempt / 'output.log').open('w') as log:
                process = subprocess.Popen(cmd, cwd=ROOT, env=env,
                    stdout=log, stderr=subprocess.STDOUT)
                atomic_json(attempt / 'process.json', dict(pid=process.pid, start=time.time()))
                returncode = process.wait()
            atomic_json(attempt / 'exit.json', dict(returncode=returncode, end=time.time()))
            rows = audit_attempt(attempt, range(start, stop), files)
            if rows is None:
                raise RuntimeError(f'Shard interrupted/incomplete, not credited: {attempt}')
        completed.extend(rows)
        shard_receipts.append(str(attempt / 'execution/manifest.json'))
        counts = Counter(row['status'] for row in completed)
        summary = dict(state='running' if stop != len(cases) else 'complete',
            updated_at=datetime.now(timezone.utc).isoformat(),
            requested=len(cases), completed=len(completed), counts=dict(counts),
            unexecuted=len(cases) - len(completed),
            planned_uop_packets=sum(row['actual_sequence_uops'] for row in inventory),
            admitted_uops=sum(row.get('admitted_uops', 0) for row in completed),
            writebacks=sum(row.get('writebacks', 0) for row in completed),
            manifests=shard_receipts, elapsed_seconds=time.monotonic() - started,
            scope='public full-length shape and synthetic consumer byte-placement checks; not whole-chip ISA acceptance')
        atomic_json(out / 'summary.json', summary)
        atomic_json(out / 'completed-shapes.json', completed)
        print(f'COMMITTED {len(completed)}/{len(cases)} {dict(counts)}; '
              f'admitted uops {summary["admitted_uops"]}', flush=True)
    print('All 8352 shape attempts have audited native receipts.', flush=True)
    if any(row['status'] != 'PASS' for row in completed):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
