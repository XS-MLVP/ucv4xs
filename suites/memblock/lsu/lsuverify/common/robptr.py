"""Circular-pointer relations used by more than one LSU DUT.

These are written from the *relation* definitions in the Chisel source, not
from any generated bit expression:

* ``RobPtr`` (RobBundles.scala:294-358): ``flag`` is the wrap bit, ``value`` is
  the slot index, ``isFormer`` splits one ROB entry into two uops.
* ``SqPtr`` (NewStoreQueue.scala:34-58 + MultiFlagCircualQueuePtr.scala:95-180):
  ``first_flag`` is the wrap bit, ``second_flag`` is the extra flag needed
  because the physical SQ is not a power of two times its multiple,
  ``operation_value = {second_flag, value}``.

Sharing them keeps ``needFlush`` and ``withInPhysicalQueue`` defined exactly once
for the whole project.
"""
from __future__ import annotations

# RobSize=160, so RobPtr.value is 8 bits wide.
ROB_SIZE = 160
ROB_VALUE_BITS = 8

# StoreQueuePhysicalSize=64, StoreQueueMultiple=2.
SQ_PHYSICAL_SIZE = 64
SQ_MULTIPLE = 2
SQ_VALUE_BITS = 6
SQ_SECOND_FLAG_BITS = 1

LEVEL_FLUSH_AFTER = 0
LEVEL_FLUSH = 1


def is_same_entry(a_flag: int, a_value: int, b_flag: int, b_value: int) -> bool:
    return a_flag == b_flag and a_value == b_value


def is_same_slot(a_flag: int, a_value: int, a_former: int,
                 b_flag: int, b_value: int, b_former: int) -> bool:
    return is_same_entry(a_flag, a_value, b_flag, b_value) and a_former == b_former


def is_after_slot(a_flag: int, a_value: int, a_former: int,
                  b_flag: int, b_value: int, b_former: int) -> bool:
    """``RobPtr.isAfterSlot``: ring compare plus former/latter ordering."""
    if is_same_entry(a_flag, a_value, b_flag, b_value):
        return (not a_former) and bool(b_former)
    return (a_flag ^ b_flag ^ (1 if a_value > b_value else 0)) == 1


def rob_need_flush(rob_flag: int, rob_value: int, rob_former: int,
                   redirect: dict) -> bool:
    """``RobPtr.needFlush``: flushItself (level=flush, same slot) or strictly after."""
    if not redirect["valid"]:
        return False
    if redirect["level"] == LEVEL_FLUSH:
        if is_same_slot(rob_flag, rob_value, rob_former,
                        redirect["flag"], redirect["value"], redirect["former"]):
            return True
    return is_after_slot(rob_flag, rob_value, rob_former,
                         redirect["flag"], redirect["value"], redirect["former"])


def sq_operation_value(second_flag: int, value: int) -> int:
    return ((second_flag & ((1 << SQ_SECOND_FLAG_BITS) - 1)) << SQ_VALUE_BITS) | (
        value & ((1 << SQ_VALUE_BITS) - 1))


def sq_ge(a_first: int, a_second: int, a_value: int,
          b_first: int, b_second: int, b_value: int) -> bool:
    """``MultiFlagCircularQueuePtr.>=``: flag XOR numerical compare."""
    return bool(a_first ^ b_first) ^ (
        sq_operation_value(a_second, a_value) >= sq_operation_value(b_second, b_value))


def sq_lt(a_first: int, a_second: int, a_value: int,
          b_first: int, b_second: int, b_value: int) -> bool:
    return bool(a_first ^ b_first) ^ (
        sq_operation_value(a_second, a_value) < sq_operation_value(b_second, b_value))


def sq_add(first: int, second: int, value: int, amount: int) -> tuple[int, int, int]:
    """``SqPtr + v`` in the power-of-two branch used by this configuration.

    ``multiEntries = 64 * 2 = 128`` is a power of two, so the Chisel code takes
    ``(Cat(first_flag, operation_value) + v)`` and simply splits the 8-bit sum
    back into ``first_flag`` / ``second_flag`` / ``value``.
    """
    raw = ((first & 1) << 7) | ((second & 1) << 6) | (value & 0x3F)
    total = (raw + amount) & 0xFF
    return (total >> 7) & 1, (total >> 6) & 1, total & 0x3F


def sq_in_physical_queue(sq_first: int, sq_second: int, sq_value: int,
                         deq_first: int, deq_second: int, deq_value: int) -> bool:
    """``SqPtr.withInPhysicalQueue(start)``: ``this >= start && this < start + 64``."""
    end_first, end_second, end_value = sq_add(deq_first, deq_second, deq_value,
                                              SQ_PHYSICAL_SIZE)
    return sq_ge(sq_first, sq_second, sq_value, deq_first, deq_second, deq_value) and\
        sq_lt(sq_first, sq_second, sq_value, end_first, end_second, end_value)


def no_redirect() -> dict:
    return {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0}


def redirect(flag=0, value=0, former=1, level=LEVEL_FLUSH, valid=1) -> dict:
    return {"valid": valid, "level": level, "flag": flag, "value": value,
            "former": former}
