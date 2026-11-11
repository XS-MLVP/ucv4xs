import json

from suites.memblock.lsq.testbenches.shared.env.dut import ROOT
from suites.memblock.lsq.testbenches.enter_sbuffer.transactions import Inputs
from suites.memblock.lsq.testbenches.enter_sbuffer.transactions import Offer
from suites.memblock.lsq.testbenches.enter_sbuffer.transactions import Write
from suites.memblock.lsq.testbenches.enter_sbuffer.transactions import encode
from suites.memblock.lsq.testbenches.enter_sbuffer.transactions import SbufferWord
from suites.memblock.lsq.testbenches.enter_sbuffer.transactions import Observation
from suites.memblock.lsq.testbenches.shared.transactions import UNSET


class Ports:
    def __init__(self, dut):
        self.dut, self.inputs, self.outputs = dut, {}, {}
        def walk(node, prefix=()):
            if "Pin" in node:
                name = "_".join(prefix)
                if name != "clock":
                    (self.inputs if node["Pin"] == "input" else self.outputs)[name] = getattr(dut, name)
            else:
                for name, child in node.items():
                    if isinstance(child, dict):
                        walk(child, (*prefix, name))
        walk(json.loads((ROOT / "dut/enter_sbuffer_queue/signals.json").read_text()))
        assert set(self.inputs) == set(encode(Inputs())) and len(self.inputs) == 16

    def sample(self, event):
        values = {name: pin.U() for name, pin in self.inputs.items()}
        offers = []
        for lane in range(2):
            prefix = f"io_fromDeqModule_{lane}_"
            get = lambda key: values[prefix + "bits_" + key]
            write = Write(get("addr"), get("vaddr"), get("data"), get("mask"), bool(get("wline")), bool(get("deqPtrMove")) if lane == 0 else True)
            offers.append(Offer(bool(values[prefix + "valid"]), write))
        inp = Inputs(tuple(offers), tuple(bool(values[f"io_toSbuffer_req_{lane}_ready"]) for lane in range(2)), bool(values["reset"]))
        return inp, {name: pin.U() for name, pin in self.outputs.items()}

    def observe(self, pins):
        """Decode one sampled public window into immutable transactions."""
        def word(lane):
            prefix = f"io_toSbuffer_req_{lane}_"
            return None if not pins[prefix + "valid"] else SbufferWord(
                1, pins[prefix + "bits_addr"], pins[prefix + "bits_vaddr"], pins[prefix + "bits_data"],
                pins[prefix + "bits_mask"], bool(pins[prefix + "bits_wline"]))
        return Observation(
            bool(pins["io_empty"]),
            (bool(pins["io_deqPtrMove_0"]), bool(pins["io_deqPtrMove_1"])),
            (bool(pins["io_fromDeqModule_0_ready"]), bool(pins["io_fromDeqModule_1_ready"])),
            word(0), word(1))

    def expected(self, observation):
        out = {"io_empty": observation.empty} if observation.empty is not None else {}
        if observation.deq_pointer_moves is not UNSET:
            for lane, value in enumerate(observation.deq_pointer_moves):
                if value is not None:
                    out[f"io_deqPtrMove_{lane}"] = value
        if observation.accept_ready is not UNSET:
            for lane, value in enumerate(observation.accept_ready):
                if value is not None:
                    out[f"io_fromDeqModule_{lane}_ready"] = value
        for lane, word in enumerate((observation.sbuffer_word_0, observation.sbuffer_word_1)):
            if word is UNSET:
                continue
            out.update(self.word_expected(lane, word))
        return out

    def word_expected(self, lane, word):
        prefix = f"io_toSbuffer_req_{lane}_"
        if word is None:
            return {prefix + "valid": 0}
        assert isinstance(word, SbufferWord), word
        out = {prefix + "valid": int(word.valid if word.valid is not None else 1)}
        for field, suffix in (("addr", "addr"), ("vaddr", "vaddr"), ("data", "data"), ("mask", "mask"), ("wline", "wline")):
            value = getattr(word, field)
            if value is not None:
                out[prefix + "bits_" + suffix] = value
        return out
