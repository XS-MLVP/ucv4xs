"""Top-level producer ABI controls; no extra hardware functional credit."""
from types import SimpleNamespace

import pytest

from suites.frontend.ftq.testbenches.ftq.transactions.types import BackendRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import IfuRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import Prediction
from suites.frontend.ftq.testbenches.ftq.transactions.types import Meta
from suites.frontend.ftq.testbenches.ftq.env.driver import encoding

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('kind', (BackendRedirect, IfuRedirect))
def test_redirect_guard_target_is_not_narrowed_to_the_pc_width(kind):
    for target in ((1 << 50), (1 << 51) - 1):
        value = kind(0, target=target)
        assert value.target == target
    with pytest.raises(ValueError, match='target'):
        kind(0, target=1 << 51)
    for pc in ((1 << 50), (1 << 51) - 2):
        assert kind(0, pc=pc).pc == pc
    with pytest.raises(ValueError, match='pc'):
        kind(0, pc=1 << 51)


@pytest.mark.parametrize('encoder,value', (
    (encoding.encode_prediction, Prediction(0)),
    (encoding.encode_meta, Meta(0)),
    (encoding.encode_backend_redirect, BackendRedirect(0)),
    (encoding.encode_ifu_redirect, IfuRedirect(0)),
))
def test_encoders_reject_duck_typed_objects_before_any_group_is_driven(encoder, value):
    from dataclasses import fields
    duck = SimpleNamespace(**{field.name: getattr(value, field.name) for field in fields(value)})
    with pytest.raises(ValueError, match='validated'):
        encoder(duck)


@pytest.mark.parametrize('stage', ('s2', 's3'))
def test_override_cannot_silently_replace_a_missing_pointer_with_zero(stage):
    with pytest.raises(ValueError, match='pointer'):
        Prediction(0, **{stage + '_override': 1})
    valid = Prediction(0, **{stage + '_override': 1, stage + '_ptr': 0})
    assert getattr(valid, stage + '_ptr') == 0


@pytest.mark.parametrize('kind', ('backend', 'ifu'))
async def test_guard_target_high_bit_reaches_the_real_public_redirect(ftq_agent, kind):
    from suites.frontend.ftq.testbenches.ftq.tests.support import allocate
    agent = ftq_agent
    await allocate(agent, 3, with_meta=False)
    await agent.write_meta(Meta(1))
    target = (1 << 50) | 0x80003000
    if kind == 'backend':
        value, _ = await agent.backend_redirect(BackendRedirect(1, target=target, offset=0))
    else:
        value, _ = await agent.ifu_redirect(IfuRedirect(1, target=target, offset=0, can_train=0))
    assert value is not None
    assert value.target == target >> 1


@pytest.mark.parametrize('kind', ('backend', 'ifu'))
async def test_redirect_pc_guard_bit_reaches_the_public_cfi_pc(ftq_agent, kind):
    from suites.frontend.ftq.testbenches.ftq.tests.support import allocate
    agent = ftq_agent
    await allocate(agent, 3, with_meta=False)
    await agent.write_meta(Meta(1))
    pc = (1 << 50) | 0x8000_2100
    offset = 3
    if kind == 'backend':
        value, _ = await agent.backend_redirect(BackendRedirect(1, pc=pc, offset=offset))
    else:
        value, _ = await agent.ifu_redirect(IfuRedirect(1, pc=pc, offset=offset, can_train=0))
    assert value is not None
    assert value.cfi_pc == ((pc >> 1) + offset) % (1 << 50)


class Signal:
    def __init__(self, width, output=False):
        self.width, self.output = width, output

    def W(self):
        return self.width

    def IsInIO(self):
        return not self.output

    def IsOutIO(self):
        return self.output


def schema():
    from suites.frontend.ftq.testbenches.ftq.env.bundle.abi import layout
    inputs, outputs = layout()
    signals = {name: Signal(width) for name, width in (inputs | {'clock': 1}).items()}
    signals.update((name, Signal(width, True)) for name, width in outputs.items())
    return SimpleNamespace(_inputs={name: signals[name] for name in inputs},
        input_names=lambda: tuple(inputs), output_names=lambda: frozenset(outputs),
        dut=SimpleNamespace(**signals))


def test_defaultconfig_metadata_geometry_has_fixed_answers_not_live_discovery():
    from suites.frontend.ftq.testbenches.ftq.env.bundle.abi import layout
    from suites.frontend.ftq.testbenches.ftq.env.bundle.abi import metadata_inputs
    inputs, outputs = layout()
    assert len(inputs) == 439 and len(outputs) == 470 and len(metadata_inputs()) == 329
    assert inputs['io_fromBackend_redirect_bits_target'] == 51
    assert inputs['io_fromBackend_redirect_bits_pc'] == 51
    assert inputs['io_fromIfu_wbRedirect_bits_pc'] == 51
    assert inputs['io_softPrefetch_2_bits_vaddr'] == 50
    assert outputs['io_toBpu_redirect_bits_cfiPc_addr'] == 50
    assert outputs['io_toICache_toPrefetch_bits_req_1_source_value'] == 1
    assert inputs['io_fromBpu_meta_bits_resolveMeta_mbtb_entries_1_4_position'] == 5
    assert 'io_fromBpu_meta_bits_resolveMeta_mbtb_entries_1_4_attribute_branchType' not in inputs
    assert outputs['io_toICache_toPrefetch_bits_twoPrefetchCase_value'] == 4
    assert outputs['io_toICache_toMainPipe_bits_req_0_bankSel_0'] == 8


@pytest.mark.parametrize('name', (
    'clock', 'reset', 'io_fromBackend_redirect_bits_target',
    'io_fromBpu_prediction_bits_startPc_addr',
    'io_fromBpu_meta_bits_redirectMeta_ras_topRetAddr_addr',
    'io_fromBpu_meta_bits_resolveMeta_mbtb_entries_1_3_attribute_branchType',
    'io_fromBpu_meta_bits_resolveMeta_mbtb_entries_1_4_position',
    'io_fromBpu_meta_bits_resolveMeta_sc_debug_scPathTakenVec_9',
    'io_toBpu_train_bits_startPcVec_dup_2_1_addr',
    'io_toICache_toPrefetch_bits_twoPrefetchCase_value',
    'io_toICache_toMainPipe_bits_req_1_bankSel_1',
))
@pytest.mark.parametrize('mutation', ('width', 'direction'))
def test_wrong_native_abi_is_rejected_even_for_formerly_unchecked_metadata(name, mutation):
    from suites.frontend.ftq.testbenches.ftq.env.bundle.abi import validate
    value = schema()
    signal = getattr(value.dut, name)
    if mutation == 'width':
        signal.width += 1
    else:
        signal.output = not signal.output
    with pytest.raises(ValueError, match='expected'):
        validate(value)


@pytest.mark.parametrize('mutation', ('missing-meta', 'extra-meta', 'missing-output', 'extra-output'))
def test_metadata_prefix_discovery_cannot_silently_accept_a_new_field(mutation):
    from suites.frontend.ftq.testbenches.ftq.env.bundle.abi import layout
    from suites.frontend.ftq.testbenches.ftq.env.bundle.abi import validate
    value = schema()
    inputs, outputs = layout()
    if mutation == 'missing-meta':
        del inputs['io_fromBpu_meta_bits_resolveMeta_phr_phrPtr_value']
    elif mutation == 'extra-meta':
        inputs['io_fromBpu_meta_bits_surprise'] = 1
    elif mutation == 'missing-output':
        del outputs['io_toBpu_train_bits_meta_commonHR_bw']
    else:
        outputs['surprise_output'] = 1
    value.input_names = lambda: tuple(inputs)
    value.output_names = lambda: frozenset(outputs)
    with pytest.raises(ValueError, match='schema mismatch'):
        validate(value)
