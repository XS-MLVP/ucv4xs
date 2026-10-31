"""Source isomorphism does not replace exact compiled-native producer checks."""
from hashlib import sha256
import json
from pathlib import Path
import pytest

from suites.frontend.bpu.coverage.local_guards import ROOT
from suites.frontend.bpu.bpu.coverage.guard_audit import COMPILED,ORIGINAL,source_claims
from tools.review_guard_gaps import review,main
from tests.framework.test_local_guard_gaps import baseline


@pytest.fixture
def integrated_baseline(baseline):
    # Entirely synthetic fixture; not real coverage or feature evidence.
    report=baseline/'rtl-line-coverage.json'
    native=json.loads(report.read_text())
    claims,sources=source_claims(native)
    native['dut']['bpu']=dict(source_lines=dict(total=122,hit=1),uncovered_rtl_source_lines=[
        *[dict(file=COMPILED,line=line) for item in claims for line in range(item['first'],item['last']+1)],
        dict(file=COMPILED,line=2)])
    report.write_text(json.dumps(native))
    epoch=baseline/'source-epoch.json'
    frozen=json.loads(epoch.read_text())
    frozen.update({str((ROOT/row['file']).resolve()):row['sha256'] for row in sources})
    epoch.write_text(json.dumps(frozen))
    records=[]
    for item in claims:
        fields=dict(f=str((ROOT/COMPILED).resolve()),l=str(item['guard']),o=item['arm'],page='v_branch/WriteBuffer_12',
            S=f"{item['first']}-{item['last']}")
        meta=''.join('\x01'+key+'\x02'+value for key,value in fields.items())
        records.append(f"C '{meta}' 0\n")
    path=baseline/'pytest-artifacts/workers/gw0/native/bpu/native-merged.dat'
    path.parent.mkdir(parents=True)
    path.write_text(''.join(records))
    manifest=baseline/'pytest-artifacts/rtl-coverage-manifest.json'
    value=json.loads(manifest.read_text());value['files'].append(str(path));manifest.write_text(json.dumps(value))
    return baseline


def test_only_the_120_proven_native_keys_are_classified_and_other_bpu_rows_stay_unknown(integrated_baseline):
    run=integrated_baseline
    before={p:sha256(p.read_bytes()).hexdigest() for p in run.rglob('*') if p.is_file()}
    result=review(run,duts=('bpu',))['dut']['bpu']
    assert result['raw_missing']==121 and result['locally_classified']==120
    assert result['unclassified']==[(COMPILED,2)]
    assert result['native_source_lines']==dict(total=122,hit=1)
    assert not result['functional_pass_credit'] and not result['whole_design_formal_claim']
    assert {row['file'] for row in result['sources']}=={ORIGINAL,COMPILED}
    assert {p:sha256(p.read_bytes()).hexdigest() for p in before}==before


@pytest.mark.parametrize('line,replacement',((46,'module Changed('),(546,'_GEN_58 = ~rowIdx & _GEN_25;'),
    (840,'entries_0_0_entry_takenCtr_value <= io_write_1_bits_entry_takenCtr_value;'),(808,'if (~hit_1) begin')))
def test_any_changed_integrated_body_or_module_rejects_proof_transfer(integrated_baseline,monkeypatch,line,replacement):
    path=ROOT/COMPILED;before=path.read_bytes();changed=path.read_text().splitlines();changed[line-1]=replacement
    read=Path.read_text
    monkeypatch.setattr(Path,'read_text',lambda p,*a,**kw:'\n'.join(changed) if p==path else read(p,*a,**kw))
    with pytest.raises(AssertionError):review(integrated_baseline,duts=('bpu',))
    assert path.read_bytes()==before


@pytest.mark.parametrize('fault',('stale-source','nonzero-producer','wrong-native-arm'))
def test_source_similarity_alone_cannot_waive_current_native_evidence(integrated_baseline,fault):
    run=integrated_baseline
    if fault=='stale-source':
        p=run/'source-epoch.json';data=json.loads(p.read_text());data[str((ROOT/COMPILED).resolve())]='0'*64;p.write_text(json.dumps(data))
    else:
        p=run/'pytest-artifacts/workers/gw0/native/bpu/native-merged.dat';data=p.read_text()
        p.write_text(data.replace("' 0\n","' 1\n",1) if fault=='nonzero-producer' else data.replace('\x01o\x02else','\x01o\x02if',1))
    with pytest.raises(AssertionError):review(run,duts=('bpu',))


def test_cli_prints_only_counts_for_large_unclassified_sets_and_exports_nothing_implicitly(integrated_baseline,monkeypatch,capsys):
    run=integrated_baseline;before={p for p in run.rglob('*') if p.is_file()}
    monkeypatch.setattr('sys.argv',['review_guard_gaps','--baseline',str(run),'--dut','bpu'])
    main()
    result=json.loads(capsys.readouterr().out)['bpu']
    assert result['unclassified_count']==1 and result['locally_classified']==120 and 'unclassified' not in result
    assert {p for p in run.rglob('*') if p.is_file()}==before
