"""Owned fully associative victim records and snapshot service obligations.

Inputs are the reference model's writes and predictions. No sampled SRAM,
physical victim selection or observed counters seed this state.
SPDX-License-Identifier: MPL-2.0
"""
from dataclasses import dataclass, replace


class RecencyTree:
    def __init__(self, capacity):
        if capacity < 2 or capacity & (capacity - 1):
            raise ValueError('binary replacement tree requires a power of two')
        self.capacity = capacity
        self.older = [0] * (capacity - 1)

    def victim(self):
        node = 0
        while node < self.capacity - 1:
            node = 2 * node + 1 + self.older[node]
        return node - self.capacity + 1

    def touch(self, slot):
        if not 0 <= slot < self.capacity:
            raise ValueError('replacement slot outside capacity')
        node = self.capacity - 1 + slot
        while node:
            parent = (node - 1) // 2
            direction = node - (2 * parent + 1)
            self.older[parent] = 1 - direction
            node = parent


@dataclass(frozen=True, slots=True)
class Record:
    bank: int
    row: int
    entry: object
    counter: int = 2


class VictimRecords:
    def __init__(self, capacity=16):
        self.records = [None] * capacity
        self.recency = RecencyTree(capacity)

    def matching(self, bank, row, tag):
        return tuple((i, record) for i, record in enumerate(self.records)
                     if record is not None and record.bank == bank and record.row == row
                     and record.entry.valid and record.entry.tag == tag)

    def exact(self, bank, row, entry):
        return next((i for i, record in self.matching(bank, row, entry.tag)
                     if record.entry.position == entry.position), None)

    def snapshot(self, bank, row, evicted, incoming):
        old = self.exact(bank, row, evicted) if evicted.valid else None
        new = self.exact(bank, row, incoming) if incoming.valid else None
        vacant = next((i for i, record in enumerate(self.records) if record is None), None)
        destination = old if old is not None else new if new is not None else (
            vacant if vacant is not None else self.recency.victim())
        if new is not None:
            self.records[new] = None
        if evicted.valid and (not incoming.valid or
                             (evicted.tag, evicted.position) != (incoming.tag, incoming.position)):
            self.records[destination] = Record(bank, row, evicted)
            self.recency.touch(destination)

    def train(self, bank, row, tag, branches, ordinal, align_halfwords, correction):
        touched = []
        rewritten = None
        for slot, record in self.matching(bank, row, tag):
            position = ordinal * align_halfwords + record.entry.position
            entry, counter = record.entry, record.counter
            for branch in branches:
                if branch.position == position and branch.kind == 1:
                    counter = max(0, min(3, counter + (1 if branch.taken else -1)))
                    touched.append(slot)
            if correction is not None and correction.position == record.entry.position and (
                    correction.kind == 3 and correction.action in (0, 2)
                    or (correction.kind, correction.action) != (entry.kind, entry.action)):
                entry, counter, rewritten = correction, 2, slot
            self.records[slot] = replace(record, entry=entry, counter=counter)
        if rewritten is not None or touched:
            self.recency.touch(rewritten if rewritten is not None else min(touched))
