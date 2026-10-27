"""Project every ABTB way; transient multi-hit is not a one-hot interface."""
from bpuverify.bpu.model.phr.model import folds


def training_tag_fold_pair(actual, tag_history):
    """Compare latched training folds with the independently qualified input."""
    expected = folds(tag_history)
    observed = actual['meta']['resolve']['utage']['foldedPathHistForTrain_hist']
    return (tuple(expected[i] for i in (1, 2, 7, 8)),
            tuple(observed[i]['foldedHist'] for i in (1, 2, 7, 8)))


def conditional_source_ways(abtb, position):
    return [way for way, entry in enumerate(abtb['entries'])
        if abtb['valid'] and entry['hit'] and entry['position'] == position
        and entry['attribute']['branchType'] == 1]


def public_readback_pair(actual, abtb, payload, *, pc, index, position, target=None, table=1,
                         prediction_position=None):
    """Expected validity comes from the captured input, not actual UTAGE valid."""
    selected = conditional_source_ways(abtb, position)
    metadata = actual['meta']['resolve']['utage']
    fields = ('hit', 'tableId', 'cfiPosition', 'takenCtr_value', 'predTaken')
    expected_slots, actual_slots = [], []
    for way, entry in enumerate(metadata['abtbResult']):
        expected = dict(valid=int(way in selected))
        observed = dict(valid=entry['valid'])
        if way in selected:
            expected.update(hit=1, tableId=table, cfiPosition=position,
                takenCtr_value=payload['counter'], predTaken=int(payload['counter'] >= 4))
        if way in selected or entry['valid']:
            observed.update({name: entry[name] for name in fields})
        expected_slots.append(expected)
        actual_slots.append(observed)
    expected_prediction = dict(start_pc=pc)
    if selected:
        expected_prediction.update(target=pc if target is None else target, taken=1,
            position=position if prediction_position is None else prediction_position)
    actual_prediction = {name: actual['prediction'][name] for name in expected_prediction}
    indices = [index, index] if isinstance(index, int) else list(index)
    return (dict(width=len(abtb['entries']), readIndex=indices, slots=expected_slots, prediction=expected_prediction),
        dict(width=len(metadata['abtbResult']), readIndex=metadata['readIndex'], slots=actual_slots, prediction=actual_prediction))
