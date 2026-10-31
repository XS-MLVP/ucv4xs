"""Flat picker port encoding for OrderedPermitCtrl."""
from .types import Beat, NUM_ENTRIES


def encode(beat: Beat):
    values = {}
    for index, entry in enumerate(beat.entries):
        prefix = f'in_entries_{index}_'
        values.update({
            prefix + 'valid': int(entry.valid),
            prefix + 'static_uopType': entry.uop_type,
            prefix + 'static_robIdx_flag': entry.rob_flag,
            prefix + 'static_robIdx_value': entry.rob_value,
            prefix + 'static_uopIdx': entry.uop_idx,
            prefix + 'static_lastUop': int(entry.last_uop),
            prefix + 'dynamic_exception': int(entry.exception),
            prefix + 'dynamic_state': entry.state,
        })
    values.update({
        'in_splitDoneUpdate_valid': int(beat.split_done.valid),
        'in_splitDoneUpdate_bits_entryIdxOH': (
            1 << beat.split_done.entry_idx if beat.split_done.valid else 0
        ),
        'in_redirect_valid': int(beat.redirect.valid),
        'in_redirect_bits_level': beat.redirect.level,
        'in_redirect_bits_robIdx_flag': beat.redirect.rob_flag,
        'in_redirect_bits_robIdx_value': beat.redirect.rob_value,
    })
    return values


def output_names():
    return tuple(f'out_orderedCanProceed_{index}' for index in range(NUM_ENTRIES))
