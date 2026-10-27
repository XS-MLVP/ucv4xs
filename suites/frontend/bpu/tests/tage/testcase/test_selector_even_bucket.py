"""Even selector buckets 4 and 6 (tables 2 and 3) saturate at both endpoints.

``useAltOnNa`` is indexed by ``2 * providerTable + altConf``.  Buckets 0/1 are
covered by ``test_selector_buckets.py``, bucket 2 by
``test_selector_high_bucket.py`` and buckets 3/5/7 by
``test_selector_odd_bucket.py``.  This case covers the two remaining even
buckets, 4 and 6.

Preparation is the simplest shape that makes them stable: a **single allocation
directly into table 2 or 3 with no alternate**.  ``altConf`` then comes from the
base counter instead of an alternate entry, and because the base prediction is
an input to the DUT (the caller re-supplies ``base_conf = 0`` on every beat) it
does not train at all.  So:

* ``altConf`` stays 0 for the whole drive -> the bucket index never moves;
* ``altOrBasePred`` stays 0 -> the provider at counter 4 has
  ``providerPred = 1 != 0``, so both vote directions are available:
  ``actual = 0`` gives ``+1`` and ``actual = 1`` gives ``-1``;
* counter 3 is neutral (``providerPred = 0 == altOrBasePred``) and only walks the
  counter back to 4, so each direction advances one step per two beats.

Which table the first allocation picks is chosen by the TAGE LFSR.  The case
walks a fixed tag sequence on one reset and takes the first tag whose provider
lands on table 2 (bucket 4) or table 3 (bucket 6).  That is a bounded
preparation search, not a relaxation: the produced bucket, ``altConf`` and
``altOrBasePred`` are asserted, and the anchor is read from the DUT rather than
assumed, so a change in allocation behaviour fails the case instead of silently
weakening it.

Every beat is compared against the closed-form ``(provider counter,
altOrBasePred, selector)`` model for all eight registers, both endpoints are
required, and one further real vote past each endpoint must be clamped rather
than wrapped.
"""

from __future__ import annotations

import json

import pytest

from bpuverify.tage.transaction.types import TageTraining

POSITION = 4
LOW, HIGH = 0, 31
WEAK = (3, 4)
TAGS = tuple(0x1000 + 0x40 * index for index in range(8))


async def beat(agent, pc, prediction, actual, *, mispredict=0):
    await agent.train(TageTraining(pc, POSITION, actual, 0, prediction.meta,
                                   mispredict=mispredict, base_counter_value=0))
    return await agent.predict(pc, POSITION, 0, base_conf=0)


async def prepare(agent, bucket):
    """Walk a fixed tag sequence; return the first allocation into table 2 or 3."""

    await agent.reset()
    saw = []
    for pc in TAGS:
        cold = await agent.predict(pc, POSITION, 0, base_conf=0)
        if cold.meta['hasProvider']:
            prediction = cold
        else:
            await agent.train(TageTraining(pc, POSITION, 1, 0, cold.meta))
            prediction = await agent.predict(pc, POSITION, 0, base_conf=0)
        for _ in range(20):
            if prediction.meta['providerTakenCtr_value'] >= 4:
                break
            prediction = await beat(agent, pc, prediction, 1)
        # One not-taken mispredict.  It may allocate a longer table (which is
        # what makes table 3 reachable at all); either way the resulting shape is
        # read back and asserted below instead of being assumed.
        prediction = await beat(agent, pc, prediction, 0, mispredict=1)
        produced = 2 * prediction.meta['providerTableIdx'] + prediction.meta['altConf']
        saw.append((hex(pc), prediction.meta['providerTableIdx'],
                    prediction.meta['altConf'], prediction.meta['altOrBasePred']))
        if produced != bucket:
            continue
        meta = prediction.meta
        assert meta['providerTableIdx'] >= 2, ('bucket 4/6 needs table 2/3', meta)
        assert meta['altConf'] == 0 and meta['altOrBasePred'] == 0, (
            'the no-alternate shape must keep altConf 0 and altOrBasePred 0', meta)
        return prediction, pc
    raise AssertionError(('no tag allocated directly into the requested table',
                          bucket, saw))


def step_value(meta, actual, values):
    index = 2 * meta['providerTableIdx'] + meta['altConf']
    delta = 0
    if meta['providerTakenCtr_value'] in WEAK:
        if int(meta['providerTakenCtr_value'] >= 4) != meta['altOrBasePred']:
            delta = 1 if meta['altOrBasePred'] == actual else -1
    return index, delta, max(LOW, min(HIGH, values[index] + delta))


def choose(meta, direction):
    counter = meta['providerTakenCtr_value']
    if counter >= 5:
        return 0
    if counter <= 2:
        return 1
    if counter == 4:
        return 0 if direction > 0 else 1
    return 1


async def drive(agent, pc, prediction, values, bucket, direction, limit=200):
    trace = []
    for _ in range(limit):
        meta = prediction.meta
        index = 2 * meta['providerTableIdx'] + meta['altConf']
        assert index == bucket, ('the even bucket moved', dict(bucket=bucket,
                               index=index, meta=meta))
        assert meta['altConf'] == 0 and meta['altOrBasePred'] == 0, (
            'the no-alternate shape changed', meta)
        actual = choose(meta, direction)
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

    extra = []
    for _ in range(40):
        meta = prediction.meta
        actual = choose(meta, direction)
        index, delta, value = step_value(meta, actual, values)
        prediction = await beat(agent, pc, prediction, actual)
        values[index] = value
        observed = await agent.sample_selectors()
        assert observed == tuple(values), ('clamp drift', dict(
            expected=list(values), observed=list(observed)))
        if delta:
            extra.append(dict(index=index, delta=delta, value=value))
            break
    assert extra and extra[-1]['value'] == target and values[bucket] == target, (
        'a further real vote past the endpoint must be clamped',
        dict(extra=extra, bucket=bucket, value=values[bucket]))

    others = [(index, value) for index, value in enumerate(final) if index != bucket]
    assert others == [(index, value) for index, value in enumerate(anchor)
                      if index != bucket], (
        'driving one even bucket changed an unrelated register',
        dict(bucket=bucket, anchor=anchor, final=list(final)))
    return dict(bucket=bucket, pc=pc, anchor=anchor, final=list(final),
                votes=len(votes), overflow=extra[-1])


@pytest.mark.feature('BPU-TAGE-020')
@pytest.mark.parametrize('bucket', [4, 6])
async def test_even_bucket_saturates_at_both_endpoints(tage_agent, bucket, request):
    up = await endpoint(tage_agent, bucket, +1)
    down = await endpoint(tage_agent, bucket, -1)
    assert up['pc'] == down['pc'], 'both directions must use the same tag and table'
    assert up['final'][bucket] == HIGH and down['final'][bucket] == LOW
    request.node.user_properties.append((
        'tage_selector_even_bucket',
        json.dumps(dict(bucket=bucket, table=bucket // 2, alt_conf=bucket % 2,
                        shape='single allocation into table 2/3, no alternate',
                        pc=up['pc'], tags=TAGS.index(up['pc']) + 1,
                        up=dict(votes=up['votes'], overflow=up['overflow'],
                                anchor=up['anchor'], final=up['final']),
                        down=dict(votes=down['votes'], overflow=down['overflow'],
                                  anchor=down['anchor'], final=down['final'])),
                   sort_keys=True)))
