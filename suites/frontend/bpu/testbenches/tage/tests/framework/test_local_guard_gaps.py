"""Guard contradictions are not automatically native DA reachability proofs."""
import pytest

from suites.frontend.bpu.testbenches.shared.coverage.local_guards import ROOT
from suites.frontend.bpu.testbenches.shared.coverage.local_guards import claim
from suites.frontend.bpu.testbenches.shared.coverage.local_guards import match_native


def test_span_mapping_can_classify_an_else_head_without_confusing_the_covered_anchor():
    file = 'rtl/tage/WriteBuffer_12.sv'
    assertions = [claim(file,871,875,849,'else','local-priority-contradiction')]
    native = dict(dut={'tage':dict(source_lines=dict(total=8,hit=3),
        uncovered_rtl_source_lines=[dict(file=file,line=line) for line in range(871,876)])})
    point = dict(f=str(ROOT/file),l='849',page='v_line/WriteBuffer',o='else',S='871-875')
    result = match_native(assertions,native,'tage',[(point,0),({**point,'o':'if','S':'849'},300)])
    assert result['locally_classified']==5 and result['unclassified']==[]
