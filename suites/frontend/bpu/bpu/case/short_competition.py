"""Protect, release, replace and consume both owners through real programs."""
from suites.frontend.bpu.bpu.bundle.short_competition import competition_binding
from suites.frontend.bpu.bpu.env.short_context_ownership import short_context_env
from suites.frontend.bpu.bpu.env.short_competition import Environment
from suites.frontend.bpu.bpu.checker.short_competition import Checks
from suites.frontend.bpu.bpu.model.short_competition import RELEASE_PATHS


async def check_competition(agent,p,coverage):
    async with short_context_env(agent,p,coverage,checks_factory=Checks,env_factory=Environment,
            binding_factory=lambda agent,**options:competition_binding(agent,p,**options)) as env:
        c=env.checks
        await env.select(p.old)
        await env.stabilize_old()
        c.mark('old-qualified-protection',state=c.states()[p.old])
        c.mark('shared-real-predecessors',pcs=p.original(p.old).pcs)
        c.mark('complete-distinct-owners',tags=[path.tags[0] for path in p.paths])
        before=c.states()[p.old]
        await env.query(p.original(p.new),None,base=p.old_taken,taken=p.new_taken,
            public_taken=p.old_taken,phase='new-misses-protected-short')
        c.check((p.old,before),(c.active_owner,c.states()[p.old]),'new branch cannot change protected old confidence or protection')
        c.mark('protected-short-keeps-old-owner',state=before)
        weak=4 if p.new_taken else 3
        original_long=next(ledger for key,ledger in c.long_records.items()
            if key[0]==p.new and key[1]==p.original(p.new).read_indices[1])
        await env.query(p.original(p.new),(1,original_long.counter,p.new_taken),base=p.old_taken,taken=p.new_taken,
            phase='new-long-while-old-protected')
        c.mark('new-own-long-fallback',branch=p.new)
        await env.storage('protected')
        c.declared_results[p.old]=p.new_taken
        for number in range(len(RELEASE_PATHS)):
            counter,protection=c.states()[p.old]
            path=p.release(number)
            await env.query(path,(0,counter,p.old_taken),base=p.old_taken,taken=p.new_taken,
                public_taken=p.old_taken,phase='old-original-error-'+str(number+1))
            c.check(max(0,protection-1),c.states()[p.old][1],'each original old error releases only its own protection')
        c.check(0,c.states()[p.old][1],'normal old errors release the shared record')
        c.mark('old-errors-release-protection',originals=len(RELEASE_PATHS))
        c.declared_results[p.old]=p.old_taken
        for number in range(3):
            counter,protection=c.states()[p.old]
            await env.query(p.original(p.old),(0,counter,p.old_taken),base=p.old_taken,taken=p.old_taken,
                phase='old-correct-agreement-'+str(number+1))
            c.check((0,0),(protection,c.states()[p.old][1]),'correct agreement must not re-protect the released record')
        c.check((7 if p.old_taken else 0,0),c.states()[p.old],'old strong confidence survives without replacement protection')
        c.mark('agreement-restores-confidence-not-protection',state=c.states()[p.old])
        await env.storage('released')
        retained={key:(ledger.counter,ledger.protection) for key,ledger in c.long_records.items()}
        await env.query(p.admission,None,base=p.old_taken,taken=p.new_taken,public_taken=p.old_taken,
            phase='new-cold-original-admits-short')
        c.check((p.new,(weak,1)),(c.active_owner,c.states()[p.new]),'newcomer starts with its own weak confidence and initial protection')
        c.mark('new-own-weak-confidence',counter=weak)
        await env.storage('new-owner')
        c.check(retained,{key:(ledger.counter,ledger.protection) for key,ledger in c.long_records.items()},
            'short ownership transfer preserves both branches original long experiences')
        await env.query(p.admission,(0,weak,p.new_taken),base=p.old_taken,taken=p.new_taken,
            phase='new-short-after-replacement')
        await env.query(p.original(p.old),None,base=p.old_taken,taken=p.old_taken,
            phase='old-own-fallback')
        c.mark('old-falls-back-without-borrowing-new',branch=p.old)
        new_long=next(ledger for key,ledger in c.long_records.items()
            if key[0]==p.new and key[1]==p.original(p.new).read_indices[1])
        await env.query(p.original(p.new),(1,new_long.counter,p.new_taken),base=p.old_taken,taken=p.new_taken,
            phase='new-original-long-preserved')
        old_long=next(ledger for key,ledger in c.long_records.items()
            if key[0]==p.old and key[1]==p.release(0).read_indices[1])
        await env.query(p.release(0),(1,old_long.counter,p.new_taken),base=p.old_taken,taken=p.old_taken,
            public_taken=p.new_taken,phase='old-original-long-preserved')
        c.mark('both-long-experiences-preserved',records=len(c.long_records))
        c.mark('actual-shared-SRAM-stages',snapshots=len(c.storage_checks))
        c.mark('original-sources-once-and-immutable',snapshots=len(c.originals))
    try:c.finish_competition()
    except BaseException as error:
        coverage.evidence=dict(c.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:coverage.evidence=dict(c.summary(),status='PASS')
