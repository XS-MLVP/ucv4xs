"""BPU-integrated AheadBTB counter traversal selected by the regression profile."""
from suites.frontend.bpu.testbenches.shared.env.pytest_plugins.regression import PROFILES

REPRESENTATIVE_COORDINATES = ((0, 0),)
PHYSICAL_COORDINATES = tuple((bank, entry_set) for bank in range(4) for entry_set in range(64))


def counter_coordinates(profile):
    if profile not in PROFILES:
        raise ValueError(f'unknown regression profile: {profile}')
    return PHYSICAL_COORDINATES if profile == 'physical' else REPRESENTATIVE_COORDINATES


def pytest_configure(config):
    config.addinivalue_line('markers', 'abtb_counter_matrix: ABTB semantic scenarios parametrized by regression scope')


def pytest_generate_tests(metafunc):
    if metafunc.definition.get_closest_marker('abtb_counter_matrix') is not None:
        coordinates = counter_coordinates(metafunc.config.getoption('regression_profile'))
        metafunc.parametrize('bank,entry_set', coordinates,
                             ids=[f'bank{bank}-set{entry_set}' for bank, entry_set in coordinates])
