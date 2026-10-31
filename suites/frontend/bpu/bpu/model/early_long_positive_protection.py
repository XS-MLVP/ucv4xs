from suites.frontend.bpu.bpu.model.early_opposition import FALLBACK
"""The last taken provider has no longer candidate, but keeps learning."""
from suites.frontend.bpu.models.configuration import *

from suites.frontend.bpu.bpu.model.early_opposition import CONDITIONAL, FALLBACK
from suites.frontend.bpu.bpu.model.early_protection import Identity, rules as protection_rules
from suites.frontend.bpu.bpu.model.path_history import SHIFT, WIDTH, path_contribution
from suites.frontend.bpu.utage.model.semantic import HISTORIES, Context, indices, tag


EDGES = {
    'upper-hold': (('reach-upper', 'reward', 2, 3), ('upper-hold', 'reward', 3, 3)),
    'upper-release': (('reach-upper', 'reward', 2, 3), ('upper-hold', 'reward', 3, 3),
                      ('upper-release', 'penalty', 3, 2)),
    'lower-recover': (('toward-lower', 'penalty', 2, 1), ('reach-lower', 'penalty', 1, 0),
                      ('lower-hold', 'penalty', 0, 0), ('lower-recover', 'reward', 0, 1)),
    'direction-crossing': (('toward-lower', 'penalty', 2, 1), ('reach-lower', 'penalty', 1, 0),
                           ('lower-hold', 'penalty', 0, 0), ('T-becomes-NT', 'penalty', 0, 0),
                           ('NT-error-restores-T', 'penalty', 0, 0),
                           ('T-correction-restores-protection', 'reward', 0, 1)),
}
REVISIT_PREFIX = (CONDITIONAL,) * ((max(HISTORIES)+SHIFT-1)//SHIFT) + (FALLBACK, CONDITIONAL, CONDITIONAL)
SHORT_REVISIT_PREFIX = (CONDITIONAL,) * ((max(HISTORIES)+SHIFT-1)//SHIFT)
EXTRA = ('confirmed-T-seed', 'neutral-direction-strength', 'long-not-short-provider',
         'actual-acceptance-window')
FREE_SHORT_MODES = ('lower-recover', 'direction-crossing')


def rules(mode):
    return protection_rules(mode, edges=EDGES) + EXTRA + (
        ('longer-allocation-eligibility', 'last-provider-error-accounted')
        if mode != 'upper-hold' else ()) + (
        ('short-available-before-long-error', 'no-backward-allocation-with-free-short', 'short-resident-preserved')
        if mode in FREE_SHORT_MODES else ()) + (
        ('restored-T-before-protection',) if mode == 'direction-crossing' else ())


def intended_identity(pc):
    # These are two different logical ancestors. Derive them from real branch
    # paths, not DUT indices or whichever long provider happens to appear.
    word = 0
    for position in REVISIT_PREFIX:
        word = ((word << SHIFT) ^ path_contribution((pc//16)*16+position, pc)) % (1 << WIDTH)
    read = Context.from_recent(word % (1 << PHR_BITS))
    match = Context.from_recent(((word << SHIFT) ^ path_contribution((pc//16)*16+CONDITIONAL, pc)) % (1 << PHR_BITS))
    return Identity(1, indices(pc, read)[1], tag(pc, match, 1), CONDITIONAL)
