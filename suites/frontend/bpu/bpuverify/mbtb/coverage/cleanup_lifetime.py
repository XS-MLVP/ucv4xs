"""A clear and an independent correction must both complete, not just arrive."""
from copy import deepcopy
from toffee import Bin,CoverGroupDef,CoverPointDef,Scoreboard
from bpuverify.mbtb.coverage.catalog import mbtb_cleanup_overlap_coverage_model
from bpuverify.mbtb.model.cleanup_programs import SEMANTIC_PROGRAMS,RULES

PHASES=('prepared','overlapped','revisited')
PHASE_RULES=(RULES[:1],RULES[1:4],RULES[4:])


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared evidence role required')
    bins={p.label+'.'+r:Bin.values(p.label+'.'+r) for p in SEMANTIC_PROGRAMS for r in RULES}
    return CoverGroupDef('mbtb_cleanup_lifetime_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.mbtb.cleanup-lifetime.'+status)


class Coverage:
    def __init__(self,program):
        self.program=program;self.legacy=mbtb_cleanup_overlap_coverage_model()
        self.groups={s:lifetime_coverage(s) for s in ('reached','checked')}
        self.phases=[];self.closed=False
    def sample(self,values):
        if self.closed or len(self.phases)==len(PHASES):raise ValueError('completed cleanup cannot be replayed')
        if {k:v for k,v in values.items() if k!='phase'}!=self.program.sample() or values.get('phase')!=PHASES[len(self.phases)]:
            raise ValueError('declared replica and ordered cleanup phases required')
        self.legacy.sample(values)
        for rule in PHASE_RULES[len(self.phases)]:self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule))
        self.phases.append(values['phase'])
    def finish(self,receipt):
        assert not self.closed and tuple(self.phases)==PHASES,'incomplete cleanup cannot earn checked credit'
        assert receipt['original_metadata_unchanged'] is True
        assert receipt['independent_reference_checks']>0 and receipt['independent_reference_failures']==0
        assert receipt['public_profiles_checked'] is True and receipt['request_offset']==4
        assert receipt['integrated_ftq_reachability_proven'] is False
        board=Scoreboard('mbtb.cleanup-complete-interference')
        board.check(expected=receipt['expected_dual'],actual=receipt['actual_dual'])
        board.check(expected=receipt['expected_feedback'],actual=receipt['actual_feedback'])
        assert len(receipt['actual_dual']['ports'])==2 and not receipt['actual_dual']['foreign_writes']
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
        return dict(program=self.program.state(),completed_obligations=list(RULES),physical_schema_unchanged=True,**deepcopy(receipt))
