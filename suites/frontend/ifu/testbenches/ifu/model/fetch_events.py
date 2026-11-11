"""Named IFU event counts, from accepted fetch metadata and semantic events.

Contract: Ifu.perfEvents and ICachePerfInfo's hit/miss categories, in the public
DefaultConfig baseline. These are13 Boolean counts, NOT accumulated counters.
The public HasPerfEvents interface registers them twice; the agent associates
that latency with input history and never uses observed counters as an answer.
"""
NAMES = ('frontend_flush', 'request', 'miss', 'line0_request', 'line1_request',
         'line0_hit', 'line1_hit', 'only0_hit', 'only0_miss',
         'both_hit', 'hit0_miss1', 'miss0_hit1', 'both_miss')


def event_counts(*, enqueue, frontend_flush, hits=(0, 0), double_line=0):
    hit0, hit1 = map(bool, hits)
    double = bool(double_line)
    categories = (True, not (hit0 and (not double or hit1)), True, double,
                  hit0, double and hit1, not double and hit0, not double and not hit0,
                  double and hit0 and hit1, double and hit0 and not hit1,
                  double and not hit0 and hit1, double and not hit0 and not hit1)
    return (int(bool(frontend_flush)),) + tuple(int(bool(enqueue) and category) for category in categories)
