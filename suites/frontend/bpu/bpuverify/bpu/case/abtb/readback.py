"""Synchronous SRAM observation association; no driving and no DUT-seeded model."""
from copy import deepcopy


def matching_sram_readbacks(records, *, bank, entry_set, expected_entry, begin_tick, end_tick):
    if type(bank) is not int or not 0 <= bank < 4:
        raise ValueError('physical bank must be an integer in [0,4)')
    if type(entry_set) is not int or not 0 <= entry_set < 64:
        raise ValueError('physical set must be an integer in [0,64)')
    if not (type(begin_tick) is type(end_tick) is int and 0 <= begin_tick < end_tick):
        raise ValueError('invalid alias observation window')
    if not records:
        raise ValueError('complete monitor trace is required')
    # The static monitor captures preedge then rising, with continuous event
    # ticks. Validate rather than silently dropping gaps or borrowing held data.
    previous = None
    for row in records:
        if type(row['tick']) is not int or row['tick'] <= 0:
            raise ValueError('invalid observation tick')
        if row['phase'] not in ('preedge', 'rising'):
            raise ValueError('unknown observation phase')
        if previous is not None and (row['tick'] != previous['tick'] + 1
                or row['phase'] == previous['phase']):
            raise ValueError('monitor trace must be continuous and alternating')
        previous = row
    if records[0]['tick'] != 1 or records[0]['phase'] != 'preedge' or end_tick > records[-1]['tick']:
        raise ValueError('trace must contain reset epoch and the whole alias window')
    result = []
    for request, response in zip(records, records[1:]):
        if request['phase'] != 'preedge':
            continue
        if not begin_tick < request['tick'] < response['tick'] <= end_tick:
            continue
        if request['value']['reset'] or response['value']['reset']:
            continue
        read = request['value']['banks'][bank]['read_input']
        if not read['valid'] or read['set_index'] != entry_set:
            continue
        # Response-side request pins can already describe a different request.
        # Read identity comes exclusively from the originating preedge request.
        for way, entry in enumerate(response['value']['banks'][bank]['sram']['read']):
            if entry == expected_entry:
                result.append(dict(tick=response['tick'], request_tick=request['tick'],
                    response_tick=response['tick'], bank=bank, set_index=entry_set,
                    way=way, entry=deepcopy(entry)))
    return result
