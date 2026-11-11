# LRQ-STRICT-001 — 没有真实入队的lane仍可能按schedIndex或不可用allocateSlot清除活动strict，导致地址ready位使严格依赖提前重放

## 状态与范围

```ucv-bug
{
  "id": "LRQ-STRICT-001",
  "title": "没有真实入队的lane仍可能按schedIndex或不可用allocateSlot清除活动strict，导致地址ready位使严格依赖提前重放",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "closed",
      "evidence": [
        "docs/history/lsq-regression-a0c2a26cb-20261102.json",
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md"
      ],
      "note": "2026-11-02/03 新基线完整回归记录 11 个节点 FAIL→PASS；上游 73cc6ee42（无真实 enq 不再清 strict）已进入当前基线，remaining_root_causes 不再列本项。本次文档整理未重跑 native，关闭依据是历史新基线完整运行记录与上游提交。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "docs/bugs/evidence/bug-reports-20261022/README.md",
        "manifest/known-issues.json"
      ],
      "note": "旧基线 893e1580 上 11 个节点失败；该历史结论保留。"
    }
  ],
  "resolution": {
    "reason": "fixed",
    "evidence": [
      "docs/history/lsq-regression-a0c2a26cb-20261102.json",
      "docs/spec/verification/evidence/reports/upstream-audit-20261103.md"
    ],
    "note": "旧基线 XiangShan 893e1580b705d81f113c30c7a05734e09a08050e 上该问题为 open；2026-11-02/03 新基线完整回归记录对应节点 FAIL→PASS，上游修复提交已进入 public-a0c2a26cb。本次文档整理未重跑 native。"
  }
}
```


**当前基线 `public-a0c2a26cb`：closed（历史新基线完整运行记录为 FAIL→PASS；本次未重跑 native）。**

## 现象

没有真实入队的lane仍可能按schedIndex或不可用allocateSlot清除活动strict，导致地址ready位使严格依赖提前重放

120个C_MA strict=true owner，SQ7，addressReadyPtr=0、sqEmpty=false、upper=64；仅addressReadyVec置1后slot0公开valid=1，期望0，输出uop.loadWaitStrict仍为1

## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala:393-395,825-828,861-865`。
- 生成 RTL 位置：`soc-split/rtl/LoadQueueReplay.sv:33683-35965`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/replay-expanded-01/`
- `replay-timing-directed-01 15 PASS/3 FAIL，三个lane的valid=false feedback payload均可清除活动strict；普通非strict payload负例、头窗口/优先/年龄/冷却均通过`
- `lsq-expanded-10/wrap-history-audit-v1.json：真实8个老Store+120个Load全池，SQ0地址缺口使实际指针仍0，只有SQ7真实STA/STD就绪、无匹配addressWakeup，tick312 Replay0.valid提前1且输出原uop.strict仍1；128UID失败保留，非strict全池对照完整完成。另expanded-08/09/10保留三个disabled反馈入口反例，均由真实SQ反馈而非外驱ready位激活。没有实际错误Replay握手或Backend/ISA后果声明。`
- [tests/replay/test_extended.py::test_strict_full_pool_is_not_unblocked_by_only_ready_bits](../../../tests/replay/test_extended.py)
- [tests/replay/test_timing.py::test_disabled_feedback_cannot_clear_strict_dependency[0]](../../../tests/replay/test_timing.py)
- [tests/replay/test_timing.py::test_disabled_feedback_cannot_clear_strict_dependency[1]](../../../tests/replay/test_timing.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

已实际确认全池及三个无效feedback入口的公开valid提前，不以内部strict寄存器作oracle；源码证据支持原因定位。必要条件对照和完整剩余语义仍继续补充。未修改目标RTL或严格参考。


## 历史处置

旧基线 `XiangShan 893e1580b705d81f113c30c7a05734e09a08050e` 上该问题为 open；`public-a0c2a26cb` 的 2026-11-02/03 完整回归记录对应节点 FAIL→PASS，上游修复提交已进入当前基线。目录因此从 open 移至 closed；旧基线版本和旧证据保留，不删除、不改写。本次文档整理未运行 native。

## 历史证据

- [当前基线完整回归与逐问题差分](../../../../../../docs/history/lsq-regression-a0c2a26cb-20261102.json)：`fixed_by_upstream.LRQ-STRICT-001 = 11`。
- [上游修复与本地节点复核](../../spec/verification/evidence/reports/upstream-audit-20261103.md)。
- [旧报告](../evidence/bug-reports-20261022/06-LRQ-STRICT-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
