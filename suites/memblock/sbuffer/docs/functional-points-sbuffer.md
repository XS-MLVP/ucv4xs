# Sbuffer 顶层功能点、合同与状态

Sbuffer 是 MemBlock 中位于 StoreQueue 与 DCache 之间的 16 行写合并缓冲。本文件先定义
人类可读的微架构语义，再映射到用例和覆盖 bin。子块 `SbufferData` 的语义见
[functional-points-sbuffer-data.md](functional-points-sbuffer-data.md)。

源码基线 `kunminghu-v3 @ 893e1580`；RTL 为 `../../soc-split/rtl/Sbuffer.sv` 原样副本。
Picker 只导出一份 `Sbuffer` DUT（内部保留真实 `SbufferData`），导出参数含
`--rw mem_direct -w memory-direct.fst -c`；不启用 VPI、不启用 internal-cfg。运行时
不调用 `SetWaveform`，因此 trace 能力已编译但默认不产生波形；也不写逐周期信号/事务
dump。

## 1. 结构与职责

```
Sbuffer
├── SbufferData（真实子块，16 行 × 4 lane × 16 字节）
├── PLRU 行替换
├── 入队 s0/s1/s2 三级流水与 merge/insert
├── 写出 s0/s1 + DCache 命中/重放响应
├── 三种排空状态（idle / replace / drain_all / drain_sbuffer）
└── 三路 load 数据转发
```

Sbuffer 只保存 **已提交（committed/retired）** 的 store；它不负责发射、地址翻译或
写回 ROB。行的 `state_valid` 表示槽内有尚未写出的字节；`state_inflight` 表示该行
正在写往 DCache。

## 2. 功能点

### SBT-ENQ-01 新行分配与同拍双端口
一笔 store 命中已有行时合并到该行（`merge`）；否则分配一个空行（`insert`）。
两路 store 可以同拍入队：异行各占一行；同一新行可在同拍接收两个 lane 的字节，
后一个端口覆盖重叠字节。父块的 `in.req(1).ready` 依赖 `in.req(0).ready`，因此
端口 1 不会单独先于端口 0 被接受。
**观察**：入队后通过转发读回字节；行内容与端口顺序一致。

### SBT-ENQ-02 行位图与虚标签别名
`wvec` 按物理标签选择行。合并时若新 store 的虚标签与行保存的虚标签不同，说明同一
物理行被不同虚地址写过，硬件置 `merge_need_uarch_drain`，随后排空整个 Sbuffer。
**观察**：跨虚标签合并后新入队被阻塞，排空完成后恢复接受。

### SBT-ENQ-03 容量与 sbFull
16 行全部有效时 `sbFull=1`，新行被阻塞；已有行的 merge 仍可接受。写出并收到
DCache 命中响应后释放行，`sbFull` 撤销、入队恢复。
**观察**：满时 ready=0、合并仍 ready；释放后 ready=1。

### SBT-ENQ-04 同块 inflight 串行
同一物理块已有 inflight 写请求时，新 store 仍可分配一个不同行（用于接收新数据），
但该新行不得在旧请求返回前写往 DCache。
**观察**：同块旧请求未 hit 前，新行不产生写请求；hit 后才写出。

### SBT-WRITE-01 写出原因与 payload
写请求可以由四种原因触发：行超时（`cohCount` 达到 `sbuffer_timeout`）、容量替换
（活动行数达到阈值）、flush 排空、以及 replay 后重试。请求携带行内完整的 512 位
data/mask 与物理/虚拟行地址；`addr` 只保留行基址，`vaddr` 保留虚标签。
**观察**：请求的 mask/data 必须与模型中该行内容逐字节一致；id 落在 16 行内且对应
唯一一条内容匹配的活行。

### SBT-WRITE-02 replay 重试
DCache 用 `replay_resp` 表示该行需要重发。行保持有效、置 `w_timeout`；超时计数
到期后同一行槽重发写请求，最终由 `main_pipe_hit_resp` 释放。
**观察**：重试请求的 id/地址/mask/data 与首次一致；命中后行消失。

### SBT-FLUSH-01 两级空语义与三种排空条件
Sbuffer 对外提供两个“空”信号，语义不同，消费者也不同：

| 信号 | 语义 | 消费者 | 是否含 SQ |
|---|---|---|---|
| `sbempty` | Sbuffer 行全空 && 在途输入为空 && MSHR 无 store miss | LSQ → `SbufferCtrlIO.Resp.empty` → CBO FSM | 否 |
| `flush.empty` | `sbempty && sqempty` | `MemBlock.stIsEmpty` → Fence 的 `sbIsEmpty`；AtomicsUnit | 是 |

- **CMO flush（isCmo=1）**：完成条件是 `sbempty`。CMO 必须在 SQ 头部执行，其自身 SQ
  条目在 writeback 前不释放，所以处理期间 `sqempty` 必为 0；要求 `sqempty` 会死锁。
  CMO 必须等待更老的已提交 store 真正到达一致性点，因此 `sbempty` 还要包含
  `mshr_store_empty`。更年轻的 store 由 SQ 顺序出队天然阻塞，无需排空。
- **普通 flush（fence/atomics，isCmo=0）**：完成条件是 `flush.empty`，必须等整条
  store 路径（Sbuffer + 输入 + MSHR + SQ）都空。
- **uarch drain**：虚标签别名合并触发，只排空 Sbuffer 自身，不要求 MSHR/SQ。

设计依据：上游 PR #6183 显式拆分 `cmo_empty`/`all_empty`；`MemBlock` 把 `sbempty`
接到 LSQ、把 `flush.empty` 接到 `stIsEmpty`；`Fence` 等 `sbIsEmpty`，CBO FSM 等
`sbufferCtrl.resp.empty`。完整论证见
[flush 合同复核](reports/flush-contract-review-20261024.md)。

**观察**：CMO 排空后，MSHR 非空时 `sbempty=0`；MSHR 空后即使 `sqempty=0`，`sbempty=1`
而 `flush.empty=0`；`sqempty=1` 后 `flush.empty=1`。普通 flush 排空后 `sbempty=1` 但
`flush.empty=0`，直到 `sqempty=1`。

### SBT-WRITE-01 写出原因与 payload
写请求可以由四种原因触发：行超时（`cohCount` 达到 `sbuffer_timeout`）、容量替换
（活动行数达到阈值）、flush 排空、以及 replay 后重试。请求携带行内完整的 512 位
data/mask 与物理/虚拟行地址；`addr` 只保留行基址，`vaddr` 保留虚标签。
**观察**：请求的 mask/data 必须与模型中该行内容逐字节一致；id 落在 16 行内且对应
唯一一条内容匹配的活行。

**`wline` 的合法域**：父块只在 `cbo.zero` 产生 `wline`，且 payload 恒为 0
（`NewStoreQueue`: `wline := isCbo && isCboZero`；cbo.zero 的 store data 被强制为 0；
RTL 断言为 "wline only supports whole zero write now"）。顶层 UT 只在零 payload 下
验证 `wline`；`SbufferData` 模块级的非零 payload 广播只作为模块能力，不代表父块可达
行为。

### SBT-FWD-01 三路 load 转发
每路 load 查询在 s0 给出虚地址、s1 给出物理地址；Sbuffer 在 s2 返回该 16B lane
的字节 mask/data。有效行（active）优先于 inflight 行；同拍多行命中时按行索引
Mux1H。
**观察**：返回 mask/data 与模型中对应 lane 的合并字节一致；无命中时 mask=0。

### SBT-FWD-02 虚实标签不一致告警
若某行的虚标签匹配但物理标签不匹配（或反之），`matchInvalid=1`，提示父级需要
重放；`s1Kill` 抑制该告警。该告警不阻断返回数据。
**观察**：单向不一致时 invalid=1；kill 时 invalid=0；一致时为 0。

### SBT-RESET-01 复位
复位清空所有行、在途请求和 replay 状态；复位后 `sbempty=1`、`sbFull=0`、无写请求。
**观察**：复位后不残留旧行/旧请求。

## 3. 功能点 → 用例 → 覆盖 bin

| 功能点 | 用例 | 覆盖组 |
|---|---|---|
| SBT-ENQ-01 | `test_merge_and_forward`、`test_dual_port_enqueue` | `sbuffer_enq` |
| SBT-ENQ-02 | `test_uarch_drain_on_vtag_mismatch_merge` | `sbuffer_enq` |
| SBT-ENQ-03 | `test_capacity_full_and_resume` | `sbuffer_capacity` |
| SBT-ENQ-04 | `test_sameblock_serialization` | `sbuffer_sameblock` |
| SBT-WRITE-01 | 所有写出用例（含 `test_wline_zero_all_lines` 的零 payload wline） | `sbuffer_writeout` |
| SBT-WRITE-02 | `test_replay_resends_same_line` | `sbuffer_replay` |
| SBT-FLUSH-01/02 | `test_fence_flush_empty_requires_sqempty`、`test_cmo_completion_uses_sbempty_without_sqempty`、`test_uarch_drain_on_vtag_mismatch_merge` | `sbuffer_flush` |
| SBT-FWD-01/02 | `test_merge_and_forward` | `sbuffer_forward` |
| SBT-RESET-01 | `test_reset_and_idle`、`test_reset_with_entries` | `sbuffer_reset` |

## 4. 合法输入域与 don't-care

- `in.req` 只在 `ready=1` 时算接受；payload 在 valid=0 时不比较。
- `sqempty` 由 LSQ 提供；`mshr_store_empty` 由 DCache 提供；本 UT 以外部代理驱动，
  不代表相应父块已通过。
- `csrCtrl.sbuffer_timeout` 决定行超时；`force_write` 降低替换阈值。
- 未初始化/已释放行的 data 不比较；只比较模型中记录为有效的字节。
- `perf_*` 输出只作活动见证，不作为功能正确性答案。
- 波形默认关闭；诊断需要时显式传 `waveform_filename` 并单独保存。

## 5. 当前状态

- 16 个顶层用例全部 PASS；功能覆盖 8 组 100%；DUT 行 12648/13191（95.88%）、
  branch 2690/2724（98.8%）、toggle 70275/85706（82.0%）；剩余缺口见 known-issues。
- 覆盖率分析与补例闭环见 `docs/reports/`。
