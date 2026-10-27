"""Review targets for this emitted WriteBuffer variant, not golden behavior.

Every item must be checked against source and native producer metadata. Keeping
the bounded review coordinates here avoids depending on deletable old reports.
"""


def counter_blocks():
    blocks = []
    def add(row,entry,port,outer,inner,otherwise,first,last,guard,definition):
        blocks.append(dict(file='rtl/tage/WriteBuffer.sv',outer_guard_line=outer,guard=guard,definition=definition,
            inner_hit_guard_line=inner,inner_else_line=otherwise,body_first_line=first,body_last_line=last,
            assignment=f'entries_{row}_{entry}_entry_takenCtr_value <= io_write_{port}_bits_entry_takenCtr_value;'))
    for entry in range(4):
        offset = 95*entry
        selected1 = ('_GEN_97','_GEN_99','_GEN_101','_GEN_102')[entry]
        selected0 = ('_GEN_25','_GEN_28','_GEN_31','(&_GEN_17)')[entry]
        add(0,entry,1,804+offset,808+offset,814+offset,815+offset,815+offset,
            f'_GEN_{129+entry}',f'hit_1 & {selected1}')
        for outer,length in ((832,2),(856,2),(885,1)):
            start = outer+offset
            add(0,entry,0,start,start+1,start+7,start+8,start+7+length,
                f'_GEN_{58+2*entry}',f'hit & ~rowIdx & {selected0}')
        selected = ('_GEN_96','_GEN_98','_GEN_100','(&_GEN_86)')[entry]
        start = 1184+34*entry
        add(1,entry,1,start,start+1,start+7,start+8,start+8,
            f'_GEN_{133+entry}',f'hit_1 & rowIdx_1 & {selected}')
        for start in (1197+34*entry,1424+20*entry):
            add(1,entry,0,start,start+1,start+7,start+8,start+8,
                f'_GEN_{66+entry}',f'hit & _GEN_{36+entry}')
        start = 1376+12*entry
        add(0,entry,0,start,start+1,start+7,start+8,start+8,
            f'_GEN_{58+2*entry}',f'hit & ~rowIdx & {selected0}')
    return blocks
