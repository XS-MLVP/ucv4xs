"""Update and subsequent prediction are different hardware event families."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

UPDATE_RULES=('increment','decrement','upper-saturation','lower-saturation',
    'strong-provider-suppressed','agreement-suppressed')


def selector_coverage(family,status):
    choices=UPDATE_RULES if family=='update' else ('provider','alternate') if family=='selection' else ()
    if not choices or status not in ('reached','checked'):
        raise ValueError('unknown TAGE selector event coverage scope')
    return CoverGroupDef(f'tage_selector_{family}_events_v1',(
        CoverPointDef('rule',{name:Bin.values(name) for name in choices}),
        CoverPointDef('alt_conf',{str(value):Bin.values(value) for value in (0,1)}),
    )).instantiate(f'kunminghu_v3.bpu.tage_selector.{family}.{status}',
        contract='genuine associated source -> independent reset-derived selector -> checked effect')


class SelectorCoverage:
    def __init__(self):
        self.groups={(family,status):selector_coverage(family,status)
            for family in ('update','selection') for status in ('reached','checked')}

    def sample(self,family,status,event,**source):
        self.groups[family,status].sample(dict(event,alt_conf=event['index']&1),metadata=dict(event,**source))

    def require(self):
        for group in self.groups.values():group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())), output/'functional-coverage-tage-selector-events.json')


def routing_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown routing coverage status')
    return CoverGroupDef('tage_selector_logical_input_routing_v1',(
        CoverPointDef('index',{str(index):Bin.values(index) for index in range(16)}),
    )).instantiate(f'kunminghu_v3.bpu.tage_selector.routing.{status}',
        contract='qualified actual source -> provider/confidence index -> complete sixteen-register commit')


class SelectorRoutingCoverage:
    def __init__(self):
        self.groups={status:routing_coverage(status) for status in ('reached','checked')}

    def sample(self,status,vote,**source):
        self.groups[status].sample(dict(index=vote['index']),metadata=dict(vote,**source))

    def require(self):
        for group in self.groups.values():group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())), output/'functional-coverage-tage-selector-routing.json')
