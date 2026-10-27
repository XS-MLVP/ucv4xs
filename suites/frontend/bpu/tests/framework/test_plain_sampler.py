"""The fused plain-value sampler must be exactly the old two-pass result.

``compile_plain`` replaced ``_plain(compile_sampler(node)())`` at three hot
observation boundaries. That is only safe if it is *identical*: same nesting,
same types, same integers, and the same rejection of four-state (X/Z) values.
A faster sampler that silently masks an unknown bit would turn a real RTL
divergence into a passing test, so strictness is part of the contract.

Nothing here drives the DUT beyond construction; every case is a comparison
between the two samplers over the same live signals.
"""
from __future__ import annotations

from toffee import Bundle
from toffee.data import compile_sampler

import pytest

from bpuverify.bpu.bundle.values import _plain
from bpuverify.common.env.plain_sampler import compile_plain


def reference(node):
    """The exact expression ``compile_plain`` must reproduce."""

    return _plain(compile_sampler(node)())


class FakeLeaf:
    """Minimal XData-compatible leaf for equivalence and strictness cases."""

    def __init__(self, value: int, width: int, xmask: int = 0):
        self._value, self._width, self._xmask = value, width, xmask
        self.reads = 0

    def U(self):
        self.reads += 1
        return self._value

    def W(self):
        return self._width

    def XMask(self):
        return self._xmask

    def GetBytes(self):
        return self._value.to_bytes((self._width + 7) // 8, 'little')

    def GetBvalBytes(self):
        return self._xmask.to_bytes((self._width + 7) // 8, 'little')


def test_nesting_types_and_values_match_the_two_pass_reference():
    tree = Bundle(
        reset=FakeLeaf(1, 1),
        wide=FakeLeaf((1 << 40) | 0x5A5A, 48),
        banks=tuple(
            Bundle(valid=FakeLeaf(bank % 2, 1),
                   counters=tuple(FakeLeaf(bank * 8 + way, 8) for way in range(4)))
            for bank in range(2)),
        nested=Bundle(inner=Bundle(flag=FakeLeaf(0, 1))))
    expected, actual = reference(tree), compile_plain(tree)()
    assert actual == expected
    assert type(actual) is type(expected) is dict
    assert list(actual) == list(expected)
    for key in expected:
        assert type(actual[key]) is type(expected[key]), key
    assert type(actual['banks']) is tuple and len(actual['banks']) == 2
    assert type(actual['banks'][1]['counters']) is tuple
    assert all(type(value) is int for value in actual['banks'][1]['counters'])
    # The fused path must read each leaf once, not twice.
    assert tree['reset'].reads == 2  # one reference read + one fused read


def test_unknown_bits_still_raise_instead_of_masking():
    leaf = FakeLeaf(0b0101, 4, xmask=0b0100)
    with pytest.raises(ValueError, match='X/Z'):
        reference(Bundle(leaf=leaf))
    leaf.reads = 0
    with pytest.raises(ValueError, match='X/Z'):
        compile_plain(Bundle(leaf=leaf))()
    assert leaf.reads == 1, 'the fused path must not swallow the failing read'


def test_wide_leaves_fall_back_to_the_byte_path_unchanged():
    value = (1 << 100) + 7
    wide = FakeLeaf(value, 128)
    # Wider than 64 bits: the fused sampler must defer to the byte path rather
    # than truncate, so both samplers must report the same full value.
    expected, actual = reference(Bundle(wide=wide)), compile_plain(Bundle(wide=wide))()
    assert actual == expected == {'wide': value}
    assert actual['wide'].bit_length() == 101


def test_wide_leaf_unknown_bits_raise_too():
    wide = FakeLeaf(1, 128, xmask=1 << 90)
    with pytest.raises(ValueError, match='X/Z'):
        reference(Bundle(wide=wide))
    with pytest.raises(ValueError, match='X/Z'):
        compile_plain(Bundle(wide=wide))()


def test_zero_width_is_one_bit_like_signal_width():
    leaf = FakeLeaf(1, 0)
    assert compile_plain(Bundle(leaf=leaf))() == {'leaf': 1}
