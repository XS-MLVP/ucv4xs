"""Payload field mapping for NewPipelineConnectPipe_3."""

import pytest

from suites.vector.vagq.testbenches.shared.env.bundle.legacy_pins import P
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.env.encoding import encode
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.env.specs import PIPE3
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Beat
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Pipe3Payload

pytestmark = [
    pytest.mark.toffee_functional_coverage(False),
    pytest.mark.selftest,
]


def test_pipe3_encodes_compact_issue_mask_payload():
    values = encode(PIPE3, Beat(in_valid=True, payload=Pipe3Payload(issue_mask=0xa55a)))
    assert values[P.p_in_bits_issueMask] == 0xa55a
    assert P.p_in_bits_pc not in values
