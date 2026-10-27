"""Input-selected tasks and distinct final-NT checks; never provider-filter inputs."""
from bpuverify.bpu.model.abtb.final_not_taken import PHASES
from bpuverify.bpu.model.abtb.final_not_taken import plan
from bpuverify.bpu.model.abtb.final_not_taken import capacity
from bpuverify.bpu.model.abtb.final_not_taken import fall_through
from bpuverify.bpu.case.abtb.alias_plan import checkpoint_route

PILOT_CASES=((0,0),(1,0),(2,31),(3,63),(0,56))


def programs(intent,alias):
    a,b,c,d=intent['cycles'][alias]
    return (dict(pc=a,position=6,target=b,branch_type=1,taken=1),
        dict(pc=b,position=7,target=c,branch_type=3,taken=1),
        dict(pc=c,position=7,target=d,branch_type=3,taken=1),
        dict(pc=d,position=7,target=a,branch_type=3,taken=1))


def selected_program(intent,alias,goal):
    if type(goal) is not int or goal not in (0,3):
        raise ValueError('real MainBTB direction goal must be0or3')
    conditional,*_=programs(intent,alias)
    if goal:return conditional
    row=fall_through(conditional['pc'])
    return dict(pc=conditional['pc'],target=row['target'],position=row['position'],
        branch_type=row['branch_type'],taken=0)


def input_qualified(source,token,intent,redirect_valid,alias=0):
    a,b,c,d=intent['cycles'][alias]
    return bool(token is not None and not redirect_valid
        and source['prediction']['start_pc']==a and token['pc']==d
        and token['mode']=='normal' and token['bank']==intent['bank']
        and token['entry_set']==intent['entry_set']
        and token['folded6']&15==intent['low4_index_source_history'])


def final_comparison(program,source,rising):
    if rising['tick']!=source['meta_tick'] or not rising['public_meta']['valid']:
        raise ValueError('exact associated valid S3 metadata event required')
    expected=dict(valid=1,pc=program['pc'],taken=program['taken'],position=program['position'],
        target=program['target'],branch_type=program['branch_type'])
    return expected,{key:rising['abtb']['final'][key] for key in expected}


def required_operations(confirmed,intent,alias,phase,required):
    a,_,_,_=intent['cycles'][alias]
    return {name:[row for row in confirmed if row['phase']==phase
        and row['bank']==intent['bank'] and row['set_index']==intent['entry_set']
        and row['transition']==name and row.get('feedback') is not None
        and row['feedback']['pc']==a
        and row['feedback']['taken']==int(not name.startswith('dec'))] for name in required}
