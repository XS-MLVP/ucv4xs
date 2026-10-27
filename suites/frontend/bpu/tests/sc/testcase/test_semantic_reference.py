"""SC learning is conditioned on history, not caller-supplied table indices."""
import pytest

from bpuverify.sc.transaction.types import ScHistory, ScTraining


@pytest.mark.feature('BPU-SC-023')
async def test_parallel_history_contexts_use_their_own_learned_weight_snapshots(sc_agent):
    await sc_agent.reset()
    pc, position, counter = 0x40000040, 4, 4
    contexts = (ScHistory(), ScHistory(0x93, 0x9b, 0xb, 0xa5),
                ScHistory(0x42, 0x63, 0x6, 0x39, common_valid=False))
    # Different semantic contexts share the PC bias but have distinct history
    # features. Each feedback returns the actual source metadata unchanged.
    for history, taken in zip(contexts, (0, 1, 0), strict=True):
        prediction = await sc_agent.predict(pc, position, counter, history=history)
        await sc_agent.train(ScTraining(pc, position, taken, prediction.meta, history=history))
    baseline = [await sc_agent.predict(pc, position, counter, history=history) for history in contexts]
    before = sc_agent.reference.board.status.checked
    sequence = (0, 1, 2, 1, 0, 2)
    transfers = [sc_agent.submit_predict(pc, position, counter, history=contexts[index]) for index in sequence]
    await sc_agent.drain_predictions()
    predictions = [await transfer for transfer in transfers]
    assert [value.meta for value in predictions] == [baseline[index].meta for index in sequence]
    assert [value.taken for value in predictions] == [baseline[index].taken for index in sequence]
    assert baseline[0].taken == 0 and baseline[1].taken == 1 and baseline[2].taken == 0
    assert sc_agent.reference.board.status.checked >= before + len(sequence)
    assert sc_agent.reference.board.status.failed == 0
    for group in sc_agent.semantic_coverage.groups.values():
        group.assert_coverage(100)
