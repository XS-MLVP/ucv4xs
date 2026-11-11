# VSQ-REDIR-IF-001 — 同拍dispatch与redirect的接口边界中，entry写入被禁止但虚拟tail仍计入新请求，恢复返回被取消的旧end而非幸存end

## 状态与范围

```ucv-bug
{
  "id": "VSQ-REDIR-IF-001",
  "title": "同拍dispatch与redirect的接口边界中，entry写入被禁止但虚拟tail仍计入新请求，恢复返回被取消的旧end而非幸存end",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "docs/spec/verification/evidence/reports/interaction-probes-20261106.md",
        "manifest/known-issues.json"
      ],
      "note": "2026-11-06 完整回归的上一轮 219 个 FAIL 按目录统计含 vsq 2 条，与旧记录的两个接口边界失败节点数量一致，但未逐 nodeid 确认；当前基线按 unverified 记录，不写成已复现。"
    },
    {
      "baseline": "XiangShan 893e1580b705d81f113c30c7a05734e09a08050e",
      "status": "open",
      "evidence": [
        "docs/bugs/evidence/bug-reports-20261022/README.md",
        "manifest/known-issues.json"
      ],
      "note": "旧基线 893e1580 的接口边界普通失败；保留为历史复现，域限制不变。"
    }
  ]
}
```


**当前基线 `public-a0c2a26cb`：unverified（未逐节点复验；旧基线结论不得写成当前已复现）。**

**域限制**：该条只证明接口边界行为，不声称正常架构流量可达；目录状态仍为 open。

## 现象

同拍dispatch与redirect的接口边界中，entry写入被禁止但虚拟tail仍计入新请求，恢复返回被取消的旧end而非幸存end

原有ROB10/11各1flow，物理end1/2；ROB12在redirect(ROB10,flushAfter)同拍的lane0或7到达，公开redirectPtr.valid=1而bits=SQ2，严格接口期望仅幸存ROB10的end即SQ1。

## 预期依据与根因

- Scala/设计位置：`VirtualStoreQueue.scala:151-171,213-234,343-372`。
- 生成 RTL 位置：`见对应旧报告与 manifest/known-issues.json`。
- 期望来自既定事务/接口合同和原始生产者账本，不读取待测 RTL 的内部状态作为 oracle。

## 复现与对照

- `results/vsq-expanded-01/ (原用例名test_inflight_dispatch_on_redirect_does_not_leave_a_ghost_virtual_entry)`
- `仅UNIT-INTERFACE，不声明普通生产者合法/架构缺陷。LSQWrapper.scala:499-502对!redirect门控后寄存dispatch；CtrlBlock.scala:818/830/867及Backend.scala:235/578将相同redirect和enq直通，XSCore.scala:150/210直连MemBlock；MemBlock.scala:494/1055/1058仅给redirect增加一拍。普通LSQ侧redirect与dispatch门控严格对齐而互斥。`
- [tests/vsq/test_extended.py::test_same_cycle_dispatch_redirect_interface_boundary_has_no_ghost[0]](../../../tests/vsq/test_extended.py)
- [tests/vsq/test_extended.py::test_same_cycle_dispatch_redirect_interface_boundary_has_no_ghost[7]](../../../tests/vsq/test_extended.py)

所有失败保留为普通 FAIL，没有 xfail、skip 或 waiver。历史运行目录若未随 Git 保存，只保留 manifest、报告和哈希索引；本次整理不复制运行产物。

## 适用范围与仍未证明

保留边界普通FAIL、不放宽参考或xfail/skip；新增合法dispatch前一拍的lane0/3/7对照。未修改目标RTL，不能以接口压力扩大成已证实架构缺陷，也不能用普通流量通过宣布所有接口边界通过。

## 历史证据

- （该问题在 [manifest/known-issues.json](../../../manifest/known-issues.json) 与后续审计中首次登记，无独立旧报告文件。）
- [已知问题清单](../../../manifest/known-issues.json)
- [旧错误报告入口](../evidence/bug-reports-20261022/README.md)
