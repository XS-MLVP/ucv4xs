"""Synthetic copy/producer associations, never DUT coverage evidence."""
from copy import deepcopy
from pathlib import Path
import re
import pytest
from bpuverify.bpu.coverage.main_gaps import SOURCE,CROSS,ARBITRATION,OWN,copy_catalog,associate,producer_witnesses

SOURCE_PATH='/synthetic/Main.sv'


def fixture():
    text=Path(SOURCE).read_text();catalog=copy_catalog(text);lines=text.splitlines();rows=[];points=[]
    for copy in catalog:
        rows.extend(dict(file=SOURCE,line=n,verilog=lines[n-1].strip()) for n in range(copy['first'],copy['last']+1))
        arm='else' if copy['header']=='else begin' else 'if'
        fields=dict(f=SOURCE_PATH,l=str(copy['anchor']),o=arm,page='v_branch/WriteBuffer_4',
            S=f"{copy['first']}-{copy['last']}",h='synthetic-only')
        points.append((fields,0))
    return rows,points,text


def test_complete_payload_sources_not_fixed_line_ranges_define_the_candidate_families():
    rows,points,text=fixture();result=associate(rows,points,text,source_path=SOURCE_PATH)
    assert set(result['candidate_DA_counts'])=={CROSS,ARBITRATION,OWN}
    assert result['raw_missing']==len(rows) and result['native_producer_count']==len(points)
    assert not result['functional_pass_credit'] and not result['whole_design_formal_claim']
    assert result['rank_does_not_prove_simultaneous_pending_records']
    shifted='// unrelated header\n\n'+text
    before=copy_catalog(text);after=copy_catalog(shifted)
    assert [(c['family'],c['owner'],c['rank'],c['write_port']) for c in before]==[
        (c['family'],c['owner'],c['rank'],c['write_port']) for c in after]
    assert all(b['first']+2==a['first'] and b['anchor']+2==a['anchor'] for b,a in zip(before,after,strict=True))


def test_a_control_only_else_producer_is_not_labelled_as_a_complete_copy_effect():
    rows,points,text=fixture();copy=next(c for c in copy_catalog(text) if c['family']==ARBITRATION and c['header'].startswith('else if'))
    line=copy['introducer'];rows.append(dict(file=SOURCE,line=line,verilog=text.splitlines()[line-1].strip()))
    points.extend((dict(f=SOURCE_PATH,l=str(line),o=arm,page='v_branch/WriteBuffer_4',h='control-only'),0)
        for arm in ('if','else'))
    result=associate(rows,points,text,source_path=SOURCE_PATH)
    controls=[p for p in result['native_producers'] if p['control_only']]
    assert len(controls)==2 and {p['arm'] for p in controls}=={'if','else'}
    assert all(p['missing_lines']==[line] for p in controls)


@pytest.mark.parametrize('fault',('missing-producer','nonzero-producer','wrong-anchor','wrong-arm','wrong-kind',
    'duplicate-producer','wide-span','duplicate-DA','stale-source','unknown-DA'))
def test_incomplete_or_wrong_native_associations_are_rejected(fault):
    rows,points,text=fixture();rows=deepcopy(rows);points=deepcopy(points)
    if fault=='missing-producer':points.pop()
    elif fault=='nonzero-producer':points[0]=(points[0][0],1)
    elif fault=='wrong-anchor':points[0][0]['l']=str(int(points[0][0]['l'])+1)
    elif fault=='wrong-arm':points[0][0]['o']='else'
    elif fault=='wrong-kind':points[0][0]['page']='v_toggle/WriteBuffer_4'
    elif fault=='duplicate-producer':points.append(deepcopy(points[0]))
    elif fault=='wide-span':points[0][0]['S']=f"{rows[0]['line']}-{rows[-1]['line']}"
    elif fault=='duplicate-DA':rows.append(deepcopy(rows[0]))
    elif fault=='stale-source':rows[0]['verilog']='invented payload'
    else:rows.append(dict(file=SOURCE,line=1,verilog=text.splitlines()[0].strip()))
    with pytest.raises(ValueError):associate(rows,points,text,source_path=SOURCE_PATH)


@pytest.mark.parametrize('fault',('mixed-port','missing-field','wrong-field','changed-hit-gate','missing-hit-branch','unclosed-block'))
def test_unsupported_or_partial_source_copies_cannot_be_classified(fault):
    text=Path(SOURCE).read_text();copy=copy_catalog(text)[0];lines=text.splitlines()
    if fault=='mixed-port':
        lines[copy['first']-1]=lines[copy['first']-1].replace(f"io_write_{copy['write_port']}_",f"io_write_{(1+copy['write_port'])%4}_")
    elif fault=='missing-field':lines[copy['last']-1]=''
    elif fault=='wrong-field':lines[copy['last']-1]=lines[copy['last']-1].replace('_bits_entry_targetLowerBits','_bits_entry_tag')
    elif fault=='changed-hit-gate':lines=[line.replace('io_write_3_valid & (|hitMaskUInt_3);','io_write_3_valid & ~(|hitMaskUInt_3);') for line in lines]
    elif fault=='missing-hit-branch':
        symbol=re.search(r'(\w+)\s*=\s*io_write_3_valid\s*&\s*\(\|hitMaskUInt_3\);',text)[1]
        lines=[line.replace(f'if ({symbol}) begin',f'if (~{symbol}) begin') for line in lines]
    else:lines.append('begin')
    with pytest.raises(ValueError):copy_catalog('\n'.join(lines))


def test_exact_standalone_arm_span_signatures_only_show_observed_UT_paths():
    rows,points,text=fixture();result=associate(rows,points,text,source_path=SOURCE_PATH)
    points=[(dict(fields,h='standalone-context'),index+1) for index,(fields,_) in enumerate(points)]
    witnesses=producer_witnesses(result['native_producers'],points,source_path=SOURCE_PATH)
    assert len(witnesses)==len(points) and all(w['observed'] for w in witnesses)
    assert [w['standalone_count'] for w in witnesses]==list(range(1,len(points)+1))
    # Hierarchy aggregation asks whether ANY UT context executed a signature.
    more=[(dict(points[0][0],h='another-context'),7)]
    again=producer_witnesses(result['native_producers'],[*points,*more],source_path=SOURCE_PATH)
    assert again[0]['standalone_count']==8 and again[1:]==witnesses[1:]


@pytest.mark.parametrize('mismatch',('file','arm','span','kind','zero','negative'))
def test_wrong_or_absent_standalone_signature_is_not_path_evidence(mismatch):
    rows,points,text=fixture();producers=associate(rows,points,text,source_path=SOURCE_PATH)['native_producers']
    field=dict(points[0][0]);count=1
    if mismatch=='file':field['f']='/other/source.sv'
    elif mismatch=='arm':field['o']='else'
    elif mismatch=='span':field['S']='1-2'
    elif mismatch=='kind':field['page']='v_toggle/WriteBuffer'
    elif mismatch=='zero':count=0
    else:count=-1
    if mismatch=='negative':
        with pytest.raises(ValueError):producer_witnesses(producers,[(field,count)],source_path=SOURCE_PATH)
    else:
        witnesses=producer_witnesses(producers,[(field,count)],source_path=SOURCE_PATH)
        assert not witnesses[0]['observed']
