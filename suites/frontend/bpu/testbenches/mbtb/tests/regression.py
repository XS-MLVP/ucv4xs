"""MainBTB replacement, entry-key and cleanup program collection axes."""
from suites.frontend.bpu.testbenches.shared.env.pytest_plugins.regression import PROFILES

MBTB_REPRESENTATIVE_INDICES = (0, 255)


def mbtb_replacement_indices(profile):
    if profile not in PROFILES:
        raise ValueError(f'unknown regression profile: {profile}')
    return tuple(range(256)) if profile == 'physical' else MBTB_REPRESENTATIVE_INDICES


def pytest_configure(config):
    config.addinivalue_line('markers', 'mbtb_replacement_matrix: MBTB replacement indices parametrized by regression scope')
    config.addinivalue_line('markers', 'mbtb_entry_key_matrix: semantic programs with physical replicas only on demand')
    config.addinivalue_line('markers', 'mbtb_cleanup_matrix: clear/correction semantic programs and optional physical replicas')


def pytest_generate_tests(metafunc):
    # Preserve the original mutually exclusive marker precedence across providers.
    if metafunc.definition.get_closest_marker('abtb_counter_matrix') is not None:
        return
    if metafunc.definition.get_closest_marker('mbtb_replacement_matrix') is not None:
        indices = mbtb_replacement_indices(metafunc.config.getoption('regression_profile'))
        metafunc.parametrize('index', indices, ids=[f'index{index}' for index in indices])
    elif metafunc.definition.get_closest_marker('mbtb_entry_key_matrix') is not None:
        from suites.frontend.bpu.testbenches.mbtb.model.two_key_programs import programs
        profile=metafunc.config.getoption('regression_profile')
        selected=programs(profile)
        metafunc.parametrize('program',selected,ids=[p.label+('.replica'+''.join(map(str,p.coordinates))
            if profile=='physical' else '') for p in selected])
    elif metafunc.definition.get_closest_marker('mbtb_cleanup_matrix') is not None:
        from suites.frontend.bpu.testbenches.mbtb.model.cleanup_programs import programs
        profile=metafunc.config.getoption('regression_profile')
        selected=programs(profile)
        metafunc.parametrize('program',selected,ids=[p.label+('.replica'+''.join(map(str,p.coordinates))
            if profile=='physical' else '') for p in selected])
