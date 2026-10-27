"""SC-guided early prediction experience, not backend execution truth."""
from dataclasses import dataclass

from bpuverify.bpu.model.conditional_prefix import Layout
from bpuverify.bpu.model.selection import Kind
from bpuverify.tage.model.semantic import TABLES

PROFILES = tuple(entry+'.'+mode for entry in ('compressed-entry','conditional-entry') for mode in ('held','flowing'))
RULES = ('real-early-conditional-original','independent-SC-opposition',
    'same-original-middle-choice','SC-final-target-and-repair',
    'younger-release-and-original-history','actual-original-guidance',
    'next-complete-learning-state','exact-restored-original',
    'natural-early-NT-consumer','fresh-complete-early-target',
    'original-nine-domains-immutable','distinct-real-SC-learning-inputs',
    'newer-opposite-guidance-owns-its-update','newer-protection-loss-confirmed')


@dataclass(frozen=True)
class Program(Layout):
    def __post_init__(self):
        if self.profile not in PROFILES:
            raise ValueError('declared SC early-learning instruction program required')

    @property
    def x(self):
        return self.b+0x400

    @property
    def stable_predecessor_history(self):
        return self.recent


def direction_ready(bank,token,program):
    branches,fields,late = bank.tage_decision(token)
    slot = next((i for i,b in enumerate(branches) if b is not None and b.position==2),None)
    return slot is not None and (fields.get(f'{slot}.has_provider')
        and fields.get(f'{slot}.counter')==3 and fields.get(f'{slot}.table')==TABLES-1
        and not fields.get(f'{slot}.has_alt') and not fields.get(f'{slot}.use_provider')
        and bool(fields.get(f'{slot}.alternative')) and late.branch.kind==Kind.CONDITIONAL
        and late.branch.position==2 and late.branch.target==program.d)
