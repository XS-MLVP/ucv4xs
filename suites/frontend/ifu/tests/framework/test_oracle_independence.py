"""Oracle independence: frozen wrong algorithms must be rejected by the checks.

A single altered expected value (see ``test_checker_discrimination``) tests one
field.  A stronger, method-level check is to run a *complete but wrong* algorithm
and show that the same comparison rejects it while accepting the correct model.
Each wrong algorithm is the classic error for its module and is written
independently of the RTL:

- RVC expansion that forgets the compressed register remapping (rd/rs1 encode
  ``8+field``, not the raw 5-bit field);
- boundary detection that ignores the compressed map and starts an instruction
  at every slot;
- prediction legality that treats every taken prediction as legal;
- uncache ordering that delays *all* non-cacheable reads instead of only the
  non-idempotent ones.
"""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.case_loader import load_case_module
from suites.frontend.ifu.model import cenc
from suites.frontend.ifu.model import pred_checker as pred_model
from suites.frontend.ifu.model.boundary import BoundaryInput
from suites.frontend.ifu.model.boundary import SLOTS
from suites.frontend.ifu.model.boundary import predict as boundary_predict
from suites.frontend.ifu.model.boundary import starts as boundary_starts
from suites.frontend.ifu.model.rvc import Expansion
from suites.frontend.ifu.model.rvc import expand


def wrong_expand(word: int) -> Expansion:
    """A plausible but wrong decoder: no compressed register remapping."""

    correct = expand(word)
    if correct.ill or correct.hint or (word & 3) == 3:
        return correct
    rd = (correct.bits >> 7) & 0x1F
    if not 8 <= rd < 16:
        return correct  # no compressed remap in this encoding
    # Forgetting the remap means using the raw 3-bit field as the destination.
    patched = (correct.bits & ~(0x1F << 7)) | ((rd - 8) << 7)
    return Expansion(patched, False, form=correct.form + "-wrong-rd")


@pytest.mark.feature("IFU-ENV-002")
def test_rvc_model_and_dut_reject_a_missing_register_remap(rvc_expander):
    cases = load_case_module("tests/rvc_expander/test_rvc_expander.py", "cases_oracle_rvc")
    for word in (cenc.c_addi(10, 1), cenc.c_lw(8, 9, 0), cenc.c_slli(15, 3)):
        correct = expand(word)
        wrong = wrong_expand(word)
        assert correct.bits != wrong.bits, f"{word:#06x} no longer discriminates"
        cases.check(rvc_expander, word, correct)  # DUT follows the correct model
        with pytest.raises(AssertionError):
            cases.check(rvc_expander, word, wrong)  # and rejects the wrong algorithm


@pytest.mark.feature("IFU-ENV-002")
def test_boundary_model_and_dut_reject_one_instr_per_slot(instr_boundary):
    cases = load_case_module("tests/instr_boundary/test_instr_boundary.py", "cases_oracle_ib")
    wrong_starts = [True] * SLOTS  # every slot would be an instruction start
    for rvc in (0, 0b0101010101010101):
        scene = cases.window(size0=32, taken=(0, 31), rvc=rvc, total_end=31)
        correct = boundary_starts(scene)
        assert correct != wrong_starts
        expected = boundary_predict(scene)
        # Build a wrong snapshot by trusting the "every slot starts" algorithm
        # for validity only; the DUT must disagree.
        observed = cases.observe(instr_boundary)
        bad = dict(observed)
        bad["valid"] = tuple(int(value) for value in wrong_starts)
        with pytest.raises(AssertionError):
            cases.check(instr_boundary, scene, observed=bad)
        # Slot 1 starts an instruction exactly when slot 0 is compressed.
        assert expected.valid[1] == (1 if rvc & 1 else 0)


@pytest.mark.feature("IFU-ENV-002")
def test_pred_checker_model_and_dut_reject_accept_all_taken(pred_checker):
    cases = load_case_module("tests/pred_checker/test_pred_checker.py", "cases_oracle_pc")
    scene = cases.request(
        cases.base_instruction(0, 0x1000),
        cases.base_instruction(1, 0x1004, branch_type=pred_model.DIRECT, is_pred_taken=0),
        cases.base_instruction(2, 0x1008),
    )
    strict = pred_model.predict(scene)
    assert strict.redirect.valid == 1 and strict.fault_class == "jalFault"
    # A model that only enforces "taken implies control flow" but never checks
    # unpredicted jumps sees no fault: it would pass the wrong instruction.
    permissive = pred_model.Request(valid=1, instrs=[
        pred_model.Instr(**{**instruction.__dict__,
                            "is_pred_taken": 1,
                            "branch_type": pred_model.INDIRECT})
        if instruction.valid else instruction
        for instruction in scene.instrs
    ])
    assert pred_model.predict(permissive).redirect.valid == 0
    cases.check(pred_checker, scene)  # the DUT follows the strict contract
    stage1, stage2 = cases.observe(pred_checker)
    bad = dict(stage2)
    bad["valid"] = 0  # what the permissive model would conclude
    with pytest.raises(AssertionError):
        cases.check(pred_checker, scene, observed=(stage1, bad))


@pytest.mark.feature("IFU-ENV-002")
def test_uncache_model_and_dut_reject_wait_for_all_uncached(uncache_unit):
    cases = load_case_module("tests/uncache_unit/test_uncache_unit.py", "cases_oracle_uc")
    model = cases.start(uncache_unit)
    out = cases.cycle(uncache_unit, model, cases.Inputs(req_valid=1, req_pbmt=cases.NC))
    assert out["req_ready"] == 1
    assert model.phase == cases.SEND, "an NC read must not wait for older commits"
    # A model that waits for NC would still be in WAIT_COMMIT and would expect
    # no launch; check that the DUT's next-cycle snapshot contradicts it.
    wrong = dict(cases.expected_dict(model.outputs(cases.Inputs(to_ready=1))))
    wrong["to_valid"] = 0
    with pytest.raises(AssertionError):
        cases.cycle(uncache_unit, model, cases.Inputs(to_ready=1), expected_override=wrong)


@pytest.mark.feature("IFU-ENV-002")
def test_wrong_algorithms_differ_at_scale():
    """The frozen algorithms must really be wrong, not just on one hand-picked word."""

    rng = random.Random(0xA17E)
    differences = sum(
        1 for _ in range(500)
        if expand(word := rng.getrandbits(16)).bits != wrong_expand(word).bits
        or expand(word).ill != wrong_expand(word).ill
    )
    assert differences > 50, differences
