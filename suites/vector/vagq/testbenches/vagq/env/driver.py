"""Synchronous external driver for the clocked picker VAGQ root."""
from dataclasses import replace

from suites.vector.vagq.testbenches.vagq.env.probe import encode
from suites.vector.vagq.testbenches.vagq.transactions import Beat


class Driver:
    def __init__(self, dut, ports):
        self.dut = dut
        self.clock = ports.clock
        self.reset = ports.reset
        self.ports = ports
        self.reset.AsImmWrite()
        for signal in ports.inputs.values():
            signal.AsImmWrite()

    def drive(self, beat: Beat):
        self.ports.inputs.drive(encode(beat))

    def reset_dut(self):
        self.drive(Beat())
        self.reset.Set(1)
        self.dut.Step(2)
        self.reset.Set(0)
        self.dut.Step(1)

    def tick(self):
        self.dut.Step(1)


def _resolve_ready(name, carried, explicit, count):
    """Combine sampled and explicitly supplied ready evidence for one group.

    ``None`` means no evidence.  A tuple is positive evidence, including an
    all-False handshake.  Two positive sources must agree; silently letting an
    argument override known sampled evidence would manufacture an ACK.  With
    no evidence at all the group is all-False, so no acknowledgement is made.
    """
    if carried is not None and explicit is not None:
        carried, explicit = tuple(carried), tuple(explicit)
        if carried != explicit:
            raise ValueError(
                f'conflicting {name} evidence: observation={carried}, '
                f'beat={explicit}')
        return explicit
    chosen = explicit if explicit is not None else carried
    if chosen is None:
        return (False,) * count
    chosen = tuple(chosen)
    if len(chosen) != count or not all(isinstance(value, bool) for value in chosen):
        raise ValueError(f'{name} evidence must be {count} booleans')
    return chosen


def response_beat(observation, *, base=None, data=0, beat=None):
    """Build legal responses for requests whose target actually fired.

    A response candidate needs three independent facts from the same cycle:
    the request payload was valid (LSU/STA additionally need metadata valid),
    the target ready was asserted, and both came from the same sampled cycle.
    Ready evidence may be carried by ``observation`` (``decode(..., beat=...)``)
    and/or supplied explicitly as the same-cycle ``beat``.  The two positive
    sources must agree; a conflict is rejected rather than letting the
    argument override the sample.  With no evidence the group is all-False, so
    missing handshake evidence can never manufacture an ACK.  ``base`` only
    supplies next-cycle inputs and never substitutes for handshake evidence.
    """
    from suites.vector.vagq.testbenches.vagq.transactions import EmptyResponse
    from suites.vector.vagq.testbenches.vagq.transactions import Response
    from suites.vector.vagq.testbenches.vagq.transactions import VrfResponse

    if base is None:
        base = Beat()
    ldu_ready = _resolve_ready(
        'ldu_ready', observation.ldu_ready,
        None if beat is None else beat.ldu_ready, 3)
    sta_ready = _resolve_ready(
        'sta_ready', observation.sta_ready,
        None if beat is None else beat.sta_ready, 2)
    empty_ready = _resolve_ready(
        'empty_ready', observation.empty_ready,
        None if beat is None else beat.empty_ready, 2)
    ldu = [
        Response(
            valid=True,
            entry_idx=request.entry_idx,
            issue_mask=1 << request.byte_offset,
        ) if request.valid and request.meta_valid and ldu_ready[lane] else Response()
        for lane, request in enumerate(observation.loads)
    ]
    sta = [
        Response(
            valid=True,
            entry_idx=request.entry_idx,
            issue_mask=1 << request.byte_offset,
        ) if request.valid and request.meta_valid and sta_ready[lane] else Response()
        for lane, request in enumerate(observation.stores)
    ]
    empty = [
        EmptyResponse(
            valid=True,
            entry_idx=request.entry_idx,
            issue_mask=request.issue_mask,
        ) if request.valid and empty_ready[lane] else EmptyResponse()
        for lane, request in enumerate(observation.empty_requests)
    ]

    vrf = VrfResponse()
    if observation.vrf_read.valid:
        vrf = VrfResponse(
            valid=True,
            entry_idx=observation.vrf_read.entry_idx,
            rob_flag=observation.vrf_read.rob_flag,
            rob_value=observation.vrf_read.rob_value,
            data=data,
        )
    return replace(base, ldu_resp=tuple(ldu), sta_resp=tuple(sta),
                   empty_resp=tuple(empty), vrf_resp=vrf)
