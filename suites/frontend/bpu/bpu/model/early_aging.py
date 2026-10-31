"""Event-level allocation failures, independent of RTL controls and clock wires."""
from dataclasses import dataclass

FAILURES_PER_AGE = 128


@dataclass(frozen=True, slots=True)
class Allocation:
    wrong_position: int | None
    provider: int | None
    candidate: int | None

    @property
    def failed(self):
        return self.wrong_position is not None and self.candidate is None

    @property
    def mask(self):
        return 0 if self.candidate is None else 1 << self.candidate


def allocation(feedback, protection):
    """Only the original executed conditional prefix can request a new record.

    Protection is the independently owned state at the learning READ, not a
    sampled allocation mask, current provider, or counter used as a seed.
    """
    if len(protection) != 2 or any(type(value) is not int or not 0 <= value <= 3 for value in protection):
        raise ValueError('two independently owned two-bit protection values required')
    errors = [source for source in feedback.sources if source.valid
        and source.position <= feedback.position
        and (source.position < feedback.position or feedback.kind == 1)
        and (source.predicted if source.hit else source.base)
            != bool(source.position == feedback.position and feedback.taken)]
    first = min(errors, key=lambda source: source.position) if errors else None
    provider = first.provider if first is not None and first.hit else None
    minimum = 0 if provider is None else provider + 1
    candidate = next((table for table in range(minimum, 2) if protection[table] == 0), None)
    return Allocation(None if first is None else first.position, provider, candidate)


class FailureLedger:
    """Count actual qualified learning events, never elapsed cycles or sends."""
    def __init__(self):
        self.count = self.failures = self.ages = self.successes = 0

    @property
    def aging(self):
        return self.count == FAILURES_PER_AGE

    def apply(self, decision):
        if self.aging:
            self.count = 0
            self.ages += 1
        elif decision is not None and decision.failed:
            self.count += 1
            self.failures += 1
        if decision is not None and decision.wrong_position is not None and not decision.failed:
            self.successes += 1


def aged(protection):
    if len(protection) != 2 or any(len(table) != 512 for table in protection):
        raise ValueError('aging requires the complete two-table state')
    return (tuple(max(0, value - 1) for value in protection[0]),
            tuple(value // 2 for value in protection[1]))


def require_recovery_window(current_edges, source_edges, *, capacity, history_bits, shift):
    """Conservative necessary window, NOT a complete FTQ/physical-ancestry proof."""
    displacement = (current_edges - source_edges) * shift
    if displacement < 0 or displacement > capacity - history_bits:
        raise ValueError(f'recovery checkpoint outside retained history window: '
                         f'displacement={displacement}, budget={capacity-history_bits}')
    return displacement
