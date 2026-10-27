"""Separate native layouts for the two generated pipe modules."""
from dataclasses import dataclass

from .types import Pipe3Payload, PipePayload


@dataclass(frozen=True, slots=True)
class Spec:
    module: str
    group: str
    payload_type: type
    fields: tuple[tuple[str, str], ...]  # domain attribute, native wire suffix


PIPE1 = Spec(
    'NewPipelineConnectPipe', 'vagq.pipe1.checked', PipePayload,
    (('entry_idx', 'entryIdx'), ('rob_flag', 'robIdx_flag'), ('rob_value', 'robIdx_value'),
     ('is_load', 'isLoad'), ('lq_flag', 'lqIdx_flag'), ('lq_value', 'lqIdx_value'),
     ('sq_first_flag', 'sqIdx_first_flag'), ('sq_second_flag', 'sqIdx_second_flag'),
     ('sq_value', 'sqIdx_value'), ('elem_idx', 'elemIdx'), ('data_size', 'dataSize'),
     ('data_mask', 'dataMask'), ('pc', 'pc'), ('ftq_flag', 'ftqPtr_flag'),
     ('ftq_value', 'ftqPtr_value'), ('ftq_offset', 'ftqOffset'), ('byte_offset', 'byteOffset'),
     ('vaddr', 'vaddr'), ('pdest', 'pdest')),
)
PIPE3 = Spec(
    'NewPipelineConnectPipe_3', 'vagq.pipe3.checked', Pipe3Payload,
    (('entry_idx', 'entryIdx'), ('rob_flag', 'robIdx_flag'), ('rob_value', 'robIdx_value'),
     ('is_load', 'isLoad'), ('lq_value', 'lqIdx_value'), ('sq_first_flag', 'sqIdx_first_flag'),
     ('sq_second_flag', 'sqIdx_second_flag'), ('sq_value', 'sqIdx_value'), ('issue_mask', 'issueMask')),
)
