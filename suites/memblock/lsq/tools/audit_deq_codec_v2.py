#!/usr/bin/env python3
"""Revised public occupancy-domain audit; v1 and all old snapshots retained."""
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from suites.memblock.lsq.deq.types import Inputs, encode


def main():
    for count in range(129):
        pins = encode(Inputs(valid_count=count))
        assert pins["io_validCnt"] == count
    for count in (-1, 129, 255, 256):
        try:
            encode(Inputs(valid_count=count))
        except ValueError:
            pass
        else:
            raise AssertionError("invalid virtual occupancy accepted")
    print(json.dumps({"status": "129_virtual_occupancies_encoded_and_four_outside_domain_rejected_not_native_ut",
                      "evidence": "NewStoreQueue.scala:1548/1619 virtualValidCount connects enqPtr.distanceBetween(deqPtrExt.head)",
                      "historical_correction": "v1 static audit covered 0..64 and incorrectly rejected65; its snapshot and report remain unchanged"}, indent=2))


if __name__ == "__main__":
    main()
