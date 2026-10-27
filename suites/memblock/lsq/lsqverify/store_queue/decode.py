"""Passive raw-pin decoder; no DUT or reference-model state is inspected."""
from lsqverify.psq.decode import decode as psq_decode
from lsqverify.psq.types import Inputs as PsqInputs, encode as psq_encode
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import Redirect, RobPtr
from lsqverify.vsq.types import Dispatch
from .types import Inputs, SHARED_FIELDS


def decode(pins):
    def rob(prefix):
        return RobPtr(bool(pins[prefix + "flag"]), pins[prefix + "value"], bool(pins[prefix + "isFormer"]))
    def sq(prefix):
        return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])
    physical = psq_encode(PsqInputs())
    physical.update({key: value for key, value in pins.items() if key in physical})
    external = psq_decode(physical)
    dispatch = []
    for lane in range(8):
        prefix = f"io_enq_req_{lane}_"
        dispatch.append(Dispatch(bool(pins[prefix + "valid"]), bool(pins[prefix + "bits_needAlloc"]), rob(prefix + "bits_uop_robIdx_"),
                                 pins[prefix + "bits_uop_numLsElem"], sq(prefix + "bits_reqEndPtr_sqIdx_")))
    return Inputs(tuple(dispatch), rob("io_fromRob_robHeadPtr_"),
                  Redirect(bool(pins["io_redirect_valid"]), rob("io_redirect_bits_robIdx_"), bool(pins["io_redirect_bits_level"])),
                  **{name: getattr(external, name) for name in SHARED_FIELDS})
