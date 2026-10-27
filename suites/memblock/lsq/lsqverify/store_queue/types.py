"""Only actual external StoreQueue inputs, never synthetic VSQ permissions."""
from dataclasses import dataclass, fields

from lsqverify.forward.types import Query, Translation
from lsqverify.psq.types import Address, Attributes, Data, Inputs as PsqInputs, SecondPage, encode as psq_encode
from lsqverify.vlq.types import Redirect, RobPtr
from lsqverify.vsq.types import Dispatch, Inputs as VsqInputs, encode as vsq_encode


@dataclass(frozen=True)
class Inputs:
    dispatch: tuple = (Dispatch(),) * 8
    rob_head: RobPtr = RobPtr()
    redirect: Redirect = Redirect()
    addresses: tuple = (Address(), Address())
    attributes: tuple = (Attributes(), Attributes())
    data: tuple = (Data(), Data())
    second_pages: tuple = (SecondPage(), SecondPage())
    queries: tuple = (Query(),) * 3
    translations: tuple = (Translation(),) * 3
    sbuffer_ready: tuple = (False, False)
    sbuffer_empty: bool = True
    cache_ready: bool = False
    cache_response: bool = False
    cache_denied: bool = False
    cache_corrupt: bool = False
    uncache_ready: bool = False
    uncache_ack_valid: bool = False
    uncache_ack_to_load: bool = False
    uncache_response: bool = False
    writeback_ready: bool = False
    reset: bool = False


SHARED_FIELDS = tuple(field.name for field in fields(Inputs) if field.name not in ("dispatch", "rob_head", "redirect"))


def execution(inp, **connected):
    return PsqInputs(**{name: getattr(inp, name) for name in SHARED_FIELDS}, **connected)


def encode(inp):
    physical = {key: value for key, value in psq_encode(execution(inp)).items() if not key.startswith("io_fromVirtualStoreQueue_")}
    virtual = {key: value for key, value in vsq_encode(VsqInputs(dispatch=inp.dispatch, rob_head=inp.rob_head, redirect=inp.redirect, reset=inp.reset)).items()
               if not key.startswith("io_fromPhysicalQueue_")}
    assert physical["reset"] == virtual["reset"]
    physical.update(virtual)
    assert len(physical) == 182
    return physical
