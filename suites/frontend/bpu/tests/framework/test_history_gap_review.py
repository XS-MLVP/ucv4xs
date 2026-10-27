"""Synthetic native evidence: conditional legality is never a blanket waiver."""
from hashlib import sha256
import json
from pathlib import Path
import re
import pytest

from bpuverify.bpu.coverage.history_gaps import SOURCE,MODEL,assignment,local_claims,constrained_claims,cursor_sources
from bpuverify.common.coverage.local_guards import ROOT,Source
from tools.review_history_gaps import review,main


def candidate_zeros(source):
    # Independent fixture geometry: offset j+1 cannot reach cell i from an
    # even pointer when i-(j+1) is odd. Last ELSE anchors are positive hits.
    raw=set();else_anchors=[]
    for number,line in enumerate(source.lines,1):
        match=re.fullmatch(r'phr_(\d+) <= phrWrite(?:Bits|LowBits)\[(\d+)\];',line)
        if match and (int(match[1])-int(match[2])-1)%2:
            raw.add((SOURCE,number))
            if int(match[2]):raw.add((SOURCE,number-1))
            else:else_anchors.append(number-1)
    return raw,else_anchors


@pytest.fixture
def baseline(tmp_path):
    source=Source(SOURCE);raw,else_anchors=candidate_zeros(source)
    local=local_claims(source);conditional,_=constrained_claims(source,raw)
    assert len(local)==13 and len(conditional)==1404
    claims=[*local,*conditional]
    raw.update((item['file'],item['first']) for item in local)
    raw.update(((SOURCE,2),('rtl/bpu/Other.sv',2)))
    p=tmp_path/'synthetic-run';p.mkdir()
    (p/'diagnostic-rtl-line-coverage.json').write_text(json.dumps(dict(pytest_exitstatus=1,dut=dict(bpu=dict(
        source_lines=dict(total=len(raw)+len(else_anchors),hit=len(else_anchors)),
        uncovered_rtl_source_lines=[dict(file=f,line=n) for f,n in sorted(raw)])))))
    (p/'source-epoch.json').write_text(json.dumps({str(ROOT/file):sha256((ROOT/file).read_bytes()).hexdigest() for file in (SOURCE,MODEL)}))
    path=p/'pytest-artifacts/workers/gw0/native/bpu/native-merged.dat';path.parent.mkdir(parents=True)
    rows=[]
    for item in claims:
        fields=dict(f=str(ROOT/SOURCE),l=str(item['guard']),o=item['arm'],S=str(item['first']),page='v_branch/Phr')
        rows.append((fields,0))
    rows.extend((dict(f=str(ROOT/SOURCE),l=str(n),o='else',page='v_branch/Phr'),10) for n in else_anchors)
    path.write_text(''.join("C '"+''.join('\x01'+k+'\x02'+v for k,v in fields.items())+f"' {count}\n" for fields,count in rows))
    manifest=p/'pytest-artifacts/rtl-coverage-manifest.json';manifest.parent.mkdir(exist_ok=True)
    manifest.write_text(json.dumps(dict(files=[str(path)])))
    return p


def snapshot(run):return {p:sha256(p.read_bytes()).hexdigest() for p in run.rglob('*') if p.is_file()}


def test_default_proves_only_local_guards_and_does_not_silently_assume_legal_metadata(baseline):
    before=snapshot(baseline);result=review(baseline)
    assert result['phr_missing']==1418 and result['local_guard_keys']==13
    assert result['conditional_cursor_keys']==0 and len(result['unclassified'])==1405
    assert not result['assume_owned_checkpoints'] and result['cursor_contract'] is None
    assert not result['functional_pass_credit'] and not result['whole_design_formal_claim']
    assert result['native_denominator_unchanged'] and snapshot(baseline)==before


def test_explicit_owned_constraint_separates_1404_keys_and_keeps_unknown_rows_and_hit_else_anchors(baseline):
    before=snapshot(baseline);result=review(baseline,assume_owned_checkpoints=True)
    assert result['local_guard_keys']==13 and result['conditional_cursor_keys']==1404
    assert result['unclassified']==[(SOURCE,2)]
    assert result['cursor_contract']['alignment']==2 and not result['cursor_contract']['unrestricted_input_proof']
    _,anchors=candidate_zeros(Source(SOURCE))
    assert not {item['first'] for item in result['claims']}&set(anchors)
    assert not result['functional_pass_credit'] and not result['whole_design_formal_claim']
    assert snapshot(baseline)==before


@pytest.mark.parametrize('fault',('stale-rtl','stale-model','nonzero-producer','wrong-arm','missing-producer','overlapping-else','missing-manifest','foreign-native','foreign-report'))
def test_missing_or_changed_frozen_native_evidence_cannot_support_classification(baseline,fault,tmp_path):
    path=baseline/'pytest-artifacts/workers/gw0/native/bpu/native-merged.dat'
    report=None
    if fault in ('stale-rtl','stale-model'):
        p=baseline/'source-epoch.json';d=json.loads(p.read_text());d[str(ROOT/(SOURCE if fault=='stale-rtl' else MODEL))]='0'*64;p.write_text(json.dumps(d))
    elif fault=='nonzero-producer':path.write_text(path.read_text().replace("' 0\n","' 1\n",1))
    elif fault=='wrong-arm':path.write_text(path.read_text().replace('\x01o\x02cond_else','\x01o\x02cond_if',1))
    elif fault=='missing-producer':path.write_text('\n'.join(path.read_text().splitlines()[1:])+'\n')
    elif fault=='overlapping-else':
        fields=dict(f=str(ROOT/SOURCE),l='2056',o='else',S='2057',page='v_branch/Phr')
        path.write_text(path.read_text()+"C '"+''.join('\x01'+k+'\x02'+v for k,v in fields.items())+"' 0\n")
    elif fault in ('missing-manifest','foreign-native'):
        p=baseline/'pytest-artifacts/rtl-coverage-manifest.json'
        p.write_text(json.dumps(dict(files=[] if fault=='missing-manifest' else [str(tmp_path/'native/bpu/foreign.dat')])))
    else:report=tmp_path/'foreign.json';report.write_text('{}')
    with pytest.raises(AssertionError):review(baseline,native_report=report,assume_owned_checkpoints=True)


@pytest.mark.parametrize('before,after',(
    ('io_train_s3_overrideValid & ~io_train_redirect_valid','~io_train_s3_overrideValid & ~io_train_redirect_valid'),
    ('_s0_foldedPhr_T = io_s1Train_valid & io_s1Train_prediction_taken','_s0_foldedPhr_T = io_s1Train_valid'),
    ('else if (_s0_foldedPhr_T) begin','else if (io_s1Train_valid) begin'),
    ('? {13{io_train_s2_prediction_taken}}','? {13{io_train_s3_prediction_taken}}'),
    (': s1_foldedPhrReg_hist_12_foldedHist;',': s1_foldedPhrReg_hist_11_foldedHist;'),
))
def test_local_proof_rejects_changed_winner_or_ternary_body(monkeypatch,before,after):
    source=Source(SOURCE);assert before in source.text
    changed=source.text.replace(before,after,1)
    original=Path.read_text
    monkeypatch.setattr(Path,'read_text',lambda p,*a,**kw:changed if p==ROOT/SOURCE else original(p,*a,**kw))
    with pytest.raises(AssertionError):local_claims(Source(SOURCE))


@pytest.mark.parametrize('before,after',(
    ("phrPtr_value <= 6'h0;","phrPtr_value <= 6'h1;"),
    ("s1_phrPtr_value <= 6'h0;","s1_phrPtr_value <= 6'h1;"),
    ("{1'h0, io_train_s3_phrMeta_phrPtr_value} + 7'h32;","{1'h0, io_train_s3_phrMeta_phrPtr_value} + 7'h33;"),
    ("_GEN_15 = {1'h0, io_train_redirect_valid ? _GEN_8 : phrPtr_value};","_GEN_15 = 7'h1;"),
    ("new_value_14 = _GEN_15 + 7'hF;","new_value_14 = _GEN_15 + 7'hE;"),
    ("if (_new_ptr_value_T_29 == 6'h0)","if (_new_ptr_value_T_29 == 6'h1)"),
    ('phr_0 <= phrWriteBits[14];','phr_0 <= phrWriteBits[15];'),
))
def test_constraint_proof_rejects_changed_pointer_or_offset_geometry(monkeypatch,before,after):
    source=Source(SOURCE);raw,_=candidate_zeros(source);assert before in source.text
    changed=source.text.replace(before,after,1)
    original=Path.read_text
    monkeypatch.setattr(Path,'read_text',lambda p,*a,**kw:changed if p==ROOT/SOURCE else original(p,*a,**kw))
    with pytest.raises(AssertionError):constrained_claims(Source(SOURCE),raw)


def test_new_unaccounted_pointer_writer_invalidates_inductive_closure():
    source=Source(SOURCE);source.lines.append("phrPtr_value <= 6'h1;")
    with pytest.raises(AssertionError,match='changed pointer writers'):cursor_sources(source)


def test_hit_or_absent_incompatible_assignment_rejects_the_input_constraint():
    source=Source(SOURCE);raw,_=candidate_zeros(source);raw.remove((SOURCE,2057))
    with pytest.raises(AssertionError,match='incompatible assignment'):constrained_claims(source,raw)


def test_comparisons_are_not_parsed_as_assignment_definitions():
    source=Source(SOURCE)
    assert assignment(source,'_new_ptr_value_T_29').startswith('$signed(')
    source.lines.append("_new_ptr_value_T_29 = 6'h0;")
    with pytest.raises(AssertionError,match='ambiguous'):assignment(source,'_new_ptr_value_T_29')


def test_cli_is_compact_and_never_exports_an_implicit_audit(baseline,monkeypatch,capsys):
    before=snapshot(baseline)
    monkeypatch.setattr('sys.argv',['review_history_gaps','--baseline',str(baseline),'--assume-owned-checkpoints'])
    main();result=json.loads(capsys.readouterr().out)
    assert result['conditional_cursor_keys']==1404 and result['unclassified_count']==1
    assert 'claims' not in result and 'native_points' not in result and snapshot(baseline)==before


def test_input_constraint_cannot_be_enabled_by_an_accidentally_truthy_string(baseline):
    with pytest.raises(ValueError,match='explicitly boolean'):review(baseline,assume_owned_checkpoints='false')
