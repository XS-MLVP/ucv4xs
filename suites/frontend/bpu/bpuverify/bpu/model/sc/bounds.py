"""Single logical key per global threshold lane; no physical bank/row matrix."""
from bpuverify.bpu.model.sc.used import INITIAL, MINIMUM, MAXIMUM
from bpuverify.bpu.model.phr.model import path_hash
from bpuverify.bpu.model.sc.training_path import training_indices


def bounds_plan(way, boundary):
    if type(way) is not int or way not in range(4) or boundary not in ('lower','upper'):
        raise ValueError('unknown threshold lane or boundary')
    positions = (way, way ^ 5) if way < (way ^ 5) else (way ^ 5, way)
    pc = 0x40010000 + 1056 * positions[0]
    assert path_hash(pc + positions[0], pc) == 0
    assert all((p & 3) ^ (p >> 2) == way for p in positions)
    # Lower priming uses two genuine not-taken outcomes to establish SC=0;
    # subsequent correct NT feedback is a legal two-branch direction vector.
    start = INITIAL + (2 if boundary == 'lower' else 0)
    near = MINIMUM + 1 if boundary == 'lower' else MAXIMUM - 1
    approach = abs(start-near)
    approach_requests=(approach+1)//2
    return dict(way=way,boundary=boundary,pc=pc,positions=positions,start=start,near=near,
        bound=MINIMUM if boundary=='lower' else MAXIMUM,outward=-1 if boundary=='lower' else 1,
        approach=approach,approach_requests=approach_requests,requests=approach_requests+11,
        initial_sc=int(boundary=='upper'))


def threshold_events(update):
    """Classify qualified votes, not test phases or observation operations.

    A lane with no participating vote is outside this event's scope. Its
    isolation is still checked by the complete four-register comparison.
    """
    events=[]
    for way,(old,new,inc,dec,candidate) in enumerate(zip(update['before'],update['after'],
            update['increments'],update['decrements'],update['candidates'],strict=True)):
        if not inc+dec:
            continue
        if inc==dec:
            rule='cancel-at-lower' if old==MINIMUM else 'cancel-at-upper' if old==MAXIMUM else 'cancel-interior'
        elif candidate<MINIMUM:
            rule='reject-below-at-bound' if old==MINIMUM else 'reject-below-from-interior'
        elif candidate>MAXIMUM:
            rule='reject-above-at-bound' if old==MAXIMUM else 'reject-above-from-interior'
        elif new==MINIMUM:
            rule='enter-lower'
        elif new==MAXIMUM:
            rule='enter-upper'
        elif old==MINIMUM:
            rule='leave-lower'
        elif old==MAXIMUM:
            rule='leave-upper'
        else:
            rule='increase-interior' if inc>dec else 'decrease-interior'
        events.append(dict(way=way,rule=rule,before=old,after=new,
            increments=inc,decrements=dec,candidate=candidate))
    return events


def public_decisions(reference,pc,positions,providers,thresholds,common):
    """Pure SC decision from reset-derived SRAM and explicit prediction inputs."""
    indices=training_indices(pc,0,common)
    result=[]
    for position,provider in zip(positions,providers,strict=True):
        way=(position&3)^(position>>2);counter=provider[2]
        bias=4*way+2*int(counter in (3,4))+int(counter>=4)
        total=0
        for table,index in indices.items():
            lane=bias if table=='biasTable' else way
            memory=reference.memories[f'{table}_bank{pc&1}']
            encoded=0 if table in ('globalTable_0','bwTable_0') and not common['valid'] else (
                memory.get(index,[0]*(16 if table=='biasTable' else 4))[lane])
            signed=encoded-64 if encoded&32 else encoded
            total+=2*signed+1
        shift=4 if counter in (0,7) else 6 if counter in (3,4) else 5
        above=int(abs(total)>(thresholds[way]>>shift))
        result.append((int(total>=0),above,above))
    return tuple(result)
