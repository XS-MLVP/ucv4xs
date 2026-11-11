"""MiniConfig geometry and independent qualified-feedback/maintenance rules."""
SETS=(128,128,256)  # Configs.scala:256/256/512 rows, two banks per table.
BANKS=2
MAX_TICK=255
USEFUL_MASK=2  # Packed IttageEntry: padding bit0, useful bit1; all other bits preserved.
ENTRY_MASK=(1<<36)-1  # valid1/tag7/confidence2/offset19/pointer4/usePc1/useful1/padding1.


def qualified(value):
    branch,=value['branches'];meta=value['resolve_meta']['ittage']
    excluded=bool(meta['provider']['valid'] and meta['providerCnt_value']==0
        and meta['providerTarget_addr']==branch['target'])
    return bool(branch['mispredict'] and not excluded)


def tick_step(counter,value):
    if counter==MAX_TICK:return 0,'saturation-reset'
    if value is None:return counter,None
    meta=value['resolve_meta']['ittage'];branch,=value['branches']
    if qualified(value):
        return (max(0,counter-1),'decrement') if meta['allocate']['valid'] else (counter+1,'increment')
    excluded=bool(branch['mispredict'] and meta['provider']['valid'] and meta['providerCnt_value']==0
        and meta['providerTarget_addr']==branch['target'])
    return counter,'correct-unconfident-suppressed' if excluded else 'correct-update-suppressed'


def table_step(busy,index,*,request,update,start,sets):
    advance=bool(busy and not(request or update))
    return (int(bool(start or (busy and not(advance and index==sets-1)))),
        (index+int(advance))%sets)


def write_plan(value):
    result=[None]*len(SETS)
    if value is None:return result
    meta=value['resolve_meta']['ittage'];branch,=value['branches'];target=branch['target']
    def update(table,old,*,allocate=False,useful_valid=False,useful=0,correct=False):
        result[table]=dict(pc=value['pc'],allocate=int(allocate),old_counter=old,
            correct=int(correct),useful_valid=int(useful_valid),useful=useful)
    if meta['provider']['valid']:
        if meta['altProvider']['valid'] and meta['providerCnt_value']==0 and branch['mispredict']:
            update(meta['altProvider']['bits'],meta['altProviderCnt_value'])
        correct=meta['providerTarget_addr']==target
        update(meta['provider']['bits'],meta['providerCnt_value'],correct=correct,useful_valid=True,
            useful=int(correct) if meta['altDiffers'] else meta['providerUsefulCnt_value'])
    if qualified(value) and meta['allocate']['valid']:
        update(meta['allocate']['bits'],0,allocate=True,useful_valid=True)
    return result
