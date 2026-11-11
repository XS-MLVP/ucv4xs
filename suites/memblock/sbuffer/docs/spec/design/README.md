# Sbuffer Design spec

状态：**整理入口，设计确认待完成**。本页把现有功能点、接口合同和范围说明收敛到设计
入口；要求主要来自固定基线 RTL、Chisel 源码、RISC-V CMO 规范和已有验证合同，尚未
记录设计 owner 的逐条确认，因此不等同已签核的微架构规格。

适用基线：最近完整证据绑定 `public-893e1580b` / DefaultConfig；当前根默认基线为
`public-a0c2a26cb`，本工程尚未在该基线重新生成 RTL、构建或回归。实际版本以
`ucv info sbuffer` 和根配置为准。

## 1. 范围与层次

本工程验证 MemBlock 中位于 StoreQueue 与 DCache 之间的 16 行写合并缓冲，按
`SbufferData → Sbuffer` 自下而上组织：

| DUT 键 | 顶层 | 职责 | 设计要求入口 |
|---|---|---|---|
| `sbuffer_data` | SbufferData | 16 行 × 4 lane × 16B 数据/掩码阵列，按字节 merge、按行清 mask | [SBD 功能点](functional-points-sbuffer-data.md) |
| `sbuffer` | Sbuffer | 入队/merge/insert、写出与 replay、排空、load 转发、行替换 | [SBT 功能点](functional-points-sbuffer.md) |

顶层 `Sbuffer` 内部保留真实 `SbufferData`；独立 `SbufferData` DUT 用于字节级存储语义。
顶层导出参数和 DUT 映射见 [ucv.json](../../../ucv.json)；RTL 哈希、工具链和 DUT 清单
见 `manifest/`。

## 2. 接口、配置与合法输入

- Sbuffer 只保存已提交（committed/retired）的 store；不负责发射、地址翻译或写回 ROB。
- 每行 `state_valid` 表示槽内有尚未写出的字节，`state_inflight` 表示该行正在写往 DCache。
- 入队为 s0/s1/s2 三级流水；两路 store 可同拍入队，同一新行的后端口覆盖重叠字节；
  父块 `in.req(1).ready` 依赖 `in.req(0).ready`。
- 写出请求携带行内完整 512-bit data/mask、物理/虚拟行地址；`addr` 只保留行基址，
  `vaddr` 保留虚标签。
- `wline` 的父块合法域只有 `cbo.zero` 的零 payload；`SbufferData` 模块允许非零整行
  广播，但不作为父块可达行为证据。稳定 ID 和原依据见
  [验证约束](../verification/constraints.md#wline-zero-payload-only)。
- 本工程不启用 VPI 和 internal signal config；运行期不调用 `SetWaveform`，不保存
  逐周期信号/事务 dump。

## 3. 行为要求与关键合同

逐 DUT 的稳定功能点 ID、情形和观察点见：

- [SBT-ENQ-01..04、SBT-WRITE-01/02、SBT-FLUSH-01、SBT-FWD-01/02、SBT-RESET-01](functional-points-sbuffer.md)
- [SBD-WRITE-01..08、SBD-FLUSH-01..04、SBD-RESET-01、SBD-STABLE-01](functional-points-sbuffer-data.md)

两项跨模块合同需要单独保留：

- **两级空语义**：`sbempty` 包含 Sbuffer 行、在途输入和 MSHR store miss，不含 SQ；
  CMO 完成条件消费 `sbempty`，因为 CMO 自身 SQ 条目在 writeback 前不释放，要求
  `sqempty` 会死锁。`flush.empty = sbempty && sqempty`，供 fence/atomics 使用。
  该结论依据 RISC-V CMO 规范、XiangShan PR #6183 和
  [flush/empty 合同复核](../verification/evidence/flush-contract-review-20261024.md)，
  已关闭为“非缺陷”（`FLUSH-EMPTY-TWO-LEVELS-REVIEWED`）。
- **写回阻塞与 replay**：DCache 未接受写回时，Sbuffer 行保持有效并置 `w_timeout`，
  超时后重发同一行；DCache 命中响应释放行。该行为与 DCache 的 WritebackQueue 阻塞
  契约共同工作，不能只看 Sbuffer 单侧。

## 4. 依据与待确认问题

- 功能点依据来自 `Sbuffer.scala`、`SbufferData`、`NewStoreQueue.scala`、`Fence.scala`、
  `AtomicsUnit.scala`、`MemBlock.scala` 和生成 RTL；文档中的旧源码路径只用于定位当时基线。
- `SbufferData` 的 `initial` 块只在仿真时间 0 执行，`if(reset)` 的另一分支不可由运行期
  激励到达；该工具边界见 `SBD-TIME0-INIT`。
- 待确认：设计 owner 对功能点和两级空语义的逐条确认、同块高槽与 lane 半区情形的
  完成条件，以及 `wline` 未来是否扩展到非零 payload。
- 设计要求变更使用 Git review；新增要求分配稳定 ID，并在验证规格中登记场景与证据。
