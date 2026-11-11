# DEQ-FINISH-ORDER-001 — 第二head的NC/IO handleFinish被无身份PopCount加入释放计数，能越过未消费旧普通项提前释放其SQ所有权

## 状态与范围

```ucv-bug
{
  "id": "DEQ-FINISH-ORDER-001",
  "title": "第二head的NC/IO handleFinish被无身份PopCount加入释放计数，能越过未消费旧普通项提前释放其SQ所有权",
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
      "note": "上游 4efe9f034 已修复 6 个节点，但新基线完整回归仍记录 14 个节点因 split 语义失败；当前基线仍未完全修复，本次未重跑。"
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

第二head的NC/IO handleFinish被无身份PopCount加入释放计数，能越过未消费旧普通项提前释放其SQ所有权



## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1301,1318-1324,1658-1659；特殊read==deq只在注释声称，真实PSQ/VSQ未保证`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/sq-stream-directed-01/，独立flow账本发现必要条件随机25090的旧split credit提前；不是把失败当作检查器时限放宽`
- `lsq-expanded-08/population-history-audit-v1.json及expanded-09旧172逐bit复核：memory1/2/7各一例，真实VSQ将年轻特殊项许可为ROB头，旧普通Sbuffer原字节消费0次，tick66/70公开SQ头已从0到1、随后到2；先消费老项的3对照真正排空。明确protocol-only probe，不冒充全输出参考；失败NC例仍欠外部resp单列保留。`
- `results/sq-expanded-03/lifecycle-audit.json：memory type1/2/7三个最小例Sbuffer ready始终false、旧普通请求实际消费0次，年轻NC确认或IO实际WB后sqDeqPtr从0到1且旧请求仍valid；另随机1例同类提前credit`
- [tests/store_queue/test_special.py::test_later_special_finish_cannot_release_an_unconsumed_ordinary_head[1-False]](../../../tests/store_queue/test_special.py)
- [tests/store_queue/test_special.py::test_later_special_finish_cannot_release_an_unconsumed_ordinary_head[2-False]](../../../tests/store_queue/test_special.py)
- [tests/store_queue/test_special.py::test_later_special_finish_cannot_release_an_unconsumed_ordinary_head[7-False]](../../../tests/store_queue/test_special.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

真实LSQ公开producer边界确认；根因也可能由父级补强特殊头约束解决，不假定仅叶子需要修复。尚未证明完整Backend发射/仲裁约束或ISA后果；不改RTL、不豁免失败。

## 历史证据

- [旧报告](../evidence/bug-reports-20261022/03-DEQ-FINISH-ORDER-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
