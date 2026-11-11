# DEQ-ZERO-001 — CBO.zero处于writeZero时，旧普通store的Sbuffer fire可被误当自己的零写，随后WB并释放SQ但没有零写副作用

## 状态与范围

```ucv-bug
{
  "id": "DEQ-ZERO-001",
  "title": "CBO.zero处于writeZero时，旧普通store的Sbuffer fire可被误当自己的零写，随后WB并释放SQ但没有零写副作用",
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
      "note": "2026-11-02/03 新基线完整回归记录 15 个节点仍失败，逐条源码确认 CboState.writeZero 退出条件未改；本次未重跑。"
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

CBO.zero处于writeZero时，旧普通store的Sbuffer fire可被误当自己的零写，随后WB并释放SQ但没有零写副作用



## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:975-978,980-983；旧请求仍可驻留真实EnterSbufferQueue`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/psq-model-expanded-01/，独立UID账本发现zero owner没有自己的Sbuffer片段却完成WB/SQ释放`
- `lsq-expanded-08/population-history-audit-v1.json及expanded-09旧172逐bit复核：年轻缓存Load完成独立义务；tick66仅旧普通Store实际fire、tick70 zero实际WB、tick72 SQ已到2且两队列empty，zero自己的PA零写0次。无旧项对照完成；明确protocol-only probe，不冒充全输出参考。`
- `results/psq-expanded-05/lifecycle-audit.json及test_zero_owner的zero-owner-check.json：tick46旧普通store fire、tick50实际zero WB、tick56已释放SQ2，自己的零写0次`
- `results/sq-expanded-03/lifecycle-audit.json：真实VSQ/PSQ在旧普通请求驻留时接受ROB头zero，tick68只消费旧普通写，随后实际zero WB并释放SQ/全空，自己的零写0次；无旧项对照正常完成。`
- [tests/psq/test_zero_owner.py::test_zero_wb_has_its_own_real_zero_sbuffer_transfer[True]](../../../tests/psq/test_zero_owner.py)
- [tests/psq/test_full_model.py::test_full_reference_external_uid_actor_seeded_mix_and_drain[21249]](../../../tests/psq/test_full_model.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

真实LSQ公开边界已复现，完整Backend发行/背压及ISA后果未证明。问题表不参与测试或参考，也不是xfail/豁免。

## 历史证据

- [旧报告](../evidence/bug-reports-20261022/02-DEQ-ZERO-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
