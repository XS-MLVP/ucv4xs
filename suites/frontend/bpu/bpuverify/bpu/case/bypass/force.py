"""bpuverify.bpu.case.bypass.force components."""

from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.checker.bypass.force import SramChecks


async def run_two_key(agent, output):
    from bpuverify.bpu.case.bypass.force_seed import run_seed
    from bpuverify.bpu.case.bypass.force_plan import second_key
    from bpuverify.bpu.case.bypass.force_second_key import force_old_entry_to_SRAM
    instances = []
    def factory(case):
        checker = SramChecks(case)
        instances.append(checker)
        return checker
    from types import FunctionType
    namespace = dict(run_seed.__globals__, CombinedChecks=factory)
    scenario = FunctionType(run_seed.__code__, namespace, run_seed.__name__,
        run_seed.__defaults__, run_seed.__closure__)
    scenario.__kwdefaults__ = run_seed.__kwdefaults__
    plan = second_key()
    report = dict(formal_credit=False, native_credit=False, actual_memory_written_by_test=False,
        metadata_fabricated=False, extra_cold_checkpoints_before_any_training=True, second_key=plan)
    try:
        await scenario(agent, output, extra_checkpoint_pcs=(plan['a'], plan['b'], plan['c']),
            continuation=force_old_entry_to_SRAM)
        report.update(passed=True, summary=instances[0].bypass.finish())
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        if instances:
            checker = instances[0].bypass
            report.update(records=checker.records, sram_cycles=checker.sram_cycles,
                bank_writes=checker.bank_writes, SRAM_reads=checker.SRAM_reads,
                forced_conflicts=checker.forced_conflicts,
                reset_cache_divergences=checker.reset_cache_divergences,
                failed_frame=checker.failed_frame)
        dump_trace((output / 'integrated-two-key-force-writeback.json'), report)
    return report
