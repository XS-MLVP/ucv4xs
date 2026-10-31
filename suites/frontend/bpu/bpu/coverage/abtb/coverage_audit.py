"""Read-only replay of archived observations, never formal coverage promotion.

Run with ``python -m suites.frontend.bpu.integrated.abtb.coverage_audit --output NEW.json
TRACE.json [TRACE.json.gz ...]``. Inputs and the replay sources are checked
before and after; output creation is exclusive so an old audit is not replaced.
"""
import argparse
from datetime import datetime
from datetime import timezone
import gzip
from hashlib import file_digest
import importlib
import json
from pathlib import Path
import sys

from suites.frontend.bpu.bpu.coverage.abtb.supplemental import CounterCoverage


def identity(path):
    with path.open('rb') as stream:
        digest = file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path.resolve()), size=path.stat().st_size, sha256=digest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('traces', type=Path, nargs='+')
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('output already exists; preserve the old audit and choose a new path')
    paths = [path.resolve(strict=True) for path in args.traces]
    if len(set(paths)) != len(paths):
        parser.error('duplicate input traces')
    modules = ('suites.frontend.bpu.bpu.coverage.abtb.coverage_audit',
        'suites.frontend.bpu.bpu.coverage.abtb.supplemental', 'suites.frontend.bpu.bpu.case.abtb.provenance',
        'suites.frontend.bpu.abtb.model.state.counter', 'suites.frontend.bpu.bpu.model.sc.model',
        'toffee.coverage', 'toffee.scoreboard')
    sources = [Path(importlib.import_module(module).__file__).resolve() for module in modules]
    before = [identity(path) for path in paths + sources]
    results = []
    error = None
    try:
        for path in paths:
            opener = gzip.open if path.suffix == '.gz' else open
            with opener(path, 'rt') as stream:
                trace = json.load(stream)
            coverage = CounterCoverage()
            summary = coverage.collect(trace)
            results.append(dict(trace=str(path), replay_passed=True, summary=summary,
                group_coverage={group.instance: group.coverage for group in coverage.groups}))
            print(dict(trace=str(path), replay_passed=True,
                physical_path_bins=len(summary['transition_counts'])), flush=True)
            del trace, coverage
    except Exception as failure:
        error = repr(failure)
    after = [identity(path) for path in paths + sources]
    unchanged = before == after
    status = int(error is not None or not unchanged or len(results) != len(paths))
    report = dict(format='bpu-integrated-abtb-counter-coverage-readonly-audit', version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        process_exitstatus=status, failure=error, inputs_and_sources_unchanged=unchanged,
        identities=before, results=results, formal_credit=False, fresh_DUT_run=False,
        old_transition_claims_used_as_sampling_evidence=False, goal_complete=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(dict(process_exitstatus=status, inputs_and_sources_unchanged=unchanged, failure=error), flush=True)
    return status


if __name__ == '__main__':
    sys.exit(main())
