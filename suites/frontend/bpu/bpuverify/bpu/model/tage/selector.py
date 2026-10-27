"""Selector inputs from genuine FTQ feedback, never observed selector state."""
INITIAL=16
MAXIMUM=31
COUNT=16


def feedback_votes(bits):
    owners=[owner for bank in bits['meta']['mbtb_entries'] for owner in bank]
    metadata=bits['meta']['tage_entries']
    votes=[]
    need_read=False
    for slot,row in enumerate(bits['branches']):
        branch=row['bits']
        conditional=bool(row['valid'] and branch['attribute']['branchType']==1)
        matches=[i for i,owner in enumerate(owners) if owner['rawHit'] and owner['position']==branch['cfiPosition']]
        owner=matches[0] if matches else None
        valid=bool(conditional and owner is not None)
        meta=metadata[owner] if owner is not None else None
        if valid:
            need_read|=bool(branch['mispredict'] or (not meta['useProvider'] and meta['hasAlt']))
        provider=bool(valid and meta['hasProvider'])
        counter=meta['providerTakenCtr_value'] if provider else 0
        index=2*meta['providerTableIdx']+meta['altConf'] if valid else 0
        weak=counter in (3,4)
        disagreement=bool(provider and int(counter>=4)!=meta['altOrBasePred'])
        qualified=bool(provider and weak and disagreement)
        increase=bool(qualified and meta['altOrBasePred']==branch['taken'])
        decrease=bool(qualified and int(counter>=4)==branch['taken'])
        votes.append(dict(slot=slot,valid=int(valid),index=index,inc=int(increase),dec=int(decrease),
            provider=provider,weak=weak,disagreement=disagreement,owner=owner,
            position=branch['cfiPosition'],meta=meta,
            base_counter=owners[owner]['counter_value'] if valid else 0))
    return votes,int(need_read)


def update_selectors(values,votes):
    if len(values)!=COUNT or any(type(v) is not int or not 0<=v<=MAXIMUM for v in values):
        raise ValueError('sixteen unsigned five-bit selector values required')
    inc=[0]*COUNT;dec=[0]*COUNT
    for vote in votes:
        if vote['valid']:
            inc[vote['index']]+=vote['inc'];dec[vote['index']]+=vote['dec']
    after=tuple(max(0,min(MAXIMUM,value+a-b)) for value,a,b in zip(values,inc,dec,strict=True))
    events=[]
    for index,(old,new,a,b) in enumerate(zip(values,after,inc,dec,strict=True)):
        if a+b:
            rule='upper-saturation' if old==new==MAXIMUM and a>b else (
                'lower-saturation' if old==new==0 and b>a else
                'increment' if a>b else 'decrement' if b>a else 'opposed-cancel')
            events.append(dict(rule=rule,index=index,before=old,after=new,increments=a,decrements=b))
    for vote in votes:
        if vote['provider'] and not (vote['inc'] or vote['dec']):
            events.append(dict(rule='strong-provider-suppressed' if not vote['weak'] else 'agreement-suppressed',
                index=vote['index'],slot=vote['slot']))
    return after,events


def read_projection(reads,raw_tags,vote):
    """Training read operands are explicit inputs, not a full SRAM reference."""
    hits=[]
    for table,entries in enumerate(reads):
        ways=[way for way,entry in enumerate(entries)
            if entry['valid'] and entry['tag']==(raw_tags[table]^vote['position'])]
        if ways:
            way=ways[0];hits.append((table,way,entries[way]))
    if not hits:
        return dict(hasProvider=0)
    table,way,entry=hits[-1]
    alternate=hits[-2][2]['counter'] if len(hits)>1 else vote['base_counter']
    return dict(hasProvider=1,providerTableIdx=table,providerWayIdx=way,
        providerTakenCtr_value=entry['counter'],
        hasAlt=int(len(hits)>1),altOrBasePred=int(alternate>=(4 if len(hits)>1 else 2)),
        altConf=int(alternate not in (3,4)) if len(hits)>1 else int(alternate in (0,3)))


def exercise_program():
    """Feedback values establish conditions; these are not settling delays.

    The first pair has provider4/alternate3. Two down/down/up/up excursions
    make the alternate strongly negative. Crossing 16->15 can weaken it once;
    one further excursion restores that source before the monotonic passes.
    """
    yield 'prime-strong-negative-alternate',(0,0,1,1)*2
    yield 'cross-selector-sign',(1,0)*2
    yield 'restore-strong-negative-alternate',(0,0,1,1)
    yield 'lower-saturation',(1,0)*INITIAL
    yield 'upper-sign-crossing',(0,1)*INITIAL
    # At the sign crossing, the restoring taken feedback also trains the
    # newly selected alternate. Re-establish its confidence before continuing
    # to saturate the SAME high-confidence bucket, not a different register.
    yield 'restore-upper-confidence',(0,0,1,1)
    yield 'upper-saturation',(0,1)*(MAXIMUM-INITIAL+1)
