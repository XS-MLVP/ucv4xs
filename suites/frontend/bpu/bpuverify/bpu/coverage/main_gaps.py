"""Source/native associations for Main entry-copy paths, not reachability proofs.

Extract complete payload copies and their lexical owners instead of assigning
meaning to fixed line ranges. A storage rank is not a semantic event: only a
checked input/effect/consumer scenario can establish its actual cause.
"""
from collections import Counter
from hashlib import sha256
import re

from bpuverify.common.coverage.rtl import _covered_lines

SOURCE='rtl/bpu/WriteBuffer_4.sv'
FIELDS=('hit','setIdx','entry_tag','entry_attribute_branchType','entry_attribute_rasAction',
    'entry_position','entry_targetCarry_value','entry_targetLowerBits')
CROSS='cross-owner-copy-candidate'
ARBITRATION='dual-entry-arbitration-candidate'
OWN='own-owner-update-candidate'


def copy_catalog(text):
    """Supported compiled begin/end copy blocks; fail closed on other shapes."""
    lines=[line.split('//',1)[0].strip() for line in text.splitlines()]
    hit_gates={}
    for port in (1,2,3):
        pattern=rf'(?:wire\s+)?(\w+)\s*=\s*io_write_{port}_valid\s*&\s*\(\|hitMaskUInt_{port}\);'
        found=[m[1] for line in lines if (m:=re.fullmatch(pattern,line))]
        if len(found)!=1:raise ValueError('unique competing entry-input hit gate required')
        header=f'if ({found[0]}) begin'
        if header not in lines:raise ValueError('competing entry-input hit gate has no lexical branch')
        hit_gates[header]=port
    if lines.count(next(h for h,p in hit_gates.items() if p==3))!=1:
        raise ValueError('last-entry-input hit gate has no unique lexical branch')
    modules=[number for number,line in enumerate(lines,1) if line.startswith('module WriteBuffer_4(')]
    if len(modules)!=1:raise ValueError('one compiled Main WriteBuffer module required')
    contexts={};stack=[];closed=None
    for number,line in enumerate(lines,1):
        # Global random-initialization macro definitions are not module blocks.
        if number<modules[0]:
            contexts[number]=();continue
        # Only generated lexical blocks are supported, not arbitrary SV.
        tokens=re.findall(r'\bbegin\b|\bend\b',line)
        for token in tokens:
            if token=='end':
                if not stack:raise ValueError('unmatched end in Main copy source')
                closed=stack.pop()
            else:
                first=number;header=line
                if not line.startswith(('if (','else if (','else begin','always ','initial ','for (')):
                    # Complete a generated multiline if header without
                    # mistaking the final continuation for its source anchor.
                    while first>1 and not lines[first-1].startswith(('if (','else if (')):
                        first-=1
                        if any(mark in lines[first-1] for mark in (';','begin','end')):
                            raise ValueError(f'unsupported multiline Main block header at {number}: {line!r}, boundary={first}')
                    header=' '.join(lines[first-1:number])
                anchor=closed['line'] if header=='else begin' and closed else first
                stack.append(dict(line=first,anchor=anchor,header=header))
        contexts[number]=tuple(dict(item) for item in stack)
    if stack:raise ValueError('unclosed Main copy source block')
    result=[]
    for first,line in enumerate(lines,1):
        match=re.fullmatch(r'entries_([0-3])_([0-3])_hit\s*<=\s*io_write_([0-3])_bits_hit;',line)
        if not match:continue
        owner,rank,port=map(int,match.groups());parts=[];last=first
        # Wrapped RHS lines do not consume a field; collect all eight statements.
        while ''.join(parts).count(';')<len(FIELDS):
            if last>len(lines):raise ValueError('incomplete Main entry payload copy')
            parts.append(lines[last-1]);last+=1
        body=re.sub(r'\s+','', ' '.join(parts));last-=1
        wanted=''.join(f'entries_{owner}_{rank}_{field}<=io_write_{port}_bits_{field};' for field in FIELDS)
        if body!=wanted:raise ValueError(f'partial or mixed-source Main payload copy at {first}')
        parents=contexts[first]
        if not parents:raise ValueError('Main payload copy has no lexical owner')
        branch=parents[-1]
        if not (branch['header'].startswith(('if (','else if (')) or branch['header']=='else begin'):
            raise ValueError('Main payload copy is not immediately branch-owned')
        if any(contexts[n]!=parents for n in range(first,last+1)):
            raise ValueError('Main payload copy crosses a lexical boundary')
        competing=any(hit_gates.get(item['header'],-1)>owner for item in parents)
        family=CROSS if owner!=port else ARBITRATION if competing else OWN
        result.append(dict(owner=owner,rank=rank,write_port=port,family=family,
            first=first,last=last,introducer=branch['line'],anchor=branch['anchor'],
            header=branch['header'],ancestors=parents))
    if not result:raise ValueError('no complete Main payload copy found')
    return result


def associate(rows,points,text,*,source_path):
    """Associate every actual zero DA key and ALL of its native producers.

    Else-only control producers may share the source line with a copy's if
    producer. They are recorded as control-only, not as executed assignments.
    The result grants no functional credit and excludes no denominator row.
    """
    catalog=copy_catalog(text);lines=text.splitlines();missing={row['line']:row for row in rows if row['file']==SOURCE}
    if len(missing)!=sum(row['file']==SOURCE for row in rows):raise ValueError('duplicate Main native DA key')
    assignments={};used={}
    for line,row in missing.items():
        if not 0<line<=len(lines) or lines[line-1].strip()!=row['verilog'].strip():
            raise ValueError('stale Main native source text')
        matches=[(i,copy) for i,copy in enumerate(catalog) if copy['introducer']<=line<=copy['last']]
        if len(matches)!=1:raise ValueError(f'unmapped or overlapping Main source-copy key: {line}')
        index,copy=matches[0];assignments[line]=index;used[index]=copy
    producers=[];seen=set();descriptors=set()
    for fields,count in points:
        if fields.get('f')!=source_path:continue
        relevant=_covered_lines(fields)&missing.keys()
        if not relevant:continue
        descriptor=tuple(sorted(fields.items()))
        if descriptor in descriptors:raise ValueError('duplicate native Main producer')
        descriptors.add(descriptor)
        if fields.get('page','').partition('/')[0] not in ('v_line','v_branch'):
            raise ValueError('Main DA association requires native line/branch producers')
        indices={assignments[line] for line in relevant}
        if len(indices)!=1:raise ValueError('one native producer crosses different Main copy blocks')
        index=indices.pop();copy=used[index];anchor=int(fields['l']);arm=fields.get('o')
        if count!=0:raise ValueError('current missing DA key has a nonzero native producer')
        control_only=not any(copy['first']<=line<=copy['last'] for line in relevant)
        expected_anchor=copy['introducer'] if arm in ('if','elsif') or control_only else copy['anchor']
        if arm not in ('if','elsif','else') or anchor!=expected_anchor:
            raise ValueError('native arm/anchor does not identify the lexical Main copy')
        if not control_only and (arm=='else')!=(copy['header']=='else begin'):
            raise ValueError('native arm contradicts the Main source branch')
        seen.update(relevant)
        producers.append(dict(page=fields['page'],anchor=anchor,arm=arm,span=fields.get('S',''),
            context=fields.get('h',''),count=count,control_only=control_only,
            missing_lines=sorted(relevant),copy=index,family=copy['family']))
    if seen!=missing.keys():raise ValueError('missing native producer; never infer one from source text alone')
    return dict(format='bpu-main-copy-source-native-association',version=1,
        scope='source-path candidates only; NOT reachability, unreachability, defect-blocking or functional PASS',
        source=SOURCE,source_sha256=sha256(text.encode()).hexdigest(),raw_missing=len(missing),
        candidate_DA_counts=dict(Counter(used[index]['family'] for index in assignments.values())),
        missing_line_to_copy={str(line):index for line,index in sorted(assignments.items())},
        copies=used,native_producers=producers,native_producer_count=len(producers),
        native_denominator_unchanged=True,functional_pass_credit=False,whole_design_formal_claim=False,
        rank_does_not_prove_simultaneous_pending_records=True)


def producer_witnesses(producers,points,*,source_path):
    """Match exact native signatures across UT contexts; never imply correctness.

    Ignoring the hierarchy here intentionally asks whether *any* standalone
    context observed the same compiled arm/span, not whether a BPU instance or
    an integrated FTQ input can do so. Callers must qualify the source/build,
    input-test statuses and artifact receipts before interpreting the counts.
    """
    counts=Counter()
    for fields,count in points:
        if fields.get('f')!=source_path:continue
        kind=fields.get('page','').partition('/')[0]
        if kind not in ('v_line','v_branch'):continue
        key=kind,int(fields['l']),fields.get('o'),fields.get('S','')
        if count<0:raise ValueError('negative native producer count')
        counts[key]+=count
    result=[]
    for producer in producers:
        key=producer['page'].partition('/')[0],producer['anchor'],producer['arm'],producer['span']
        result.append(dict(anchor=producer['anchor'],arm=producer['arm'],span=producer['span'],
            control_only=producer['control_only'],signature_present=key in counts,
            standalone_count=counts.get(key,0),observed=counts.get(key,0)>0))
    return result
