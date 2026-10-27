"""One-sided property oracles, deliberately not RTL-shaped predictors.

The existing ``ForwardModel.expected()`` predicts pin values.  That is useful
for timing, but if it copies an RTL decision (for example "span means full
coverage") it will agree with the RTL on the same bug.  The functions here do
not predict outputs.  They take the immutable producer ledger (original store
vaddr/paddr/size/mask/data, program order) and assert a property that must
hold no matter how the RTL is written:

* every load byte with an older in-flight store producer must be forwarded
  from the youngest such store, or the response must block the load;
* an exception candidate may only come from a real bus error, and the chosen
  candidate must be the oldest one by program order.

A violation means the RTL (or an equally wrong predictor) accepted stale data.
"""


def store_covers_byte(store, address):
    """Whether the original store request actually writes this physical byte."""
    if store.cache_operation:
        return address // 64 == store.paddr // 64
    offset = address - store.paddr
    return 0 <= offset < store.length and bool(store.mask >> offset & 1)


def youngest_byte_source(address, older_stores):
    """Youngest older store that really wrote ``address``; None if none did.

    ``older_stores`` is ordered oldest first, as the producer program order.
    """
    for _, store in reversed(tuple(older_stores)):
        if not store.address_ready:
            continue
        if store_covers_byte(store, address):
            return store
    return None


def forward_byte_violations(load, older_stores, observed, prefix):
    """List of (byte, reason) for unsafe accepted forwarding.

    ``load`` needs ``vaddr``, ``paddr`` and ``mask`` (byte mask in the 16B
    window).  ``observed`` is the sampled public output dict.
    """
    blocked = any(observed.get(prefix + field, 0) for field in (
        "bits_forwardInvalid", "bits_matchInvalid",
        "bits_addrInvalid_valid", "bits_dataInvalid_valid"))
    if blocked:
        return []
    window = load.paddr // 16 * 16
    violations = []
    for byte in range(16):
        if not (load.mask >> byte) & 1:
            continue
        address = window + byte
        source = youngest_byte_source(address, older_stores)
        if source is None:
            continue
        if not observed.get(prefix + f"bits_forwardMask_{byte}", 0):
            violations.append((byte, "in-flight store byte neither forwarded nor blocked"))
            continue
        if not source.data_ready:
            violations.append((byte, "forwarded from store whose data is not ready"))
            continue
        want = source.data >> (8 * (address - source.paddr)) & 0xFF
        if observed.get(prefix + f"bits_forwardData_{byte}", 0) != want:
            violations.append((byte, "forwarded byte does not match youngest producer"))
    return violations


def exception_candidate_violation(entries, observed):
    """Check uncache exception validity and oldest-by-program-order selection.

    ``entries`` is an iterable of dicts with at least ``rob_order``,
    ``uop_order``, ``bus_error`` and the payload fields the chosen exception
    would report (``rob_value``, ``vaddr``).  ``observed`` is the public
    ``io_exceptionInfo_*`` pin dict.
    """
    errors = [entry for entry in entries if entry["bus_error"]]
    valid = bool(observed.get("io_exceptionInfo_valid", 0))
    if not errors:
        return [] if not valid else [("valid", "exception reported without a bus error")]
    oldest = min(errors, key=lambda entry: (entry["rob_order"], entry["uop_order"]))
    if not valid:
        return [("valid", "real bus error did not produce an exception")]
    if observed.get("io_exceptionInfo_bits_robIdx_value") != oldest["rob_value"]:
        return [("robIdx", "exception owner is not the oldest bus error")]
    return []
