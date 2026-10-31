# IFU 行为等价类与关键组合

按 [行为等价类方法](../../../../skills/design/behavior-equivalence.md) 记录“为什么这些
样本可以合并、哪些必须拆开”。每行都给出正确/错误结果的区分点与落点，未展开的大空间
单独给出抽样策略和残余，不用“已随机”代替组合覆盖。

## RvcExpander（输入：16 位压缩字 + FS 状态）

| 类 | 合法前提 | 为什么可合并/必须拆开 | 正确 vs 错误结果 | 落点 |
|---|---|---|---|---|
| 32 位透传 | 低两位 = 11 | 与压缩类无共享解码路径，独立类 | 原样返回 vs 任何改写 | `test_full_width_passthrough` |
| 整数算术 C 类 | quadrant 1、funct3 ∈ {0,1,2,4,5,6,7} | 共享“立即数 + rd/rs1 重映射”语义；按 funct3 拆分是因为立即数与操作数选择不同 | 展开为唯一 RVI vs 遗漏 +8 重映射 | `test_integer_forms`、错误算法 `wrong_expand` |
| 整数访存 C 类 | quadrant 0/2 的 load/store | 共享“按宽度缩放偏移 + 基址”语义；必须按 funct3 拆开以区分符号/零扩展与宽度 | 偏移/符号正确 vs 偏移错位 | `test_memory_forms` |
| 控制转移 C 类 | c.j / c.beqz / c.bnez / c.jr / c.jalr | 共享位移符号扩展，但链接寄存器与条件不同，必须拆开 | 目标 PC/链接寄存器正确 vs 位移或 rd 错 | `test_control_forms` |
| 浮点 C 类 | fld/fsd/fldsp/fsdsp | 只在 FS 开启时合法；与整数类必须拆开 | FS 开→展开、FS 关→非法 vs 恒展开 | `test_float_forms_follow_fs_state` |
| Zcb | c.lbu/lh/lhu/sb/sh + 窄扩展 | 复用 quadrant 0/1 的编码空间但语义不同，必须与标准 C 拆开 | 正确宽度/符号 vs 当成标准 C | `test_zcb_forms`、随机 500 字 |
| 保留编码 | 规范 reserved | 与 hint 必须拆开：一个必须非法、一个必须合法 | il=1 vs il=0 | `test_reserved_encodings_are_illegal` |
| hint | 规范 hint | 允许生产者规范化，只比较合法性与是否异常 | 不异常 vs 误报非法 | `test_hint_encodings_remain_legal` |

抽样策略：定向表覆盖每个 funct3/funct2 至少一次，再对 16 位全空间随机 12000 字 ×
FS 两态与模型比对；未展开的部分是对“模型与 RTL 同时错”的残余（无独立第三描述）。

## InstrBoundary（输入：32 槽窗口 + 压缩图 + carry + 块边界）

| 类 | 合法前提 | 合并/拆分理由 | 正确 vs 错误 | 落点 |
|---|---|---|---|---|
| 全 RVI 窗口 | 压缩图 = 0 | 格点退化为隔槽起始 | 隔槽起始 vs 每槽起始 | `test_full_width_window_starts_every_other_slot`、错误算法 `one_instr_per_slot` |
| 全压缩窗口 | 压缩图全 1 | 每槽起始 | 每槽有效 vs 漏起始 | `test_compressed_window_starts_every_slot` |
| 混合格点 | 任意合法压缩图 | 必须覆盖压缩/非压缩交替后的起点累积 | 起点正确 vs 偏一 | `test_end_mask_counts_instruction_ends_in_a_prefix`、随机窗口 |
| carry-in | 槽 0 是上窗口后半 | 与普通窗口必须拆开：槽 0 有效但非起始 | 槽 0 有效、槽 1 起新指令 vs 槽 0 被当起始 | `test_carry_in_continues_a_full_width_instruction` |
| 块内偏移 | 5 位字段 | 低 lane 高位恒 0（宽度截断），高 lane 才可非零 | 偏移=槽-基址 vs 未减基址 | `test_offset_coordinate_sweep` |
| 块 1 归属 | blockSel | 与块 0 必须拆开（坐标原点不同） | 块 1 自 0 起算 vs 延续块 0 | `test_second_block_owns_slots_from_its_own_start` |
| 跨块 RVI | 块 0 末槽起始且未 taken | 与“taken/压缩结束”必须拆开 | 标记 cross vs 拆两条或漏标记 | `test_cross_block_full_width_continuation` |
| 窗口末尾半指令 | 结束位在 RVI 前半 | 与块内结束区分：分别报告 first/total | 报告半指令 vs 不报告 | `test_window_end_reports_a_half_full_width_instruction` |

未展开空间：压缩图与 split 的全组合（2^32 × 32）不可穷举；改为“合法格点 + 随机
split/taken/块归属”600 例，加 split 1..30 全扫。残余：极端压缩图与异常元数据组合
（异常在顶层覆盖）。

## PredChecker（输入：35 lane 请求）

| 类 | 合法前提 | 合并/拆分理由 | 正确 vs 错误 | 落点 |
|---|---|---|---|---|
| 无违规 | 每 lane 类别与 taken 一致 | 所有合法组合可合并（结论都是“全部入队、不重定向”） | 全部入队 vs 误截断 | `test_legal_predictions_enqueue_everything` |
| 未预测直接跳 | direct + taken=0 | 与间接/返回必须拆开：目标可算 | 目标=PC+位移、taken=1 vs 顺序 PC | `test_unpredicted_direct_jump_redirects_to_its_target` |
| 未预测间接/返回 | indirect，含/不含 pop | 本阶段都不可知目标，可合并为“顺序 PC”，但 rasAction 必须保留 | 顺序 PC + rasAction vs 编造目标 | `test_indirect_and_return_faults_redirect_sequentially` |
| 非 CFI taken | 类别 none + taken=1 | 与 invalid-taken 必须拆开（后者无属性） | 顺序 PC、notCfiTaken=1 vs 当成 CFI | `test_non_cfi_taken_redirects_to_the_fall_through` |
| invalid-taken | 预测指向非法/中段 lane | 必须单独：属性无效、步长取压缩位 | invalidTaken=1、branchType=None vs 带属性 | `test_invalid_taken_is_a_fault_without_an_instruction_class`、顶层中段用例 |
| 多故障 | 两个以上违规 | 取最早者；与单故障拆开 | 最早 lane 的目标 vs 后续更显眼者 | `test_earliest_fault_wins_and_truncates_later_lanes`、逐 lane 扫描 |
| 请求撤销 | valid=0 | 必须拆开：重定向是响应而非状态 | 撤销后 valid=0 vs 残留 | `test_redirect_follows_requests_and_never_persists` |

抽样策略：故障位置 0..34 全扫（每个位置一次），故障类 5 类 × 尾部 lane {27,31,33,34}，
再 400 例随机请求。残余：lane35 无指令端口，不可构造指令类故障。

## IfuUncacheUnit（输入：请求 + 总线事件）

| 类 | 合法前提 | 合并/拆分理由 | 正确 vs 错误 | 落点 |
|---|---|---|---|---|
| 幂等非缓存 | PBMT=NC 或 PMA 且非 MMIO | 可合并：都无需等待 | 立即 SEND vs 等待 | `test_ordinary_non_cacheable_pages_do_not_wait`、错误算法 `wait_for_all` |
| 非幂等 | isMmio 或 PBMT=IO | 必须拆开等待条件来源，但等待语义相同 | 等待 commit vs 超车 | `test_non_idempotent_accesses_wait_for_commit` |
| 发射反压 | to_ready=0 或 ifuStall=1 | 可合并：都保持请求 | 地址/类型稳定 vs 漂移或丢弃 | `test_request_is_held_until_the_bus_accepts` |
| 响应映射 | corrupt/denied 四种 | 必须按状态拆开 | HWE/AF/无异常 vs 混用 | `test_bus_status_becomes_instruction_exception_and_one_pulse` |
| 完成脉冲 | 响应后一拍 | 必须拆开：脉冲宽度=1 | 单拍 vs 多拍/漏脉冲 | 同上 + `test_completion_is_back_to_back_usable` |
| flush 四阶段 | Idle/Wait/Send/WaitResp | 必须逐阶段（副作用不同） | 回 Idle 且清脉冲 vs 残留 | `test_flush_aborts_every_phase_and_discards_late_response` |
| 迟到响应 | flush 后 from_valid | 必须拆开：丢弃 | 无响应 vs 产生指令 | 同上、`test_response_in_idle_is_ignored` |

抽样策略：定向覆盖所有状态迁移边，再 700 拍随机（含 flush 3%、反压、错误响应）。
残余：请求只验证“不丢失”，不验证最大完成延迟（合同无此保证）。

## FrontendTrigger（输入：4 trigger 配置 + 36 lane PC）

| 类 | 合法前提 | 合并/拆分理由 | 正确 vs 错误 | 落点 |
|---|---|---|---|---|
| EQ/GE/LT | 支持的 match 类型 | 必须按关系拆开（边界行为不同） | 关系正确 vs 只用 EQ | `test_equal_match_raises_configured_action`、`test_greater_equal_and_less_than_compare_the_whole_address` |
| 不支持 match | 1/4/5… | 必须与支持类拆开：不得命中 | 不命中 vs 误命中 | 随机配置（`match_type=1`） |
| 门控 | enable/select/debug | 三个门控必须分别拆开（清/恢复时机不同） | 不命中 vs 泄漏命中 | `test_enable_select_and_debug_mode_gate_matching` |
| 配置更新 | tUpdate 指定索引 | 必须逐索引：副本独立 | 只改目标 trigger vs 泄漏 | `test_update_targets_only_the_selected_index`、逐副本扫描 |
| 链 | 成对链 | 必须与无链拆开 | 终端动作 vs 链首自己开火 | `test_pairwise_chain_arms_the_next_trigger` |
| 动作优先级 | debug/breakpoint/none | 必须拆开优先级 | debug > bp > none vs 反序 | `test_breakpoint_requires_permission_and_debug_wins` |
| 逐 lane | 单 lane 命中 | 必须逐 lane（物理副本） | 仅目标 lane vs 串扰 | `test_action_resolution_at_every_lane` |
| tdata2 超出实现地址空间 | `tdata2` 是 64 位 CSR 可写值 | 必须与“窗口内地址”拆开：高位是否参与比较决定 EQ/GE/LT 的答案 | 全宽：`2^50+pc` 不命中、`tdata2=2^50` 时 LT 全命中；RTL 截断：前者命中、后者全不命中 | `test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc`、`test_tdata2_above_the_address_space_is_greater_for_less_than`（当前 **FAIL**，R-13） |

抽样策略：每 trigger 副本单独配置一次、动作逐 36 lane 扫描、128 字节边界扫描
（比较器低/高半 carry），再 180 步随机配置/使能/调试态。残余：timing 由 CSR 固定为
before-execution，接口无 timing 端口，链的 timing 相同条件不可独立验证。

## IfuPerfAnalysis（输入：理由快照 + 注释事件）

| 类 | 合法前提 | 合并/拆分理由 | 正确 vs 错误 | 落点 |
|---|---|---|---|---|
| 传播 | 任意理由位 | 三级延迟相同，可合并 | 3 拍后原样 vs 错拍/丢位 | `test_reset_is_quiet_and_reasons_age_out` |
| 注入 | icache/itlb bubble | 注入级相同（stage1），但理由位不同 | 对应位 vs 混用 | `test_icache_and_itlb_miss_bubbles_are_attributed` |
| 回写 BTB | ifuWbRedirect | 全三级标记，与单级注入必须拆开 | 3 拍 BTB vs 1 拍 | `test_writeback_redirect_blames_btb_for_the_whole_window` |
| 后端覆盖 | control-flow / mem-vio / other | 三类必须拆开（理由位不同） | 正确理由 vs 合并 | `test_backend_control_redirect_overrides_predictor_blame`、`test_memory_violation_and_other_redirect_have_distinct_blame` |
| 并发 | 回写 + 后端同拍 | 必须单独：优先级 | 两者共存 vs 覆盖掉一个 | `test_writeback_btb_blame_wins_over_backend_override` |
| 老化 | 事件停止 | 与持续注入拆开 | 3 拍后消失 vs 残留 | 同传播用例 |

抽样策略：每个可达理由位各注入一次，再 600 拍随机。未展开：68 个无端口理由位（见
退出标准 R-07）。

## Ifu（顶层，输入：取指窗口 + 重定向/flush/uncache/trigger）

| 类 | 合法前提 | 合并/拆分理由 | 正确 vs 错误 | 落点 |
|---|---|---|---|---|
| 单块混合指令 | 合法压缩图 | 共享“边界→展开→对齐→入队”路径，可合并为一种指令流类 | 指令字/PC/FTQ/endOffset 正确 vs 错位 | `test_single_block_mixed_instructions` |
| 双块/跨块 RVI | split 落在 RVI 前半 | 必须与单块拆开（half 组装） | 一条跨块指令 vs 两条 | `test_two_blocks_and_cross_block_full_width_instruction`、split 全扫 |
| 写指针对齐 | 前次入队 1..3 条 | 必须按 shift 0..3 拆开 | 移位对齐 vs 丢失/乱序 | `test_second_fetch_is_aligned_to_the_write_bank_pointer`、12 轮回绕 |
| 预测截断 | 各故障类 | 必须按类拆开（目标/属性不同） | 截断+重定向 vs 错误路径入队 | jump lane 扫描、`test_not_cfi_taken_redirects_sequentially` |
| invalid-taken | 预测指向 RVI 前半 | 与普通故障拆开（无属性、步长 2） | 丢弃整个窗口 vs 入队半条 | `test_prediction_into_the_middle_of_an_instruction_is_invalid_taken` |
| 反压 | toIBuffer.ready=0 | 必须单独：稳定性 | 同一拍保持 vs 漂移 | `test_ibuffer_backpressure_holds_the_beat` |
| flush | backend redirect / BPU s3 | 两种来源必须分别拆开（作用阶段不同） | 丢弃在飞 vs 到达 IBuffer | `test_backend_redirect_discards_the_inflight_fetch`、`test_bpu_stage3_flush_drops_the_window` |
| 异常 | PF/GPF/AF/ECC/非法 | 必须按异常类型拆开（是否写 GPA、mask 位置不同） | 正确 lane+类型 vs 挂错 | `test_page_fault_and_gpf_metadata`、`test_icache_ecc_corruption_raises_hardware_error`、`test_illegal_compressed_instruction_is_localized` |
| 半指令续取 | 窗口截断 + carry | 必须与跨块拆开（跨窗口 vs 跨块） | 一条完整指令 vs 两半 | `test_instruction_split_across_two_fetch_windows_is_assembled` |
| uncache | PBMT=NC/IO、MMIO | 必须与缓存路径拆开（单指令 + 顺序重定向） | 一条指令 + PC+2/+4 vs 混入缓存流 | `test_uncache_fetch_issues_request_and_enqueues_one_instruction`、跨页 resend |
| trigger | PC 命中 | 必须单独：动作随指令入队 | 目标 lane vs 串扰 | `test_frontend_trigger_marks_the_matching_instruction` |

抽样策略：32 槽满窗、随机压缩程序 5 轮（地址/数据位覆盖）、split 1..30、指令类别
逐 lane、uncache 各阶段。未展开：窗口 × 压缩图 × 异常 × 对齐的全组合不可穷举；
残余见 `exit-criteria.md` R-06/R-09/R-10。

## 组合之外的说明

- 以上分类是**有界**说明：每行只证明该类样本能区分正确与代表错误，不证明其他类
  不存在。未分类输入按“合法格点生成 + 随机抽样”处理，并登记抽样策略。
- pairwaise/随机不保证三维以上交互（如 split × carry × 异常 × 对齐）；高风险交叉
  用定向用例（split 全扫、carry 续取、异常两类位置）单独覆盖。
- 时序性质（背压保持、脉冲宽度、flush 副作用、请求撤销）均按拍验证，不以静态状态
  代替；每项在功能点表中有“时间关系”描述。
