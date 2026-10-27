"""Synthetic input contracts only: none is a DUT/coverage reachability claim."""
from copy import deepcopy
from itertools import product
from pathlib import Path
from types import SimpleNamespace
import re
import pytest
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.bpu.model.sc.model import NAMES
from bpuverify.bpu.model.sc.model import ScReference
from bpuverify.bpu.model.sc.model import encoded_payload
from bpuverify.bpu.model.sc.model import width
from bpuverify.bpu.model.sc.training_path import train_need_write
from bpuverify.bpu.model.sc.history import history_indices
from bpuverify.sc.transaction.types import ScBatchTraining
from bpuverify.sc.transaction.types import ScBranchFeedback
from bpuverify.sc.model.threshold import ScThresholdModel
from bpuverify.bpu.model.sc.used import branch_effects, used_requests, threshold_update, UsedScReference, ThresholdReference
from bpuverify.bpu.monitor.sc.used import UsedScMonitor, pipeline_leaves
POSITIONS = (5, 4, 7, 6)
ROOT = Path(__file__).resolve().parents[3]

def transaction(*, bank=0, way=0, key=0, used=1, predicted=0, tage=1, valid=1, above=1, taken=1, hit=1, conditional=1, bias=0, common_valid=1):
    pc = 1073758208 + key * 128 + bank
    position = POSITIONS[way]
    owners = [dict(rawHit=hit, position=position), dict(rawHit=0, position=0), dict(rawHit=0, position=0), dict(rawHit=0, position=0)]
    common = dict(valid=common_valid, ghr=129, bw=11, imli=3)
    indices = history_indices(pc, common)
    base = pc >> 3 & 127
    sc = dict(scPred=[predicted, 0, 0, 0], tagePred=[tage, 0, 0, 0], tagePredValid=[valid, 0, 0, 0], useScPred=[used, 0, 0, 0], sumAboveThres=[above, 0, 0, 0], scBiasLowerBits=[bias, 0, 0, 0], debug=dict(predPathIdx=[base ^ 9], predGlobalIdx=[indices['globalTable_0']], predBWIdx=[indices['bwTable_0']], predImliIdx=base ^ 3, predBiasIdx=base))
    return dict(pc=pc, resolve_meta=dict(commonHR=common, sc=sc, mbtb_entries=[owners[:2], owners[2:]]), branches=[dict(position=position, target=1073807360, branch_type=1 if conditional else 3, taken=taken, mispredict=0, ras_action=0)])

@pytest.mark.parametrize('bank', [0, 1])
@pytest.mark.parametrize('way', range(4))
@pytest.mark.parametrize('flags', list(product((0, 1), repeat=8)))
def test_full_boolean_read_update_and_threshold_truth_table(bank, way, flags):
    used, predicted, tage, valid, above, taken, hit, conditional = flags
    tx = transaction(bank=bank, way=way, used=used, predicted=predicted, tage=tage, valid=valid, above=above, taken=taken, hit=hit, conditional=conditional)
    effect, = branch_effects(tx)
    expected_read = bool(hit and conditional and valid and (not used or predicted != taken or predicted != tage))
    expected_update = bool(expected_read and (predicted != taken or not above))
    assert effect['way'] == way and effect['read_eligible'] == expected_read
    assert effect['counter_update'] == expected_update
    assert effect['counter_delta'] == ((1 if taken else -1) if expected_update else 0)
    assert effect['threshold_delta'] == ((1 if predicted != taken else -1) if expected_update else 0)
    assert train_need_write(encoded_payload(tx)) == int(expected_read)
    model = ScThresholdModel()
    standalone = ScBatchTraining(tx['pc'], tx['resolve_meta']['sc'], (ScBranchFeedback(tx['branches'][0]['position'], taken, 0, mbtb_hit=hit, branch_type=tx['branches'][0]['branch_type']),))
    admitted = model.apply(standalone)
    actual = threshold_update((1130,) * 4, [effect])
    assert actual['after'] == admitted.after
    assert actual['increments'] == admitted.increments and actual['decrements'] == admitted.decrements

@pytest.mark.parametrize('bank', [0, 1])
@pytest.mark.parametrize('common_valid', [0, 1])
@pytest.mark.parametrize('encoded', range(64))
def test_every_signed_counter_encoding_allways_bias_selectors_tables(bank, common_valid, encoded):
    for way, bias, taken in product(range(4), range(4), (0, 1)):
        tx = transaction(bank=bank, way=way, bias=bias, common_valid=common_valid, predicted=1 - taken, taken=taken, tage=taken)
        ref = ScReference()
        debug = tx['resolve_meta']['sc']['debug']
        indices = dict(pathTable_0=debug['predPathIdx'][0], imliTable=debug['predImliIdx'], biasTable=debug['predBiasIdx'])
        if common_valid:
            indices.update(history_indices(tx['pc'], tx['resolve_meta']['commonHR']))
        for table, index in indices.items():
            ref.memories[f'{table}_bank{bank}'][index] = [encoded] * width(table)
        before = deepcopy(ref.memories)
        requests = used_requests(tx, ref.memories)
        signed = encoded - 64 if encoded & 32 else encoded
        changed = max(-32, min(31, signed + (1 if taken else -1))) & 63
        expected_names = {f'{table}_bank{bank}' for table in indices} if changed != encoded else set()
        assert set(requests) == expected_names
        for table, index in indices.items():
            name = f'{table}_bank{bank}'
            if name not in requests:
                continue
            lane = way * 4 + bias if table == 'biasTable' else way
            expected_data = [encoded] * width(table)
            expected_data[lane] = changed
            assert requests[name] == dict(set_index=index, masks=[int(i == lane) for i in range(width(table))], data=expected_data)
        assert ref.memories == before
        assert branch_effects(tx)[0]['read_eligible']

@pytest.mark.parametrize('bank', [0, 1])
@pytest.mark.parametrize('way', range(4))
@pytest.mark.parametrize('taken', [0, 1])
def test_used_correct_tage_agrees_skips_read_but_disagrees_reads_without_counter_update(bank, way, taken):
    no_read = transaction(bank=bank, way=way, predicted=taken, tage=taken, taken=taken)
    read_hold = transaction(bank=bank, way=way, predicted=taken, tage=1 - taken, taken=taken)
    assert not branch_effects(no_read)[0]['read_eligible']
    assert branch_effects(read_hold)[0]['read_eligible']
    assert not branch_effects(read_hold)[0]['counter_update']
    assert used_requests(no_read, ScReference().memories) == {}
    assert used_requests(read_hold, ScReference().memories) == {}
    assert threshold_update((1130,) * 4, branch_effects(read_hold))['after'] == (1130,) * 4

@pytest.mark.parametrize('bank', [0, 1])
@pytest.mark.parametrize('way', range(4))
def test_nonzero_common_valid_scused_four_depths_dirty_merge_clean_reactivate(bank, way):
    ref = UsedScReference()
    assert UsedScReference.reset is ScReference.reset and UsedScReference.step is ScReference.step
    ready = {name: 0 for name in NAMES}
    for key in range(4):
        tx = transaction(bank=bank, way=way, key=key, bias=0)
        ref.accept(key * 2, tx)
        _, actions = ref.step(ref.pending.pop(key * 2 + 2), ready)
        assert len(actions) == 5 and all((row['kind'] == 'miss' for row in actions))
    active = [name for name in NAMES if name.endswith(f'bank{bank}')]
    assert all(([row['dirty'] for row in ref.slots[name]] == [1] * 4 for name in active))
    for key in range(4):
        tx = transaction(bank=bank, way=way, key=key, bias=1)
        ref.accept(10 + key * 2, tx)
        _, actions = ref.step(ref.pending.pop(12 + key * 2), ready)
        assert len(actions) == 5 and all((row['kind'] == 'dirty_merge' for row in actions))
    for _ in range(4):
        drains, _ = ref.step({}, dict.fromkeys(NAMES, 1))
        assert len(drains) == 5
    assert all((not row['dirty'] for name in active for row in ref.slots[name]))
    for key in range(4):
        tx = transaction(bank=bank, way=way, key=key, bias=2)
        ref.accept(30 + key * 2, tx)
        _, actions = ref.step(ref.pending.pop(32 + key * 2), ready)
        assert len(actions) == 5 and all((row['kind'] == 'clean_reactivate' for row in actions))
    assert ref.pending == {}

@pytest.mark.parametrize('value', [640, 641, 1130, 5039, 5040])
@pytest.mark.parametrize('way', range(4))
@pytest.mark.parametrize('directions', [(-1, -1), (-1, 1), (1, -1), (1, 1)])
def test_threshold_sameway_net_votes_range_rejection_not_endpoint_clamp(value, way, directions):
    effects = [dict(way=way, counter_update=True, threshold_delta=delta) for delta in directions]
    before = [1130] * 4
    before[way] = value
    update = threshold_update(before, effects)
    candidate = value + sum(directions)
    expected = candidate if 640 <= candidate <= 5040 else value
    assert update['after'][way] == expected
    assert update['rejected_ways'] == (() if 640 <= candidate <= 5040 else (way,))
    assert all((update['after'][other] == 1130 for other in range(4) if other != way))

@pytest.mark.parametrize('taken', [0, 1])
def test_adjacent_pipeline_preserves_t1_and_t2_even_read_no_update(taken):
    ref = ThresholdReference()
    wrong = transaction(predicted=1 - taken, tage=taken, taken=taken)
    hold = transaction(predicted=taken, tage=1 - taken, taken=taken)
    skip = transaction(predicted=taken, tage=taken, taken=taken)
    first = ref.advance(wrong, t0_fire=1)
    second = ref.advance(hold, t0_fire=1)
    third = ref.advance(skip, t0_fire=1)
    fourth = ref.advance(skip, t0_fire=0)
    fifth = ref.advance(skip, t0_fire=0)
    assert first['t1_fire'] == first['t2_write_valid'] == 0
    assert second['t1_write_valid'] == 1 and second['after'][0] == 1131
    assert third['t1_write_valid'] == third['t2_write_valid'] == 1 and third['after'][0] == 1131
    assert fourth['t1_write_valid'] == 0 and fourth['t2_write_valid'] == 1
    assert fifth['t1_fire'] == fifth['t2_write_valid'] == 0
    assert ref.advance(None, t0_fire=0, reset=1)['after'] == (1130,) * 4

def test_missing_owner_unconditional_provider_invalid_and_invalid_slots_are_noops():
    for options in (dict(hit=0), dict(conditional=0), dict(valid=0)):
        tx = transaction(**options)
        assert used_requests(tx, ScReference().memories) == {}
        assert not branch_effects(tx)[0]['qualified']
    tx = transaction()
    tx['branches'] = [None, None]
    assert branch_effects(tx) == [] and used_requests(tx, ScReference().memories) == {}

def test_reverse_chisel_owner_priority_and_gapped_feedback():
    tx = transaction()
    owners = tx['resolve_meta']['mbtb_entries']
    owners[0][1] = deepcopy(owners[0][0])
    sc = tx['resolve_meta']['sc']
    sc['scPred'][1] = 1
    sc['tagePred'][1] = 1
    sc['useScPred'][1] = 1
    sc['sumAboveThres'][1] = 1
    tx['branches'] = [None, None, *tx['branches']]
    effect, = branch_effects(tx)
    assert effect['slot'] == 2 and effect['prediction_slot'] == 0 and effect['read_eligible']

def test_two_sameway_opposite_votes_cancel_path_but_update_distinct_bias_lanes():
    tx = transaction(way=1, bias=0, predicted=0, taken=1)
    owners = tx['resolve_meta']['mbtb_entries']
    owners[0][1] = dict(rawHit=1, position=1)
    sc = tx['resolve_meta']['sc']
    for field, value in dict(scPred=1, tagePred=0, tagePredValid=1, useScPred=1, sumAboveThres=1, scBiasLowerBits=1).items():
        sc[field][1] = value
    tx['branches'].extend([None, dict(position=1, target=1073811456, branch_type=1, taken=0, mispredict=0, ras_action=0)])
    effects = branch_effects(tx)
    assert len(effects) == 2 and all((row['way'] == 1 for row in effects))
    requests = used_requests(tx, ScReference().memories)
    assert set(requests) == {'biasTable_bank0'}
    assert requests['biasTable_bank0']['masks'] == [int(i in (4, 5)) for i in range(16)]
    assert requests['biasTable_bank0']['data'][4:6] == [1, 63]
    assert threshold_update((1130,) * 4, effects)['after'][1] == 1132

def test_reference_still_rejects_full_dirty_not_silently_claimed_closed():
    ref = UsedScReference()
    for key in range(4):
        tx = transaction(key=key)
        requests = used_requests(tx, ref.memories)
        ref.step(requests, dict.fromkeys(NAMES, 0))
    with pytest.raises(ValueError, match='full dirty overwrite'):
        ref.step(used_requests(transaction(key=4), ref.memories), dict.fromkeys(NAMES, 0))

@pytest.mark.parametrize('path,value', [(['pc'], -1), (['pc'], 1 << 49), (['branches'], []), (['branches', 0, 'position'], 16), (['branches', 0, 'taken'], 2), (['branches', 0, 'branch_type'], 4), (['resolve_meta', 'sc', 'useScPred', 0], 2), (['resolve_meta', 'sc', 'scBiasLowerBits', 0], 4), (['resolve_meta', 'sc', 'tagePredValid'], [1]), (['resolve_meta', 'mbtb_entries', 0, 0, 'rawHit'], 2)])
def test_invalid_feedback_is_atomic_for_full_state_reference(path, value):
    tx = transaction()
    parent = tx
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    ref = UsedScReference()
    before = deepcopy((ref.slots, ref.memories, ref.pending))
    with pytest.raises(ValueError):
        ref.accept(2, tx)
    assert (ref.slots, ref.memories, ref.pending) == before

@pytest.mark.parametrize('field', ['predGlobalIdx', 'predBWIdx'])
def test_wrong_captured_common_history_index_rejected(field):
    tx = transaction()
    tx['resolve_meta']['sc']['debug'][field][0] ^= 1
    with pytest.raises(ValueError, match='index mismatch'):
        used_requests(tx, ScReference().memories)

def test_monitor_all35_leaves_exist_with_correct_width_in_native_yaml():
    text = (ROOT / 'dut/bpu/BpuDut_offset.yaml').read_text()
    entries = {name: int(width) for name, width in re.findall('^  - name: (BpuDut_top\\.Bpu\\.sc\\.[^\\n]+)\\n(?:    [^\\n]+\\n)*?    rtl_width: (\\d+)$', text, re.M)}
    wanted = pipeline_leaves()
    assert len(wanted) == len(set(wanted)) == 35
    for leaf in wanted:
        assert entries['BpuDut_top.Bpu.sc.' + leaf] == (13 if leaf.startswith(('scThreshold_', 't1_writeThresVec_')) else 1)

def install_fake_base(monkeypatch):
    import bpuverify.bpu.monitor.sc.used as used_monitor
    from bpuverify.bpu.bundle.values import _plain

    def base(self, agent):
        self.paths = {'sc': 'Bpu.sc.'}
        self.binding = PortBinding(agent.dut.clock, Bundle(buffers=Bundle(dummy=SimpleNamespace(value=0)), t0=Bundle(dummy=SimpleNamespace(value=0)), training=Bundle(dummy=SimpleNamespace(value=0)), prediction=Bundle(dummy=SimpleNamespace(value=0))), 'fake.old.monitor')
        self.decoder = _plain
    monkeypatch.setattr(used_monitor.ScMonitor, '__init__', base)

    def forbidden(*args, **kwargs):
        raise AssertionError('VPI/internal access forbidden')
    agent = SimpleNamespace(dut=SimpleNamespace(clock=object(), GetInternalSignal=forbidden, GetInternalSignalList=forbidden))
    return (used_monitor, agent)

def test_monitor_preserves_static_bundle_and_inherited_lossless_subscriptions(monkeypatch):
    module, agent = install_fake_base(monkeypatch)
    calls = []

    def memory(dut, path):
        calls.append(path)
        return SimpleNamespace(value=0)
    monkeypatch.setattr(module, 'memory_signal', memory)
    monitor = module.UsedScMonitor(agent)
    assert set(calls) == {'Bpu.sc.' + leaf for leaf in pipeline_leaves()}
    assert monitor.binding.bits.used_pipeline.t1_fire.value == 0
    assert len(monitor.binding.bits.used_pipeline.thresholds) == 4
    assert module.UsedScMonitor.start is module.ScMonitor.start
    assert module.UsedScMonitor.aclose is module.ScMonitor.aclose
    assert monitor.binding.name == 'bpu.sc.used_full_state_and_threshold'

@pytest.mark.parametrize('missing', pipeline_leaves())
def test_monitor_missing_signal_hard_fails_without_internal_fallback(monkeypatch, missing):
    module, agent = install_fake_base(monkeypatch)
    monkeypatch.setattr(module, 'memory_signal', lambda dut, path: None if path == 'Bpu.sc.' + missing else SimpleNamespace(value=0))
    with pytest.raises(RuntimeError, match='Missing static SC-used observation signal'):
        module.UsedScMonitor(agent)
