"""Semantic obligations; checked credit follows both boundary comparisons."""
from toffee import Bin, CoverGroupDef, CoverPointDef
from .types import Beat, Offer

RULES = (
    'reset', 'idle', 'invalid_count', 'grant', 'blocked', 'wrap',
    'release', 'release_no_bypass', 'walk', 'redirect',
    'walk_over_allocate', 'redirect_over_walk', 'redirect_over_allocate',
    'release_overlap_allocate', 'walk_overlap_release',
)


def obligations(state, boundary):
    if boundary.reset:
        return ('reset',)
    tx = boundary.beat
    decision = state.decision(tx)
    rules = []
    if not isinstance(tx.request, Offer):
        rules.append('idle')
    elif not 1 <= tx.request.count <= 8:
        rules.append('invalid_count')
    elif decision.valid:
        rules.append('grant')
        if decision.start + tx.request.count > 8:
            rules.append('wrap')
    else:
        rules.append('blocked')
        # Would prematurely applying release make an otherwise blocked offer fit?
        if state.following(Beat(released=tx.released)).decision(tx).valid:
            rules.append('release_no_bypass')
    if tx.released:
        rules.append('release')
    if tx.recovery is not None:
        rules.append('redirect')
        if tx.walked is not None:
            rules.append('redirect_over_walk')
        if decision.valid:
            rules.append('redirect_over_allocate')
    elif tx.walked is not None:
        rules.append('walk')
        if decision.valid:
            rules.append('walk_over_allocate')
        if tx.walked & tx.released:
            rules.append('walk_overlap_release')
    elif any(decision.mask & 1 << position for position in tx.released):
        rules.append('release_overlap_allocate')
    return tuple(rules)


class ManagerCoverage:
    def __init__(self, *, capture=True):
        schema = CoverGroupDef('vagq_manager_obligations_v1', (
            CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
        ))
        self.groups = {status: schema.instantiate(
            f'vagq.manager.{status}', capture=capture,
            contract='committed public control -> independent ring state -> paired boundary checks/v1')
            for status in ('reached', 'checked')}

    def sample(self, status, rules, cycle):
        for rule in rules:
            self.groups[status].sample({'rule': rule}, metadata={'cycle': cycle})
