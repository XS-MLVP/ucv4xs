"""Source-bound local priority proofs for the locked DefaultConfig RTL.

Each proof validates complete assignments and exact enclosing conditions.
Native producer association is a separate required step; denominators and
functional verdicts are never changed by this diagnostic classification.
"""
from itertools import product
import json
from pathlib import Path
from suites.frontend.bpu.coverage.local_guards import Source, claim, ROOT
from suites.frontend.bpu.tage.coverage.guard_catalog import counter_blocks, SOURCE


def _truth_table(kind,*,keep_priority=True):
    result=[]
    for hit,selected,written,equal in product((False,True),repeat=4):
        path=(not(hit and selected) if keep_priority else True) and hit
        if kind=='dirty_copy':path=path and selected
        elif kind=='clean_copy':path=path and not(not written or equal or not selected)
        else:raise ValueError(kind)
        if path:result.append(dict(hit=hit,selected=selected,written=written,equal=equal))
    return result


def _copy_blocks():
    source=Source(SOURCE);blocks=[]
    for row in (0,1):
        port=1-row;hit='|hitMaskUInt_1' if port else '|hitMaskUInt'
        dirty='|_hitNotWritten_T_1' if port else '|_hitNotWritten_T'
        written='(|_hitWritten_T_3)' if port else '(|_hitWritten_T_1)'
        compare='_GEN_115' if port else '_GEN_41'
        for entry in range(4):
            guard=f'_GEN_{125+entry}' if port else f'_GEN_{63+entry}'
            selected=('_GEN_93','_GEN_95','_GEN_97','_GEN_98')[entry] if port else f'_GEN_{33+entry}'
            definition=f'({hit}) & {selected}'
            definition_line=source.definition(guard,definition)
            outers=[n for n,line in enumerate(source.lines,1) if line==f'if ({guard}) begin']
            assert len(outers)==(1 if port else 3)
            for outer in outers:
                fields=(('setIdx','entry_valid','entry_tag','entry_takenCtr_value') if port else
                        ('setIdx','entry_valid','entry_tag') if source.lines[outer].startswith('entries_') else
                        ('entry_takenCtr_value',))
                category='keys' if len(fields)==3 else 'priority'
                hit_line=source.closing(outer)+1
                source.expect(hit_line,f'else if ({hit}) begin')
                source.expect(hit_line+1,f'if ({dirty}) begin')
                dirty_guard=hit_line+2
                source.expect(dirty_guard,f'if ({selected})'+(' begin' if len(fields)>1 else ''))
                clean_guard=source.closing(hit_line+1)+1
                gate=f'~{written} | {compare} | ~{selected}'
                if port:
                    source.expect(clean_guard,f'else if ({gate}) begin')
                else:
                    clean_name=f'_GEN_{51+entry}'
                    source.definition(clean_name,gate)
                    source.expect(clean_guard,f'else if ({clean_name}) begin')
                    source.expect(clean_guard+1,'end')
                otherwise=source.closing(clean_guard)+1
                source.expect(otherwise,'else'+(' begin' if len(fields)>1 else ''))
                for kind,copy_guard,first in (('dirty_copy',dirty_guard,dirty_guard+1),
                                             ('clean_copy',clean_guard,otherwise+1)):
                    last=first+len(fields)-1
                    for offset,field in enumerate(fields):
                        source.expect(first+offset,f'entries_{row}_{entry}_{field} <= io_write_{port}_bits_{field};')
                    source.encloses(hit_line,first,last)
                    if len(fields)>1:source.expect(last+1,'end')
                    assert not _truth_table(kind)
                    control=_truth_table(kind,keep_priority=False);assert control
                    blocks.append(dict(file=SOURCE,row=row,entry=entry,write_port=port,category=category,
                        kind=kind,priority_guard_line=outer,priority_definition_line=definition_line,
                        priority_definition=f'{guard} = {definition}',later_hit_guard_line=hit_line,
                        copy_guard_line=copy_guard,body_first_line=first,body_last_line=last,
                        path_constraint='!(H && S) && H && S' if kind=='dirty_copy' else '!(H && S) && H && !(!W || C || !S)',
                        two_state_valuations_checked=16,satisfying_valuations=0,
                        negative_control_without_priority_witness=control[0]))
    return blocks


def _rows(blocks):
    return {(b['file'],n) for b in blocks for n in range(b['body_first_line'],b['body_last_line']+1)}


def _audit(native,*,keys=False):
    native=json.loads((ROOT/'results/rtl-line-coverage.json').read_text()) if native is None else native
    copies=_copy_blocks();prior=counter_blocks()
    if keys:prior += [b for b in copies if b['category']=='priority']
    blocks=[b for b in copies if b['category']==('keys' if keys else 'priority')]
    older,added=_rows(prior),_rows(blocks)
    raw={(v['file'],v['line']) for v in native['dut']['tage']['uncovered_rtl_source_lines']}
    assert len(blocks)==(8 if keys else 24)
    assert len(older)==(88 if keys else 40) and len(added)==(24 if keys else 48)
    assert not older&added and older|added<=raw
    return dict(format='bpu-generated-rtl-key-copy-priority-audit' if keys else 'bpu-generated-rtl-priority-unreachable-audit',
        version=1,generated_at=native['generated_at'],dut='tage',
        proof_scope='Exact local two-state priority contradictions, not full RTL reachability',
        native_line_coverage=native['dut']['tage']['source_lines'],native_denominator_unchanged=True,
        raw_uncovered_source_lines=len(raw),prior_classified_assignment_lines=len(older),
        additional_classified_assignment_lines=len(added),combined_classified_assignment_lines=len(older|added),
        not_classified_remaining_source_lines=len(raw-older-added),
        classification_does_not_prove_other_lines_reachable=True,blocks=blocks)


def audit(native=None):return _audit(native)

def audit_key_copies(native=None):return _audit(native,keys=True)


def source_claims(native):
    source=Source(SOURCE);claims=[]
    for block in counter_blocks():
        # The outer guard contains H; the literal-copy ELSE requires !H.
        hit='|hitMaskUInt_1' if block['write_port'] else '|hitMaskUInt'
        source.definition(block['guard'],block['definition'])
        source.expect(block['inner_hit_guard_line'],f'if ({hit}) begin')
        assert not any(value and not value for value in (False,True))
        claims.append(claim(SOURCE,block['body_first_line'],block['body_last_line'],
            block['inner_hit_guard_line'],'else','outer-hit-and-inner-not-hit-counter'))
    for block in audit(native)['blocks']+audit_key_copies(native)['blocks']:
        first,last=block['body_first_line'],block['body_last_line']
        if block['kind']=='clean_copy' and source.lines[first-2]=='else begin':first-=1
        claims.append(claim(SOURCE,first,last,block['copy_guard_line'],
            'if' if block['kind']=='dirty_copy' else 'else','priority-excluded-'+block['kind']))
    assert sum(item['last']-item['first']+1 for item in claims)==120
    return claims,[dict(file=SOURCE,sha256=source.sha256)]


if __name__=='__main__':print(json.dumps(audit(),indent=2))
