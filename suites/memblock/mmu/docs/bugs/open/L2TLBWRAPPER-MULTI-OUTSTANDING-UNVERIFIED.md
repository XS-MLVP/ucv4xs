# L2TLBWRAPPER-MULTI-OUTSTANDING-UNVERIFIED — wrapper 多 outstanding 覆盖缺口

## 状态与范围

```ucv-bug
{
  "id": "L2TLBWRAPPER-MULTI-OUTSTANDING-UNVERIFIED",
  "title": "wrapper 多 outstanding 覆盖缺口",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/verification/README.md",
        "manifest/baseline.json",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "旧版本已处置（旧基线验证缺口完成），当前基线未重建、未复跑 native；待复验，不能写成当前通过。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "closed",
      "evidence": [
        "tests/l2/test_l2tlbwrapper.py::test_wrapper_four_outstanding",
        "docs/spec/verification/evidence/reports/l2tlbwrapper-20261025.md"
      ],
      "note": "覆盖缺口已补齐；>2 的更多压力不等于整 MMU 验收。"
    }
  ],
  "resolution": {
    "reason": "fixed",
    "evidence": [
      "tests/l2/test_l2tlbwrapper.py::test_wrapper_four_outstanding",
      "docs/spec/verification/evidence/reports/l2tlbwrapper-20261025.md"
    ],
    "note": "覆盖缺口已补齐；>2 的更多压力不等于整 MMU 验收。 当前基线待复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（旧版本已处置，当前待复验）。**

## 观察与处置

`mem_latency` 0/1/7 下 4 个 outstanding 请求通过 wrapper；旧 latency-7 workaround 掩盖了 A 请求监视丢失。

## 结论

覆盖缺口已补齐；>2 的更多压力不等于整 MMU 验收。


## 历史处置

旧基线 `XiangShan 893e1580b705d81f113c30c7a05734e09a08050e` 上该验证缺口已完成并关闭；当前基线 `public-a0c2a26cb` 未复验，因此按当前主线状态规则将目录移回 open，保留旧 closed 版本与历史 resolution。旧证据和结论不删除、不改写。本次文档整理未运行 native。

## 历史证据

- [tests/l2/test_l2tlbwrapper.py::test_wrapper_four_outstanding](../../../tests/l2/test_l2tlbwrapper.py)
- [docs/spec/verification/evidence/reports/l2tlbwrapper-20261025.md](../../spec/verification/evidence/reports/l2tlbwrapper-20261025.md)
