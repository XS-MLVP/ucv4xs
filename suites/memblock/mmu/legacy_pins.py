"""Central mapping from logical pin fields to generated RTL names.

Functional tests use this schema; only this module spells physical names.
"""


class Pins:
    """Logical field names; ``io`` adds the generated RTL prefix."""

    def io(self, suffix: str) -> str:
        return "io_" + suffix

    p_bitmap_req_ready = "io_bitmap_req_ready"
    p_bitmap_resp_bits_cf = "io_bitmap_resp_bits_cf"
    p_bitmap_resp_valid = "io_bitmap_resp_valid"
    p_bitmap_wakeup_ready = "io_bitmap_wakeup_ready"
    p_bitmap_wakeup_valid = "io_bitmap_wakeup_valid"
    p_csr_hgatp_changed = "io_csr_hgatp_changed"
    p_csr_priv_virt_changed = "io_csr_priv_virt_changed"
    p_csr_satp_changed = "io_csr_satp_changed"
    p_csr_vsatp_changed = "io_csr_vsatp_changed"
    p_hptw_req_ready = "io_hptw_req_ready"
    p_hptw_resp_valid = "io_hptw_resp_valid"
    p_llptw_ready = "io_llptw_ready"
    p_mem_mask = "io_mem_mask"
    p_mem_req_ready = "io_mem_req_ready"
    p_mem_resp_valid = "io_mem_resp_valid"
    p_pmp_resp_ld = "io_pmp_resp_ld"
    p_pmp_resp_mmio = "io_pmp_resp_mmio"
    p_refill_valid = "io_refill_valid"
    p_req_valid = "io_req_valid"
    p_resp_ready = "io_resp_ready"
    p_sfence_valid = "io_sfence_valid"


P = Pins()
