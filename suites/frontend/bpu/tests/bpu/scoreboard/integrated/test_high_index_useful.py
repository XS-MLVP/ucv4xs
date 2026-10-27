"""Real checkpoint geometry, independent high-row roles and late-fault gates."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from toffee import Scoreboard, ScoreboardMismatch
from bpuverify.bpu.case.bypass.high_index import HIGH_INDEX_CONTRACTS, coverage_model
from bpuverify.bpu.coverage.bypass.high_index import collect_updates
from bpuverify.bpu.env.bypass.program import ProgramEnvironment
from bpuverify.bpu.env.bypass.sparse import SparseProgramEnvironment
from bpuverify.bpu.model.bypass.high_index import base_alias, program
from bpuverify.bpu.model.abtb.alias import physical_index
from bpuverify.bpu.model.bypass.model import BypassReference
from bpuverify.bpu.model.bypass.sparse import joint_proof, recipe
from bpuverify.bpu.transaction.types import BpuMeta, BpuPrediction, BpuTransaction
from tests.bpu.scoreboard.integrated.test_coverage_collection import inputs


class BootstrapHarness(ProgramEnvironment):
    def __init__(self):
        super().__init__(self, None, None, {})
        self.cold, self.recoveries = [], []

    async def wait(self, operation, *args):
        return await operation

    async def reset(self, pc):
        self.reset_pc = pc

    async def configure_predictors(self, **enabled):
        self.enables = enabled

    async def next_transaction(self, *, start_pc, **limits):
        assert start_pc % 16 == 0  # Actual cold stream's address stride.
        self.cold.append(start_pc)
        return SimpleNamespace(prediction=SimpleNamespace(start_pc=start_pc))

    async def recover(self, target, checkpoint, label):
        source = checkpoint.prediction.start_pc
        assert (source & ~7) == ((target - 1) & ~7) and source <= target - 1
        self.recoveries.append(dict(source=source, target=target, cfi=target - 1))
        return SimpleNamespace(prediction=SimpleNamespace(start_pc=target))


@pytest.mark.parametrize('offset', range(16))
async def test_bootstrap_captures_real_second_half_sources_when_required(offset):
    pc = 0x40010100 + offset
    env = BootstrapHarness()
    await env.bootstrap((dict(pc=pc),))
    assert env.checkpoints[pc].prediction.start_pc == pc - 1
    assert env.cold == [(pc - 2) & ~15]
    assert len(env.recoveries) == (2 if (pc - 2) & 8 else 1)
    if len(env.recoveries) == 2:
        assert env.recoveries[0]['target'] == ((pc - 2) & ~7)


async def test_existing_sparse_programs_keep_their_original_single_stage_sources():
    for value in (recipe()['old'], recipe()['second']):
        env = BootstrapHarness()
        await env.bootstrap(tuple(dict(pc=pc) for pc in value['nodes']))
        assert len(env.recoveries) == 4
        assert env.cold == [(pc - 1) & ~15 for pc in sorted(value['nodes'])]


class WarmHarness(SparseProgramEnvironment):
    def __init__(self):
        self.board, self.final_sources, self.restored, self.redirects = Scoreboard('warm-source'), [], [], []
        checker = SimpleNamespace(compare=lambda expected, actual, **context:
            self.board.check(expected=expected, actual=actual))
        super().__init__(self, checker, None, {})

    def check_final(self, actual, **expected):
        self.final_sources.append(actual)

    async def restore_steady(self, value, checkpoint):
        self.restored.append(checkpoint)
        return 40

    async def redirect(self, redirect):
        self.redirects.append(redirect.payload())
        return 40

    async def next_transaction(self, **selection):
        assert selection == dict(start_pc=program()['pc'], after_tick=40, limit=256)
        return 'genuine-new-A'

    async def wait(self, operation, *args):
        return await operation


async def test_warm_capture_uses_installed_D_source_and_exact_redirect_boundary():
    env, value = WarmHarness(), program()
    checkpoint = SimpleNamespace(prediction=SimpleNamespace(start_pc=value['nodes'][3]))
    env.use_steady_source(value, checkpoint)
    assert await env.capture(value, 'capture') == 'genuine-new-A'
    assert env.restored == env.final_sources == [checkpoint]


async def test_warm_C_capture_redirects_to_D_with_the_real_C_CFI_and_metadata():
    env, value = WarmHarness(), program()
    checkpoint = BpuTransaction(20, 24,
        BpuPrediction(value['nodes'][2], value['nodes'][3], 1, 7, 0, 0),
        BpuMeta({}, dict(genuine_C_checkpoint='unit-token'), None))
    env.use_steady_source(value, checkpoint, source='C')
    assert await env.capture(value, 'capture') == 'genuine-new-A'
    assert env.final_sources == [checkpoint] and not env.restored
    assert env.redirects == [dict(meta=checkpoint.meta.redirect, target=value['nodes'][3],
        cfi_pc=(value['nodes'][2] & ~7) + 7, taken=1, branch_type=3, ras_action=0)]
    assert env.report['steady_recoveries'][0]['accepted_tick'] == 40


def test_wrong_warm_source_fails_before_storing_a_checkpoint():
    env, value = WarmHarness(), program()
    checkpoint = SimpleNamespace(prediction=SimpleNamespace(start_pc=value['pc']))
    with pytest.raises(ScoreboardMismatch):
        env.use_steady_source(value, checkpoint)
    assert not env.final_sources and not hasattr(env, '_steady_sources')


@pytest.mark.parametrize('source', (None, 'A', 'B', 'C ', False))
async def test_unsupported_warm_source_is_rejected_before_native_work(source):
    env, value = WarmHarness(), program()
    with pytest.raises(ValueError, match='C or D'):
        env.use_steady_source(value, None, source=source)
    with pytest.raises(ValueError, match='C or D'):
        await env.steady_checkpoint(value, source=source)
    assert not env.redirects and not env.final_sources


def test_high_program_has_distinct_index_tag_ancestors_and_full_history_proof():
    value = program()
    assert joint_proof(value) == 1104
    for phase in ('positive', 'negative'):
        ctx = value[phase][value['pc']]
        assert ctx['index_pc'] == value['nodes'][3] != value['pc']
        assert ctx['indices'][0] == 494 and ctx['tags'][0] == 112
    assert value['negative'][value['pc']]['indices'][1] == 270
    assert value['negative'][value['pc']]['tags'][1] == 84


def test_one_base_alias_preserves_base_but_separates_both_MicroTAGE_indices():
    value = program()
    alias = base_alias(value)
    assert alias['nodes'][2] == value['nodes'][2] + 32
    assert joint_proof(alias) == 1104
    for phase in ('positive', 'negative'):
        original, alternate = value[phase][value['pc']], alias[phase][value['pc']]
        assert physical_index(original['index_pc'], original['index_folds'][0]) == 200
        assert physical_index(alternate['index_pc'], alternate['index_folds'][0]) == 200
        assert original['indices'][0] == 494 and alternate['indices'][0] == 510
        assert all(a != b for a, b in zip(original['indices'], alternate['indices'], strict=True))


def test_alias_recipe_rejects_a_changed_original_base_identity():
    value = program()
    value['positive'][value['pc']]['index_folds'] = (45, 489)
    with pytest.raises(AssertionError, match='complete ABTB index'):
        base_alias(value)


def test_alias_recipe_rejects_an_unseparated_original_MicroTAGE_index():
    value = program()
    value['positive'][value['pc']]['indices'] = (510, 30)
    with pytest.raises(AssertionError, match='separate both'):
        base_alias(value)


def high_frames(*, allocation_read_index=494):
    references, frames = [BypassReference(0), BypassReference(1)], []
    boundary = dict(read_index=5, train_index=494, tag=112, allocate_position=6, update_position=6)
    steps = [(1, inputs()), (0, inputs(**boundary)),
        (0, inputs(**dict(boundary, train_index=allocation_read_index), allocate=1))]
    for direction, valid in ((1, 1), (1, 1), (1, 1), (1, 0), (0, 1), (0, 1), (0, 1), (0, 1)):
        steps.append((0, inputs(**boundary, update=1, update_taken=1, useful_valid=valid, useful_increase=direction)))
    for reset, values in steps:
        def frame(phase):
            return dict(phase=phase, tick=len(frames) + 1, value=dict(reset=reset,
                tables=[dict(inputs=deepcopy(values), state=reference.state(), outputs=reference.outputs(values))
                    for reference in references]))
        frames.append(frame('preedge'))
        for reference in references:
            reference.advance(values, reset=bool(reset))
        frames.append(frame('rising'))
    return frames


def test_reset_derived_roles_include_real_changes_and_both_saturation_holds():
    updates = collect_updates(high_frames())
    assert [row['after'] for row in updates] == [1, 2, 3, 3, 3, 2, 1, 0, 0]
    assert [row['before'] for row in updates] == [0, 1, 2, 3, 3, 3, 2, 1, 0]
    assert [row['role'] for row in updates] == ['allocation'] + ['increase'] * 3 + ['agreement-hold'] + ['decrease'] * 4
    assert all(row['index'] == 494 and row['tag'] == 112 and row['position'] == 6 for row in updates)


def test_useful_effect_belongs_to_registered_T1_not_the_current_T0_read_index():
    frames = high_frames(allocation_read_index=17)[:6]
    updates = collect_updates(frames)
    assert len(updates) == 1 and updates[0]['role'] == 'allocation'
    assert updates[0]['index'] == 494 and updates[0]['inputs']['train_index'] == 17
    assert frames[-1]['value']['tables'][0]['state']['train_index'] == 17
    assert frames[-1]['value']['tables'][0]['state']['useful'][494] == 1
    assert frames[-1]['value']['tables'][0]['state']['useful'][17] == 0


@pytest.mark.parametrize('kwargs', (dict(index=463), dict(tag=209), dict(position=7)))
def test_other_keys_or_positions_cannot_earn_the_original_useful_roles(kwargs):
    assert collect_updates(high_frames(), **kwargs) == []


def test_no_role_credit_for_last_write_without_its_observed_effect():
    frames = high_frames()
    complete = collect_updates(frames)
    assert collect_updates(frames[:-1]) == complete[:-1]


@pytest.mark.parametrize('fault', ('useful', 'neighbor', 'dirty', 'counter', 'enq', 'output', 'phase', 'gap', 'reset'))
def test_any_late_observation_fault_prevents_update_collection(fault):
    frames = high_frames()
    frame = frames[-1]
    row = frame['value']['tables'][0]
    if fault == 'useful':
        row['state']['useful'][494] ^= 1
    elif fault == 'neighbor':
        row['state']['useful'][511] ^= 1
    elif fault == 'dirty':
        row['state']['status'][0]['dirty'] ^= 1
    elif fault == 'counter':
        row['state']['cells'][0]['counter'] ^= 1
    elif fault == 'enq':
        row['state']['enq']['value'] ^= 1
    elif fault == 'output':
        row['outputs']['write']['counter'] ^= 1
    elif fault == 'phase':
        frame['phase'] = 'preedge'
    elif fault == 'gap':
        frame['tick'] += 2
    else:
        frames[0]['value']['reset'] = 0
    with pytest.raises(ScoreboardMismatch):
        collect_updates(frames)


@pytest.mark.parametrize('kwargs', (dict(index=-1), dict(index=512), dict(index=True),
    dict(tag=-1), dict(tag=256), dict(tag=True), dict(position=-1), dict(position=32), dict(position=True)))
def test_bad_scope_rejected_before_any_native_frame(kwargs):
    with pytest.raises(ValueError, match='high-row'):
        collect_updates(None, **kwargs)


def test_empty_frames_cannot_create_update_roles():
    with pytest.raises(ValueError, match='reset-derived'):
        collect_updates([])


@pytest.mark.parametrize('missing', HIGH_INDEX_CONTRACTS)
def test_each_high_index_contract_is_required(missing):
    coverage = coverage_model()
    for contract in HIGH_INDEX_CONTRACTS:
        if contract != missing:
            coverage.sample(dict(contract=contract))
    with pytest.raises(AssertionError):
        coverage.assert_coverage(100)
    coverage.sample(dict(contract=missing))
    coverage.assert_coverage(100)
