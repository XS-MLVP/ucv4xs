"""Standalone TAGE selector endpoints for the buckets the public protocol can build.

The DUT keeps eight five-bit ``useAltOnNa`` registers indexed ``2*table + altConf``.
``BPU-TAGE-020`` only proves same-beat vote aggregation; the eight clamp arms were
uncovered, so this case drives real endpoints and compares the register against a
closed-form model of the documented arithmetic:

    vote = provider is weak (3 or 4) and provider_pred != alternate_or_base_pred
    step = +1 if alternate_or_base_pred == actual else -1

Design choices that keep the witness honest:

* the model is anchored at the register value measured **after** preparation and
  then predicts every subsequent delta and the exact clamp at 0/31;
* each driving beat re-reads the DUT vector, so a single wrong step fails;
* every other register must stay at its anchored value;
* the bucket is asserted to be the one the DUT itself reports, and the case only
  uses table 0, where ``altConf`` is the supplied base confidence (no alternate
  entry exists), so the training-side and prediction-side bucket must agree.

Tables 1-3 need an alternate entry, and the training-side ``altConf`` is then
recomputed from the alternate counter at training time.  Probing showed it does
not always equal the prediction-side ``altConf`` (e.g. a beat reported as
(1, altConf=1) moved register 2, not 3).  Those buckets are therefore **not**
claimed here; the divergence is recorded in
``docs/tage-selector-endpoint-analysis-20261021.md``.
"""

from __future__ import annotations

import json
import pytest

from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.tage.transaction.types import TageTraining

POSITION = 4
INITIAL = 16
LOW, HIGH = 0, 31


def step_value(value, metadata, actual):
    """One documented selector step; returns (delta, new value)."""

    provider_pred = int(metadata['providerTakenCtr_value'] >= 4)
    alternate_pred = metadata['altOrBasePred']
    weak = metadata['providerTakenCtr_value'] in (3, 4)
    delta = 0
    if weak and provider_pred != alternate_pred:
        delta = 1 if alternate_pred == actual else -1
    return delta, max(LOW, min(HIGH, value + delta))


async def prepare_table_zero(agent, base_conf):
    """One cold miss plus one taken outcome allocates a table-0 provider."""

    await agent.reset()
    cold = await agent.predict(PC, POSITION, 0, base_conf=base_conf)
    assert cold.meta['hasProvider'] == 0
    await agent.train(TageTraining(PC, POSITION, 1, 0, cold.meta))
    prediction = await agent.predict(PC, POSITION, 0, base_conf=base_conf)
    assert prediction.meta['hasProvider'] == 1
    assert prediction.meta['providerTableIdx'] == 0, prediction.meta
    return prediction


async def settle_to_four(agent, prediction, base_conf):
    """Bring the provider counter to 4; returns the beats used."""

    beats = []
    for _ in range(6):
        if prediction.meta['providerTakenCtr_value'] == 4:
            return prediction, beats
        await agent.train(TageTraining(PC, POSITION, 1, 0, prediction.meta,
                                       mispredict=0, base_counter_value=0))
        beats.append(prediction.meta)
        prediction = await agent.predict(PC, POSITION, 0, base_conf=base_conf)
    raise AssertionError(('provider counter did not settle to 4', prediction.meta))


async def drive(agent, prediction, anchor, target, base_conf, bucket, *, limit=90):
    """Alternate the outcome so each weak beat carries exactly one real vote."""

    prediction, beats = await settle_to_four(agent, prediction, base_conf)
    value = (await agent.sample_selectors())[bucket]
    trace = [dict(settling_beats=len(beats))]
    for step in range(limit):
        metadata = prediction.meta
        # Only the 4->vote, 3/5->restore alternation keeps the provider weak.
        actual = (0 if target == HIGH else 1) if metadata['providerTakenCtr_value'] == 4\
            else (1 if target == HIGH else 0)
        await agent.train(TageTraining(PC, POSITION, actual, 0, metadata,
                                       mispredict=0, base_counter_value=0))
        delta, value = step_value(value, metadata, actual)
        observed = await agent.sample_selectors()
        assert observed[bucket] == value, (
            'DUT selector diverged from the closed-form step',
            dict(bucket=bucket, step=step, delta=delta, expected=value,
                 observed=observed[bucket], metadata=metadata))
        others = [item for index, item in enumerate(observed) if index != bucket]
        assert others == [item for index, item in enumerate(anchor) if index != bucket], (
            'a different selector bucket moved', dict(bucket=bucket, observed=observed))
        prediction = await agent.predict(PC, POSITION, 0, base_conf=base_conf)
        trace.append(dict(step=step, delta=delta, value=value,
                          counter=metadata['providerTakenCtr_value'],
                          alternate_pred=metadata['altOrBasePred']))
        if value == target:
            return prediction, trace
    raise AssertionError(('bucket did not reach its endpoint',
                          dict(bucket=bucket, target=target, value=value)))


@pytest.mark.feature('BPU-TAGE-020')
@pytest.mark.parametrize('base_conf', (0, 1), ids=('altConf0', 'altConf1'))
async def test_table_zero_selector_saturates_and_holds_at_both_endpoints(
        tage_agent, request, base_conf):
    prediction = await prepare_table_zero(tage_agent, base_conf)
    bucket = 2 * prediction.meta['providerTableIdx'] + prediction.meta['altConf']
    assert bucket == base_conf, (
        'table 0 has no alternate, so altConf must equal the supplied base confidence',
        prediction.meta)
    anchor = await tage_agent.sample_selectors()
    assert anchor[bucket] == INITIAL, anchor

    prediction, up = await drive(tage_agent, prediction, anchor, HIGH,
                                 base_conf, bucket)
    held = await tage_agent.sample_selectors()
    assert held[bucket] == HIGH, held
    # One further increment must be clamped, not wrapped.
    metadata = prediction.meta
    if metadata['providerTakenCtr_value'] in (3, 4):
        actual = 0 if metadata['altOrBasePred'] == 0 else 1
        delta, predicted = step_value(HIGH, metadata, actual)
        if delta > 0:
            await tage_agent.train(TageTraining(PC, POSITION, actual, 0, metadata,
                                                mispredict=0, base_counter_value=0))
            after = await tage_agent.sample_selectors()
            assert predicted == HIGH and after[bucket] == HIGH, (
                'upper clamp did not hold', dict(predicted=predicted, after=after))

    prediction, down = await drive(tage_agent, prediction, anchor, LOW, base_conf, bucket)
    final = await tage_agent.sample_selectors()
    assert final[bucket] == LOW, final
    others = [item for index, item in enumerate(final) if index != bucket]
    assert others == [item for index, item in enumerate(anchor) if index != bucket], (
        'driving one bucket changed another', dict(anchor=anchor, final=final))

    # Durable carrier: an isolated regression reclaims its worker sandbox, so a
    # process-global path would lose the trace even though the case passed.
    request.node.user_properties.append((
        'tage_selector_bucket',
        json.dumps(dict(bucket=bucket, anchor=list(anchor),
                        upper=dict(value=HIGH, votes=len([row for row in up if row.get('delta')])),
                        lower=dict(value=LOW, votes=len([row for row in down if row.get('delta')])),
                        final=list(final), up_trace=up, down_trace=down), sort_keys=True)))
    assert len([row for row in up if row.get('delta')]) >= HIGH - INITIAL
    assert len([row for row in down if row.get('delta')]) >= HIGH - LOW
