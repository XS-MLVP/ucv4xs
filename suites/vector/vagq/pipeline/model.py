"""One-slot Decoupled state model shared only at the protocol-semantic level."""
from dataclasses import dataclass

from .types import Beat, Observation, Pipe3Payload, PipePayload


@dataclass(frozen=True, slots=True)
class State:
    valid: bool = False
    payload: PipePayload | Pipe3Payload = PipePayload()

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
