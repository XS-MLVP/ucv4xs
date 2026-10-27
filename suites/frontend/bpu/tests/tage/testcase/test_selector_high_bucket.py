"""A high-table selector bucket must also saturate at 0 and 31.

Buckets 0/1 are covered by ``test_selector_buckets.py``: with a single-table
provider (no alternate entry) the supplied base confidence *is* the ``altConf``
term.  Reaching tables 1-3 needs a **strong alternate**, which the public
protocol does not offer directly, so this case builds one:

1. allocate a table-0 provider;
2. vote its selector bucket below 16, so ``useProvider`` becomes 1 and the entry
   is frozen against further alternate training;
3. grow that entry to counter 7 (a strong alternate);
4. one genuine mispredict escalates to a longer table: the new provider sits in
   table 1-3 and the frozen table-0 entry becomes the alternate with
   ``altOrBasePred = 1``;
5. drive the provider counter in the 3/4 window so each voting beat casts
   exactly one real vote.

The expected register delta is closed-form (``weak and provider_pred !=
alternate_pred`` -> +/-1) and is applied to the register index **the DUT's own
metadata names for that beat**.  That index is not asserted to be constant:
``altConf`` is recomputed from the alternate counter on both the prediction and
the training side, and a beat that trains the alternate can legitimately move
it.  What is asserted is that the whole eight-register vector equals the model
after every beat, that every vote lands on one and the same register, and that
both endpoints are reached and held.

The escalation table is chosen by the DUT's LFSR, so the case searches a bounded
number of no-op beats for a run whose alternate is strong enough to survive the
first vote.  That is a preparation search, not a relaxation: the assertions are
identical for every attempt and a run that cannot reach both endpoints fails.
"""

from __future__ import annotations

import json

import pytest

from bpuverify.tage.case.definitions import PC
from bpuverify.tage.transaction.types import TageTraining

POSITION = 4
INITIAL = 16
LOW, HIGH = 0, 31


async def beat(agent, prediction, actual):
    await agent.train(TageTraining(PC, POSITION, actual, 0, prediction.meta,
                                   mispredict=0, base_counter_value=0))
    return await agent.predict(PC, POSITION, 0, base_conf=0)


def index_of(metadata):
    return 2 * metadata['providerTableIdx'] + metadata['altConf']


def step_value(value, metadata, actual):
    """One documented selector step; returns (index, delta, new value)."""

    index = index_of(metadata)
    provider_pred = int(metadata['providerTakenCtr_value'] >= 4)
    alternate_pred = metadata['altOrBasePred']
    weak = metadata['providerTakenCtr_value'] in (3, 4)
    delta = 0
    if weak and provider_pred != alternate_pred:
        delta = 1 if alternate_pred == actual else -1
    return index, delta, max(LOW, min(HIGH, value + delta))


async def freeze_a_strong_alternate(agent, shift, levels=1):
    """Return a prediction whose alternate is the frozen table-0 entry."""

    await agent.reset()
    cold = await agent.predict(PC, POSITION, 0, base_conf=0)
    assert cold.meta['hasProvider'] == 0
    await agent.train(TageTraining(PC, POSITION, 1, 0, cold.meta))
    prediction = await agent.predict(PC, POSITION, 0, base_conf=0)
    assert prediction.meta['providerTableIdx'] == 0

    # 1) bring the table-0 selector below 16: useProvider -> 1 freezes the entry
    for _ in range(80):
        meta = prediction.meta
        actual = 1 if meta['providerTakenCtr_value'] == 4 else 0
        prediction = await beat(agent, prediction, actual)
        if (await agent.sample_selectors())[0] <= 10:
            break
    else:
        raise AssertionError('table-0 selector did not fall below 16')

    # 2) grow the frozen entry to a strong counter
    for _ in range(10):
        if prediction.meta['providerTakenCtr_value'] >= 7:
            break
        prediction = await beat(agent, prediction, 1)
    else:
        raise AssertionError(('frozen entry did not reach a strong counter',
                              prediction.meta))

    for _ in range(shift):
        prediction = await beat(agent, prediction, 0)

    # 3) one genuine mispredict per level escalates to a longer table
    for level in range(levels):
        for _ in range(6):
            await agent.train(TageTraining(PC, POSITION, 1 - prediction.taken, 0,
                                           prediction.meta, mispredict=1))
            prediction = await agent.predict(PC, POSITION, 0, base_conf=0)
            if prediction.meta['providerTableIdx'] >= level + 1:
                break
        meta = prediction.meta
        assert meta['providerTableIdx'] >= level + 1, meta
        # Grow this provider back to a strong counter before the next level.
        # Do not touch it after the last escalation: those beats would vote in
        # the bucket under test and destroy the 16 anchor.
        if level + 1 < levels:
            for _ in range(10):
                if prediction.meta['providerTakenCtr_value'] >= 7:
                    break
                prediction = await beat(agent, prediction, 1)
    meta = prediction.meta
    assert meta['hasAlt'] == 1 and meta['altOrBasePred'] == 1, meta
    return prediction


async def drive(agent, prediction, values, direction, *, limit=200):
    """One vote per voting beat; the whole vector must match the model."""

    trace = []
    for _ in range(limit):
        metadata = prediction.meta
        counter = metadata['providerTakenCtr_value']
        alternate_pred = metadata['altOrBasePred']
        # Walk back into the weak window without voting, then cast the vote.
        if counter >= 5:
            actual = 0
        elif counter <= 2:
            actual = 1
        elif counter == 3:
            actual = (1 if direction > 0 else 0) if alternate_pred == 1 else 1
        else:
            actual = (0 if direction > 0 else 1) if alternate_pred == 0 else 0
        index, delta, value = step_value(values[index_of(metadata)], metadata, actual)
        await agent.train(TageTraining(PC, POSITION, actual, 0, metadata,
                                       mispredict=0, base_counter_value=0))
        values[index] = value
        observed = await agent.sample_selectors()
        assert observed == tuple(values), (
            'DUT selector vector diverged from the closed-form model',
            dict(index=index, delta=delta, metadata=metadata,
                 expected=list(values), observed=list(observed)))
        prediction = await agent.predict(PC, POSITION, 0, base_conf=0)
        trace.append(dict(index=index, delta=delta, value=value,
                          counter=counter, alternate_pred=metadata['altOrBasePred']))
        if delta and value == (HIGH if direction > 0 else LOW):
            return prediction, trace
    raise AssertionError(('endpoint not reached', dict(direction=direction,
                          values=list(values), trace=trace[-6:])))


async def check_endpoint(agent, shift, direction):
    """One fresh preparation; drive one direction to its endpoint and hold it."""

    prediction = await freeze_a_strong_alternate(agent, shift)
    values = list(await agent.sample_selectors())
    anchor = list(values)
    assert prediction.meta['altOrBasePred'] == 1, prediction.meta
    prediction, trace = await drive(agent, prediction, values, direction)
    final = await agent.sample_selectors()
    voted = {row['index'] for row in trace if row['delta']}
    assert len(voted) == 1, ('one direction must drive one register', voted, trace[-4:])
    bucket, = voted
    target = HIGH if direction > 0 else LOW
    assert final[bucket] == target, (direction, bucket, list(final))

    # One further vote in the same direction must be a real overflow that is
    # clamped at the endpoint (not a "we never got another vote" pass).
    overflow = None
    if direction > 0 and final[bucket] == HIGH:
        prediction, extra = await drive(agent, prediction, list(final), +1)
        after = await agent.sample_selectors()
        assert any(row['delta'] > 0 for row in extra) and after[bucket] == HIGH, (
            'upper clamp did not hold', dict(bucket=bucket, after=list(after)))
        overflow = dict(direction=+1, votes=len([row for row in extra if row['delta']]),
                        value=after[bucket], final=list(after))
    elif direction < 0 and final[bucket] == LOW:
        prediction, extra = await drive(agent, prediction, list(final), -1)
        after = await agent.sample_selectors()
        assert any(row['delta'] < 0 for row in extra) and after[bucket] == LOW, (
            'lower clamp did not hold', dict(bucket=bucket, after=list(after)))
        overflow = dict(direction=-1, votes=len([row for row in extra if row['delta']]),
                        value=after[bucket], final=list(after))

    return dict(shift=shift, direction=direction, bucket=bucket, anchor=anchor,
                final=list(final), votes=len([row for row in trace if row['delta']]),
                clamp=overflow, trace=trace)


@pytest.mark.feature('BPU-TAGE-020')
async def test_high_table_bucket_saturates_at_both_endpoints(tage_agent, request):
    # The escalation table is LFSR-chosen, so a bounded shift search finds a run
    # whose table-0 entry stays strong.  The same shift then reproduces the same
    # table on a fresh reset, so both directions exercise the same bucket.
    shift = None
    for candidate in range(8):
        prediction = await freeze_a_strong_alternate(tage_agent, candidate)
        meta = prediction.meta
        if meta['altOrBasePred'] == 1 and meta['altConf'] == 0:
            shift = candidate
            break
    assert shift is not None, 'no bounded preparation produced a stable strong alternate'

    up = await check_endpoint(tage_agent, shift, +1)
    down = await check_endpoint(tage_agent, shift, -1)
    assert up['bucket'] == down['bucket'], (
        'both directions must exercise the same high bucket',
        dict(up=up['bucket'], down=down['bucket']))

    bucket = up['bucket']
    assert 2 <= bucket <= 7
    for row in (up, down):
        others = [(index, value) for index, value in enumerate(row['final'])
                  if index not in (bucket, 0)]
        assert all(value == INITIAL for _, value in others), (
            'driving one high bucket changed an unrelated register', row['final'])

    request.node.user_properties.append((
        'tage_selector_high_bucket',
        json.dumps(dict(bucket=bucket, table=bucket // 2, alt_conf=bucket % 2,
                        shift=shift,
                        up=dict(anchor=up['anchor'], votes=up['votes'],
                                clamp=up['clamp'], final=up['final']),
                        down=dict(anchor=down['anchor'], votes=down['votes'],
                                  clamp=down['clamp'], final=down['final'])),
                   sort_keys=True)))
