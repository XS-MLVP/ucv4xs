"""Opaque native bypass payloads for arbitration scenarios.

Field enumeration, per-leaf width masks and the physical ROB identity encoding
stay in this adapter.  A functional scenario chooses only the channel
(load/store), validity, ROB flag/value and a deterministic payload-pattern
seed; it never sees schema order, leaf names or widths.
"""
from suites.vector.vagq.testbenches.arbiter.env.schema import INPUT_NAMES
from suites.vector.vagq.testbenches.arbiter.env.schema import INPUT_WIDTHS
from suites.vector.vagq.testbenches.arbiter.transactions import NativeReq


CHANNEL_GROUP = {'load': 'issueLda', 'store': 'issueSta'}


def native_request(kind, *, valid=False, rob_flag=0, rob_value=0, pattern_seed=0):
    """Build one opaque native bypass payload for ``kind`` in {load, store}.

    Payload bytes follow the historic deterministic pattern: every field of
    the channel takes ``(seed + index + 1)`` masked to its own leaf width,
    where ``index`` is the field's position in the generated input schema.
    The ROB identity is then encoded physically in this adapter.
    """
    try:
        group = CHANNEL_GROUP[kind]
    except KeyError as error:
        raise ValueError(f'native bypass kind must be load or store: {kind!r}') from error
    marker = f'io_{group}_0_bits_'
    fields = {}
    for index, name in enumerate(INPUT_NAMES):
        if not name.startswith(marker):
            continue
        width = INPUT_WIDTHS[name]
        fields[name.removeprefix(marker)] = (pattern_seed + index + 1) & ((1 << width) - 1)
    fields['robIdx_flag'] = int(rob_flag)
    fields['robIdx_value'] = int(rob_value)
    return NativeReq.from_dict(valid=valid, **fields)
