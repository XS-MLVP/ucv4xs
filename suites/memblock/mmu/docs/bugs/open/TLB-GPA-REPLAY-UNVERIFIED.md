# TLB-GPA-REPLAY-UNVERIFIED — TLB GPA/getGpa 重放覆盖缺口

## 状态与范围

```ucv-bug
{
  "id": "TLB-GPA-REPLAY-UNVERIFIED",
  "title": "TLB GPA/getGpa 重放覆盖缺口",
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
        "tests/tlb/test_tlb.py::test_gpa_replay_for_all_stage_gpf",
        "results/tlb-gpa-tests-06/coverage-audit.json"
      ],
      "note": "旧缺口由新增验证补齐；当前基线未重跑，关闭依据为历史补充用例和审计。"
    }
  ],
  "resolution": {
    "reason": "fixed",
    "evidence": [
      "tests/tlb/test_tlb.py::test_gpa_replay_for_all_stage_gpf",
      "results/tlb-gpa-tests-06/coverage-audit.json"
    ],
    "note": "旧缺口由新增验证补齐；当前基线未重跑，关闭依据为历史补充用例和审计。 当前基线待复验。",
    "historical": true
  }
}
```


**当前基线 `public-a0c2a26cb`：unverified（旧版本已处置，当前待复验）。**

## 观察与处置

补充 `test_gpa_replay_for_all_stage_gpf` 后 need_gpa/GPA 重放可观察，TLB 行覆盖从 3644/3657 提升到 3655/3657。

## 结论

旧缺口由新增验证补齐；当前基线未重跑，关闭依据为历史补充用例和审计。


## 历史处置

旧基线 `XiangShan 893e1580b705d81f113c30c7a05734e09a08050e` 上该验证缺口已完成并关闭；当前基线 `public-a0c2a26cb` 未复验，因此按当前主线状态规则将目录移回 open，保留旧 closed 版本与历史 resolution。旧证据和结论不删除、不改写。本次文档整理未运行 native。

## 历史证据

- [tests/tlb/test_tlb.py::test_gpa_replay_for_all_stage_gpf](../../../tests/tlb/test_tlb.py)
- `results/tlb-gpa-tests-06/coverage-audit.json`
