# LQU-MMIO-IF-001 — 多个MMIO selector有效时所有selector收到共同ready，只有高ID输出总线，低ID也进入等待响应而丢失其请求

## 状态与范围

```ucv-bug
{
  "id": "LQU-MMIO-IF-001",
  "title": "多个MMIO selector有效时所有selector收到共同ready，只有高ID输出总线，低ID也进入等待响应而丢失其请求",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/verification/evidence/reports/interaction-probes-20261106.md",
        "manifest/known-issues.json"
      ],
      "note": "当前基线没有该接口边界用例的逐节点复验；2026-11-06 完整回归的 load_uncache 目录仍有失败，但未逐条证明包含本边界。不得写成当前已复现。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "docs/bugs/evidence/bug-reports-20261022/README.md",
        "manifest/known-issues.json"
      ],
      "note": "旧基线 893e1580 的接口边界普通失败；保留为历史复现，域限制不变。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未复验；旧基线结论不得写成当前已复现）。**

**域限制**：该条只证明接口边界行为，不声称正常架构流量可达；目录状态仍为 open。

## 现象

多个MMIO selector有效时所有selector收到共同ready，只有高ID输出总线，低ID也进入等待响应而丢失其请求



## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:421-429,444-453`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- [tests/load_uncache/test_timing_boundaries.py::test_multiple_mmio_selectors_interface_priority_not_rob_legality_claim](../../../tests/load_uncache/test_timing_boundaries.py)
- `results/load-uncache-expanded-02/`
- `UNIT-INTERFACE边界：pending跨过两个未完成MMIO；不符合常规ROB提交许可代理，不声称合法架构流量可达或系统硬件缺陷已证实`

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

保留普通失败和域限制；不把该边界当正常ROB行为，也不以放宽参考使其通过。合法MMIO/NC优先用例另行运行。

## 历史证据

- （该问题在 [manifest/known-issues.json](../../../manifest/known-issues.json) 与后续审计中首次登记，无独立旧报告文件。）
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
