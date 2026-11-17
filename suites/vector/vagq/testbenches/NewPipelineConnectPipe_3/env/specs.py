"""Native layout for NewPipelineConnectPipe_3."""
from dataclasses import dataclass

from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Pipe3Payload


@dataclass(frozen=True, slots=True)
class Spec:
    module: str
    group: str
    payload_type: type
    fields: tuple[tuple[str, str], ...]  # domain attribute, native wire suffix


PIPE3 = Spec(
    'NewPipelineConnectPipe_3', 'vagq.pipe3.checked', Pipe3Payload,
    (('entry_idx', 'entryIdx'), ('rob_flag', 'robIdx_flag'), ('rob_value', 'robIdx_value'),
     ('is_load', 'isLoad'), ('lq_value', 'lqIdx_value'), ('sq_first_flag', 'sqIdx_first_flag'),
     ('sq_second_flag', 'sqIdx_second_flag'), ('sq_value', 'sqIdx_value'), ('issue_mask', 'issueMask')),
)
