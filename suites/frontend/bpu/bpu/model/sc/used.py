"""SC-used input-derived gates, all-table masked writes and threshold votes.

No DUT prestate seeds this reference. A read can be required even when every
table write mask is zero. Full-dirty shadow overwrite remains explicitly open.
"""
from suites.frontend.bpu.models.configuration import *

from copy import deepcopy
from suites.frontend.bpu.bpu.model.sc.model import ScReference
from suites.frontend.bpu.bpu.model.sc.model import width
from suites.frontend.bpu.bpu.model.sc.history import history_indices
SC_BITS = ('scPred', 'tagePred', 'tagePredValid', 'useScPred', 'sumAboveThres')
MINIMUM, MAXIMUM, INITIAL, THRESHOLD_WIDTH = (SC_MIN_THRESHOLD, SC_MAX_THRESHOLD, 1130, 13)

def uint(value, bits, name):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError((name, f'unsigned{bits}-bit integer required'))
    return value

def branch_effects(transaction):
    pc = uint(transaction['pc'], 49, 'pc')
    branches = transaction['branches']
    if not 1 <= len(branches) <= 8:
        raise ValueError('one to eight branch slots required')
    meta = transaction['resolve_meta']
    sc = meta['sc']
    owners = [row for bank in meta['mbtb_entries'] for row in bank]
    if len(owners) != RESULT_SLOTS:
        raise ValueError('exact ten DefaultConfig prediction slots required')
    for name in SC_BITS:
        if len(sc[name]) != RESULT_SLOTS:
            raise ValueError((name, 'ten prediction slots required'))
        for value in sc[name]:
            uint(value, 1, name)
    if len(sc['scBiasLowerBits']) != RESULT_SLOTS:
        raise ValueError('ten bias selectors required')
    for value in sc['scBiasLowerBits']:
        uint(value, 2, 'scBiasLowerBits')
    for owner in owners:
        uint(owner['rawHit'], 1, 'rawHit')
        uint(owner['position'], 5, 'owner_position')
    result = []
    for slot, branch in enumerate(branches):
        if branch is None:
            continue
        position = uint(branch['position'], 5, 'position')
        taken = uint(branch['taken'], 1, 'taken')
        kind = uint(branch['branch_type'], 2, 'branch_type')
        hits = [index for index, owner in enumerate(owners) if owner['rawHit'] and owner['position'] == position]
        index = min(hits) if hits else None
        way = position % SC_WAYS ^ position // SC_WAYS
        qualified = bool(index is not None and kind == 1 and sc['tagePredValid'][index])
        used = sc['useScPred'][index] if index is not None else 0
        predicted = sc['scPred'][index] if index is not None else 0
        tage = sc['tagePred'][index] if index is not None else 0
        above = sc['sumAboveThres'][index] if index is not None else 0
        wrong = taken != predicted
        read = bool(qualified and (not (used and predicted == taken == tage)))
        update = bool(read and (wrong or not above))
        bias = way * 4 + (sc['scBiasLowerBits'][index] if index is not None else 0)
        result.append(dict(slot=slot, prediction_slot=index, position=position, way=way, bias_lane=bias, taken=taken, used=used, sc_pred=predicted, tage_pred=tage, above=above, qualified=qualified, read_eligible=read, counter_update=update, counter_delta=(1 if taken else -1) if update else 0, threshold_delta=(1 if wrong else -1) if update else 0))
    return result

def threshold_update(values, effects):
    if len(values) != SC_WAYS:
        raise ValueError('eight global threshold registers required')
    values = tuple((uint(value, THRESHOLD_WIDTH, 'threshold') for value in values))
    if any((not MINIMUM <= value <= MAXIMUM for value in values)):
        raise ValueError('threshold prior state outside architectural range')
    inc, dec = ([0] * SC_WAYS, [0] * SC_WAYS)
    for effect in effects:
        if effect['counter_update']:
            (inc if effect['threshold_delta'] > 0 else dec)[effect['way']] += 1
    candidates = tuple((max(0, min((1 << THRESHOLD_WIDTH) - 1, old + a - b)) for old, a, b in zip(values, inc, dec, strict=True)))
    rejected = tuple((index for index, value in enumerate(candidates) if not MINIMUM <= value <= MAXIMUM))
    after = tuple((old if index in rejected else candidates[index] for index, old in enumerate(values)))
    return dict(before=values, after=after, increments=tuple(inc), decrements=tuple(dec), candidates=candidates, rejected_ways=rejected)

def used_requests(transaction, memories):
    effects = branch_effects(transaction)
    if not any((effect['read_eligible'] for effect in effects)):
        return {}
    pc, meta = (transaction['pc'], transaction['resolve_meta'])
    common, debug = (meta['commonHR'], meta['sc']['debug'])
    derived = history_indices(pc, common)
    indices = dict(pathTable_0=debug['predPathIdx'][0], pathTable_1=debug['predPathIdx'][1], imliTable=debug['predImliIdx'], biasTable=debug['predBiasIdx'])
    if common['valid']:
        for table, field, index in ((f'{family}_{i}', field, i) for family, field in (('globalTable', 'predGlobalIdx'), ('bwTable', 'predBWIdx')) for i in range(2)):
            if debug[field][index] != derived[table]:
                raise ValueError(('captured real common-history index mismatch', table))
        indices.update(derived)
    result = {}
    for table, index in indices.items():
        uint(index, 7, 'SC table index')
        name = f'{table}_bank{pc & 1}'
        old = memories[name].get(index, [0] * width(name))
        if len(old) != width(name):
            raise ValueError('complete old reference SRAM row required')
        old = [uint(value, 6, 'signed_counter_encoding') for value in old]
        delta = [0] * width(name)
        for effect in effects:
            if effect['counter_update']:
                lane = effect['bias_lane'] if table == 'biasTable' else effect['way']
                delta[lane] += effect['counter_delta']
        data = []
        for value, change in zip(old, delta, strict=True):
            signed = value - 64 if value & 32 else value
            data.append(max(-32, min(31, signed + change)) & 63)
        masks = [int(a != b) for a, b in zip(old, data, strict=True)]
        if any(masks):
            result[name] = dict(set_index=index, masks=masks, data=data)
    return result

class UsedScReference(ScReference):
    """Reuse the complete admitted SRAM/slots transition, not weaker state."""

    def accept(self, tick, transaction):
        if tick + 2 in self.pending:
            raise ValueError('more than one feedback accepted in a cycle')
        requests = used_requests(transaction, self.memories)
        self.pending[tick + 2] = requests
        return deepcopy(requests)

class ThresholdReference:
    """Pure cycle kernel; clock-phase admission requires real native traces."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.values = (INITIAL,) * SC_WAYS
        self.prior_fire = 0
        self.registered_effects = []
        self.prior_write = 0

    def advance(self, transaction, *, t0_fire, reset=0):
        uint(t0_fire, 1, 't0_fire')
        uint(reset, 1, 'reset')
        if reset:
            self.reset()
            return dict(reset=True, after=self.values, t1_fire=0, t1_write_valid=0, t2_write_valid=0)
        effects = branch_effects(transaction)
        old_effects = self.registered_effects if self.prior_fire else []
        update = threshold_update(self.values, old_effects)
        t1_valid = int(any((effect['read_eligible'] for effect in old_effects)))
        result = dict(reset=False, t1_fire=self.prior_fire, t1_write_valid=t1_valid, t2_write_valid=self.prior_write, threshold_update=update, t0_write_valid=[int(any((effect['slot'] == slot and effect['read_eligible'] for effect in effects))) for slot in range(8)], t1_write_valid_vec=[int(any((effect['slot'] == slot and effect['read_eligible'] for effect in old_effects))) for slot in range(8)], before=self.values, after=update['after'])
        self.values = update['after']
        self.prior_fire = t0_fire
        self.prior_write = t1_valid
        if t0_fire:
            self.registered_effects = deepcopy(effects)
        return result
