"""suites.frontend.bpu.bpu.case.bypass.sram components."""

from suites.frontend.bpu.runtime.trace import dump_trace
from types import FunctionType
from suites.frontend.bpu.bpu.case.bypass.lower_ring import run_lower_ring
from suites.frontend.bpu.bpu.checker.bypass.sram_scenario import SramChecks
from suites.frontend.bpu.bpu.env.bypass.sram import SramObservation


async def run_sram_loop(agent, output):
    instances = []
    def factory(case):
        checker = SramChecks(case)
        instances.append(checker)
        return checker
    namespace = dict(run_lower_ring.__globals__, CombinedChecks=factory, CombinedObservation=SramObservation)
    scenario = FunctionType(run_lower_ring.__code__, namespace, run_lower_ring.__name__,
        run_lower_ring.__defaults__, run_lower_ring.__closure__)
    report = dict(formal_credit=False, native_credit=False, actual_memory_written_by_test=False,
        source_stimulus_code_unchanged=True)
    try:
        await scenario(agent, output)
        report.update(passed=True, summary=instances[0].bypass.finish())
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        if instances:
            checker = instances[0].bypass
            report.update(records=checker.records, sram_cycles=checker.sram_cycles,
                reset_cache_divergences=checker.reset_cache_divergences,
                failed_frame=checker.failed_frame)
        dump_trace((output / 'integrated-sram-reset-and-loop.json'), report)
    return report
