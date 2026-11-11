"""Guard contradictions are not automatically native DA reachability proofs."""
import pytest

from suites.frontend.bpu.testbenches.shared.coverage.local_guards import ROOT
from suites.frontend.bpu.testbenches.shared.coverage.local_guards import claim
from suites.frontend.bpu.testbenches.shared.coverage.local_guards import match_native
from suites.frontend.bpu.testbenches.shared.coverage.local_guards import native_points


def fixture():
    file = 'rtl/sc/WriteBuffer.sv'
    assertions = [claim(file,366,374,365,'if','diagnostic-fixture')]
    native = dict(dut={'sc':dict(source_lines=dict(total=20,hit=11),
        uncovered_rtl_source_lines=[dict(file=file,line=line) for line in range(366,375)])})
    point = dict(f=str(ROOT/file),l='365',page='v_branch/WriteBuffer',o='if',S='365-374',h='example')
    return assertions,native,point


@pytest.mark.parametrize('fault',('missing','wrong-anchor','wrong-arm','extra-producer','nonzero','native-row-not-zero','partial-span'))
def test_zero_count_or_nearby_source_text_is_not_sufficient_for_native_association(fault):
    claims,native,point = fixture()
    points = [(point,0)]
    if fault=='missing': points = []
    elif fault=='wrong-anchor': point['l'] = '338'
    elif fault=='wrong-arm': point['o'] = 'else'
    elif fault=='extra-producer': points.append(({**point,'l':'338','o':'if'},0))
    elif fault=='nonzero': points = [(point,1)]
    elif fault=='native-row-not-zero': native['dut']['sc']['uncovered_rtl_source_lines'].pop()
    else: point['S'] = '365-373'
    with pytest.raises(AssertionError): match_native(claims,native,'sc',points)


def test_native_mapping_checks_all_producers_and_retains_unknown_rows():
    claims,native,point = fixture()
    native['dut']['sc']['uncovered_rtl_source_lines'].append(dict(file=claims[0]['file'],line=999))
    native['dut']['sc']['source_lines']['hit'] = 10
    result = match_native(claims,native,'sc',[(point,0),({**point,'page':'v_line/WriteBuffer'},0)])
    assert result['locally_classified']==9 and len(result['native_points'])==2
    assert result['unclassified']==[('rtl/sc/WriteBuffer.sv',999)]
    assert result['native_source_lines']==dict(total=20,hit=10)


def test_parser_ignores_toggle_counts_in_the_same_source_range(tmp_path):
    _,_,point = fixture()
    def record(fields,count):
        meta = ''.join('\x01'+key+'\x02'+value for key,value in fields.items())
        return f"C '{meta}' {count}\n"
    data = tmp_path/'native.dat'
    data.write_text(record(point,0)+record({**point,'page':'v_toggle/WriteBuffer'},999))
    assert native_points(data)==[(point,0)]
