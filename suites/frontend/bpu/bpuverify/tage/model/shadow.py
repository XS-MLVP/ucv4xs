"""Bounded TAGE retained-owner counter transitions, not a full TAGE model.

The highest-table buffer has four banks, two owner rows and four depths.
A write hits by (set, tag), independently of the requesting physical way.
Counter updates use the retained value and saturate, not the metadata-derived
counter in the request. SRAM drain precedes writes; a same-slot update wins.
Full-row miss/PLRU overwrite and multiple simultaneous writes are outside this
single-write reference. No mapped coverage point is waived by this model.
"""
from bpuverify.common.model.configuration import *
from copy import deepcopy


SLOT_FIELDS = ('valid', 'dirty', 'set_idx', 'tag', 'entry_valid', 'counter')
WRITE_FIELDS = ('set_idx', 'tag', 'entry_valid', 'counter', 'taken')


def _integer(value, maximum):
    return isinstance(value, int) and 0 <= value <= maximum


def _validate_banks(banks):
    if len(banks) != 4 or any(len(bank) != 2 or any(len(row) != 4 for row in bank) for bank in banks):
        raise ValueError('TAGE shadow reference requires four banks, two owners, four depths')
    for bank in banks:
        for row in bank:
            for slot in row:
                if (set(slot) != set(SLOT_FIELDS)
                    or any(not _integer(slot[field], limit) for field, limit in (
                        ('valid', 1), ('dirty', 1), ('set_idx', TAGE_ROWS - 1), ('tag', 8191),
                        ('entry_valid', 1), ('counter', 7)))
                    or slot['dirty'] > slot['valid']):
                    raise ValueError('invalid TAGE shadow slot')


def advance_tage_shadow(banks, read_ready, *, bank=None, port=None, write=None):
    """Return a new full shadow snapshot after one cycle and one optional write.

    ``banks`` is a previously qualified starting state, never an observed
    post-write result. ``read_ready`` describes this cycle's arbitration.
    The caller independently freezes request payloads before driving them.
    A new miss can reuse a clean slot, preferring the same set; an unsupported
    full miss is rejected rather than inventing a PLRU outcome.
    """
    _validate_banks(banks)
    if (len(read_ready) != 4 or any(len(row) != 2 or any(not _integer(v, 1) for v in row)
                                  for row in read_ready)):
        raise ValueError('TAGE read-ready reference requires four pairs of bits')
    if write is None:
        if bank is not None or port is not None:
            raise ValueError('bank/port require a write payload')
    elif (not _integer(bank, 3) or not _integer(port, 1)
          or set(write) != set(WRITE_FIELDS)
          or any(not _integer(write[field], limit) for field, limit in (
              ('set_idx', TAGE_ROWS - 1), ('tag', 8191), ('entry_valid', 1), ('counter', 7), ('taken', 1)))):
        raise ValueError('invalid TAGE single-write request')
    after = deepcopy(banks)
    for bank_idx, owners in enumerate(banks):
        for owner, row in enumerate(owners):
            dirty = [depth for depth, slot in enumerate(row) if slot['dirty']]
            if dirty and read_ready[bank_idx][owner]:
                after[bank_idx][owner][dirty[0]]['dirty'] = 0
    owner = depth = None
    if write is not None:
        hits = [(owner, depth) for owner, row in enumerate(banks[bank]) for depth, slot in enumerate(row)
                if slot['valid'] and (slot['set_idx'], slot['tag']) == (write['set_idx'], write['tag'])]
        if len(hits) > 1:
            raise ValueError('ambiguous TAGE retained key')
        if hits:
            owner, depth = hits[0]
            old = banks[bank][owner][depth]['counter']
            counter = min(7, old+1) if write['taken'] else max(0, old-1)
        else:
            owner = port
            same_set = [index for index, slot in enumerate(banks[bank][owner])
                        if slot['valid'] and slot['set_idx'] == write['set_idx']]
            if len(same_set) > 1:
                raise ValueError('ambiguous TAGE same-set victim')
            clean = [index for index, slot in enumerate(banks[bank][owner]) if not slot['dirty']]
            if not same_set and not clean:
                raise ValueError('full-row miss/PLRU overwrite is outside the bounded reference')
            depth = same_set[0] if same_set else clean[0]
            counter = write['counter']
        after[bank][owner][depth].update(valid=1, dirty=1, set_idx=write['set_idx'],
            tag=write['tag'], entry_valid=write['entry_valid'], counter=counter)
    return {'banks': after, 'owner': owner, 'depth': depth}


def expected_tage_cross_owner_writes(pc, target, origin, prefix):
    """Freeze highest-table payloads: prime current way, then replay old way.

    Prefix providers must be genuine counter-6 residents in the destination
    way at distinct same-bank sets. The target migrated from original way
    counter 5 to destination way counter 4. All feedback is correct taken,
    with taken base prediction, so it does not increment any useful counter.
    """
    if (not isinstance(pc, int) or pc < 0 or not _integer(target, 2 * TAGE_TABLES)
        or not _integer(origin, 1) or len(prefix) > 3):
        raise ValueError('unsupported TAGE cross-owner scenario')
    prefix = tuple(prefix)
    if (any(not isinstance(address, int) or address < 0 or address & 3 != pc & 3
            or not _integer(position, 2 * TAGE_TABLES) for address, position in prefix)
        or len({(address >> 2) & (TAGE_ROWS - 1) for address, _ in prefix} | {(pc >> 2) & (TAGE_ROWS - 1)}) != len(prefix)+1):
        raise ValueError('prefix needs distinct same-bank sets')
    requests = tuple((address, position, 1-origin, 7) for address, position in prefix)+(
        (pc, target, 1-origin, 5),)+(tuple((pc, target, origin, 6) for _ in range(3)))
    frames = []
    for address, position, port, counter in requests:
        banks = [[None, None] for _ in range(4)]
        banks[address & 3][port] = dict(set_idx=(address >> 2) & (TAGE_ROWS - 1),
            tag=((address >> 11) & 8191) ^ position, counter=counter, entry_valid=1, taken=1)
        frames.append(tuple(tuple(bank) for bank in banks))
    return tuple(frames)
