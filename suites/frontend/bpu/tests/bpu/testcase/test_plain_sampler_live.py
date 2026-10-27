"""The fused plain sampler must match the two-pass result on live BPU bundles.

``compile_plain`` is used at three hot observation boundaries, so the equality
has to hold on the real, fully bound signal trees — not only on synthetic fakes.
Each case compares the two samplers over the same live DUT in one process.
"""
from __future__ import annotations

import pytest
from toffee.data import compile_sampler

from bpuverify.bpu.bundle.pipeline import pipeline_binding
from bpuverify.bpu.bundle.values import _plain
from bpuverify.common.env.plain_sampler import compile_plain


@pytest.mark.parametrize('scope', ['main', 'with_sc', 'with_tage', 'with_ahead',
                                   'with_ittage', 'with_ras', 'all'])
def test_live_dut_leaves_match_on_a_real_observation_bundle(bpu_agent, scope):
    options = {}
    if scope == 'all':
        options = dict(with_sc=True, with_tage=True, with_ahead=True,
                       with_ittage=True, with_ras=True)
    elif scope != 'main':
        options = {scope: True}
    bits = pipeline_binding(bpu_agent, **options)
    expected = _plain(compile_sampler(bits.bits)())
    actual = compile_plain(bits.bits)()
    assert actual == expected, f'fused sampler diverged on {scope}'
    assert set(actual) == set(expected)
