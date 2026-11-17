"""Existing Bitmap completion checks (BM-01/BM-03); no response-derived oracle."""


def check_response(resp: dict, *, cf: int, cfs: list[int], request_id: int) -> None:
    assert resp["cf"] == cf and resp["cfs"] == cfs and resp["id"] == request_id
