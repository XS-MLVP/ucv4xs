"""Two logical counter histories, including a separately serviced upper hold."""
from suites.frontend.bpu.bpu.model.tage.dual_migration import PC, PATHS, OUTCOMES, counters_after

SOURCE_COUNT = 4
COMMIT_COUNTERS = tuple(counters_after(n) for n in range(1, 4)) + ((0, 7),)


def counters_after_service(ordinal):
    if type(ordinal) is not int or not 1 <= ordinal <= SOURCE_COUNT:
        raise ValueError('one service for each of the four declared old branch pairs')
    return COMMIT_COUNTERS[ordinal - 1]
