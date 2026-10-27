"""Actual original and registered receipts; never predictor golden data."""
from copy import deepcopy


def receipts(rows):
    inputs=[row for row in rows if row['commit']['valid']]
    registered=[row for row in rows if row['pending_commit']['valid']]
    if len(inputs)!=1 or len(registered)!=1:
        raise AssertionError(f'one actual original input and registered commit required: {len(inputs)}, {len(registered)}')
    source,actual=inputs[0]['commit']['bits'],registered[0]['pending_commit']
    if source['meta']['ssp']!=actual['ssp'] or source['meta']['tosw']!=actual['tosw']:
        raise AssertionError('registered action changed its exact original source metadata')
    return source,actual


def commit_facts(rows):
    """Keep actual ownership boundaries and final state, not every cycle."""
    payload,registered=receipts(rows)
    return deepcopy(dict(actual_input=payload,actual_registered=registered,
        input_tick=next(row['tick'] for row in rows if row['commit']['valid']),
        registered_tick=next(row['tick'] for row in rows if row['pending_commit']['valid']),
        retained=dict(head=rows[-1]['head'],cells=rows[-1]['cells'])))
