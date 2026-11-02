"""Independent69-bit word and validity histories; MBIST never creates validity."""
from suites.frontend.icache.metabank.transaction.types import MetaOrigin, MetaBankWay
from suites.frontend.icache.models.sram_word import KnownWord


class MetaStorage:
    def __init__(self, uid=0, epoch=0, tick=0):
        self.words = [[0] * 4 for _ in range(128)]
        self.known = [0] * 128
        self.valid = [0] * 128
        self.memory_sources = [[MetaOrigin(uid, epoch, 'uninitialized', tick, index, way) for way in range(4)]
                               for index in range(128)]
        self.validity_sources = [list(row) for row in self.memory_sources]

    def write(self, index, mask, words, *, uid, epoch, tick, kind):
        for way in range(4):
            if mask >> way & 1:
                self.words[index][way] = words[way]
                self.memory_sources[index][way] = MetaOrigin(uid, epoch, kind, tick, index, way)
                self.known[index] |= 1 << way

    def reset_validity(self, *, uid, epoch, tick):
        self.valid = [0] * 128
        self.validity_sources = [[MetaOrigin(uid, epoch, 'reset', tick, index, way) for way in range(4)]
                                 for index in range(128)]

    def validate(self, index, mask, *, uid, epoch, tick):
        self.valid[index] |= mask
        for way in range(4):
            if mask >> way & 1:
                self.validity_sources[index][way] = MetaOrigin(uid, epoch, 'write', tick, index, way)

    def flush(self, *, uid, epoch, tick):
        self.valid = [0] * 128
        self.validity_sources = [[MetaOrigin(uid, epoch, 'flush', tick, index, way) for way in range(4)]
                                 for index in range(128)]

    def read(self, index):
        return tuple(MetaBankWay.from_word((self.valid[index] >> way) & 1, word)
                     for way, word in enumerate(self.words[index]))

    def macro_word(self, index, group):
        return self.words[index][group * 2] | (self.words[index][group * 2 + 1] << 69)

    def macro_sample(self, index, group):
        mask = sum(((1 << 69) - 1) << (position * 69) for position in range(2)
                   if self.known[index] >> (group * 2 + position) & 1)
        return KnownWord(self.macro_word(index, group), mask)
