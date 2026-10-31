"""Frozen BPU production entry: generic execution/coverage belongs to toffee."""
from collections import Counter
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET

from tools.refresh_coverage import ROOT, FLOOR, NAMES, read, write, digest, source_epoch
from suites.frontend.bpu.pytest_plugins.points import summary_for, validate_report

CANONICAL = ('feature-points.json','rtl-line-coverage.json','rtl-coverage-manifest.json',
             'verification-report.html','summary.json')


def snapshot_publications(results):
    """Protect live publications, not deleted historical output locations.

    A compact baseline's original input names are provenance only. Follow its
    retained LCOV and evidence bundle, never recreate its obsolete run trees.
    Legacy publications remain protected whenever they are actually present.
    """
    results=Path(results).resolve()
    paths={results/name for name in CANONICAL if (results/name).is_file()}
    paths.update(results/name for name in ('latest-complete-measurement.json',
        'current-semantic-gap-review.json','current/summary.json','current/qualified-execution-union.json')
        if (results/name).is_file())

    def retained(name, expected):
        path=Path(name)
        if not path.is_absolute():
            path=(results.parent/path if path.parts[0]==results.name else results/path)
        if not path.resolve().is_relative_to(results) or not path.is_file() or digest(path)!=expected:
            raise ValueError(f'missing, foreign or changed current baseline artifact: {path}')
        paths.add(path)

    index=results/'current/native-index.json'
    if index.is_file():
        paths.add(index)
        for row in read(index)['dut'].values():retained(row['lcov_file'],row['sha256'])
    index=results/'current/evidence-index.json'
    if index.is_file():
        paths.add(index)
        value=read(index);retained(value['bundle'],value['sha256'])
    return {str(path.relative_to(results)):digest(path) for path in sorted(paths)}


def execution_verdicts(path, expected):
    """Preserve ordinary failures, strict xfails and exact parameter identities."""
    from _pytest.junitxml import bin_xml_escape, mangle_test_address
    keys, actual = {}, {}
    for node in expected:
        parts = mangle_test_address(node)
        key = '.'.join(parts[:-1]), bin_xml_escape(parts[-1])
        if key in keys:
            raise ValueError('ambiguous JUnit identity')
        keys[key] = node
    for case in ET.parse(path).getroot().findall('.//testcase'):
        key = case.get('classname'), case.get('name')
        if key not in keys or keys[key] in actual:
            raise ValueError('unexpected or duplicate JUnit test')
        skipped = case.find('skipped')
        if skipped is not None and skipped.get('type') != 'pytest.xfail':
            raise ValueError('ordinary skip is not qualified production evidence')
        actual[keys[key]] = ('ERROR' if case.find('error') is not None else
            'FAIL' if case.find('failure') is not None else 'XFAIL' if skipped is not None else 'PASS')
    if actual.keys() != set(expected):
        raise ValueError('JUnit execution differs from the frozen collection')
    return actual


def managed_command(output, args):
    command = [sys.executable, '-m', 'toffee', 'run', '--output', str(output/'execution'),
        '--workers', str(args.workers), '-q', '-p', 'no:cacheprovider', '--tb=short',
        f'--junitxml={output}/pytest.xml', '--durations=20', f'--regression-profile={args.regression_profile}']
    if args.workers > 1:
        command.append('--maxschedchunk=1')
    if getattr(args, 'keep_coverage_inputs', False) or getattr(args, 'dump_trace', False):
        command.append('--keep-coverage-inputs')
    if getattr(args, 'export_coverage_json', False):
        command.append('--export-coverage-json')
    if getattr(args, 'dump_trace', False):
        command.append('--dump-trace')
    if not args.select:
        command.append('--bpu-full-suite')
    return command + (args.select or [])


def run_unpartitioned(args):
    output = args.run_dir.resolve()
    automatic_epoch = source_epoch()
    epoch = dict(automatic_epoch)
    if args.source_epoch:
        supplied = read(args.source_epoch)
        if any(digest(path) != sha for path,sha in supplied.items()):
            raise ValueError('supplied source epoch changed')
        epoch.update(supplied)
    protected = snapshot_publications(ROOT/'results')
    output.mkdir(parents=True, exist_ok=False)
    write(output/'source-epoch.json', epoch)
    write(output/'owner.json', dict(pid=os.getpid(), engine='xreactor-managed', workers=args.workers,
        full_suite_requested=not bool(args.select), selected_scopes=args.select,
        native_merge_owner='toffee', functional_merge_owner='toffee',
        cycle_trace_export=False, per_case_functional_export=False, normal_disk_floor_bytes=FLOOR))
    started, stages = time.monotonic(), []
    result = dict(engine='xreactor-managed', process_exitstatus=1, goal_complete=False,
        regression_profile=args.regression_profile, reports_published=False,
        full_regression_complete=False, selected_regression_complete=False)

    def stage(label, command):
        if shutil.disk_usage(output).free < FLOOR:
            raise RuntimeError('normal disk safety floor reached')
        before = time.monotonic()
        with (output/f'{label}.log').open('x') as stream:
            child = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            write(output/f'{label}-process.json',dict(pid=child.pid,command=command))
            print(f'{label}: PID {child.pid}, {output}/{label}.log',flush=True)
            code = child.wait()
        stages.append(dict(stage=label,exitstatus=code,elapsed_seconds=time.monotonic()-before))
        return code

    try:
        code = stage('collection',[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',
            f'--regression-profile={args.regression_profile}','--collect-only',*(args.select or [])])
        if code:
            raise ValueError('collection failed')
        expected = [line for line in (output/'collection.log').read_text().splitlines()
                    if line.startswith('tests/') and '::' in line]
        if not expected or len(expected) != len(set(expected)):
            raise ValueError('invalid frozen collection')
        print(f'managed regression: {len(expected)} tests, {args.workers} workers',flush=True)
        code = stage('pytest',managed_command(output,args))
        execution = output/'execution'
        manifest = read(execution/'manifest.json')
        if (manifest.get('state') != 'committed' or not manifest.get('coverage_complete')
                or not manifest.get('cleanup_complete') or manifest.get('cleanup_error')
                or manifest['pytest_exitstatus'] != code):
            raise ValueError('managed coverage did not commit and cleanly consume its inputs')
        for row in manifest['artifacts']:
            path = Path(row['path'])
            if (not path.is_relative_to(execution) or path.is_symlink()
                    or path.stat().st_size != row['size'] or digest(path) != row['sha256']):
                raise ValueError('committed managed artifact identity changed')
        tests = execution_verdicts(output/'pytest.xml',expected)
        if dict(Counter(tests.values())) != manifest['tests']:
            raise ValueError('managed verdict counts differ from exact JUnit collection')
        features = read(execution/'feature-points.json')
        validate_report(features)
        if features['integrity_errors']:
            raise ValueError('project feature evidence incomplete')
        planned = {row['id'] for row in read(ROOT/'verification_plan.json')['features']}
        if {row['id'] for row in features['features']} != planned:
            raise ValueError('functional point identities differ from current plan')
        for row in features['features']:
            if any(tests.get(test['nodeid']) != test['status'] for test in row['tests']):
                raise ValueError('feature/test verdict association changed')
        if not args.select and summary_for(features,'all')['executed'] != len(planned):
            raise ValueError('full regression has unexecuted functional points')
        from suites.frontend.bpu.coverage.rtl import build_report
        native = build_report(execution/'rtl-coverage-manifest.json',output/'rtl-line-coverage.json')
        if not args.select and set(native['dut']) != set(NAMES):
            raise ValueError('full regression did not measure all ten DUTs')
        if not all(digest(path) == sha for path,sha in epoch.items()) or source_epoch() != automatic_epoch:
            raise ValueError('frozen execution source changed')
        if any(digest(ROOT/'results'/name) != sha for name,sha in protected.items()):
            raise ValueError('canonical reports changed')
        shutil.copyfile(execution/'feature-points.json',output/'feature-points.json')
        functional = read(execution/'functional-summary.json')
        write(output/'test-results.json',tests)
        result.update(process_exitstatus=code, coverage_complete=True, tests=dict(Counter(tests.values())),
            exact_collection=len(expected), full_execution_complete=not bool(args.select),
            full_regression_complete=not args.select and code==0,
            selected_regression_complete=bool(args.select) and code==0,
            functional_points=summary_for(features), environment_contracts=summary_for(features,'environment'),
            all_points=summary_for(features,'all'), functional_groups=functional['total_groups'],
            full_groups=functional['full_groups'], source_epoch_unchanged=True, canonical_reports_unchanged=True,
            native_source_lines={name:row['source_lines'] for name,row in native['dut'].items()},
            coverage_report=str(execution/'coverage.html') if (execution/'coverage.html').is_file() else None,
            native_artifact_count=sum(row['kind']=='native' for row in manifest['artifacts']),
            worker_inputs_reclaimed=not (execution/'_workers').exists())
        write(output/'summary.json',result)
    except BaseException as error:
        result.update(failure=repr(error),traceback=traceback.format_exc())
        print(result['traceback'],file=sys.stderr,flush=True)
    finally:
        result.update(stages=stages,elapsed_seconds=time.monotonic()-started,
            finished_at=datetime.now(timezone.utc).isoformat())
        write(output/'exit.json',result)
    return result['process_exitstatus']


def run(args):
    """Default production path never mixes generated DUT packages in a worker."""
    from tools.dut_isolated_regression import run as isolated_run
    return isolated_run(args)
