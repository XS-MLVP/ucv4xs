"""Binding/decoder controls, not hardware functional evidence."""
import pytest
from toffee import Bundle

from suites.frontend.bpu.bpu.agent.main import BpuAgent
from suites.frontend.bpu.bpu.bundle.ports import validate_consumed_ports
from suites.frontend.bpu.bpu.monitor.decode import _decode_meta, _decode_prediction
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from tests.framework.fakes import Signal

pytestmark = pytest.mark.selftest


def prediction_sample(**extra):
    return Bundle(start_pc=Signal(0x4000, width=50), taken=Signal(1),
                  position=Signal(5, width=5), s2_override=Signal(),
                  s3_override=Signal(), **extra).sample()


def test_declared_observable_target_cannot_disappear_from_a_snapshot():
    with pytest.raises((AttributeError, KeyError, ValueError)):
        _decode_prediction(prediction_sample(), target_observable=True)


def test_dce_target_cannot_be_silently_reintroduced_in_a_snapshot():
    with pytest.raises(ValueError, match='fields'):
        _decode_prediction(prediction_sample(target=Signal(0x8000, width=50)))


def test_explicit_decoder_capability_preserves_a_real_target_without_fabrication():
    result = _decode_prediction(prediction_sample(target=Signal(0x8000, width=50)),
                                target_observable=True)
    assert result.target == 0x8000
    assert _decode_prediction(prediction_sample()).target is None


def test_declared_observable_perf_cannot_disappear_from_a_snapshot():
    sample = Bundle(resolve=Bundle(value=Signal()), redirect=Bundle(value=Signal())).sample()
    with pytest.raises((AttributeError, KeyError, ValueError)):
        _decode_meta(sample, perf_observable=True)


def test_valid_only_constant_is_not_part_of_the_driver_payload():
    agent = BpuAgent.__new__(BpuAgent)
    agent._reset_vector = 0x4000
    agent._prediction_ready = agent._meta_ready = 1
    agent._predictor_enabled = dict.fromkeys(('ubtb', 'abtb', 'mbtb', 'tage', 'sc', 'ittage', 'ras'), 1)
    assert 'meta_ready' not in agent._control_values()


async def test_unavailable_retirement_observation_rejects_before_redirect_is_driven():
    agent = BpuAgent.__new__(BpuAgent)
    agent.retirement_monitor = None
    driven = []

    async def redirect(transaction):
        driven.append(transaction)

    agent.redirect = redirect
    with pytest.raises(RuntimeError, match='not observable'):
        await agent.redirect_and_settle(BpuRedirect(0x4000, {}))
    assert not driven


def consumed_io(*, missing=None, extra=None, bad_width=None, bad_direction=None):
    def signal(name, width=1, direction='output'):
        return Signal(width=width + int(name == bad_width),
                      direction=('input' if direction == 'output' else 'output')
                      if name == bad_direction else direction)

    fields = {name: signal('prediction.' + name, width) for name, width in (
        ('startPc_addr', 50), ('taken', 1), ('endPosition', 5), ('s2Override', 1), ('s3Override', 1))}
    if missing is not None:
        fields.pop(missing)
    if extra is not None:
        fields[extra] = signal(extra)
    return Bundle(toFtq=Bundle(
        prediction=Bundle(valid=signal('prediction.valid'), ready=signal('prediction.ready', direction='input'),
                          bits=Bundle(**fields)),
        meta=Bundle(valid=signal('meta.valid'), bits=Bundle(
            resolveMeta=Bundle(value=signal('resolveMeta')),
            redirectMeta=Bundle(value=signal('redirectMeta')),
            commitMeta_ras=Bundle(value=signal('commitMeta_ras')))),
        s2FtqPtr=Bundle(flag=signal('s2.flag'), value=signal('s2.value', 6)),
        s3FtqPtr=Bundle(flag=signal('s3.flag'), value=signal('s3.value', 6))))


def test_reviewed_consumed_port_projection_is_legal():
    validate_consumed_ports(consumed_io())


@pytest.mark.parametrize('field', ('startPc_addr', 'taken', 'endPosition', 's2Override', 's3Override'))
def test_missing_consumed_field_is_not_reinterpreted_as_dce(field):
    with pytest.raises(ValueError, match='fields changed'):
        validate_consumed_ports(consumed_io(missing=field))


@pytest.mark.parametrize('field', ('target_addr', 'newFlag'))
def test_changed_consumed_projection_requires_a_real_migration(field):
    with pytest.raises(ValueError, match='fields changed'):
        validate_consumed_ports(consumed_io(extra=field))


@pytest.mark.parametrize('field', (
    'prediction.valid', 'prediction.ready', 'prediction.startPc_addr', 'prediction.taken',
    'prediction.endPosition', 'prediction.s2Override', 'prediction.s3Override', 'meta.valid'))
@pytest.mark.parametrize('fault', ('bad_width', 'bad_direction'))
def test_consumed_leaf_width_and_direction_cannot_drift(field, fault):
    with pytest.raises(ValueError, match='width|direction'):
        validate_consumed_ports(consumed_io(**{fault: field}))
