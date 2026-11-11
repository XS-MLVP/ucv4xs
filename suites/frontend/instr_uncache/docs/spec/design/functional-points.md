# 功能点与验证责任

账本共 **17 项**：硬件 13 项（13 PASS），验证环境 4 项（4 PASS）。
每项都有独立 oracle、驱动/采样路径、checker 和用例；随机用例的每个时钟槽都先由
`model/` 计算期望，再由 DUT 双相采样比较，不用 RTL 赋值反推期望。

> 2026-11-08 收口：原硬件点 `INC-FLUSH-012` 的 `UNCERTAIN` 已按结构证据分类改为
> **验证环境分区**的结构检查点（`metadata.domain=environment`、
> `metadata.structure_only=true`）。它验证 DefaultConfig 下 flush 被恒接 0 并裁剪
> 的事实，不验证 flush 行为；不计硬件通过率，也不写成硬件 PASS。对应残余
> `R-FLUSH` 由 blocking/open 改为 out-of-domain / accepted-limited。详见
> [合同 §9](contracts.md)。

驱动/采样是三个 DUT 各自的 agent：`SyncSingleCycleDriver` 单周期槽负责输入，
`SamplingMonitor(DriveStable)`/`SamplingMonitor(RisingEdge)` 负责无漏采样的边沿前后
快照；组合 Arbiter 用 `GetXClock()` 单相采样。checker 分两层：每个槽的完整合同
比较（`check_outputs`）和功能点专属事件断言（`check_acquire`、`check_response`、
`check_wfi` 等）。

| ID | 合同义务 | oracle | driver / monitor | 专属 checker | 主要用例 | 状态 |
|---|---|---|---|---|---|---|
| `INC-ENT-001` | Invalid 才接受 req；未完成期间不接第二笔；完成后可接下一笔 | `EntryModel.tick` 的 `accepted/completed` 与状态 | `EntryAgent.request/cycle`；Entry 双相监控 | `check_request_accepted`、`check_single_outstanding` | `test_request_accept_acquire_stall_and_single_response`、`test_single_outstanding_rejects_second_request_until_completion`、随机 | PASS |
| `INC-ENT-002` | A 地址 8B 对齐；resend 为 +8；NC/MM user 位传播 | `aligned_bus_address`、`EntryModel.outputs` | `request`/`acquire` | `check_acquire`、`check_acquire_stalled` | 对齐参数化 5 例、resend 用例、随机 | PASS |
| `INC-ENT-003` | 按 `addr(2,1)` 从 8B 拍抽取 4B 窗口 | `fetch_window` | `grant` + Entry 双相 | `check_response` | `test_four_byte_window_uses_addr_bits_2_1[0..3]` | PASS |
| `INC-ENT-004` | 干净非 RVC 跨 8B 自动 resend；两拍拼接；只 resend 一次 | `refill_needs_resend`、`EntryModel._refill` | 连续 `acquire`/`grant` | `check_acquire`、`check_response` | 两拍拼接、RVC 不 resend、随机 | PASS |
| `INC-ENT-005` | 跨页且干净非 RVC 才输出 needResend；RVC/corrupt 抑制 | `cross_page_boundary`、模型响应 | `grant` + 响应槽 | `check_response` | 跨页参数化 3 例、随机 | PASS |
| `INC-ENT-006` | corrupt/denied 原样传播；denied 必须 corrupt；异常抑制 resend | 模型异常寄存器与 `Inputs` 合法域 | `grant(corrupt, denied)` | `check_response` | 干净/corrupt/denied 3 例、随机 | PASS |
| `INC-ENT-007` | wfi 期间不发 A；`wfiSafe` 仅在 RefillResp 为 0；撤销后继续 | 模型 `acquire_valid`/`wfi_safe` | `acquire(wfi_req)`、`idle(wfi_req)` | `check_wfi` | `test_wfi_blocks_new_acquire_and_reports_safe_by_state` | PASS |
| `INC-ENT-008` | 缺 D 响应保持；不发假响应；reset 清 outstanding 并回 Invalid | 模型状态与 `aborted` 计数 | `idle` 连续槽、`reset` | `check_response_loss_persists`、`check_no_response` | 响应丢失、reset 取消、idle reset | PASS |
| `INC-ARB-001` | 1:1 逐字段传递；三个错误/重发位独立 | `arbiter_outputs` | `RespArbiterAgent.evaluate` + xclock 单相 | `check_identity`、`check_outputs` | 6 个定向向量、8 组错误组合、400 随机 | PASS |
| `INC-TOP-001` | 顶层请求→A→D→响应的完整服务；单次完成脉冲 | `TopModel` 组合 Entry | `TopAgent.request/acquire/grant/idle` | 顶层 `check_request_accepted`/`check_response` | 请求-停顿-完成、随机 | PASS |
| `INC-TOP-002` | 只有 source=0 的 D 响应可见；source=1 不写响应、不结束请求 | `TopModel.entry_inputs` 的 source 过滤 | `TopAgent.grant(source=...)` | `check_source_filter` | `test_top_filters_nonzero_d_source` | PASS |
| `INC-TOP-003` | 顶层 wfiSafe/单 outstanding/reset/响应丢失与真实 Entry 一致 | `TopModel` | 顶层槽、`reset` | `check_wfi`、`check_single_outstanding`、`check_response_loss_persists` | WFI、单 outstanding、响应丢失、reset、随机 | PASS |
| `INC-TOP-004` | 顶层地址/窗口/resend/跨页/异常与 Entry 合同一致 | `fetch_window`、`refill_needs_resend`、`TopModel` | 顶层 request/acquire/grant | 顶层 `check_acquire`、`check_response` | 4 个窗口、跨 8B、跨页 3 例、异常 3 例、高位 bit42 | PASS |
| `INC-ENV-001` | 三个 DUT 端口宽度/方向/缺失常量逐项绑定 | `ports.py` 的 `INPUTS/OUTPUTS/ABSENT` | 构造期绑定 | 构造期断言 + audit | 3 个绑定用例 | PASS |
| `INC-ENV-002` | checker 对一位错误有区分力 | `Scoreboard` 直接对照 | 无 DUT | 注入错误期望 | 4 个错误对照 | PASS |
| `INC-ENV-003` | denied 无 corrupt、非 2B 对齐必须在进入 DUT 前拒绝 | `Inputs.__post_init__` | 无 DUT | `StimulusError` | 2 个拒绝 + 1 个合法对照 | PASS |
| `INC-FLUSH-012` | DefaultConfig 下 flush 恒 0、`io_flush`/`needFlush` 被裁剪的结构事实 | `docs/spec/verification/evidence/flush-closure.json` + Scala/RTL 哈希 | 绑定审计 + `tools/audit_flush_closure.py` | `check_flush_pruned` + 证据一致性用例 | `test_flush_path_is_structurally_pruned`、`test_flush_closure_recorded_evidence_matches_active_design`、`test_generated_closure_has_no_flush_port_or_register` | PASS（环境结构证据，**非行为验证**） |

## 功能点与随机回归

- Entry 随机：seed 1/2 各 320 拍合法协议序列，覆盖请求、A 反压、D 响应、
  corrupt/denied、WFI、跨页/resend 和偶发 reset；每拍与模型全字段比较。
- 顶层随机：seed 1/2 各 320 拍，D source 以 10% 概率取 1 作为过滤对照，
  其余为 source=0 的合法响应；每拍与组合模型比较，结束时排空到 Invalid。
- Arbiter 随机：seed 1/2 各 400 个向量，valid/data/corrupt/denied/needResend
  全部随机（denied 仅在 corrupt=1 时生成）。

## 状态解释

- `PASS` 只表示该功能点的全部用例通过合同检查，不是 Frontend/芯片验收。
- `INC-FLUSH-012` 是**环境分区**的结构检查点：证据是 `Frontend.scala:266` 的
  `instrUncache.io.flush := false.B`、唯一实例 `Frontend.scala:125`、生成闭包无
  `io_flush`/`needFlush`、`Frontend.sv` 实例无 flush 连接。它不驱动 flush、不验证
  取消行为，不能写成“flush 已验证”或硬件 PASS；若证据文件/哈希变化，用例会失败
  并要求重新分类。
- `INC-ENV-*` 与 `INC-FLUSH-012` 是环境/绑定/检查器自检，报告按 `environment`
  分区，不进入硬件通过率。
