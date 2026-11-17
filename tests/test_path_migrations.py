"""Splitting a testbench must not assign an old result to an arbitrary DUT."""
import pytest

from ucv.common import UcvError, write
from ucv.layout import relocated_name, relocated_names, relocated_paths


def test_split_navigation_preserves_exact_node_ownership_and_old_suffixes(tmp_path):
    write(tmp_path/'docs/path-migrations.json', {'schema': 2, 'paths': {
        'legacy': 'combined',
        'combined': ['variants/one', 'variants/two'],
        'combined/test_cases.py::test_value[One-3]': 'variants/one/test_cases.py::test_value[3]',
        'combined/test_cases.py::test_value[Two-3]': 'variants/two/test_cases.py::test_value[3]',
        'combined/test_cases.py::test_only_one': 'variants/one/test_cases.py::test_only_one',
    }})
    assert relocated_names(tmp_path, 'legacy/README.md') == [
        'variants/one/README.md', 'variants/two/README.md']
    assert relocated_paths(tmp_path, 'legacy/README.md') == [
        tmp_path/'variants/one/README.md', tmp_path/'variants/two/README.md']
    for owner, number in [('One', 'one'), ('Two', 'two')]:
        assert relocated_name(tmp_path, f'legacy/test_cases.py::test_value[{owner}-3]') == (
            f'variants/{number}/test_cases.py::test_value[3]')
    assert relocated_name(tmp_path, 'legacy/test_cases.py::test_only_one[seed-7]') == (
        'variants/one/test_cases.py::test_only_one[seed-7]')
    # Unspecified/unknown variants have multiple successors, not guessed credit.
    for name in ('legacy/test_cases.py', 'legacy/test_cases.py::test_value[Unknown-3]'):
        with pytest.raises(UcvError, match='Ambiguous path migration'):
            relocated_name(tmp_path, name)
    assert relocated_name(tmp_path, 'legacy_other/test.py') == 'legacy_other/test.py'


@pytest.mark.parametrize('paths', [
    {'old': ['one', 'two'], 'two': 'old'},
    {'old': ['one', 'old/nested']},
    {'old': ['one', 'two'], 'one': 'three', 'three': 'one'},
])
def test_a_cycle_in_any_split_branch_is_rejected(tmp_path, paths):
    write(tmp_path/'docs/path-migrations.json', {'schema': 2, 'paths': paths})
    with pytest.raises(UcvError, match='cycle'):
        relocated_names(tmp_path, 'old/test.py')


@pytest.mark.parametrize('schema,destination', [
    (1, ['one', 'two']), (2, []), (2, ['one', 'one']), (2, ['one', None]),
    (2, ['one', '']), (2, {'one': 'two'}), (True, 'one'),
])
def test_split_map_requires_an_explicit_schema_and_unique_named_successors(tmp_path, schema, destination):
    write(tmp_path/'docs/path-migrations.json', {'schema': schema, 'paths': {'old': destination}})
    with pytest.raises(UcvError, match='Invalid path migration map'):
        relocated_names(tmp_path, 'old')


def test_converging_branches_are_not_cycles_and_cannot_escape_the_workspace(tmp_path):
    paths = {'old': ['one', 'two'], 'one': 'final', 'two': 'final'}
    write(tmp_path/'docs/path-migrations.json', {'schema': 2, 'paths': paths})
    assert relocated_name(tmp_path, 'old/test.py') == 'final/test.py'
    paths['two'] = '../outside'
    write(tmp_path/'docs/path-migrations.json', {'schema': 2, 'paths': paths})
    with pytest.raises(UcvError):
        relocated_names(tmp_path, 'old/test.py')


def test_explicit_retained_branch_preserves_both_owners_but_self_alias_is_a_cycle(tmp_path):
    write(tmp_path/'docs/path-migrations.json', {'schema': 2, 'paths': {
        'old/env.py': ['old/env.py', 'variant/env.py'],
        'old/tests/test_variants.py::test_two': 'variant/tests/test_variants.py::test_two',
    }})
    assert relocated_names(tmp_path, 'old/env.py') == ['old/env.py', 'variant/env.py']
    with pytest.raises(UcvError, match='Ambiguous'):
        relocated_name(tmp_path, 'old/env.py')
    assert relocated_name(tmp_path, 'old/tests/test_variants.py::test_two') == (
        'variant/tests/test_variants.py::test_two')
    for destination in ('old', ['old']):
        write(tmp_path/'docs/path-migrations.json', {'schema': 2, 'paths': {'old': destination}})
        with pytest.raises(UcvError, match='cycle'):
            relocated_names(tmp_path, 'old')
