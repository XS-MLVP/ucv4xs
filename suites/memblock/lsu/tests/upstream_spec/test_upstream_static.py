import ucv.runtime as ucv_paths
"""Source-level checks for counters that the generated DUT does not expose.

These are ordinary FAILs against the fixed source snapshot, not native DUT
simulation. They are kept separate from hardware port probes.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ucv_paths.source_path_for(ROOT) / 'src/main/scala/xiangshan/mem/pipeline'


def test_std_out_of_range_counter_is_not_inverted():
    text = (SOURCE / "StdExeUnit.scala").read_text()
    # Upstream #6653: the counter must count legal-issue violations, not all
    # idle/legal cycles. The fixed source still has the negation.
    assert 'XSPerfAccumulate("STD_out_of_range_issue", io.in.valid && s0IllegalIssue)' in text
