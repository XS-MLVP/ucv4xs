"""Same latest-age obligation with genuine integrated input and output owners."""
from copy import deepcopy

from suites.frontend.bpu.bpu.env.main_replacement import replacement_program, adjacent_feedback, branch
from suites.frontend.bpu.bpu.monitor.main_replacement import MainReplacementMonitor
from suites.frontend.bpu.mbtb.model.replacement_overlap import ReplacementProgram, PC
from suites.frontend.bpu.mbtb.checker.replacement_overlap import ReplacementChecks


def response_profile(row,checks):
    entries=row['entries']
    for entry in entries:
        if entry['valid']:
            checks.check((1,0,int(entry['counter']>=2)),(entry['kind'],entry['action'],entry['taken']),
                         'actual MainBTB branch attributes and qualified direction')
    return tuple((slot,e['position'],e['target'],e['counter']) for slot,e in enumerate(entries) if e['valid'])


async def check_main_replacement(agent,coverage,mode):
    program=ReplacementProgram(mode);checks=ReplacementChecks(program,coverage,'bpu')
    async with replacement_program(agent) as env,MainReplacementMonitor(agent) as monitor:
        for pc in program.pcs.values():
            first=None
            for record in sorted(program.profile(pc,prepared=True),key=lambda r:r.position):
                source=await env.capture_source(pc)
                outcomes=(() if first is None else (branch(first,taken=False),))+(branch(record,wrong=True),)
                await env.resolve(source,*outcomes)
                first=record
        touch=await env.capture_source(program.touch.pc)
        allocate=await env.capture_source(PC)
        frozen=deepcopy((touch.meta,allocate.meta))
        checks.check(True,touch.meta_tick!=allocate.meta_tick,'different actual published source lifetimes')
        rows=tuple(monitor.response_for(source)[1] for source in (touch,allocate))
        expected=tuple(tuple((r.way,r.position,r.target,r.counter) for r in program.profile(pc,prepared=True))
                       for pc in (program.touch.pc,PC))
        checks.sources(tuple(response_profile(row,checks) for row in rows),expected)
        first=next(r for r in program.prepared if r.pc==PC and r.position==1)
        allocation=(branch(first,taken=False),branch(program.new,wrong=True))
        sources=(allocate,) if program.lookup_only else (touch,allocate)
        outcomes=(allocation,) if program.lookup_only else (
            (branch(program.touch,taken=program.taken,wrong=program.taken),),allocation)
        await adjacent_feedback(env,sources,outcomes,checks)
        for pc in program.pcs.values():
            fresh=await env.capture_source(pc)
            _,row=monitor.response_for(fresh)
            checks.profile(pc,response_profile(row,checks))
            env.checker.retire_source(fresh.meta_tick)
        checks.immutable(frozen,(touch.meta,allocate.meta))
        for source in (touch,allocate):env.checker.retire_source(source.meta_tick)
        env.checker.finish()
