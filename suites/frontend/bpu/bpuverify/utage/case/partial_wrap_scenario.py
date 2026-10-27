"""Public two-write intent and retained-neighbor readback; no signal operations."""

from bpuverify.common.env.trace import dump_trace, trace_exports_enabled
from dataclasses import asdict

from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.case.shadow_ring_scenario import prepare_shadow_contexts
from bpuverify.utage.case.shadow_ring_scenario import read_shadow_contexts
from bpuverify.utage.model.addressing import hash_indices
from bpuverify.utage.model.addressing import prediction_tag
from bpuverify.utage.checker.partial_wrap import UtagePartialWrapChecker


async def check_partial_wrap(agent, coverage, output, *, mode, bank):
    await agent.reset()
    contexts = await prepare_shadow_contexts(agent, table=1, bank=bank)
    cells = tuple(dict(valid=1, index=hash_indices(context.pc, context.history)[1],
        data_valid=1, tag=prediction_tag(context.pc, context.history, 1), position=5, counter=3)
        for context in contexts)
    checker = UtagePartialWrapChecker(cells, bank=bank, mode=mode)
    transaction = UtageTraining(contexts[0].pc, 5, 0, contexts[0].prediction.meta, mispredict=0)
    checker.plan((transaction, transaction))
    summary, failure, monitor = None, None, None
    try:
        async with agent.observe_partial_wrap(checker) as monitor:
            if mode == 'adjacent':
                await agent.train_many((transaction, transaction))
            else:
                await agent.train(transaction)
                await agent.train(transaction)
            predictions = await read_shadow_contexts(agent, contexts[2:], table=1)
            for context, observed in zip(contexts[2:], predictions, strict=True):
                entry = observed.meta['abtbResult'][0]
                checker.check((1, 0, 1, 3), (observed.hit, observed.taken, entry['tableId'],
                    entry['takenCtr_value']), point='retained neighbor public provider')
                checker.check(hash_indices(context.pc, context.history), tuple(observed.meta['readIndex']),
                    point='independent retained neighbor address')
            summary = checker.finish()
        for phase in ('old_slot2_payload', 'all_retained_neighbors'):
            coverage.sample(dict(mode=mode, bank=bank, phase=phase))
    except BaseException as error:
        failure = repr(error)
        raise
    finally:
        if trace_exports_enabled():
            result = dict(format='bpu-utage-partial-shadow-wrap-candidate', version=1,
                bank=bank, mode=mode, original_contexts=[asdict(context) for context in contexts],
                initial_expected_cells=cells, genuine_feedback=asdict(transaction), feedback_count=2,
                passive_trace=[] if monitor is None else monitor.trace, summary=summary,
                failure=failure, formal_credit=False)
            dump_trace(output / f'partial-wrap-bank{bank}-{mode}.json', result)
