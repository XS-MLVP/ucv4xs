"""Independent permit state machine; no native handles or simulator phases."""
from dataclasses import dataclass

from .types import Beat, Entry, NUM_ENTRIES, Observation, Permit


def _same_rob(permit, entry):
    return permit is not None and permit.rob_flag == entry.rob_flag and permit.rob_value == entry.rob_value


def _need_flush(permit, redirect):
    if permit is None or not redirect.valid:
        return False
    same = permit.rob_flag == redirect.rob_flag and permit.rob_value == redirect.rob_value
    return (bool(redirect.level) and same) or permit.rob_flag != redirect.rob_flag or (
        permit.rob_value > redirect.rob_value
    )


@dataclass(frozen=True, slots=True)
class State:
    permits: tuple[Permit | None, ...] = (None,) * NUM_ENTRIES

    def __post_init__(self):
        if len(self.permits) != NUM_ENTRIES:
            raise ValueError('permit state must contain eight physical slots')

    def observe(self, entries: tuple[Entry, ...]) -> Observation:
        bits = []
        for index, entry in enumerate(entries):
            direct = not entry.valid or not entry.is_ordered or not entry.is_load or entry.uop_idx == 0
            permit = self.permits[index]
            bits.append(direct or (_same_rob(permit, entry) and permit.uop_idx == entry.uop_idx))
        return Observation(tuple(bits))

    def selected(self, beat: Beat):
        if not beat.split_done.valid:
            return None
        return beat.entries[beat.split_done.entry_idx]

    def actions(self, beat: Beat):
        entry = self.selected(beat)
        ordered_done = entry is not None and entry.is_ordered_load
        consume = ordered_done and entry.uop_idx != 0
        handoff = ordered_done and not entry.exception and not entry.last_uop
        successor = None if entry is None else (beat.split_done.entry_idx + 1) % NUM_ENTRIES
        return ordered_done, consume, handoff, successor

    def following(self, beat: Beat):
        ordered_done, consume, handoff, successor = self.actions(beat)
        permits = list(self.permits)
        source = beat.split_done.entry_idx if beat.split_done.valid else None
        for index, permit in enumerate(permits):
            if _need_flush(permit, beat.redirect) or (consume and index == source):
                permits[index] = None
        if handoff:
            entry = beat.entries[source]
            permits[successor] = Permit(entry.rob_flag, entry.rob_value, (entry.uop_idx + 1) & 7)
        return State(tuple(permits))
