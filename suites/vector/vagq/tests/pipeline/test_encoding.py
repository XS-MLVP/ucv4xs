"""Payload field mapping is distinct for the two generated pipe roots."""
import pytest

from vagqverify.pipeline.encoding import encode
from vagqverify.pipeline.specs import PIPE1, PIPE3
from vagqverify.pipeline.types import Beat, Pipe3Payload, PipePayload

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_pipe1_encodes_full_lsu_metadata():
    values = encode(PIPE1, Beat(in_valid=True, payload=PipePayload(pc=0x123, vaddr=0x456, pdest=7)))
    assert values['io_in_valid'] == 1
    assert values['io_in_bits_pc'] == 0x123
    assert values['io_in_bits_vaddr'] == 0x456
    assert values['io_in_bits_pdest'] == 7


def test_pipe3_encodes_compact_issue_mask_payload():
    values = encode(PIPE3, Beat(in_valid=True, payload=Pipe3Payload(issue_mask=0xa55a)))
    assert values['io_in_bits_issueMask'] == 0xa55a
    assert 'io_in_bits_pc' not in values
