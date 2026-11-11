"""One short-history branch surviving strength limits and longer allocation.

Older outcomes distinguish long histories while the common recent suffix
continues to address the same short branch. These are program paths, not a
bank/set enumeration or a way to prescribe table contents.
"""
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import CONDITIONAL
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import FALLBACK
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import loop_history
from suites.frontend.bpu.testbenches.bpu.model.early_protection import Identity
from suites.frontend.bpu.testbenches.bpu.model.early_protection import rules as protection_rules
from suites.frontend.bpu.testbenches.utage.model.semantic import Context
from suites.frontend.bpu.testbenches.utage.model.semantic import indices
from suites.frontend.bpu.testbenches.utage.model.semantic import tag


EDGES = {
    'upper-hold': (('approach-upper', 'reward', 1, 2), ('reach-upper', 'reward', 2, 3),
                   ('upper-hold', 'reward', 3, 3)),
    'upper-release': (('approach-upper', 'reward', 1, 2), ('reach-upper', 'reward', 2, 3),
                      ('upper-hold', 'reward', 3, 3), ('upper-release', 'penalty', 3, 2)),
    'lower-recover': (('reach-lower', 'penalty', 1, 0), ('lower-hold', 'penalty', 0, 0),
                      ('lower-recover', 'reward', 0, 1)),
}
# The second prefix differs in the last older history bit retained after the
# common fallback suffix. Reuse the first prefix for the final short consumer.
OLDER_PATHS = ((CONDITIONAL,) * 6,
               (CONDITIONAL,) * 4 + (FALLBACK, CONDITIONAL),
               (CONDITIONAL,) * 6)

EXTRA = ('short-not-long-provider', 'actual-acceptance-window', 'neutral-seed-confirmed')


def rules(mode):
    return protection_rules(mode, edges=EDGES) + EXTRA + (
        ('longer-allocation-eligibility', 'parallel-long-allocation', 'fresh-long-consumer')
        if mode != 'upper-hold' else ())


def original_identity(pc):
    context = Context.from_recent(loop_history(pc, FALLBACK))
    return Identity(0, indices(pc, context)[0], tag(pc, context, 0), CONDITIONAL)
