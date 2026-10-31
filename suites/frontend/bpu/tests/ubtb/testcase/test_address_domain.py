"""Semantic tag/target boundaries, with addresses in the public byte API."""
import pytest

from suites.frontend.bpu.ubtb.case.address import CASES, check_address_case


@pytest.mark.feature('BPU-UBTB-008')
@pytest.mark.parametrize('case', CASES, ids=lambda case: case.name)
async def test_public_byte_addresses_preserve_identity_and_local_target(ubtb_agent, case):
    await check_address_case(ubtb_agent, case)
