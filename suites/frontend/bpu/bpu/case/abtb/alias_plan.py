"""Pilot intents and strict input qualification, independent of provider results."""
from copy import deepcopy
from suites.frontend.bpu.bpu.model.abtb.alias import plan

PILOT_CASES = ((0, 0), (1, 0), (2, 31), (3, 63))
ALL_CASES = tuple((bank, entry_set) for bank in range(4) for entry_set in range(64))


def checkpoint_route(pc):
    if type(pc) is not int or not 2 <= pc < 1 << 49:
        raise ValueError('representable CFI and preceding public checkpoint required')
    lead = (pc - 2) & ~15
    targets = []
    if lead & ~15 != (pc - 2) & ~15:
        targets.append((pc - 2) & ~15)
    targets.append(pc - 1)
    source = lead
    for target in targets:
        assert source & ~15 == (target - 1) & ~15 and source <= target - 1
        source = target
    assert source == pc - 1
    return dict(pc=pc, cold_lead=lead, actual_not_taken_checkpoint_targets=targets)


def programs(intent, alias=0):
    a, b = intent['taken_pairs'][alias]
    return (dict(pc=b, position=7, target=a, branch_type=3),
        dict(pc=a, position=7, target=b, branch_type=1))


def input_qualified(source, token, intent, redirect_valid, alias=0):
    a, b = intent['taken_pairs'][alias]
    return bool(token is not None and not redirect_valid
        and source['prediction']['start_pc'] == a and token['pc'] == b
        and token['mode'] == 'normal' and token['bank'] == intent['bank']
        and token['entry_set'] == intent['entry_set']
        and token['folded6'] & 15 == intent['low4_index_source_history'])


def final_comparison(program, source, rising):
    if rising['tick'] != source['meta_tick'] or not rising['public_meta']['valid']:
        raise ValueError('exact associated valid S3 metadata event required')
    expected = dict(valid=1, pc=program['pc'], taken=1, position=program['position'],
        target=program['target'], branch_type=program['branch_type'])
    return expected, {key: rising['abtb']['final'][key] for key in expected}


def qualified_fixture(bank, entry_set):
    intent = plan(bank, entry_set)
    a, b = intent['taken_pairs'][0]
    return intent, dict(prediction=dict(start_pc=a)), dict(pc=b, bank=bank,
        entry_set=entry_set, mode='normal', folded6=intent['low4_index_source_history'])
