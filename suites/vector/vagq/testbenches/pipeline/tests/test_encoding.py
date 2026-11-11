"""Payload field mapping is distinct for the two generated pipe roots."""

import pytest

from suites.vector.vagq.testbenches.shared.env.bundle.legacy_pins import P
from suites.vector.vagq.testbenches.pipeline.env.encoding import encode
from suites.vector.vagq.testbenches.pipeline.env.specs import PIPE1
from suites.vector.vagq.testbenches.pipeline.env.specs import PIPE3
from suites.vector.vagq.testbenches.pipeline.transactions import Beat
from suites.vector.vagq.testbenches.pipeline.transactions import Pipe3Payload
from suites.vector.vagq.testbenches.pipeline.transactions import PipePayload

pytestmark = [
    pytest.mark.toffee_functional_coverage(False),
    pytest.mark.selftest,
]


def test_pipe1_encodes_full_lsu_metadata():
    # Independent physical expectations: these constants are deliberately not
    # derived from PIPE1.fields, so a swapped Spec still fails this selftest.
    values = encode(PIPE1, Beat(in_valid=True, payload=PipePayload(pc=0x123, vaddr=0x456, pdest=7)))
    assert values[P.p_in_valid] == 1
    assert values[P.p_in_bits_pc] == 0x123
    assert values[P.p_in_bits_vaddr] == 0x456
    assert values[P.p_in_bits_pdest] == 7


def test_pipe3_encodes_compact_issue_mask_payload():
    values = encode(PIPE3, Beat(in_valid=True, payload=Pipe3Payload(issue_mask=0xa55a)))
    assert values[P.p_in_bits_issueMask] == 0xa55a
    assert P.p_in_bits_pc not in values
