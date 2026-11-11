# LSU-MATCHINV-CAUSE-001 — matchInvalid 回写仍携带 replay cause，LQ 建立伪重放项

## 状态与范围

```ucv-bug
{
  "id": "LSU-MATCHINV-CAUSE-001",
  "title": "matchInvalid 回写仍携带 replay cause，LQ 建立伪重放项",
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
      "note": "上游 #5810 仍 open；固定 RTL 未修。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未重建/未复跑；旧基线已复现，当前基线不得写成已复现）。**

## 现象

S3 beat `matchInvalid=1, cause_4=1, causeOrR=1` 时，`rollback_valid=1`，但 `lqWrite.rep_info_need_rep=1` 且 `cause_4=1`；期望 `need_rep=0`、所有 cause 清 0。

## 预期依据

matchInvalid 是终结性 poisoned-load 路径，应只触发 rollback/flush，不应在 LQ 建立 replay entry。

## 复现与对照

定向 S3 用例；同时检查 rollback、pipeOut 与 LQ cause；旧测试只看前两者，漏掉 LQ 副作用。

## 根因

`NewLoadUnit.scala:1561` 的 `lqWriteCause = Mux(useS4HeadReplay, s4HeadReplayCause, cause)` 没有 matchInvalid 优先清零。

## 适用范围与仍未证明

确认公开 LQ 写回字段；未证明后续 redirect 清理一定失效或整核后果。

## 历史证据

- [docs/bugs/evidence/bug-reports-20261026/05-upstream-review-20261026.md](../evidence/bug-reports-20261026/05-upstream-review-20261026.md)
- <https://github.com/OpenXiangShan/XiangShan/issues/5810>
