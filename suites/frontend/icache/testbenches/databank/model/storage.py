"""Whole-word SRAM storage and independent declared-input ancestry.

Functional writes pack data/code plus a zero pad bit; MBIST sees every one of
the 66 bits. There is no expected value derived from a DUT response.
"""
from suites.frontend.icache.testbenches.databank.transactions.types import StorageOrigin


class BankStorage:
    def __init__(self, *, reset_uid=0, epoch=0, tick=0):
        self.words = [[0] * 4 for _ in range(256)]
        self.known = [0] * 256
        self.origins = [[StorageOrigin(reset_uid, epoch, 'uninitialized', tick, index, way)
                         for way in range(4)] for index in range(256)]

    def write(self, index, mask, word, *, uid, epoch, tick, kind):
        for way in range(4):
            if mask >> way & 1:
                self.words[index][way] = word
                self.origins[index][way] = StorageOrigin(uid, epoch, kind, tick, index, way)
                self.known[index] |= 1 << way

    def read(self, indices):
        return tuple(self.words[index][way] for way, index in enumerate(indices))

    def sources(self, indices):
        return tuple(self.origins[index][way] for way, index in enumerate(indices))

    def known_mask(self, indices):
        return sum((self.known[index] & (1 << way)) for way, index in enumerate(indices))
