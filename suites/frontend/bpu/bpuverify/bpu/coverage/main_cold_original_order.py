"""A qualified cold source earns reached bins; a failure earns no checked bins."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.bpu.coverage.main_original_order import Coverage as OriginalCoverage
from bpuverify.bpu.model.main_cold_original_order import Program,ORDERS,PHASES,COUNTERS,RULES


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared lifetime status required')
    bins={Program(order,phase,counter).label+'.'+rule:Bin.values(Program(order,phase,counter).label+'.'+rule)
        for order in ORDERS for phase in PHASES for counter in COUNTERS for rule in RULES}
    return CoverGroupDef('bpu_cold_original_resolution_order_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.bpu.cold-original-resolution-order.'+status)


class Coverage(OriginalCoverage):
    def __init__(self,program):
        self.program,self.seen,self.closed=program,set(),False
        self.groups={status:lifetime_coverage(status) for status in ('reached','checked')}
