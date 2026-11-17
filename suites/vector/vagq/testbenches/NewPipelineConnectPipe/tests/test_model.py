"""Single-slot pipe model qualification with fixed protocol answers."""
import pytest

from suites.vector.vagq.testbenches.NewPipelineConnectPipe.model import State
from suites.vector.vagq.testbenches.NewPipelineConnectPipe.transactions import Beat
from suites.vector.vagq.testbenches.NewPipelineConnectPipe.transactions import PipePayload

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_empty_slot_is_ready_and_capture_sets_valid_payload():
    payload = PipePayload(entry_idx=3, rob_value=0x12, data_mask=0x55aa, vaddr=0x1234)
    state = State(payload=PipePayload())
    beat = Beat(in_valid=True, out_ready=False, payload=payload)
    assert state.observe(beat).in_ready is True
    following = state.following(beat)
    assert following.valid is True and following.payload == payload


def test_simultaneous_fire_replaces_and_flush_dominates_everything():
    old = PipePayload(entry_idx=1, vaddr=1)
    new = PipePayload(entry_idx=2, vaddr=2)
    state = State(True, old)
    replacement = state.following(Beat(True, True, True, False, new))
    assert replacement == State(True, new)
    flushed = state.following(Beat(True, True, True, True, new))
    assert flushed.valid is False and flushed.payload == new


@pytest.mark.parametrize('factory', [lambda: PipePayload(data_mask=1 << 16)], ids=['<lambda>0'])
def test_payload_widths_reject_truncation(factory):
    with pytest.raises(ValueError):
        factory()
