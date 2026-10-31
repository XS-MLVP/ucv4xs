"""Qualified pending-operation interactions, independent of test recipes."""


def pending_interaction(state, inputs, reset=0):
    """Selected interaction and its actual sources, not merely a route label.

    Scope: S1 RET pairing and advancing neutral S2 correction over a younger
    CALL/RET. Other MicroRAS operations have separate verification obligations.
    """
    if reset or inputs['redirect'] or inputs['s3']['valid']:
        return None
    younger=inputs['s1']
    if inputs['s2']['valid']:
        if (inputs['s2']['action']==0 and inputs['fire2'] and state['s3_push']
                and inputs['fire1'] and younger['action'] in (1,2)):
            rule='neutral-S2-cancel-S1-RETURN' if younger['action']==1 else 'neutral-S2-cancel-S1-CALL'
        else:
            return None
    elif inputs['fire1'] and younger['action']==1:
        if state['s2_push'] and state['s3_push']:
            rule='return-pairs-S2-forwards-S3'
        elif not state['s2_push'] and not state['s2_pop'] and state['s3_push']:
            rule='return-pairs-S3-uses-main'
        else:
            return None
    else:
        return None
    return dict(rule=rule, s1_pc=younger['pc'],s1_position=younger['position'],
        s1_action=younger['action'],s2_pc=inputs['s2']['pc'],
        older_return=state['s3_address'],main_top=inputs['main_top'])
