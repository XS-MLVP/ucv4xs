"""Typed constructors shared by PSQ functional tests."""
from suites.memblock.lsq.testbenches.psq.transactions import PublicResponse
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.shared.transactions import CacheRequest
from suites.memblock.lsq.testbenches.shared.transactions import ExceptionInfo
from suites.memblock.lsq.testbenches.shared.transactions import ForwardExpectation
from suites.memblock.lsq.testbenches.shared.transactions import RobIdentity
from suites.memblock.lsq.testbenches.shared.transactions import SbufferWord
from suites.memblock.lsq.testbenches.shared.transactions import UncacheRequest
from suites.memblock.lsq.testbenches.shared.transactions import Writeback


def sqptr(position):
    return SqPtr.encode(position)


def word(addr=None, vaddr=None, mask=None, data=None, wline=None, *, valid=1):
    return SbufferWord(valid=valid, addr=addr, vaddr=vaddr, mask=mask, data=data, wline=wline)


def forward(*, valid=1, forward_mask=None, forward_data=None, data_byte_mask=None, data_invalid=None,
            data_invalid_value=None, match_invalid=None, forward_invalid=None,
            addr_invalid=None):
    return ForwardExpectation(valid=valid, forward_invalid=forward_invalid, match_invalid=match_invalid,
                              addr_invalid=addr_invalid, data_invalid=data_invalid,
                              data_invalid_value=data_invalid_value, forward_mask=forward_mask,
                              forward_data=forward_data, data_byte_mask=data_byte_mask)


def rob(value=None, flag=None, former=None):
    return RobIdentity(value, flag, former)


def writeback(*, rob_identity=None, access_fault=None, bus_error=None, mmio=None, ncio=None, valid=1):
    return Writeback(rob_identity, access_fault, bus_error, mmio, ncio, valid)


def cache(address=None, opcode=None, *, valid=1):
    return CacheRequest(address, opcode, valid)


def uncache(*, addr=None, vaddr=None, data=None, mask=None, ident=None, nc=None, memory_backed=None, rob_identity=None):
    return UncacheRequest(addr, vaddr, data, mask, ident, nc, memory_backed, rob_identity)


def exception(*, vaddr=None, hyper=None, access_fault=None, bus_error=None, rob_identity=None, valid=1):
    return ExceptionInfo(vaddr, hyper, access_fault, bus_error, rob_identity, valid)


def observation(**fields):
    return PublicResponse(**fields)
