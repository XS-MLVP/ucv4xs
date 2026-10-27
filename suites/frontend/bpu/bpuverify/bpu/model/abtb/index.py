"""Independent ABTB normal/hold/S2/S3 index tokens; no DUT state seeding."""
from copy import deepcopy


class IndexReference:
    def __init__(self, *, address_shift=1):
        self.address_shift = address_shift
        self.initialized = False
        self.a1 = self.s2 = self.replay = None
        self.s1_valid = self.s2_valid = self.replay_valid = False

    def token(self, pc, folded6, tick):
        index = ((pc << self.address_shift) & 255) ^ (folded6 & 15)
        return dict(pc=pc, folded6=folded6, source_tick=tick,
            bank=index & 3, entry_set=index >> 2, mode='normal')

    def check(self, meta, enabled):
        if not self.initialized:
            return False
        valid = int(bool(enabled and self.s2_valid))
        assert meta['valid'] == valid, ('ABTB_index_valid', valid, meta['valid'])
        if valid:
            assert self.s2 is not None, 'valid ABTB output lacks reset-derived index source'
            assert meta['setIdx'] == self.s2['entry_set'], ('ABTB_index_set', self.s2, meta['setIdx'])
            assert meta['bankMask'] == 1 << self.s2['bank'], ('ABTB_index_bank', self.s2, meta['bankMask'])
        return bool(valid)

    def advance(self, *, reset, enable, fire0, fire1, fire2, s2_override, s3_override,
                redirect, pc, folded6, tick):
        a1, s2, replay = deepcopy((self.a1, self.s2, self.replay))
        old1, old2, old_replay = self.s1_valid, self.s2_valid, self.replay_valid
        active = bool(enable and fire0)
        if active:
            # The index registers are RegEnable, not RegInit.
            self.a1 = self.token(pc, folded6, tick)
        if reset:
            self.initialized = True
            self.s1_valid = self.s2_valid = self.replay_valid = False
            self.s2 = self.replay = None
            return
        if not self.initialized:
            return
        s2_fire = bool(old2 and fire1 and not (s2_override or s3_override or redirect))
        ready = bool(s2_fire or not old2 or s2_override or s3_override or redirect)
        s1_fire = bool(enable and old1 and ready and fire0)
        if s1_fire or s2_override or s3_override:
            selected = replay if s3_override else s2 if s2_override else a1
            self.s2 = deepcopy(selected)
            if self.s2 is not None:
                self.s2['mode'] = 'S3_override' if s3_override else 'S2_override' if s2_override else 'normal'
        if not enable or redirect:
            self.s2_valid = False
        elif s3_override:
            self.s2_valid = old_replay
        elif s1_fire and not s2_override:
            self.s2_valid = True
        elif s2_fire:
            self.s2_valid = False
        if not enable:
            self.s1_valid = False
        elif active:
            self.s1_valid = True
        elif redirect or s1_fire:
            self.s1_valid = False
        if not enable or redirect or s3_override:
            self.replay_valid = False
        elif fire2:
            self.replay_valid = old2
            self.replay = deepcopy(s2)


def control(**changes):
    result = dict(reset=0, enable=1, fire0=1, fire1=1, fire2=1,
        s2_override=0, s3_override=0, redirect=0, pc=0x40010003, folded6=10, tick=0)
    result.update(changes)
    return result


def primed():
    model = IndexReference()
    model.advance(**control(reset=1, pc=0x40010001, tick=0))
    model.advance(**control(pc=0x40010002, tick=1))
    model.advance(**control(pc=0x40010003, tick=2))
    return model
