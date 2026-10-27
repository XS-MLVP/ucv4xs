"""Explicit, previewed reclamation of superseded measurement artifacts only.

No directory is recursively deleted. Keep a complete selected run, published
report/profile comparison dependencies, and all unclassified analysis evidence.
The apply step must reproduce the exact inode/size/mtime selection preview.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import re
import shutil
import stat

DUTS = {'abtb', 'bpu', 'ittage', 'mbtb', 'ras', 'sc', 'tage', 'ubtb', 'uras', 'utage'}
CANONICAL = ('feature-points.json', 'rtl-line-coverage.json', 'rtl-coverage-manifest.json',
             'verification-report.html', 'summary.json')
REPORTS = {'rtl-line-coverage.json', 'diagnostic-rtl-line-coverage.json',
           'qualification-native.json'}
PAGES = {'verification-report.html', 'diagnostic-coverage-report.html', 'coverage.html'}
ANALYSIS_WORDS = ('summary', 'analysis', 'diagnos', 'audit', 'qualification', 'review',
                  'receipt', 'manifest', 'retention', 'pruned', 'cleanup', 'plan',
                  'evidence', 'verdict', 'failure', 'mismatch', 'regression')


def load(path):
    return json.loads(path.read_text())


def fingerprint(path):
    with path.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def walk(root):
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if not (Path(directory)/name).is_symlink())
        for name in sorted(files):
            path = Path(directory)/name
            if stat.S_ISREG(path.lstat().st_mode):
                yield path


def protect(results, keep):
    """Resolve live report dependencies without retaining obsolete worker DATs."""
    protected = {path for path in walk(keep)}
    protected.update(results/name for name in CANONICAL if (results/name).is_file())
    reports = {results/'rtl-line-coverage.json'}
    profiles = results/'regression-profiles'
    for index in (profiles/'production/latest.json', profiles/'physical/latest.json',
                  profiles/'legacy-exhaustive.json'):
        if not index.exists():
            continue
        value = load(index)
        protected.add(index)
        if 'run_directory' in value:
            run = Path(value['run_directory'])
            for name in ('summary.json', 'exit.json', 'rtl-line-coverage.json'):
                protected.add(run/name)
            reports.add(run/'rtl-line-coverage.json')
        else:
            reports.add(Path(value['report']))
    for report in reports:
        if not report.exists():
            continue
        protected.add(report)
        for row in load(report).get('dut', {}).values():
            if row.get('lcov_file'):
                protected.add(Path(row['lcov_file']))
    canonical_lines = results/'rtl-lines'
    if canonical_lines.exists():
        protected.update(walk(canonical_lines))
    for path in protected:
        if (path.is_symlink() or not path.resolve().is_relative_to(results)
                or not path.is_file()):
            raise ValueError(f'invalid protected dependency: {path}')
    return protected


def category(relative):
    """Conservative allowlist: analysis has priority over generic trace names."""
    name = relative.name.lower()
    if name.endswith(('.dat', '.dat.gz')):
        return 'native DAT'
    if name.endswith(('.fst', '.vcd', '.fsdb', '.vpd', '.fst.gz', '.vcd.gz')):
        return 'waveform'
    if name.endswith(('.info', '.lcov', '.lcov.gz')):
        return 'LCOV'
    if name in REPORTS:
        return 'generated RTL report'
    if name in PAGES:
        return 'generated coverage HTML'
    if (name.startswith('functional-coverage') or name in
            {'functional.json', 'functional.json.gz', 'functional-summary.json'}):
        return 'functional coverage snapshot'
    if not name.endswith(('.json', '.json.gz', '.jsonl', '.ndjson')):
        return None
    if any(word in name for word in ANALYSIS_WORDS):
        return None
    parts = relative.parts
    if len(parts) == 1:
        # Root JSONs are the project's historical diagnosis/decision records.
        return None
    in_dut_output = parts[0] in DUTS or any(
        part == 'results' and parts[i+1] in DUTS for i, part in enumerate(parts[:-1]))
    if in_dut_output:
        return 'raw DUT scenario trace'
    if re.search(r'(^|[-_.])(trace|waveform|cycles?)([-_.]|$)', name):
        return 'raw trace'
    return None


def snapshot(results, keep):
    protected = protect(results, keep)
    candidates, kept, kinds, runs, inodes = [], {}, Counter(), defaultdict(Counter), set()
    selection = sha256()
    unique_bytes = 0
    for path in walk(results):
        relative = path.relative_to(results)
        kind = None if path in protected else category(relative)
        if not kind:
            kept[str(relative)] = fingerprint(path)
            continue
        info = path.stat()
        identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        record = [str(relative), *identity]
        selection.update(json.dumps(record, separators=(',', ':')).encode()+b'\n')
        candidates.append((path, identity))
        kinds[kind] += 1
        run = relative.parts[0] if len(relative.parts)>1 else '[root]'
        runs[run]['paths'] += 1
        if identity[:2] not in inodes:
            inodes.add(identity[:2])
            unique_bytes += info.st_blocks*512
            runs[run]['allocated_bytes'] += info.st_blocks*512
    return candidates, kept, dict(
        format='bpu-superseded-artifact-cleanup', version=1, results=str(results),
        keep_run=str(keep), created_at=datetime.now(timezone.utc).isoformat(),
        selection_sha256=selection.hexdigest(), selected_paths=len(candidates),
        unique_allocated_bytes=unique_bytes, categories=dict(kinds),
        retained_files=len(kept), retained_sha256=kept,
        runs={name:dict(value) for name,value in sorted(runs.items())},
        protected_dependency_paths=sorted(str(path.relative_to(results)) for path in protected),
        policy='latest run complete; published/profile comparison metadata only; '
               'historical measurement payload removed; analysis/logs/scripts retained',
        recovery='deleted measurement payload requires a rerun; historical receipts '
                 'and manifests describe original execution, not current raw availability')


def check_active(candidates):
    targets = {str(path) for path, _ in candidates}
    for process in Path('/proc').iterdir():
        if not process.name.isdigit() or int(process.name)==os.getpid():
            continue
        try:
            for handle in (process/'fd').iterdir():
                try:
                    target = os.readlink(handle)
                except OSError:
                    continue
                if target in targets:
                    raise RuntimeError(f'active process {process.name} references {target}')
        except (PermissionError, FileNotFoundError):
            continue


def apply(results, candidates, kept):
    check_active(candidates)
    before = shutil.disk_usage(results).free
    for path, identity in candidates:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode)
                or (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)!=identity
                or not path.resolve().is_relative_to(results)):
            raise RuntimeError(f'candidate changed: {path}')
    for path, _ in candidates:
        path.unlink()
    # Only directories emptied by the exact selected file removals are removed.
    parents = {parent for path,_ in candidates for parent in path.parents
               if parent != results and parent.is_relative_to(results)}
    for directory in sorted(parents,key=lambda path:len(path.parts),reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    for name, expected in kept.items():
        path = results/name
        if not path.is_file() or fingerprint(path)!=expected:
            raise RuntimeError(f'retained file changed: {name}')
    return dict(state='complete', deleted_paths=len(candidates),
                retained_hashes_verified=True, free_bytes_before=before,
                free_bytes_after=shutil.disk_usage(results).free,
                finished_at=datetime.now(timezone.utc).isoformat())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path(__file__).resolve().parents[1]/'results')
    parser.add_argument('--keep-run', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    results, keep, plan_path = args.results.resolve(), args.keep_run.resolve(), args.plan.resolve()
    if (results.name!='results' or not keep.is_dir() or keep==results
            or not keep.is_relative_to(results) or not plan_path.is_relative_to(results)):
        parser.error('results must be a results directory; keep/plan must be strictly inside it')
    candidates, kept, plan = snapshot(results,keep)
    if args.apply:
        previous = load(plan_path)
        if (previous['selection_sha256']!=plan['selection_sha256']
                or previous['keep_run']!=str(keep) or previous['results']!=str(results)):
            raise RuntimeError('selection differs from the inspected preview')
        # Preview was added after its own scan; it must not invalidate its own ledger.
        retained = dict(kept)
        retained.pop(str(plan_path.relative_to(results)),None)
        if retained!=previous['retained_sha256']:
            raise RuntimeError('retained evidence differs from preview')
        outcome = apply(results,candidates,kept)
        receipt = plan_path.with_name(plan_path.stem+'-receipt.json')
        with receipt.open('x') as stream:
            json.dump(dict(plan=plan_path.name,selection_sha256=plan['selection_sha256'],
                           categories=plan['categories'],**outcome),stream,indent=2)
    else:
        with plan_path.open('x') as stream:
            json.dump(plan,stream,indent=2)
    print(json.dumps({key:value for key,value in plan.items()
                      if key not in ('retained_sha256','runs','protected_dependency_paths')},indent=2))


if __name__=='__main__':
    main()
