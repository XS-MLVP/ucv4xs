"""RPT-03 transparent response payload, derived from the offered transaction."""


def response_payload(tag: int, ppn: int, stage: int) -> dict:
    return {"tag": tag, "ppn": ppn, "s2xlate": stage}
