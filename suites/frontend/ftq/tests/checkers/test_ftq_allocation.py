"""Allocation-plan and direct preview controls, not hardware feature credit."""
from types import SimpleNamespace

import pytest

from suites.frontend.ftq.ftq.agent.main import FtqAgent
from suites.frontend.ftq.ftq.transaction.cycle import FtqInput, allocation_plan
from suites.frontend.ftq.ftq.transaction.types import (
    BackendRedirect, Meta, PredictionSpec, RedirectEvent, TrainingEntry,
)

pytestmark = pytest.mark.selftest


def test_prediction_spec_owns_its_metadata_snapshot():
    payload = {'resolveMeta_phr_phrPtr_value': 7}
    spec = PredictionSpec(0, meta=payload)
    payload['resolveMeta_phr_phrPtr_value'] = 8
    assert spec.meta['resolveMeta_phr_phrPtr_value'] == 7
    with pytest.raises(TypeError):
        spec.meta['resolveMeta_phr_phrPtr_value'] = 9


@pytest.mark.parametrize('values', (
    dict(start_pc=1 << 50), dict(start_pc=0, taken=True),
    dict(start_pc=0, meta={'unknown': 1}),
    dict(start_pc=0, meta={'resolveMeta_phr_phrPtr_value': 1 << 10}),
))
def test_prediction_spec_rejects_bad_domain_before_an_allocation_plan_is_used(values):
    with pytest.raises(ValueError):
        PredictionSpec(**values)


async def test_allocate_rejects_later_duck_spec_before_any_input_progress():
    effects = []

    async def called(*args, **kwargs):
        effects.append((args, kwargs))
        return SimpleNamespace(ready=True)

    agent = SimpleNamespace(consumers=called, offer=called, step=called,
        complete_offer=called, write_meta=called)
    with pytest.raises(ValueError, match='PredictionSpec'):
        await FtqAgent.allocate(agent, (PredictionSpec(0),
            SimpleNamespace(start_pc=1, taken=1, end_position=3, meta={})), consume=True)
    assert not effects


@pytest.mark.parametrize('options', (
    dict(consume=1), dict(with_meta=0), dict(meta_limit=True),
    dict(meta_limit=-1), dict(meta_limit=1.5), dict(start_index=True),
    dict(start_index=64), dict(start_flag=True), dict(start_flag=2),
))
async def test_invalid_later_plan_options_cannot_change_consumer_levels_or_the_first_entry(ftq_agent, options):
    agent = ftq_agent
    before = agent.input_driver.frame
    count = agent.dut.sampled_cycles
    with pytest.raises(ValueError):
        await agent.allocate((PredictionSpec(0),), **options)
    assert agent.input_driver.frame == before
    assert agent.dut.sampled_cycles == count
    assert not agent.input_receipt()


def test_full_plan_keeps_complete_domain_and_wraps_the_explicit_pointer_flag():
    spec = PredictionSpec((1 << 50) - 1, end_position=31,
        meta={'redirectMeta_ras_topRetAddr_addr': (1 << 50) - 1})
    plan = allocation_plan((spec, spec), start_index=63, start_flag=1)
    assert [(meta.flag, meta.index) for _, meta in plan] == [(1, 63), (0, 0)]
    assert plan[0][0].start_pc == spec.start_pc
    assert plan[1][1].fields == spec.meta
    assert allocation_plan((spec,) * 2, meta_limit=1)[1][1] is None
    assert all(meta is None for _, meta in allocation_plan((spec,) * 2, with_meta=False))


@pytest.mark.parametrize('build', (
    lambda fields: RedirectEvent(0, 0, 0, 0, 0, 0, 0, metadata=fields),
    lambda fields: TrainingEntry(0, (0, 0, 0, 16), (), 0, 0, 0, metadata=fields),
))
def test_direct_record_constructor_cannot_alias_mutable_metadata(build):
    payload = {'known': 7}
    value = build(payload)
    payload['known'] = 8
    assert value.metadata['known'] == 7
    with pytest.raises(TypeError):
        value.metadata['known'] = 9


async def test_matched_ahead_redirect_preview_is_a_detached_readonly_record(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x80001000),) * 2)
    await agent.write_meta(Meta(1, fields={'redirectMeta_commonHRMeta_ghr': 7}))
    await agent.ahead_set(1)
    await agent.ahead_clear()
    event, _ = await agent.drive_backend_redirect(BackendRedirect(1, offset=0))
    assert event is not None
    assert event.metadata['commonHRMeta_ghr'] == 7
    with pytest.raises(TypeError):
        event.metadata['commonHRMeta_ghr'] = 8
    await agent.finish_backend_redirect()
    # Redirect flushes this slot. Re-establish its producer before new s3 meta;
    # a bare meta1 here would illegally advance PNR beyond the rewound BPU1.
    await agent.allocate((PredictionSpec(0x80002000,
        meta={'redirectMeta_commonHRMeta_ghr': 9}),), start_index=1)
    assert event.metadata['commonHRMeta_ghr'] == 7


async def test_reset_cannot_return_the_old_epoch_redirect_topdown_snapshot(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x80001000),))
    await agent.backend_redirect(BackendRedirect(0))
    assert agent.redirect_topdown().backend_redirect
    await agent.reset()
    with pytest.raises(AssertionError, match='no redirect topdown'):
        agent.redirect_topdown()
    assert agent.input_driver.frame == FtqInput()
