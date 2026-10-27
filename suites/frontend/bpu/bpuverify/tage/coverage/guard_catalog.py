"""Bounded review targets for the locked DefaultConfig WriteBuffer.

Line numbers are located in the current source. The expected conditions,
copy fields and multiplicities remain explicit and are checked by the audit.
"""
from bpuverify.common.coverage.local_guards import Source

SOURCE='rtl/tage/WriteBuffer.sv'


def counter_blocks():
    source=Source(SOURCE);blocks=[]
    for entry in range(4):
        selected0=f'_GEN_{22+3*entry}' if entry<3 else '(&_GEN_21)'
        selected1=('_GEN_92','_GEN_94','_GEN_96','(&_GEN_91)')[entry]
        for row,port,guard,definition,count in (
            (0,1,f'_GEN_{125+entry}',f'(|hitMaskUInt_1) & '+('_GEN_93','_GEN_95','_GEN_97','_GEN_98')[entry],1),
            (0,0,f'_GEN_{55+2*entry}',f'(|hitMaskUInt) & ~rowIdx & {selected0}',4),
            (1,1,f'_GEN_{129+entry}',f'(|hitMaskUInt_1) & rowIdx_1 & {selected1}',1),
            (1,0,f'_GEN_{63+entry}',f'(|hitMaskUInt) & _GEN_{33+entry}',2),
        ):
            source.definition(guard,definition)
            hit='|hitMaskUInt_1' if port else '|hitMaskUInt'
            outers=[n for n,line in enumerate(source.lines,1) if line==f'if ({guard}) begin']
            found=[]
            for outer in outers:
                inner=outer+(4 if row==0 and port==1 else 1)
                if source.lines[inner-1]!=f'if ({hit}) begin':continue
                otherwise=source.closing(inner)+1
                assert source.lines[otherwise-1]=='else'
                first=otherwise+1;last=first
                while not source.lines[last-1].endswith(';'):last+=1
                assignment=f'entries_{row}_{entry}_entry_takenCtr_value <= io_write_{port}_bits_entry_takenCtr_value;'
                assert ''.join(''.join(source.lines[first-1:last]).split())==''.join(assignment.split())
                source.encloses(outer,first,last)
                found.append(dict(file=SOURCE,row=row,entry=entry,write_port=port,
                    outer_guard_line=outer,guard=guard,definition=definition,
                    inner_hit_guard_line=inner,inner_else_line=otherwise,
                    body_first_line=first,body_last_line=last,assignment=assignment))
            assert len(found)==count,(row,entry,port,len(found),count)
            blocks.extend(found)
    return blocks
