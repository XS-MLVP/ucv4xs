"""Semantic values with a transaction-time visibility queue, not a bank RTL clone."""
from collections import deque

from .types import Commit


def matches(spec, query, value):
    if spec["kind"] == "byte_mask":
        return bool(query.value & value)
    if spec["kind"] == "address_line" and query.line:
        return query.value >> spec["line_low_bits"] == value >> spec["line_low_bits"]
    return query.value == value


class CamModel:
    def __init__(self, spec):
        self.spec = spec
        self.entries = [None] * spec["size"]
        self.versions = [0] * spec["size"]
        self.pending = deque([()] * (spec["write_delay"] - 1))
        self.sequence = 0

    def advance(self, observation):
        incoming = tuple((i, w) for i, w in enumerate(observation.writes) if w.enabled)
        if len({w.address for _, w in incoming}) != len(incoming):
            raise ValueError("simultaneous conflicting CAM writes are outside the contract")
        for _, w in incoming:
            if not 0 <= w.address < self.spec["size"] or not 0 <= w.value < 1 << self.spec["width"]:
                raise ValueError("CAM write outside legal address/data domain")
        if self.pending:
            commits = self.pending.popleft()
            self.pending.append(incoming)
        else:
            commits = incoming
        result = []
        for lane, write in commits:
            self.sequence += 1
            old = self.entries[write.address]
            self.entries[write.address] = write.value
            self.versions[write.address] = self.sequence
            result.append(Commit(lane, write.address, old, write.value, self.sequence))
        return tuple(result)


def compare(observation, entries, spec, *, phase, tick):
    known = sum(1 << i for i, value in enumerate(entries) if value is not None)
    for port, (query, actual) in enumerate(zip(observation.queries, observation.masks, strict=True)):
        expected = sum(1 << i for i, value in enumerate(entries)
                       if value is not None and matches(spec, query, value))
        assert actual & known == expected, (
            spec["top"], phase, tick, "query", port, query,
            "actual_known", hex(actual & known), "expected", hex(expected), "known", hex(known))
    return known.bit_count() * len(observation.queries)
