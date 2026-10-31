"""Stable hardware event obligations, separate reached and checked credit."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.uras.model.semantic import Action

HELD_PROFILES = tuple(old + '.' + resume for old in ('old-call', 'old-return')
                      for resume in ('resume-together', 'resume-before'))
HELD_RULES = ('distinct-original-operation', 'held-correction', 'withdrawn-proposal',
              'fresh-corrected-consumer', 'single-logical-return', 'no-old-source-resurrection')


def held_call_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('held call proof requires reached or checked status')
    return CoverGroupDef('uras_held_call_repair_v1', (
        CoverPointDef('obligation', {profile + '.' + rule: Bin.values(profile + '.' + rule)
            for profile in HELD_PROFILES for rule in HELD_RULES}),
    )).instantiate('kunminghu_v3.uras.held_call_repair.' + status,
        contract='held call correction -> withdrawn offer -> fresh consumer -> one logical pop')


class HeldCallCoverage:
    def __init__(self, profile):
        if profile not in HELD_PROFILES:
            raise ValueError('declared held-call lifetime required')
        self.profile = profile
        self.groups = {status: held_call_coverage(status) for status in ('reached', 'checked')}

    def sample(self, status, rules):
        for rule in rules:
            if rule not in HELD_RULES:
                raise ValueError('unknown held-call obligation')
            self.groups[status].sample(dict(obligation=self.profile + '.' + rule))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())),
                                  output / 'functional-coverage-held-call-repair.json')


RULES = (
    'MRAS.OP.CALL_ACCEPT', 'MRAS.OP.RETURN_ACCEPT', 'MRAS.OP.POP_PUSH_ACCEPT',
    'MRAS.CORRECTION.REPLACE_PENDING', 'MRAS.CORRECTION.FLUSH_YOUNGER',
    'MRAS.REDIRECT.FLUSH', 'MRAS.RECOVERY.BLOCK_MAIN_TOP',
    'MRAS.PIPE.ADVANCE', 'MRAS.PIPE.RETIRE', 'MRAS.PREDICT.HOLD',
    'MRAS.RETURN.CANCEL_PENDING_PUSH', 'MRAS.RETURN.UNKNOWN_DEPTH',
)


def semantic_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('MicroRAS event status must be reached or checked')
    return CoverGroupDef('uras_semantic_obligations_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.uras.semantic_events.{status}',
                  contract='public operation event -> independent stack reduction -> associated public response')


def obligations(events, before, result):
    if events.reset:
        return ()
    if events.redirect:
        return ('MRAS.REDIRECT.FLUSH',)
    rules = []
    operation = events.accept
    if events.correct_retiring is not None:
        operation = events.correct_retiring
        rules.append('MRAS.CORRECTION.FLUSH_YOUNGER')
    elif events.correct_pending is not None:
        operation = events.correct_pending
        rules.append('MRAS.CORRECTION.REPLACE_PENDING')
    if operation is not None:
        accepted = {Action.CALL: 'MRAS.OP.CALL_ACCEPT',
                    Action.RETURN: 'MRAS.OP.RETURN_ACCEPT',
                    Action.RETURN_AND_CALL: 'MRAS.OP.POP_PUSH_ACCEPT'}
        if operation.action in accepted:
            rules.append(accepted[operation.action])
        if operation.action is Action.RETURN:
            rules.append('MRAS.RETURN.CANCEL_PENDING_PUSH' if result.usable
                         else 'MRAS.RETURN.UNKNOWN_DEPTH')
        if (not before['main_trusted'] and not result.usable
                and operation.action is Action.NEUTRAL and events.correct_retiring is None):
            rules.append('MRAS.RECOVERY.BLOCK_MAIN_TOP')
    else:
        rules.append('MRAS.PREDICT.HOLD')
    if events.correct_retiring is None:
        if events.advance:
            rules.append('MRAS.PIPE.ADVANCE')
        elif events.retire and before['older'] is not None:
            rules.append('MRAS.PIPE.RETIRE')
    return tuple(rules)


class UrasSemanticCoverage:
    def __init__(self):
        self.groups = {status: semantic_coverage(status) for status in ('reached', 'checked')}

    def sample(self, status, rules, *, tick, output_tick):
        for rule in rules:
            self.groups[status].sample(dict(rule=rule),
                metadata=dict(rule=rule, input_tick=tick, output_tick=output_tick))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())), output / 'functional-coverage-semantic-events.json')
