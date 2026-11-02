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

from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.isa import jal
from suites.frontend.ifu.model.rvc import Expansion
from suites.frontend.ifu.model.rvc import expand


@pytest.mark.feature("IFU-ENV-002")
async def test_rvc_expander_rejects_a_wrong_expected_word(rvc_expander):
    from suites.frontend.ifu.rvc_expander.checker import check_decoding
    from suites.frontend.ifu.rvc_expander.types import DecodeRequest
    word = c_addi(10, 2)
    expected = expand(word)
    request = DecodeRequest(word)
    observed = (await rvc_expander.decode(request)).result
    check_decoding(request, observed, expected)  # legal control, production checker
    with pytest.raises(AssertionError):
        check_decoding(request, observed, Expansion(expected.bits ^ 1, False))
    reserved = 0x0000  # c.addi4spn with zero immediate
    request = DecodeRequest(reserved)
    observed = (await rvc_expander.decode(request)).result
    check_decoding(request, observed, expand(reserved))
    with pytest.raises(AssertionError):
        check_decoding(request, observed, Expansion(0, False))


@pytest.mark.feature("IFU-ENV-002")
async def test_instr_boundary_rejects_an_altered_observation(instr_boundary):
    from dataclasses import replace
    from suites.frontend.ifu.instr_boundary.checker import check_boundary
    from suites.frontend.ifu.instr_boundary.stimulus import random_window
    scene = random_window(random.Random(7))
    observed = (await instr_boundary.analyze(scene)).result
    check_boundary(scene, observed)  # legal control uses the production checker
    for field, value in (
        ("valid", tuple(1 - bit for bit in observed.valid)),
        ("instr_end_mask", (0,) * 32),
        ("is_cross_block", (1,) * 32),
    ):
        bad = replace(observed, **{field: value})
        with pytest.raises(AssertionError):
            check_boundary(scene, bad)


@pytest.mark.feature("IFU-ENV-002")
async def test_pred_checker_rejects_a_wrong_target_and_fault_index(pred_checker):
    from dataclasses import replace
    from suites.frontend.ifu.model.pred_checker import DIRECT, Instr, Request, SLOTS, predict
    from suites.frontend.ifu.pred_checker.checker import check_prediction
    scene = Request(instrs=(Instr(valid=1, pc=0x2000),
        Instr(valid=1, pc=0x2004, branch_type=DIRECT, jump_offset=0x80),
        Instr(valid=1, pc=0x2008)) + (Instr(),) * (SLOTS - 3))
    observed = await pred_checker.cycle(scene)
    expected = predict(scene)
    check_prediction(observed, expected, observed.previous_redirect)  # legal control
    bad = replace(observed, redirect=replace(observed.redirect, target=observed.redirect.target ^ 2))
    with pytest.raises(AssertionError):
        check_prediction(bad, expected, observed.previous_redirect)
    bad = replace(observed, redirect=replace(observed.redirect, valid=0))
    with pytest.raises(AssertionError):
        check_prediction(bad, expected, observed.previous_redirect)
    bad = replace(observed, fixed_instr_valid=(1, 1, 1) + (0,) * (SLOTS - 4))
    with pytest.raises(AssertionError):
        check_prediction(bad, expected, observed.previous_redirect)


@pytest.mark.feature("IFU-ENV-002")
async def test_uncache_unit_rejects_a_wrong_completion_expectation(uncache_unit):
    from dataclasses import replace
    from suites.frontend.ifu.model.uncache import Inputs, Outputs
    from suites.frontend.ifu.uncache_unit.checker import RESET, check_outputs
    from suites.frontend.ifu.uncache_unit.types import BusReply
    observed = await uncache_unit.cycle(Inputs(req_valid=1, req_pbmt=1, to_ready=0))
    assert observed.before.req_ready == 1
    check_outputs(observed.before, RESET, phase='legal-control')
    with pytest.raises(AssertionError):
        check_outputs(observed.before, RESET, expected=replace(RESET, req_ready=0), phase='wrong-ready')
    uid = observed.events.accepted_uid
    await uncache_unit.cycle(Inputs(to_ready=1))
    completed = await uncache_unit.reply(uid, BusReply(1))
    expected = Outputs(1, 1, 1, 0, 0, 0, 0, 1, 1)
    check_outputs(completed.after, expected, phase='legal-completion')
    with pytest.raises(AssertionError):
        check_outputs(completed.after, expected, expected=replace(expected, resp_data=0), phase='wrong-data')


@pytest.mark.feature("IFU-ENV-002")
async def test_frontend_trigger_rejects_a_wrong_lane_action(frontend_trigger):
    from dataclasses import replace
    from suites.frontend.ifu.frontend_trigger.checker import check_actions
    from suites.frontend.ifu.model.trigger import ACTION_DEBUG, ACTION_NONE, Inputs, Trigger, Update, consecutive_pcs
    base = 0x3000
    target = base + 2 * 5
    inputs = Inputs(Update(1, 0, Trigger(action=ACTION_DEBUG, tdata2=target)),
                    enable=(1, 0, 0, 0), pcs=consecutive_pcs(base))
    await frontend_trigger.cycle(inputs)
    observed = (await frontend_trigger.cycle(replace(inputs, update=Update()))).before
    assert observed.actions[5] == ACTION_DEBUG
    check_actions(observed, observed.actions, phase='legal-control')
    bad = list(observed.actions)
    bad[5] = ACTION_NONE
    with pytest.raises(AssertionError):
        check_actions(observed, bad, phase='wrong-expectation')


@pytest.mark.feature("IFU-ENV-002")
async def test_perf_analysis_rejects_a_wrong_reason_bit(perf_analysis):
    from suites.frontend.ifu.model.perf import Inputs, TAGE_MISS
    from suites.frontend.ifu.perf_analysis.checker import check_reasons
    await perf_analysis.reset()
    pattern = 1 << TAGE_MISS
    await perf_analysis.cycle(Inputs(backend_redirect=1, control_flow_redirect=1, tage_miss=1))
    observed = await perf_analysis.cycle()
    assert observed == pattern
    check_reasons(observed, pattern)  # legal control uses the production checker
    with pytest.raises(AssertionError):
        check_reasons(observed, pattern ^ 1)


@pytest.mark.feature("IFU-ENV-002")
async def test_ifu_rejects_an_altered_enqueue_and_redirect(ifu_agent):
    from dataclasses import replace
    from suites.frontend.ifu.ifu.checker import check_enqueue, check_redirect
    from suites.frontend.ifu.ifu.types import FetchRequest
    from suites.frontend.ifu.model.fetch import build_window
    request = FetchRequest(build_window([(jal(1, 0x40), 0), (c_addi(9, 1), 1)], 0x4000,
                                        ftq0=(0, 3)))
    result = await ifu_agent.fetch(request)
    beat, redirect = result.beat, result.redirect
    assert beat is not None and redirect is not None
    check_enqueue(beat, request, 0)  # legal control, same production checker
    check_redirect(redirect, request, 0)
    with pytest.raises(AssertionError):
        check_enqueue(replace(beat, enq=beat.enq ^ 1), request, 0)
    wrong = (beat.instrs[0] ^ 1,) + beat.instrs[1:]
    with pytest.raises(AssertionError):
        check_enqueue(replace(beat, instrs=wrong), request, 0)
    with pytest.raises(AssertionError):
        check_redirect(replace(redirect, taken=1 - redirect.taken), request, 0)
