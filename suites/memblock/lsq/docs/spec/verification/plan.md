# LSQ：内部子模块 → 分支组合 → 整体 UT

状态：当前实施计划，描述持续有效的验证范围、真实层次、实施顺序、合同门禁和完成条件。基线为工程继承的 `public-a0c2a26cb`（DefaultConfig）。2026-10-18/19 的逐轮进度和旧里程碑已迁到 [evidence/plan-progress-20261018-20261019.md](evidence/plan-progress-20261018-20261019.md)，保留原日期、旧根 `memblock-hash/lsq/`、旧基线 `XiangShan 893e1580…` 和原结论；本页不再把旧轮次写成当前状态。

## 1. 当前入口与状态

| 内容 | 入口 |
|---|---|
| 验证范围、功能点、覆盖、问题与完成条件 | [Verification spec](README.md) |
| 可执行功能点矩阵 | [`testbenches/lsq_wrapper/coverage/function_points.py`](../../../testbenches/lsq_wrapper/coverage/function_points.py)；自检 `testbenches/lsq_wrapper/tests/meta/test_function_points.py`、`testbenches/lsq_wrapper/tests/meta/test_critical_fields.py` |
| 当前问题状态 | [bugs/README.md](../../bugs/README.md)；`open/`、`closed/` 目录是唯一当前状态依据 |
| 设计合同 | [Design spec](../design/README.md) 与 [contracts/](../design/contracts) |
| 历史运行报告 | [evidence/reports/](evidence/reports)；保留原日期、基线和判定 |
| 旧计划与逐轮进度 | [evidence/plan-progress-20261018-20261019.md](evidence/plan-progress-20261018-20261019.md) |

- 最近完整运行记录为 2026-11-06 `public-a0c2a26cb` seed 1 的 2600 节点 **2369 PASS / 231 FAIL**，不是整体验收；本次 2026-11-09 文档整理没有重跑 native。
- 当前问题目录为 **17 open / 2 closed**。`FWD-SQID-001`、`LRQ-STRICT-001` 已依据 `public-a0c2a26cb` 的完整回归记录和进入基线的上游提交关闭；旧基线 `893e1580…` 版本仍为 open，历史 FAIL 和旧报告保留。正式记录见 [FWD-SQID-001](../../bugs/closed/FWD-SQID-001.md)、[LRQ-STRICT-001](../../bugs/closed/LRQ-STRICT-001.md)。
- 本文只描述当前仍需执行的验证范围和顺序，不把任何历史 PASS、覆盖百分比或已关闭单项当成整体验收。

## 2. 范围与真实层次

验证根为工程 `suites/memblock/lsq`（历史文档中的旧根 `memblock-hash/lsq/` 已迁移；旧路径映射见 `docs/navigation.json` 的 `relocations`）。验证对象是 `LsqWrapper` 的真实 RTL 子树：内部子块、Load/Store 分支和整体分别建立独立 DUT 与证据，不直接以整块 smoke 代替分层验证。

当前锁定源码中的关键实例化位置（供合同/源码核对；完整路径登记在 `workspace.json` 的 `chisel` 字段）：

- `mem/MemBlock.scala:512-514` 实例化 `NewLoadUnit`/`NewStoreUnit`/`StdExeUnit`；`:588` 实例化 `LsqWrapper`。
- `mem/lsqueue/LSQWrapper.scala:158-159` 实例化 `LoadQueue`/`StoreQueue`。
- `mem/lsqueue/LoadQueue.scala:229-233` 实例化 `LoadQueueRAR`/`LoadQueueRAW`/`LoadQueueReplay`/`VirtualLoadQueue`/`LoadQueueUncache`。
- `mem/lsqueue/LoadQueueUncache.scala:298` 实例化 16 个 `UncacheEntry`；`:300` 实例化 `FreeList_3`。
- `mem/lsqueue/LoadQueueRAR.scala:103`/`:121` 实例化 `LqPAddrModule`/`FreeList`；`LoadQueueRAW.scala:91`/`:103`/`:119` 实例化 `LqPAddrModule_1`/`LqMaskModule`/`FreeList_1`；`LoadQueueReplay.scala:113` 定义 `AgeDetector`，`:176-187` 提供 apply helper，`:630` 在 3 个 bank 的 map 中调用，生成 `AgeDetector_36..38`；`:299` 实例化 `FreeList_2`。
- `mem/lsqueue/NewStoreQueue.scala:905` 在 `DeqModule` 内实例化 `EnterSbufferQueue`；`:1617-1619` 实例化 `ForwardModule`/`DeqModule`/`UnalignQueue`；`:2185-2186` 实例化 `VirtualStoreQueue`/`PhysicalStoreQueue`。

真实层次：

```text
MemBlock
├── LsqWrapper
│   ├── LoadQueue
│   │   ├── VirtualLoadQueue
│   │   ├── LoadQueueRAR
│   │   │   ├── FreeList
│   │   │   └── LqPAddrModule
│   │   ├── LoadQueueRAW
│   │   │   ├── FreeList_1
│   │   │   ├── LqPAddrModule_1
│   │   │   └── LqMaskModule
│   │   ├── LoadQueueReplay
│   │   │   ├── FreeList_2
│   │   │   └── AgeDetector_36 × 3
│   │   └── LoadQueueUncache
│   │       ├── UncacheEntry / UncacheEntry_1 … _15
│   │       ├── FreeList_3
│   │       └── 仲裁与流水寄存器
│   └── StoreQueue
│       ├── VirtualStoreQueue
│       └── PhysicalStoreQueue
│           ├── ForwardModule
│           ├── DeqModule
│           │   └── EnterSbufferQueue
│           └── UnalignQueue
└── ExceptionInfoGen                    ← 相邻 MemBlock 子块，不在 LSQ 内

Backend / CtrlBlock
└── LsqEnqCtrl                          ← 相邻分配控制，不在 LsqWrapper 内
```

`ExceptionInfoGen`、`LsqEnqCtrl` 虽在 `mem/lsqueue/` 源目录定义，却不是 `LsqWrapper` 的子模块；前者留给 MemBlock 异常汇聚专项，后者作为 LSQ 完成后的分配/恢复联调对象。

## 3. 基线配置与变体映射

当前锁定源码 `Parameters.scala:102-113` 的主要配置：VLQ=120、RAR=96、RAW=56、Replay=120、Uncache entries=16、物理 SQ=64、SQ Multiple=2、SnapshotInterval=1、UnalignQueue=2；`Parameters.scala:167-168` 给出 LoadPipelineWidth=3、StorePipelineWidth=2。默认 DCache 是双通道。本工程先覆盖此实际配置，不承诺任意参数 sweep；SnapshotInterval 当前源码要求为 1，RAW=56、VLQ/Replay=120 不是 2 的幂，指针不可按简单二进制截断模拟。

| 家族 | DUT keys | 真实 top | 定义与实例化来源 |
|---|---|---|---|
| FreeList | `freelist_rar`、`freelist_raw`、`freelist_replay`、`freelist_uncache` | `FreeList`、`FreeList_1`、`FreeList_2`、`FreeList_3` | `FreeList.scala:25` 定义；分别由 `LoadQueueRAR.scala:121`、`LoadQueueRAW.scala:119`、`LoadQueueReplay.scala:299`、`LoadQueueUncache.scala:300` 实例化。四个 top 共用同一类定义，后缀是 Chisel 对同名实例的消歧名，不是四个不同类。 |
| 地址/字节 CAM | `cam_rar`、`cam_raw`、`cam_mask` | `LqPAddrModule`、`LqPAddrModule_1`、`LqMaskModule` | `LoadQueueData.scala:136`/`:210` 定义；RAR/RAW 分别在 `LoadQueueRAR.scala:103`、`LoadQueueRAW.scala:91`/`:103` 实例化。 |
| Age selector | `age_replay` | `AgeDetector_36`（代表 `AgeDetector_36..38`） | `LoadQueueReplay.scala:113` 定义；`:176-187` apply helper；`:630` 三个 bank 各一个实例。DUT 只选一个 top，测试按 40 entries、3 enq 参数检查共享语义。 |
| Uncache entry | `uncache_entry_0` … `uncache_entry_15` | `UncacheEntry`、`UncacheEntry_1` … `_15` | `LoadQueueUncache.scala:33` 定义；`:298` 用 `Seq.tabulate(LoadUncacheBufferSize)` 以 `entryIndex` 实例化 16 个。后缀是生成名，不是独立类。 |
| Load 业务 | `virtual_load_queue`、`load_queue_rar`、`load_queue_raw`、`load_queue_replay`、`load_queue_uncache`、`load_queue` | 同名 top | 定义文件见各自合同；`LoadQueue.scala:229-233` 组合五个子块，`LSQWrapper.scala:158` 组合 `LoadQueue`。 |
| Store 业务 | `virtual_store_queue`、`forward_module`、`deq_module`、`unalign_queue`、`enter_sbuffer_queue`、`physical_store_queue`、`store_queue` | 同名 top | 定义与实例化见 `VirtualStoreQueue.scala`、`NewStoreQueue.scala:905,1617-1619,2185-2186`，`StoreQueue` 由 `LSQWrapper.scala:159` 组合。 |
| 整体 | `lsq_wrapper` | `LsqWrapper` | `LSQWrapper.scala:86` 定义；`MemBlock.scala:588` 实例化。 |

后缀不可随意替换，也不能使用别的模块里同名的 FreeList/AgeDetector。FreeList 源码的 `allocateReq`、`empty` 等端口可能在现成 SV 中被常量传播删除；合同以实际公开端口为准，不绑定不存在的信号，也不把缺失观察点标成已测。

## 4. DUT 清单、层次与实施顺序

| 层 | DUT keys | 先完成的主要依赖 |
|---|---|---|
| L0 | `freelist_*`、`cam_*`、`age_replay`、`uncache_entry_*`、`enter_sbuffer_queue`、`unalign_queue`、`forward_module` | 各自公开接口、合法分配/查询域和独立参考 |
| L1 | `virtual_load_queue`、`load_queue_rar`、`load_queue_raw`、`load_queue_replay`、`load_queue_uncache`、`virtual_store_queue`、`deq_module` | 对应 L0 子块与外部协议代理 |
| L2 | `physical_store_queue`、`store_queue`、`load_queue` | P-M 子块组合、真实子块保留、跨块事务生命周期 |
| L3 | `lsq_wrapper` | LoadQueue、StoreQueue 全部真实子块和外部 producer/consumer 边界 |

推荐顺序：基线/合同门禁 → 四个 FreeList 变体 → 地址/mask CAM → AgeDetector → VirtualLoadQueue（第一个业务 DUT）→ 其余 Load 业务块 → Store 叶子与业务块 → PhysicalStoreQueue → StoreQueue/LoadQueue → LsqWrapper → LsqEnqCtrl 相邻专项。此顺序是工程依赖顺序，不表示 VirtualLoadQueue 实例化 FreeList；每块使用独立真实 DUT 和 checker，父块测试保留真实子块。

完整 LSQ 验收前须覆盖四个 FreeList 变体和 UncacheEntry 的实际 ID 特化。DelayN/通用仲裁先在业务父块中验证连接影响，除非有独立风险，不先扩成通用组件项目。`LqRawDataModule` 是抽象类；Bundle/Ptr 是类型；未在本子树实例化的 `LqVAddrModule` 不列为本轮 DUT。

闭包文件数、物理行数和旧轮次计数只属于对应历史基线，已随逐轮进度迁入 [历史材料](evidence/plan-progress-20261018-20261019.md)，本页不以旧闭包数字代替当前构建/覆盖证据。

## 5. 子块最少功能集合

下列功能组是人工检查清单；可执行 kind × outcome 与交互窗口以 [`testbenches/lsq_wrapper/coverage/function_points.py`](../../../testbenches/lsq_wrapper/coverage/function_points.py)、[kind-outcome-matrix](../design/contracts/kind-outcome-matrix.md) 和 [interaction-semantics](../design/contracts/interaction-semantics.md) 为准。组 ID 不是当前 coverage schema；缺失项按合同和矩阵补，不能用声明式 bin 采样代替 reached/checked。

### 基础块

| 功能组 | DUT | 必查项 |
|---|---|---|
| LSQ-FL | FreeList 家族 | 复位槽位集合、合法多路分配、耗尽、回收、同拍分配/回收、回绕、无重复活跃分配；预分配延迟与分 bank 回收批次 |
| LSQ-CAM | PAddr/Mask CAM | 写生效延迟、同步读/read-enable 保持、比较结果、RAR/RAW 编码、mask 相交、wline/cacheline 选择 |
| LSQ-AGE | AgeDetector_36 | ready 子集内最老选择、同拍多 enq 的年龄、testbenches/deq/重用冲突、空结果；确认使用旧状态而非误作零延迟 next-state |
| LSQ-UE | UncacheEntry 家族 | MMIO 等 ROB 头与 NC 发起规则、请求背压、mid/sid、响应、wakeup、bypass 消费、错误、各阶段 redirect |
| LSQ-ESB | EnterSbufferQueue | 多路顺序约束、背压、满空、同拍出入复用、deqPtrMove 与真实消费关联 |
| LSQ-UQ | UnalignQueue | 第二物理页地址、SQ 索引、addrReadyPtr 门控、redirect、回绕、合法 one-hot 入队 |
| LSQ-FWD | ForwardModule | 年龄域/回绕、年轻匹配 store、字节范围、跨 16B/跨页、数据未就绪、虚实地址不一致、CBO、无效槽排除 |

FreeList 的 `validCount` 是已分配/占用数，不是空闲数；回收 mask 到再次可分配有流水延迟，不假设同拍 free 立即可用。CAM 同地址多写等非法输入单列负向测试，不作为普通功能随机。

### LoadQueue 分支

| 功能组 | DUT | 必查项 |
|---|---|---|
| LSQ-VLQ | VirtualLoadQueue | numLsElem 连续区间、稀疏 lane、非 2 幂回绕、乱序完成/连续头释放、replay 不完成、redirect 多拍恢复、SQ 可接收约束 |
| LSQ-RAR | LoadQueueRAR | 何时分配、ldWbPtr 释放、release 前后拍窗口、NC/released、年轻 load 命中、partial-address/hash、1/2 拍 revoke、full 的容量预留 |
| LSQ-RAW | LoadQueueRAW | 未决老 store 分配域、地址与 mask、最老违规 load、wline、tlbMiss 屏蔽、选择流水中的 redirect/revoke、回绕 |
| LSQ-LRQ | LoadQueueReplay | 原因优先级、分配/重用、分 bank 年龄选择、ready/背压、各类 hint/wakeup、store 唤醒取消和实际 data 写入、再 replay/完成、redirect、specialMode |
| LSQ-LQU | LoadQueueUncache | 输入排序/过滤、容量不足 rollback、entry 分配/释放、mid→sid、MMIO/NC 仲裁、唤醒/数据 bypass、异常/取消 |

VLQ 的 `committed` 是 load 完成状态，不是 ROB 架构退休；ldin.ready 常真也不等于每次 ldin 都完成，还要检查 need_rep/updateAddrValid。RAR 的 lqFull 不是“零空槽”，存在双请求重放相关预留。RAW 选择延迟与配置相关，不凭印象写周期常数。Replay 当前有 13 类 cause，含提前/延迟 hint、store 取消和长驻留 specialMode；源码统计/调试位在 release SV 未必保留。

### StoreQueue 分支

| 功能组 | DUT | 必查项 |
|---|---|---|
| LSQ-VSQ | VirtualStoreQueue | numLsElem→物理区间快照、虚拟/物理容量、ROB head/退休/preCommit 差异、idle/release/walk、连续 redirect、多圈 flag |
| LSQ-DEQ | DeqModule | committed/retired 边界、cacheable→Sbuffer、MMIO/NC→Uncache、idResp/resp/writeback、CBO、跨页第二地址、drain、异常/WFI |
| LSQ-PSQ | PhysicalStoreQueue | STA/STD 先后、ready 指针/位图、issuePtr/physicalUpper、转发与出队并发、取消、旧写入不得污染复用槽 |
| LSQ-SQ | StoreQueue | VSQ/PSQ 区间、退休/preCommit/恢复/释放反馈；empty/full、forward、写出与异常一致 |

ForwardModule 必须包含历史回归 `88fb444c5`（2026-10-13）：老 store 经 VA1、较新但仍早于 load 的 store 经 VA2，二者映射同一物理地址，load 经 VA1。应按合同识别虚实 CAM 不一致并要求重放，不能把老 store 旧值当作安全完成；还需反例，晚于 load、无效槽或无字节重叠的物理命中不能错误参与判断。

## 6. 组合层验收

### L2：LoadQueue / StoreQueue

- LoadQueue：真实 VLQ 的 ldWbPtr 与 RAR/Replay 对接；RAR/RAW 容量与 replay；Uncache 唤醒、数据返回与 replay；共享 ldin/redirect 的不同流水延迟。
- StoreQueue：真实 VSQ→PSQ 的区间、preCommit、retired、redirect；PSQ→VSQ 释放反馈；转发、写出和非对齐队列并行。
- 保留子块回归，再增加独立组合不变量；不简单汇总子块覆盖率或把真实子块替换为 Python 模型。

### L3：整体 LsqWrapper

| 场景组 | 必查结果 |
|---|---|
| INT-ALLOC | 混合分配，needAlloc/numLsElem/start/end 一致；一边受限时联合 canAccept |
| INT-FWD | STA/STD 乱序就绪下正确转发或重放；别名、字节/跨页、回绕、槽位复用 |
| INT-REPLAY | SQ readiness、storeDataWrite、wake/cancel 的真实连接；满足实际释放条件才重发 |
| INT-VIOLATION | Store 地址迟到触发 RAW rollback；RAR/release 参与重执行；取消条目不误触发 |
| INT-UNCACHE | Load/Store 共用请求仲裁，pendingstate/uncacheOutstanding，idResp/resp 的 is2lq 路由不串单 |
| INT-REDIRECT | redirect 与写入/完成/请求/响应/回收同拍；恢复阻塞、恢复指针一致，旧事务不污染新条目 |
| INT-COMMIT | ROB 提交/退休、Sbuffer/Uncache 写出、dequeue 计数，路径不重复完成 |
| INT-EXCEPTION | MMIO/NC 错误、load/store 异常有效信息透传；不冒充独立 ExceptionInfoGen 的选择覆盖 |
| INT-STRESS | 合法并发、容量边界、非 2 幂多次回绕、背压、scalar/vector 元信息；活性注明公平性/超时假设 |

L3 保留 LsqWrapper 全部真实子块。外部代理模拟 dispatch/ROB、LDU/STA/STD、Cache release/refill/hint、Uncache、Sbuffer 边界，不接入 Python LoadQueue/StoreQueue 来替代硬件。LsqEnqCtrl 在 L3 后做相邻专项：先独立 UT，再验证真实端口上的 rename/dispatch 预分配与 LSQ 恢复反馈；多 DUT 连接或新 wrapper 单独评审，本轮不生成；此专项通过不等于 Backend 已验收。

## 7. 开始用例前的合同门禁

每个 DUT 需明确：

1. 唯一 key、精确 top、导出类名、父实例/参数、闭包/哈希；不模糊匹配第一个同名后缀。
2. 真实端口方向/宽度、分组、常量/优化删除字段；初始化所有真实输入，不驱动输出。
3. 分配、完成、redirect、forward、wake/hint、uncache request/idResp/response、retire/writeout 等领域事务到信号的映射。
4. valid/ready 与 Valid-only 的区别、允许的 lane 顺序、取消规则、公平性；不把随机 bit 组合当合法事务。
5. 发送/采样/检查的周期和相位；事务语义与时序适配分离，不用散落 Step(n) 修补 checker。
6. 独立环形年龄模型：LQ 非 2 幂、SQ multi-flag、ROB slot/必要的 uopIdx；不以普通整数比较替代。
7. don't-care：无 valid 的 payload、未初始化/已取消数据、源码 DontCare、当前未保留功能；不比较未定义值，不把它们标成已通过。
8. 每个功能点绑定实际观察和结果检查，具备最小定向向量、合法随机种子及产物位置。

参考语义不要复刻 RTL 位矩阵：FreeList 用独立槽位与延迟回收账本，AgeDetector 用序列年龄，业务队列用事务生命周期和字节/顺序关系。内部 memory-direct 信号只辅助定位，不能作为模型正确答案。

## 8. 分层通过标准与完成条件

运行门禁：补齐本工程工具/ABI/coverage 锁；原生 DUT 真正可导入、实例化、初始化、走时钟，不只看导出退出码。

- 子块：每个必需功能点既 reached 又 checked；定向和合法随机通过，日志/种子可复现；原生行/分支分母与缺口有说明，无点不算 100%。
- 变体：四个 FreeList 不能只测一个；UncacheEntry 共用模型但需检查全部实际 ID 的路由特化和关键边界。
- 组合：进入父块验收前完成必需下级的合同与单测；保留回归，增加真实连接检查与并发。
- 整体：INT 场景有独立证据，所有必需子块/分支通过；缺失端口或未实现能力列未覆盖，不以高行覆盖抵消。
- 产物：每次运行独立 results 目录，记录测试/功能点、种子、波形策略、RTL/导出包/工具版本和覆盖分母。

完成条件以 [Verification spec](README.md) 第 5 节为准：设计要求有合同或独立依据；对应 kind × outcome 格和交互窗口有必达激励、独立预期、真实观察点和合法对照；真实 FAIL 保留为 FAIL；覆盖分母和缺口逐项分类；当前基线重新构建、运行并保留源码/种子/构建/RTL 哈希。本文档整理不提供这些新证据，也不声称整体通过。

## 9. 历史材料与版本边界

- 逐轮进度、旧闭包/行数、2026-10-18/19 里程碑和旧 `memblock-hash/lsq/` 路径：见 [evidence/plan-progress-20261018-20261019.md](evidence/plan-progress-20261018-20261019.md)。原内容事实和稳定引用保留；旧基线 `893e1580…` 的 `LRQ-STRICT-001 仍 NOT_PASS` 是历史记录，当前处置见 [closed/LRQ-STRICT-001.md](../../bugs/closed/LRQ-STRICT-001.md)。
- 2026-11-03/06 的 `public-a0c2a26cb` 报告、2026-10-22 错误包和上游核查仍按原日期/基线保存在 [evidence/reports/](evidence/reports) 与 [bugs/evidence/](../../bugs/evidence)；不同基线的数字不能合并成一次通过率。
- 旧路径到当前位置的映射记录在 `docs/navigation.json` 的 `relocations`；冻结证据中的原命令、原路径和哈希不据此改写。
