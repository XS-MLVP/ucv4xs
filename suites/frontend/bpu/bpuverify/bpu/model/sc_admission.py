"""Original feedback eligibility crosses actual concurrent resource use."""
from dataclasses import dataclass

from bpuverify.bpu.model.statistical_prefix import Layout, ConcurrentContextLayout

MODES = ('same-resource.used-wrong','same-resource.used-correct','independent-resource.used-wrong')
PROFILES = tuple(direction+'.'+mode for direction in ('condition-taken','condition-not-taken') for mode in MODES)
READ_ONLY_PROFILES = tuple(direction+'.'+resource+'.used-correct-disagrees'
    for direction in ('condition-taken','condition-not-taken')
    for resource in ('same-resource','independent-resource'))
RULES = ('real-used-original','active-prediction-stream','complete-proposal-owned',
    'eligibility-selects-admission','one-actual-acceptance','actual-learning-effects',
    'fresh-owned-consumer','original-evidence-preserved')
BURST_PROFILES = tuple(direction+'.'+resource+'.queued-mixed'
    for direction in ('condition-taken','condition-not-taken')
    for resource in ('same-resource','independent-resource'))
BURST_RULES = ('distinct-complete-originals','actual-prediction-overlap','held-head-preserves-payload',
    'actual-ordered-adjacent-acceptances','eligibility-belongs-to-original','all-signed-learning-effects',
    'fresh-consumers-for-both-branches','immutable-old-evidence')


@dataclass(frozen=True)
class Program(Layout):
    def __post_init__(self):
        if self.profile not in (*PROFILES,*READ_ONLY_PROFILES):
            raise ValueError('declared SC admission behavior required')

    @property
    def b(self):
        return 0x40000002

    @property
    def positive(self):
        return self.profile.startswith('condition-taken.')

    @property
    def needs_read(self):
        return not self.profile.endswith('.used-correct')

    @property
    def read_only(self):
        return self.profile.endswith('.used-correct-disagrees')

    @property
    def needs_write(self):
        return self.needs_read and not self.read_only

    @property
    def blocked(self):
        return self.needs_read and '.same-resource.' in self.profile

    @property
    def loop(self):
        # Two resource relations, never a physical coverage sweep. Distinct
        # Main rows prevent the stream setup replacing the measured branch.
        return self.b+(0x80 if '.same-resource.' in self.profile else 0x181)

    @property
    def actual_taken(self):
        return not self.positive if self.needs_write else self.positive


@dataclass(frozen=True)
class BurstProgram(Program):
    """Two wrong corrected predictions surround another branch's feedback."""
    def __post_init__(self):
        if self.profile not in BURST_PROFILES:
            raise ValueError('declared concurrent feedback burst required')

    @property
    def source_pcs(self):
        return self.b,self.x,self.b

    @property
    def truths(self):
        return not self.positive,self.positive,not self.positive


CONTEXT_BURST_PROFILES = tuple(order+'.'+agreement+'.'+resource
    for order in ('old-first','young-first') for agreement in ('agree','disagree')
    for resource in ('same-resource','independent-resource'))
CONTEXT_BURST_RULES = tuple('fresh-consumers-for-both-contexts' if rule=='fresh-consumers-for-both-branches'
                          else rule for rule in BURST_RULES) + ('distinct-valid-nonzero-contexts',
    'shared-and-private-feature-effects','original-qualification-not-current',
    'all-context-numeric-consumers','original-age-vs-arrival-order')


@dataclass(frozen=True, slots=True)
class ContextBurstLayout(ConcurrentContextLayout):
    """One loop supplies two real experiences; no multi-branch setup alias."""
    def __post_init__(self):
        if self.profile not in CONTEXT_BURST_PROFILES:
            raise ValueError('declared distinct-context feedback lifetime required')

    def prefix_for(self, context):
        if context not in self.contexts:
            raise ValueError('one of the two real loop experiences required')
        return self.loop_prefix

    contexts=('short-loop','long-loop')

    @property
    def loop_prefix(self):return 0x40010600

    @property
    def jump(self):return self.loop_prefix+0x200

    def exit_history(self, context):
        if context not in self.contexts:raise ValueError('declared loop experience required')
        return 3 if context=='short-loop' else 7

    def history(self, context):
        from bpuverify.bpu.model.common_history import GHR_WIDTH,BW_WIDTH
        value=self.exit_history(context)<<1  # The actual loop exit appends NT.
        return value% (1<<GHR_WIDTH),value% (1<<BW_WIDTH)

    @property
    def teaching_contexts(self):return (self.contexts[0],)*4+(self.contexts[1],)*4

    @property
    def capture_contexts(self):return self.contexts*8

    @property
    def weakening_count(self):return 6

    @property
    def arrival_order(self):
        available=tuple(range(self.weakening_count,len(self.capture_contexts)))
        return available if self.profile.startswith('old-first.') else available[::-1]

    @property
    def truths(self):return (False,)*6+(True,True)+(False,False)

    @property
    def source_pcs(self):return (self.b,)*len(self.truths)

    @property
    def blocked(self):return self.same_resource
