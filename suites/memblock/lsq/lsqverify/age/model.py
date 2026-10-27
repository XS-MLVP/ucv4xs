from .types import Change, bitmap


def selected(order, ready):
    return next((item for item in order if ready >> item & 1), None)


def compare(observation, order, *, phase, tick):
    assert not observation.ready_mask & ~bitmap(order), (phase, tick, "ready outside live domain")
    winner = selected(order, observation.ready_mask)
    expected = 0 if winner is None else 1 << winner
    assert observation.output == expected, (phase, tick, "order", order, "ready", hex(observation.ready_mask),
                                           "actual", hex(observation.output), "expected", hex(expected))
    return winner


class AgeModel:
    def __init__(self, size):
        self.size = size
        self.order = []
        self.generations = {}
        self.reset_kind = None

    def advance(self, obs):
        before = tuple(self.order)
        if obs.reset:
            if any(obs.enqueue_masks) or obs.remove_mask or obs.ready_mask:
                raise ValueError("reset requires idle age-selector inputs")
            self.reset_kind = self.reset_kind or ("active" if before else "initial")
            self.order = []
            self.generations.clear()
            return Change(before, (), (), (), (), self.reset_kind)
        self.reset_kind = None
        if obs.ready_mask & ~bitmap(before):
            raise ValueError("ready must be a subset of the current live set")
        if any(mask.bit_count() > 1 for mask in obs.enqueue_masks):
            raise ValueError("each enqueue port must be zero or one-hot")
        incoming = tuple(mask.bit_length() - 1 for mask in obs.enqueue_masks if mask)
        if len(set(incoming)) != len(incoming):
            raise ValueError("enqueue ports may not target the same ID")
        removed = tuple(item for item in before if obs.remove_mask >> item & 1)
        survivors = [item for item in before if not obs.remove_mask >> item & 1]
        inserted = tuple(item for item in incoming if not obs.remove_mask >> item & 1)
        if set(inserted) & set(survivors):
            raise ValueError("enqueue of an already-live age-selector ID")
        reused = tuple(item for item in inserted if item in self.generations)
        for item in inserted:
            self.generations[item] = self.generations.get(item, 0) + 1
        self.order = [*survivors, *inserted]
        assert len(set(self.order)) == len(self.order) <= self.size
        assert all(0 <= item < self.size for item in self.order)
        return Change(before, inserted, removed, tuple(item for item in incoming if obs.remove_mask >> item & 1), reused)
