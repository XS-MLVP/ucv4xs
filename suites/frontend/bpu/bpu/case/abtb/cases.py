"""Normal pytest intent API for real integrated counter/write-lineage scenarios."""
from pathlib import Path
import sys
from tempfile import mkdtemp

from suites.frontend.bpu.bpu.case.abtb.alias_plan import ALL_CASES
from suites.frontend.bpu.bpu.case.abtb.alias import run_five_alias_cycle
from suites.frontend.bpu.bpu.model.abtb.final_not_taken import ALL_CASES as FINAL_NOT_TAKEN_CASES
from suites.frontend.bpu.bpu.case.abtb.final_not_taken import run_final_not_taken_cycle
from suites.frontend.bpu.bpu.case.abtb.later_taken import run_later_taken_cycle
from suites.frontend.bpu.bpu.case.abtb.requirements import require_counter_paths
from suites.frontend.bpu.bpu.coverage.abtb.session import CounterCaseCoverage
from suites.frontend.bpu.runtime.timing import CaseTiming


_RUNNERS = {'five_alias': run_five_alias_cycle, 'final_not_taken': run_final_not_taken_cycle,
            'later_taken': run_later_taken_cycle}


async def check_counter_case(agent, output, *, kind, bank, entry_set):
    if type(bank) is not int or type(entry_set) is not int:
        raise ValueError('physical bank/set must be integers, not aliases or booleans')
    supported = FINAL_NOT_TAKEN_CASES if kind == 'final_not_taken' else ALL_CASES
    if kind not in _RUNNERS or (bank, entry_set) not in supported:
        raise ValueError(f'unsupported integrated counter intent: {kind!r}, bank={bank!r}, set={entry_set!r}')
    case = f'{kind.replace("_", "-")}-bank{bank}-set{entry_set}'
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Independent artifact namespace; complete diagnostic traces remain opt-in.
    artifact = Path(mkdtemp(prefix=f'integrated-{case}-', dir=output))
    timing, coverage, passed = CaseTiming(), CounterCaseCoverage(), False
    coverage.timing = timing
    try:
        with timing.phase('stimulus_and_live_checks'):
            trace = await _RUNNERS[kind](agent, artifact, bank=bank, entry_set=entry_set, coverage=coverage)
        with timing.phase('coverage_finalize'):
            bypass_summary, counter_summary = coverage.validate(trace)
        paths = None
        with timing.phase('requirements'):
            if kind in ('final_not_taken', 'later_taken'):
                paths = require_counter_paths(counter_summary, bank=bank, entry_set=entry_set,
                    causes=('same_position_taken', kind))
        # Neither independent collector publishes credit until both validators
        # and all per-way requirements have succeeded and monitors are closed.
        with timing.phase('coverage_commit_and_export'):
            coverage.commit()
            coverage.bypass.save(output, case=case)
            coverage.counter.save(output, case=case)
        passed = True
        return dict(case=case, artifact=str(artifact), bypass=bypass_summary,
            counter=counter_summary, required_paths=paths, full_matrix_or_FTQ_closed=False)
    finally:
        coverage.abort()
        failure = sys.exception()
        try:
            timing.save(artifact / 'timing.json', passed=passed)
        except OSError as error:
            if failure is None:
                raise
            failure.add_note(f'Unable to save case timing: {error}')
