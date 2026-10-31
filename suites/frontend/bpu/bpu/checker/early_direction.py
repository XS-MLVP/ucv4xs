"""Only independently defined fields gate comparisons, never observed hits."""


def metadata_values(expected,actual):
    return {key:actual['entries'][int(key.split('.')[0])][key.split('.')[1]] if '.' in key else tuple(actual[key])
        for key in expected if key not in ('hits','meta_valid') and not key.endswith('.taken')}


def live_values(sources,enabled,actual):
    if len(actual['useful'])!=2 or any(len(table)!=512 for table in actual['useful']):
        raise ValueError('independent MicroTAGE state checking requires both complete 512-cell useful vectors')
    prediction=sources.current_short(enabled);values=prediction.values()
    wanted={key:value for key,value in values.items() if key not in ('hits','meta_valid') and not key.endswith('.taken')}
    observed=metadata_values(wanted,actual['meta'])
    providers=prediction.frame.providers() if prediction.frame is not None else (None,)*4
    active=enabled and sources.ahead.frame is not None and sources.ahead.frame.valid
    if active:
        # Raw lanes affect source arbitration only with an owned Ahead beat.
        # A disabled Main repair can change naked hit registers without an
        # enabled MicroTAGE request/payload; those bits are not a response.
        wanted['raw_hits']=tuple(int(provider is not None) for provider in providers)
        observed['raw_hits']=tuple(actual['hits'])
    # Useful state is independently owned, including untouched cells. Seeing
    # an expected learning effect is not proof that the hardware applied it.
    # Zero is the fixed reset/default for every one of these 1,024 cells.
    # Encode BOTH full vectors sparsely, independently: an unexpected actual
    # nonzero remains an extra key and cannot disappear behind expected gates.
    wanted['useful_nonzero']={f'{table}.{index}':value for table,values in enumerate(sources.short.useful)
        for index in range(512) if (value:=values.get(index,0))}
    observed['useful_nonzero']={f'{table}.{index}':value for table,values in enumerate(actual['useful'])
        for index,value in enumerate(values) if value}
    for way,provider in enumerate(providers):
        if active and provider is not None:
            key=f'{way}.correction'
            wanted[key]=int(prediction.frame.read.entries[provider].counter>=4)
            observed[key]=actual['taken'][way]
    return wanted,observed


def fast_values(sources,cycle,actual):
    token,choice=cycle.tokens[2],cycle.decisions[2]
    wanted=dict(valid=int(token is not None));observed=dict(valid=actual['valid'])
    if token is not None:
        branch=choice.branch
        values=sources.defined_short_metadata(token)
        wanted.update(pc=token.pc,position=branch.position,taken=int(branch.taken),kind=int(branch.kind),
            meta={key:value for key,value in values.items() if key not in ('hits','meta_valid') and not key.endswith('.taken')})
        observed.update({key:actual[key] for key in ('pc','position','taken','kind')})
        observed['meta']=metadata_values(wanted['meta'],actual['meta'])
    return wanted,observed
