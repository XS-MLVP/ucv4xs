"""One candidate set from reset and qualified writes; random filter is an input."""
from copy import deepcopy

TABLES=4
WAYS=2
SETS=128
BANKS=4
MAX_FAILURES=255


def empty_set():
    return [[dict(valid=0,tag=0,counter=0,useful=0) for _ in range(WAYS)] for _ in range(TABLES)]


def prediction(cells,pc,position,base,selectors):
    tag=((pc>>9)&8191)^position
    hits=[(t,w,c) for t,table in enumerate(cells) for w,c in enumerate(table) if c['valid'] and c['tag']==tag]
    # Current scenario has unique tags, but choose first way at each history length.
    by_table={}
    for t,w,c in hits:by_table.setdefault(t,(t,w,c))
    providers=list(by_table.values())
    if providers:
        table,way,entry=providers[-1]
        alternate=providers[-2][2]['counter'] if len(providers)>1 else base
        has_alt=int(len(providers)>1)
        conf=int(alternate not in (3,4)) if has_alt else int(base in (0,3))
        use=int(not(entry['counter'] in (3,4) and selectors[2*table+conf]>=16))
        return dict(hasProvider=1,providerTableIdx=table,providerWayIdx=way,
            providerTakenCtr_value=entry['counter'],providerUsefulCtr_value=entry['useful'],
            hasAlt=has_alt,altConf=conf,altOrBasePred=int(alternate>=(4 if has_alt else 2)),useProvider=use)
    return dict(hasProvider=0,providerTableIdx=0,providerWayIdx=0,providerTakenCtr_value=0,
        providerUsefulCtr_value=0,hasAlt=0,altConf=int(base in (0,3)),altOrBasePred=int(base>=2),useProvider=0)


def candidate_masks(cells,meta):
    masks=[]
    for table in cells:
        invalid=sum((not c['valid'])<<w for w,c in enumerate(table))
        weak=sum((c['counter'] in (3,4) and not c['useful'])<<w for w,c in enumerate(table))
        unused=sum((not c['useful'])<<w for w,c in enumerate(table))
        masks.append(invalid or weak or unused)
    longer=((15<< (meta['providerTableIdx']+1))&15) if meta['hasProvider'] else 15
    return masks,sum(bool(mask)<<t for t,mask in enumerate(masks))&longer


def transition(cells,meta,*,pc,position,taken,mispredict,random_mask):
    if meta['hasAlt']:raise ValueError('aging scenario uses independent tags and the real MainBTB base, not tagged alternates')
    before=deepcopy(cells);after=deepcopy(cells)
    provider_direction=int(meta['providerTakenCtr_value']>=4)
    final=provider_direction if meta['useProvider'] else meta['altOrBasePred']
    need=int(bool(mispredict and final!=taken and not(meta['hasProvider'] and meta['providerTableIdx']==3)
        and not(meta['hasProvider'] and not meta['useProvider'] and provider_direction==taken
                    and meta['providerTakenCtr_value'] in (3,4))))
    masks,can=candidate_masks(cells,meta)
    selected=(can&random_mask) or can
    table=(selected&-selected).bit_length()-1 if selected else None
    way=(masks[table]&-masks[table]).bit_length()-1 if table is not None else None
    writes=[[None]*WAYS for _ in range(TABLES)]
    if meta['hasProvider']:
        t,w=meta['providerTableIdx'],meta['providerWayIdx'];entry=after[t][w]
        entry['counter']=max(0,min(7,entry['counter']+(1 if taken else -1)))
        entry['useful']=min(3,entry['useful']+int(provider_direction==taken and provider_direction!=meta['altOrBasePred']))
        writes[t][w]=dict(entry=deepcopy(entry),entry_en=int(entry['counter']!=before[t][w]['counter']),
            useful_en=int(entry['useful']!=before[t][w]['useful']),taken=taken)
        if not(writes[t][w]['entry_en'] or writes[t][w]['useful_en']):writes[t][w]=None
    allocate=int(bool(need and can))
    if allocate:
        entry=dict(valid=1,tag=((pc>>9)&8191)^position,counter=4 if taken else 3,useful=0)
        after[table][way]=entry
        writes[table][way]=dict(entry=deepcopy(entry),entry_en=1,useful_en=1,taken=taken)
    return dict(after=after,need=need,can=can,allocate=allocate,
        table=1<<table if table is not None else 0,way=1<<way if way is not None else 0,writes=writes)


def counter_transition(counter,*,fire,need,can,busy):
    start=int(bool(fire and counter==MAX_FAILURES and not busy))
    after=0 if start else min(MAX_FAILURES,counter+int(bool(fire and need and not can and not busy)))
    return after,start


def clear_step(banks,*,start,ready):
    """Request handshakes advance each bank; start intentionally rewrites row0."""
    result=[]
    for (busy,index),accept in zip(banks,ready,strict=True):
        if start:result.append((1,0))
        elif busy and accept:result.append((0,0) if index==SETS-1 else (1,index+1))
        else:result.append((busy,index))
    return result
