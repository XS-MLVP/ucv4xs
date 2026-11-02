"""Fixed DefaultConfig logical ABI; source and live widths cannot agree wrong."""
from toffee.data import iter_data_leaves,signal_width


def expected_schema():
    fields={'control.enable':1,'lookup.start_pc':50,
        'lookup.s0_fire':1,'lookup.s1_fire':1,'lookup.s2_fire':1,'lookup.s3_fire':1,
        'lookup.victim_taken[0]':1,'lookup.victim_taken[1]':1,
        'training.valid':1,'training.start_pc0':49,'training.start_pc1':49,
        'status.reset_done':1,'status.train_ready':1}
    for slot in range(8):
        for name,width in dict(valid=1,target=49,taken=1,position=5,branch_type=2,ras_action=2,mispredict=1).items():
            fields[f'training.branches[{slot}].{name}']=width
    for slot in range(10):
        fields[f'prediction.entries[{slot}].valid']=1
        for name,width in {'taken':1,'target_addr':50,'cfiPosition':5,
                'attribute.branchType':2,'attribute.rasAction':2}.items():
            fields[f'prediction.entries[{slot}].bits.{name}']=width
    for role,ways in (('training',4),('prediction',5)):
        for align in range(2):
            for way in range(ways):
                leaves={'rawHit':1,'position':5,'counter_value':2}
                if way<4:leaves.update({'attribute.branchType':2,'attribute.rasAction':2})
                for name,width in leaves.items():fields[f'{role}.meta_entries[{align}][{way}].{name}']=width
    return fields


def validate_schema(actual):
    expected=expected_schema()
    missing=sorted(set(expected)-set(actual));extra=sorted(set(actual)-set(expected))
    wrong={name:(width,actual[name]) for name,width in expected.items()
        if name in actual and (type(actual[name]) is not int or actual[name]!=width)}
    if missing or extra or wrong:
        raise ValueError(f'MainBTB DefaultConfig ABI differs: missing={missing}, extra={extra}, widths={wrong}')


def validate_binding(ports):
    actual={}
    for role in ('control','lookup','training','prediction','status'):
        binding=getattr(ports,role)
        actual.update({name:signal_width(leaf) for name,leaf in iter_data_leaves(binding.bits,role)})
    actual['training.valid']=signal_width(ports.training.valid)
    validate_schema(actual)
