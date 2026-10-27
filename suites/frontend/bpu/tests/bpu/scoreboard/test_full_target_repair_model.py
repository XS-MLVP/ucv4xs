"""Full-target requirements, not the RTL's limited low-bit comparator."""
from dataclasses import replace

import pytest

from bpuverify.bpu.model.selection import Branch, Choice, Kind, final_repair, middle_repair
from tests.bpu.scoreboard.test_semantic_pipeline import ScriptedSources, boot


@pytest.mark.parametrize('source', ('micro', 'ahead'))
@pytest.mark.parametrize('pc,target,wrapped', (
    (0x407F_FFE0, 0x4080_0100, 0x4040_0100),
    (0x4080_0000, 0x407F_FF00, 0x40BF_FF00),
))
def test_high_region_difference_requires_full_late_repair(source, pc, target, wrapped):
    early = Choice(Branch(4, wrapped, Kind.DIRECT), None, source)
    correct = Choice(replace(early.branch, target=target), 0, 'main')
    assert wrapped != target
    assert wrapped % (1 << 22) == target % (1 << 22)
    assert not middle_repair(early, correct)
    assert final_repair(early, correct, correct, corrected_middle=False), (pc, early, correct)


@pytest.mark.parametrize('source', ('micro', 'ahead'))
def test_full_target_agreement_does_not_invent_a_repair(source):
    early = Choice(Branch(4, 0x4080_0100, Kind.DIRECT), None, source)
    correct = Choice(early.branch, 0, 'main')
    assert not middle_repair(early, correct)
    assert not final_repair(early, correct, correct, corrected_middle=False)


@pytest.mark.parametrize('source', ('micro', 'ahead'))
def test_middle_repair_already_consumed_full_target_needs_no_duplicate(source):
    early = Choice(Branch(4, 0x4040_0100, Kind.DIRECT), None, source)
    correct = Choice(replace(early.branch, target=0x4080_0100), 0, 'main')
    assert not final_repair(early, correct, correct, corrected_middle=True)


@pytest.mark.parametrize('source', ('micro', 'ahead'))
def test_high_target_repair_owns_original_token_and_cancels_younger_path(source):
    pc, target, wrapped = 0x407F_FFE0, 0x4080_0100, 0x4040_0100
    early = Choice(Branch(4, wrapped, Kind.DIRECT), None, source)
    correct = Choice(replace(early.branch, target=target), 0, 'main')
    model, event = boot(ScriptedSources({pc: {1: early, 2: correct, 3: correct}}), pc=pc)
    for _ in range(3):
        model.advance(event)
    original = model.stages[2]
    cycle = model.advance(event)
    assert cycle.final_repair, cycle
    assert cycle.presented == (original, correct)
    assert cycle.flushes[:2] == (True, True)
    assert model.stages[0].pc == target
    assert model.stages[1:] == (None, None)
    assert model.history.taken_edges == 1
