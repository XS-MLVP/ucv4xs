"""Single-slot pipe model qualification with fixed protocol answers."""
import pytest

from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.model import State
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Beat
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Pipe3Payload

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_full_slot_holds_under_backpressure_and_does_not_capture():
    old = Pipe3Payload(entry_idx=2, rob_value=7, issue_mask=0x11)
    new = Pipe3Payload(entry_idx=4, rob_value=9, issue_mask=0x22)
    state = State(True, old)
    beat = Beat(in_valid=True, out_ready=False, payload=new)
    assert state.observe(beat).in_ready is False
    assert state.following(beat) == state


def test_right_fire_without_input_consumes_but_out_ready_alone_does_not():
    old = Pipe3Payload(entry_idx=2, issue_mask=0x11)
    state = State(True, old)
    assert state.following(Beat(out_ready=True, payload=old)).valid is True
    assert state.following(Beat(right_out_fire=True, payload=old)).valid is False


@pytest.mark.parametrize('factory', [lambda: Pipe3Payload(issue_mask=1 << 16)], ids=['<lambda>1'])
def test_payload_widths_reject_truncation(factory):
    with pytest.raises(ValueError):
        factory()
