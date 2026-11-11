# LSQ-BUS-OWNERSHIP-001 — NC outstanding期间旧Load响应无身份清除后来IO Store的串行占用，Store尚欠自身响应就提前暴露下一Load请求

## 状态与范围

```ucv-bug
{
  "id": "LSQ-BUS-OWNERSHIP-001",
  "title": "NC outstanding期间旧Load响应无身份清除后来IO Store的串行占用，Store尚欠自身响应就提前暴露下一Load请求",
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
      "note": "2026-11-02/03 新基线完整回归记录 6 个失败节点，s_load/s_store 仍在任意 resp.fire 后退出；本次未重跑。"
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

NC outstanding期间旧Load响应无身份清除后来IO Store的串行占用，Store尚欠自身响应就提前暴露下一Load请求



## 预期依据与根因

- Scala/设计位置：`XiangShan/src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala:291-299；soc-split/rtl/LsqWrapper.sv:1507-1508，load/store等待态均在任意共享resp.valid后归idle，未核对is2lq或原串行owner`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/lsq-expanded-04/：69例59 PASS/10 FAIL，其中本问题4个普通FAIL、NC Store必要条件对照4个全部真实排空`
- `producer-domain-audit-v1.json保存固定开源commit、干净树及5份源码快照；NC entry可推测发行，Uncache e0拒绝只含drain/full/同block冲突，所用三个PA为不同block，未发现nonNC必须等待全部旧NC才可接受的互斥。确切外部SID分配优先级/时延没有作为原生Uncache协同仿真证明。初版审计误把boot空拍也要求outstanding=true，拒绝记录和旧审计器保留，修正仅限定已分配后的事务窗口，不改测试或RTL。`
- [tests/lsq_wrapper/test_bus_ownership.py::test_old_nc_load_response_cannot_unlock_later_serial_store[serial-io-1-0]](../../../tests/lsq_wrapper/test_bus_ownership.py)
- [tests/lsq_wrapper/test_bus_ownership.py::test_old_nc_load_response_cannot_unlock_later_serial_store[serial-io-1-2]](../../../tests/lsq_wrapper/test_bus_ownership.py)
- [tests/lsq_wrapper/test_bus_ownership.py::test_old_nc_load_response_cannot_unlock_later_serial_store[serial-io-4-0]](../../../tests/lsq_wrapper/test_bus_ownership.py)
- [tests/lsq_wrapper/test_bus_ownership.py::test_old_nc_load_response_cannot_unlock_later_serial_store[serial-io-4-2]](../../../tests/lsq_wrapper/test_bus_ownership.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

证实真实Wrapper公开边界提前req.valid，不是第三笔实际req.fire或架构副作用证据；未完成Backend/ISA可达性、Uncache原生联合仿真或重新elaborate。普通LSQ程序序/总线身份域与4个older-load/tie UNIT-INTERFACE用例分开。此表不被测试/参考读取，不修改RTL、不xfail/skip、不将已存在的serial bin成功见证当完整验收。

## 历史证据

- [旧报告](../evidence/bug-reports-20261022/05-LSQ-BUS-OWNERSHIP-001.md)
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
