"""Generated ABTB source-line ownership, separate from coverage counter arms."""
from collections import Counter
from collections import defaultdict
import re

CELL=re.compile(r'\btakenCounter_(\d+)_(\d+)_(\d+)_value\b')
DECLARE=re.compile(r'^\s*reg\s+(?:\[[^\]]+\]\s+)?(takenCounter_(\d+)_(\d+)_(\d+)_value)\s*;')
RESET=re.compile(r"^\s*(takenCounter_(\d+)_(\d+)_(\d+)_value) <= 2'h2;")
REQUIRED={'reset_weak_positive','reset_selection','decrement_assignment',
    'decrement_nonzero_guard','decrease_selection','increment_or_hold_guard',
    'increment_saturated_guard','increment_assignment'}


def source_index(lines):
    """Fail closed on declared cells whose exact update block is not recognized."""
    declared={tuple(map(int,match.groups()[1:])) for line in lines
        if (match:=DECLARE.match(line)) is not None}
    cells={}
    ownership={}
    for offset,line in enumerate(lines):
        match=RESET.match(line)
        if match is None:continue
        name=match[1]
        coordinate=tuple(map(int,match.groups()[1:]))
        if coordinate in cells:raise ValueError(('duplicate ABTB counter cell',coordinate))
        start=offset-1
        while start>=max(0,offset-3) and not lines[start].lstrip().startswith('if ('):
            start-=1
        if start<max(0,offset-3) or '_needReset_T' not in lines[start]:
            raise ValueError(('ABTB reset selector missing',coordinate,offset+1))
        ends=[number for number in range(offset+1,min(offset+21,len(lines)))
            if f"{name} <= {name} + 2'h1;" in lines[number]]
        if len(ends)!=1:raise ValueError(('ABTB increment assignment missing',coordinate))
        increase=ends[0]
        if increase+1>=len(lines) or lines[increase+1].strip()!='end':
            raise ValueError(('ABTB update block end missing',coordinate))
        end=increase+1
        registers={m.group(0) for row in lines[start:end+1] for m in CELL.finditer(row)}
        if registers!={name}:raise ValueError(('cross-cell ABTB block',coordinate,registers))
        roles={}
        for number in range(start,end+1):
            code=lines[number].split('//',1)[0].strip()
            if number==offset:role='reset_weak_positive'
            elif number==start:role='reset_selection'
            elif f"{name} <= {name} - 2'h1;" in code:role='decrement_assignment'
            elif f'if (|{name})' in code:role='decrement_nonzero_guard'
            elif 'if (_needIncrease_T' in code and '~t1_train_branch_taken' in code:role='decrease_selection'
            elif code.startswith('else if (~(_needIncrease_T'):role='increment_or_hold_guard'
            elif f'(&{name})' in code:role='increment_saturated_guard'
            elif number==increase:role='increment_assignment'
            elif '_needIncrease_T' in code:role='update_eligibility'
            else:role='structural_or_reset_continuation'
            roles[number+1]=role
        if not REQUIRED<=set(roles.values()):
            raise ValueError(('ABTB update roles incomplete',coordinate,roles))
        cells[coordinate]=dict(name=name,first_line=start+1,last_line=end+1,roles=roles)
        for line_number,role in roles.items():
            if line_number in ownership:raise ValueError(('overlapping ABTB blocks',line_number))
            bank,entry_set,way=coordinate
            ownership[line_number]=dict(bank=bank,set=entry_set,way=way,role=role)
    if declared!=set(cells):
        raise ValueError(('ABTB declared/update geometry mismatch',sorted(declared-set(cells)),sorted(set(cells)-declared)))
    return dict(cells=cells,lines=ownership)


def source_matrix(gaps,index):
    """Count native SF+DA keys; do not infer counter transition coverage."""
    keys=[(gap['file'],gap['line']) for gap in gaps]
    if len(keys)!=len(set(keys)):raise ValueError('duplicate native ABTB source-line gap')
    counts=defaultdict(Counter)
    roles=Counter()
    mapped=0
    for gap in gaps:
        owner=gap.get('counter_gap')
        if owner is None:continue
        coordinate=(owner['bank'],owner['set'],owner['way'])
        if coordinate not in index['cells']:raise ValueError(('unknown ABTB cell',coordinate))
        if index['lines'].get(gap['line'])!=owner:raise ValueError('ABTB source-line owner mismatch')
        counts[coordinate][owner['role']]+=1
        roles[owner['role']]+=1
        mapped+=1
    rows=[dict(bank=bank,set=entry_set,way=way,missing_source_lines=sum(counts[key].values()),
        missing_by_role=dict(sorted(counts[key].items())))
        for key in sorted(index['cells']) for bank,entry_set,way in (key,)]
    banks=sorted({key[0] for key in index['cells']})
    by_bank=[dict(bank=bank,missing_source_lines=sum(row['missing_source_lines'] for row in rows if row['bank']==bank))
        for bank in banks]
    return dict(unit='verilator_native_lcov_SF_DA_source_lines',uncovered_source_lines=len(gaps),
        mapped_source_lines=mapped,unmapped_source_lines=len(gaps)-mapped,
        geometry=dict(cells=len(index['cells']),banks=banks),
        cells_with_missing_lines=sum(bool(row['missing_source_lines']) for row in rows),
        by_role=dict(sorted(roles.items())),by_bank=by_bank,cells=rows,
        source_line_hit_does_not_prove_counter_saturation_hold=True)
