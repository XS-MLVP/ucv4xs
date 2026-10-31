"""Exact neutral S2 correction/older-push association and wrong-path checks."""
from dataclasses import asdict
from suites.frontend.bpu.bpu.transaction.types import BpuStage1Source
from suites.frontend.bpu.uras.model.pipeline import return_address


def source_frame(checker, transaction):
    frames = [frame for frame in checker.records if frame['tick'] == transaction.prediction_tick]
    checker.check(1, len(frames), 'one exact MicroRAS source frame')
    return frames[0]


def check_program_output(checker, phr, transaction, intent, *, cold_neutral=False):
    expected = dict(start_pc=intent['pc'], target=intent['pc'] + 16 if cold_neutral else intent['target'],
        taken=int(not cold_neutral), position=intent['position'], s2_override=0, s3_override=0)
    checker.check(expected, asdict(transaction.prediction), 'complete planned S1 prediction', intent=intent)
    checker.check(BpuStage1Source.FALLTHROUGH if cold_neutral else BpuStage1Source.UBTB,
        transaction.meta.perf.s1_source, 'planned public early source', intent=intent)
    frame = source_frame(checker, transaction)
    checker.check((1, intent['pc'], intent['position'], intent['action']),
        (frame['inputs']['fire1'], frame['inputs']['s1']['pc'], frame['inputs']['s1']['position'],
         frame['inputs']['s1']['action']), 'actual accepted MicroRAS input', intent=intent)
    final = [row for row in phr.records if row['tick'] == transaction.meta_tick]
    checker.check(1, len(final), 'one exact associated final S3 frame')
    row, = final
    checker.check((intent['pc'], intent['target'], 1, intent['position']),
        (row['parent']['s3_pc'], row['parent']['s3_target'], row['parent']['s3_taken'],
         row['boundary']['s3']['prediction']['position']), 'complete planned final S3 result', intent=intent)
    return frame


def check_correction(checker, phr, transaction, older_call, neutral, wrong_path):
    tick = transaction.prediction_tick + 2  # Actual S1 -> S2 stage advance.
    frames = [row for row in checker.records if row['tick'] == tick]
    checker.check(1, len(frames), 'exact neutral S2 correction frame')
    frame, = frames
    inputs, state = frame['inputs'], frame['expected_before']
    checker.check('s2-neutral/s3-push', frame['route'], 'required neutral-correction overlap')
    checker.check((0, 0, 1), (inputs['redirect'], inputs['s3']['valid'], inputs['s2']['valid']),
        'no redirect or older S3 correction substitutes for neutral S2')
    checker.check((neutral['pc'], neutral['position'], 0, 1),
        (inputs['s2']['pc'], inputs['s2']['position'], inputs['s2']['action'], inputs['fire2']),
        'actual neutral S2 correction input')
    expected_return = return_address(older_call)
    checker.check((1, 0, expected_return), (state['s3_push'], state['s3_pop'], state['s3_address']),
        'older real call remains pending with its distinct return address')
    checker.check((1, wrong_path['pc'], wrong_path['position'], wrong_path['action']),
        (inputs['fire1'], inputs['s1']['pc'], inputs['s1']['position'], inputs['s1']['action']),
        'younger wrong-path operation really appears before flush')
    checker.check((1, expected_return, 0, 0),
        (frame['expected_after']['usable'], frame['expected_after']['address'],
         frame['expected_after']['s2_push'], frame['expected_after']['s2_pop']),
        'forward older address and cancel younger pending operation')
    outputs = [row for row in phr.records if row['tick'] == tick]
    checker.check(1, len(outputs), 'exact public S2 correction frame')
    public, = outputs
    checker.check((1, 1), (public['public_prediction']['valid'], public['pipeline']['s1_flush']),
        'public correction and younger pipeline flush')
    checker.check(dict(start_pc=neutral['pc'], target=neutral['target'], taken=1,
        position=neutral['position'], s2_override=1, s3_override=0),
        public['public_prediction']['bits'], 'complete public neutral correction')
    checker.check(older_call['pc'], public['parent']['s3_pc'], 'exact older S3 call ancestor')
    return frame


def check_wrong_path_absent(checker, phr, commit, wrong_path, boundary):
    metadata = [row for row in phr.records if row['tick'] > boundary and row['public_meta']['valid']
        and row['public_meta']['bits']['perf']['start_pc'] == wrong_path['pc']]
    checker.check([], metadata, 'wrong-path operation has no final public metadata')
    speculative = [row for row in commit.records if row['tick'] > boundary and row['spec']['valid']
        and row['spec']['pc_bytes'] == 2 * wrong_path['pc']]
    checker.check([], speculative, 'wrong-path operation never reaches main RAS speculation')
