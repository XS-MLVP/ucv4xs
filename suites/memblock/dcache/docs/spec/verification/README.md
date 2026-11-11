# DCache Verification spec

状态：**现有验证资产的统一入口，完整性待审查**。设计要求见 [Design spec](../design/README.md)。

覆盖与功能证据主记录绑定 `public-893e1580b` / DefaultConfig、
`results/soundness-recheck-03`（210 PASS + 3 XFAIL、61 个功能组 100%）；后续
2026-11-01 事务修复检查点记录 229 PASS + 3 XFAIL，但没有重算覆盖。

当前根默认基线为 `public-a0c2a26cb`。2026-11-10/11 事务适配轮实际改动的 8 个 DUT
（`probe_queue`、`banked_data_array`、`ctrl_unit`、`miss_queue`、`writeback_queue`、
`dcache`、`dcache_wrapper`、`miss_ready_gen`）均已有该基线的 build + smoke 收据；
`duplicated_tag_array`、`counter_filter`、`miss_track`、`load_pipe`、`main_pipe`
本轮未改，仍使用 `public-893e1580b` 的既有 native 包。

2026-11-11 主 agent 已核验这 8 个改动 DUT 的完整当前基线集合：**162 PASS / 3 XFAIL**，
165 个节点与对应 collection 逐项一致，冻结源码稳定。统一入口另选 **20 PASS / 3 XFAIL**，
run_status=PASS、任务 exit 0、CLI exit 1、hardware_verdict=INCOMPLETE；集合重叠不累计。
已审查适配范围接受，不等于完整 DCache/整核硬件签核。其余 5 个仍是旧基线证据；
mixed-native 的 **233 PASS / 3 XFAIL**（`after-full.xml`）不是全工程当前基线结论。
本页不重算覆盖，也不把旧 PASS 推到尚未在新基线重跑的 DUT。

## 1. 验证范围与假设

- 验证 13 个实际 DUT：11 个内部/叶块、DCache 顶层和 DCacheWrapper；各 DUT 有独立
  Picker 构建和测试边界，顶层内联子模块的覆盖率不跨 DUT 相加。
- 激励只使用公开端口；正常回归不启用 VPI、internal signal config 或逐周期信号/事务 dump。
  本轮独立审查另有有界公开引脚摘要与三个场景的字段记录，仅作差分诊断，不计覆盖提升。
- 独立期望来自功能点合同、Chisel/Scala 源码、TileLink 协议和独立行模型；不使用 DUT
  输出反推期望。
- 已知缺陷使用严格 expected-failure 保留真实判定；XFAIL 不计 PASS，修复后应转为
  unexpected pass 并重新评估对应功能点。
- 当前范围不包含 Uncache 与 DCache 的仲裁、CSR/中断、WPU 或完整 MemBlock 组合；
  这些不是 DCacheWrapper 的内部逻辑。

## 2. 功能项、场景与实现关联

| DUT | 测试入口 | 模型/检查器 | 功能点 | 主要证据 |
|---|---|---|---|---|
| DuplicatedTagArray | [testbenches/duplicated_tag_array](../../../testbenches/duplicated_tag_array/tests) | `testbenches/duplicated_tag_array/model.py`、`coverage.py` | [DTA-FP-001..008](../design/functional-points-duplicated-tag-array.md) | [报告](evidence/duplicated-tag-array-20261024.md) |
| CtrlUnit | [testbenches/ctrl_unit](../../../testbenches/ctrl_unit/tests) | `testbenches/ctrl_unit/env/__init__.py`、`coverage.py` | [CU-FP-001..009](../design/functional-points-ctrl-unit.md) | [报告](evidence/ctrl-unit-20261024.md) |
| MissReadyGen | [testbenches/miss_ready_gen](../../../testbenches/miss_ready_gen/tests) | `testbenches/miss_ready_gen/env/__init__.py`、`coverage.py` | [MRG-FP-001..005](../design/functional-points-miss-ready-gen.md) | [报告](evidence/miss-ready-gen-20261024.md) |
| CounterFilter | [testbenches/counter_filter](../../../testbenches/counter_filter/tests) | `testbenches/counter_filter/model.py`、`coverage.py` | [CF-FP-001..006](../design/functional-points-counter-filter.md) | [报告](evidence/counter-filter-20261024.md) |
| MissTrack | [testbenches/miss_track](../../../testbenches/miss_track/tests) | `testbenches/miss_track/model.py`、`coverage.py` | [MT-FP-001..009](../design/functional-points-miss-track.md) | [报告](evidence/miss-track-20261024.md) |
| LoadPipe | [testbenches/load_pipe](../../../testbenches/load_pipe/tests) | `testbenches/load_pipe/model.py`、`coverage.py` | [LP-FP-001..008](../design/functional-points-load-pipe.md) | [报告](evidence/load-pipe-20261024.md) |
| BankedDataArray | [testbenches/banked_data_array](../../../testbenches/banked_data_array/tests) | `testbenches/banked_data_array/model.py`、`coverage.py` | [BDA-FP-001..008](../design/functional-points-banked-data-array.md) | [报告](evidence/banked-data-array-20261024.md) |
| MainPipe | [testbenches/main_pipe](../../../testbenches/main_pipe/tests) | `testbenches/main_pipe/env/__init__.py`、`coverage.py` | [MP-FP-001..018](../design/functional-points-main-pipe.md) | [报告](evidence/main-pipe-20261025.md) |
| MissQueue | [testbenches/miss_queue](../../../testbenches/miss_queue/tests) | `testbenches/miss_queue/env/__init__.py`、`coverage.py` | [MQ-FP-001..010](../design/functional-points-miss-queue.md) | [报告](evidence/miss-queue-20261025.md) |
| ProbeQueue | [testbenches/probe_queue](../../../testbenches/probe_queue/tests) | `testbenches/probe_queue/env/__init__.py`、`coverage.py` | [PQ-FP-001..004](../design/functional-points-probe-queue.md) | [报告](evidence/writeback-probe-20261024.md) |
| WritebackQueue | [testbenches/writeback_queue](../../../testbenches/writeback_queue/tests) | `testbenches/writeback_queue/env/__init__.py`、`coverage.py` | [WQ-FP-001..005](../design/functional-points-writeback-queue.md) | [报告](evidence/writeback-probe-20261024.md) |
| DCache | [testbenches/dcache](../../../testbenches/dcache/tests) | `testbenches/dcache/env/__init__.py`、`testbenches/dcache/env/traffic.py`、`tilelink.py` | [DC-FP-001..013](../design/functional-points-dcache.md) | [顶层报告](evidence/dcache-top-20261025.md) |
| DCacheWrapper | [testbenches/dcache_wrapper](../../../testbenches/dcache_wrapper/tests) | `testbenches/dcache_wrapper/env/__init__.py`、`tools/wrapper_portmap.py` | [WFP-001..007](../design/functional-points-dcache-wrapper.md) | [wrapper 报告](evidence/dcache-wrapper-20261025.md) |

### 覆盖组实现

功能点文档末尾的覆盖组是当前功能覆盖定义；每个组在对应 DUT 的 `coverage.py` 中实例化，
只有在行为比较成功后才采样。组名与实现对应如下：

| DUT | 覆盖组 |
|---|---|
| DuplicatedTagArray | `duplicated_tag_array.reset/read/write/conflict/mbist` |
| CtrlUnit | `ctrl_unit.access/regs/inject` |
| MissReadyGen | `miss_ready_gen.channel/field/independence` |
| CounterFilter | `counter_filter.query/enq/lifetime` |
| MissTrack | `miss_track.spec/event/table/lifecycle` |
| LoadPipe | `load_pipe.transaction/miss/conflict` |
| BankedDataArray | `banked_data_array.read/write/line/conflict/ecc` |
| MainPipe | `main_pipe.store/atomic/probe/refill/prefetch/lrsc/amo_cas/refill_evict/flag_error/ecc/address` |
| MissQueue | `miss_queue.alloc/merge/refill/release/block/cmo/store_flag` |
| ProbeQueue | `probe_queue.probe` |
| WritebackQueue | `writeback_queue.release/ack/block` |
| DCache | `dcache.load/miss/store/control/eviction/atomic/cmo` |
| DCacheWrapper | `dcache_wrapper.portmap/ctrl/core/channel/perf/spec` |

L2 传输检查的独立边界见 [L2 传输合同](../design/l2-transport-contract.md) 与
[testbenches/dcache/tests/checkers/test_l2_responder.py](../../../testbenches/dcache/tests/checkers/test_l2_responder.py)。
端口映射的可审计产物是 `manifest/dcache-wrapper-portmap.json`（由
`tools/wrapper_portmap.py` 生成）。

### 事务适配边界

功能用例只通过各 DUT 的 env 方法提交请求、读取不可变快照；物理引脚名、编码和
`.Set/.Step` 留在 env/driver 适配层。当前已收口的接口如下（不是覆盖率或硬件通过凭据）：

| DUT | 事务入口 | 采样/接受边界 |
|---|---|---|
| ProbeQueue | `ProbeRequest`、`offer_probe/settle_probe/transmit_probe/cancel_probe_offer`、`hold_mainpipe_ready`、`observe_pipe_window`、`lock_lrsc_block/unlock_lrsc_block` | B ready 在推进沿前采样；未接受时保持 valid/payload；未 settle 的 offer 不得覆盖；新 offer 不清 LR/SC 等持久控制；`ProbeAcceptance` 记录 fired/cycles |
| BankedDataArray | `ReadRequest`、`read_ports_together`、`read_line_with_read`、`readline_hold_without_go`、`readline_go_with_stall` | `read_ports_together` 是单拍 attempt：ready 沿前采样，逐 port 返回 `accepted`；只有 accepted 的窗口/延迟冲突被读取并更新缓存，未接受不产生响应；`read_line_with_read` 返回冻结 `ReadlineHazard`。所有输入域在 `_idle` 写入前校验 |
| CtrlUnit | `send_write/write/read`、`read_held`、`d_pending/accept_d` | D valid/ready 在沿前判断；held read 逐沿检查数据稳定 |
| MissQueue | `enqueue/enqueue_parallel`、`refill`、`complete`、`check_block`、`cmo_request`、`drive_lq_empty`、`full_state` | 所有 fire 条件先 refresh 再推进；返回逐拍快照 |
| MissReadyGen | `drive/drive_ready/eval/check`、`ready_snapshot/valid_snapshot` | 组合扇出每向量在 `Step` 后整组比较，不逐引脚读取 |
| WritebackQueue | `drive/fire/cancel_request`、`issue_and_wait`、`ack`、`block_probe` | C valid 沿前采样；D ack 以 source 关联 |
| DCache | `load_once`、`service_miss`、`refill_with_releases`、`transmit_probe`、`observe_release/wait_release/acknowledge_release`、`drive_lq_state`、`wait_error` | A/B/D/C 握手在沿前采样；`observe_release` 只读不消费（无 beat 时最多推进 `limit` 沿，推进沿先关 C.ready，不能消费未登记 beat）；`wait_release` 只在完整 Release(1 beat)/ReleaseData(2 beats) 的真实接受后返回带 token 的 `ReleaseMessage`，总 `limit` 为沿预算，beat 间合法空拍不读 payload、不计 beat，超预算/头变化都失败；`acknowledge_release` 以本 env 登记的**对象身份**绑定（同值跨 env/复制 token 也拒绝）且 ack-once，错 source/channel/header/旧 reset 世代/伪造/重复在任何 D 驱动前拒绝，ACK 沿关闭其他 C ready；`wait_error` 先 Step 再采样，保持原 12 沿窗口 |
| DCacheWrapper | 继承 DCache 事务；`fabric_state/drive_fabric_committed/watch_fabric_candidate`、`perf_snapshot`、`wrapper_pin_names`、`perf_internal_net` | wrapper 端口改名和 42 个 perf 输出以不可变快照返回；`watch_fabric_candidate` 先采样候选、再在 `stop_cycle` 撤 load valid、最后返回，恢复冻结用例的撤激励顺序 |

`tests/checkers/` 下的 L2 responder 自检保留 `selftest` 分类；它们验证编码/装配器，
不计硬件功能 credit。静态 `--require-transaction-boundary` 清零只说明这些文件不再出现
引脚/信号语法耦合，不等于 monitor 所有权、独立 oracle 或硬件语义已经验收。

## 3. 运行、覆盖与判定

最近完整运行 `results/soundness-recheck-03`（2026-10-26，seed 1，`--workers 4`）：

| 指标 | 结果 | 口径 |
|---|---|---|
| 用例 | 210 PASS + 3 XFAIL / 219.28 s | 3 个 XFAIL 是同一已确认缺陷 `MQ-STORE-MERGE-DATA-PENDING` 的三处严格复现 |
| 功能覆盖 | 61 组全部 100% | 每组有行为级断言，不是信号枚举 |
| 子模块行覆盖 | 8059 / 8309 = 97.0% | DUT-only；8 个 DUT 为 100% |
| DCache 行覆盖 | 50262 / 51179 = 98.21% | 剩余行是内联子模块重复计数和生成代码 |
| DCacheWrapper 行覆盖 | 50455 / 51265 = 98.42% | wrapper 自身 86 / 86 = 100% |
| trace policy | PASS | 无波形、无逐周期 dump |

数字取自 [覆盖率报告](evidence/coverage-20261025.md)；该报告保留原运行、工具版本和
分母。多 seed 记录为 `seed-sweep-01..04`，四个种子结果一致。上述数字只属于
`public-893e1580b` 和对应构建，不能外推到当前默认基线或整核。

后续 2026-11-01 事务修复检查点记录 **229 PASS + 3 XFAIL**：原项逐条判定保持，新增项
包含事务边界和自检；该运行没有重算上面的覆盖率数字，也不改变 3 个 XFAIL 的缺陷归属。
两组结果都绑定 `public-893e1580b`。当前基线只对本文开头列出的 8 个改动 DUT 有
build/smoke/完整受影响集合运行收据；其余 5 个 DUT 仍以旧基线证据为准，不能合并成统一结论。

本轮原 232 项收集保全，新增 1 个多沿背压功能控制和 4 个纯自检，共 237 项。固定原
native 对照的 37 个原节点两侧均 **34 PASS / 3 XFAIL**，判定保全不表示逐沿完全相同：
两处 B.valid 在接受后撤销，clean Release 的 ready 刷新/完成判断修正后少走 7 沿；
该实测 clean Release 不属于“C 完成前提前 ACK”，不可与通用半包 ACK 控制反例混称。
证据与剩余框架所有权边界见
`results/transaction-adapters-20261110/dcache/independent-final-review.md`，不升级历史覆盖或问题状态。

覆盖率口径：行覆盖为 DUT-only，排除 Picker harness；分支为 Verilator 原生点；
toggle 不作为通过标准。顶层内联子模块的覆盖率不跨 DUT 求和。审查记录见
[用例可信度复核](evidence/soundness-recheck-20261026.md) 和
[交付自检](evidence/delivery-selfcheck-20261025.md)。

## 4. 当前未关闭项与完成条件

范围、资源和接口边界约束（含稳定 ID）见 [constraints.md](constraints.md)，
例如 DCacheWrapper 不包含 Uncache 通路；它们不是当前缺陷，也不是设计退役。

- [MQ-STORE-MERGE-DATA-PENDING](../../bugs/open/MQ-STORE-MERGE-DATA-PENDING.md)：确认
  RTL 缺陷，未修复；严格 xfail 保留。
- [CF-DEQUEUE-PIPELINE-NO-RESET](../../bugs/open/CF-DEQUEUE-PIPELINE-NO-RESET.md)：短复位
  下 CounterFilter 出队流水可能偏移；环境中以 5 拍复位规避，上游未修复。
- [DCACHE-REFILL-NOT-RESIDENT](../../bugs/closed/DCACHE-REFILL-NOT-RESIDENT.md)：原 RTL
  指控已按验证环境误报关闭（`invalid`，仅关闭 `public-893e1580b` 的旧归因）；当前默认
  基线仍为 `unverified`，新基线未复跑不等于旧 RTL 指控重新成立。
- 未纳入范围：Uncache/WPU/CSR、完整 MemBlock 组合、SRAM 阵列全扫和未被公开端口
  暴露的旁路；这些缺口不能被“功能组 100%”覆盖。
- 完成条件：设计要求有可追溯依据；当前基线的构建/冒烟/功能运行和产物完整性可核验；
  open/closed 问题结论与证据一致；未验证范围明确，不以修改期望或扩大豁免取得全绿。

## 5. 证据索引

重要历史运行材料保存在 [evidence/](evidence/README.md)，包括逐 DUT UT 报告、覆盖率、
功能点审计、P0 收口、交付自检和旧版说明；文件保留原日期、基线和结论边界。运行产物
本身仍在被忽略的 `results/`；本轮当前基线实测与历史资料分别列于上文，不修改旧报告原字节。
