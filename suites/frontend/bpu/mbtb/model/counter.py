"""Bounded two-key counter writeback under same-bank read priority.

Four physical banks, two ways and 64 sets describe this installed MiniConfig.
Each key starts at counter 2. Neither this model nor the trace summarizer is a
general MainBTB reference, overflow model, or entry-buffer replacement model.
"""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy
from dataclasses import replace


def expected_mbtb_counter_activity(align, bank, way, taken, mode, *, sets=(1,2), reads=24):
    if align not in (0, 1) or taken not in (0, 1) or bank not in range(MAIN_BANKS) or way not in range(MAIN_WAYS):
        raise ValueError('counter scenario requires align/bank/way/taken in 0/1')
    if mode not in ('blocked','flow'):
        raise ValueError('counter scenario mode must be blocked or flow')
    if len(sets)!=2 or len(set(sets))!=2 or any(not isinstance(index,int) or not 0<=index<MAIN_ROWS for index in sets):
        raise ValueError('counter scenario needs two distinct 6-bit sets')
    if not isinstance(reads, int) or reads < 4:
        raise ValueError('counter scenario needs a read window covering both requests')
    count = 3 if taken else 1
    requests = tuple({'align':align,'bank':bank,'set_idx':index,'way_mask':1<<way,
                      'counters':tuple(count if index_way==way else None for index_way in range(MAIN_WAYS))}
                     for index in sets)
    blocked = mode=='blocked'
    return {'requests':requests,'writebacks':deepcopy(requests),'input_to_request_ticks':(2,2),
            'request_ready':(1,1),'request_blocked':(int(blocked),)*2,
            'buffered_enqueues':((align,bank),)*2 if blocked else (),
            'peak_occupancy':2 if blocked else 0,'writeback_offsets':(2,4) if blocked else (2,2),
            'read_overlap':True,'lookups':reads,'lookup_cadence_ok':True,
            'lookup_completion_ticks':(4,)*reads}


def expected_mbtb_counter_states(prepared, align, way, taken):
    if len(prepared)!=4 or (align not in (0, 1) or taken not in (0, 1) or way not in range(MAIN_WAYS)):
        raise ValueError('counter states need two targets and two sentinels in the supported geometry')
    states = deepcopy(prepared)
    active = align*(MAIN_WAYS + 1)+way
    for index in (0,1):
        entry = prepared[index]['entries'][active]
        meta = prepared[index]['meta_entries'][align][way]
        if not entry.valid or entry.branch_type!=1 or meta['counter_value']!=2 or not meta['rawHit']:
            raise ValueError('counter target must be a real conditional hit with initial counter 2')
        states[index]['entries'] = tuple(replace(value,taken=taken) if i==active else value
                                        for i,value in enumerate(states[index]['entries']))
        states[index]['meta_entries'][align][way]['counter_value'] = 3 if taken else 1
    return states


def summarize_mbtb_counter_activity(frames, feedback, lookups, mode):
    """Normalize only observed IO/occupancy; do not evaluate the reference."""
    if mode not in ('blocked','flow'):
        raise ValueError('counter activity mode must be blocked or flow')
    requests,writebacks,buffered,occupancies = [],[],[],[]

    def record(align,bank,queue,port):
        mask = queue[port+'_way']
        return {'align':align,'bank':bank,'set_idx':queue[port+'_set'],'way_mask':mask,
                'counters':tuple(value if mask&(1<<way) else None
                                 for way,value in enumerate(queue[port+'_counters']))}

    for frame in frames:
        for align,row in enumerate(frame.value['queues']):
            for bank,queue in enumerate(row):
                occupancies.append(0 if queue['empty'] else MAIN_RETAINED if queue['enq_ptr']==queue['deq_ptr'] else (queue['enq_ptr'] - queue['deq_ptr']) % MAIN_RETAINED)
                if queue['enq_valid']:
                    requests.append((frame.event.tick,record(align,bank,queue,'enq'),
                                     queue['enq_ready'],int(not queue['deq_ready'])))
                if queue['deq_valid'] and queue['deq_ready']:
                    writebacks.append((frame.event.tick,record(align,bank,queue,'deq')))
                if queue['do_enq']:
                    buffered.append((align,bank))
    inputs = tuple(frame.event.tick for frame in feedback)
    accepted = tuple(transfer.accepted_event.tick for transfer in lookups)
    completed = tuple(transfer.completed_event.tick for transfer in lookups)
    return {
        'requests':tuple(value for tick,value,ready,blocked in requests),
        'writebacks':tuple(value for tick,value in writebacks),
        'input_to_request_ticks':tuple(tick-inputs[i] if i<len(inputs) else None
                                      for i,(tick,value,ready,blocked) in enumerate(requests)),
        'request_ready':tuple(ready for tick,value,ready,blocked in requests),
        'request_blocked':tuple(blocked for tick,value,ready,blocked in requests),
        'buffered_enqueues':tuple(buffered),'peak_occupancy':max(occupancies,default=0),
        'writeback_offsets':tuple(tick-accepted[-1] if mode=='blocked' and accepted else
                                  tick-inputs[i] if mode=='flow' and i<len(inputs) else None
                                  for i,(tick,value) in enumerate(writebacks)),
        'read_overlap':bool(accepted) and all(accepted[0]<=tick<=accepted[-1]
                                             for tick,value,ready,blocked in requests),
        'lookups':len(lookups),
        'lookup_cadence_ok':bool(accepted) and accepted==tuple(range(accepted[0],accepted[0]+2*len(accepted),2)),
        'lookup_completion_ticks':tuple(done-start for start,done in zip(accepted,completed,strict=True)),
    }
