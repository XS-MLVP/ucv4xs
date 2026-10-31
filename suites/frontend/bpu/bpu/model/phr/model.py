"""Independent DefaultConfig circular-cell circular-history reference; never reads observed state."""
from suites.frontend.bpu.models.configuration import *

from copy import deepcopy

LENGTH = PHR_STORAGE_BITS
MASK = (1 << LENGTH) - 1
LOW = (1 << 13) - 1
LAYOUT = PHR_FOLDS


def fold(history, length, width):
    # XOR complete width-bit chunks, including the partial most-significant
    # chunk. This is the same polynomial fold as the per-bit definition.
    result, remaining, mask = 0, history & ((1 << length) - 1), (1 << width) - 1
    while remaining:
        result ^= remaining & mask
        remaining >>= width
    return result


def folds(history):
    return [fold(history, length, width) for length, width in LAYOUT]


def subtract(pointer, amount):
    value = pointer['value']
    if value not in range(LENGTH) or pointer['flag'] not in (0, 1):
        raise ValueError(f'invalid PHR pointer {pointer!r}')
    return dict(value=(value - amount) % LENGTH, flag=pointer['flag'] ^ int(value < amount))


def path_hash(pc, target):
    return (((pc & 511) << 4) ^ (target >> 1)) & ((1 << 15) - 1)


class BpuPhrReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.meta2 = dict(pointer=dict(flag=0, value=0), low=0)
        self.meta3 = deepcopy(self.meta2)
        self.state = dict(cells=[0] * LENGTH, pointer=dict(flag=0, value=0),
            s1_pointer=dict(flag=0, value=0), pending=dict(valid=0, taken=0, low=0, shift=0),
            fold0_reg=[0] * len(LAYOUT), fold1=[0] * len(LAYOUT), fold2=[0] * len(LAYOUT), fold3=[0] * len(LAYOUT))

    def physical_read(self, pointer):
        cells = self.state['cells']
        return sum(cells[(pointer['value'] + 1 + bit) % LENGTH] << bit for bit in range(LENGTH))

    def logical(self):
        state, pending = self.state, self.state['pending']
        history = self.physical_read(state['pointer'])
        if pending['valid']:
            width = 15 if pending['taken'] else 13
            bits = (pending['low'] << 2) | pending['shift'] if pending['taken'] else pending['low']
            history = (history & ~((1 << width) - 1)) | bits
        return history

    def advance(self, boundary, reset):
        if reset:
            self.reset()
            return
        previous = self.state
        result = deepcopy(previous)
        logical = self.logical()
        for stage, expected in (('s2', self.meta2), ('s3', self.meta3)):
            if boundary[stage]['valid'] and boundary[stage]['meta'] != expected:
                raise AssertionError(dict(point='pipeline metadata association', stage=stage,
                    expected=expected, actual=boundary[stage]['meta']))
        requests = {}
        for stage in ('s1', 's2', 's3'):
            row = boundary[stage]
            prediction = row['prediction']
            requests[stage] = dict(valid=row['valid'], taken=prediction['taken'],
                cfi_pc=(row['start_pc'] // ALIGN_HALFWORDS * ALIGN_HALFWORDS) + prediction['position'], target=prediction['target'],
                meta=dict(pointer=previous['s1_pointer'], low=logical & LOW) if stage == 's1'
                    else deepcopy(self.meta2 if stage == 's2' else self.meta3))
        requests['redirect'] = boundary['redirect']
        winner = next((stage for stage in ('redirect', 's3', 's2', 's1') if requests[stage]['valid']), None)
        selected_folds = previous['fold0_reg']
        pointer = previous['pointer']
        if winner is not None:
            row = requests[winner]
            pointer = subtract(row['meta']['pointer'], 2 * row['taken'])
            if winner != 's1' or row['taken']:
                # S1 consumes the complete logical view, including all fifteen
                # pending taken bits; restoring only the thirteen metadata low
                # bits would drop pending bits13/14 before the next shift.
                history = logical if winner == 's1' else (
                    (self.physical_read(row['meta']['pointer']) & ~LOW) | row['meta']['low'])
                if row['taken']:
                    history = ((history << 2) ^ path_hash(row['cfi_pc'], row['target'])) & MASK
                selected_folds = folds(history)
        result['pointer'] = pointer
        # Physical history commits the previous pending word, unless redirect
        # replaces that write with its historical pointer/low bits immediately.
        pending = previous['pending']
        if winner == 'redirect':
            row = requests['redirect']
            taken = row['taken']
            hash_value = path_hash(row['cfi_pc'], row['target'])
            low = row['meta']['low'] ^ (hash_value >> 2) if taken else row['meta']['low']
            bits, write_pointer = ((low << 2) | (hash_value & 3) if taken else low), pointer
            width = 15 if taken else 13
        elif pending['valid']:
            bits = ((pending['low'] << 2) | pending['shift']) if pending['taken'] else pending['low']
            write_pointer, width = previous['pointer'], 15 if pending['taken'] else 13
        else:
            bits, write_pointer, width = 0, previous['pointer'], 0
        for bit in range(width):
            result['cells'][(write_pointer['value'] + bit + 1) % LENGTH] = (bits >> bit) & 1
        pending_winner = winner if winner in ('s2', 's3') or winner == 's1' and requests['s1']['taken'] else None
        result['pending']['valid'] = int(pending_winner is not None)
        if pending_winner is not None:
            row = requests[pending_winner]
            hash_value = path_hash(row['cfi_pc'], row['target'])
            result['pending'].update(taken=row['taken'],
                low=row['meta']['low'] ^ ((hash_value >> 2) if row['taken'] else 0),
                shift=hash_value & 3)
        if not boundary['stall']:
            result['fold0_reg'] = list(selected_folds)
        if boundary['fire0']:
            result['s1_pointer'] = dict(pointer)
            result['fold1'] = list(selected_folds)
        if boundary['fire1']:
            result['fold2'] = list(previous['fold1'])
        if boundary['fire2']:
            result['fold3'] = list(previous['fold2'])
        old_meta2 = deepcopy(self.meta2)
        if boundary['fire1']:
            self.meta2 = dict(pointer=deepcopy(previous['s1_pointer']), low=logical & LOW)
        if boundary['fire2']:
            self.meta3 = old_meta2
        self.state = result
