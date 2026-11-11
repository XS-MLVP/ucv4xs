# LSU-S3-KILL-WB-001 — redirect kill 的 S3 Load 仍驱动 ldout、intRF 和 lqWrite 写回

## 状态与范围

```ucv-bug
{
  "id": "LSU-S3-KILL-WB-001",
  "title": "redirect kill 的 S3 Load 仍驱动 ldout、intRF 和 lqWrite 写回",
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
      "note": "上游 #6154 仍 open；固定 RTL 未修。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未重建/未复跑；旧基线已复现，当前基线不得写成已复现）。**

## 现象

S3 beat 已被 redirect kill，但 scalar 的 `ldoutValid`、`ldout.toRob.valid`、`lqWriteValid` 仍为 1；向量路径有 kill 门控，scalar 没有。

## 预期依据

被 kill 的 S3 Load 不得驱动写回、intRF 或 LQ 写入；三者应为 0。

## 复现与对照

S3 beat ROB index=30，redirect target=5（年轻于 redirect）；观察 `io_ldout_toRob_valid`、`io_ldout_toIntRf_valid`、`io_lqWrite_valid` 实际 `(1,1,1)`，期望 `(0,0,0)`。

## 根因

`NewLoadUnit.scala:1516,1529,1557` 的 scalar valid 没有 `!kill`；`:909` 的 kill 只用于另一部分逻辑。

## 适用范围与仍未证明

确认公开端口行为；未独立证明 RF 侧信道或整核后果。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261026/05-upstream-review-20261026.md](../evidence/bug-reports-20261026/05-upstream-review-20261026.md)
- <https://github.com/OpenXiangShan/XiangShan/issues/6154>
