"""PHR missing-key attribution, not coverage exclusion or a DUT-state model.

Local contradictory guards need no input assumption. Cursor-residue claims
are separate and conditional on reset plus genuinely owned checkpoints at
redirect/S2/S3 inputs; arbitrary externally supplied metadata is NOT covered.
Every claim still needs exact compiled-native producer/span validation.
"""
from math import gcd
import re

from bpuverify.bpu.model.path_history import WIDTH,SHIFT
from bpuverify.common.coverage.local_guards import Source,claim


SOURCE='rtl/bpu/Phr.sv'
MODEL='bpuverify/bpu/model/path_history.py'


def compact(value):return re.sub(r'\s+','',value)


def assignment(source,name,expected=None):
    pattern=r'(?<![\w])'+re.escape(name)+r'\s*=(?!=)\s*([^;]*);'
    found=re.findall(pattern,'\n'.join(source.lines))
    assert len(found)==1,('ambiguous or missing definition',name,len(found))
    value=compact(found[0])
    if expected is not None:assert value==compact(expected),('changed source definition',name,value,expected)
    return value


def residue_contract(width=WIDTH,shift=SHIFT):
    """Closure of reset/shift/hold/owned-restore, in logical cursor units."""
    if type(width) is not int or type(shift) is not int or not 0<shift<width:
        raise ValueError('history cursor geometry must be positive integers')
    divisor=gcd(width,shift)
    return dict(width=width,shift=shift,alignment=divisor,
        reachable_values=tuple(range(0,width,divisor)),
        assumptions=('reset has occurred','redirect and override checkpoints belong to this history epoch'),
        unrestricted_input_proof=False)


def local_claims(source):
    source.expect(1126,'wire         _s0_foldedPhr_T = io_s1Train_valid & io_s1Train_prediction_taken;')
    assignment(source,'s3UpdateWins','io_train_s3_overrideValid & ~io_train_redirect_valid')
    assignment(source,'s2UpdateWins','io_train_s2_overrideValid & ~io_train_redirect_valid & ~io_train_s3_overrideValid')
    assignment(source,'s1UpdateWins','_s0_foldedPhr_T & ~io_train_redirect_valid & ~io_train_s3_overrideValid & ~io_train_s2_overrideValid')
    claims=[]
    for outer,condition,first,last,guard in (
        (5089,'s3UpdateWins',5094,5094,5093),
        (5097,'s2UpdateWins',5102,5102,5101),
        (5105,'s1UpdateWins',5110,5111,5109),
    ):
        source.expect(outer,('if' if condition=='s3UpdateWins' else 'else if')+f' ({condition}) begin')
        source.encloses(outer,first,last)
        expected={
            's3UpdateWins':"pendingLowBits <= io_train_s3_overrideValid ? {13{io_train_s3_prediction_taken}} & s3HashComponents_hash[14:2] ^ io_train_s3_phrMeta_phrLowBits : 13'h0; pendingShiftBits <= s3HashComponents_hash[1:0];",
            's2UpdateWins':"pendingLowBits <= io_train_s2_overrideValid ? {13{io_train_s2_prediction_taken}} & s2HashComponents_hash[14:2] ^ io_train_s2_phrMeta_phrLowBits : 13'h0; pendingShiftBits <= s2HashComponents_hash[1:0];",
            's1UpdateWins':"pendingLowBits <= io_s1Train_prediction_taken ? (io_s1Train_valid ? s1HashComponents_hash[14:2] ^ pendingPhrValue[12:0] : 13'h0) : pendingPhrValue[12:0]; pendingShiftBits <= s1HashComponents_hash[1:0];",
        }[condition]
        assert compact(''.join(source.lines[outer:source.closing(outer)-1]))==compact(expected)
        for number in range(first,last+1):
            claims.append(claim(SOURCE,number,number,guard,'cond_else','winning-update-implies-inner-valid-and-taken'))
    outers=[n for n,line in enumerate(source.lines,1) if line=='else if (_s0_foldedPhr_T) begin']
    assert len(outers)==1,('ambiguous folded-history winner',outers)
    outer,=outers
    source.expect(outer,'else if (_s0_foldedPhr_T) begin')
    for number,slot in ((5189,12),(5193,11),(5197,10),(5201,9),(5205,8),(5209,7),(5216,3),(5221,1),(5225,0)):
        source.encloses(outer,number,number)
        expected=f's0_foldedPhrReg_hist_{slot}_foldedHist <= io_s1Train_prediction_taken ? s1S0FoldedPhr_nextFoldedPhr_res_hist_{slot}_foldedHist : s1_foldedPhrReg_hist_{slot}_foldedHist;'
        assert compact(''.join(source.lines[number-4:number]))==compact(expected)
        claims.append(claim(SOURCE,number,number,number-1,'cond_else','s1-update-implies-taken-fold'))
    return claims


def cursor_sources(source):
    """All stored-pointer RHSs preserve the owned checkpoint residue class."""
    assert (WIDTH,SHIFT)==(52,2),'this source proof is for the frozen geometry'
    text='\n'.join(source.lines)
    s1='s1Update_updateResult_phrPtr_flipped_new_ptr'
    result=f'_{s1}_new_ptr_value_T_1'
    expected={
        'phrPtr_value':("6'h0",'_GEN_8','_GEN_12','_GEN_10',f'io_s1Train_prediction_taken ? {result} : s1_phrPtr_value'),
        's1_phrPtr_value':("6'h0",'_GEN_8','_GEN_12','_GEN_10',result,'phrPtr_value'),
        's2_phrMeta_phrPtr_value':("6'h0",'s1_phrPtr_value'),
    }
    for name,rhs in expected.items():
        actual=re.findall(r'(?<![\w])'+name+r'\s*<=\s*([^;]*);',text)
        assert sorted(map(compact,actual))==sorted(map(compact,rhs)),('changed pointer writers',name,actual)
    for prefix,owner,taken,output in (
        ('redirectUpdate_updateResult_phrPtr_flipped_new_ptr','io_train_redirect_bits_meta_phr_phrPtr_value','io_train_redirect_bits_taken','_GEN_8'),
        ('s2Update_updateResult_phrPtr_flipped_new_ptr','io_train_s2_phrMeta_phrPtr_value','io_train_s2_prediction_taken','_GEN_10'),
        ('s3Update_updateResult_phrPtr_flipped_new_ptr','io_train_s3_phrMeta_phrPtr_value','io_train_s3_prediction_taken','_GEN_12'),
        (s1,'s1_phrPtr_value',None,result),
    ):
        new,diff,flag=prefix+'_new_value','_'+prefix+'_diff_T_4',prefix+'_reverse_flag'
        assignment(source,new,f"{{1'h0, {owner}}} + 7'h32")
        assignment(source,diff,f"{{1'h0, {new}}} - 8'h34")
        assignment(source,flag,f"$signed({diff}) > -8'sh1")
        expression=f'{flag} ? {diff}[5:0] : {new}[5:0]'
        assignment(source,output,expression if taken is None else f'{taken} ? ({expression}) : {owner}')
    assignment(source,'_GEN_15',"{1'h0, io_train_redirect_valid ? _GEN_8 : phrPtr_value}")


def constrained_claims(source,raw):
    cursor_sources(source)
    contract=residue_contract()
    pattern=re.compile(r'phr_(\d+) <= phrWrite(Bits|LowBits)\[(\d+)\];')
    guard_pattern=re.compile(r'(?:else )?if \((_new_ptr_value_T_\d+) == 6\x27h([\dA-F]+)\)')
    seen=set();checked=set();claims=[]
    for number,line in enumerate(source.lines,1):
        match=pattern.fullmatch(line)
        if not match:continue
        cell,kind,bit=int(match[1]),match[2],int(match[3]);offset=bit+1
        key=kind,cell,bit
        assert key not in seen;seen.add(key)
        guard=guard_pattern.fullmatch(source.lines[number-2]);assert guard and int(guard[2],16)==cell
        name=guard[1]
        if name not in checked:
            expression=assignment(source,name)
            branch=re.fullmatch(r'\$signed\((\w+)\)>-8\x27sh1\?\1\[5:0\]:(\w+)\[5:0\]',expression)
            assert branch,('changed circular offset',name,expression)
            diff,new=branch.groups()
            assignment(source,new,f"_GEN_15 + 7'h{offset:X}")
            assignment(source,diff,f"{{1'h0, {new}}} - 8'h34")
            checked.add(name)
        if (cell-offset)%contract['alignment']==0:continue
        assert (SOURCE,number) in raw,('incompatible assignment is hit or lacks a native key; input constraint not established',number)
        # A last-elsif anchor can be covered by its ELSE producer even though
        # the assignment's IF arm is impossible. Never relabel that hit key.
        for point in (number-1,number):
            if (SOURCE,point) in raw:
                claims.append(claim(SOURCE,point,point,number-1,'if' if offset==1 else 'elsif',
                    'owned-checkpoint-cursor-residue'))
    wanted={(kind,cell,bit) for kind,length in (('Bits',15),('LowBits',13)) for cell in range(WIDTH) for bit in range(length)}
    assert seen==wanted,('changed write expansion',len(seen),len(wanted))
    return claims,contract
