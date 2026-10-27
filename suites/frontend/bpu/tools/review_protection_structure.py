"""Strict local protection-array source review, NOT pipeline equivalence.

Checks the entire reviewed generated shape, not a sampled bank or a matching
module name. Unknown shapes fail closed. No native-line exclusions or hardware
PASS credit are produced; feedback qualification upstream remains unproved.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import re


class SourceShapeError(ValueError):
    pass


def require(condition,message):
    if not condition:raise SourceShapeError(message)


def compact(value):return re.sub(r'\s+','',value)


def uncomment(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*',lambda m:re.sub(r'[^\n]',' ',m[0]),text,flags=re.S)


def assignment(code,name):
    values=re.findall(r'\b'+re.escape(name)+r'\s*=(?!=)\s*([^;]+);',code)
    require(len(values)==1,f'one definition required for {name}')
    return compact(values[0])


def begin_body(code,begin):
    require(code[begin:begin+5]=='begin','expected begin token')
    depth=0
    for token in re.finditer(r'\bbegin\b|\bend\b',code[begin:]):
        depth+=1 if token[0]=='begin' else -1
        if depth==0:return begin+5,begin+token.start(),begin+token.end()
    raise SourceShapeError('unterminated source block')


@dataclass(frozen=True)
class Structure:
    module:str
    source_sha256:str
    initial:int
    maintenance:str
    rows:tuple

    @property
    def clauses(self):
        return {line:dict(index=row['index'],role=role) for row in self.rows for role,line in row['lines'].items()}


def review(text):
    code=uncomment(text);newlines=[m.start() for m in re.finditer('\n',code)]
    line=lambda offset:bisect_right(newlines,offset)+1
    definition=lru_cache(maxsize=None)(lambda name:assignment(code,name))
    modules=re.findall(r'\bmodule\s+(\w+)\s*\(',code)
    require(len(modules)==1,'exactly one generated module required')
    declarations=re.findall(r'\breg\s*\[1:0\]\s*(usefulEntries_(\d+)_(\d+)_value)\s*;',code)
    require(len(declarations)==512,'exactly512 declared protection cells required')
    states={name:(int(bank),int(offset)) for name,bank,offset in declarations}
    require(len(states)==512 and set(states.values())=={(b,o) for b in range(4) for o in range(128)},
            'complete unique protection state geometry required')

    # Both t0 and t1 read the entire full-index state. Packed order is part
    # of the check, including the highest row and each bank, not a comment.
    packed={}
    for m in re.finditer(r'\bwire\s*\[3:0\]\[1:0\]\s*(\w+)\s*=\s*([^;]+);',code):
        refs=re.findall(r'usefulEntries_(\d+)_(\d+)_value',m[2])
        if not refs:continue
        offsets={int(o) for b,o in refs};require(len(offsets)==1,'packed row aliases another row')
        offset,=offsets
        expected='{'+','.join('{usefulEntries_'+str(b)+'_'+str(offset)+'_value}' for b in (3,2,1,0))+'}'
        require(compact(m[2])==expected,'packed bank order or payload changed')
        require(offset not in packed,'duplicate packed source row');packed[offset]=m[1]
    require(set(packed)==set(range(128)),'all128 packed read rows required')
    for name,index in (('_GEN_127','io_train_t0_trainIndex_bits'),('_GEN_137','t1_trainIndex')):
        expected='{'+','.join('{'+packed[o]+'['+index+'[1:0]]}' for o in reversed(range(128)))+'}'
        require(assignment(code,name)==expected,'complete read row order or bank selection changed')
    require(assignment(code,'_GEN_138')=='_GEN_137[t1_trainIndex[8:2]]','t1 complete read index changed')
    require(assignment(code,'io_train_t0_read_useful')=='_GEN_127[io_train_t0_trainIndex_bits[8:2]]',
            't0 complete read index changed')
    require(assignment(code,'_GEN_139')=='io_train_t1_alloc_valid|io_train_t1_update_valid&io_train_t1_update_bits_usefulValid',
            'protection qualification changed')
    require(assignment(code,'_newUseful_T_8')=='(&_GEN_138)&io_train_t1_update_bits_needUseful|_GEN_138==2\'h0&~io_train_t1_update_bits_needUseful',
            'saturation boundary or direction changed')
    require(assignment(code,'_newUseful_T_13')=='io_train_t1_update_bits_needUseful?2\'(_GEN_138+2\'h1):2\'(_GEN_138-2\'h1)',
            'protection arithmetic changed')

    reset=re.search(r'\bif\s*\(reset\)\s*(begin)\b',code);require(reset is not None,'explicit reset block required')
    reset_first,reset_last,reset_end=begin_body(code,reset.start(1))
    require(not re.search(r'\bif\b',code[reset_first:reset_last]),'reset contains unreviewed conditional behavior')
    resets=re.findall(r'\b(usefulEntries_\d+_\d+_value)\s*<=\s*([^;]+);',code[reset_first:reset_last])
    require(len(resets)==512 and {name for name,rhs in resets}==set(states) and all(compact(rhs)=="2'h0" for name,rhs in resets),
            'all protection cells must reset exactly once to zero')
    require(re.match(r'\s*else\s+begin\b',code[reset_end:]) is not None,'reset priority changed')
    aging=re.search(r'\bif\s*\(io_usefulReset\)\s*(begin)\b',code)
    require(aging is not None and aging.start()>reset_end,'maintenance outside normal operation')
    aging_first,aging_last,aging_end=begin_body(code,aging.start(1))
    aged=list(re.finditer(r'\b(usefulEntries_\d+_\d+_value)\s*<=\s*([^;]+);',code[aging_first:aging_last]))
    require(len(aged)==512 and {m[1] for m in aged}==set(states),'all maintenance destinations required')
    initial=None;maintenance=None
    for m in aged:
        rhs=compact(m[2]);name=m[1]
        kind=('decrement' if rhs==name+"==2'h0?2'h0:2'("+name+"-2'h1)" else
              'halve' if rhs=="{1'h0,"+name+'[1]}' else None)
        require(kind is not None and maintenance in (None,kind),'unreviewed or mixed maintenance rule')
        maintenance=kind
    without_aging=code[aging_first:aging_last]
    for m in reversed(aged):without_aging=without_aging[:m.start()]+without_aging[m.end():]
    require(not compact(without_aging),'extra behavior in maintenance block')
    normal=re.match(r'\s*else\s+(begin)\b',code[aging_end:]);require(normal is not None,'learning must follow maintenance ELSE')
    normal_first,normal_last,_=begin_body(code,aging_end+normal.start(1))
    body=code[normal_first:normal_last]
    pattern=(r'if\s*\((?P<guard>[^;]+?)\)\s*begin\s*'
        r'(?P<allocation_choice>if\s*\(io_train_t1_alloc_valid\))\s*'
        r'(?P<allocation_initialize>(?P<state>usefulEntries_\d+_\d+_value)\s*<=\s*(?P<initial>2\x27h[12]);)\s*'
        r'(?P<saturation_choice>else\s+if\s*\(_newUseful_T_8\))\s*'
        r'(?P<saturation_preserve>(?P=state)\s*<=\s*_GEN_138;)\s*else\s*'
        r'(?P<counter_change>(?P=state)\s*<=\s*_newUseful_T_13;)\s*end')
    blocks=list(re.finditer(pattern,body));require(len(blocks)==512,'all512 exact learning blocks required')
    first=blocks[0].start();require(not re.search(r'\bif\b',body[:first]),'unreviewed extra learning guard')
    tail=body[first:]
    for m in reversed(blocks):tail=tail[:m.start()-first]+tail[m.end()-first:]
    require(not compact(tail),'extra behavior between learning blocks')
    names=[];rows=[]

    def decode(term):
        value=compact(term)
        if re.fullmatch(r'_GEN_\d+',value):value=definition(value)
        equal=re.fullmatch(r't1_trainIndex\[(1:0|8:2)\]==([27])\x27h([0-9a-fA-F]+)',value)
        if equal:
            field,width,constant=equal.groups();width=int(width);constant=int(constant,16)
            require(width==(2 if field=='1:0' else 7) and 0<=constant<1<<width,'invalid decode width or value')
            return field,constant
        reduce=re.fullmatch(r'\(&\(t1_trainIndex\[(1:0|8:2)\]\)\)',value)
        require(reduce is not None,'unreviewed bank/row predicate')
        return reduce[1],3 if reduce[1]=='1:0' else 127

    for m in blocks:
        name=m['state'];require(name in states,'learning targets undeclared state');names.append(name)
        value=int(m['initial'][-1]);require(initial in (None,value),'mixed provider allocation initial values');initial=value
        guard=compact(m['guard']);require(guard.startswith('_GEN_139&'),'common learning qualifier missing')
        terms=guard[len('_GEN_139&'):].split('&',1)
        # Bank3 uses a reduction AND inside parentheses, so split by the
        # delimiter following that complete term instead of its inner AND.
        if guard.startswith('_GEN_139&(&(t1_trainIndex[1:0]))&'):
            terms=['(&(t1_trainIndex[1:0]))',guard[len('_GEN_139&(&(t1_trainIndex[1:0]))&'):]]
        require(len(terms)==2,'exact bank and row conditions required')
        bank=decode(terms[0]);offset=decode(terms[1])
        require(bank[0]=='1:0' and offset[0]=='8:2','complete nine-bit destination decoding required')
        require(states[name]==(bank[1],offset[1]),'learning decode disagrees with its storage destination')
        rows.append(dict(index=4*offset[1]+bank[1],state=name,
            lines={role.replace('_','-'):line(normal_first+m.start(role)) for role in
                ('allocation_choice','allocation_initialize','saturation_choice','saturation_preserve','counter_change')}))
    require(Counter(names)==Counter(states.keys()),'every destination must have exactly one learning block')
    require((initial,maintenance) in ((1,'decrement'),(2,'halve')),'short/long parameter semantics mixed')
    writes=list(re.finditer(r'\b(usefulEntries_\d+_\d+_value)\s*<=',code))
    require(len(writes)==2560,'extra or missing protection state writes')
    require(all(reset_first<=m.start()<reset_last or aging_first<=m.start()<aging_last or
                normal_first<=m.start()<normal_last for m in writes),'protection write outside reviewed priority blocks')
    blocking=re.findall(r'\busefulEntries_\d+_\d+_value\s*=(?!=)\s*([^;]+);',code)
    require(all(re.fullmatch(r'_RANDOM\[[^]]+\]\[[^]]+\]',compact(rhs)) for rhs in blocking),
            'unexpected blocking protection assignment outside random initialization')
    return Structure(modules[0],sha256(text.encode()).hexdigest(),initial,maintenance,tuple(sorted(rows,key=lambda r:r['index'])))
