# 功能点与验证责任

账本共 **23 项**：硬件 19 项（19 PASS），验证环境 4 项（4 PASS）。每项都有独立
oracle、驱动/采样路径、checker 和用例；随机用例的每个时钟槽都由 `model/` 先算
期望，再由 DUT 双相采样比较。

驱动/采样是每个 DUT 的 agent：`SyncSingleCycleDriver` 槽负责输入，
`SamplingMonitor(DriveStable)`/`SamplingMonitor(RisingEdge)` 负责边沿前后无漏采样
快照；checker 同时比较 before/after 两相。

| ID | 合同义务 | oracle | driver / monitor | 专属 checker | 主要用例 | 状态 |
|---|---|---|---|---|---|---|
| `IBUF-VTG-001` | vsetvli/vsetivli 在所在 lane 生成请求的 vma/vta/vsew/vlmul，后续 lane 继承 | `model.vtype.lane_window` 的 ISA 解码 | `vtype_gen` 单周期槽 + 双相监控 | `check_outputs`（完整 80 输出） | `test_vsetvli_generates_configuration_on_any_lane[0..7]`、`test_vsetivli_generates_configuration`、随机 | PASS |
| `IBUF-VTG-002` | 8 个 decode lane 独立；valid=0 的 lane 不按 vset 解码；非 vset 透传 | `lane_window` 的 per-lane valid 和链 | 同上 | `check_outputs` | `test_invalid_lane_does_not_decode_as_vset`、`test_non_vset_lanes_pass_the_speculated_configuration`、随机 | PASS |
| `IBUF-VTG-003` | e8/e16/e32/e64 × mf8…m8 支持表、保留编码、VLMAX | 独立手写 VLMAX 表 + `decode_vtype` | 同上 | `check_outputs`、`test_vlmax_matches_the_architectural_table` | 64 组合扫描、随机 | PASS |
| `IBUF-VTG-004` | 保留 vtypei 位、保留/超 ELEN 的 SEW/LMUL、`rd=rs1=x0` 的 VLMAX 改变均置 vill | `lane_window` 的 vill 规则 | 同上 | `check_outputs` | `test_reserved_vtypei_bits_set_vill`、`test_reserved_sew_and_lmul_encodings_are_illegal`、keep-vl 两例 | PASS |
| `IBUF-VTG-005` | spec/arch 双状态；commit vsetvl > commit vtype > walkVType > walkToArch > canUpdate | `VTypeGenModel.tick` 的优先级 | 同上 | `check_outputs` | `test_commit_vtype_snapshot_updates_arch_only`、`test_walk_to_arch_uses_the_pre_edge_arch`、`test_walk_vtype_has_priority_over_arch_copy`、`test_commit_vsetvl_updates_both_states_with_priority` | PASS |
| `IBUF-VTG-006` | `canUpdateVType=0` 时 spec 不吸收 window | `VTypeGenModel` | 同上 | `check_outputs` | `test_can_update_vtype_zero_freezes_speculation`、`test_can_update_vtype_advances_speculation` | PASS |
| `IBUF-VTG-007` | 同 window 连续 vset 按 lane 链接；keep-vl 参考最近前驱 lane | `lane_window` 的 cumulative VLMAX | 同上 | `check_outputs` | `test_keep_vl_uses_the_nearest_preceding_lane`、随机 | PASS |
| `IBUF-VTG-008` | 复位返回 `vill=1`/零配置；静默复位周期输出 INIT | `VTypeGenModel.reset_state` | 同上 | `check_outputs` | `test_reset_initializes_vill_and_zero_configuration` | PASS |
| `IBUF-VTG-009` | specvtype 是每条指令前的快照 | `lane_window` 的 snapshots | 同上 | `check_outputs` | `test_specvtype_snapshots_precede_each_lane`、随机 | PASS |
| `IBUF-TOP-001` | 入队/出队保持指令字、RVC、foldpc、predTaken、FTQ、offset、trigger 与顺序 | `IBufferModel` 的队列项 | `ibuffer` 单周期槽 + 双相监控 | `check_outputs`、`check_no_head_bubble` | `test_queued_enqueue_is_dequeued_into_the_window`、`test_full_width_payload_reaches_every_queue_position`、随机 | PASS |
| `IBUF-TOP-002` | 48 槽循环指针、occupancy、empty/full | 模型指针与 occupancy | 同上 | `check_outputs`、`test_fifo_order_survives_pointer_wrap` | FIFO 回绕、全 48 位置 payload、随机 | PASS |
| `IBUF-TOP-003` | `allowEnq` 使用上一周期声明的 `prevInstrCount`；满时 stall 且不破坏队列 | 模型的 `allow_enq_next` | 同上 | `check_enqueue`/`check_not_enqueued` | `test_flow_control_stalls_an_unannounced_fill_and_recovers`、`test_all_four_write_bank_offsets_are_accepted` | PASS |
| `IBUF-TOP-004` | 输出窗口替换/追加、头部连续 | 模型的 `outputEntriesNext` | 同上 | `check_no_head_bubble`、`check_no_bubble_after_edge` | `test_append_mode_keeps_old_entries_and_appends`、随机 | PASS |
| `IBUF-TOP-005` | 队列空+decode+无 vset 时旁路；旁路取 spec；含 vset 禁用旁路；最多 8 条 | 模型的 `useBypass`/`numBypass` | 同上 | `check_bypass` | `test_bypass_forwards_a_beat_and_stages_both_phases`、`test_bypass_caps_at_eight_and_queues_the_remainder`、`test_vset_disables_bypass...` | PASS |
| `IBUF-TOP-006` | 非旁路路径的 window 坐标编号、vtype 链与 specvtype | 模型 + 内嵌 `VTypeGenModel` | 同上 | `check_outputs` | `test_vset_disables_bypass_and_queued_lanes_get_the_new_vtype`、`test_appended_window_restarts_the_vtype_chain` | PASS |
| `IBUF-TOP-007` | flush 清队列/窗口/指针/异常并恢复 ready | 模型的 flush 分支 | 同上 | `check_flush` | `test_flush_discards_queue_window_and_pointers`、`test_flush_while_full_restores_ready`、随机 | PASS |
| `IBUF-TOP-008` | 前端异常只附加到匹配指令；五个 exception bit、crossPage、backendException、satpFlush | 模型的 `firstException`/`deqExceptionOffset` | 同上 | `check_outputs` | 队列首条、追加位置 1..7、出队 offset 1..7、旁路、无异常 satp 对照 | PASS |
| `IBUF-TOP-009` | 组合路径中的 walk/commit 与 `resumingVType` 冻结 | 内嵌 `VTypeGenModel` | 同上 | `check_outputs` | `test_walk_vtype_configures_the_next_dequeued_window`、`test_commit_then_walk_to_arch...`、`test_resuming_vtype_freezes_the_output_window`、随机 | PASS |
| `IBUF-TOP-010` | stall reason 取最高 topdown reason / FetchFrag / 0；redirect override | 模型的 `_stall_reason`/override | 同上 | `check_outputs` | 最高 reason、FetchFrag、全空、control-flow override、随机 | PASS |
| `IBUF-ENV-001` | 两个 DUT 的全部端口宽度/方向绑定；真实 VTypeGen 子模块在闭包内 | `ports.py` 的 INPUTS/OUTPUTS 与构建收据 | 构造期绑定 | 绑定断言 + `test_ibuffer_closure_retains_the_real_vtype_gen` | 3 个绑定/结构用例 | PASS |
| `IBUF-ENV-002` | 一位错误必须被 checker 拒绝，正确值通过 | `Scoreboard` 直接对照 | 无 DUT | 注入错误期望 | 5 个区分力用例 | PASS |
| `IBUF-ENV-003` | 非法 lane/对齐/quiet-beat/异常类型/队列溢出在进入 DUT 前拒绝 | `Inputs.__post_init__`、模型对齐检查、agent 声明检查 | 无 DUT 或 agent 前置检查 | `StimulusError` | 10 个拒绝/合法对照 | PASS |
| `IBUF-ENV-004` | vtype oracle/编码器/队列不变量的独立审计 | 手写 ISA 表与结构不变量 | 无 DUT | 直接断言 | 5 个 oracle 审计用例 | PASS |

## 随机回归

- `VTypeGen`：seed 1/2 各 240 个随机周期，随机 8-lane 指令（含 vsetvli/vsetivli、
  保留位、非法编码）、walk/commit/vsetvl/canUpdate 控制；每周期比较 80 个输出。
- `IBuffer`：seed 1/2 各 300 个随机 beat，随机入队数量（含 0/1/2/…/24）、
  vset/普通指令、旁路/队列/追加、flush、`resumingVType`、walk/commit、异常与
  topdown/redirect；每周期比较完整输出面。
- 两 seed 的完整 collected nodeid 和 collection SHA 相同，所有判定一致。

## 状态解释

- `PASS` 只表示该功能点的全部用例通过合同检查，不是 Frontend 或芯片验收。
- 上述回归没有 `XFAIL/XPASS/SKIP/UNCERTAIN`；未证明范围见
  [退出标准](../verification/exit-criteria.md)，不用豁免替换。
- 环境项在报告中按 `environment` 分区，不进入硬件通过率。
