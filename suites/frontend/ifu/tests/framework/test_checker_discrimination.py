"""Negative controls: the real DUT observations must fail altered expectations.

A green suite only proves the checks ran.  These tests take the *same* live
observation each module check consumes, verify the untouched expectation still
passes (legal control), then inject a wrong expectation/observation and require
the check to raise.  That distinguishes "the checker compares this field" from
"the field is never compared", and shows a failure would be visible.

The injection layers are explicit:
- ``expected`` injection: the model's answer is altered;
- ``observation`` injection: the DUT snapshot is altered.

Neither is a hardware mutation; they validate the checking chain only.
"""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.case_loader import load_case_module
from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.isa import jal
from suites.frontend.ifu.model.rvc import Expansion
from suites.frontend.ifu.model.rvc import expand


@pytest.mark.feature("IFU-ENV-002")
def test_rvc_expander_rejects_a_wrong_expected_word(rvc_expander):
    cases = load_case_module("tests/rvc_expander/test_rvc_expander.py", "cases_rvc_disc")
    word = c_addi(10, 2)
    expected = expand(word)
    cases.check(rvc_expander, word, expected)  # legal control
    with pytest.raises(AssertionError):
        cases.check(rvc_expander, word, Expansion(expected.bits ^ 1, False))
    reserved = 0x0000  # c.addi4spn with zero immediate
    cases.check(rvc_expander, reserved, expand(reserved))
    with pytest.raises(AssertionError):
        cases.check(rvc_expander, reserved, Expansion(0, False))


@pytest.mark.feature("IFU-ENV-002")
def test_instr_boundary_rejects_an_altered_observation(instr_boundary):
    cases = load_case_module("tests/instr_boundary/test_instr_boundary.py", "cases_ib_disc")
    scene = cases.make_window(random.Random(7))  # legal lattice + coordinates
    cases.check(instr_boundary, scene)  # legal control
    observed = cases.observe(instr_boundary)
    for field, value in (
        ("valid", tuple(1 - bit for bit in observed["valid"])),
        ("instr_end_mask", (0,) * 32),
        ("is_cross_block", (1,) * 32),
    ):
        bad = dict(observed)
        bad[field] = value
        with pytest.raises(AssertionError):
            cases.check(instr_boundary, scene, observed=bad)


@pytest.mark.feature("IFU-ENV-002")
def test_pred_checker_rejects_a_wrong_target_and_fault_index(pred_checker):
    cases = load_case_module("tests/pred_checker/test_pred_checker.py", "cases_pc_disc")
    scene = cases.request(
        cases.base_instruction(0, 0x2000),
        cases.base_instruction(1, 0x2004, branch_type=2, is_pred_taken=0, jump_offset=0x80),
        cases.base_instruction(2, 0x2008),
    )
    cases.check(pred_checker, scene)  # legal control
    stage1, stage2 = cases.observe(pred_checker)
    bad = dict(stage2)
    bad["target"] = stage2["target"] ^ 1
    with pytest.raises(AssertionError):
        cases.check(pred_checker, scene, observed=(stage1, bad))
    bad = dict(stage2)
    bad["valid"] = 1 - stage2["valid"]
    with pytest.raises(AssertionError):
        cases.check(pred_checker, scene, observed=(stage1, bad))


@pytest.mark.feature("IFU-ENV-002")
def test_uncache_unit_rejects_a_wrong_completion_expectation(uncache_unit):
    cases = load_case_module("tests/uncache_unit/test_uncache_unit.py", "cases_uc_disc")
    model = cases.start(uncache_unit)
    observed = cases.cycle(uncache_unit, model, cases.Inputs(req_valid=1, req_pbmt=1))
    assert observed["req_ready"] == 1
    bad = dict(observed)
    bad["req_ready"] = 0
    with pytest.raises(AssertionError):
        cases.cycle(uncache_unit, model, cases.Inputs(req_valid=1, req_pbmt=1),
                    expected_override=bad)


@pytest.mark.feature("IFU-ENV-002")
def test_frontend_trigger_rejects_a_wrong_lane_action(frontend_trigger):
    cases = load_case_module("tests/frontend_trigger/test_frontend_trigger.py", "cases_tr_disc")
    model = cases.start(frontend_trigger)
    base = 0x3000
    target = base + 2 * 5
    cases.cycle(frontend_trigger, model,
                cases.configure(0, cases.Trigger(cases.EQ, action=cases.ACTION_DEBUG,
                                                 tdata2=target)), base)
    observed = cases.cycle(frontend_trigger, model, cases.normal(), base)
    assert observed[5] == cases.ACTION_DEBUG
    bad = list(observed)
    bad[5] = cases.ACTION_NONE
    with pytest.raises(AssertionError):
        cases.cycle(frontend_trigger, model, cases.normal(), base, expected_override=bad)


@pytest.mark.feature("IFU-ENV-002")
def test_perf_analysis_rejects_a_wrong_reason_bit(perf_analysis):
    cases = load_case_module("tests/perf_analysis/test_perf_analysis.py", "cases_pa_disc")
    model = cases.start(perf_analysis)
    pattern = cases.mask(cases.TAGE_MISS)
    cases.cycle(perf_analysis, model, cases.Inputs(backend_redirect=1,
                                                   control_flow_redirect=1,
                                                   tage_miss=1))
    observed = cases.cycle(perf_analysis, model, cases.EMPTY)
    assert observed == pattern
    with pytest.raises(AssertionError):
        cases.cycle(perf_analysis, model, cases.EMPTY,
                    expected_override=pattern ^ 1)


@pytest.mark.feature("IFU-ENV-002")
def test_ifu_rejects_an_altered_enqueue_and_redirect(ifu):
    cases = load_case_module("tests/ifu/test_ifu_fetch.py", "cases_top_disc")
    ifu.reset_once()
    window = cases.build_window([(jal(1, 0x40), 0), (c_addi(9, 1), 1)], 0x4000,
                                ftq0=(0, 3))
    beat, redirect = cases.fetch(ifu, window)
    assert beat is not None and redirect is not None
    cases.check_beat(beat, window)  # legal control
    cases.check_redirect(redirect, cases.aligned_lanes(window, 0)[1], window)
    bad_beat = dict(beat)
    bad_beat["enq"] = beat["enq"] ^ 1
    with pytest.raises(AssertionError):
        cases.check_beat(bad_beat, window)
    bad_beat = dict(beat)
    bad_beat["instrs"] = list(beat["instrs"])
    bad_beat["instrs"][0] ^= 1
    with pytest.raises(AssertionError):
        cases.check_beat(bad_beat, window)
    bad_redirect = dict(redirect)
    bad_redirect["taken"] = 1 - redirect["taken"]
    with pytest.raises(AssertionError):
        cases.check_redirect(bad_redirect, cases.aligned_lanes(window, 0)[1], window)
