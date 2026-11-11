"""Producer provenance cannot waive schema/checking or promote port pressure."""
from dataclasses import replace

import pytest

from suites.frontend.ifu.testbenches.ifu.checker import check_enqueue
from suites.frontend.ifu.testbenches.ifu.transactions import FetchRequest
from suites.frontend.ifu.testbenches.ifu.transactions import ProducerFetchRequest
from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi
from suites.frontend.ifu.testbenches.ifu.model.fetch import build_window
from suites.frontend.ifu.testbenches.ifu.model.isa import addi
from suites.frontend.ifu.testbenches.ifu.model.isa import beq

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-004')]


@pytest.mark.parametrize('base,count,taken', [(0x1000, 1, 0), (0x101e, 18, 1), (0x1ffe, 2, 1)])
def test_short_fallthrough_or_oversize_taken_is_not_a_producer_window(base, count, taken):
    window = build_window([(c_addi(9, 1), 1)] * count, base, taken0=taken)
    with pytest.raises(ValueError, match='size.*fall-through extent'):
        ProducerFetchRequest(window, physical_address=base)
    assert FetchRequest(window, physical_address=base).input_source == 'port-characterization'


@pytest.mark.parametrize('flag,value', [(0, 2), (1, 0)])
def test_dual_fetch_requires_successor_identity_not_only_well_sized_ports(flag, value):
    window = build_window([(c_addi(9, 1), 1)] * 2, 0x2000, split=1,
                          taken0=1, taken1=1, ftq0=(0, 0), ftq1=(flag, value))
    with pytest.raises(ValueError, match='successor FTQ'):
        ProducerFetchRequest(window)


def test_ftq_wrap_is_accepted_but_cross_page_dual_fetch_and_translated_offset_mismatch_are_not():
    window = build_window([(c_addi(9, 1), 1)] * 2, 0x2000, split=1,
                          taken0=1, taken1=1, ftq0=(0, 63), ftq1=(1, 0))
    assert ProducerFetchRequest(window).input_source == 'producer'
    cross = build_window([(c_addi(9, 1), 1)] * 2, 0x2ffe, split=1, taken0=1, taken1=1)
    with pytest.raises(ValueError, match='same virtual page'):
        ProducerFetchRequest(cross, physical_address=0xffe)
    with pytest.raises(ValueError, match='page offset'):
        ProducerFetchRequest(build_window([(c_addi(9, 1), 1)], 0x2002, taken0=1), physical_address=0)


@pytest.mark.parametrize('metadata', [{'pbmt0': 3}, {'backend_exc0': 1}, {'satp0': 1}])
def test_reserved_translation_and_backend_flags_cannot_gain_dual_producer_credit(metadata):
    window = build_window([(c_addi(9, 1), 1)] * 2, 0x2000, split=1,
                          taken0=1, taken1=1, **metadata)
    with pytest.raises(ValueError, match='reserved encoding|forbids dual fetch'):
        ProducerFetchRequest(window)


async def test_original_r14_port_window_is_not_promoted_by_a_correct_payload(ifu_agent):
    word = addi(5, 0, 1)
    old_first = build_window([(word, 0)], 0x103c, split=1, taken0=1,
                             ftq0=(0, 31), ftq1=(0, 32))
    with pytest.raises(ValueError, match='fall-through extent'):
        ProducerFetchRequest(old_first, physical_address=0x3c)
    first = ProducerFetchRequest(build_window([(word, 0)] + [(c_addi(9, 1), 1)] * 16,
        0x103c, split=1, taken0=1, ftq0=(0, 31), ftq1=(0, 32)), physical_address=0x3c)
    await ifu_agent.fetch(first)
    resume = ProducerFetchRequest(build_window([(c_addi(9, 1), 1), (beq(0, 0, 8), 0)],
        0x103e, split=1, carry_word=word, taken0=1, taken1=1, ftq0=(0, 32), ftq1=(0, 33)), physical_address=0x3e)
    result = await ifu_agent.fetch(resume)
    check_enqueue(result.beat, resume, 0)  # Current independent producer answer.
    # Freeze the old missing-prediction model for the same full carry word.
    instructions = (replace(resume.window.instructions[0], pred_taken=0),) + resume.window.instructions[1:]
    # Admission now rejects this inconsistent declaration, so inject the frozen
    # old oracle at the checker boundary, not through production constructors.
    with pytest.raises(ValueError, match='instruction descriptor'):
        FetchRequest(replace(resume.window, instructions=instructions), physical_address=0x3e)
    old_oracle = replace(resume)
    object.__setattr__(old_oracle, 'window', replace(resume.window, instructions=instructions))
    with pytest.raises(AssertionError, match='enq'):
        check_enqueue(result.beat, old_oracle, 0)


async def test_a_producer_typed_continuation_cannot_promote_its_port_only_low_half(ifu_agent):
    from suites.frontend.ifu.testbenches.uncache_unit.transactions import BusReply
    word = addi(5, 0, 1)
    first = FetchRequest(build_window([(c_addi(9, 1), 1)] * 31 + [(word, 0)], 0x8000, truncate=1))
    await ifu_agent.fetch(first)
    assert ifu_agent.carry.input_source == 'port-characterization'
    following = ProducerFetchRequest(build_window([(c_addi(9, 1), 1)], 0x8040,
        taken0=1, pbmt0=1, ftq0=(0, 1)), physical_address=0x9040)
    result = await ifu_agent.read_uncached(following, BusReply(word >> 16))
    assert result.beat.instrs[3] == word and result.peer_source == 'producer'
    assert result.input_source == 'port-characterization'


@pytest.mark.parametrize('word,branch,ras', [(addi(5, 0, 1), 0, 0), (beq(0, 0, 8), 1, 0), (0x00008067, 3, 1)])
def test_carry_uses_the_full_instruction_isa_class_and_its_finishing_taken_position(word, branch, ras):
    window = build_window([(c_addi(9, 1), 1)], 0x103e, split=1,
                          carry_word=word, taken0=1, taken1=1)
    carry = window.instructions[0]
    assert carry.pred_taken == 1 and carry.invalid_taken == 0
    assert carry.branch_type == branch and carry.ras_action == ras


async def test_live_producer_age_rejects_old_and_ambiguous_ids_but_accepts_a_successor_at_wrap(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.transactions import Frame
    first = ProducerFetchRequest(build_window([(c_addi(9, 1), 1)] * 32, 0x4000, ftq0=(0, 63)))
    accepted = await ifu_agent.cycle(Frame(request=first, ibuffer_ready=0))
    assert accepted.accepted_uid is not None
    before = ifu_agent.checked_cycles
    for ptr in ((0, 62), (1, 63)):
        older = ProducerFetchRequest(build_window([(c_addi(9, 1), 1)] * 32, 0x5000, ftq0=ptr))
        with pytest.raises(ValueError, match='younger.*half-ring'):
            await ifu_agent.cycle(Frame(request=older, ibuffer_ready=0))
    assert ifu_agent.checked_cycles == before
    following = ProducerFetchRequest(build_window([(c_addi(9, 1), 1)] * 32, 0x5000, ftq0=(1, 0)))
    next_accepted = await ifu_agent.cycle(Frame(request=following, ibuffer_ready=0))
    assert next_accepted.accepted_uid is not None and next_accepted.accepted_uid != accepted.accepted_uid
    await ifu_agent.idle(7)
    assert ifu_agent.beat_fires == 2 and not ifu_agent.outstanding
