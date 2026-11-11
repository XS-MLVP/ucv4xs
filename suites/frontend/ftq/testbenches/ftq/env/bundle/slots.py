"""Full-slot encoding; physical leaves never escape the driver/monitor layer."""
from toffee import Bundle

from suites.frontend.ftq.testbenches.ftq.env.bundle.abi import layout
from suites.frontend.ftq.testbenches.ftq.env.driver.encoding import encode_backend_redirect
from suites.frontend.ftq.testbenches.ftq.env.driver.encoding import encode_callret
from suites.frontend.ftq.testbenches.ftq.env.driver.encoding import encode_ifu_redirect
from suites.frontend.ftq.testbenches.ftq.env.driver.encoding import encode_meta
from suites.frontend.ftq.testbenches.ftq.env.driver.encoding import encode_prediction
from suites.frontend.ftq.testbenches.ftq.env.driver.encoding import encode_resolve
from suites.frontend.ftq.testbenches.ftq.env.driver.encoding import encode_soft_prefetch
from suites.frontend.ftq.testbenches.ftq.transactions.cycle import FtqInput


class FtqInputPorts:
    def __init__(self, dut, ports):
        self.ports = ports
        self.widths, _ = layout()
        self.inputs = {name: dut.input(name) for name in self.widths}
        self.bits = Bundle(**self.inputs)

    def encode(self, frame):
        if type(frame) is not FtqInput:
            raise ValueError('Ftq driver requires a validated FtqInput')
        values = dict.fromkeys(self.widths, 0)
        values['reset'] = int(frame.reset)

        def group(pins, payload):
            values.update((pins.physical(key), value) for key, value in payload.items())

        if frame.prediction is not None:
            prediction = frame.prediction
            group(self.ports.prediction, encode_prediction(prediction))
            if prediction.s3_override:
                group(self.ports.meta, dict(s3_flag=prediction.s3_flag, s3_value=prediction.s3_ptr))
        if frame.meta is not None:
            group(self.ports.meta, encode_meta(frame.meta) | dict(s3_flag=frame.meta.flag, s3_value=frame.meta.index))
        if frame.backend_redirect is not None:
            group(self.ports.backend_redirect, encode_backend_redirect(frame.backend_redirect))
        if frame.ifu_redirect is not None:
            group(self.ports.ifu_redirect, encode_ifu_redirect(frame.ifu_redirect))
        for pins, report in zip(self.ports.resolve, frame.resolve, strict=True):
            if report is not None:
                group(pins, encode_resolve(report))
        for pins, row in zip(self.ports.callret, frame.callret, strict=True):
            if row is not None:
                group(pins, encode_callret(row))
        for pins, entry in zip(self.ports.soft_prefetch, frame.soft_prefetch, strict=True):
            if entry is not None:
                group(pins, encode_soft_prefetch(entry))
        if frame.commit is not None:
            flag, pointer = frame.commit
            group(self.ports.commit, dict(valid=1, flag=flag, ptr=pointer))
        if frame.ahead is not None:
            flag, pointer = frame.ahead
            group(self.ports.ahead, dict(valid=1, flag=flag, value=pointer))
        group(self.ports.consumers, dict(prefetch=frame.consumers.prefetch,
            mainpipe=frame.consumers.mainpipe, train=frame.consumers.train,
            real_two_fetch=frame.consumers.real_two_fetch))
        # All groups, including the shared s3 pointer, validate before ANY write.
        for name, value in values.items():
            if type(value) is not int or not 0 <= value < (1 << self.widths[name]):
                raise ValueError(f'Ftq slot {name} must fit {self.widths[name]} bits')
        return values
