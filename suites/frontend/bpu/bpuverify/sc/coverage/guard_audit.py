"""Exact hit / not-hit contradictions in the two SC write-buffer variants."""
from itertools import product

from bpuverify.common.coverage.local_guards import Source, claim


def source_claims():
    claims,sources = [],[]
    variants = (
        ('rtl/sc/WriteBuffer.sv',338,15,4,(365,399,433,467,481,517,553,589)),
        ('rtl/sc/WriteBuffer_8.sv',806,39,16,(893,1011,1129,1247,1285,1405,1525,1645)),
    )
    for file,outer,base,ways,guards in variants:
        source = Source(file)
        source.expect(outer,'if (hit) begin')
        for ordinal,guard_line in enumerate(guards):
            entry = ordinal%4
            guard = f'_GEN_{base+entry}'
            victim = f"victim == 2'h{entry}" if entry!=3 else '(&victim)'
            source.definition(guard,'~hit & '+victim)
            source.expect(guard_line,('else if' if ordinal<4 else 'if')+f' ({guard}) begin')
            first,last = guard_line+1,guard_line+1+2*ways
            fields = ('setIdx',*(f'wayMask_{way}' for way in range(ways)),*(f'wayData_{way}' for way in range(ways)))
            for line,field in enumerate(fields,first):
                source.expect(line,f'entries_0_{entry}_{field} <= io_write_0_bits_{field};')
            source.expect(last+1,'end')
            source.encloses(outer,first,last)
            assert source.closing(guard_line)==last+1
            # Extra guards cannot make hit && !hit satisfiable.
            assert not any(hit and (not hit and selected) for hit,selected in product((False,True),repeat=2))
            assert any(not hit and selected for hit,selected in product((False,True),repeat=2))
            claims.append(claim(file,first,last,guard_line,'if','outer-hit-and-inner-not-hit-assignment'))
        sources.append(dict(file=file,sha256=source.sha256))
    assert sum(item['last']-item['first']+1 for item in claims)==336
    return claims,sources
