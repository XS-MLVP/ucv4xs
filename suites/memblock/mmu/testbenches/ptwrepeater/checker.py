"""Existing response-payload checks for PTWRepeaterNB (RPT-02/RPT-03)."""
from suites.memblock.mmu.testbenches.ptwrepeater.model import response_payload


def check_response_payload(env, tag: int, ppn: int, stage: int) -> None:
    expected = response_payload(tag, ppn, stage)
    assert env.response_snapshot()["tag"] == expected["tag"]
    assert env.response_snapshot()["ppn"] == expected["ppn"]
    assert env.response_snapshot()["s2xlate"] == expected["s2xlate"]
