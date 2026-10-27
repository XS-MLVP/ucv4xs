"""Strict valid-payload comparison for the public Arbiter leaves."""
from toffee import CheckContext, Scoreboard, ScoreboardMode

from .schema import LOAD_META_FIELDS, LOAD_REQ_FIELDS, STORE_META_FIELDS, STORE_REQ_FIELDS


def _signature(outputs):
    result = []

    for lane in range(3):
        result.append((
            f'issueLda_{lane}_ready',
            outputs[f'io_issueLda_{lane}_ready'],
        ))
        valid = outputs[f'io_lduReq_{lane}_valid']
        result.append((f'lduReq_{lane}_valid', valid))
        meta_valid = outputs[f'io_lduReq_{lane}_bits_meta_valid']
        result.append((f'lduReq_{lane}_meta_valid', meta_valid))
        if valid:
            result.extend((
                (f'lduReq_{lane}_req_{field}', outputs[f'io_lduReq_{lane}_bits_req_{field}'])
                for field in LOAD_REQ_FIELDS
            ))
            if meta_valid:
                result.extend((
                    (f'lduReq_{lane}_meta_{field}', outputs[f'io_lduReq_{lane}_bits_meta_{field}'])
                    for field in LOAD_META_FIELDS
                    if field != 'valid'
                ))
        result.append((f'vagqLsuReq_{lane}_ready', outputs[f'io_vagqLsuReq_{lane}_ready']))

    for lane in range(2):
        result.append((
            f'issueSta_{lane}_ready',
            outputs[f'io_issueSta_{lane}_ready'],
        ))
        valid = outputs[f'io_staReq_{lane}_valid']
        result.append((f'staReq_{lane}_valid', valid))
        meta_valid = outputs[f'io_staReq_{lane}_bits_meta_valid']
        result.append((f'staReq_{lane}_meta_valid', meta_valid))
        if valid:
            result.extend((
                (f'staReq_{lane}_req_{field}', outputs[f'io_staReq_{lane}_bits_req_{field}'])
                for field in STORE_REQ_FIELDS
            ))
            if meta_valid:
                result.extend((
                    (f'staReq_{lane}_meta_{field}', outputs[f'io_staReq_{lane}_bits_meta_{field}'])
                    for field in STORE_META_FIELDS
                    if field != 'valid'
                ))
        result.append((f'vagqLsuReq_{lane}_ready', outputs[f'io_vagqLsuReq_{lane}_ready']))

    for lane in range(2):
        result.append((
            f'vagqStoreDataReq_{lane}_ready',
            outputs[f'io_vagqStoreDataReq_{lane}_ready'],
        ))
        valid = outputs[f'io_vagqStdData_{lane}_valid']
        result.append((f'vagqStdData_{lane}_valid', valid))
        if valid:
            for field in ('data', 'sqIdx_first_flag', 'sqIdx_second_flag', 'sqIdx_value'):
                result.append((
                    f'vagqStdData_{lane}_{field}',
                    outputs[f'io_vagqStdData_{lane}_bits_{field}'],
                ))
    return tuple(result)


class Checker:
    def __init__(self):
        self.board = Scoreboard('arbiter.outputs')
        self.sequence = 0

    def compare(self, expected, actual, beat):
        self.board.check(
            expected=_signature(expected.outputs),
            actual=_signature(actual),
            context=CheckContext(
                self.board.name,
                ScoreboardMode.DIRECT,
                sequence_id=self.sequence,
                request=beat,
            ),
        )
        self.sequence += 1
