"""A predeclared taken record: neutral strength, protection limits and recovery."""
from bpuverify.bpu.model.early_protection import rules as protection_rules
from bpuverify.bpu.model.early_short_protection import EDGES as STRENGTH_EDGES
from bpuverify.bpu.model.early_opposition import CONDITIONAL, FALLBACK
from bpuverify.bpu.model.path_history import SHIFT
from bpuverify.utage.model.semantic import HISTORIES


EDGES = dict(STRENGTH_EDGES, **{
    'direction-return': (('T-becomes-NT', 'penalty', 1, 0),
                         ('NT-error-restores-T', 'penalty', 0, 0),
                         ('T-correction-restores-protection', 'reward', 0, 1)),
})

# Both paths finish with the same recent taken history. Their older outcomes
# differ so an already protected long record cannot masquerade as a new one.
OLDER_PATHS = ((CONDITIONAL,) * (max(HISTORIES)//SHIFT),
               (FALLBACK,) * ((max(HISTORIES)-min(HISTORIES))//SHIFT)
               + (CONDITIONAL,) * (min(HISTORIES)//SHIFT))
EXTRA = ('confirmed-T-seed', 'neutral-direction-strength', 'short-not-long-provider',
         'actual-acceptance-window')


def rules(mode):
    extras = tuple('weak-T-seed-preserved' if mode == 'direction-return' and name == 'neutral-direction-strength'
                   else name for name in EXTRA)
    return protection_rules(mode, edges=EDGES) + extras + (
        ('longer-allocation-eligibility', 'parallel-long-allocation', 'fresh-long-consumer')
        if mode in ('upper-release', 'lower-recover') else
        ('longer-allocation-eligibility',) if mode == 'direction-return' else ())
