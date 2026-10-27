"""Semantic path words and owned checkpoints for BPU composition.

Not a PHR register model: there are no cells, pending masks, ports or sampled
metadata inputs. This is the logical contract needed by a composed predictor.
Physical circular-storage lifetime and cycle scheduling are separate duties.
Addresses are the integrated driver's halfword address units.
"""
from bpuverify.common.model.configuration import *

from dataclasses import dataclass


LAYOUT = PHR_FOLDS
WIDTH, LOW_WIDTH, SHIFT = PHR_STORAGE_BITS, 13, 2


def address(value):
    if type(value) is not int or not 0 <= value < 1 << 49:
        raise ValueError('path-history address must fit the halfword PC contract')


def path_contribution(pc, target):
    address(pc)
    address(target)
    # Build the two independent address contributions, not an RTL wire tree.
    return ((pc % 512) * 16) ^ ((target // 2) % 32768)


@dataclass(frozen=True, slots=True)
class Checkpoint:
    sequence: int
    history: int
    taken_edges: int

    def metadata(self):
        cursor = (-SHIFT * self.taken_edges) % (2 * WIDTH)
        return dict(phrPtr=dict(flag=cursor // WIDTH, value=cursor % WIDTH),
                    phrLowBits=self.history % (1 << LOW_WIDTH))

    def folds(self):
        return tuple(sum((sum((self.history >> position) & 1
            for position in range(bit, length, width)) % 2) << bit
            for bit in range(width)) for length, width in LAYOUT)


class PathHistoryReference:
    def __init__(self):
        self.history = self.taken_edges = self.sequence = 0
        self.owned = {}

    def reset(self):
        self.history = self.taken_edges = 0
        self.owned.clear()

    def checkpoint(self):
        checkpoint = Checkpoint(self.sequence, self.history, self.taken_edges)
        self.sequence += 1
        self.owned[checkpoint.sequence] = checkpoint
        return checkpoint

    def retire(self, checkpoint):
        if type(checkpoint) is not Checkpoint or self.owned.get(checkpoint.sequence) is not checkpoint:
            raise ValueError('retirement requires an owned history checkpoint')
        del self.owned[checkpoint.sequence]

    def advance(self, *, taken, cfi_pc, target, restore=None):
        if type(taken) is not bool:
            raise ValueError('path-history direction must be a semantic bool')
        address(cfi_pc)
        address(target)
        if restore is not None and (type(restore) is not Checkpoint or self.owned.get(restore.sequence) is not restore):
            raise ValueError('restore requires a checkpoint owned by this reset epoch')
        history = self.history if restore is None else restore.history
        count = self.taken_edges if restore is None else restore.taken_edges
        if taken:
            history = ((history * 4) ^ path_contribution(cfi_pc, target)) % (1 << WIDTH)
            count += 1
        self.history, self.taken_edges = history, count
        return self.checkpoint()
