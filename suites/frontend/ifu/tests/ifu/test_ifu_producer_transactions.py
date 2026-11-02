"""Audited upstream field relationships and explicitly executed recovery histories.

This verifies the IFU boundary, not an integrated BPU/FTQ/ICache implementation or
all possible predictor/translation histories. The old port tests remain intact.
"""
import pytest

from suites.frontend.ifu.ifu.types import ProducerFetchRequest
from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.fetch import build_window
from suites.frontend.ifu.model.isa import addi, beq


@pytest.mark.feature('IFU-TOP-005')
@pytest.mark.feature('IFU-TOP-011')
@pytest.mark.parametrize('rs1', [0, 6], ids=['normal-upper-half', 'upper-half-low11'])
async def test_real_ftq_extent_and_taken_carry_completion_keep_block_zero_identity(ifu_agent, rs1):
    word = addi(5, rs1, 1)
    # The first taken block ends on the low half; the non-taken successor must
    # extend17 halfwords from0x103e to its real fall-through boundary0x1060.
    first = ProducerFetchRequest(build_window([(word, 0)] + [(c_addi(9, 1), 1)] * 16,
        0x103c, split=1, taken0=1, ftq0=(0, 31), ftq1=(0, 32)), physical_address=0x3c)
    initial = await ifu_agent.fetch(first)
    assert initial.beat.valid == initial.beat.enq == 0 and initial.redirect.target == 0x103e
    # A one-halfword first block at0x103e must be predicted taken, not called
    # fall-through. The completed ADDI is not a CFI, so this legal false
    # prediction redirects to0x1040 and still belongs to the finishing block0.
    resume = ProducerFetchRequest(build_window([(c_addi(9, 1), 1), (beq(0, 0, 8), 0)],
        0x103e, carry_word=word, split=1, taken0=1, taken1=1,
        ftq0=(0, 32), ftq1=(0, 33)), physical_address=0x3e)
    completed = await ifu_agent.fetch(resume)
    assert completed.beat.instrs[0] == word and completed.beat.ftq[0] == (0, 32)
    assert completed.beat.enq == 1 and completed.redirect.ftq == (0, 32)
    assert completed.redirect.target == 0x1040 and completed.redirect.taken == 0
    assert completed.input_source == 'producer' and ifu_agent.carry is None


@pytest.mark.feature('IFU-TOP-002')
@pytest.mark.parametrize('base,count', [(0x70000, 32), (0x70020, 32), (0x70fe0, 16), (0x70ffe, 1)])
async def test_full_fallthrough_extent_accepts_alignment_and_page_end_boundaries(ifu_agent, base, count):
    item = ProducerFetchRequest(build_window([(c_addi(9, 1), 1)] * count, base),
                                physical_address=0x900000 | (base & 0xfff))
    result = await ifu_agent.fetch(item)
    assert result.beat.valid == result.beat.enq == (1 << count) - 1
    assert result.redirect is None and result.input_source == 'producer'
