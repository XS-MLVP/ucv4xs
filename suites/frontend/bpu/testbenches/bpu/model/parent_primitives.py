"""Independent parent contracts: fetch extent and a two-edge CSR delay.

Fetch extent is bounded by 64 bytes, 32-byte alignment and a 4KiB page. Arithmetic
is expressed in halfwords, including the full 50-bit guarded address modulus.
No sampled predictor result, register or delayed output seeds this reference.
"""
from collections import deque

from suites.frontend.bpu.testbenches.bpu.model.configuration import ALIGN_HALFWORDS
from suites.frontend.bpu.testbenches.bpu.model.configuration import FETCH_BYTES

ENABLES = ('ubtb', 'abtb', 'mbtb', 'tage', 'sc', 'ittage', 'ras')


def fetch_extent(pc):
    if type(pc) is not int or not 0 <= pc < 1 << 50:
        raise ValueError('fallthrough PC requires an unsigned 50-bit halfword')
    aligned = (pc // ALIGN_HALFWORDS) * ALIGN_HALFWORDS
    next_block = aligned + FETCH_BYTES // 2
    next_page = (pc // 2048 + 1) * 2048
    successor = min(next_block, next_page)
    return dict(target=successor % (1 << 50), position=successor - aligned - 1)


class ParentPrimitiveReference:
    def __init__(self):
        self.controls = deque(maxlen=2)
        self.lookup_pc = None

    def accept(self, controls, *, fire, pc):
        if (set(controls) != set(ENABLES) or any(type(value) is not int or value not in (0, 1)
                                               for value in controls.values())):
            raise ValueError('complete seven-bit CSR input required')
        if type(fire) is not int or fire not in (0, 1):
            raise ValueError('S0 fire must be a bit')
        # Each sampled clock advances the delay, even while reset is asserted;
        # DelayN has no reset input. Do not reset it along with the predictors.
        self.controls.append(dict(controls))
        result = {}
        if len(self.controls) == 2:
            delayed = self.controls[0]
            result['delayed'] = dict(delayed)
            result['enabled'] = dict(delayed,
                **{name: delayed[name] & delayed['mbtb'] for name in ('tage', 'sc', 'ittage', 'ras')},
                utage=delayed['abtb'])
        if fire:
            self.lookup_pc = pc
        if self.lookup_pc is not None:
            result['fallthrough'] = fetch_extent(self.lookup_pc)
        return result
