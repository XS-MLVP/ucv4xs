"""MicroTage fast-train launch/T1 and dirty shadow-buffer write requests."""
from suites.frontend.bpu.ports.activity import bind_activity


def training_activity(dut):
    return bind_activity(dut, 'MicroTage', {
        'pipeline': (r't0_fire_REG', r't1_fire'),
        'writes': (r'MicroTageTable(?:_1)?\.wbuffer\.io_tryWrite_valid',),
    }, name='utage.training_activity')
