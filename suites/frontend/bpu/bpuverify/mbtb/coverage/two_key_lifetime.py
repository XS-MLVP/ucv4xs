"""Semantic completion and an unchanged optional physical matrix are distinct."""
from copy import deepcopy
from toffee import Bin,CoverGroupDef,CoverPointDef,Scoreboard
from bpuverify.mbtb.coverage.catalog import mbtb_entry_keys_coverage_model
from bpuverify.mbtb.model.two_key_programs import SEMANTIC_PROGRAMS,RULES

PHASES=('prepared','updated','revisited')
PHASE_RULES=(RULES[:1],RULES[1:4],RULES[4:])


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared two-key evidence role required')
    bins={p.label+'.'+r:Bin.values(p.label+'.'+r) for p in SEMANTIC_PROGRAMS for r in RULES}
    return CoverGroupDef('mbtb_two_key_lifetime_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.mbtb.two-key-lifetime.'+status)


class Coverage:
    def __init__(self,program):
        self.program=program;self.legacy=mbtb_entry_keys_coverage_model()
        self.groups={s:lifetime_coverage(s) for s in ('reached','checked')}
        self.phases=[];self.closed=False
    def sample(self,values):
        if self.closed or len(self.phases)==len(PHASES):raise ValueError('completed two-key lifetime cannot be replayed')
        phase=values.get('phase')
        if {k:v for k,v in values.items() if k!='phase'}!=self.program.sample() or phase!=PHASES[len(self.phases)]:
            raise ValueError('only the declared physical replica and ordered semantic phases may contribute')
        self.legacy.sample(values)
        for rule in PHASE_RULES[len(self.phases)]:self.groups['reached'].sample(dict(obligation=self.program.label+'.'+rule))
        self.phases.append(phase)
    def finish(self,receipt):
        if self.closed or tuple(self.phases)!=PHASES:raise AssertionError('incomplete two-key lifetime has no checked credit')
        assert receipt['original_metadata_unchanged'] is True
        assert receipt['independent_reference_checks']>0 and receipt['independent_reference_failures']==0
        assert len(receipt['actual_activity']['requests'])==len(receipt['actual_activity']['writebacks'])==2
        assert len({(r['set_idx'],r['tag']) for r in receipt['actual_activity']['requests']})==2
        Scoreboard('mbtb.two-key-lifetime-complete-activity').check(expected=receipt['expected_activity'],actual=receipt['actual_activity'])
        for rule in RULES:self.groups['checked'].sample(dict(obligation=self.program.label+'.'+rule))
        self.closed=True
        return dict(program=self.program.state(),completed_obligations=list(RULES),physical_schema_unchanged=True,**deepcopy(receipt))
