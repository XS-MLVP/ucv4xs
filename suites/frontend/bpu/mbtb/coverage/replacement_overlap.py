"""Semantic case x obligation coverage; no bank/set dimension."""
from toffee import Bin, CoverPointDef, CoverGroupDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.mbtb.model.replacement_overlap import CASES
from suites.frontend.bpu.mbtb.checker.replacement_overlap import RULES


class ReplacementCoverage:
    def __init__(self, mode, *, scope='mbtb'):
        if mode not in CASES or scope not in ('mbtb','bpu'):raise ValueError('unknown replacement coverage scope')
        self.mode=mode
        self.groups={status:CoverGroupDef(f'{scope}_latest_main_age_v1',(
            CoverPointDef('obligation',{f'{m}.{r}':Bin.values(f'{m}.{r}') for m in CASES for r in RULES}),
        )).instantiate(f'kunminghu_v3.{scope}.main-latest-age.{status}') for status in ('reached','checked')}

    def record(self,status,rule,**witness):
        self.groups[status].sample(dict(obligation=f'{self.mode}.{rule}'),metadata=dict(mode=self.mode,**witness))

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-main-latest-age.json')
