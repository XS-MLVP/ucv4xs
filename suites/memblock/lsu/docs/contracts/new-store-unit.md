# `NewStoreUnit`：集成 store 地址单元

## 1. 职责

集成 S0–S4，对外提供：S0 的 TLB 请求与 `stin_ready`、S1 的 SQ 地址写 / STA nuke
查询 / 非对齐队列请求 / RS 反馈（父层再打一拍）、S2 的存储类型侧带、S3 的 ROB 写回
与异常信息。

## 2. 关键时序（实测，不是推断）

| 事件 | 相对 `stin` 的周期 |
|---|---|
| `tlb_req`、`toSqAddr`、`staNukeQueryReq`、`updateLFST` | 同拍（S0 寄存器 → S1 组合） |
| `feedBackSlow` | +1（父层 `RegNext`/`RegEnable`） |
| `toSqAddrRe` | +1（S1 寄存器 → S2 组合） |
| `stout` / `exceptionInfo` | +3（S1/S2 寄存器 + S3 延迟管） |

`feedBackSlow.bits.hit` 在 `valid=0` 时保持旧值（`RegEnable`），因此只在 valid 时比较。

## 3. 关键结构语义

- **head/tail 环回**：S1 在 head 拍组合产生 `unalignTail`，直接进入 S0 的仲裁器。
  因为尾段优先级最高，它**在同一拍就抢走仲裁**：`stin_ready` 当拍变 0，且
  `tlb_req` 发出的是尾段地址（下一个 16B 字）。这是实测行为（见
  `test_tail_wins_the_arbiter_in_the_head_cycle`），也是 S0/S1 各自 UT 无法覆盖的
  跨级效应。
- **固定延迟、无背压**：S0 输出、S1/S2 流水都没有 ready；每拍最多一个 beat。
- **kill 的三处来源**：S0（redirect，带 arb.valid 门控）、S1（redirect 无门控 +
  illegalIssue + youngCrossHead）、S2/S3（redirect 无门控）。
- **跨页 head 需要地址就绪**：`cross4KPage && !isAddrReadyHead` 的年轻 head 会被
  S1 杀掉并强制重放，所以跨页用例必须让 `sqAddrReadyPtr` 指向该 store 的 SQ 槽。
- **CBO**：S1/S2 会把 vaddr/paddr 对齐到 16B、size 置 4、`wlineflag=1`；CBO 访问
  uncache 空间报 access fault；正常完成的 CBO 不写 ROB。

## 4. 输入合法域与外部代理

- `stin`：IQ 发射的标量 store。parent 边界上 `instrType` 恒为 scalar（S0 合成），
  因此**向量与预取路径在本配置不可达**；相关分支记为结构性不可达。
- `tlb_resp`：每次访问一份响应；`miss=1` 表示 miss。
- `pmp`：ld/st/mmio 三路响应。
- `csrTrigger`：4 路 trigger 配置。
- `sqDeqPtr`/`sqAddrReadyPtr`：SQ 指针。
- 外部 LSQ/DCache/ROB 全部由测试侧驱动，不是它们已验证的证据。

## 5. 覆盖与缺口

剩余 toggle 全部是结构常量：`io_prefetchTrain_bits_*`（父层把该输出恒接 0，本配置
无预取训练器）、非对齐尾段掩码的高位、尾段地址低 4 位、以及只能由向量/预取
`instrType` 驱动的位。剩余分支是 5 个 `initial` 块里的 `if (reset)`（工具边界）和
3 个 `MemTrigger_3` 向量 unit-stride 分支（本配置无向量生产者）。

## 6. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala:860-945`（S0–S4 连接、反馈寄存、延迟管）
- `soc-split/rtl/NewStoreUnit.sv`（本 DUT）
