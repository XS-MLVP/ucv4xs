# FTQ 功能点

功能点按微架构意图描述，而不是按端口或 RTL 赋值枚举。每个点至少有一个可失败的
接口级断言；必要的内部指针只用于区分同一接口状态下的所有权，不作为唯一期望来源。

下表列出代表性用例；完整、逐条的功能点 → 测试 → 本次判定映射由
`tools/traceability.py` 从 `@pytest.mark.feature` 标记生成，见
[功能点追溯](traceability.md)。

## ResolveQueue

| ID | 语义 | 可观察行为 | 用例 |
|---|---|---|---|
| FTQ-RQ-001 | 一个新解析目标只建立一个训练所有权 | 新 `ftqIdx` 写入队首，`startPc`/首分支保持；无消费者时稳定不丢 | `test_resolve_queue.py::test_new_index_creates_one_owned_entry_and_holds_under_backpressure` |
| FTQ-RQ-002 | 同一 `ftqIdx` 的多来源解析合并为一个条目，分支按来源顺序占用最多 8 个槽 | 同一拍 0/1/2/IFU 或多拍到达只增加分支，不重复占队列槽；8 槽内顺序和 payload 保持 | `test_same_index_lanes_merge...`、`test_one_entry_accepts_all_eight_branch_slots...`、`test_every_backend_ifu_lane_validity_combination...`、`test_all_physical_and_branch_slots_survive_streaming_wrap`、`test_random_ownership_sequence...`、`test_backend_lane_and_ifu_same_index_merge_in_one_cycle`、`test_same_cycle_same_index_lanes_merge_in_program_order` |
| FTQ-RQ-003 | 已驻留目标的后续解析附着到原条目 | 队首 `ftqIdx` 和 `startPc` 不变，第二分支追加；条目只出队一次 | `test_later_resolve_updates_existing_index_without_duplicate`、`test_same_index_partial_lane_groups_merge_without_duplicate` |
| FTQ-RQ-004 | IFU 解析是独立且始终接纳的来源 | IFU 直跳/返回不被后端过滤规则吞掉 | `test_ifu_resolve_is_an_independent_always_accepted_source` |
| FTQ-RQ-005 | 后端无需训练的正确直跳/返回不占训练容量 | 正确 direct、return 解析不产生 `bpuTrain.valid`；误预测条件/间接分支产生 | `test_backend_correct_direct_and_return_resolves_do_not_allocate` |
| FTQ-RQ-006 | 出队是单条目、可背压的握手 | `ready=0` 保持队首；`ready=1` 恰好消费一个；空队列不被 `ready` 伪造 | `test_ready_consumes_exactly_one_entry_and_empty_queue_stays_idle`、槽位流式用例 |
| FTQ-RQ-007 | 后端重定向使比新 `ftqIdx` 更年轻的解析失效 | 老队首保留，年轻条目被跳过，不进入训练 | `test_redirect_flushes_younger_entries_and_keeps_older_head` |
| FTQ-RQ-008 | BPU 新入队与已驻留目标冲突时，旧推测被撤销 | 同指针条目变 flush，之后可用新 payload 重建；不同指针不误伤 | `test_bpu_enqueue_at_resident_index_invalidates_stale_speculation` |
| FTQ-RQ-009 | 容量保留区阻止接纳但允许排空 | 16 槽、保留 4 槽时 12 条后可排空，第 13 条被丢弃且不污染已接纳序列 | `test_reserve_guard_stops_admission_but_preserves_drain` |
| FTQ-RQ-010 | 复位丢弃所有未完成解析所有权 | 复位后无训练输出，重新可接纳 | `test_reset_discards_pending_resolution_and_reinitializes` |
| FTQ-RQ-011 | 超过 8 条容量的解析报告必须被丢弃，不能改写已记录分支 | 第 9 条或同拍超量组只填满空槽，已有 8 条保持不变 | `test_resolve_overflow.py::test_ninth_branch_resolve_is_dropped_not_overwritten`、`test_same_cycle_group_overflow_preserves_existing_branch`（当前 **strict XFAIL**，真实 RTL 缺陷，见 [缺陷记录](bugs/resolve-queue-branch-overflow.md)） |

## CommitQueue

| ID | 语义 | 可观察行为 | 用例 |
|---|---|---|---|
| FTQ-CQ-001 | 只有带 RAS 动作的退休指令进入队列 | `rasAction=None` 不占槽；call/return/pop-push 进入 | `test_commit_queue.py::test_only_call_and_return_actions_enter_the_queue` |
| FTQ-CQ-002 | 同拍多 lane 的 call/return 按程序顺序打包，队首按 FIFO 输出 | 多 lane 有效时 payload/顺序保持；同槽不同 lane 优先级覆盖 | `test_lane_packing_preserves_program_order_and_payload`、lane 矩阵、随机混合流、toggle 用例 |
| FTQ-CQ-003 | 入队与出队同拍发生时不旁路、不覆盖 | 新条目排到队尾，队首仍是已知元素 | `test_simultaneous_enqueue_and_dequeue_preserve_fifo_without_bypass` |
| FTQ-CQ-004 | 容量保留区阻止覆盖未消费的 call/return | 达到 `CommitQueueSize-8` 后停止接纳，排空后恢复 | `test_capacity_guard_never_overwrites_queued_call_returns` |
| FTQ-CQ-005 | 复位清空所有排队动作 | 队首/尾部都不可见，复位后可重新入队 | `test_reset_discards_all_pending_actions` |

## Ftq 顶层组合

| ID | 语义 | 可观察行为 | 用例 |
|---|---|---|---|
| FTQ-TOP-001 | 复位后的五个所有权指针和所有出队通道处于空闲 | `bpu/pf/fetch/commit/pnr=0`，无预取/取指/训练/提交/重定向 | `test_reset_initializes_all_queue_owners_and_idles_cleanly` |
| FTQ-TOP-002 | 被接纳的预测占用一个 FTQ entry，并把 startPc 写回后端 PC 存储 | `toBackend.wen` 与索引/PC 同拍有效；entry 写入并可被预取/取指读取 | `test_accepted_prediction_owns_one_entry_and_writes_backend_pc` |
| FTQ-TOP-003 | 预测接纳受 FTQ 满、预取深度和训练背压三个独立条件约束 | 32 深度门限、64 满门限、BpTrainStallLimit=8 分别可关闭 `prediction.ready`，释放后恢复 | `test_prefetch_depth_stalls...`、`test_full_ftq_stall...`、`test_train_backpressure_ages_into_update_bubble` |
| FTQ-TOP-004 | 预取请求描述当前 `pfPtr` 的 entry 并只推进一个所有权 | start/next-line/set/cross-line/ftqIdx 正确；`fire` 后 `pfPtr+1` | `test_prefetch_request_describes_the_owned_entry_and_advances_once` |
| FTQ-TOP-005 | 2-prefetch 只在第二个块已过 PNR、同页且无后端异常标记时成立 | SameLine 时一次推进 2；跨页/未过 PNR 时 Conflict 且只推进 1 | `test_two_prefetch_requires_second_entry_past_pnr_and_same_page`、`test_two_prefetch_rejects_cross_page_pair` |
| FTQ-TOP-006 | 主流水取指请求描述 fetch block；2-fetch 受 PNR、总大小、页和异常标记约束 | `req1.valid` 与 `realTwoFetchValid` 共同决定 `fetchPtr` 推进 1 或 2 | `test_mainpipe_request...`、`test_two_fetch_requires...`、`test_two_fetch_rejects_oversized_pair` |
| FTQ-TOP-007 | s2 override 用最终预测重写 s2 所属 entry，并回卷预取/取指 | s2 flush 有效，entry 被覆盖，`pf/fetch` 回卷到 s2 索引 | `test_s2_override_rewrites_owned_entry_and_rewinds_prefetch_fetch` |
| FTQ-TOP-008 | s3 override 优先于 s2，且 s3 元数据确认推进 PNR | s3 flush 到 ICache/IFU，entry 覆盖，`pnr=s3Ptr+1`；已推进的 pf/fetch 回卷 | `test_s3_override_has_priority_and_meta_advances_pnr`、`test_s3_override_rewinds_already_advanced...` |
| FTQ-TOP-009 | PNR 是“BPU 不能再撤回”的边界，2-prefetch/2-fetch 以它为准 | 第二个块未过 PNR 时绝不合并；已过时可合并，后续对不再自动合并 | 由 TOP-005/006 的 pnr 场景覆盖 |
| FTQ-TOP-010 | 后端重定向优先于 IFU，统一回卷所有所有权并转发重定向元数据 | 指针回到 `newFtqIdx`；redirectFlush、toIfu、toBpu 的 cfiPc/target/attribute/meta 正确；ahead 命中取消延迟 | `test_backend_redirect_rewinds...`、`test_ftq_idx_ahead_*`、`test_backend_redirect_has_priority...` |
| FTQ-TOP-011 | IFU 重定向在下一拍生效；返回目标取重定向元数据的 RAS top | 返回用 `topRetAddr`，非返回用显式 target；`canTrain=0` 不产生训练 | `test_ifu_return_redirect...`、`test_ifu_non_return...` |
| FTQ-TOP-012 | 后端异常/satp 标记绑定到重定向目标，只在窗口内污染预取/取指 | IPF/GPF/AF 映射到请求标记；三个 fetch block 后清除；satp 不伪造异常 | `test_backend_exception_tags...`、`test_satp_flush_tags...`、GPF/AF 用例 |
| FTQ-TOP-013 | 退休指针单调推进，同一退休指针不会重复推进 | 保持同一 commit 只前进一次；下一个指针才继续 | `test_commit_pointer_advances_once_per_retired_entry` |
| FTQ-TOP-014 | 退休 call/return 经 CommitQueue 保序送到 BPU，并取对应 commit meta | `toBpu.commit` 的 rasAction/meta 与入队 payload 一致；容量门限与排空正确 | `test_call_return_commit_uses_stored_commit_meta`、顶层 commit lane sweep、顶层 guard/drain |
| FTQ-TOP-015 | 解析经 ResolveQueue 变成训练事务，首个误预测之后的同 entry 分支被屏蔽 | train 的 startPcVec、分支、meta 正确；首误预测后分支无效；握手后释放 | `test_resolve_becomes_training...`、`test_first_mispredict_mask_covers_every_branch_slot`、`test_top_level_backend_lane_matrix_reaches_training`、`test_top_level_resolve_stream_fills_all_branch_slots`、`test_ifu_resolve_hits_resident_entry_in_every_physical_slot`、`test_top_level_branch_slot_and_source_priority_sweep`、`test_top_level_resolve_guard_limits_admission_and_preserves_order` |
| FTQ-TOP-016 | 训练缓存可保持，并在更老重定向时被冲刷 | train 保持到 ready；老于缓存的 redirect 立即撤销 `train.valid` | `test_train_cache_is_flushed...` |
| FTQ-TOP-017 | entry/meta 队列按物理索引保存重定向、解析、提交元数据 | 高索引和全 64 索引可读回；重定向/训练/提交各自读取正确索引 | `test_high_index_meta...`、`test_metadata_queues_accept_every_physical_index`、`test_every_metadata_bit_accepts_all_ones_and_all_zeros` |
| FTQ-TOP-018 | 满/更新气泡通过 topdown 原因暴露给 IFU | FTQ 满时 `reasons_9`；训练/深度气泡时 `reasons_2` | 由 TOP-003 用例覆盖 |
