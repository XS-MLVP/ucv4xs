"""StoreDelay input/checker controls, not real RTL mutation coverage."""
from dataclasses import FrozenInstanceError, replace
import random

import pytest

from suites.memblock.lsu.store_delay.env import make_bits, no_redirect, redirect
from suites.memblock.lsu.store_delay.ports import DelayPorts
from suites.memblock.lsu.store_delay.transactions import DelayCommand, PAYLOAD_FIELDS

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('change', ['missing', 'unknown', 'overflow', 'rob_range'])
def test_bad_payload_is_rejected_before_any_native_write(change):
    values = make_bits()
    if change == 'missing':
        values.pop('fullva')
    elif change == 'unknown':
        values['fulva'] = 1
    elif change == 'overflow':
        values['fullva'] = 1 << 64
    else:
        values['uop_robIdx_value'] = 160
    with pytest.raises(ValueError, match='missing=|does not fit|ROB value'):
        DelayCommand.build(1, values, no_redirect())


@pytest.mark.parametrize('change', ['missing', 'unknown', 'encoding', 'rob_range'])
def test_bad_redirect_is_not_defaulted_or_truncated(change):
    values = redirect()
    if change == 'missing':
        values.pop('former')
    elif change == 'unknown':
        values['formr'] = 1
    elif change == 'encoding':
        values['level'] = 2
    else:
        values['value'] = 160
    with pytest.raises(ValueError, match='missing=|does not fit|ROB value'):
        DelayCommand.build(1, make_bits(), values)


def test_frozen_command_does_not_retain_the_callers_dictionary():
    bits = make_bits(None, fullva=0x1234)
    command = DelayCommand.build(1, bits, no_redirect())
    bits['fullva'] = 0
    assert command.bits[tuple(PAYLOAD_FIELDS).index('fullva')] == 0x1234
    with pytest.raises(FrozenInstanceError):
        command.valid = 0


def test_random_payload_helper_respects_non_power_of_two_rob():
    rng = random.Random(20261101)
    values = [make_bits(rng)['uop_robIdx_value'] for _ in range(1000)]
    assert all(0 <= value < 160 for value in values)
    assert 0 in values and 159 in values
    with pytest.raises(ValueError, match='unknown StoreDelay payload'):
        make_bits(None, full_va=3)


def test_missing_required_port_cannot_turn_into_an_all_zero_pass():
    with pytest.raises(AttributeError):
        DelayPorts(object())


@pytest.mark.parametrize('fault', ['missing_final', 'corrupt_final', 'repeat_final'])
async def test_final_beat_and_no_repeat_are_checked_on_context_exit(store_delay_factory, monkeypatch, fault):
    env = store_delay_factory()
    captured = []
    expected = 'finish no duplicate.*out.valid' if fault == 'repeat_final' else 'finish pending beat.*out.'
    with pytest.raises(AssertionError, match=expected):
        async with env.running():
            await env.reset()
            await env.cycle(1, make_bits(None, fullva=0x1234), no_redirect(), 'last input')
            original = env._monitor.capture

            def injected(event):
                actual = original(event)
                captured.append(actual.valid)
                if fault == 'missing_final':
                    return replace(actual, valid=0)
                if fault == 'repeat_final':
                    return replace(actual, valid=1)
                data = list(actual.bits)
                data[tuple(PAYLOAD_FIELDS).index('fullva')] ^= 1
                return replace(actual, bits=tuple(data))

            monkeypatch.setattr(env._monitor, 'capture', injected)
    assert captured[0] == 1, 'fault must reach a real final valid output'
    if fault == 'repeat_final':
        assert captured == [1, 0]
