# LSU-HWPF-MISS-001 — 硬件预取已 miss，性能事件 s2_hw_pf_miss 却恒为 0

## 状态与范围

```ucv-bug
{
  "id": "LSU-HWPF-MISS-001",
  "title": "硬件预取已 miss，性能事件 s2_hw_pf_miss 却恒为 0",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/verification/README.md",
        "manifest/baseline.json"
      ],
      "note": "当前基线未重建、未复跑 native；旧基线已复现/已复核，不能写成当前基线已复现。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "results/recheck-prefetch-spec-02/",
        "results/recheck-prefetch-seed-17-01/",
        "results/recheck-prefetch-seed-123-01/"
      ],
      "note": "种子 1/17/123 均 1 PASS/1 FAIL；命中对照通过。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未重建/未复跑；旧基线已复现，当前基线不得写成已复现）。**

## 现象

`isHwPrefetch` 蕴含 `isPrefetch`，而 `cause(C_DM)` 要求 `troubleMaker = !isPrefetch && !alwaysWriteback`；两者互斥，`s2_hw_pf_miss` 永不产生。`io_perf_3_value` 在 miss=1 的实际硬件预取上仍为 0。

## 预期依据

有效、未取消的硬件预取发生 DCache miss 时，延迟后的 s2_hw_pf_miss 事件应为 1；命中负对照应为 0。

## 复现与对照

独立 `LoadUnitS2` 原生 DUT：合法硬件预取编码、TLB 命中、无 redirect/kill/异常，DCache miss=1；命中对照 PASS，miss 反例普通 FAIL。节点 `test_hw_pf_miss_event_counts_a_real_cache_miss[1]`，实际 0、期望 1。

## 根因

`NewLoadUnit.scala:1059-1061,1120,1280-1286` 与 `package.scala:98-99` 的条件互斥；生成 `LoadUnitS2.sv:549-550,573-575,865-866,1137` 保留同一根因。

## 适用范围与仍未证明

只确认性能事件错误；未证明访存数据错误、死锁或整核 ISA 后果。NewLoadUnit 父块 perf7 是静态传播，不另计根因。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261026/01-LSU-HWPF-MISS-001.md](../evidence/bug-reports-20261026/01-LSU-HWPF-MISS-001.md)
- [docs/bugs/evidence/bug-reports-20261026/README.md](../evidence/bug-reports-20261026/README.md)
