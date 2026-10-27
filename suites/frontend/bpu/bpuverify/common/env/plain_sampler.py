"""Compile a Bundle tree into a sampler that yields plain Python values.

``compile_sampler`` builds a ``BundleValue`` tree whose leaves are ``LogicValue``
objects; callers then walk that tree again with ``_plain`` to get ints. For the
large read-only diagnostic bundles used by the BPU monitors that is three passes
per leaf (allocate ``LogicValue``, allocate ``BundleValue``, recurse with
``_plain``) where one would do.

This module fuses those passes. It returns exactly the structure
``_plain(compile_sampler(node)())`` would return — nested ``dict``/``tuple``
with ``int`` leaves — with the same strictness: a leaf whose ``XMask`` is
non-zero still raises ``ValueError('logic value contains X/Z bits')`` rather
than silently reporting a masked zero.

Leaves that the fast path does not cover (wider than 64 bits, or nodes that are
not ``XData``-style signals) fall back to ``compile_sampler`` plus ``_plain``, so
the shape and the four-state semantics stay identical.
"""
from __future__ import annotations

from toffee import Bundle
from toffee.data import compile_sampler

from bpuverify.bpu.bundle.values import _plain

UNKNOWN = 'logic value contains X/Z bits'


def _fast_leaf(node):
    """Return a closure reading one XData-style leaf, or None to use the fallback."""

    unsigned = getattr(node, 'U', None)
    width_of = getattr(node, 'W', None)
    if not callable(unsigned) or not callable(width_of):
        return None
    width = int(width_of())
    if width == 0:
        # Matches ``toffee.signals.signal_width``: a zero-width leaf is one bit.
        width = 1
    elif width < 0:
        raise ValueError('signal width must be positive')
    if width > 64:
        # Wide values need the aval/bval byte path in ``compile_signal_sampler``.
        return None
    mask = (1 << width) - 1
    xmask = getattr(node, 'XMask', None)
    if callable(xmask):
        def read():
            value = int(unsigned())
            if int(xmask()):
                raise ValueError(UNKNOWN)
            return value & mask
    else:
        def read():
            return int(unsigned()) & mask
    return read


def compile_plain(node):
    """Compile fresh plain-value sampling for a fixed data node tree."""

    if isinstance(node, Bundle):
        fields = tuple((name, compile_plain(value)) for name, value in node.items())
        return lambda: {name: sample() for name, sample in fields}
    if isinstance(node, tuple):
        samplers = tuple(compile_plain(value) for value in node)
        return lambda: tuple(sample() for sample in samplers)
    leaf = _fast_leaf(node)
    if leaf is not None:
        return leaf
    sampler = compile_sampler(node)
    return lambda: _plain(sampler())
