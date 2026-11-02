"""The original700-frame port-pressure generator, preserving exact native words."""
from suites.frontend.ifu.model.uncache import Inputs


def random_port_inputs(rng):
    corrupt = int(rng.random() < 0.1)
    denied = int(rng.random() < 0.05)
    if denied and not corrupt:
        denied = 0
    return Inputs(
        flush=int(rng.random() < 0.03),
        req_valid=int(rng.random() < 0.35),
        req_paddr=rng.getrandbits(47) << 1,  # Old values were raw halfword coordinates.
        req_is_mmio=int(rng.random() < 0.3),
        req_pbmt=rng.randrange(4),
        is_first_instr=int(rng.random() < 0.3),
        ifu_stall=int(rng.random() < 0.25),
        empty_after=int(rng.random() < 0.3),
        to_ready=int(rng.random() < 0.7),
        from_valid=int(rng.random() < 0.3),
        from_data=rng.getrandbits(32),
        from_corrupt=corrupt, from_denied=denied,
        from_need_resend=int(rng.random() < 0.2),
    )
