"""Instruction experience -> real SC teacher -> naturally consumed early NT."""
from dataclasses import asdict

from bpuverify.bpu.case.conditional_prefix import prepare_sources
from bpuverify.bpu.checker.sc_early_learning import Checks
from bpuverify.bpu.env.sc_early_learning import experiment
from bpuverify.bpu.model.sc_early_learning import direction_ready
from bpuverify.bpu.model.selection import Kind


async def run_program(env):
    c,p = env.checks,env.checks.program
    anchor = await prepare_sources(env)
    await env.conditional('base-near-positive',await env.query_owned(anchor))
    await env.controls(tage=True)
    await env.conditional('weak-provider-follows-positive-base',await env.query_owned(anchor),wrong=True)
    control = await env.query_owned(anchor)
    c.check(True,direction_ready(c.bank,c.save(control),p),'real weak provider gives TAGE final authority to taken Main')
    await env.teaching_outcome('discover-independent-X-condition',await env.query_pc(anchor,p.x),taken=True)
    await env.teaching_outcome('independent-X-negative-provider',await env.query_pc(anchor,p.x),taken=False,maximum=True)
    await env.controls(sc=True)
    originals = tuple([await env.query_pc(anchor,p.x) for _ in range(4)])
    for index,source in enumerate(originals):
        await env.teaching_outcome(f'SC-negative-experience-{index}',source,taken=False)
    c.sc_control = await env.query_owned(anchor)
    token = c.save(c.sc_control)
    value = c.bank.statistical_snapshot(token,resolved=True)
    fields = dict(c.bank.tage_snapshot(token,resolved=True).wanted)
    slot, = [i for i in range(4) if fields.get(f'{i}.has_provider')]
    c.check(True,direction_ready(c.bank,token,p),'independent SC experience did not train the target TAGE identity')
    c.check((1,0,-19),(value.prediction.used[slot],value.prediction.directions[slot],value.prediction.sums[slot]),
        'real SC evidence now opposes final taken TAGE')
    c.check((4,Kind.INDIRECT,p.a),(value.late.branch.position,value.late.branch.kind,value.late.branch.target),
        'calibrated SC releases the original indirect target')
    await env.controls(abtb=True)
    await env.observe_teacher(anchor)
    return c.finish()


async def run(agent,profile,coverage,evidence):
    checks = Checks(profile,coverage)
    try:
        async with experiment(agent,checks) as env:
            facts = await run_program(env)
            # Dataclass histories in one final witness, never per-cycle JSON.
            facts['SC_teacher'] = dict(facts['SC_teacher'],
                read_history=asdict(facts['SC_teacher']['read_history']),
                metadata=asdict(facts['SC_teacher']['metadata']))
            evidence.update(facts)
    except Exception as error:
        evidence['error'] = str(error)
        evidence['first_failure_context'] = checks.failure_evidence()
        raise
    finally:
        if checks.pipeline is not None and checks.pipeline.failure is not None:
            evidence['first_failure_context'] = checks.failure_evidence()
