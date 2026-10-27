"""Odd selector buckets (table `n`, weak-suppressed alternate) saturate at both ends.

`useAltOnNa` is indexed by `2 * providerTable + altConf`, where
``altConf = !alternate.takenCtr.isWeak``:

* ``altConf = 0`` (even bucket) means the alternate sits in the *weak* window
  (counter 3/4), so either side is one step from flipping the bucket;
* ``altConf = 1`` (odd bucket) means the alternate is strong (5/6/7) or
  saturated negative (0/1/2).

The even bucket 2 is covered by ``test_selector_high_bucket.py`` with a frozen
weak alternate.  This case covers the odd buckets with the other stable shape:
**a saturated-negative alternate**.  A table-0 provider is driven to counter 0
and then mispredicts on a taken branch; the old entry becomes the alternate at
counter 0 (``altPred = 0``, ``altConf = 1``) and the new provider is allocated
one table longer.  Because counter 0 holds under further not-taken training, the
alternate stays at 0 for the whole drive, the bucket index never moves, and both
directions remain steppable:

* counter 4 + ``actual = 0`` -> ``+1`` vote (alternate agrees),
* counter 4 + ``actual = 1`` -> ``-1`` vote (provider agrees),
* counter 3 is neutral with ``altPred = 0`` and only walks the counter back.

Which table a mispredict allocates is chosen by the TAGE LFSR, so the case walks
a fixed tag sequence (one fresh table-0 tag per attempt) until the requested
bucket appears.  That is a bounded preparation search, not a relaxation: every
attempt is asserted and a bucket that cannot be produced fails.

Every beat is compared against the closed-form ``(provider, alternate, selector)``
state for all eight registers, and both endpoints plus one further real vote
past each endpoint are required.
"""

from __future__ import annotations

import json

import pytest

from bpuverify.tage.transaction.types import TageTraining

POSITION = 4
INITIAL = 16
LOW, HIGH = 0, 31
WEAK = (3, 4)
TAGS = tuple(0x1000 + 0x40 * index for index in range(8))


async def beat(agent, pc, prediction, actual, *, mispredict=0):
    await agent.train(TageTraining(pc, POSITION, actual, 0, prediction.meta,
                                   mispredict=mispredict, base_counter_value=0))
    return await agent.predict(pc, POSITION, 0, base_conf=0)


async def escalate_once(agent, pc):
    """Give ``pc`` a saturated-negative table-0 provider, then allocate longer."""

    cold = await agent.predict(pc, POSITION, 0, base_conf=0)
    if not cold.meta['hasProvider']:
        await agent.train(TageTraining(pc, POSITION, 1, 0, cold.meta))
        prediction = await agent.predict(pc, POSITION, 0, base_conf=0)
    else:
        prediction = cold
    for _ in range(60):
        if prediction.meta['providerTakenCtr_value'] == 0:
            break
        prediction = await beat(agent, pc, prediction, 0)
    assert prediction.meta['providerTakenCtr_value'] == 0, (
        'the table-0 provider did not reach a saturated-negative counter',
        prediction.meta)
    await agent.train(TageTraining(pc, POSITION, 1, 0, prediction.meta, mispredict=1))
    prediction = await agent.predict(pc, POSITION, 0, base_conf=0)
    meta = prediction.meta
    assert meta['providerTableIdx'] >= 1 and meta['hasAlt'] == 1, meta
    assert meta['altOrBasePred'] == 0 and meta['altConf'] == 1, meta
    return prediction, 2 * meta['providerTableIdx'] + meta['altConf']


async def prepare(agent, bucket):
    """Replay the tag sequence until ``bucket`` is allocated; the anchor must be 16."""

    await agent.reset()
    for pc in TAGS:
        prediction, produced = await escalate_once(agent, pc)
        if produced == bucket:
            values = await agent.sample_selectors()
            assert values[bucket] == INITIAL, (
                'preparation must leave the target bucket at its reset value',
                dict(bucket=bucket, values=values))
            return prediction, pc
    raise AssertionError(('tag sequence did not produce the requested bucket', bucket))


def step_value(meta, actual, values):
    index = 2 * meta['providerTableIdx'] + meta['altConf']
    delta = 0
    if meta['providerTakenCtr_value'] in WEAK:
        provider_pred = int(meta['providerTakenCtr_value'] >= 4)
        if provider_pred != meta['altOrBasePred']:
            delta = 1 if meta['altOrBasePred'] == actual else -1
    return index, delta, max(LOW, min(HIGH, values[index] + delta))


async def drive(agent, pc, prediction, values, bucket, direction, limit=200):
    """Drive one endpoint; the index must stay on ``bucket`` and the model must hold."""

    trace = []
    for _ in range(limit):
        meta = prediction.meta
        index = 2 * meta['providerTableIdx'] + meta['altConf']
        assert index == bucket, ('the stable odd bucket moved', dict(bucket=bucket,
                               index=index, meta=meta))
        assert meta['altConf'] == 1 and meta['altOrBasePred'] == 0, (
            'a saturated-negative alternate must stay saturated', meta)
        counter = meta['providerTakenCtr_value']
        if counter >= 5:
            actual = 0
        elif counter <= 2:
            actual = 1
        elif counter == 4:
            actual = 0 if direction > 0 else 1
        else:
            actual = 1 if direction > 0 else 0
        index, delta, value = step_value(meta, actual, values)
        await agent.train(TageTraining(pc, POSITION, actual, 0, meta,
                                       mispredict=0, base_counter_value=0))
        values[index] = value
        observed = await agent.sample_selectors()
        assert observed == tuple(values), (
            'DUT selector vector diverged from the closed-form model',
            dict(index=index, delta=delta, meta=meta,
                 expected=list(values), observed=list(observed)))
        prediction = await agent.predict(pc, POSITION, 0, base_conf=0)
        trace.append(dict(index=index, delta=delta, value=value))
        if delta and value == (HIGH if direction > 0 else LOW):
            return prediction, trace
    raise AssertionError(('endpoint not reached', dict(direction=direction,
                          values=list(values), trace=trace[-4:])))


async def endpoint(agent, bucket, direction):
    prediction, pc = await prepare(agent, bucket)
    values = list(await agent.sample_selectors())
    anchor = list(values)
    prediction, trace = await drive(agent, pc, prediction, values, bucket, direction)
    final = await agent.sample_selectors()
    votes = [row for row in trace if row['delta']]
    assert {row['index'] for row in votes} == {bucket}, (
        'every vote must land on the driven bucket', [row['index'] for row in votes])
    target = HIGH if direction > 0 else LOW
    assert final[bucket] == target, (direction, bucket, list(final))

    # One further vote in the same direction must be clamped, not wrapped.
    extra = []
    for _ in range(40):
        meta = prediction.meta
        if meta['providerTakenCtr_value'] == 4 and meta['altOrBasePred'] == 0:
            actual = 0 if direction > 0 else 1
        elif meta['providerTakenCtr_value'] <= 2:
            actual = 1
        elif meta['providerTakenCtr_value'] >= 5:
            actual = 0
        else:
            actual = 1 if direction > 0 else 0
        index, delta, value = step_value(meta, actual, values)
        prediction = await beat(agent, pc, prediction, actual)
        values[index] = value
        observed = await agent.sample_selectors()
        assert observed == tuple(values), ('clamp drift', dict(expected=list(values),
                                             observed=list(observed)))
        if delta:
            extra.append(dict(index=index, delta=delta, value=value))
            break
    assert extra and extra[-1]['value'] == target and values[bucket] == target, (
        'a further real vote past the endpoint must be clamped', dict(extra=extra,
        bucket=bucket, value=values[bucket]))

    others = [(index, value) for index, value in enumerate(final)
              if index != bucket]
    assert others == [(index, value) for index, value in enumerate(anchor)
                      if index != bucket], (
        'driving one odd bucket changed an unrelated register',
        dict(bucket=bucket, anchor=anchor, final=list(final)))
    return dict(bucket=bucket, pc=pc, anchor=anchor, final=list(final),
                votes=len(votes), overflow=extra[-1], trace=trace)


@pytest.mark.feature('BPU-TAGE-020')
@pytest.mark.parametrize('bucket', [3, 5, 7])
async def test_odd_bucket_saturates_at_both_endpoints(tage_agent, bucket, request):
    up = await endpoint(tage_agent, bucket, +1)
    down = await endpoint(tage_agent, bucket, -1)
    assert up['pc'] == down['pc'], 'both directions must use the same tag and table'
    request.node.user_properties.append((
        'tage_selector_odd_bucket',
        json.dumps(dict(bucket=bucket, table=bucket // 2, alt_conf=bucket % 2,
                        pc=up['pc'], up=dict(votes=up['votes'], overflow=up['overflow'],
                                             anchor=up['anchor'], final=up['final']),
                        down=dict(votes=down['votes'], overflow=down['overflow'],
                                  anchor=down['anchor'], final=down['final'])),
                   sort_keys=True)))
