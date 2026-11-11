"""The oracle descriptor cannot disagree with the bytes actually driven."""
from dataclasses import replace

import pytest

from suites.frontend.ifu.testbenches.ifu.transactions import FetchRequest
from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi
from suites.frontend.ifu.testbenches.ifu.model.fetch import build_window
from suites.frontend.ifu.testbenches.ifu.model.isa import addi
from suites.frontend.ifu.testbenches.ifu.model.isa import beq

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-004')]


def window():
    return build_window([(addi(5, 0, 1), 0), (c_addi(9, 1), 1), (beq(0, 0, 8), 0)],
                        0x4000, split=3, taken1=1)


@pytest.mark.parametrize('field,value', [
    ('word', 0), ('raw_data', 0), ('out_data', 0), ('pc', 0x5000),
    ('slot', 1), ('is_rvc', 1), ('block', 1), ('start_offset', 1),
    ('end_offset', 0), ('cross', 1), ('pred_taken', 1), ('invalid_taken', 1),
    ('ftq_flag', 1), ('ftq_value', 2), ('ill', 1), ('branch_type', 1),
    ('ras_action', 1), ('jump_offset', 2), ('truncated', 1),
])
def test_input_descriptor_cannot_forge_a_different_oracle_from_the_same_bytes(field, value):
    original = window()
    FetchRequest(original)
    changed = (replace(original.instructions[0], **{field: value}),) + original.instructions[1:]
    with pytest.raises(ValueError, match='instruction descriptor'):
        FetchRequest(replace(original, instructions=changed))


@pytest.mark.parametrize('field,value', [('spec_count', 0), ('spec_count0', 0), ('half0', 1), ('half1', 1)])
def test_prefix_counts_and_half_markers_must_describe_the_driven_byte_stream(field, value):
    original = window()
    with pytest.raises(ValueError, match='derived window'):
        FetchRequest(replace(original, **{field: value}))


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'reorder', 'bytes'])
def test_no_missing_repeated_reordered_or_stale_instruction_description(change):
    original = window()
    if change == 'missing':
        changed = replace(original, instructions=original.instructions[:-1])
    elif change == 'duplicate':
        changed = replace(original, instructions=original.instructions + original.instructions[-1:])
    elif change == 'reorder':
        changed = replace(original, instructions=original.instructions[::-1])
    else:
        line = list(original.line0)
        line[0] ^= 0x100  # Keep instruction width/map unchanged.
        changed = replace(original, line0=line)
    with pytest.raises(ValueError, match='instruction descriptor'):
        FetchRequest(changed)


async def test_rejected_descriptor_never_drives_a_slot_and_the_legal_chain_still_completes(ifu_agent):
    original = window()
    before = ifu_agent.checked_cycles
    changed = (replace(original.instructions[0], out_data=0),) + original.instructions[1:]
    with pytest.raises(ValueError, match='instruction descriptor'):
        await ifu_agent.fetch(FetchRequest(replace(original, instructions=changed)))
    assert ifu_agent.checked_cycles == before and ifu_agent.req_fires == 0
    result = await ifu_agent.fetch(FetchRequest(original))
    assert result.beat is not None and ifu_agent.req_fires == ifu_agent.beat_fires == 1


def test_byte_walk_admits_varied_widths_splits_carry_line_wrap_and_partial_final_words():
    import random
    rng = random.Random(20261101)
    for _ in range(1200):
        carry = (rng.getrandbits(32) | 3) if rng.randrange(2) else 0
        used, program = int(bool(carry)), []
        target = rng.randrange(used + 1, 33)
        while used < target:
            rvc = rng.randrange(2)
            word = ((rng.getrandbits(16) & ~3) | rng.randrange(3)) if rvc else rng.getrandbits(32) | 3
            program.append((word, rvc))
            used += 2 - rvc
        # Only the final full-width word may straddle the end of32 slots.
        item = build_window(program, rng.randrange(0, 1 << 23) * 2,
            split=None if used > 32 else rng.randrange(1, used + 1),
            taken0=rng.randrange(2), taken1=rng.randrange(2), carry_word=carry, truncate=1)
        FetchRequest(item)


@pytest.mark.parametrize('field,value', [('slot', 32), ('start_offset', -1), ('end_offset', 32),
    ('raw_data', 1 << 32), ('out_data', 1 << 32), ('branch_type', 4), ('ras_action', 4),
    ('jump_offset', -1), ('jump_offset', 1 << 51)])
def test_every_derived_integer_has_an_explicit_encoding_domain(field, value):
    original = window()
    changed = (replace(original.instructions[0], **{field: value}),) + original.instructions[1:]
    with pytest.raises(ValueError):
        FetchRequest(replace(original, instructions=changed))


def test_hand_written_rvi_descriptor_and_raw_bytes_do_not_depend_on_the_stimulus_builder(monkeypatch):
    from suites.frontend.ifu.testbenches.ifu.model import fetch
    from suites.frontend.ifu.testbenches.ifu.model.fetch import Inst
    from suites.frontend.ifu.testbenches.ifu.model.fetch import Window
    raw = (0x13,) + (0,) * 31
    description = Inst(word=0x13, is_rvc=0, pc=0x4000, slot=0, block=0,
                       start_offset=0, end_offset=1, cross=0, raw_data=0x13, out_data=0x13)
    item = Window(instructions=(description,), size0=2, size1=0, split=2,
        block1_valid=0, half0=0, half1=0, spec_count=1, spec_count0=1, map=2,
        line0=raw, line1=(0,) * 32, line_offset0=0, line_offset1=2,
        ftq0=(0, 0), ftq1=(0, 1), start0_pc=0x4000, start1_pc=0x4004)
    monkeypatch.setattr(fetch, 'build_window', lambda *_a, **_kw: pytest.fail('input validation called the generator'))
    assert FetchRequest(item).window == item
    with pytest.raises(ValueError, match='instruction descriptor'):
        FetchRequest(replace(item, instructions=(replace(description, out_data=0),)))
