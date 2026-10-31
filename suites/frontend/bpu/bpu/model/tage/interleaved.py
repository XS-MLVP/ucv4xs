"""Semantic stimulus contract; the predictor oracle remains TageReference.

Four known branches occupy both fetch windows. Other valid resolved branches
interleave them: valid-but-untracked is not an empty/invalid feedback slot.
No physical SRAM coordinate is an axis of this program.
"""
PC = 0x40000800
RESOLVED = tuple(range(0,16,2))
TRACKED = (4,6,10,14)
UNTRACKED = tuple(position for position in RESOLVED if position not in TRACKED)
OWNERS = ((2,0),(2,1),(3,0),(3,1))


def target(position):
    return PC+0x200+position*0x20


def opposing_base_program():
    """Known zero 2-bit bases -> two; earlier executed branches resolve NT.

    Work backwards so later taken outcomes cannot weaken an already restored
    earlier base. Two outcomes are counter semantics, not a settling delay.
    """
    for selected in reversed(TRACKED):
        for _ in range(2):
            yield tuple((position,position==selected,position==selected)
                for position in TRACKED if position<=selected)


def discovery_outcomes(selected):
    """Resolve every earlier conditional NT before the newly taken branch."""
    if selected not in UNTRACKED:raise ValueError('discovery requires a formerly untracked branch')
    return tuple((position,position==selected,position==selected) for position in RESOLVED if position<=selected)
