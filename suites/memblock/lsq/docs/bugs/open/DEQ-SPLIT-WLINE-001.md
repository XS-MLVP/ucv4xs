# DEQ-SPLIT-WLINE-001 — 普通跨16B store尾段的wline错误继承相邻CBO.zero字段，即使相邻项未committed仍输出整line写控制

## 状态与范围

```ucv-bug
{
  "id": "DEQ-SPLIT-WLINE-001",
  "title": "普通跨16B store尾段的wline错误继承相邻CBO.zero字段，即使相邻项未committed仍输出整line写控制",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "docs/history/lsq-regression-a0c2a26cb-20261102.json",
        "docs/lessons/lsq-baseline-regression-20261103.md",
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md",
        "docs/spec/verification/evidence/reports/interaction-probes-20261106.md"
      ],
      "note": "2026-11-02/03 新基线完整回归记录 15 个失败节点，wline 仍来自 ctrlEntry.isCbo；2026-11-06 完整回归仍有 deq 目录失败。本次未重跑。"
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

普通跨16B store尾段的wline错误继承相邻CBO.zero字段，即使相邻项未committed仍输出整line写控制

SQ0普通8B store在VA0x9400c/PA0xabcd00c，data0x8877665544332211、mask0xff；相邻SQ1 CBO.zero。实际Sbuffer lane1 fire携带正确尾地址0xabcd010、mask0xf、有效data0x88776655，唯独wline=1而严格应0。

## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1174-1188,1243-1248,1272; soc-split/rtl/DeqModule.sv真实dataQueue连接`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/deq-lifecycle-expanded-01/随机seed54017，完整域后续3个种子复现`
- `lsq-expanded-08/population-history-audit-v1.json及expanded-09旧172逐bit复核：原普通split的真实STA/STD及相邻ROB头zero，经真实VSQ/PSQ在tick50消费尾段，正确原PA/mask/data但wline=1而应0；相邻非zero必要条件对照完成。明确protocol-only probe，不替代逐拍全输出参考。`
- `results/deq-lifecycle-expanded-03/中test_actual_split_tail_fire_keeps_ordinary_store_wline四例，立即/三拍背压、相邻已/未committed均为普通失败`
- `results/psq-initial-01/initial-audit.json：两个实际Sbuffer fire反例由真实STA/STD和分拆首末请求生成，VSQ代理enq2/preCommit1，未提交的相邻CBO.zero真实控制污染普通tail；psq-expanded-01保持同样2个普通失败。`
- `results/deq-lifecycle-expanded-03/lifecycle-audit.json，独立字节/UID公开历史审计及四个真实Sbuffer消费见证；相邻inval/clean/flush六个完整完成对照通过，完整域另一个400 UID种子与四个非zero对照仍运行`
- [tests/deq/test_lifecycle.py::test_full_seeded_mixed_traffic_and_fair_drain[full-domain-54017]](../../../tests/deq/test_lifecycle.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

真实LSQ公开边界已证实；完整Backend的CBO发射/仲裁及ISA后果仍未证明，不扩大为架构整line破坏。不修改RTL、不将wline当don't-care、不读取此问题表调整参考。

## 历史证据

- [旧报告](../evidence/bug-reports-20261022/09-DEQ-SPLIT-WLINE-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
