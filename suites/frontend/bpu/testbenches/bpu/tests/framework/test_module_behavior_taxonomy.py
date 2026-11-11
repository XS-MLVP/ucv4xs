"""Document consistency only: behavior IDs, point links and scenario notes.

This taxonomy integrity check is a selftest, not hardware or coverage credit.
Scenario reached/checked and actual verdicts belong to the runtime matrix.
"""
import json
import re
from copy import deepcopy
from collections import defaultdict

import pytest

from suites.frontend.bpu import ROOT
from ucv.layout import relocated

pytestmark = pytest.mark.selftest

MODULES = {
    'MainBTB': 'MBTB', 'Ras': 'RAS', 'Bpu 顶层': 'INT',
    'MicroBTB': 'UBTB', 'AheadBTB': 'ABTB', 'MicroTAGE': 'UTAGE',
    'TAGE': 'TAGE', 'SC': 'SC', 'ITTAGE': 'ITTAGE', 'MicroRAS': 'URAS',
}
REQUIRED_BEHAVIORS = {
    'MBTB': ('MBTB.lookup', 'MBTB.learn', 'MBTB.residency', 'MBTB.service'),
    'RAS': ('RAS.stack', 'RAS.recovery', 'RAS.retire'),
    'INT': ('BPU.select', 'BPU.learn', 'BPU.history', 'BPU.arbitrate'),
    'UBTB': ('UBTB.lookup', 'UBTB.confidence', 'UBTB.lifecycle'),
    'ABTB': ('ABTB.lookup', 'ABTB.learn', 'ABTB.residency', 'ABTB.lifecycle'),
    'UTAGE': ('UTAGE.select', 'UTAGE.learn', 'UTAGE.service'),
    'TAGE': ('TAGE.select', 'TAGE.learn', 'TAGE.service'),
    'SC': ('SC.select', 'SC.weights', 'SC.threshold'),
    'ITTAGE': ('ITTAGE.select', 'ITTAGE.region', 'ITTAGE.service'),
    'URAS': ('URAS.stack', 'URAS.recovery', 'URAS.enable'),
}
RANGE = re.compile(r'([0-9]{3})(?:[–-]([0-9]{3}))?')
BEHAVIOR = re.compile(r'`([A-Z]+\.[a-z-]+)`\s+\S.*')
SECTION = re.compile(r'^## (.+?)\n(.*?)(?=^## |\Z)', re.M | re.S)


def behavior_catalog(text):
    """Display wording may change; existing stable IDs must remain traceable.

    A newly discovered candidate behavior may have no old point yet. It must
    say 待分配 and explicitly retain its gap, not be deleted to make IDs match.
    """
    sections = set()
    catalog = {}
    for heading, body in SECTION.findall(text):
        for title, prefix in MODULES.items():
            if not heading.startswith(title + '：'):
                continue
            if prefix in sections:
                raise ValueError('duplicate module section')
            sections.add(prefix)
            classes = set()
            for line in body.splitlines():
                if not line.startswith('|') or '；' not in line.split('|', 2)[1]:
                    continue
                columns = line.split('|')
                if len(columns) != 6 or any(not cell.strip() for cell in columns[1:5]):
                    raise ValueError('behavior class lacks input/output/gap columns')
                label, ranges = columns[1].split('；', 1)
                match = BEHAVIOR.fullmatch(label.strip())
                if match is None:
                    raise ValueError('behavior needs a stable ID and display name')
                behavior = match[1]
                namespace = 'BPU' if prefix == 'INT' else prefix
                if not behavior.startswith(namespace + '.'):
                    raise ValueError('behavior belongs to a different module')
                if behavior in catalog:
                    raise ValueError('duplicate behavior family')
                classes.add(behavior)
                found = set()
                candidate = ranges.strip() == '待分配'
                if candidate and 'gap' not in columns[4]:
                    raise ValueError('candidate behavior needs an explicit gap')
                for token in (() if candidate else ranges.strip().split('、')):
                    numbers = RANGE.fullmatch(token.strip())
                    if numbers is None:
                        raise ValueError('malformed point range')
                    first, last = numbers.groups()
                    lo, hi = int(first), int(last or first)
                    if lo > hi:
                        raise ValueError('reversed feature range')
                    found.update(f'BPU-{prefix}-{value:03d}' for value in range(lo, hi + 1))
                if not candidate and not found:
                    raise ValueError('empty behavior ID')
                catalog[behavior] = dict(module=prefix, features=found, candidate=candidate)
            if not set(REQUIRED_BEHAVIORS[prefix]) <= classes:
                raise ValueError('existing stable behavior removed without review')
    if sections != set(MODULES.values()):
        raise ValueError('one or more DUTs have no behavior section')
    return catalog


def classified_points(text):
    assignments = defaultdict(set)
    for row in behavior_catalog(text).values():
        assignments[row['module']].update(row['features'])
    return assignments


def inputs():
    return (ROOT / 'docs/spec/design/module-behavior-matrix.md').read_text()


def test_all_ten_duts_and_every_hardware_id_have_a_behavior_class():
    classified = classified_points(inputs())
    assert len(classified) == 10
    assert all(all(node.startswith(f'BPU-{module}-') for node in items)
               for module, items in classified.items())


@pytest.mark.parametrize('fault', ('missing-module', 'renamed-behavior'))
def test_taxonomy_cannot_silently_omit_an_existing_or_new_point(fault):
    document = inputs()
    if fault == 'missing-module':
        document = document.replace('## SC：统计纠偏、资格与阈值', '## 未分类：统计纠偏、资格与阈值')
    else:
        document = document.replace('`MBTB.learn`', '`MBTB.unknown`')
    with pytest.raises(ValueError):
        classified_points(document)


def test_display_wording_changes_do_not_redefine_a_behavior():
    document = inputs()
    assert classified_points(document.replace('条件方向与纠正；', '条件方向学习及属性纠正；')) == classified_points(document)


def test_new_requirement_without_a_test_or_old_id_can_be_retained_as_a_gap():
    document = inputs()
    row = '\n| `MBTB.unreviewed` 新发现的候选行为；待分配 | 合同与合法域待核 | 待独立确认预期和禁止副作用 | gap：下一实验先核producer合同 |\n'
    document = document.replace('## Ras：', row + '\n## Ras：')
    assert behavior_catalog(document)['MBTB.unreviewed']['candidate']


def nonempty(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('nonempty documentary rationale required')


def local_refs(paths):
    if not isinstance(paths, list) or not paths:
        raise ValueError('at least one source reference is required')
    for path in paths:
        nonempty(path)
        target = (ROOT / path.split('::', 1)[0]).resolve()
        if path.startswith('/') or not target.is_relative_to(ROOT.resolve()):
            raise ValueError('reference must name an existing suite file')
        if not relocated(ROOT, path).is_file():
            raise ValueError('reference must name an existing suite file')


def validate_scenarios(notes, catalog):
    """Validate notes/links, never infer execution from a stored declaration.

    Ignored run artifacts need not be installed for this portable selftest.
    Historical evidence must additionally be opened and audited at review time.
    """
    if notes.get('format') != 'bpu-behavior-scenario-notes' or notes.get('version') != 1:
        raise ValueError('unknown notes format')
    baseline = notes.get('baseline', {})
    nonempty(baseline.get('name'))
    if not re.fullmatch(r'[a-f0-9]{40}', baseline.get('commit', '')) or baseline.get('config') != 'DefaultConfig':
        raise ValueError('explicit complete baseline required')
    required = {'scenario_id', 'behavior_id', 'crosses', 'feature_ids', 'design_review',
                'legal_precondition', 'stimulus_and_history', 'event', 'oracle',
                'forbidden_side_effects', 'observations', 'completion', 'controls',
                'implementation', 'evidence', 'gap'}
    seen = set()
    for row in notes['scenarios']:
        if not required <= row.keys() or row.keys() - required - {'input_fields'}:
            raise ValueError('missing fields or static verdict in design notes')
        nonempty(row['scenario_id'])
        if row['scenario_id'] in seen:
            raise ValueError('duplicate scenario identity')
        seen.add(row['scenario_id'])
        behavior_ids = [row['behavior_id'], *row['crosses']]
        if any(key not in catalog for key in behavior_ids):
            raise ValueError('scenario references an unknown behavior')
        points = set(row['feature_ids'])
        linked = set().union(*(catalog[key]['features'] for key in behavior_ids))
        if not points <= linked:
            raise ValueError('scenario point is not associated with its behaviors')
        design = row['design_review']
        if design['state'] not in ('pending-review', 'module-contract'):
            raise ValueError('unrecognized design review state')
        local_refs(design['source_refs'])
        nonempty(design['legal_scope'])
        for key in ('legal_precondition', 'event', 'completion'):
            nonempty(row[key])
        for key in ('stimulus_and_history', 'forbidden_side_effects', 'observations'):
            if not isinstance(row[key], list) or not row[key]:
                raise ValueError('missing stimulus or checking obligation')
            for text in row[key]:
                nonempty(text)
        local_refs(row['oracle']['source_refs'])
        if not row['oracle']['expected']:
            raise ValueError('missing independent expectation or pending rationale')
        implementation = row['implementation']
        if implementation['state'] not in ('not-implemented', 'implemented', 'blocked'):
            raise ValueError('unrecognized implementation state')
        if implementation['state'] == 'implemented':
            local_refs(implementation['nodeids'])
            local_refs(implementation['checker_refs'])
            if not row['controls']:
                raise ValueError('implemented example needs a declared control layer')
        elif implementation['state'] == 'not-implemented' and implementation['nodeids']:
            raise ValueError('unimplemented scenario cannot claim live test bindings')
        for control in row['controls']:
            nonempty(control['layer'])
            local_refs([control['nodeid']])
        evidence = row['evidence']
        if evidence['kind'] == 'none':
            if set(evidence) != {'kind', 'run_refs'} or evidence['run_refs']:
                raise ValueError('no-evidence record has a claimed run')
        elif evidence['kind'] == 'historical-selected':
            if set(evidence) != {'kind', 'run_refs', 'lookup_key'}:
                raise ValueError('evidence records references, not a copied verdict')
            if implementation['state'] == 'not-implemented' or not evidence['run_refs']:
                raise ValueError('historical sample requires a real test binding')
            local_refs(implementation['nodeids'])
            if evidence['lookup_key'] not in implementation['nodeids']:
                raise ValueError('historical evidence belongs to another test')
            for run in evidence['run_refs']:
                if not run['directory'].startswith('results/') or '..' in run['directory'].split('/'):
                    raise ValueError('run location must be repository-relative')
                if not re.fullmatch(r'[a-f0-9]{64}', run['source_sha256']):
                    raise ValueError('frozen run source is required')
                if type(run['seed']) is not int or run['seed'] < 1:
                    raise ValueError('true seed is required')
                nonempty(run['artifact'])
        else:
            raise ValueError('execution must reference facts, not a static PASS')
        for key in ('category', 'missing', 'impact', 'owner', 'next_action'):
            nonempty(row['gap'][key])


def scenario_inputs():
    document = inputs()
    notes = json.loads((ROOT / 'docs/spec/verification/functional/behavior-scenarios.json').read_text())
    return notes, behavior_catalog(document)


def test_example_scenarios_keep_contract_implementation_and_evidence_separate():
    notes, catalog = scenario_inputs()
    validate_scenarios(notes, catalog)
    assert [row['evidence']['kind'] for row in notes['scenarios']] == ['historical-selected', 'none', 'none']


@pytest.mark.parametrize('fault', ('unknown-behavior', 'missing-oracle', 'missing-obligation',
                                 'static-pass', 'nested-static-pass', 'missing-gap-owner',
                                 'borrowed-nodeid', 'invented-binding'))
def test_scenario_notes_reject_missing_basis_or_invented_evidence(fault):
    original, catalog = scenario_inputs()
    notes = deepcopy(original)
    row = notes['scenarios'][0]
    if fault == 'unknown-behavior':
        row['behavior_id'] = 'MBTB.unknown'
    elif fault == 'missing-oracle':
        row['oracle']['source_refs'] = []
    elif fault == 'missing-obligation':
        row['forbidden_side_effects'] = []
    elif fault == 'static-pass':
        row['status'] = 'PASS'
    elif fault == 'nested-static-pass':
        row['evidence']['status'] = 'PASS'
    elif fault == 'missing-gap-owner':
        row['gap']['owner'] = ''
    elif fault == 'borrowed-nodeid':
        row['evidence']['lookup_key'] = 'another-test'
    else:
        notes['scenarios'][1]['implementation']['nodeids'] = row['implementation']['nodeids']
    with pytest.raises(ValueError):
        validate_scenarios(notes, catalog)


def test_blocked_implementation_can_retain_real_historical_evidence():
    notes, catalog = scenario_inputs()
    notes['scenarios'][0]['implementation']['state'] = 'blocked'
    # No validator rule demands a PASS from a run; its real FAIL/ERROR/etc.
    # remains in the linked artifact and cannot be demoted by these notes.
    validate_scenarios(notes, catalog)


DESIGN_AXES = {'source', 'state', 'identity', 'address', 'capacity', 'timing', 'lifecycle', 'outcome'}
DESIGN_OUTCOMES = {'miss', 'hit', 'repair', 'rejected', 'cancelled', 'replacement', 'maintenance'}
REQUIRED_INTERACTIONS = {
    'X.s3-fasttrain-abtb-utage', 'X.abtb-valid-allnt-ubtb', 'X.s2-s3-target-only',
    'X.mbtb-nt-read-reset-full', 'X.vbtb-late-replace', 'X.phr-commonhr-guard-active',
    'X.tage-sc-provider-training-conflict', 'X.ittage-region-late-alias',
    'X.ras-uras-return-handoff', 'X.csr-derived-enable-inflight', 'X.ftq-prefix-meta-lifetime',
}


def text_list(values):
    if not isinstance(values, list) or not values:
        raise ValueError('nonempty documentary list required')
    for value in values:
        nonempty(value)


def scala_file(path):
    nonempty(path)
    if (not path.startswith('src/main/scala/xiangshan/') or not path.endswith('.scala')
            or '..' in path.split('/') or '\\' in path):
        raise ValueError('source reference must be checkout-relative Scala')


def scala_refs(refs, source_loader=None):
    if not isinstance(refs, list) or not refs:
        raise ValueError('behavior needs concrete Scala locations')
    for ref in refs:
        if set(ref) != {'file', 'lines', 'anchor'}:
            raise ValueError('Scala reference needs path, inclusive range and anchor')
        scala_file(ref['file'])
        nonempty(ref['anchor'])
        span = ref['lines']
        if (not isinstance(span, list) or len(span) != 2
                or any(type(value) is not int for value in span)
                or not 1 <= span[0] <= span[1]):
            raise ValueError('invalid Scala source range')
        if source_loader is not None:
            lines = source_loader(ref['file']).splitlines()
            if span[1] > len(lines) or ref['anchor'] not in '\n'.join(lines[span[0] - 1:span[1]]):
                raise ValueError('source range or anchor does not match checkout')


def validate_coverage_design(design, catalog, notes, source_loader=None):
    """Design completeness relative to declared families/axes, NOT DUT coverage.

    Cases inherit an explicit unmapped/none state. Mapping a case to evidence is
    a separate audited operation in behavior-scenarios.json, never a PASS here.
    Source text is optional for a portable package without a source checkout;
    the review audit must additionally check commit/config and source hashes.
    """
    root_keys = {'format', 'version', 'date', 'baseline', 'scope', 'evidence_policy',
                 'axes', 'module_axes', 'coverage_limit', 'inheritance', 'out_of_domain',
                 'behaviors', 'interactions', 'candidate_requirements'}
    if set(design) != root_keys or design['format'] != 'bpu-scala-coverage-design' or design['version'] != 1:
        raise ValueError('unknown coverage-design schema or static verdict')
    if design['baseline'] != notes['baseline']:
        raise ValueError('design and historical-note baseline differ')
    for key in ('date', 'scope', 'evidence_policy', 'coverage_limit'):
        nonempty(design[key])
    if set(design['axes']) != DESIGN_AXES:
        raise ValueError('design omits an explicit semantic dimension')
    for explanation in design['axes'].values():
        nonempty(explanation)
    inherit = design['inheritance']
    if set(inherit) != {'binding', 'evidence', 'owner', 'completion_rule'}:
        raise ValueError('ambiguous design inheritance')
    if inherit['binding'] != {'state': 'unmapped', 'nodeids': [], 'checker_refs': []}:
        raise ValueError('design-only cases cannot invent live bindings')
    if inherit['evidence'] != {'kind': 'none', 'run_refs': []}:
        raise ValueError('design-only cases cannot claim execution evidence')
    nonempty(inherit['owner'])
    nonempty(inherit['completion_rule'])
    if not design['out_of_domain']:
        raise ValueError('domain exclusions need owners and reasons')
    for row in design['out_of_domain']:
        if set(row) != {'domain', 'owner', 'reason'}:
            raise ValueError('unexplained domain exclusion')
        for value in row.values():
            nonempty(value)

    historical = {row['scenario_id']: row for row in notes['scenarios']}
    reviewed, cases = set(), {}
    behavior_keys = {'behavior_id', 'scala_refs', 'contract_refs', 'implementation_observation',
                     'partition_basis', 'legal_scope', 'observations', 'completion', 'cases'}
    case_keys = {'scenario_id', 'outcomes', 'oracle_status', 'given', 'events', 'expected',
                'forbidden', 'control', 'next_experiment'}
    for row in design['behaviors']:
        if not behavior_keys <= row.keys() or row.keys() - behavior_keys - {'existing_scenario_ids'}:
            raise ValueError('behavior lacks obligations or claims static execution')
        key = row['behavior_id']
        if key not in catalog or key in reviewed:
            raise ValueError('unknown or duplicate reviewed behavior')
        reviewed.add(key)
        scala_refs(row['scala_refs'], source_loader)
        local_refs(row['contract_refs'])
        for name in ('implementation_observation', 'partition_basis', 'legal_scope', 'completion'):
            nonempty(row[name])
        text_list(row['observations'])
        for old in row.get('existing_scenario_ids', []):
            if old not in historical or historical[old]['behavior_id'] != key:
                raise ValueError('historical example belongs to another behavior')
        if len(row['cases']) < 2:
            raise ValueError('a behavior needs distinguishable design partitions')
        for case in row['cases']:
            if set(case) != case_keys:
                raise ValueError('case lacks a checking obligation or claims a verdict')
            sid = case['scenario_id']
            if (not isinstance(sid, str) or not sid.startswith(key + '.')
                    or sid in cases or sid in historical):
                raise ValueError('case identity is duplicated, borrowed or unstable')
            if (not isinstance(case['outcomes'], list) or not case['outcomes']
                    or not set(case['outcomes']) <= DESIGN_OUTCOMES):
                raise ValueError('missing or foreign predictor outcome domain')
            if case['oracle_status'] not in {'module-contract', 'pending-confirmation'}:
                raise ValueError('implementation observation cannot silently become a golden')
            for name in ('given', 'expected', 'forbidden', 'control', 'next_experiment'):
                nonempty(case[name])
            text_list(case['events'])
            cases[sid] = catalog[key]['module']
    if reviewed != set(catalog):
        raise ValueError('one or more behavior families lack a source/scenario review')

    if set(design['module_axes']) != set(MODULES.values()):
        raise ValueError('a DUT lacks an explicit dimension review')
    assigned = set()
    for module, axes in design['module_axes'].items():
        if set(axes) != DESIGN_AXES:
            raise ValueError('a DUT dimension is unclassified')
        for linked in axes.values():
            text_list(linked)
            if any(cases.get(sid) != module for sid in linked):
                raise ValueError('dimension borrows an unknown or another DUT case')
            assigned.update(linked)
    if assigned != set(cases):
        raise ValueError('a designed partition has no declared dimension entry')

    candidate_keys = {'behavior_id', 'state', 'old_feature_ids', 'scala_refs', 'basis',
                      'missing', 'owner', 'next_action'}
    candidates = set()
    for row in design['candidate_requirements']:
        key = row['behavior_id']
        if (set(row) != candidate_keys or key in candidates or key in catalog
                or not re.fullmatch(r'[A-Z]+\.[a-z-]+', key)
                or key.split('.')[0] not in {'BPU', *MODULES.values()}):
            raise ValueError('invalid unassigned candidate requirement')
        if row['state'] != 'candidate-gap' or row['old_feature_ids']:
            raise ValueError('candidate cannot be silently promoted to a passed old point')
        scala_refs(row['scala_refs'], source_loader)
        for name in ('basis', 'missing', 'owner', 'next_action'):
            nonempty(row[name])
        candidates.add(key)

    interaction_keys = {'interaction_id', 'behavior_ids', 'source_refs', 'status', 'legal_precondition',
                        'events', 'expected', 'forbidden', 'checks', 'control', 'next_experiment'}
    interactions = set()
    for row in design['interactions']:
        if set(row) != interaction_keys:
            raise ValueError('interaction lacks joint-state obligations or claims evidence')
        key = row['interaction_id']
        if not key.startswith('X.') or key in interactions:
            raise ValueError('invalid or duplicate interaction identity')
        interactions.add(key)
        members = row['behavior_ids']
        if (len(set(members)) < 2 or len(set(members)) != len(members)
                or not set(members) <= reviewed | candidates):
            raise ValueError('interaction must identify distinct known responsibilities')
        if row['status'] != 'pending-confirmation':
            raise ValueError('unexecuted joint design cannot claim a runtime verdict')
        text_list(row['source_refs'])
        for source in row['source_refs']:
            scala_file(source)
            if source_loader is not None:
                nonempty(source_loader(source))
        for name in ('legal_precondition', 'events', 'expected', 'forbidden', 'checks',
                     'control', 'next_experiment'):
            nonempty(row[name])
    if not REQUIRED_INTERACTIONS <= interactions:
        raise ValueError('a reviewed high-risk interaction disappeared')
    return cases


def coverage_design_inputs():
    notes, catalog = scenario_inputs()
    reference = notes['coverage_design_ref']
    local_refs([reference])
    design = json.loads((ROOT / reference).read_text())
    return design, catalog, notes


def test_ten_dut_source_review_and_bounded_scenario_design_is_consistent():
    design, catalog, notes = coverage_design_inputs()
    cases = validate_coverage_design(design, catalog, notes)
    assert set(cases.values()) == set(MODULES.values())


def test_scala_locations_match_installed_checkout_without_claiming_execution():
    design, catalog, notes = coverage_design_inputs()
    checkout = ROOT / 'XiangShan'
    if not (checkout / 'src/main/scala/xiangshan/frontend/bpu/Bpu.scala').is_file():
        pytest.skip('optional Scala checkout is not installed; portable design test still runs')
    validate_coverage_design(design, catalog, notes, lambda path: (checkout / path).read_text())


@pytest.mark.parametrize('fault', (
    'missing-behavior', 'duplicate-behavior', 'missing-module-axis', 'missing-axis',
    'foreign-axis-case', 'missing-source', 'reversed-source', 'escaping-source',
    'missing-contract', 'missing-partition-basis', 'missing-forbidden', 'missing-control',
    'missing-completion', 'missing-next-experiment', 'duplicate-case', 'static-pass',
    'invented-binding', 'invented-run', 'unknown-interaction-member', 'missing-interaction',
    'interaction-static-pass', 'candidate-without-owner', 'candidate-promoted-to-old-pass',
    'foreign-outcome', 'unconfirmed-as-pass',
))
def test_coverage_design_rejects_missing_obligations_and_invented_credit(fault):
    original, catalog, notes = coverage_design_inputs()
    design = deepcopy(original)
    row = design['behaviors'][0]
    case = row['cases'][0]
    if fault == 'missing-behavior':
        design['behaviors'].pop()
    elif fault == 'duplicate-behavior':
        design['behaviors'].append(deepcopy(row))
    elif fault == 'missing-module-axis':
        del design['module_axes']['SC']
    elif fault == 'missing-axis':
        del design['module_axes']['SC']['lifecycle']
    elif fault == 'foreign-axis-case':
        design['module_axes']['SC']['source'] = [case['scenario_id']]
    elif fault == 'missing-source':
        row['scala_refs'] = []
    elif fault == 'reversed-source':
        row['scala_refs'][0]['lines'] = [218, 138]
    elif fault == 'escaping-source':
        row['scala_refs'][0]['file'] = 'src/main/scala/xiangshan/../../secrets.scala'
    elif fault == 'missing-contract':
        row['contract_refs'] = []
    elif fault == 'missing-partition-basis':
        row['partition_basis'] = ''
    elif fault == 'missing-forbidden':
        case['forbidden'] = ''
    elif fault == 'missing-control':
        case['control'] = ''
    elif fault == 'missing-completion':
        row['completion'] = ''
    elif fault == 'missing-next-experiment':
        case['next_experiment'] = ''
    elif fault == 'duplicate-case':
        row['cases'].append(deepcopy(case))
    elif fault == 'static-pass':
        case['verdict'] = 'PASS'
    elif fault == 'invented-binding':
        design['inheritance']['binding']['nodeids'] = ['invented-test']
    elif fault == 'invented-run':
        design['inheritance']['evidence']['run_refs'] = ['invented-run']
    elif fault == 'unknown-interaction-member':
        design['interactions'][0]['behavior_ids'][0] = 'MBTB.unknown'
    elif fault == 'missing-interaction':
        design['interactions'].pop()
    elif fault == 'interaction-static-pass':
        design['interactions'][0]['status'] = 'PASS'
    elif fault == 'candidate-without-owner':
        design['candidate_requirements'][0]['owner'] = ''
    elif fault == 'candidate-promoted-to-old-pass':
        design['candidate_requirements'][0]['old_feature_ids'] = ['BPU-INT-001']
    elif fault == 'foreign-outcome':
        case['outcomes'] = ['translation-fault']
    else:
        case['oracle_status'] = 'PASS'
    with pytest.raises(ValueError):
        validate_coverage_design(design, catalog, notes)


def test_source_range_checks_reject_a_checkout_that_disagrees_with_the_review():
    design, catalog, notes = coverage_design_inputs()
    with pytest.raises(ValueError, match='range or anchor'):
        validate_coverage_design(design, catalog, notes, lambda _: 'not the reviewed Scala\n')


def test_new_unassigned_requirement_remains_a_gap_without_a_test_or_feature_id():
    original, catalog, notes = coverage_design_inputs()
    design = deepcopy(original)
    candidate = deepcopy(design['candidate_requirements'][0])
    candidate['behavior_id'] = 'MBTB.new-candidate'
    design['candidate_requirements'].append(candidate)
    validate_coverage_design(design, catalog, notes)
