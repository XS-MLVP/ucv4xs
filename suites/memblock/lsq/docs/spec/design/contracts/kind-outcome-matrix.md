# LSQ 事务类型 × 响应结果矩阵（功能点账本）

本合同把 [instruction-source-mapping](instruction-source-mapping.md) 的 8 个事务类型与 6 个
响应结果域交叉，逐格给出判定与证据位置。它是 [behavior-equivalence 方法](../../../../../../../skills/design/behavior-equivalence.md)
第 2–4 步"按模块找维度 / 构造区分性样本 / 分层组合"的 LSQ 实例。

**存在的理由**：2026-11-03 的 MMIO Store 漏检证明，"8 类型 × 100 步随机"能覆盖 clean 完成，
但从不提问"响应带错误时怎么办"。补上结果域这一轴后，同一套激励就能把漏检变成可判定。

## 1. 图例

| 标记 | 含义 |
|---|---|
| `P` | 已覆盖且通过；括号内为权威运行中的 nodeid 数（`/tmp/opencode/lsq-runs/full-a0c2a26cb-v3`） |
| `F` | 已覆盖且真实 FAIL（RTL 缺陷或模型残余），括号内为 nodeid 数 |
| `GAP` | 机制存在、激励或观测缺失；必须写明缺什么、怎么补 |
| `N/A` | DUT 接口上不存在该机制，给出结构依据 |
| `出域` | 机制在上层/其它模块，给出承接模块 |

三个结果域在本工程的观测点：

| 结果域 | 观测点 |
|---|---|
| clean | 原 owner 完成、指针前进、无异常位 |
| fault | Load：`io_ldExceptionInfo_*`/`bypass_s2Resp_*`；Store：`io_mmioStout_bits_exceptionVec_7/19`；CBO：同 Store |
| replay | `io_replay_{bank}_valid` + replay 反馈；仅 Load |
| tag_error | dcache 响应 `tag_error`/`tl_d_corrupt`；仅 cached Load 与 CBO 通道 |
| refill | `refill`/`l2_hints` 输入与 MSHR miss；仅 Load |
| tlb_miss | Load：`slow_tlb`/`fast_tlb` hint；Store：`storeAddrIn.tlbMiss` |

## 2. 矩阵

| kind | clean | fault | replay | tag_error | refill | tlb_miss |
|---|---|---|---|---|---|---|
| `cached`（Load） | `P` 17<br>`testbenches/load_queue/tests/test_initial.py` | `P` 78<br>`test_ldu_s4_errors.py`（tag_error/tl_d_corrupt） | `P` 67+84<br>`testbenches/replay/tests/test_timing.py`、`test_ldu_s4_precise.py` | `P` 78<br>同上 AF 模式 | `P` 20<br>`test_replay_population.py` | `P` 78<br>`test_ldu_s4_plain.py`（PF）+ TlbHint |
| `nc_load` | `P` 4<br>`test_bus.py`（nc/fault=False） | `P` 4<br>`test_bus.py`（fault=True）+ `bus_owners.py` | `P`<br>`test_bus.py` 断言 `replay_0_valid` | `N/A`<br>Uncache 响应无 tag_error | `N/A`<br>不经过 MSHR | `GAP`<br>共用 LQ hint 通道有覆盖，NC 专属组合未单列 |
| `mmio_load` | `P` 4+9<br>`test_bus.py`、`testbenches/deq/tests/test_uncache_and_queue.py` | `P` 4<br>`test_bus.py`（fault=True） | `P`<br>同上 | `N/A` | `N/A` | `GAP`<br>同上 |
| `io_load` | `P` 15+7<br>`testbenches/load_queue/tests/test_uncache.py`、`test_uncache_pressure.py` | `P` 23<br>`test_uncache_recovery.py`（`uncache_owners.transfer(error/nderr)`） | `P` 23<br>同上 | `N/A` | `N/A` | `GAP`<br>同上 |
| `store`（cached） | `P` 大量<br>`testbenches/store_queue/*`、`testbenches/psq/*` | `P` 2<br>`testbenches/store_queue/tests/test_recovery.py::test_exception_and_optional_uq_cancel_*`（**预先 `hasException`，不是响应故障**） | `N/A`<br>Store 无 replay | `N/A`<br>普通 Store 无 dcache 响应 | `N/A` | `P` 1<br>`testbenches/store_queue/tests/test_remaining.py::test_ready_holes_and_tlb_retry_*` |
| `nc_store` | `P` 4<br>`test_bus.py`（nc） | **结构不可上报**<br>FSM `waitReqAck → idle`（`NewStoreQueue.scala:1044-1049`），`handleFinish` 走 `ncFinish`（`:1706-1707`），**从不进入 writeback**<br>证据：`/tmp/opencode/lsq-audit-20261103e-ncfault`（干净与故障都无 WB） | `N/A` | `N/A` | `N/A` | `P`<br>共用 Store 地址通道 |
| `io_store` | `P` 4<br>`test_bus.py`（io） | **`F` 2**<br>`testbenches/lsq_wrapper/tests/test_uncache_store_fault.py`：`nderr→exceptionVec_7`、`error→exceptionVec_19` 均为 0<br>（本矩阵新增，见 §3） | `N/A` | `N/A` | `N/A` | `P`<br>共用 Store 地址通道 |
| `cbo` | `P` 7+2<br>`test_serialized_cbo.py`、`test_normal_cbo_paths.py` | **`F` 3+5**<br>`testbenches/deq/tests/test_cbo_fault_consumption.py`、`test_serialized_cbo.py`（缓存错误写回丢失/顺序） | `N/A` | `N/A`<br>CBO 响应只有 denied/corrupt | `N/A` | `GAP`<br>CBO 地址翻译 miss 无专门用例 |

## 3. 本矩阵驱动的两个新事实

### 3.1 `io_store × fault`：观测点缺失（本次新增红）

同一份 `UncacheWordResp` 被 Load 和 Store 共用，但：

- 生产者 `Uncache.toUncacheWordResp` 只驱动 `nderr`/`error`，`denied`/`corrupt` 保持 `DontCare`（`Uncache.scala:112-129`）；
- Load 侧读 `nderr`/`error`（`LoadQueueUncache.scala:195-196、211-221`）→ 可上报；
- Store 侧读 `denied`/`corrupt`（`NewStoreQueue.scala:1087/1095`）→ 恒 0。

生成的 `PhysicalStoreQueue` 端口里 `io_toUncacheBuffer_resp` **只有 `valid`，没有 `bits`**，
`DeqModule.sv` 的 `hasAccessFault`/`hasHardwareError` 只剩 DCache(CBO) 一路。所以这是
"结构上不可能满足的断言"，不是随机没命中。

### 3.2 `nc_store × fault`：FSM 结构决定不可上报

NC Store 在 `waitReqAck` 收到 `idResp` 就直接回 `idle`，完成标志由 `ncFinish` 单独置位，
**没有 writeback 阶段**。因此"NC Store 总线错误"在本层无法表达；若要支持，改的是
`NewStoreQueue` 的 FSM 与响应字段，属 RTL 设计变更，不是测试补充。

## 4. 显式缺口条目（与矩阵同格式）

| ID | 位置 | 缺口 | 影响 | 补法 |
|---|---|---|---|---|
| `GAP-6704` | `store × cross16B × 首/尾窗口` | 现有 `memory_owners.write()` 在同一函数内连发首、尾包；无"首包已接受、尾包未到"窗口 | 该窗口内年轻 Load 读到旧值（上游 #6704）在本层不可达 | 拆 `write_head_only()` → 插入只读低半区 Load → 断言"被前递或被阻塞" → 再发尾包与对照 |
| `GAP-6688` | `cbo/replay × 配置域` | DUT 固定 `ColdDownThreshold=12`，未生成 0 配置 | 阈值 0 时 replay 被禁用（上游 #6688） | 单独构建 0 配置 DUT；0 应被断言拒绝，1/12/15 合法边界可通过 |
| `GAP-PSQ-CREDIT` | `cbo/store × deq credit` | `testbenches/deq/model.py` 不消费 `DeqControl.memory_type`，可缓存条目需要 Sbuffer credit 的规则未建模 | 3 条 post-edge 残余；NC/IO 条目在 deq 窗口的类型与 credit 关系未验证 | 把 credit 需求写进模型（按 `isCacheable && !isCbo && !vecInactive`），单独一轮复验 |
| `GAP-AMO-OBLIGATION` | `AMO × sbuffer 排空` | AMO 不进 LSQ，但要求 `stIsEmpty`（`MemBlock.scala:1181-1182、1225`） | 上游 #6597 的整核交互在本层不可见 | 归 `MemBlock` 组合域；若要做，需 Sbuffer+AtomicsUnit 联合 DUT |
| `GAP-SEG-VSTORE` | `向量 store × AMO` | 现有 VSQ 激励只给 `flows` 计数，无多寄存器 segmented store + AMO 序列 | 上游 #6597 的 `retirePtr` 断言不可复现 | 需要真实 segmented store 的 flow 拆分与后续 AMO 授权序列 |

## 4.5 跨模块交互窗口（不属于单个 kind × outcome 格）

单 kind × 单结果域表达不了"两个模块的条件交错出窗口"。这些用独立账本
`function_points.INTERACTION_WINDOWS` 记录，语义见
[interaction-semantics.md](interaction-semantics.md)。

| ID | 边界 | 窗口 | 状态 | 证据 |
|---|---|---|---|---|
| `IWL-VSQ-RETIRE` | VSQ→PSQ | 多 flow 分段 store 退休时 `retirePtr` 的等式 | `gap` | #6597 形态；现有激励只给 flows 计数 |
| `IWL-UQ-SECOND-PAGE` | PSQ→UQ→Forward | 第一页进 Sbuffer、第二页仍在 EnterSbufferQueue | **`fail`** | 探针 3/3 FAIL，对照 3/3 PASS；#6822 同根因 |
| `IWL-NC-CROSS16B` | DeqModule→Uncache | NC store 跨 16B | **`pass`** | 初版探针非法（漏了上游 `am`），撤回；修正后 LSQ 正确拒绝 |
| `IWL-CREDIT-TYPE` | DeqModule→ESB | 可缓存/不可缓存混排的 credit 需求 | `gap` | `testbenches/deq/model.py` 未按类型算 credit |
| `IWL-PRECOMMIT-RETIRE` | VSQ→PSQ | 预提交后、退休前的指针界 | `pass` | `test_remaining.py` 每拍检查 |

## 5. 维护规则

- 新增或修改任一 cell，必须同时更新本表与 [指令映射表](instruction-source-mapping.md)；
  不允许只加测试不加行。
- `P` 必须能追到 nodeid（权威运行或定向运行目录）；`F` 必须能追到失败断言与源码位置。
- `GAP` 必须写"缺什么 + 怎么补"，不接受"暂未覆盖"。
- 每个 `N/A` 必须给接口/结构依据，不能因为"没写测试"就标 `N/A`。
- 结论边界：`public-a0c2a26cb`、DefaultConfig、seed 1；其它基线/配置需重跑后单独标注。
