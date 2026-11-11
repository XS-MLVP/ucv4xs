# LSQ 上游漏洞核查与参考模型/用例 appropriateness 审核（2026-11-03）

## 1. 范围、基线与来源

| 项 | 值 |
|---|---|
| 本地基线 | `public-a0c2a26cb` / `a0c2a26cbe3c862175174bad03a1a23c406315ed`（DefaultConfig） |
| 上游仓库 | `https://github.com/OpenXiangShan/XiangShan.git`，分支 `kunminghu-v3` |
| 上游快照 | `2145ba1c95fe2d7862416dfd2766da3fef207a8b`（2026-11-03 拉取） |
| 基线之后提交数 | 10 |
| 触及 `mem/lsqueue` 的提交 | 3（均已合并，2026-11-03） |
| 本地权威完整结果 | `/tmp/opencode/lsq-runs/full-a0c2a26cb-v3`：2356 PASS / 219 FAIL，2575 nodeid，seed 1，32 workers |
| 本轮新增运行 | `/tmp/opencode/lsq-audit-20261103a…h`（详见 §6） |

方法：`git fetch origin kunminghu-v3` 后按 `mem/lsqueue` 路径过滤；用 GitHub API 读取全部相关
Issue/PR 的当前状态与正文，再与本地 Scala pre-image、DUT、参考模型和实际 FAIL nodeid 逐条对齐。
上游结论只覆盖上述快照，不是对 `kunminghu-v3` 未来状态的承诺。

## 2. 基线之后的上游提交：逐条判定

| 提交 | 标题 | 触及 LSQ | 处理 |
|---|---|---|---|
| `2145ba1c9` | fix(decode): select CBO opcode for inval-to-flush conversion (#6754) | 否 | 解码层，出域 |
| `effee80b5` | feat(crob): former/latter remaining writeback counts (#6749) | 否 | ROB 调试域 |
| `dc7eb7338` | fix(StoreQueue): wait for CBO zero enqueue before flushing (#6762) | **是** | 本地缺陷仍在，见 §3.3 |
| `43fe084b3` | fix(StoreQueue): fix cross16B unalign forward mask (#6718) | **是** | 本地缺陷仍在，见 §3.1 |
| `d3472986b` | fix(StoreQueue): fix judgement of `MdpHit` when `waitSqidx` is retired (#6714) | **是** | 本地缺陷仍在，见 §3.2 |
| `a026b34f5` | fix(LoadUnit): fix rollback info under same RobIdx (#6678) | 否 | LDU，不在 LSQ DUT 闭包 |
| `429980ea2` | fix(decode): out-of-order CSRR execution (#6779) | 否 | 解码层 |
| `ecc3c3c7f` | feat(Tage): bankIdx use history bits (#6771) | 否 | BPU |
| `13e6ea2d1` | timing(Bpu): s2/s3 override (#6753) | 否 | BPU |
| `95a5e89ff` | bump(XSCache)（#6803） | 否 | 缓存子模块 |

`MemBlock.scala` 另有 `selectOldestRedirect` 重构（随 `a026b34f5` 一带），改变
`rollback/nack/nuke` 重定向仲裁；`LsqWrapper` 端口不变，因此不进入本工程 DUT 闭包，但
"同槽 flushItself 优先"的父级行为不在模块 UT 域内，见 §4 的出域项。

## 3. 已合并修复与本地失败的逐条映射

三者都是**我们已经在保留的 FAIL**，不是新增发现；本节的增量是"上游在其后一天合入的补丁
恰好覆盖了这些失败"，从而给本地反例提供了独立的第三方确认。

### 3.1 `#6718` cross-16B 前递 mask 边界（`43fe084b3`）

本地 pre-image（`NewStoreQueue.scala:639`）：

```scala
val s2OutMask = ParallelLookUp(s2ByteSelectOffset, s2SelectMask) & s2LoadMaskEnd
```

`rotateByteRight` 是环形旋转，Store 在 16B 字尾部时会把对侧字节卷进来。上游补丁增加
`s2ForwardMaskBoundary`，按载入/存储起点相对位置只保留低段或高段。本地对应
`FWD-RANGE-001`（旧基线 28 节点），本轮权威结果中 mask 折回类失败：

| 用例族 | FAIL 节点 |
|---|---:|
| `test_cross_word_store_mask_cannot_wrap_bytes_into_unwritten_addresses` | 6 |
| `test_cross_word_forward_never_invents_unwritten_physical_bytes` | 6 |
| `test_real_parent_cross_word_mask_cannot_name_unwritten_pa_bytes` | 6 |
| `test_cross_word_store_cannot_supply_unwritten_pa_bytes` | 6 |
| 同族 seeded 字节查询（`test_seeded_*cross_word*`、`test_seeded_in_window_nonalias*`） | 4 |

定向复跑 `tests/forward/test_semantics.py::test_cross_word_store_mask_cannot_wrap_bytes_into_unwritten_addresses`
仍为 6/6 FAIL（`/tmp/opencode/lsq-audit-20261103a`），与权威结果逐 nodeid 一致。

### 3.2 `#6714` 已退休 MDP 目标被误判越域（`d3472986b`）

本地 pre-image（`NewStoreQueue.scala:584`）没有 `!s2MdpTargetRetired`：

```scala
val s2MdpHitOutOfRange = s2LoadWaitBit && s2WaitSqIdx.isNotBefore(s2PhysicalQueueUpper)
```

本轮 4 个 FAIL 直接对应：`tests/forward/test_github_gap_relationship.py::test_retired_wait_target_across_flag_wrap_must_not_wait[0/1/2]`
与独立性质用例 `tests/fail_review/test_independent_forward_property.py::test_retired_wait_target_is_not_an_address_stall`。
该组用例只读公开 `addrInvalid_valid`，不依赖引脚预测器。

### 3.3 `#6762` CBO.zero 必须在自身入队后才推进（`dc7eb7338`）

本地 pre-image（`NewStoreQueue.scala:980`）仍在 FIFO **出口**握手时离开 `writeZero`：

```scala
is(CboState.writeZero) { when(io.writeToSbuffer.req.head.fire) { cboStateNext := CboState.flushSb } }
```

上游改为 `dataQueue.io.fromDeqModule.head.fire`。本地对应 `DEQ-ZERO-001`，本轮 2 个 FAIL：

- `tests/lsq_wrapper/test_serialized_cbo.py::test_serialized_zero_retired_old_sbuffer_still_requires_own_zero16_strict[True]`
- `tests/lsq_wrapper/test_serialized_cbo.py::test_serialized_zero_retired_old_sbuffer_actual_WB_and_release_protocol_only[True]`

同族控制 `[False]` 在定向运行中 PASS，说明反例的区分度来自"旧 Store 堵在 FIFO"这一前置，
而不是断言本身。

### 3.4 历史根因与上游状态（只列有明确上游条目者）

| 本地根因 | 本轮 FAIL | 上游条目 | 状态 |
|---|---:|---|---|
| `DEQ-WB-001` 写回丢错误 | 50 | #6833 第 1 项（读未驱动字段） | open PR；写回状态清标志本身未见对应 PR |
| `LQU-SID-001` SID 复用覆盖 | 29 | #6773（保留 uncache 响应） | open PR |
| `FWD-RANGE-001` mask 折回 | 28 | #6718 / `43fe084b3` | 基线后已合并 |
| `RAR-REL-001` release 错拍 | 19 | #6773（RAR 延迟释放对齐） | open PR |
| `DEQ-SPLIT-WLINE-001` split 尾段 wline | 15 | #6833 第 3 项 | open PR |
| `DEQ-ZERO-001` CBO.zero 借外部握手 | 15 | #6762 / `dc7eb7338` | 基线后已合并 |
| `DEQ-FINISH-ORDER-001` 年轻项释放老项 | 13 | `4efe9f034`（prefix dequeue） | 已在基线内，残留 14 节点另因 split 语义 |
| `FWD-ALIAS-001` PA 别名漏检 | 12 | #6690（已关）、#6833 第 2 项 | 部分修复仍在 |
| `LSQ-BUS-OWNERSHIP-001` 串行总线误解锁 | 6 | 无专门条目；#6773 同域 | 未修 |
| `FWD-SQID-001` 依赖 SQ 身份 | 3 | `302c0fe19` 等 | 已在基线内修复，残留为其它根因 |

计数沿用 [新基线回归案例](../../../../../../../../docs/lessons/lsq-baseline-regression-20261103.md) 的历史分类，本轮只做上游条目映射，没有重新归因。

## 4. 仍未合并的上游 LSQ 问题与本地覆盖

| 上游条目 | 状态 | 机制 | 本地覆盖 |
|---|---|---|---|
| #6704 跨 16B Store 首/尾请求之间 Load 读旧值 | open issue | 首包已写 vaddr/paddr，`addrValid` 只由尾包置位，前递候选看不到该 Store | **无必达窗口**。`tests/lsq_wrapper/memory_owners.py::write()` 在同一函数内连发首尾包，调用者 `await write_all()` 后才查询；随机流不构成必达门禁。登记为覆盖缺口（见 §5.3） |
| #6229/#6312 部分 mask 被当作完整覆盖 | open issue/PR | `s2FullOverlap` 用跨度而非真实 mask | 已覆盖：`test_partial_store_coverage_must_block_or_forward_every_produced_byte` 3/3 FAIL，且有独立性质 oracle 与灵敏度注入 |
| #6634 多 Uncache 异常按物理槽仲裁 | open PR | `exception.valid := RegNext(writeback)` + `ParallelPriorityMux(entries)` | 已覆盖：`test_uncache_exception_owner_is_oldest_real_bus_error` 2 FAIL（正常完成+真实错误、双真实错误） |
| #6688/#6697 `ColdDownThreshold=0` 禁用 Replay | open issue/PR | 断言未禁止 0 | **配置域外**：DUT 固定阈值 12，未生成 0 配置 |
| #6775 PBMT=NC guest load 复用过期 TLB PA | open issue | NC replay 保留旧 PADDR | **出域**：需要 LoadUnit/TLB 组合，LSQ 模块 UT 不承接 |
| #6813 跨页 Store 第二页字节被年轻 Load 读到旧值 | open issue | 跨页尾段离开 SQ 后 CAM 不再覆盖 | **出域（本层）**：需要 DCache/内存模型与 LDU 才能观察"读到旧值"；本工程合同明确只验证第一页 4B 前递与第二页 Sbuffer 片段，不声称第二页可直接安全转发 |
| #6822 第二页保护提前释放 | open PR | `fromUnalignQueue.ready` 使用 `writeSbufferWire.head.fire` | 与本工程 UQ 合同相关，但第二页对 Load 的可见性同上属整核域；现有两槽 UQ 用例只证明入队/消费/复用 |
| #6833 Store 前递与 uncached store 故障上报（4 项） | open PR | ①uncache 响应读未驱动的 `denied/corrupt`；②同义 VA 跨 16B 只按 vaddr 判；③split 尾段 wline 取自相邻 CBO；④UQ 提前释放 | ③已覆盖：7 个 `wline` FAIL（`DEQ-SPLIT-WLINE-001`）；④见 #6822；②与 #6704/#6229 同域；**①本轮新增覆盖，见 §5.1（红）** |
| #6773 保留 uncache 响应并对齐延迟释放 | open PR | SID 复用会覆盖旧 Load 的缓冲数据/错误；RAR 的 valid 与地址多延迟一拍 | 已覆盖：`LQU-SID-001` 29 节点（SID 复用类）、`RAR-REL-001` 19 节点 |
| #6830 cbo.zero 每次都排空 Sbuffer（性能） | open PR | 状态机逐条 flush | 性能域，未覆盖；不计功能缺陷 |
| #6770 cross16B 使用旧信息 | open PR | 无正文 | 与 #6704/#6718 同域，未单独复现 |
| #6817 LSQ stall HPM 事件条件 | open PR | `dispatchBlock && !lsqCanAccept` | 性能计数域，未覆盖 |
| #6597 分段向量 Store 后 AMO 触发 VSQ `retirePtr` 断言并停提交 | open issue | 退休决策比出队指针早一拍 | **未覆盖**：现有 VSQ 激励只驱动 `flows` 计数，没有"多寄存器分段向量 Store + AMO"的真实算子组合，故不复现 |
| #6826 PMA C=0 的 DRAM 被当作 Device | open PR | LoadUnit/StoreUnit/IFU 只按 PMA mmio 推导 `memBackTypeMM` | **出域**：`memBackTypeMM` 在本工程是驱动输入，其推导属 StoreUnit/LSU；本套 UT 只验证拿到该位之后的行为 |
| #6827 Uncache 主存 Store 的 difftest 地址未对齐 | open PR | 仅改 difftest 事件，RTL 不变 | **出域**：non-RTL，difftest 层 |
| #6832 split/unaligned 故障上报（4 项） | open PR | 页跨 Store 头部故障后永久重放；split Load 报尾触发；Zicbop 预取误报；StoreUnit xtval 未掩码 | **出域/未覆盖**：StoreUnit、LDU 与两阶段 TLB 组合不在本工程 DUT 闭包；UQ 两槽合同不含"一半故障"场景 |
| #6652/#6653 向量 STD 越过 SQ 物理窗口 | open PR | 向量发射缺 `sqIdx` 窗口检查 | **出域**：backend/向量发射，不在 LSQ DUT 闭包 |

## 5. 参考模型与用例 appropriateness 审核

按 [独立 oracle](../../../../../../../../skills/execution/independent-oracle.md) 与
[归因与证据](../../../../../../../../skills/review/triage-and-evidence.md) 的方法逐项检查。

### 5.1 新增覆盖：MMIO Store 的总线故障从未到达原 owner（红）

`UncacheWordResp` 由 `Uncache.toUncacheWordResp` 产生：`r := DontCare` 后只驱动
`data/id/nderr/nc/is2lq/miss/replay/tag_error/error`，**`denied`/`corrupt` 没有驱动**；
而 StoreQueue 的故障判定恰好读这两个字段（`NewStoreQueue.scala:1087/1095`）。Load 侧读的是
`error/nderr`，所以同一份响应在 Load 路径可报错、在 Store 路径不能。

新增 `tests/lsq_wrapper/test_uncache_store_fault.py`（只驱动公开 wrapper 引脚，不读模型）：

| 场景 | 期望 | 实际（`/tmp/opencode/lsq-audit-20261103g-mmiofault`） |
|---|---|---|
| MMIO 正常响应（对照） | 原 owner WB，`exceptionVec_7/19 = 0` | **PASS** |
| MMIO `nderr=1`（访问故障） | WB `exceptionVec_7 = 1` | **FAIL**（实际 0） |
| MMIO `error=1`（硬件错误） | WB `exceptionVec_19 = 1` | **FAIL**（实际 0） |

归因边界：公开引脚上，"响应字段未驱动"与 `hasHardwareError/hasAccessFault` 在
`writeback` 状态被清成 `false.B`（即已登记的 `DEQ-WB-001`）**不可区分**；本用例证明的是
"MMIO Store 的真实总线故障在写回处丢失"，不单独声称新增一个独立根因。上游 #6833 的静态
描述与字段级判断一致，但其 PR 仍未合并。

### 5.2 已修的一处合同缺口：PSQ 未把类型送入 DeqControl

原登记项："`psq/model.py` 未把 `memory_type` 接到 `DeqControl`"。这使得模型内部
`DeqInputs.dequeue_controls` 对所有条目都声称可缓存（`memory_type=0`、`isCbo=False`），
与真实 PSQ 条目类型不一致。

修正：`psq/model.py` 的 `DeqControl` 现在带 `cache_operation` 与 `memory_type`，取自同一
`head` 槽的真实条目。定向验证 `tests/psq tests/store_queue`（seed 1，8 workers，
`/tmp/opencode/lsq-audit-20261103f-psq-sq`）：**125 PASS / 35 FAIL**，与权威完整结果
**逐 nodeid 零变化**。

诚实说明：该修改让喂给 DeqModule 的窗口类型真实，但 `deq/model.py` 的期望只按
`committed/finished/inactive` 计算，并不消费窗口类型，所以本轮没有任何判定变化。真正的剩余
缺口是"deq 侧可缓存条目需要 Sbuffer credit"这条规则仍未进入模型（与 §5.4 的三条 post-edge
残余同源），不能因为引脚修正而声称已关闭。

### 5.3 仍未修的覆盖缺口：跨 16B Store 的首/尾窗口（#6704）

`memory_owners.write()` 在一次调用里发首包并立即发尾包；`write_all()` 之后才 `await`
稳定状态。即使把现有 165 个测试文件全部跑完，也不会出现"首包已接受、尾包未到"的窗口，
因此 #6704 在本工程不可达。这是测试设计缺口，不是"还没跑到"。补法（未实施）：拆出
`write_head_only()`，在首包后插入一个只读低半区字节的 Load 查询，断言"被前递或被阻塞"，
再发尾包与对照。

### 5.4 仍保留的真实残余

- 3 条 post-edge credit 记账节点（`test_split_followed_by_inactive_moves_one_sq_read_position` ×2、
  `test_full_seeded_mixed_traffic_and_fair_drain[nonzero-cbo-control-54020]`）：四种改法实测均
  引入更多回归，保留为 FAIL，不照抄 RTL。
- 同源风险已在 2026-10-22 审计中处理：`forward/model.py` 的 `full` 仍是跨度判断，
  但 `independent_properties.forward_byte_violations` 已用不可变生产者账本独立判定；
  `uncache_entry`/`load_uncache` 的异常仲裁同源点同样有独立 oracle 与灵敏度注入。本轮复核
  未发现新的"模型与 RTL 同错且无独立门禁"点。
- `#6704` 窗口（§5.3）与 `#6688` 配置域仍缺覆盖，已在上表登记，不并入 PASS。

### 5.5 共享 actor 里的同源点：`mixed_owners.py` 把 Store 总线错误当成无错误

`tests/lsq_wrapper/mixed_owners.py` 在 MMIO Store 写回处这样取期望：

```python
response = s["cache_resp"] or dict(denied=False, corrupt=False)
... exceptionVec_7: int(response["denied"]), exceptionVec_19: int(response["corrupt"])
```

`s["cache_resp"]` 只对 CBO 路径存在；普通 MMIO Store 的上车总线响应
（`job["error"]` / `job["nderr"]`，随机 1/8 置位）被直接忽略，期望恒为 0。
也就是说这条共享 actor 复刻了 RTL 的"看未驱动字段"行为，随机注入的总线错误
永远被当成干净完成。它和我新增的独立用例正好是同一缺陷的两种编码：新用例用固定
激励把错误显式打出来（2 FAIL），共享 actor 用随机激励把它吞掉（保持 PASS）。

处理建议（未实施，避免与本轮范围混在一起）：把期望改为
`denied=int(job["nderr"])`、`corrupt=int(job["error"])`，只在真正观察到响应之后
才置位；这会暴露一批 PASS→FAIL，需要单独一轮按"漏检修复"流程复验，不能顺手改。

## 6. 定向测试证据

| 运行目录 | 选择 | seed/workers | 计数 | 说明 |
|---|---|---|---:|---|
| `/tmp/opencode/lsq-audit-20261103a` | forward 折回/mask、SID、CBO zero、wline、public contracts | 1 / 8 | 13 PASS / 23 FAIL | 23 条与权威完整结果逐 nodeid 一致；`serialized_zero[False]`、`neighbor-zero` 的 `nonzero-control` 对照 PASS |
| `/tmp/opencode/lsq-audit-20261103b-nc` | psq、store_queue、serialized CBO、special memory、deq uncache | 1 / 8 | 60 PASS / 17 FAIL | §5.2 修改后的第一批定向；全部 nodeid 都在权威结果内，判定 0 差异 |
| `/tmp/opencode/lsq-audit-20261103f-psq-sq` | `tests/psq tests/store_queue` | 1 / 8 | 125 PASS / 35 FAIL | §5.2 修后；与权威结果逐 nodeid 零差异 |
| `/tmp/opencode/lsq-audit-20261103g-mmiofault` | 新增 MMIO 总线故障用例 | 1 / 2 | 1 PASS / 2 FAIL | 红/绿对照见 §5.1 |
| `/tmp/opencode/lsq-audit-20261103h-diff-targeted` | `tests/deq tests/load_queue tests/load_uncache tests/fail_review tests/normal_mixed` | 1 / 8 | 416 PASS / 64 FAIL | 480 个 nodeid 全部在权威结果内，判定 0 变化；覆盖最近一次 LSQ 提交（`10e0f63`）改动的 deq/load_queue/load_uncache 模块 |

所有运行都使用新输出目录；`run.json` 记录 `git_commit=c13ee6f…`、`git_status`（含本轮未提交
修改）与运行前后 `source_identity.sha256`，seed/workers 随同保存。运行期间没有再改
harness 或模型，因此不存在"源码在运行中变化"的作废条件。

## 7. 结论

1. **上游没有"我们已发现但上游未记录"之外的空白**：基线后 10 天内的 3 个 LSQ 修复全部
   已被本地 FAIL 覆盖（mask 折回 24+4、MDP 退休 4、CBO zero 2），说明本套 UT 在功能域上
   没有落后于上游已修问题；这些 FAIL 是真反例，不是模型滞后。
2. **真正没发现的是"总线故障上报"**：MMIO Store 的 `nderr/error` 在写回处恒为 0，本工程
   此前无任何用例覆盖该路径；已补 1 PASS 对照 + 2 FAIL 反例。归因与 `DEQ-WB-001`
   及上游 #6833 的未驱动字段重叠，不重复计根因。
3. **模型侧**：本轮修掉 PSQ→DeqControl 的类型合同缺口（0 判定变化）；未发现新的同源
   判断点；#6704 的首/尾窗口、#6688 的 0 阈值配置域、跨页第二页的整核可见性分别登记为
   覆盖缺口/出域，不用 PASS 掩盖。
4. 结论只覆盖 LSQ、DefaultConfig、`public-a0c2a26cb`、seed 1；其他九工程未在新基线上回归。

机器记录：[LSQ 上游核查](../../../../../../../../docs/history/lsq-upstream-audit-20261103.json)。
