"""Exact hit / not-hit contradictions in DefaultConfig SC write buffers."""
from itertools import product
from suites.frontend.bpu.coverage.local_guards import Source, claim


def source_claims():
    claims,sources = [],[]
    for file,base,ways in (('rtl/sc/WriteBuffer_54.sv',21,8),
                           ('rtl/sc/WriteBuffer_68.sv',69,32)):
        source = Source(file)
        outer = source.unique('if (|hitMaskUInt) begin')
        end = source.closing(outer)
        count = 0
        for entry in range(4):
            guard = f'_GEN_{base+entry}'
            victim = f"victim == 2'h{entry}" if entry!=3 else '(&victim)'
            source.definition(guard,'~(|hitMaskUInt) & '+victim)
            guards = [n for n in range(outer+1,end) if source.lines[n-1] in
                      (f'if ({guard}) begin',f'else if ({guard}) begin')]
            assert len(guards)==2,(file,entry,guards)
            for guard_line in guards:
                first,last = guard_line+1,guard_line+1+2*ways
                fields = ('setIdx',*(f'wayMask_{way}' for way in range(ways)),
                          *(f'wayData_{way}' for way in range(ways)))
                for line,field in enumerate(fields,first):
                    source.expect(line,f'entries_0_{entry}_{field} <= io_write_0_bits_{field};')
                source.expect(last+1,'end')
                source.encloses(outer,first,last)
                assert source.closing(guard_line)==last+1
                assert not any(hit and (not hit and selected)
                               for hit,selected in product((False,True),repeat=2))
                assert any(not hit and selected
                           for hit,selected in product((False,True),repeat=2))
                claims.append(claim(file,first,last,guard_line,'if',
                                    'outer-hit-and-inner-not-hit-assignment'))
                count += 1
        assert count==8
        sources.append(dict(file=file,sha256=source.sha256))
    assert sum(item['last']-item['first']+1 for item in claims)==656
    return claims,sources
