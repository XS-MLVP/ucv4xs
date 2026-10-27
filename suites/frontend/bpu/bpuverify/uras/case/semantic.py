"""Public operation programs, not a signal-state oracle in pytest cases."""
from bpuverify.uras.case.definitions import CALL_A, CALL_B, MAIN_TOP
from bpuverify.uras.transaction.types import UrasCycle


def held_call_repair_program(profile):
    """A corrected call survives withdrawal and supplies a genuinely new read.

    The final single return must expose MAIN_TOP, not the cancelled old call
    or a duplicate corrected call. No expected value comes from DUT feedback.
    """
    from bpuverify.uras.coverage.semantic import HELD_PROFILES
    from bpuverify.uras.model.semantic import Action, Operation, RasEvents
    from bpuverify.uras.transaction.types import UrasResult
    if profile not in HELD_PROFILES:
        raise ValueError('declared original operation and resume relation required')
    old = Operation(Action.CALL if profile.startswith('old-call.') else Action.RETURN,
                    CALL_A.start_pc, CALL_A.position)
    corrected = Operation(Action.CALL, CALL_B.start_pc, CALL_B.position)
    new_address = UrasResult(1, corrected.return_address)
    old_result = UrasResult(1, old.return_address) if old.action is Action.CALL else UrasResult(0, 0)
    steps = [
        ('old-source', RasEvents(main_top=MAIN_TOP, accept=old), old_result),
        ('held-correction', RasEvents(main_top=MAIN_TOP, correct_pending=corrected), new_address),
        ('withdrawn-hold', RasEvents(main_top=MAIN_TOP), new_address),
    ]
    before = profile.endswith('.resume-before')
    if before:
        steps.append(('resume-before-consumer', RasEvents(main_top=MAIN_TOP, advance=True), new_address))
    steps.extend((
        ('fresh-consumer', RasEvents(main_top=MAIN_TOP, accept=Operation(), advance=not before), new_address),
        ('return-once', RasEvents(main_top=MAIN_TOP, accept=Operation(Action.RETURN)), UrasResult(1, MAIN_TOP)),
    ))
    return tuple(steps)


async def check_held_call_repair(agent, profile, coverage):
    from bpuverify.uras.checker.semantic import HeldCallRepairChecks
    steps = held_call_repair_program(profile)
    checks = HeldCallRepairChecks(profile, steps, coverage)
    await agent.reset()
    for phase, events, _ in steps:
        actual = await agent.apply(events)
        # The monitor-decoded consumed event, not a self-comparison of the
        # driver's declaration, qualifies the held/resume boundary.
        checks.observe(phase, agent.reference.events, actual)
    agent.reference.raise_failure()
    return checks.finish()


def concurrent_program():
    return (
        UrasCycle(s1_fire=1, spec_action=2, spec_start_pc=CALL_A.start_pc,
                  spec_position=CALL_A.position, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, s2_fire=1, s3_fire=1, spec_action=2,
                  spec_start_pc=CALL_B.start_pc, spec_position=CALL_B.position, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, s2_fire=1, s3_fire=1, spec_action=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s2_valid=1, s2_action=2, s2_start_pc=CALL_A.start_pc,
                  s2_position=CALL_A.position, s2_fire=1, s3_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(),
    )


def coroutine_correction(stage):
    if stage == 1:
        return UrasCycle(s1_fire=1, spec_action=3, spec_start_pc=CALL_B.start_pc,
                         spec_position=CALL_B.position, full_ret_addr=MAIN_TOP)
    if stage == 2:
        return UrasCycle(s1_fire=1, spec_action=2, spec_start_pc=CALL_A.start_pc,
                         spec_position=CALL_A.position, s2_valid=1, s2_action=3,
                         s2_start_pc=CALL_B.start_pc, s2_position=CALL_B.position, full_ret_addr=MAIN_TOP)
    if stage == 3:
        return UrasCycle(s1_fire=1, spec_action=2, spec_start_pc=CALL_A.start_pc,
                         spec_position=CALL_A.position, s2_valid=1, s2_action=2,
                         s2_start_pc=CALL_A.start_pc, s2_position=CALL_A.position,
                         s3_valid=1, s3_action=3, s3_start_pc=CALL_B.start_pc,
                         s3_position=CALL_B.position, full_ret_addr=MAIN_TOP)
    raise ValueError('MicroRAS operation can originate from S1, S2 correction, or S3 correction')
