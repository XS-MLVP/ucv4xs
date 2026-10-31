"""Explicit regression scope; physical replication is not semantic coverage."""
import pytest

PROFILES = ('production', 'physical')
REPRESENTATIVE_COORDINATES = ((0, 0),)
PHYSICAL_COORDINATES = tuple((bank, entry_set) for bank in range(4) for entry_set in range(64))
MBTB_REPRESENTATIVE_INDICES = (0, 255)


def counter_coordinates(profile):
    if profile not in PROFILES:
        raise ValueError(f'unknown regression profile: {profile}')
    return PHYSICAL_COORDINATES if profile == 'physical' else REPRESENTATIVE_COORDINATES


def mbtb_replacement_indices(profile):
    if profile not in PROFILES:
        raise ValueError(f'unknown regression profile: {profile}')
    return tuple(range(256)) if profile == 'physical' else MBTB_REPRESENTATIVE_INDICES


def pytest_addoption(parser):
    parser.addoption('--regression-profile', choices=PROFILES, default='production',
                     help='production: representative ABTB coordinates and MBTB replacement indices (default); '
                          'physical: exhaustive ABTB bank/set and MBTB replacement-index traversal')


def pytest_configure(config):
    config.addinivalue_line('markers', 'abtb_counter_matrix: ABTB semantic scenarios parametrized by regression scope')
    config.addinivalue_line('markers', 'mbtb_replacement_matrix: MBTB replacement indices parametrized by regression scope')
    config.addinivalue_line('markers', 'mbtb_entry_key_matrix: semantic programs with physical replicas only on demand')
    config.addinivalue_line('markers', 'mbtb_cleanup_matrix: clear/correction semantic programs and optional physical replicas')


def pytest_generate_tests(metafunc):
    if metafunc.definition.get_closest_marker('abtb_counter_matrix') is not None:
        coordinates = counter_coordinates(metafunc.config.getoption('regression_profile'))
        metafunc.parametrize('bank,entry_set', coordinates,
                             ids=[f'bank{bank}-set{entry_set}' for bank, entry_set in coordinates])
    elif metafunc.definition.get_closest_marker('mbtb_replacement_matrix') is not None:
        indices = mbtb_replacement_indices(metafunc.config.getoption('regression_profile'))
        metafunc.parametrize('index', indices, ids=[f'index{index}' for index in indices])
    elif metafunc.definition.get_closest_marker('mbtb_entry_key_matrix') is not None:
        from suites.frontend.bpu.mbtb.model.two_key_programs import programs
        profile=metafunc.config.getoption('regression_profile')
        selected=programs(profile)
        metafunc.parametrize('program',selected,ids=[p.label+('.replica'+''.join(map(str,p.coordinates))
            if profile=='physical' else '') for p in selected])
    elif metafunc.definition.get_closest_marker('mbtb_cleanup_matrix') is not None:
        from suites.frontend.bpu.mbtb.model.cleanup_programs import programs
        profile=metafunc.config.getoption('regression_profile')
        selected=programs(profile)
        metafunc.parametrize('program',selected,ids=[p.label+('.replica'+''.join(map(str,p.coordinates))
            if profile=='physical' else '') for p in selected])
