"""A near-capacity call tree, not an enumeration of stack storage positions."""
from dataclasses import dataclass
from bpuverify.ras.model.model import CommittedStack,advance

ROOT=0x40030000
ROOT_RETURN=ROOT+16
POSITION=15
DEPTHS=('one-group-free','exact-retained-capacity')
RELATIONS=('outer-heavy','inner-heavy')
RULES=('distinct-recursive-layer-sources','older-calls-retired-before-growth',
    'owned-target-corrections','no-duplicate-redone-call','all-logical-calls-retained',
    'innermost-repeat-boundary','complete-mixed-pc-return-chain','outer-return-identities-restored',
    'outer-repeat-counts-preserved','every-live-operation-retired-once',
    'complete-sentinel-state-restored','immutable-originals')


@dataclass(frozen=True,slots=True)
class Program:
    depth:str
    relation:str

    def __post_init__(self):
        if type(self.depth) is not str or self.depth not in DEPTHS:raise ValueError('declared retained-capacity boundary required')
        if type(self.relation) is not str or self.relation not in RELATIONS:raise ValueError('declared outer/inner count relation required')

    @property
    def label(self):return self.depth+'.'+self.relation

    @property
    def layer_pcs(self):
        # One sentinel and one root caller also occupy retained logical groups.
        layers=len(CommittedStack().cells)-(2 if self.depth=='exact-retained-capacity' else 3)
        return tuple(ROOT+0x60*(index+1) for index in range(layers))

    @property
    def counts(self):
        repeated=(3,2) if self.relation=='outer-heavy' else (2,3)
        return (1,)*(len(self.layer_pcs)-2)+repeated

    @property
    def inner_calls(self):return self.counts[-1]

    def call_addresses(self,layers=None):
        if layers is None:layers=len(self.layer_pcs)
        if type(layers) is not int or not 0<=layers<=len(self.layer_pcs):raise ValueError('declared layer prefix required')
        return (ROOT_RETURN,)+tuple(pc+16 for pc,count in zip(self.layer_pcs[:layers],self.counts[:layers],strict=True)
            for _ in range(count))

    @property
    def return_targets(self):return self.call_addresses()[::-1]

    @property
    def return_pcs(self):return (self.layer_pcs[-1]+16,)+self.return_targets[:-1]

    def committed(self,*,layers=None,returned=0):
        addresses=self.call_addresses(layers)
        if type(returned) is not int or not 0<=returned<=len(addresses):raise ValueError('return cannot consume an absent logical caller')
        state=CommittedStack()
        for address in addresses:state=advance(state,2,address=address)
        for _ in range(returned):state=advance(state,1)
        return state

    def sites(self):
        return ((ROOT,self.layer_pcs[0],2,2),)+tuple((pc,pc,3,2) for pc in self.layer_pcs)+tuple(
            (pc+16,ROOT+0xF000,3,1) for pc in self.layer_pcs)+((ROOT_RETURN,ROOT_RETURN,2,0),)

    def state(self):
        return dict(depth=self.depth,relation=self.relation,layer_pcs=self.layer_pcs,counts=self.counts,
            logical_calls=len(self.call_addresses()),retained_groups=len(self.committed().groups),
            expected_return_pcs=self.return_pcs,expected_return_targets=self.return_targets,
            physical_coordinate_enumeration=False,all_logical_callers_retained=True)
