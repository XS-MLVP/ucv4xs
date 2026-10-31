"""Guard contradictions are not automatically native DA reachability proofs."""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from suites.frontend.bpu.coverage.local_guards import ROOT, Source, claim, match_native, native_points
from suites.frontend.bpu.sc.coverage.guard_audit import source_claims as sc_claims
from suites.frontend.bpu.tage.coverage.coverage_audit import source_claims as tage_claims
from tools.review_guard_gaps import review


def report():
    # Permissive synthetic input for source review only, NOT native evidence.
    file = 'rtl/tage/WriteBuffer_12.sv'
    size = len((ROOT/file).read_text().splitlines())
    return dict(generated_at='synthetic-unit-fixture-not-verification-evidence',dut={'tage':dict(source_lines=dict(total=size,hit=0),
        uncovered_rtl_source_lines=[dict(file=file,line=line) for line in range(1,size+1)])})


@pytest.fixture
def baseline(tmp_path):
    # Unit contracts use synthetic counters; the explicit diagnostic command
    # separately checks real frozen-run producer metadata. No old result file
    # is required by pytest or silently promoted to verification evidence.
    native,epoch,paths = dict(generated_at='synthetic-unit-fixture-not-verification-evidence',pytest_exitstatus=0,dut={}),{},[]
    for dut,factory in (('sc',sc_claims),('tage',lambda:tage_claims(report()))):
        claims,sources = factory()
        rows = [dict(file=item['file'],line=line) for item in claims for line in range(item['first'],item['last']+1)]
        native['dut'][dut] = dict(source_lines=dict(total=len(rows)+1,hit=1),uncovered_rtl_source_lines=rows)
        for source in sources:
            epoch[str((ROOT/source['file']).resolve())] = source['sha256']
        path = tmp_path/'pytest-artifacts/workers/gw0/native'/dut/'native-merged.dat'
        path.parent.mkdir(parents=True)
        records = []
        for item in claims:
            fields = dict(f=str(ROOT/item['file']),l=str(item['guard']),o=item['arm'],
                page='v_branch/WriteBuffer',S=f"{item['first']}-{item['last']}")
            meta = ''.join('\x01'+key+'\x02'+value for key,value in fields.items())
            records.append(f"C '{meta}' 0\n")
        path.write_text(''.join(records))
        paths.append(str(path))
    (tmp_path/'rtl-line-coverage.json').write_text(json.dumps(native))
    (tmp_path/'source-epoch.json').write_text(json.dumps(epoch))
    (tmp_path/'pytest-artifacts/rtl-coverage-manifest.json').write_text(json.dumps(dict(files=paths)))
    return tmp_path


@pytest.mark.parametrize('dut',('sc','tage'))
def test_reviewed_source_claims_require_matching_native_producers(dut,baseline):
    result = review(baseline)['dut'][dut]
    assert result['raw_missing']==result['locally_classified']==(656 if dut=='sc' else 120)
    assert result['unclassified']==[] and result['native_points']
    assert result['native_denominator_unchanged'] and not result['functional_pass_credit']
    assert not result['whole_design_formal_claim']


@pytest.mark.parametrize('dut,file,before,after',(
    ('sc','WriteBuffer_54.sv','if (|hitMaskUInt) begin','if (~(|hitMaskUInt)) begin'),
    ('sc','WriteBuffer_54.sv',"_GEN_21 = ~(|hitMaskUInt) & victim == 2'h0;","_GEN_21 = victim == 2'h0;"),
    ('sc','WriteBuffer_54.sv','entries_0_0_setIdx <= io_write_0_bits_setIdx;','entries_0_1_setIdx <= io_write_0_bits_setIdx;'),
    ('sc','WriteBuffer_54.sv','entries_0_0_wayData_0 <= io_write_0_bits_wayData_0;','entries_0_0_wayData_0 <= io_write_1_bits_wayData_0;'),
    ('sc','WriteBuffer_68.sv','if (|hitMaskUInt) begin','if (~(|hitMaskUInt)) begin'),
    ('sc','WriteBuffer_68.sv',"_GEN_69 = ~(|hitMaskUInt) & victim == 2'h0;","_GEN_69 = victim == 2'h0;"),
    ('tage','WriteBuffer_12.sv','if (|hitMaskUInt_1) begin','if (~(|hitMaskUInt_1)) begin'),
    ('tage','WriteBuffer_12.sv','_GEN_55 = (|hitMaskUInt) & ~rowIdx & _GEN_22;','_GEN_55 = ~rowIdx & _GEN_22;'),
    ('tage','WriteBuffer_12.sv','if (_GEN_125) begin','if (|hitMaskUInt_1) begin'),
    ('tage','WriteBuffer_12.sv','_GEN_51 = ~(|_hitWritten_T_1) | _GEN_41 | ~_GEN_33;','_GEN_51 = ~(|_hitWritten_T_1) | _GEN_41;'),
    ('tage','WriteBuffer_12.sv','else if (~(|_hitWritten_T_3) | _GEN_115 | ~_GEN_93) begin','else if (|hitMaskUInt_1) begin'),
    ('tage','WriteBuffer_12.sv','else if (_GEN_51) begin','else if (|hitMaskUInt) begin'),
    ('tage','WriteBuffer_12.sv','entries_1_0_entry_tag <= io_write_0_bits_entry_tag;','entries_0_0_entry_tag <= io_write_0_bits_entry_tag;'),
))
def test_weakened_guards_or_wrong_body_source_are_rejected_without_editing_rtl(dut,file,before,after,monkeypatch):
    path = ROOT/f'rtl/{dut}/{file}'
    original = path.read_bytes()
    text = path.read_text()
    assert before in text
    changed = text.replace(before,after)
    real_read = Path.read_text
    def read(received,*args,**kwargs):
        return changed if received==path else real_read(received,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    with pytest.raises(AssertionError):
        sc_claims() if dut=='sc' else tage_claims(report())
    assert path.read_bytes()==original


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


def test_span_mapping_can_classify_an_else_head_without_confusing_the_covered_anchor():
    file = 'rtl/tage/WriteBuffer_12.sv'
    assertions = [claim(file,871,875,849,'else','local-priority-contradiction')]
    native = dict(dut={'tage':dict(source_lines=dict(total=8,hit=3),
        uncovered_rtl_source_lines=[dict(file=file,line=line) for line in range(871,876)])})
    point = dict(f=str(ROOT/file),l='849',page='v_line/WriteBuffer',o='else',S='871-875')
    result = match_native(assertions,native,'tage',[(point,0),({**point,'o':'if','S':'849'},300)])
    assert result['locally_classified']==5 and result['unclassified']==[]


def test_parser_ignores_toggle_counts_in_the_same_source_range(tmp_path):
    _,_,point = fixture()
    def record(fields,count):
        meta = ''.join('\x01'+key+'\x02'+value for key,value in fields.items())
        return f"C '{meta}' {count}\n"
    data = tmp_path/'native.dat'
    data.write_text(record(point,0)+record({**point,'page':'v_toggle/WriteBuffer'},999))
    assert native_points(data)==[(point,0)]


def test_a_guard_closed_before_the_body_is_not_an_enclosing_proof(tmp_path):
    path = tmp_path/'block.sv'
    path.write_text('if (hit) begin\nend\nif (other) begin\na <= b;\nend\n')
    source = Source(path)
    with pytest.raises(AssertionError): source.encloses(1,4,4)


def test_diagnostic_review_is_read_only_and_has_no_implicit_exports(baseline):
    files = list(baseline.rglob('*'))
    files = [path for path in files if path.is_file()]
    files += [ROOT/name for name in ('rtl/sc/WriteBuffer_54.sv','rtl/sc/WriteBuffer_68.sv','rtl/tage/WriteBuffer_12.sv')]
    before = {str(path):sha256(path.read_bytes()).hexdigest() for path in files}
    review(baseline)
    assert {str(path):sha256(path.read_bytes()).hexdigest() for path in files}==before
    assert {path for path in baseline.rglob('*') if path.is_file()}==set(path for path in files if path.is_relative_to(baseline))


def test_deletable_historical_reports_are_not_source_proof_inputs(baseline,monkeypatch):
    real_read = Path.read_text
    def read(path,*args,**kwargs):
        assert not path.is_relative_to(ROOT/'results'),('unexpected old report dependency',path)
        return real_read(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    assert review(baseline)['dut']['tage']['locally_classified']==120


def test_stale_compiled_source_epoch_cannot_support_a_current_claim(baseline):
    path = baseline/'source-epoch.json'
    epoch = json.loads(path.read_text())
    epoch[str((ROOT/'rtl/sc/WriteBuffer_54.sv').resolve())] = '0'*64
    path.write_text(json.dumps(epoch))
    with pytest.raises(AssertionError,match='stale native source'): review(baseline)


def test_cli_exports_only_when_requested_and_never_replaces_existing_output(baseline,tmp_path,monkeypatch,capsys):
    from tools.review_guard_gaps import main
    args = ['review_guard_gaps','--baseline',str(baseline)]
    before = {path for path in baseline.rglob('*') if path.is_file()}
    monkeypatch.setattr('sys.argv',args)
    main()
    assert json.loads(capsys.readouterr().out)['tage']['locally_classified']==120
    assert {path for path in baseline.rglob('*') if path.is_file()}==before
    output = tmp_path/'explicit-review.json'
    monkeypatch.setattr('sys.argv',args+['--output',str(output)])
    main()
    first = output.read_bytes()
    assert json.loads(first)['dut']['sc']['locally_classified']==656
    with pytest.raises(FileExistsError): main()
    assert output.read_bytes()==first


def test_failed_run_diagnostic_is_labelled_and_cannot_become_functional_pass_credit(baseline):
    path = baseline/'failed-native-diagnostic.json'
    native = json.loads((baseline/'rtl-line-coverage.json').read_text())
    native['pytest_exitstatus'] = 1
    path.write_text(json.dumps(native))
    result = review(baseline,duts=('tage',),native_report=path)
    assert result['native_pytest_exitstatus']==1 and set(result['dut'])=={'tage'}
    assert not result['dut']['tage']['functional_pass_credit']
