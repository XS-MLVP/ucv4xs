# DCACHE-DENIED-ERROR-PADDR-ZERO：L2 denied/corrupt 的 paddr 只保留 vaddr 低位

状态：**已关闭（仅历史误报分类），非缺陷**。该 `closed/invalid` 只关闭历史基线的误报，
当前默认基线 `public-a0c2a26cb` 另未复验（JSON 记 `unverified`）。
`io_error.paddr` 在冷行 L2 denied/corrupt 路径上等于
`vaddr[11:0]`；页对齐地址会退化为 0。这是字段固有语义，不是错误地址丢失。

## 原问题

测试观察到 denied refill 时 `io_error.paddr=0`，曾怀疑 MainPipe 没有上报物理地址。
实际上 MainPipe 用 `Cat(s2_tag, get_untag(vaddr))` 重建上报地址；冷行 tag 仍为 0，
因此只剩 `vaddr[11:0]`。此前测试地址页对齐（低 12 位为 0），所以看到 0。

## 独立预期与实测

| 输入地址 | `io_error.paddr` | `report_to_beu` |
|---|---|---|
| `0x11000` | `0x0` | 0 |
| `0x11440` | `0x440` | 0 |
| `0x123C0` | `0x3C0` | 0 |

`report_to_beu` 只对 tag/data ECC 错误置 1；L2 denied/corrupt 时为 0，BEU 不消费该
paddr。因此消费者不应在 L2 错误上用 paddr 定位行。

## 用例与范围

新增普通通过用例
[tests/dcache/test_dcache.py](../../../tests/dcache/test_dcache.py)::test_denied_refill_error_paddr_is_vaddr_low_bits 固化该契约。
该结论只适用于当前 MainPipe 错误上报实现；如果上游将来希望 L2 错误携带完整 paddr，
需要改用 `s2_req.addr` 并单独定义字段，不能沿用本用例的期望。

## 证据

- [P0 收口报告第 2.2 节](../../spec/verification/evidence/p0-closure-20261026.md)
- 功能点 [DC-FP-009](../../spec/design/functional-points-dcache.md)
- [manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "DCACHE-DENIED-ERROR-PADDR-ZERO",
  "title": "L2 denied/corrupt 的 io_error.paddr 只保留 vaddr[11:0]",
  "kind": "investigation",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "closed",
      "evidence": [
        "suites/memblock/dcache/docs/spec/verification/evidence/p0-closure-20261026.md",
        "suites/memblock/dcache/tests/dcache/test_dcache.py::test_denied_refill_error_paddr_is_vaddr_low_bits"
      ],
      "note": "三个地址实测 paddr=vaddr[11:0]；report_to_beu=0"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "suites/memblock/dcache/README.md"
      ],
      "note": "当前默认基线尚未重新 prepare/build/run，不能沿用历史结论"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "suites/memblock/dcache/docs/spec/verification/evidence/p0-closure-20261026.md"
    ],
    "note": "字段语义如此，BEU 不消费；已用普通用例固定契约"
  }
}
```
