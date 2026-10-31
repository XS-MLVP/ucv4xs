"""Transfer a bounded proof only across exactly equal compiled source bodies.

No row is excluded and no functional PASS is produced. In particular this
does not classify the remaining cross-owner paths or prove global reachability.
"""
from suites.frontend.bpu.coverage.local_guards import Source
from suites.frontend.bpu.tage.coverage.coverage_audit import source_claims as tage_claims

ORIGINAL='rtl/tage/WriteBuffer_12.sv'
COMPILED='rtl/bpu/WriteBuffer_12.sv'


def source_claims(native):
    original,compiled=Source(ORIGINAL),Source(COMPILED)
    original.expect(46,'module WriteBuffer_12(')
    compiled.expect(46,'module WriteBuffer_12(')
    assert original.lines[:45]+original.lines[46:]==compiled.lines[:45]+compiled.lines[46:], (
        'integrated WriteBuffer body differs; never transfer a local proof by module name alone')
    assert 'tage' in native['dut'], 'bounded proof transfer requires the frozen standalone TAGE report as well'
    claims,sources=tage_claims(native)
    # The source factory rechecks every enclosing guard, definition and body.
    # The caller must still match ALL real BPU native producers, not reuse
    # standalone coverage counts or infer a span from nearby Verilog text.
    return [dict(item,file=COMPILED) for item in claims],[*sources,dict(file=COMPILED,sha256=compiled.sha256)]
