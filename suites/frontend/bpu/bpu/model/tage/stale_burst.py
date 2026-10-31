"""Minimum stale-source burst that reaches and then holds the current bound."""
OLD_COUNTER=5
CURRENT_COUNTER=4
PROPOSAL_COUNTER=6
COMMIT_COUNTERS=(5,6,7,7)
SOURCE_COUNT=len(COMMIT_COUNTERS)
