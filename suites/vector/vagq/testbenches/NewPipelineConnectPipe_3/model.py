"""One-slot Decoupled state model for NewPipelineConnectPipe_3."""
from dataclasses import dataclass

from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Beat
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Observation
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Pipe3Payload


@dataclass(frozen=True, slots=True)
class State:
    valid: bool = False
    payload: Pipe3Payload = Pipe3Payload()

    def observe(self, beat: Beat):
        return Observation(
            in_ready=bool(beat.out_ready or not self.valid),
            out_valid=self.valid,
            payload=self.payload,
        )

    def following(self, beat: Beat):
        in_ready = bool(beat.out_ready or not self.valid)
        in_fire = bool(beat.in_valid and in_ready)
        valid = False if beat.is_flush else bool(in_fire or (self.valid and not beat.right_out_fire))
        payload = beat.payload if in_fire else self.payload
        return State(valid, payload)
