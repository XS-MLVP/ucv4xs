"""Independent semantic input checks, deliberately not the driver's encoder."""
from copy import deepcopy
from bpuverify.common.model.folded_history import folded_history_values, PHR_FOLD_LAYOUT


def expected_tage_feedback(transaction, *, branch_count=8):
    if branch_count < 1 or not 1 <= len(transaction.branches) <= branch_count:
        raise ValueError('TAGE resolve vector does not fit the binding')
    branches = transaction.branches + (None,) * (branch_count - len(transaction.branches))
    active = tuple(branch for branch in branches if branch is not None and branch.valid)
    if not active:
        raise ValueError('TAGE feedback needs a valid branch')
    resolved = tuple(None if branch is None or not branch.valid else {
        'position': branch.position, 'taken': branch.actual_taken,
        'branch_type': branch.branch_type, 'mispredict': branch.mispredict,
    } for branch in branches)
    predictions = []
    for branch in active:
        if not branch.mbtb_hit:
            continue
        counter = branch.base_counter_value
        if counter is None:
            counter = 2 if branch.base_taken else 1
        if counter not in range(4) or (counter >= 2) != bool(branch.base_taken):
            raise ValueError('MainBTB counter must agree with base direction')
        predictions.append({'position': branch.position, 'branch_type': branch.branch_type,
                            'base_counter': counter, 'meta': deepcopy(branch.meta)})
    result = {'ready': 1, 'pc': transaction.pc, 'resolved': resolved,
              'prediction_entries': tuple(predictions)}
    if transaction.history:
        result['history'] = tuple(row['foldedHist'] for row in folded_history_values(transaction.history, len(PHR_FOLD_LAYOUT)))
    return result


def observed_tage_feedback(sample):
    """Normalize an immutable CycleMonitor snapshot; ignore invalid payloads."""
    bits = sample['bits']
    entries = tuple(entry for bank in bits['mbtb_meta'] for entry in bank)
    result = {
        'ready': sample['ready'], 'pc': bits['start_pc'],
        'resolved': tuple(None if not branch['valid'] else {
            key: branch[key] for key in ('position', 'taken', 'branch_type', 'mispredict')
        } for branch in bits['branches']),
        'prediction_entries': tuple({
            'position': entry['position'], 'branch_type': entry['attribute']['branchType'],
            'base_counter': entry['counter_value'], 'meta': bits['tage_meta'][slot],
        } for slot, entry in enumerate(entries) if entry['rawHit']),
    }
    history = tuple(row['foldedHist'] for row in bits.get('history', ()))
    if any(history):
        result['history'] = history
    return result
