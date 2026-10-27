"""Native comparisons are strict within a scope and explicit across scopes."""
from __future__ import annotations

import json
from pathlib import Path

from bpuverify.common.pytest.regression import PROFILES


def profile_index(root, profile):
    if profile not in PROFILES:
        raise ValueError(f'unknown regression profile: {profile}')
    return Path(root) / 'results' / 'regression-profiles' / profile / 'latest.json'


def load_baseline(root, profile, *, read, digest):
    index = profile_index(root, profile)
    if not index.exists():
        legacy = Path(root) / 'results/regression-profiles/legacy-exhaustive.json'
        if profile == 'physical' and legacy.exists():
            value = read(legacy)
            report = Path(value['report'])
            if (value.get('format') != 'bpu-legacy-exhaustive-baseline' or not report.is_absolute()
                    or report.resolve() != report or not report.is_relative_to((Path(root)/'results').resolve())
                    or digest(report) != value['sha256']):
                raise ValueError('legacy physical native baseline changed')
            return read(report)
        return None
    value = read(index)
    run = Path(value['run_directory'])
    results = (Path(root) / 'results').resolve()
    if (value.get('format') != 'bpu-regression-profile' or value.get('version') != 1
            or value.get('regression_profile') != profile or not run.is_absolute()
            or run.resolve() != run or not run.is_relative_to(results)):
        raise ValueError('invalid regression profile baseline identity')
    for name in ('summary.json', 'rtl-line-coverage.json', 'exit.json'):
        if digest(run / name) != value['sha256'][name]:
            raise ValueError('regression profile baseline changed: ' + name)
    summary, exit_result = read(run / 'summary.json'), read(run / 'exit.json')
    for report in (summary, exit_result):
        if (report.get('regression_profile') != profile or report.get('process_exitstatus') != 0
                or report.get('full_regression_complete') is not True):
            raise ValueError('baseline is not a successful full-profile regression')
    native = read(run / 'rtl-line-coverage.json')
    if native.get('regression_profile') != profile or native.get('selected_measurement') is not False:
        raise ValueError('native baseline scope differs from full-profile regression')
    return native


def retain_legacy_baseline(root, archive, summary, *, digest):
    """Pin the pre-profile exhaustive view before a representative publish."""
    target = Path(root) / 'results/regression-profiles/legacy-exhaustive.json'
    if target.exists() or summary.get('regression_profile') is not None:
        return
    if summary.get('full_regression_complete') is not True or summary.get('process_exitstatus') != 0:
        raise ValueError('cannot retain an incomplete legacy full regression')
    report = Path(archive) / 'rtl-line-coverage.json'
    with target.open('x') as stream:
        json.dump(dict(format='bpu-legacy-exhaustive-baseline', report=str(report.resolve()),
                       sha256=digest(report)), stream, indent=2)
        stream.write('\n')


def compare_native(native, published, prior, *, lcov):
    """Keep the entire native universe; scope transitions never count as gain."""
    if set(native['dut']) != set(published['dut']):
        raise ValueError('native DUT universe changed')
    losses, comparison = {}, {}
    if prior is not None and set(prior['dut']) != set(native['dut']):
        raise ValueError('profile baseline DUT universe changed')
    for name, row in native['dut'].items():
        fresh = lcov(row['lcov_file'])
        previous = lcov(published['dut'][name]['lcov_file'])
        if set(fresh) != set(previous):
            raise ValueError(f'native source-line denominator changed: {name}')
        comparison[name] = dict(total=len(fresh), current_hit=sum(count > 0 for count in fresh.values()),
            published_hit=sum(count > 0 for count in previous.values()),
            published_hit_now_unhit=sum(count > 0 and fresh[key] == 0 for key, count in previous.items()),
            published_unhit_now_hit=sum(count == 0 and fresh[key] > 0 for key, count in previous.items()))
        if prior is not None:
            scoped = lcov(prior['dut'][name]['lcov_file'])
            if set(fresh) != set(scoped):
                raise ValueError(f'profile native source-line denominator changed: {name}')
            missing = [key for key, count in scoped.items() if count > 0 and fresh[key] == 0]
            if missing:
                losses[name] = missing
    return losses, dict(same_profile_baseline_available=prior is not None,
                        initial_profile_measurement=prior is None, dut=comparison)


def publish_index(root, profile, run, *, digest):
    """Pointer only: immutable run artifacts retain each profile separately."""
    index = profile_index(root, profile)
    index.parent.mkdir(parents=True, exist_ok=True)
    value = dict(format='bpu-regression-profile', version=1, regression_profile=profile,
        run_directory=str(Path(run).resolve()),
        sha256={name: digest(Path(run) / name)
                for name in ('summary.json', 'rtl-line-coverage.json', 'exit.json')})
    pending = index.with_suffix('.pending')
    with pending.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    pending.replace(index)
