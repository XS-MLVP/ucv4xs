# LSQ-UPSTREAM-6229 — 真实 mask 只覆盖部分字节时被当作完整覆盖，缺失字节未重放

## 状态与范围

```ucv-bug
{
  "id": "LSQ-UPSTREAM-6229",
  "title": "真实 mask 只覆盖部分字节时被当作完整覆盖，缺失字节未重放",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md",
        "tests/fail_review/test_independent_forward_property.py",
        "docs/spec/verification/evidence/reports/same-source-audit-20261022.md"
      ],
      "note": "2026-11-02/03 新基线完整回归/定向性质检查记录 3 个 lane 失败，独立字节 oracle 与灵敏度对照通过；本次未重跑。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "manifest/known-issues.json"
      ],
      "note": "旧基线/关系核验阶段 3 个 lane 失败；保留为历史复现。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：open（历史记录显示仍存在；本次未重跑 native）。**

## 现象

跨 16B Store 的 `byteStart/byteEnd` 跨度看起来覆盖 Load，但真实 forward mask 只覆盖部分字节；缺失字节没有触发重放，Load 可能读到旧数据。

## 预期依据

每个应由未完成 Store 提供的字节，必须被前递或被阻塞；不能仅凭地址跨度判定完整覆盖。

## 复现与对照

`test_partial_store_coverage_must_block_or_forward_every_produced_byte` 三个 lane 均失败；独立字节 oracle 同时检查“已前递字节来源正确”和“应有字节没有遗漏”。

## 根因

`NewStoreQueue.scala:637-640` 的 `s2FullOverlap` 只比较 `byteStart/byteEnd`，不看真实 mask；旧参考模型同源，导致双方一起通过。

## 适用范围与仍未证明

本地已复现 RTL 响应差异；完整 LoadUnit/Backend 后果未证明。上游 #6229/#6312。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261022/14-relationship-11-vs-5.md](../evidence/bug-reports-20261022/14-relationship-11-vs-5.md)
- [docs/spec/verification/evidence/reports/same-source-audit-20261022.md](../../spec/verification/evidence/reports/same-source-audit-20261022.md)
- <https://github.com/OpenXiangShan/XiangShan/issues/6229>
