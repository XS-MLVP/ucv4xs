"""Fresh-reset SC-used raw replay, physical bins and fault targets."""
from bpuverify.bpu.checker.sc.reset_replay import fault_targets
from bpuverify.bpu.model.sc.used import branch_effects

def samples_from_raw(trace):
    assert trace['passed'] and trace['scoreboard_status']['failed'] == 0
    rows = {row['tick']: row for row in trace['records']}
    controls = {row['tick']: row for row in trace['preedge_records']}
    samples = []
    for accept in trace['accepts']:
        tick, transaction = (accept['tick'], accept['transaction'])
        raw = rows[tick]
        assert raw['training']['valid'] and raw['training']['ready'] and raw['t0']['fire']
        for effect in branch_effects(transaction):
            if not effect['used']:
                continue
            assert effect['qualified'] and effect['above']
            correct = effect['sc_pred'] == effect['taken']
            agrees = effect['sc_pred'] == effect['tage_pred']
            kind = 'used_correct_agree' if correct and agrees else 'used_correct_disagree' if correct else 'used_wrong'
            expected_read = int(not (correct and agrees))
            expected_write = int(not correct)
            assert effect['read_eligible'] == bool(expected_read) and effect['counter_update'] == bool(expected_write)
            assert controls[tick - 1]['t0']['fire'] == 1
            assert controls[tick + 1]['used_pipeline']['t1_fire'] == 1
            assert raw['t0']['need_write'] == expected_read
            for table in ('pathTable_0', 'imliTable', 'biasTable'):
                assert raw['t0']['reads'][table]['valid'] == expected_read
            slot = effect['slot']
            assert controls[tick - 1]['used_pipeline']['t0_valid_vec'][slot] == expected_read
            assert controls[tick + 1]['used_pipeline']['t1_valid_vec'][slot] == expected_read
            assert controls[tick + 1]['used_pipeline']['t1_write_valid'] == expected_read
            for table in ('pathTable_0', 'imliTable', 'biasTable'):
                name = f'{table}_bank{transaction['pc'] & 1}'
                assert rows[tick + 2]['buffers'][name]['write']['valid'] == expected_write
            samples.append(dict(bank=transaction['pc'] & 1, way=effect['way'], kind=kind, accepted_tick=tick, slot=slot, prediction_slot=effect['prediction_slot'], read=expected_read, write=expected_write))
    assert len(samples) == len(trace['used_feedback']) == 2
    assert {row['accepted_tick'] for row in samples} == {row['accepted_tick'] for row in trace['used_feedback']}
    return samples

def used_fault_targets(trace):
    targets = fault_targets(trace)
    for sample in samples_from_raw(trace):
        tick, slot = (sample['accepted_tick'], sample['slot'])
        prefix = sample['kind'] + '.' + trace['case']['profile']
        paths = (('rising', tick, ['training', 'bits', 'meta', 'sc', 'useScPred', sample['prediction_slot']], 'public_used'), ('rising', tick, ['t0', 'need_write'], 'T0_need_read'), ('rising', tick, ['t0', 'reads', 'pathTable_0', 'valid'], 'T0_actual_read_gate'), ('preedge', tick - 1, ['used_pipeline', 't0_valid_vec', slot], 'T0_slot_gate'), ('preedge', tick + 1, ['used_pipeline', 't1_valid_vec', slot], 'T1_slot_gate'), ('preedge', tick + 1, ['used_pipeline', 't1_write_valid'], 'T1_aggregate_read'), ('rising', tick + 2, ['buffers', f'pathTable_0_bank{sample['bank']}', 'write', 'valid'], 'T2_write_gate'), ('rising', tick + 4, ['used_pipeline', 'thresholds', sample['way']], 'threshold_update_or_hold'))
        targets.extend((dict(stream=stream, tick=at, path=path, label=prefix + '.' + label) for stream, at, path, label in paths))
    assert len(targets) == 37
    return targets
