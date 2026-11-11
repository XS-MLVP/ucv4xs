"""Explicit production/physical scope shared by registered DUT parameter providers."""
PROFILES = ('production', 'physical')


def pytest_addoption(parser):
    parser.addoption('--regression-profile', choices=PROFILES, default='production',
                     help='production: representative ABTB coordinates and MBTB replacement indices (default); '
                          'physical: exhaustive ABTB bank/set and MBTB replacement-index traversal')
