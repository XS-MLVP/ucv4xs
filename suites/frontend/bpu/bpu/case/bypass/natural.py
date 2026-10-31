"""suites.frontend.bpu.bpu.case.bypass.natural components."""

from collections import Counter
from suites.frontend.bpu.runtime.trace import dump_trace
from types import FunctionType
from suites.frontend.bpu.bpu.case.abtb.natural import run_natural_counter_sweep
from suites.frontend.bpu.bpu.checker.bypass.natural import CombinedChecks
from suites.frontend.bpu.bpu.env.bypass.natural import CombinedObservation


async def run_checked_natural_loop(agent, output, *, bank):
    instances = []
    def checker_factory(case):
        checker = CombinedChecks(case)
        instances.append(checker)
        return checker
    # Preserve the exact admitted stimulus code object. Only the two reusable
    # extension points change; no caller's globals or signed source is edited.
    namespace = dict(run_natural_counter_sweep.__globals__,
        IntegratedChecks=checker_factory, IntegratedObservation=CombinedObservation)
    stimulus = FunctionType(run_natural_counter_sweep.__code__, namespace,
        run_natural_counter_sweep.__name__, run_natural_counter_sweep.__defaults__,
        run_natural_counter_sweep.__closure__)
    report = dict(bank=bank, formal_credit=False, native_credit=False,
        scope='reset-derived 16shadow cells+1024useful cells+selection+training source+ring writeback',
        independent_parent_policy_or_SRAM_persistence_claimed=False,
        hardware_state_written=False, stimulus_code_unchanged=True)
    try:
        await stimulus(agent, output, dict(pc_bank=bank))
        checker = instances[0].bypass
        report['summary'] = checker.finish()
        assert checker.writes, 'no real integrated shadow writes observed'
        report['write_categories'] = dict(Counter((row['table'], row['source']) for row in checker.writes))
        report['write_categories'] = [{'table': table, 'source': source, 'count': count}
            for (table, source), count in report['write_categories'].items()]
        report['passed'] = True
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        if instances:
            report['records'] = instances[0].bypass.records
            report['writes'] = instances[0].bypass.writes
        dump_trace((output / f'integrated-bypass-bank{bank}.json'), report)
    # Share the already sampled frames with the reusable successful-trace
    # collector. The inner scenario has persisted these complete observations;
    # do not duplicate that large trace in the bypass artifact or resample DUT.
    report['counter_trace'] = dict(passed=True, records=instances[0].records,
        preedge_records=instances[0].control_records)
    return report
