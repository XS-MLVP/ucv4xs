"""Project independently defined Ahead fields, never use actual validity gates."""


def metadata_values(expected,actual):
    return {key:actual['entries'][int(key.split('.')[0])][key.split('.')[1]] if '.' in key else actual[key]
        for key in expected}


def live_values(sources,enabled,actual):
    wanted=sources.ahead.values(enabled);observed={}
    for key,value in tuple(wanted.items()):
        if '.' not in key:
            observed[key]=actual['meta']['valid'] if key=='meta_valid' else actual['meta'][key]
            continue
        way,field=key.split('.');way=int(way)
        if field=='micro_valid':observed[key]=actual['micro'][way]['valid']
        elif field=='meta_hit':observed[key]=actual['meta']['entries'][way]['hit']
        elif field=='target_low':observed[key]=actual['meta']['entries'][way]['target_low']
        elif field=='strong':observed[key]=actual['micro'][way]['strong']
        else:observed[key]=actual['entries'][way][field]
    for way in range(4):
        if f'{way}.target_low' not in wanted:continue
        for field in ('position','kind','action'):
            wanted[f'{way}.meta_{field}']=wanted[f'{way}.{field}']
            observed[f'{way}.meta_{field}']=actual['meta']['entries'][way][field]
        for field in ('taken','kind'):
            wanted[f'{way}.micro_{field}']=wanted[f'{way}.{field}']
            observed[f'{way}.micro_{field}']=actual['micro'][way][field]
    return wanted,observed


def fast_values(sources,cycle,actual):
    third,choice=cycle.tokens[2],cycle.decisions[2]
    wanted=dict(valid=int(third is not None));observed=dict(valid=actual['valid'])
    if third is not None:
        branch=choice.branch
        wanted.update(pc=third.pc,target=branch.target,taken=int(branch.taken),position=branch.position,
            kind=int(branch.kind),action=int(branch.action),meta=sources.defined_metadata(third))
        observed.update({key:actual[key] for key in ('pc','target','taken','position','kind','action')})
        observed['meta']=metadata_values(wanted['meta'],actual['meta'])
    return wanted,observed
