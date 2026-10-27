"""Read-only RAS component IO and retained actuals, never state seeds."""
from toffee import Bundle

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names


def semantic_binding(agent,*,observe_resources=False):
    anchor, = [name for name in memory_signal_names(agent.dut) if name.endswith('.ras.io_enable')]
    prefix = anchor.removeprefix('TOP.').removesuffix('io_enable')
    core = prefix.removesuffix('ras.')
    signal = lambda field: memory_signal(agent.dut,prefix+field)
    root = lambda field: memory_signal(agent.dut,core+field)
    pointer = lambda base: Bundle(flag=signal(base+'_flag'),value=signal(base+'_value'))
    def metadata(base):
        return Bundle(ssp=signal(base+'ssp'),sctr=signal(base+'sctr'),tosw=pointer(base+'tosw'))
    inputs = Bundle(reset=signal('reset'),enabled=signal('io_enable'),
        speculative=Bundle(valid=signal('io_specIn_valid'),bits=Bundle(
            action=signal('io_specIn_bits_attribute_rasAction'),position=signal('io_specIn_bits_cfiPosition'),
            start_pc=signal('io_specIn_bits_startPc'))),
        redirect=Bundle(valid=signal('io_redirect_valid'),bits=Bundle(
            action=signal('io_redirect_bits_attribute_rasAction'),cfi_pc=signal('io_redirect_bits_cfiPc_addr'),
            meta=metadata('io_redirect_bits_meta_ras_'))),
        commit=Bundle(valid=signal('io_commit_valid'),bits=Bundle(
            action=signal('io_commit_bits_attribute_rasAction'),meta=Bundle(
                ssp=signal('io_commit_bits_meta_ras_ssp'),tosw=pointer('io_commit_bits_meta_ras_tosw')))))
    resources = dict(resources=Bundle(bos=pointer('RasStack.bos'),
        guarded=signal('RasStack.io_specNearOverflow'))) if observe_resources else {}
    outputs = Bundle(public=Bundle(top=signal('io_topRetAddr_addr'),
        redirect_meta=metadata('io_redirectMeta_'),commit_meta=Bundle(
            ssp=signal('io_commitMeta_ssp'),tosw=pointer('io_commitMeta_tosw'))),
        retained=Bundle(head=signal('RasStack.nsp'),cells=tuple(Bundle(
            address=signal(f'RasStack.commitStack_{index}_retAddr_addr'),
            counter=signal(f'RasStack.commitStack_{index}_ctr')) for index in range(8))),**resources)
    consumer = Bundle(valid=root('s3_valid'),pc=root('s3_startPc_dup_1_addr'),
        target=root('s3_prediction_target_addr'),taken=root('s3_taken'),
        action=root('s3_prediction_attribute_rasAction'))
    return PortBinding(agent.dut.clock,Bundle(inputs=inputs,outputs=outputs,consumer=consumer),'bpu.ras.semantic-component')
