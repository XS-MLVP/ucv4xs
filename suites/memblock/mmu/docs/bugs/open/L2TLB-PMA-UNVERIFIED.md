# L2TLB-PMA-UNVERIFIED — PMA/PMP 交互覆盖缺口

## 状态与范围

```ucv-bug
{
  "id": "L2TLB-PMA-UNVERIFIED",
  "title": "PMA/PMP 交互覆盖缺口",
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
        "tests/l2/test_pmp.py::test_all_pma_entries",
        "tests/l2/test_l2tlb.py::test_pma_cacheable_page_tables_walk",
        "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
      ],
      "note": "验证缺口已补齐；未把内部 PMA 属性冒充公开输出。"
    }
  ],
  "resolution": {
    "reason": "fixed",
    "evidence": [
      "tests/l2/test_pmp.py::test_all_pma_entries",
      "tests/l2/test_l2tlb.py::test_pma_cacheable_page_tables_walk",
      "docs/spec/verification/evidence/reports/verification-soundness-20261025.md"
    ],
    "note": "验证缺口已补齐；未把内部 PMA 属性冒充公开输出。 当前基线待复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（旧版本已处置，当前待复验）。**

## 观察与处置

PMP 叶子覆盖 cfg/addr/mask，L2TLB 顶层补充 cacheable/readable TOR 与 C=0/R=0 fault 用例；PMA 属性输出仍在内部，不作为响应字段。

## 结论

验证缺口已补齐；未把内部 PMA 属性冒充公开输出。


## 历史处置

旧基线 `XiangShan 893e1580b705d81f113c30c7a05734e09a08050e` 上该验证缺口已完成并关闭；当前基线 `public-a0c2a26cb` 未复验，因此按当前主线状态规则将目录移回 open，保留旧 closed 版本与历史 resolution。旧证据和结论不删除、不改写。本次文档整理未运行 native。

## 历史证据

- [tests/l2/test_pmp.py::test_all_pma_entries](../../../tests/l2/test_pmp.py)
- [tests/l2/test_l2tlb.py::test_pma_cacheable_page_tables_walk](../../../tests/l2/test_l2tlb.py)
- [docs/spec/verification/evidence/reports/verification-soundness-20261025.md](../../spec/verification/evidence/reports/verification-soundness-20261025.md)
