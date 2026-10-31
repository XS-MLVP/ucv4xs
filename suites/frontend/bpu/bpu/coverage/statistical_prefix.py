"""SC prefix obligations require actual complete sources and fresh consumers."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.bpu.model.statistical_prefix import PROFILES, RULES
from suites.frontend.bpu.coverage.exports import write_functional_coverage


def lifetime_coverage(state):
    if state not in ('reached', 'checked'):
        raise ValueError('declared SC prefix lifecycle required')
    names = tuple(profile + '.' + rule for profile in PROFILES for rule in RULES)
    return CoverGroupDef('bpu_statistical_prefix_v1', (CoverPointDef('obligation',
        {name: Bin.values(name) for name in names}),)).instantiate('kunminghu_v3.bpu.statistical-prefix.' + state)


class Coverage:
    def __init__(self, profile):
        if profile not in PROFILES:
            raise ValueError('declared SC prefix program required')
        self.profile, self.reached, self.closed = profile, {}, False
        self.groups = {state: lifetime_coverage(state) for state in ('reached', 'checked')}

    def record(self, rule, tick):
        if self.closed or rule not in RULES:
            raise ValueError('open declared SC prefix obligation required')
        if rule not in self.reached:
            self.reached[rule] = tick
            self.groups['reached'].sample(dict(obligation=self.profile + '.' + rule), metadata=dict(tick=tick))

    def finish(self):
        if self.closed or set(self.reached) != set(RULES):
            raise AssertionError('all actual SC prefix sources, effects, feedback and consumers required')
        for rule, tick in self.reached.items():
            self.groups['checked'].sample(dict(obligation=self.profile + '.' + rule), metadata=dict(tick=tick))
        self.closed = True

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
            output / 'functional-coverage-statistical-prefix.json')


from suites.frontend.bpu.bpu.coverage.sc_admission import Coverage as RuleCoverage
from suites.frontend.bpu.bpu.model.statistical_prefix import CONTEXT_PROFILES,CONTEXT_RULES


def context_lifetime_coverage(state):
    if state not in ('reached','checked'):
        raise ValueError('declared nonzero SC context lifecycle required')
    return CoverGroupDef('bpu_sc_context_learning_v1',(CoverPointDef('obligation',
        {profile+'.'+rule:Bin.values(profile+'.'+rule)
            for profile in CONTEXT_PROFILES for rule in CONTEXT_RULES}),)).instantiate(
                'kunminghu_v3.bpu.sc-context-learning.'+state)


class ContextCoverage(RuleCoverage):
    profiles,rules=CONTEXT_PROFILES,CONTEXT_RULES
    factory=staticmethod(context_lifetime_coverage)
    filename='functional-coverage-sc-context-learning.json'


def concurrent_context_lifetime_coverage(state):
    from suites.frontend.bpu.bpu.model.statistical_prefix import CONCURRENT_CONTEXT_PROFILES,CONCURRENT_CONTEXT_RULES
    if state not in ('reached','checked'):
        raise ValueError('declared concurrent nonzero SC context lifecycle required')
    return CoverGroupDef('bpu_sc_concurrent_context_v1',(CoverPointDef('obligation',
        {profile+'.'+rule:Bin.values(profile+'.'+rule)
            for profile in CONCURRENT_CONTEXT_PROFILES for rule in CONCURRENT_CONTEXT_RULES}),)).instantiate(
                'kunminghu_v3.bpu.sc-concurrent-context.'+state)


class ConcurrentContextCoverage(RuleCoverage):
    from suites.frontend.bpu.bpu.model.statistical_prefix import CONCURRENT_CONTEXT_PROFILES,CONCURRENT_CONTEXT_RULES
    profiles,rules=CONCURRENT_CONTEXT_PROFILES,CONCURRENT_CONTEXT_RULES
    factory=staticmethod(concurrent_context_lifetime_coverage)
    filename='functional-coverage-sc-concurrent-context.json'
