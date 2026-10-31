# FrontendTrigger 忽略 tdata2 高 14 位（R-13）

## 现象

`tdata2` 由 CSR 以 `Tdata2Bundle.ALL = RW(63,0)` 暴露为 64 位可写字段，但
`FrontendTrigger` 的 PC 比较只使用 `tdata[VAddrBits-1:0]`（50 位）：

- `src/main/scala/xiangshan/frontend/ifu/FrontendTrigger.scala:72` 把
  `tdataVec(j).tdata2` 原样送入比较；
- `src/main/scala/xiangshan/backend/fu/util/Trigger.scala:241-249`
  （`TriggerCmp`）与 `:255` 起（`TriggerCmpConsecutive`）都只取
  `data(VAddrBits-1,0)` / `tdata(VAddrBits-1,0)`。

因此高位被写入、能读回，却不参与匹配。

## 复现（当前 FAIL）

```
tests/frontend_trigger/test_frontend_trigger.py::
  test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc
  test_tdata2_above_the_address_space_is_greater_for_less_than
```

- 取指窗口 `base=0x5000`，`tdata2 = 2^50 + (base+0x14)`，match=EQ：DUT 在 lane 10
  输出 `ACTION_DEBUG`（1）；全宽语义应无任何 lane 命中。
- 取指窗口 `base=0x6000`，`tdata2 = 2^50`，match=LT：DUT 36 个 lane 全部
  `ACTION_NONE`（15）；全宽语义应为 36 个 lane 全部命中。
- 对照：`tdata2` 落在 50 位地址空间内时，同一比较器与模型一致（含 128 字节进位扫描
  与逐 trigger 副本扫描）。

## 依据

- `Tdata2Bundle.ALL = RW(63,0)`（`backend/fu/NewCSR/DebugLevel.scala:301`）没有把高位
  定义为 WARL 只读 0，软件可写入并读回全部 64 位。
- PC 是 50 位地址，比较时应零扩展；`2^50 + pc` 不等于 `pc`，且任何实现 PC 都小于
  `2^50`。
- 参考模型原先把 `tdata2` 也掩码到 50 位，属于照抄 RTL 实现；本轮已改为全 64 位比较，
  并保留 in-range 随机配置作为对照。

## 影响

只影响软件把 `tdata2` 写成 ≥ 2^50 的配置：

- EQ/GE 会在真实 PC 上误命中，产生本不该有的 breakpoint/debug 进入；
- LT 会漏掉本应命中的地址；
- 触发链（chain）会因此把“误命中/漏命中”传播到相邻 trigger。

## 修复方向（二选一，需设计确认）

1. **按 64 位比较**：PC 零扩展到 64 位，`TriggerCmp` / `TriggerCmpConsecutive` 使用
   完整 `tdata2`。改动集中在 `Trigger.scala`，但 `TriggerCmpConsecutive` 的
   “只比较两个可能高位”优化需要重新证明（高位进位不止 1 个候选）。
2. **把 CSR 高位做成 WARL 只读 0**：`Tdata2Bundle` 增加写掩码，`tdata2[63:50]` 读回
   恒 0，并在合同/文档中声明“仅实现低 50 位”。这保留当前比较器，但必须同时保证
   软件写入后读回值也截断，不能只改比较侧。

任一方向修复后，两条 FAIL 必须转 PASS，并且原有 in-range 用例与随机序列保持通过；
若选方向 2，还需新增“写高位后读回为 0”的 CSR 侧用例（不在本 DUT 边界内，交由
CSR/Debug 工程承接）。

## 证据与边界

- 运行：`results/20261029T143647Z-219b7036`（`ifu: FAIL`，143 PASS / 2 FAIL）。
- 功能点：`IFU-TR-002`（硬件 54/55）。
- 该缺陷是**协议/合同不一致**（CSR 暴露宽度 vs 比较宽度），不是“任意输入都能触发的
  算术错误”；只有当软件写入 ≥ 2^50 的值时可见。
