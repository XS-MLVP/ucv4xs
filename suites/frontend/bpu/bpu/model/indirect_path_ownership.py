"""Original direction/indirect-target lifetime and legal instruction program."""
from suites.frontend.bpu.bpu.model.late_correction_learning import Program as Layout
from suites.frontend.bpu.bpu.model.selection import Kind

PROFILES = tuple(entry + '.' + mode for entry in ('compressed-entry', 'conditional-entry')
    for mode in ('held', 'flowing'))

RULES = (
    'real-conditional-experience', 'independent-target-experience',
    'same-original-direction-repair', 'same-original-target-repair',
    'wrong-successor-cancelled', 'original-history-restored',
    'original-conditional-learning', 'next-actual-state-confirmed',
    'exact-restored-original', 'fresh-original-direction-consumer',
    'original-metadata-immutable', 'all-nine-real-feedbacks',
)

PHASES = ('predecessor', 'conditional', 'not-taken', 'strengthen-negative', 'fallback',
    'stable-target-cold', 'stable-target-reinforce', 'stable-target-confirm', 'different-main-target')

def resolution(p, phase):
    kind = int(Kind.CONDITIONAL if phase in ('conditional', 'not-taken', 'strengthen-negative')
        else Kind.DIRECT if phase == 'predecessor' else Kind.INDIRECT)
    pc = p.a if phase == 'predecessor' else p.b
    position = 2 if kind == int(Kind.CONDITIONAL) else 4
    target = p.b if phase == 'predecessor' else p.a + 0x200 if phase == 'different-main-target' else p.a
    taken = phase not in ('not-taken', 'strengthen-negative')
    wrong = phase not in ('strengthen-negative', 'stable-target-reinforce', 'stable-target-confirm')
    return pc, position, target, kind, taken, wrong


def layout(profile):
    if profile not in PROFILES: raise ValueError('declared semantic profile required')
    entry, mode = profile.split('.')
    return Layout(entry, mode == 'flowing')
