"""Only actual external StoreQueue inputs, never synthetic VSQ permissions."""
from dataclasses import dataclass, fields

from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.psq.transactions import Address
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.psq.transactions import Data
from suites.memblock.lsq.testbenches.psq.transactions import Inputs as PsqInputs
from suites.memblock.lsq.testbenches.psq.transactions import SecondPage
from suites.memblock.lsq.testbenches.psq.transactions import encode as psq_encode
from suites.memblock.lsq.testbenches.vlq.transactions import Redirect
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vsq.transactions import Dispatch
from suites.memblock.lsq.testbenches.vsq.transactions import Inputs as VsqInputs
from suites.memblock.lsq.testbenches.vsq.transactions import encode as vsq_encode


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


# --- Immutable public-response observations (decode stays in env/ports) ---
from suites.memblock.lsq.testbenches.shared.transactions import UNSET as _UNSET
from suites.memblock.lsq.testbenches.shared.transactions import CacheRequest as _CacheRequest
from suites.memblock.lsq.testbenches.shared.transactions import ExceptionInfo as _ExceptionInfo
from suites.memblock.lsq.testbenches.shared.transactions import ForwardResponse as _ForwardResponse
from suites.memblock.lsq.testbenches.shared.transactions import SbufferWord as _SbufferWord
from suites.memblock.lsq.testbenches.shared.transactions import UncacheRequest as _UncacheRequest
from suites.memblock.lsq.testbenches.shared.transactions import Writeback as _Writeback


@dataclass(frozen=True)
class Observation:
    empty: int | None = None
    full: int | None = None
    force_write: int | None = None
    flush: int | None = None
    mmio_busy: int | None = None
    cache_response_ready: int | None = None
    dequeue_valid: int | None = None
    dequeue_count: int | None = None
    sq_deq_ptr: object = None
    physical_upper: object = None
    enq_dequeue_valid: int | None = None
    enq_dequeue_count: int | None = None
    recover_stall: int | None = None
    redirect_ptr: object = None
    redirect_valid: int | None = None
    addr_ready_ptr: object = None
    data_ready_ptr: object = None
    addr_ready_mask: int | None = None
    data_ready_mask: int | None = None
    addr_ready_clear_mask: int | None = None
    data_ready_clear_mask: int | None = None
    unalign_ready: tuple[int | None, int | None] | object = _UNSET
    sbuffer_word_0: _SbufferWord | None | object = _UNSET
    sbuffer_word_1: _SbufferWord | None | object = _UNSET
    cache_request: _CacheRequest | None | object = _UNSET
    uncache_request: _UncacheRequest | None | object = _UNSET
    writeback: _Writeback | None | object = _UNSET
    exception_info: _ExceptionInfo | None | object = _UNSET
    forward: tuple[_ForwardResponse, ...] = ()
