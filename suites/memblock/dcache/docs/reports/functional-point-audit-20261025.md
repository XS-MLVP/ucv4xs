# 前期功能点正确性复核（W1，2026-10-25）

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


## 1. 复核方法与范围

对 12 份 `docs/functional-points-*.md` 逐条对照：
- RTL 生成代码（`rtl/<dut>/*.sv`）与对应的 Chisel 源码；
- 驱动/参考模型（`dcacheverify/<dut>/env.py`、`model.py`）；
- 用例断言是否真的检查功能结果；
- 已归档报告中的结论是否与最新观测一致。

判定标准：
1. 功能点必须是"可观察的微架构行为"，不是信号枚举；
2. 描述不得与 RTL 实际行为相反；
3. 用例必须检查数据/状态/权限/地址等结果，不能只断言 `valid/ready`；
4. 覆盖率归因必须建立在正确的行为假设上。

## 2. 发现并修正的问题（7 项）

| # | 位置 | 问题 | 修正 | 依据 |
|---|---|---|---|---|
| 1 | `functional-points-banked-data-array.md` BDA-FP-001 | 地址函数写成 `bank = addr[10:6]`，与 `model.py` 的 `addr[5:1]` 及报告矛盾（差 1 bit：`DCacheBankOffset=log2Up(2)=1`） | 改为 `bank = addr[5:1]`，并补上 `DCacheBankOffset/DCacheSetOffset` 来源；补充 `bankMask` 按绝对 bank 号索引 | `DCacheWrapper.scala` 的 `addr_to_dcache_bank`；`dcacheverify/banked_data_array/model.py` |
| 2 | 同上 BDA-FP-008 | 声称"写入的数据读回必须 `error_delayed=0`；整线读 `readline_error_delayed=0`"，与实际观测相反，且用例从未断言这一点 | 重写为"数据往返逐位一致 + 伪错误注入按位生效 + 标志在读结束后回 0"，明确 `error_delayed` 对正确数据也置 1 属 known-issue（BDA-ECC-DELAYED-FLAG），不作为通过条件 | `known-issues.json`；新增用例 `test_ecc_error_flag_clears_after_read`、`test_readline_data_and_flag_clear` |
| 3 | `functional-points-main-pipe.md` MP-FP-006 | 声称 AMO miss 时 `atomic_resp.miss=1`。实际：被接收的 miss **不产生响应**；只有反压 replay 路径才产生响应，且 `miss` 与 `replay` 同源 | 改为"miss 当拍无响应；refill 完成后唯一一次响应 `miss=0`；replay 时 `miss=1 && replay=1`" | `MainPipe.sv:7741-7748`（`atomic_resp.valid = replay | s3_valid & ...`，`miss = atomic_replay_resp_valid`）；`test_amo_miss_request_and_replay` 已按此断言 |
| 4 | `functional-points-miss-track.md` MT-FP-007 | 声称事件插入有固定优先级 `install > alloc > training`。实际同 line 才合并；不同 line 走单端口 **RRArbiter**，alloc 可先于 install，未获授权者丢弃 | 区分"同 line 合并优先级"与"不同 line 轮转仲裁"，明确没有固定优先级 | `tests/miss_track/test_miss_track.py::test_event_priority_and_coalescing`（alloc 赢、install 丢失）；报告 §3.2 |
| 5 | `functional-points-writeback-queue.md` WQ-FP-002 | Release 的 opcode 附加了错误的 `param=0` 条件。实际 opcode = `{1'b1, voluntary, hasData}`，`param` 独立透传 | 改为 4 行真值表（7/5/6/4），说明 param 是 shrink/report 权限 | `WritebackEntry.sv:194`；新增用例 `test_release_opcode_is_independent_of_param`（param=0..3 均为 6，ProbeAck 保留 param=2） |
| 6 | `functional-points-dcache.md` DC-FP-003 | "AcquireBlock（opcode 6/7）"含糊：load miss 恒为 6，7 只用于整行 store | 明确 load→AcquireBlock(6, NtoB)，整行 store→AcquirePerm(7, NtoT)，部分 store→AcquireBlock | `MissQueue.sv` `Mux(full_overwrite, acquirePerm, acquireBlock)`；顶层用例观测 |
| 7 | `functional-points-main-pipe.md` MP-FP-002 | "整字（低 8 字节）写时不读行"过窄 | 改为判据 `bank_write & ~bank_full_write`：所有被写 bank 都整 bank 覆盖才不读行（任意对齐 8B 字、整行均成立） | `MainPipe.scala` `store_need_data/banked_store_rmask` |

另：`docs/reports/dcache-top-20261024.md` 中"store miss 走 write-through、行数据来自 store 自身"
的旧结论已标注更正，并在文件头注明该报告已被 `dcache-top-20261025.md` 取代。

## 3. 用例断言质量抽查

对全部 165 个用例做了一次"是否只断言握手"的机械筛查，并对命中项逐一确认：

| 用例 | 结论 |
|---|---|
| `test_random_legal_traffic`（CounterFilter） | `check_queries()` 每个周期把 DUT 的 3 个 query 结果与模型逐项比对，非弱断言 |
| `test_outcome_way_matrix`（LoadPipe） | `transaction()` 内部逐字节比对 128-bit 响应数据与 miss/idx 期望 |
| `test_datapath_bit_sweep`、`test_victim_selection_and_age_saturation`、`test_retained_result_on_bubble`、`test_events_refresh_all_existing_entries`（MissTrack） | `mt.query()` 按 `expected=resident/pending/candidate/suppressed` 分类断言，并检查表模型条目与 age |
| `test_all_sixteen_entries_occupied`（WritebackQueue） | 原仅检查 `req_ready`；已补每个条目的 `address` 与 opcode（偶数 7 / 奇数 6）断言 |

结论：不存在"只跑通握手"的通过用例。

## 4. 修正后的回归

- 直接 pytest 全量：**165 passed / 175.97s**（原 162，新增 3 个用例：
  BDA ECC 标志 2 个 + WBQ param 独立性 1 个；`test_all_sixteen_entries_occupied`
  补强断言）。
- 功能覆盖组仍为 100%：BDA 的 `bda.ecc` 已从"clean/error"改为
  "roundtrip/injected_xor"，避免把 known-issue 的错误标志当成覆盖目标。

## 5. 复核结论

- 12 份功能点文档中，4 份存在实质性错误（BDA、MainPipe、MissTrack、WritebackQueue），
  1 份表述不精确（DCache 顶层 opcode），均已修正并留下依据。
- 错误主要集中在"把旧报告/直觉结论写进功能点"和"把内部信号行为当成外部可观察行为"；
  修正后功能点与 RTL、驱动模型、用例断言三者一致。
- 覆盖率归因未受影响：修正的都是语义描述，唯一受影响的 BDA ECC 覆盖组已同步调整口径。
