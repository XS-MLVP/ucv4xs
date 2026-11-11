"""Arbiter1_InstrUncacheResp directed and randomized identity tests."""

from __future__ import annotations

import os
import random

import pytest

from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.checker import check_identity
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Inputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import arbiter_outputs


VECTORS = [
    Inputs(),
    Inputs(in_valid=1, in_data=0x0000_0000),
    Inputs(in_valid=1, in_data=0xDEAD_BEEF, in_corrupt=1),
    Inputs(in_valid=1, in_data=0x1357_9BDF, in_denied=1, in_corrupt=1),
    Inputs(in_valid=1, in_data=0xFFFF_FFFF, in_need_resend=1),
    Inputs(in_valid=0, in_data=0x8000_0001, in_corrupt=1, in_denied=1,
           in_need_resend=1),
]


@pytest.mark.feature("INC-ARB-001")
@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: f"v{v.in_valid}_{v.in_data:08x}")
async def test_identity_vectors_preserve_every_field(instr_uncache_resp_arbiter_agent, vector):
    observed = await instr_uncache_resp_arbiter_agent.evaluate(vector)
    expected = arbiter_outputs(vector)
    check_identity(vector, observed)
    assert observed == expected
    assert observed.out_valid == vector.in_valid
    assert observed.out_corrupt == vector.in_corrupt
    assert observed.out_denied == vector.in_denied
    assert observed.out_need_resend == vector.in_need_resend


@pytest.mark.feature("INC-ARB-001")
async def test_error_flags_are_independent_not_coupled(instr_uncache_resp_arbiter_agent):
    agent = instr_uncache_resp_arbiter_agent
    data = 0xA5A5_5A5A
    for valid in (0, 1):
        for corrupt in (0, 1):
            for denied in (0, 1):
                if denied and not corrupt:
                    continue  # illegal TileLink combination, tested as a guard
                for need_resend in (0, 1):
                    vector = Inputs(in_valid=valid, in_data=data, in_corrupt=corrupt,
                                    in_denied=denied, in_need_resend=need_resend)
                    observed = await agent.evaluate(vector)
                    assert observed.out_valid == valid
                    assert observed.out_data == data
                    assert observed.out_corrupt == corrupt
                    assert observed.out_denied == denied
                    assert observed.out_need_resend == need_resend


@pytest.mark.feature("INC-ARB-001")
async def test_randomized_identity_vectors(instr_uncache_resp_arbiter_agent):
    agent = instr_uncache_resp_arbiter_agent
    seed = int(os.environ.get("UCV_SEED", "1"))
    rng = random.Random(seed ^ 0xA4B1_0001)
    for _ in range(400):
        corrupt = rng.randrange(2)
        denied = rng.randrange(2) if corrupt else 0
        vector = Inputs(in_valid=rng.randrange(2), in_data=rng.getrandbits(32),
                        in_corrupt=corrupt, in_denied=denied,
                        in_need_resend=rng.randrange(2))
        observed = await agent.evaluate(vector)
        assert observed == arbiter_outputs(vector), f"seed {seed}"
