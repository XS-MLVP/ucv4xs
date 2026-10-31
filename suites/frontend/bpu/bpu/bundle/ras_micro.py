"""Static, read-only integrated MicroRAS state and module-input views."""
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.runtime.memory_direct import memory_signal, memory_signal_names


def micro_ras_binding(agent):
    matches = [name for name in memory_signal_names(agent.dut) if name.endswith('.uras.s2_hasPush')]
    if len(matches) != 1:
        raise RuntimeError(f'unique integrated MicroRAS required: {matches}')
    prefix = matches[0].removeprefix('TOP.').removesuffix('s2_hasPush')
    signal = lambda field: memory_signal(agent.dut, prefix + field)
    def operation(prefix):
        return Bundle(pc=signal(prefix + '_startPc_addr'), position=signal(prefix + '_cfiPosition'),
            action=signal(prefix + '_attribute_rasAction'))
    s1 = operation('io_specIn')
    def correction(stage):
        prefix = f'io_{stage}OverrideData'
        return Bundle(valid=signal(prefix + '_valid'), **{
            key: value for key, value in operation(prefix + '_bits').items()})
    inputs = Bundle(s1=s1, s2=correction('s2'), s3=correction('s3'),
        fire1=signal('io_stageCtrl_s1_fire'), fire2=signal('io_stageCtrl_s2_fire'),
        fire3=signal('io_stageCtrl_s3_fire'), redirect=signal('io_hasRedirect'),
        main_top=signal('io_fullRetAddr_addr'))
    state = Bundle(**{key: signal(field) for key, field in dict(s2_push='s2_hasPush',
        s2_pop='s2_hasPop', s3_push='s3_hasPush', s3_pop='s3_hasPop',
        s2_address='s2_retAddr_addr', s3_address='s3_retAddr_addr', usable='isCanUse',
        address='topRetAddr_addr', delayed_redirect='redirectDelay1').items()})
    return PortBinding(agent.dut.clock, Bundle(reset=agent.dut.reset, inputs=inputs, state=state,
        output=Bundle(usable=signal('io_specOut_isCanUse'), address=signal('io_specOut_retTarget_addr'))),
        'bpu.micro_ras_pipeline')
