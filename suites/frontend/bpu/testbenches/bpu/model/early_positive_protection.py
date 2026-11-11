"""A predeclared taken record: neutral strength, protection limits and recovery."""
from suites.frontend.bpu.testbenches.bpu.model.early_protection import rules as protection_rules
from suites.frontend.bpu.testbenches.bpu.model.early_short_protection import EDGES as STRENGTH_EDGES
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import CONDITIONAL
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import FALLBACK
from suites.frontend.bpu.testbenches.bpu.model.path_history import SHIFT
from suites.frontend.bpu.testbenches.utage.model.semantic import HISTORIES


EDGES = dict(STRENGTH_EDGES, **{
    'direction-return': (('T-becomes-NT', 'penalty', 1, 0),
                         ('NT-error-restores-T', 'penalty', 0, 0),
                         ('T-correction-restores-protection', 'reward', 0, 1)),
})

# Both paths finish with the same recent taken history. Two earlier fallback
# edges retain a distinct9-bit index-read ancestor on the current5/9 geometry,
# rather than reusing the protected long row from the generic preparation.
# Keep the old one-fallback program in the frozen negative control.
OLDER_PATHS = ((CONDITIONAL,) * 5,
               (CONDITIONAL, CONDITIONAL, FALLBACK, FALLBACK, CONDITIONAL))

EXTRA = ('confirmed-T-seed', 'neutral-direction-strength', 'short-not-long-provider',
         'actual-acceptance-window')


def rules(mode):
    extras = tuple('weak-T-seed-preserved' if mode == 'direction-return' and name == 'neutral-direction-strength'
                   else name for name in EXTRA)
    return protection_rules(mode, edges=EDGES) + extras + (
        ('longer-allocation-eligibility', 'parallel-long-allocation', 'fresh-long-consumer')
        if mode in ('upper-release', 'lower-recover') else
        ('longer-allocation-eligibility',) if mode == 'direction-return' else ())
