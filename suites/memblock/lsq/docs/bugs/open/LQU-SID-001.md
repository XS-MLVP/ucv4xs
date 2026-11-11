# LQU-SID-001 — 已回包但未消费的旧entry保留slaveId有效，合法重用该sid的新response覆盖旧数据/错误

## 状态与范围

```ucv-bug
{
  "id": "LQU-SID-001",
  "title": "已回包但未消费的旧entry保留slaveId有效，合法重用该sid的新response覆盖旧数据/错误",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "docs/history/lsq-regression-a0c2a26cb-20261102.json",
        "docs/lessons/lsq-baseline-regression-20261103.md",
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md"
      ],
      "note": "2026-11-02/03 新基线完整回归记录 29 个失败节点，slaveAccept 生命周期未改，逐条源码确认仍存在；本次未重跑。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "docs/bugs/evidence/bug-reports-20261022/README.md",
        "manifest/known-issues.json"
      ],
      "note": "旧基线 893e1580 的原回归证据；保留为历史复现。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：open（历史记录显示仍存在；本次未重跑 native）。**

## 现象

已回包但未消费的旧entry保留slaveId有效，合法重用该sid的新response覆盖旧数据/错误



## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:76-109,193-197,432-440`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- [tests/load_uncache/test_initial_probes.py::test_sid_reused_after_response_preserves_old_unconsumed_data](../../../tests/load_uncache/test_initial_probes.py)
- `results/load-uncache-initial-02/`
- `results/load-uncache-sid-expanded-01/: 10 PASS/7 FAIL; SID0/3/15 data and error corruption, consumed-before-reuse and different-SID controls pass`
- `results/lsq-expanded-04/bus-history-audit-v3.json：真实53文件Wrapper中6例SID合法复用失败，旧resp已返回后新ack重用SID4、两个新响应错误位取反，旧Load真实bypass消费时异常19/5变成新Load错误；不同SID的6个必要条件对照全部原数据/S3/VLQ完成。严格比较先在s1异常停机，不将本批未观察的s2字节冒称实际见证。`
- `results/lsq-expanded-15/mixed-history-audit-v3.json：三个bypass来源均先通过干净s1元信息，tick80实际旧Load s2应为0x1122334455667788重复128位，却为新Load的0xaabbccddeeff0011重复128位。旧resp tick38后新ack tick60才合法复用SID4，新resp tick62；两个正常NC原Load的fullVA与VA一致，ROB头不越过未完成Load。不同SID三个对照均完成两原UID。另混合种子28934/28935原始历史分别在tick214/556观察同类实际s2数据污染，不将这些中途失败计公平排空或架构后果。`
- [tests/load_uncache/test_sid_boundaries.py::test_old_data_held_while_new_same_sid_response_arrives[0]](../../../tests/load_uncache/test_sid_boundaries.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

确认固定生成RTL在真实22文件父块中的公开bypass数据与事务原响应不一致；未重新elaborate完整Chisel，未修复目标RTL，不把有限首轮probe当作完整父块参考或验收。

## 历史证据

- [旧报告](../evidence/bug-reports-20261022/04-LQU-SID-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
