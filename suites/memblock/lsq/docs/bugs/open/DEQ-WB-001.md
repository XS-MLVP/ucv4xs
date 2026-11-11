# DEQ-WB-001 — CBO Cache响应的denied/corrupt在writeBack背压等待一拍后被无条件清零，实际ready/valid消费时也丢失异常7/19

## 状态与范围

```ucv-bug
{
  "id": "DEQ-WB-001",
  "title": "CBO Cache响应的denied/corrupt在writeBack背压等待一拍后被无条件清零，实际ready/valid消费时也丢失异常7/19",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "docs/history/lsq-regression-a0c2a26cb-20261102.json",
        "docs/lessons/lsq-baseline-regression-20261103.md",
        "docs/spec/verification/evidence/reports/upstream-audit-20261103.md",
        "docs/spec/verification/evidence/reports/function-points-and-skill-20261103.md"
      ],
      "note": "2026-11-02/03 在 public-a0c2a26cb 的完整回归中该根因仍有 50 个失败节点，逐条源码确认未修复；2026-11-03 又新增 MMIO Store 总线故障反例（与 #6833 第 1 项同域）。本次文档整理未重跑 native。"
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

CBO Cache响应的denied/corrupt在writeBack背压等待一拍后被无条件清零，实际ready/valid消费时也丢失异常7/19

合法cacheable CBO子操作0、committed/addrValid/dataValid为1，Cache req/resp均实际握手，响应先以原denied/corrupt产生writeBack.valid及正确exception7/19；ready为0再等一拍，异常清0。随后ready=1，valid=1且rdataPtrMoveCnt=1，消费的数据异常仍为0。

同一类“未驱动/被清零的错误字段”也覆盖 MMIO Store 路径：`UncacheWordResp` 只驱动 `nderr/error`，`NewStoreQueue` 却读未驱动的 `denied/corrupt`；`PhysicalStoreQueue` 端口只有 `resp_valid`，没有 `resp_bits`。`test_uncache_store_fault.py` 的 1 个正常对照通过，`nderr=1` 和 `error=1` 两个反例在写回处 `exceptionVec_7/19` 仍为 0。按上游 #6833 第 1 项与 `DEQ-WB-001` 同一根因域记录，不重复计一个新的独立根因。

## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1082-1095,1098-1121; soc-split/rtl/DeqModule.sv:395-415`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/deq-initial-01/ (13 PASS/3 FAIL，停在背压期间)`
- `lsq-expanded-08/population-history-audit-v1.json及expanded-09旧172原始采样逐bit复核：真实VSQ/PSQ许可下，原Cache denied/corrupt/二者同时存在，背压3拍后tick56实际WB.fire异常7/19均0；3个立即WB对照通过。protocol-only probe范围明确，不冒称逐拍全输出参考。`
- `results/deq-fault-consumption-01/与results/deq-expanded-01/，3个新增用例均在实际writeBack.valid&&ready时检查，异常已为0`
- `results/deq-lifecycle-expanded-03/共9个WB失败，含旧6个probe与3个新完整分阶段参考严格保持检查；完整公开历史审计9746记录，44/46 checked，叶子仍NOT_PASS`
- `results/psq-initial-01/initial-audit.json与psq-expanded-01/storage-audit.json：真实五文件PSQ经STA/STD/S2及VSQ preCommit输入到达CBO，3个背压后实际WB fire仍丢失异常；三个无等待错误控制真实完成。`
- `tools/audit_deq_faults.py不导入参考模型，独立核验原Cache请求/响应、head稳定、错误捕获、等待和三个实际WB fire；fault-audit.json保存journal/tick/SHA。`

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

真实LSQ公开边界已确认，Backend/系统发射仲裁可达性及ISA后果仍未证明；不因DA满或缺陷存在提前结束整体目标。测试和probe均不读取本问题清单。

## 历史证据

- [旧报告](../evidence/bug-reports-20261022/01-DEQ-WB-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
