"""Intent-only two-program eviction and SRAM return, with complete passive references."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import json
from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.model.phr.model import folds
from bpuverify.bpu.model.phr.model import fold
from bpuverify.bpu.model.sc.metadata import mbtb_counter_for_position
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.bpu.checker.bypass.aging_scope import NonzeroChecks
from bpuverify.bpu.env.bypass.aging_scope import NonzeroObservation
from bpuverify.bpu.case.bypass.public_readback import conditional_source_ways
from bpuverify.bpu.case.bypass.public_readback import public_readback_pair
from bpuverify.bpu.case.abtb.timeouts import bounded
from bpuverify.bpu.case.bypass.two_program_plan import recipe
from bpuverify.bpu.case.bypass.two_program_plan import full_tags
from bpuverify.bpu.case.bypass.aging_plan import direction_epochs


async def run_natural_aging(agent, output, *, bank=1, maximum_pairs=80):
    plan = recipe(bank)
    old, second = plan["old"], plan["second"]
    checker = NonzeroChecks(dict(physical_bank=bank, scope="two genuinely trained nonzero-PHR programs"))
    observation = NonzeroObservation(agent, checker)
    report = dict(plan=plan, maximum_preedge_frames=65536, maximum_pairs=maximum_pairs,
        formal_credit=False, native_credit=False,
        hardware_internal_state_written=False, metadata_fabricated=False,
        full_parent_training_given_real_public_metadata_checked=True,
        full_public_prediction_reference_claimed=False, full_FTQ_legality_proven=False)
    checkpoints = {}
    async def wait(operation, label, cycles=8192):
        return await bounded(agent, checker, operation, label, cycles)
    async def recover(target, checkpoint, label):
        checker.compare((target-1)&~7, checkpoint.prediction.start_pc&~7,
            field="real_checkpoint_same_CFI_halfblock")
        checker.compare(True, checkpoint.prediction.start_pc<=target-1,
            field="real_checkpoint_precedes_CFI")
        redirect = BpuRedirect(target, checkpoint.meta.redirect,
            cfi_pc=target-1, taken=0, branch_type=1)
        report.setdefault("recoveries", []).append(dict(payload=redirect.payload(), source=asdict(checkpoint)))
        boundary = await wait(agent.redirect(redirect), label+": actual recovery", 32)
        actual = await wait(agent.next_transaction(start_pc=target, after_tick=boundary, limit=256), label, 512)
        report.setdefault("public_captures", []).append(dict(phase=checker.phase, **asdict(actual)))
        return actual
    async def capture(program, label):
        pc = program["pc"]
        checker.compare(pc-1, checkpoints[pc].prediction.start_pc, field="genuine_source_checkpoint_PC")
        return await recover(pc, checkpoints[pc], label)
    async def train(actual, branches, label):
        transaction = BpuBatchTraining(actual.prediction.start_pc, actual.meta.resolve, branches)
        checker.plan_feedback(transaction)
        await wait(agent.train_batch_with_prediction_pause(transaction), label, 256)
        report.setdefault("feedback", []).append(dict(phase=checker.phase, transaction=asdict(transaction)))
    def conditional(program, taken, mispredict):
        return BpuBranchFeedback(program["position"], program["pc"], 1, taken=taken, mispredict=mispredict)
    def fallback(program, mispredict=0):
        return BpuBranchFeedback(program["fallback"], program["pc"], 3, taken=1, mispredict=mispredict)
    async def drain(label):
        await wait(agent.set_ready(prediction=False, meta=True), label+": stop younger predictions", 8)
        await wait(observation.drain(), label+": complete older fastTrain", 32)
        checker.compare((None,None), (checker.counter.pending1,checker.counter.pending2),
            field="accepted_ABTB_tasks_drained", label=label)
    async def prepare(program, label):
        checker.phase = label+"_prepare"
        await drain(label)
        await wait(agent.configure_predictors(abtb=False, settle=True), "isolate real MainBTB setup", 32)
        await wait(agent.set_ready(prediction=True, meta=True), "resume real MainBTB capture", 8)
        actual = await capture(program, "cold conditional source")
        await train(actual, (conditional(program,1,1),), "allocate genuine conditional")
        actual = await capture(program, "initial MainBTB conditional")
        checker.compare(2, mbtb_counter_for_position(actual,program["position"]), field="initial_conditional_counter")
        await train(actual, (conditional(program,0,1),), "normal feedback prepares negative conditional")
        actual = await capture(program, "weak negative conditional")
        checker.compare(1, mbtb_counter_for_position(actual,program["position"]), field="negative_conditional_counter")
        await train(actual, (conditional(program,0,0),None,fallback(program,1)), "allocate genuine fallback")
        actual = await capture(program, "two genuine MainBTB residents")
        checker.compare((0,3), (mbtb_counter_for_position(actual,program["position"]),
            mbtb_meta_for_position(actual,program["fallback"])[1]["attribute"]["branchType"]),
            field="both_actual_MainBTB_residents")
    async def steer(program, goal):
        await drain("direction preparation")
        await wait(agent.configure_predictors(abtb=False, settle=True), "isolate direction feedback", 32)
        await wait(agent.set_ready(prediction=True, meta=True), "resume direction metadata capture", 8)
        actual = await capture(program, "real MainBTB direction")
        for step in range(8):
            counter = mbtb_counter_for_position(actual,program["position"])
            if counter == goal:
                break
            taken = int(counter<goal)
            branch = conditional(program,taken,int((counter>=2)!=bool(taken)))
            await train(actual, (branch,) if taken else (branch,None,fallback(program)), "normal direction feedback")
            actual = await capture(program, "real direction transition")
            checker.compare(min(3,counter+1) if taken else max(0,counter-1),
                mbtb_counter_for_position(actual,program["position"]),
                field="real_MainBTB_direction_transition", step=step)
        checker.compare(goal, mbtb_counter_for_position(actual,program["position"]), field="real_MainBTB_direction_goal")
        await wait(agent.configure_predictors(abtb=True, settle=True), "enable genuine S3 fastTrain", 32)
        return await capture(program, "start natural nonzero-history loop")
    async def exercise(program, label):
        await prepare(program,label)
        begin = checker.bypass.last_event.tick
        for phase,goal in (("warm_fallback",0),("positive",3),("negative",0),("positive_again",3)):
            checker.phase = label+"_"+phase
            await steer(program,goal)
            for _ in range(2):
                await wait(observation.settle(64), "natural predictions without external redirects", 128)
                await wait(agent.pause_prediction_reads(), "read-free commit of real shadow writes", 32)

        if label == "old":
            baseline_age = checker.bypass.policy.age_pulses
            for pair in direction_epochs(maximum_pairs):
                epoch_start = checker.bypass.last_event.tick
                prior_failures = checker.bypass.policy.failed_allocations
                for suffix, goal in pair:
                    checker.phase = f"aging_{len(report.get('aging_epochs', []))}_{suffix}"
                    await steer(program, goal)
                    await wait(observation.settle(32), "natural direction transition and useful qualification", 64)
                    await wait(agent.pause_prediction_reads(), "commit genuine writes at this direction", 32)
                report.setdefault("aging_epochs", []).append(dict(
                    begin_tick=epoch_start, end_tick=checker.bypass.last_event.tick,
                    failures_before=prior_failures, failures_after=checker.bypass.policy.failed_allocations,
                    low_tick=checker.bypass.policy.low_tick,
                    reference_aging_pulses=checker.bypass.policy.age_pulses))
                if checker.bypass.policy.age_pulses > baseline_age:
                    break
            checker.compare(True, checker.bypass.policy.age_pulses > baseline_age,
                field="natural_failed_allocation_traffic_reaches_real_aging_threshold",
                maximum_pairs=maximum_pairs, failures=checker.bypass.policy.failed_allocations,
                low_tick=checker.bypass.policy.low_tick)

        await drain(label+" final drain")
        report.setdefault("program_windows",[]).append(dict(program=label,begin_tick=begin,
            end_tick=checker.bypass.last_event.tick,windows_per_phase=2,cycles_per_window=64))
    try:
        await observation.__aenter__()
        pcs = sorted((old["pc"],second["pc"]))
        leads = {pc:(pc-1)&~15 for pc in pcs}
        await wait(agent.reset(leads[pcs[0]]), "genuine reset before aligned cold checkpoints")
        cold = {}
        for pc in pcs:
            cold[pc] = await wait(agent.next_transaction(start_pc=leads[pc],limit=512),
                "capture actual aligned cold source", 2048)
        report["cold_leads"] = [asdict(cold[pc]) for pc in pcs]
        await wait(agent.configure_predictors(ubtb=False,abtb=False,mbtb=True,tage=False,
            sc=False,ittage=False,ras=False,settle=True), "preserve cold MicroBTB miss; isolate MainBTB", 32)
        for pc in pcs:
            checkpoints[pc] = await recover(pc-1,cold[pc],"actual nonaligned checkpoint")
        report["source_checkpoints"] = [asdict(checkpoints[pc]) for pc in pcs]
        await exercise(old,"old")
        old_index = old["expected_conditional_upper_index"]
        expected = dict(data_valid=1,tag=full_tags(old["pc"],folds(old["conditional_history"]))[1],
            position=old["position"],counter=7)
        upper=checker.bypass.references[1]
        _,_,selected=upper.select(old_index)
        checker.compare(True,selected is not None,field="old_shadow_exists_before_real_eviction")
        from bpuverify.bpu.model.bypass.model import payload
        checker.compare(expected,payload(upper.cells[selected]),
            field="old_full_payload_is_correct_in_selected_shadow_before_writeback")
        report["old_shadow_before_second_program"]=deepcopy(upper.state())
        start_second = checker.bypass.last_event.tick
        await exercise(second,"second")
        new_writes = [row for row in checker.bypass.writes if row["tick"]>start_second and row["table"]==1
            and row["index"]==second["expected_conditional_upper_index"]]
        checker.compare(True,len(new_writes)>=8,field="second_program_has_at_least_eight_real_upper_updates")
        before_return = deepcopy(checker.bypass.references[1].state())
        checker.compare(False,any(cell["valid"] and cell["index"]==old_index for cell in before_return["cells"]),
            field="old_key_absent_from_all_eight_shadow_slots_before_return")
        checker.compare(expected,checker.bypass.srams[1].memory[old_index],field="old_SRAM_payload_survives_second_program")
        report["eviction"] = dict(tick=checker.bypass.last_event.tick,second_actual_upper_updates=len(new_writes),
            upper_shadow_before_return=before_return,independent_expected_old_SRAM=expected)
        checker.phase = "old_return_from_SRAM"
        read_start = checker.bypass.last_event.tick
        await wait(agent.set_ready(prediction=True,meta=True),"resume genuine old program",8)
        actual = await capture(old,"old program after actual complete shadow eviction")
        await wait(observation.settle(32),"natural old history reconvergence and genuine ABTB recovery",64)
        await wait(agent.pause_prediction_reads(),"commit genuine recovered ABTB entry",32)
        checked_public = None
        for attempt in range(32):
            actual = await wait(agent.next_transaction(start_pc=old["pc"],after_tick=actual.prediction_tick,limit=256),
                "next genuine old-program pipeline transaction",512)
            report.setdefault("public_captures",[]).append(dict(phase=checker.phase,**asdict(actual)))
            source = next(row["abtb"]["meta1"] for row in checker.records if row["tick"]==actual.prediction_tick)
            history = actual.meta.redirect["phr"]["phrLowBits"]
            # Qualify only reset-derived index SOURCE token, ABTB input and redirect guard;
            # NEVER filter by actual UTAGE hit, counter, tableId or prediction.
            physical = next(row["value"]["hash_inputs"] for row in checker.bypass.records
                if row["phase"]=="preedge" and row["tick"]==actual.prediction_tick-1)
            selected = conditional_source_ways(source,old["position"])
            token=checker.bypass.index_tokens[actual.prediction_tick]
            old_folds=(fold(old["conditional_history"],6,6),fold(old["conditional_history"],12,9))
            eligible=(token is not None and token["pc"]==old["pc"] and token["folds"]==old_folds
                and bool(selected) and not physical["redirect_valid"])
            report.setdefault("return_qualification",[]).append(dict(prediction_tick=actual.prediction_tick,
                phr_low=history,source_ABTB=source,redirect_guard=physical["redirect_valid"],expected_index_token=token,eligible=eligible))
            if eligible:
                wanted,observed = public_readback_pair(asdict(actual),source,expected,
                    pc=old["pc"],index=old_index,position=old["position"])
                checker.compare(wanted,observed,field="all_public_UTAGE_ways_and_prediction_from_replayed_SRAM",
                    prediction_tick=actual.prediction_tick)
                checked_public = dict(transaction=asdict(actual),source_ABTB_meta=source)
                break
        checker.compare(True,checked_public is not None,field="input_qualified_public_SRAM_return_checked")
        await wait(observation.settle(24),"observe accepted captured-counter update and next-cycle state",48)
        await drain("scenario finalization")
        readbacks = [row for row in checker.bypass.SRAM_reads
            if row["tick"]>read_start and row["table"]==1 and row["index"]==old_index]
        captures = [row for row in checker.bypass.writes if row["tick"]>read_start
            and row["table"]==1 and row["index"]==old_index and row["source"]=="captured_counter"]
        checker.compare(True,bool(readbacks),field="actual_old_SRAM_read_without_shadow_hit")
        checker.compare(True,bool(captures),field="actual_upper_captured_counter_at_missing_physical_bank",bank=bank)
        checker.compare(0,len(checker.feedback_plans),field="all_complete_feedback_observed")
        checker.compare(True,checker.bypass.policy.age_pulses>=1,field="actual_numeric_counter_wrap_and_age_seen")
        report.update(passed=True,actual_public_readback=checked_public,actual_no_shadow_SRAM_readbacks=readbacks,
            actual_target_captured_updates=captures,ABTB_summary=checker.summary(),bypass_summary=checker.bypass.finish())
    except BaseException as error:
        report["failure"] = repr(error)
        raise
    finally:
        await observation.aclose()
        report.update(records=checker.records,preedge_records=checker.control_records,
            coherent_transactions=checker.coherent_transactions,feedback_accepts=checker.feedback_accepts,
            accepts=checker.accepts,confirmed_transitions=checker.confirmed,gates=checker.gates,
            bypass_records=checker.bypass.records,bypass_writes=checker.bypass.writes,
            bank_writes=checker.bypass.bank_writes,SRAM_reads=checker.bypass.SRAM_reads,
            forced_conflicts=checker.bypass.forced_conflicts,
            reset_cache_divergences=checker.bypass.reset_cache_divergences,failed_frame=checker.bypass.failed_frame)
        dump_trace((output/f"integrated-natural-aging-bank{bank}.json"), report)
    return report
