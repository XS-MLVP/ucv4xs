"""Normal pytest intent API: protocol timing and coverage stay below the test."""
from suites.frontend.bpu.bpu.case.bypass.natural import run_checked_natural_loop
from suites.frontend.bpu.bpu.case.bypass.lower_ring import run_lower_ring
from suites.frontend.bpu.bpu.case.bypass.sram import run_sram_loop
from suites.frontend.bpu.bpu.case.bypass.force import run_two_key
from suites.frontend.bpu.bpu.case.bypass.history import run_nonzero_loop
from suites.frontend.bpu.bpu.case.bypass.alternate_history import run_nonzero_loop as run_alternate_loop
from suites.frontend.bpu.bpu.case.bypass.two_program import run_two_programs
from suites.frontend.bpu.bpu.case.bypass.policy_program import run_two_programs as run_policy_program
from suites.frontend.bpu.bpu.case.bypass.aging import run_natural_aging
from suites.frontend.bpu.bpu.coverage.bypass.supplemental import IntegratedCoverage
from suites.frontend.bpu.bpu.coverage.abtb.supplemental import CounterCoverage
from suites.frontend.bpu.bpu.coverage.bypass.selection import ResponseSelectionCoverage


CASES = (('natural', 0), ('natural', 1), ('lower', 0), ('sram', 0),
         ('force', 0), ('history', 2), ('history', 3), ('alternate', 1),
         ('two_program', 1), ('policy', 1), ('aging', 1))
_RUNNERS = {
    'natural': run_checked_natural_loop, 'lower': run_lower_ring,
    'sram': run_sram_loop, 'force': run_two_key, 'history': run_nonzero_loop,
    'alternate': run_alternate_loop, 'two_program': run_two_programs,
    'policy': run_policy_program, 'aging': run_natural_aging,
}


async def check_integrated_case(agent, output, *, kind, bank=0):
    if (kind, bank) not in CASES:
        raise ValueError(f'unsupported integrated intent: {kind!r}, bank={bank!r}')
    case = f'{kind}-{bank}'
    artifact = output / f'integrated-{case}'
    artifact.mkdir(parents=True, exist_ok=True)
    kwargs = {} if kind in ('lower', 'sram', 'force') else dict(bank=bank)
    trace = await _RUNNERS[kind](agent, artifact, **kwargs)
    coverage = IntegratedCoverage()
    summary = coverage.collect(trace)
    selection = ResponseSelectionCoverage()
    # Selection has its own reset-derived replay and valid-payload gate; a
    # testcase PASS or an observed slot alone must never earn these bins.
    selection_trace = dict(trace, bypass_records=trace.get('bypass_records', trace.get('records')))
    summary['response_selection'] = selection.collect(selection_trace)
    counter = None
    if kind == 'natural':
        counter = CounterCoverage()
        summary['abtb_counter'] = counter.collect(trace['counter_trace'])
    # Both replays must succeed before either collector publishes a report.
    coverage.save(output, case=case)
    selection.save(output, case=case)
    if counter is not None:
        counter.save(output, case=case)
    return summary
