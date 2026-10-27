"""Two independent semantic histories connected at their old-state boundary.

Connections below are expected values, NOT actual hidden hierarchy samples.
The real native DUT retains both real children and all their submodules.
"""
from lsqverify.psq.model import PsqModel
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr
from lsqverify.vsq.model import VsqModel
from lsqverify.vsq.types import Inputs as VsqInputs
from .types import execution


class StoreQueueModel:
    def __init__(self):
        self.virtual, self.physical = VsqModel(), PsqModel()

    def connected(self, inp):
        vsq, psq = self.virtual, self.physical
        # Payloads without valid are retained only to describe the expected
        # wire value; no check/permission may depend on an undefined payload.
        p_input = execution(inp, enqueue=SqPtr.encode(0 if inp.reset else vsq.physical_tail),
                            retired=SqPtr.encode(0 if inp.reset else vsq.retired_base + vsq.retired_due),
                            precommit_valid=not inp.reset and vsq.precommit_valid and not vsq.effective_redirect(),
                            precommit=SqPtr.encode(vsq.precommit_payload), redirect_valid=vsq.redirect_valid and not inp.reset,
                            redirect=SqPtr.encode(vsq.redirect_payload), rob=vsq.head_rob if vsq.precommit_known else RobPtr())
        v_input = VsqInputs(inp.dispatch, inp.rob_head, SqPtr.encode(0 if inp.reset else psq.head), bool(psq.credit), inp.redirect, inp.reset)
        return v_input, p_input

    def expected(self, inp, *, before=False):
        v_input, p_input = self.connected(inp)
        virtual = self.virtual.expected_before(v_input) if before else self.virtual.expected()
        physical, masks = self.physical.expected(p_input)
        values = {}
        for key, value in physical.items():
            if key == "io_empty":
                if "io_empty" in virtual:
                    values["io_sqEmpty"] = int(value and virtual["io_empty"])
            elif key == "io_full":
                values["io_sqFull"] = value
            elif key.startswith("io_sqDeq_"):
                values[key.replace("io_sqDeq_", "io_toLsqEnqCtrl_sqDeq_", 1)] = value
            else:
                values[key] = value
        if "io_sqRecoverStall" in virtual:
            values["io_toLsqEnqCtrl_sqRecoverStall"] = virtual["io_sqRecoverStall"]
        for key, value in virtual.items():
            if key.startswith("io_toPhysicalQueue_redirectPtr_"):
                values[key.replace("io_toPhysicalQueue_redirectPtr_", "io_toLsqEnqCtrl_sqRedirectPtr_", 1)] = value
        return values, masks

    def safety(self, inp, pins):
        return self.physical.safety(self.connected(inp)[1], pins)

    def advance(self, inp):
        virtual_input, physical_input = self.connected(inp)
        # Capture both above, before advancing either side. Registering the
        # peer's NEW output here would introduce a nonexistent bypass.
        virtual = self.virtual.advance(virtual_input)
        physical = self.physical.advance(physical_input)
        return {"virtual": virtual, "physical": physical}
