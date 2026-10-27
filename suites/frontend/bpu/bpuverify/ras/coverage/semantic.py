"""Combined stack actions: accepted source versus independent consumer check."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


ROLES = ('speculation', 'recovery', 'retirement')


def semantic_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('RAS semantic event status must be reached or checked')
    return CoverGroupDef('ras_pop_and_push_v1', (
        CoverPointDef('role', {role: Bin.values(role) for role in ROLES}),
    )).instantiate(f'kunminghu_v3.ras.pop_and_push.{status}',
        contract='owned source -> pop then push -> independently compared speculative/recovery or retained committed consumer')


class RasActionCoverage:
    def __init__(self):
        self.groups = {status: semantic_coverage(status) for status in ('reached', 'checked')}
        self.pending = {}

    def accept(self, events, model, tick):
        if events.reset:
            self.pending.clear()
            return
        sources = []
        if model.last_applied == ('speculation', 3, events.address):
            sources.append(('speculation', events.address, tick + 1))
        if events.enabled and events.recovery is not None and events.recovery.action == 3:
            sources.append(('recovery', events.recovery.address, tick + 3))
        if events.enabled and events.retirement is not None and events.retirement.action == 3:
            source = model.pending_retirement
            if source is not None:
                sources.append(('retirement', source.address, None))
        for role, address, due in sources:
            witness = dict(role=role, address=address, accepted_tick=tick + 1, due_tick=due,
                           retirement_required=model.retirements + int(role == 'retirement'))
            self.pending[role] = witness
            self.groups['reached'].sample(dict(role=role), metadata=witness)

    def consume(self, model, tick):
        for role, witness in tuple(self.pending.items()):
            if model.projection['top'] * 2 != witness['address']:
                continue
            if role == 'retirement':
                # An outstanding speculative call with the same target is not
                # evidence that the combined action updated committed storage.
                if (model._live(model.program.head, model.program)
                        or model.program.head.group % 8 != model.committed_head
                        or model.retirements < witness['retirement_required']):
                    continue
            elif witness['due_tick'] != tick:
                continue
            self.groups['checked'].sample(dict(role=role), metadata=dict(witness, checked_tick=tick))
            del self.pending[role]

    def write(self, output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())), output / 'functional-coverage-pop-and-push.json')
