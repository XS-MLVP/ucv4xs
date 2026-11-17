"""Identity-loss and evidence-attribution regression controls. MPL-2.0.

Synthetic migrations exercise the identity contract in
skills/pending/module-identity-and-lifecycle.md, without generated RTL or suites.
"""
from copy import deepcopy
import json

import pytest

from ucv.common import UcvError, digest, read, write
from ucv.config import Project
from ucv import modules


@pytest.fixture
def project(tmp_path):
    write(tmp_path/'ucv.json', {
        'baseline': 'new', 'suites': {}, 'profiles': {}, 'modules': 'docs/modules.json',
    })
    write(tmp_path/'dependencies/versions.json', {})
    for name, commit in (('old', 'a'*40), ('new', 'b'*40)):
        write(tmp_path/f'baselines/{name}.json', {
            'name': name, 'repository': 'https://example.test/design.git',
            'commit': commit, 'visibility': 'public', 'recursive_submodules': [],
            'patches': [], 'design': {
                'top': 'top.TopMain', 'config': 'DefaultConfig', 'num_cores': 1,
                'chisel_args': [],
            },
            'tools': {'mill': '1', 'chisel': '2', 'firtool': '3', 'java': '17'},
            'firtool_options': [],
        })
    return Project(tmp_path)


def retained_module(project, mid, name, *, parent=None, scope='public'):
    return {
        'module_id': mid, 'scope': scope, 'name': name, 'parent_id': parent,
        'lifecycle': 'active', 'aliases': [],
        'references': [f'https://example.test/contracts/{mid}'], 'tracking': {},
        'observations': [{
            'baseline': 'old', 'baseline_sha256': digest(project.baseline('old')),
            'availability': 'present', 'source': {'path': f'src/{name}.scala', 'line': 42},
            'rtl_tops': [name], 'instances': [{'path': f'XSTop.{name}'}],
            'evidence': ['old-evidence'],
        }],
        'history': [{
            'kind': 'reviewed', 'baseline': 'old', 'reason': 'Retained original scope review.',
            'evidence': ['old-evidence'],
        }],
    }


@pytest.fixture
def catalog(project):
    queue = retained_module(project, 'M-queue', 'CommitQueue', parent='M-front')
    queue['aliases'] = ['QueueV0']
    queue['tracking'] = {
        'owner': 'original-owner', 'tasks': [{'id': 'CQ-17', 'status': 'blocked'}],
        'blocker': 'Contract migration is not reviewed.',
        'results': [{'baseline': 'old', 'verdict': 'FAIL', 'reference': 'run-old/CQ-17'}],
    }
    result = {
        'schema': 1,
        'evidence': {'old-evidence': {
            'reference': 'https://example.test/old/manifest.json', 'sha256': '1'*64,
        }},
        'modules': [
            retained_module(project, 'M-front', 'Frontend'), queue,
            retained_module(project, 'M-back', 'Backend'),
            retained_module(project, 'M-private', 'CommitQueue', scope='internal'),
        ],
    }
    write(project.root/'docs/modules.json', result)
    return result


def observed_module(key, name, *, mid=None, parent=None, availability='present'):
    found = availability in {'present', 'documented'}
    row = {
        'key': key, 'name': name, 'parent_key': parent, 'availability': availability,
        'source': {'path': f'src/moved/{name}.scala', 'line': 101} if found else None,
        'rtl_tops': [name] if found else [],
    }
    if mid is not None:
        row['module_id'] = mid
    return row


def snapshot(project, *rows, coverage='partial', scope='public'):
    return {
        'schema': 1, 'scope': scope, 'baseline': 'new',
        'baseline_sha256': digest(project.baseline('new')), 'coverage': coverage,
        'evidence': {'new-evidence': {
            'reference': 'https://example.test/new/manifest.json', 'sha256': '2'*64,
        }},
        'modules': list(rows),
    }


def by_id(catalog):
    return {row['module_id']: row for row in catalog['modules']}


@pytest.mark.parametrize('identity', ['persistent-id', 'reviewed-match'])
def test_rename_and_source_move_keep_identity_history_and_manual_tracking(project, catalog, identity):
    queue = observed_module('queue-new', 'CommitStage', parent='back')
    queue['references'] = ['https://example.test/contracts/commit-stage']
    decisions = None
    if identity == 'persistent-id':
        queue['module_id'] = 'M-queue'
    else:
        decisions = {'matches': {'queue-new': {
            'module_id': 'M-queue', 'reason': 'Reviewed source move and unchanged logical role.',
        }}}
    observations = snapshot(project, observed_module('back', 'Backend', mid='M-back'), queue)
    before_catalog, before_observations = deepcopy(catalog), deepcopy(observations)

    report, updated = modules.reconcile(project, catalog, observations, decisions)

    assert report['status'] == 'READY' and not report['unresolved']
    assert set(by_id(updated)) == set(by_id(catalog))
    old, new = by_id(catalog)['M-queue'], by_id(updated)['M-queue']
    assert new['module_id'] == 'M-queue' and new['name'] == 'CommitStage'
    assert new['parent_id'] == 'M-back' and new['lifecycle'] == 'active'
    assert new['aliases'] == ['QueueV0', 'CommitQueue']
    assert new['tracking'] == old['tracking']
    assert new['history'][:len(old['history'])] == old['history']
    assert new['observations'][:-1] == old['observations']
    latest = new['observations'][-1]
    assert latest['baseline'] == 'new'
    assert latest['baseline_sha256'] == digest(project.baseline('new'))
    assert latest['source'] == queue['source'] and latest['rtl_tops'] == ['CommitStage']
    assert latest['evidence'] == ['new-evidence']
    assert 'verdict' not in latest and new['tracking']['results'][0]['baseline'] == 'old'
    assert new['references'] == old['references'] + queue['references']
    assert updated['evidence']['old-evidence'] == catalog['evidence']['old-evidence']
    kinds = next(c['kinds'] for c in report['changes'] if c['module_id'] == 'M-queue')
    assert {'renamed', 'moved', 'source-changed', 'variants-changed'} <= set(kinds)
    assert catalog == before_catalog and observations == before_observations


def test_ambiguous_same_name_stays_unresolved_and_cannot_be_applied(project, catalog):
    catalog['modules'].append(retained_module(project, 'M-other-queue', 'CommitQueue'))
    write(project.root/'docs/modules.json', catalog)
    candidate = observed_module('unknown-queue', 'CommitQueue')
    candidate['rtl_tops'] = ['UnrelatedGeneratedTop']
    observations = snapshot(project, candidate)
    path = project.root/'docs/modules.json'
    before = path.read_bytes()

    report, updated = modules.reconcile(project, catalog, observations)

    assert updated is None and report['status'] == 'NEEDS_REVIEW'
    assert len(report['unresolved']) == 1
    unresolved = report['unresolved'][0]
    assert unresolved['key'] == 'unknown-queue'
    assert set(unresolved['candidates']) == {'M-queue', 'M-other-queue'}
    assert modules.diff(project, observations) == report
    with pytest.raises(UcvError, match='unresolved identities'):
        modules.apply(project, observations, None, report['plan_sha256'])
    assert path.read_bytes() == before
    assert catalog == read(path)


@pytest.mark.parametrize('hint', ['name', 'alias', 'source', 'rtl-top'])
def test_even_a_unique_similarity_hint_needs_an_identity_decision(project, catalog, hint):
    candidate = observed_module('candidate', 'UnrelatedName')
    if hint == 'name':
        candidate['name'] = 'CommitQueue'
    elif hint == 'alias':
        candidate['name'] = 'QueueV0'
    elif hint == 'source':
        candidate['source'] = {'path': 'src/CommitQueue.scala', 'line': 99}
    else:
        candidate['rtl_tops'] = ['CommitQueue']

    report, updated = modules.reconcile(project, catalog, snapshot(project, candidate))

    assert updated is None and report['status'] == 'NEEDS_REVIEW'
    assert report['unresolved'][0]['candidates'] == ['M-queue']


def test_unresolved_parent_does_not_silently_reparent_a_known_child(project, catalog):
    observations = snapshot(
        project, observed_module('unknown-parent', 'NewContainer'),
        observed_module('queue', 'CommitQueue', mid='M-queue', parent='unknown-parent'),
    )
    report, updated = modules.reconcile(project, catalog, observations)
    assert updated is None and report['status'] == 'NEEDS_REVIEW'
    assert any(r['key'] == 'queue' and r['kind'] == 'unresolved-parent'
               for r in report['unresolved'])
    assert by_id(catalog)['M-queue']['parent_id'] == 'M-front'


@pytest.mark.parametrize('coverage', ['partial', 'documentation', 'complete'])
def test_missing_objects_remain_unobserved_without_borrowing_old_hardware(project, catalog, coverage):
    parent = observed_module('front', 'Frontend', mid='M-front',
                             availability='documented' if coverage == 'documentation' else 'present')
    report, updated = modules.reconcile(project, catalog, snapshot(project, parent, coverage=coverage))

    assert report['status'] == 'READY'
    assert set(by_id(updated)) == set(by_id(catalog))
    old, new = by_id(catalog)['M-queue'], by_id(updated)['M-queue']
    assert new['lifecycle'] == 'active' and new['parent_id'] == 'M-front'
    assert new['tracking'] == old['tracking'] and new['aliases'] == old['aliases']
    assert new['observations'][:-1] == old['observations']
    latest = new['observations'][-1]
    assert latest['baseline'] == 'new' and latest['availability'] == 'unobserved'
    assert latest['source'] is None and latest['rtl_tops'] == []
    assert not latest.get('instances') and not latest.get('actual_parent_edges')
    assert new['history'][:-1] == old['history']
    assert new['history'][-1]['kind'] == 'unobserved'
    assert by_id(updated)['M-private'] == by_id(catalog)['M-private']


@pytest.mark.parametrize('coverage', ['partial', 'documentation'])
def test_incomplete_observation_cannot_claim_absence(project, catalog, coverage):
    observations = snapshot(project, observed_module('queue', 'CommitQueue', mid='M-queue',
                                                      availability='absent'), coverage=coverage)
    with pytest.raises(UcvError, match='absence requires complete observation'):
        modules.reconcile(project, catalog, observations)


def test_documentation_cannot_claim_generated_hardware_is_present(project, catalog):
    observations = snapshot(project, observed_module('queue', 'CommitQueue', mid='M-queue'),
                            coverage='documentation')
    with pytest.raises(UcvError, match='documentation is not generated hardware evidence'):
        modules.reconcile(project, catalog, observations)


def test_complete_absence_is_not_retirement_or_a_pass(project, catalog):
    observations = snapshot(project, observed_module('queue', 'CommitQueue', mid='M-queue',
                                                      availability='absent'), coverage='complete')
    _, updated = modules.reconcile(project, catalog, observations)
    queue = by_id(updated)['M-queue']
    assert queue['lifecycle'] == 'active'
    assert queue['observations'][-1]['availability'] == 'absent'
    assert queue['tracking'] == by_id(catalog)['M-queue']['tracking']
    assert queue['tracking']['results'] == [
        {'baseline': 'old', 'verdict': 'FAIL', 'reference': 'run-old/CQ-17'},
    ]


@pytest.mark.parametrize('field,value', [
    ('tracking', {'owner': '', 'results': [{'baseline': 'new', 'verdict': 'PASS'}]}),
    ('lifecycle', 'retired'),
    ('history', []),
])
def test_scanner_input_cannot_overwrite_manual_tracking_or_lifecycle(project, catalog, field, value):
    row = observed_module('queue', 'CommitQueue', mid='M-queue')
    row[field] = value
    before = deepcopy(catalog)
    with pytest.raises(UcvError, match='observations cannot supply tracking/lifecycle'):
        modules.reconcile(project, catalog, snapshot(project, row))
    assert catalog == before


def transition_case(project, kind):
    rows = [observed_module('front', 'Frontend', mid='M-front')]
    decisions = {'add': {}, 'transitions': []}
    predecessors = ['M-queue']
    if kind == 'inlined':
        successors = ['M-front']
    elif kind == 'split':
        successors = ['M-read', 'M-write']
        rows += [observed_module('read', 'ReadQueue', parent='front'),
                 observed_module('write', 'WriteQueue', parent='front')]
        decisions['add'] = {
            'read': {'module_id': 'M-read', 'reason': 'Reviewed read-side contract boundary.'},
            'write': {'module_id': 'M-write', 'reason': 'Reviewed write-side contract boundary.'},
        }
    else:
        assert kind == 'merged'
        predecessors.append('M-back')
        successors = ['M-joined']
        rows.append(observed_module('joined', 'CombinedQueue', parent='front'))
        decisions['add'] = {'joined': {
            'module_id': 'M-joined', 'reason': 'Reviewed combined contract boundary.',
        }}
    decisions['transitions'] = [
        {'module_id': mid, 'kind': kind, 'successors': successors,
         'reason': f'Reviewed {mid} contract handoff; hardware acceptance remains open.'}
        for mid in predecessors
    ]
    return snapshot(project, *rows), decisions, predecessors, successors


@pytest.mark.parametrize('kind', ['inlined', 'split', 'merged'])
def test_successors_require_review_and_do_not_inherit_predecessor_verdicts(project, catalog, kind):
    observations, decisions, predecessors, successors = transition_case(project, kind)
    unreviewed = {**decisions, 'transitions': []}
    _, pending = modules.reconcile(project, catalog, observations, unreviewed)
    for mid in predecessors:
        assert by_id(pending)[mid]['lifecycle'] == 'active'
        assert by_id(pending)[mid]['observations'][-1]['availability'] == 'unobserved'

    report, updated = modules.reconcile(project, catalog, observations, decisions)

    assert report['status'] == 'READY'
    assert set(by_id(catalog)) <= set(by_id(updated))
    for mid in predecessors:
        old, new = by_id(catalog)[mid], by_id(updated)[mid]
        assert new['lifecycle'] == kind and new['tracking'] == old['tracking']
        assert new['observations'][:len(old['observations'])] == old['observations']
        assert new['history'][:len(old['history'])] == old['history']
        event = new['history'][-1]
        assert event['kind'] == kind and event['successors'] == successors
        assert event['baseline'] == 'new' and event['evidence'] == ['new-evidence']
        assert event['reason'] == next(t['reason'] for t in decisions['transitions']
                                       if t['module_id'] == mid)
    for mid in successors:
        successor = by_id(updated)[mid]
        assert successor['lifecycle'] == 'active'
        assert successor['observations'][-1]['availability'] == 'present'
        assert successor['tracking'] == {}
        assert not any('verdict' in observation for observation in successor['observations'])


@pytest.mark.parametrize('kind', ['inlined', 'split', 'merged'])
@pytest.mark.parametrize('missing', ['successors', 'empty-successors', 'reason', 'blank-reason'])
def test_lifecycle_transition_needs_explicit_successors_and_reason(project, catalog, kind, missing):
    observations, decisions, _, _ = transition_case(project, kind)
    change = decisions['transitions'][0]
    if missing == 'empty-successors':
        change['successors'] = []
    elif missing == 'blank-reason':
        change['reason'] = ' \t'
    else:
        del change[missing]
    before = deepcopy(catalog)
    with pytest.raises(UcvError, match='transition'):
        modules.reconcile(project, catalog, observations, decisions)
    assert catalog == before


@pytest.mark.parametrize('successors', [
    ['M-queue'], ['M-nonexistent'], ['M-front', 'M-front'], ['M-private'],
], ids=['self', 'unknown', 'duplicate', 'cross-scope'])
def test_invalid_successor_relationship_is_rejected(project, catalog, successors):
    observations, decisions, _, _ = transition_case(project, 'inlined')
    decisions['transitions'][0]['successors'] = successors
    with pytest.raises(UcvError, match='invalid successors'):
        modules.reconcile(project, catalog, observations, decisions)


def test_present_predecessor_cannot_be_declared_inlined(project, catalog):
    observations, decisions, _, _ = transition_case(project, 'inlined')
    observations['modules'].append(observed_module('queue', 'CommitQueue', mid='M-queue', parent='front'))
    with pytest.raises(UcvError, match='superseded identity still observed present'):
        modules.reconcile(project, catalog, observations, decisions)


@pytest.mark.parametrize('kind', ['inlined', 'split', 'merged'])
def test_repeated_diff_and_apply_do_not_duplicate_transitions_or_new_identities(project, catalog, kind):
    observations, decisions, _, _ = transition_case(project, kind)
    path = project.root/'docs/modules.json'
    original = path.read_bytes()
    first = modules.diff(project, observations, decisions)
    assert modules.diff(project, observations, decisions) == first
    assert path.read_bytes() == original
    result = modules.apply(project, observations, decisions, first['plan_sha256'])
    assert result['status'] == 'APPLIED' and result['updated']
    applied = path.read_bytes()
    stored = read(path)

    replay = modules.diff(project, observations, decisions)
    assert replay['status'] == 'READY' and replay['changes'] == []
    result = modules.apply(project, observations, decisions, replay['plan_sha256'])
    assert result['status'] == 'APPLIED' and not result['updated']
    assert path.read_bytes() == applied
    assert read(path) == stored


@pytest.mark.parametrize('changed', ['catalog', 'observations', 'decisions'])
def test_stale_diff_rejects_each_changed_input_without_rewriting_catalog_bytes(project, catalog, changed):
    observations = snapshot(project, observed_module('renamed', 'CommitStage'))
    decisions = {'matches': {'renamed': {
        'module_id': 'M-queue', 'reason': 'Reviewed persistent logical identity.',
    }}}
    report = modules.diff(project, observations, decisions)
    path = project.root/'docs/modules.json'
    if changed == 'catalog':
        concurrent = read(path)
        by_id(concurrent)['M-queue']['tracking']['owner'] = 'concurrent-reviewer'
        # Formatting is deliberate: rejecting a stale plan must not canonicalize it.
        path.write_text(json.dumps(concurrent, indent=4) + '\n\n')
    elif changed == 'observations':
        observations['modules'][0]['source']['line'] += 1
    else:
        decisions['matches']['renamed']['reason'] = 'Changed review scope.'
    before = path.read_bytes()

    with pytest.raises(UcvError, match='stale diff'):
        modules.apply(project, observations, decisions, report['plan_sha256'])

    assert path.read_bytes() == before
    if changed == 'catalog':
        assert by_id(read(path))['M-queue']['tracking']['owner'] == 'concurrent-reviewer'


def test_repeated_rename_application_keeps_aliases_observations_and_history_stable(project, catalog):
    observations = snapshot(project, observed_module('renamed', 'CommitStage', mid='M-queue'))
    path = project.root/'docs/modules.json'
    first = modules.diff(project, observations)
    modules.apply(project, observations, None, first['plan_sha256'])
    applied = path.read_bytes()
    with pytest.raises(UcvError, match='stale diff'):
        modules.apply(project, observations, None, first['plan_sha256'])
    assert path.read_bytes() == applied
    for _ in range(2):
        replay = modules.diff(project, observations)
        assert replay['changes'] == []
        assert not modules.apply(project, observations, None, replay['plan_sha256'])['updated']
        assert path.read_bytes() == applied


@pytest.mark.parametrize('changed', ['sha256', 'reference'])
def test_retained_evidence_cannot_be_rebound_to_another_hash_or_source(project, catalog, changed):
    observations = snapshot(project, observed_module('queue', 'CommitQueue', mid='M-queue'))
    # Reuse of exactly the retained evidence is legal; its identity is immutable.
    observations['evidence']['old-evidence'] = deepcopy(catalog['evidence']['old-evidence'])
    assert modules.reconcile(project, catalog, observations)[0]['status'] == 'READY'
    observations['evidence']['old-evidence'][changed] = (
        'f'*64 if changed == 'sha256' else 'https://example.test/replaced-evidence.json'
    )
    before = deepcopy(catalog)
    with pytest.raises(UcvError, match='cannot rewrite evidence: old-evidence'):
        modules.reconcile(project, catalog, observations)
    assert catalog == before


@pytest.mark.parametrize('route', ['explicit-id', 'reviewed-match', 'transition'])
def test_identity_and_lifecycle_decisions_cannot_cross_observation_scopes(project, catalog, route):
    row = observed_module('queue', 'CommitQueue')
    decisions = None
    if route == 'explicit-id':
        row['module_id'] = 'M-private'
    elif route == 'reviewed-match':
        decisions = {'matches': {'queue': {
            'module_id': 'M-private', 'reason': 'Same name is not the same scope.',
        }}}
    else:
        row['module_id'] = 'M-queue'
        decisions = {'transitions': [{
            'module_id': 'M-private', 'kind': 'retired', 'successors': [],
            'reason': 'A public snapshot cannot retire an internal module.',
        }]}
    with pytest.raises(UcvError, match='cross.*scopes'):
        modules.reconcile(project, catalog, snapshot(project, row), decisions)


@pytest.mark.parametrize('cycle', ['self', 'two-nodes'])
def test_new_management_tree_cycles_are_rejected(project, catalog, cycle):
    front = observed_module('front', 'Frontend', mid='M-front',
                            parent='front' if cycle == 'self' else 'queue')
    queue = observed_module('queue', 'CommitQueue', mid='M-queue', parent='front')
    before = deepcopy(catalog)
    with pytest.raises(UcvError, match='parent cycle'):
        modules.reconcile(project, catalog, snapshot(project, front, queue))
    assert catalog == before


@pytest.mark.parametrize('parent,error', [('M-private', 'parent crosses observation scopes'),
                                        ('M-queue', 'parent cycle')])
def test_corrupt_retained_tree_is_not_silently_repaired(project, catalog, parent, error):
    by_id(catalog)['M-front']['parent_id'] = parent
    with pytest.raises(UcvError, match=error):
        modules.reconcile(project, catalog, snapshot(project))


@pytest.mark.parametrize('route', ['two-explicit-ids', 'explicit-and-reviewed'])
def test_two_observations_cannot_claim_one_persistent_identity(project, catalog, route):
    first = observed_module('queue-a', 'ReadQueue', mid='M-queue')
    second = observed_module('queue-b', 'WriteQueue')
    decisions = None
    if route == 'two-explicit-ids':
        second['module_id'] = 'M-queue'
    else:
        decisions = {'matches': {'queue-b': {
            'module_id': 'M-queue', 'reason': 'A split requires separate successor identities.',
        }}}
    with pytest.raises(UcvError, match='multiple observations resolve to one ID'):
        modules.reconcile(project, catalog, snapshot(project, first, second), decisions)


@pytest.mark.parametrize('lifecycle', ['active', 'retired'])
def test_add_decision_cannot_recycle_an_existing_identity(project, catalog, lifecycle):
    old = by_id(catalog)['M-queue']
    old['lifecycle'] = lifecycle
    if lifecycle == 'retired':
        old['history'].append({
            'kind': 'retired', 'baseline': 'old', 'previous_lifecycle': 'active',
            'successors': [], 'reason': 'Historical retirement was explicitly reviewed.',
            'evidence': ['old-evidence'],
        })
        old['observations'].append({
            'baseline': 'old', 'baseline_sha256': digest(project.baseline('old')),
            'availability': 'absent', 'source': None, 'rtl_tops': [], 'evidence': ['old-evidence'],
        })
    observations = snapshot(project, observed_module('new-module', 'UnrelatedQueue'))
    decisions = {'add': {'new-module': {
        'module_id': 'M-queue', 'reason': 'A new object must not acquire historical results.',
    }}}
    before = deepcopy(catalog)
    with pytest.raises(UcvError, match='invalid match/add identity'):
        modules.reconcile(project, catalog, observations, decisions)
    assert catalog == before


def test_changed_add_replay_cannot_rebind_an_already_created_successor(project, catalog):
    observations, decisions, _, _ = transition_case(project, 'split')
    plan = modules.diff(project, observations, decisions)
    modules.apply(project, observations, decisions, plan['plan_sha256'])
    path = project.root/'docs/modules.json'
    before = path.read_bytes()
    changed = deepcopy(observations)
    read_queue = next(row for row in changed['modules'] if row['key'] == 'read')
    read_queue['source'] = {'path': 'src/unrelated/Replacement.scala', 'line': 1}
    read_queue['rtl_tops'] = ['UnrelatedHardware']

    # Accepting an exact replay must not turn all ID collisions into matches.
    with pytest.raises(UcvError, match='identity|replay'):
        modules.diff(project, changed, decisions)
    assert path.read_bytes() == before


@pytest.mark.parametrize('changed', ['commit', 'configuration', 'toolchain', 'submodules', 'options'])
def test_baseline_fingerprint_must_match_the_complete_target_manifest(project, catalog, changed):
    observations = snapshot(project, observed_module('queue', 'CommitQueue', mid='M-queue'))
    wrong = deepcopy(project.baseline('new'))
    if changed == 'commit':
        wrong['commit'] = 'c'*40
    elif changed == 'configuration':
        wrong['design']['num_cores'] = 2
    elif changed == 'toolchain':
        wrong['tools']['firtool'] = 'different-version'
    elif changed == 'submodules':
        wrong['recursive_submodules'] = [{
            'path': 'utility', 'repository': 'https://example.test/utility.git', 'commit': 'c'*40,
        }]
    else:
        wrong['firtool_options'] = ['-O=debug']
    observations['baseline_sha256'] = digest(wrong)
    before = deepcopy(catalog)
    with pytest.raises(UcvError, match='observation baseline hash mismatch'):
        modules.reconcile(project, catalog, observations)
    assert catalog == before


def test_baseline_manifest_change_after_diff_is_rejected_without_writing(project, catalog):
    observations = snapshot(project, observed_module('queue', 'CommitQueue', mid='M-queue'))
    report = modules.diff(project, observations)
    baseline = project.baseline('new')
    baseline['tools']['firtool'] = 'changed-after-review'
    write(project.root/'baselines/new.json', baseline)
    path = project.root/'docs/modules.json'
    before = path.read_bytes()
    with pytest.raises(UcvError, match='observation baseline hash mismatch'):
        modules.apply(project, observations, None, report['plan_sha256'])
    assert path.read_bytes() == before
