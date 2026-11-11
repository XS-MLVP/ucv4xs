# LSU-STD-PERF-001 — StdExeUnit 的 STD_out_of_range_issue 性能计数器条件取反

## 状态与范围

```ucv-bug
{
  "id": "LSU-STD-PERF-001",
  "title": "StdExeUnit 的 STD_out_of_range_issue 性能计数器条件取反",
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
        "results/upstream-review-regression-02/pytest.xml",
        "review/upstream_check_20261026_01/audit.json"
      ],
      "note": "上游 #6653；固定 RTL 未修。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未重建/未复跑；旧基线已复现，当前基线不得写成已复现）。**

## 现象

`XSPerfAccumulate("STD_out_of_range_issue", !(io.in.valid && s0IllegalIssue))` 统计的是“没有越界发射”的所有周期，包括 idle；应与越界发射条件同向。

## 预期依据

计数器应统计越界发射周期，不能把空闲/合法周期计入。

## 复现与对照

固定源码静态检查 `StdExeUnit.scala:87`；该计数器没有公开端口，因此保留源码契约普通 FAIL，不伪装成动态 DUT 观测。

## 根因

条件外层取反。上游 #6653 明确为性能计数器修复，不影响功能。

## 适用范围与仍未证明

仅性能；无动态端口证据，不能扩为功能缺陷。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261026/05-upstream-review-20261026.md](../evidence/bug-reports-20261026/05-upstream-review-20261026.md)
- <https://github.com/OpenXiangShan/XiangShan/issues/6653>
