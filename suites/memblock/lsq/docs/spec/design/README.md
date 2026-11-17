# LSQ Design Spec

状态：验证侧整理，供 DUT 事务/检查器实现和 review 使用；**未声明设计 owner 批准**。基线、源码提交和 RTL 哈希以 [`manifest/baseline.json`](../../../manifest/baseline.json) 与工程 `ucv.json` 为准。

## 1. 范围与层次

LSQ 工程覆盖 `LsqWrapper` 的真实 RTL 子树，按叶子 → 业务子块 → Load/Store 父块 → Wrapper 逐层验证。真实层次（`interaction-semantics.md` 的实例化依据）：

```text
LsqWrapper
├── LoadQueue
│   ├── VirtualLoadQueue
│   ├── LoadQueueRAR → FreeList / LqPAddrModule
│   ├── LoadQueueRAW → FreeList_1 / LqPAddrModule_1 / LqMaskModule
│   ├── LoadQueueReplay → FreeList_2 / AgeDetector_36
│   └── LoadQueueUncache → 16×UncacheEntry / FreeList_3 / 仲裁与流水
└── StoreQueue
    ├── VirtualStoreQueue
    └── PhysicalStoreQueue
        ├── ForwardModule
        ├── DeqModule → EnterSbufferQueue
        └── UnalignQueue
```

`ExceptionInfoGen` 与 `LsqEnqCtrl` 是相邻 MemBlock 子块，不属于 `LsqWrapper`；AMO/LR/SC 和 Zicbop prefetch 不分配到 LSQ，具体来源与出域结论见 [instruction-source-mapping.md](contracts/instruction-source-mapping.md)。

### 源码定义与实例化（public-a0c2a26cb）

`workspace.json` 的 `chisel` 字段按 DUT 登记真实源码路径；`ucv info lsq --dut <key>` 会解析到固定 commit 的本地路径和在线 URL。关键定义/实例化位置：

- `FreeList`：`mem/lsqueue/FreeList.scala:25` 定义；`LoadQueueRAR.scala:121`、`LoadQueueRAW.scala:119`、`LoadQueueReplay.scala:299`、`LoadQueueUncache.scala:300` 分别实例化 `FreeList`、`FreeList_1`、`FreeList_2`、`FreeList_3`。四个 top 共用同一类，后缀是生成名，不是四个不同类。
- 地址/字节 CAM：`LoadQueueData.scala:136` 定义 `LqPAddrModule`，`:210` 定义 `LqMaskModule`；`LoadQueueRAR.scala:103` 实例化 RAR 的地址 CAM，`LoadQueueRAW.scala:91`/`:103` 实例化 RAW 的地址/mask CAM。
- `AgeDetector`：`LoadQueueReplay.scala:113` 定义；`:176-187` 的 apply helper 在 `:630` 按 3 个 bank 调用，生成 `AgeDetector_36..38`。`age_replay` 用 `AgeDetector_36` 作为共享类代表，不表示只有这一个实例。
- `UncacheEntry`：`LoadQueueUncache.scala:33` 定义；`:298` 用 `Seq.tabulate(LoadUncacheBufferSize)` 以 `entryIndex` 实例化 16 个，生成 `UncacheEntry`、`UncacheEntry_1..15`。
- 业务/组合层：`LoadQueue.scala:229-233` 实例化五个 Load 子块；`LSQWrapper.scala:158-159` 实例化 LoadQueue/StoreQueue；`NewStoreQueue.scala:905,1617-1619,2185-2186` 实例化 EnterSbufferQueue、Forward/Deq/Unalign、Virtual/PhysicalStoreQueue；`MemBlock.scala:588` 实例化 LsqWrapper。

## 2. 接口与事务模型

- 分配入口为 `LsqWrapper.io.enq`；`needAlloc(1,0)` 选择 LoadQueue/StoreQueue。Load 的 `sqIdx` 在入口绑定物理 SQ 槽，形成后续依赖身份。
- 本层事务按 8 个 kind 分类：`cached`、`nc_load`、`mmio_load`、`io_load`、`store`、`nc_store`、`io_store`、`cbo`。kind 是内存属性与操作组合，不等同于指令族。
- 响应结果域单列为 `clean`、`fault`、`replay`、`tag_error`、`refill`、`tlb_miss`；逐格状态由 [`testbenches/lsq_wrapper/coverage/function_points.py`](../../../testbenches/lsq_wrapper/coverage/function_points.py) 维护。
- 跨模块边界、握手、背压/撤销、身份传播和完成条件见 [interaction-semantics.md](contracts/interaction-semantics.md)。

## 3. 合同目录

按用途分组；路径均在 [contracts/](contracts)。

| 层 | 主要合同 |
|---|---|
| 基础叶子 | [freelist](contracts/freelist.md)、[cam](contracts/cam.md)、[age](contracts/age.md)、[uncache-entry](contracts/uncache-entry.md)、[enter-sbuffer-queue](contracts/enter-sbuffer-queue.md)、[unalign-queue](contracts/unalign-queue.md) |
| Load 业务 | [virtual-load-queue](contracts/virtual-load-queue.md)、[load-queue-rar](contracts/load-queue-rar.md)、[load-queue-raw](contracts/load-queue-raw.md)、[load-queue-replay](contracts/load-queue-replay.md)、[load-queue-uncache](contracts/load-queue-uncache.md)、[load-queue](contracts/load-queue.md) |
| Store 业务 | [virtual-store-queue](contracts/virtual-store-queue.md)、[physical-store-queue](contracts/physical-store-queue.md)、[store-queue](contracts/store-queue.md)、[deq-module](contracts/deq-module.md)、[forward-module](contracts/forward-module.md) |
| 资源/数据池 | [store-payload-pool](contracts/store-payload-pool.md)、[store-prefix-byte-windows](contracts/store-prefix-byte-windows.md)、[load-response-payload-pool](contracts/load-response-payload-pool.md)、[load-raw-checkpoint-owners](contracts/load-raw-checkpoint-owners.md)、[replay-checkpoint-pool](contracts/replay-checkpoint-pool.md)、[sq-scalar-reservation-pool](contracts/sq-scalar-reservation-pool.md) |
| 组合/联合 | [lsq-wrapper](contracts/lsq-wrapper.md)、[lsq-ldu-joint-phases](contracts/lsq-ldu-joint-phases.md)、[lsq-ldu-joint-serial](contracts/lsq-ldu-joint-serial.md)、[lsq-ldu-mixed](contracts/lsq-ldu-mixed.md)、[lsq-ldu-rar-routing](contracts/lsq-ldu-rar-routing.md)、[lsq-ldu-s3-full-domain](contracts/lsq-ldu-s3-full-domain.md)、[lsq-ldu-s3-writeback](contracts/lsq-ldu-s3-writeback.md)、[lsq-ldu-s4-*](contracts) |
| 正常/CBO/恢复/性能 | [lsq-normal-cbo](contracts/lsq-normal-cbo.md)、[lsq-normal-mixed-source-jobs](contracts/lsq-normal-mixed-source-jobs.md)、[lsq-serialized-mixed](contracts/lsq-serialized-mixed.md)、[lsq-cbo-serialized](contracts/lsq-cbo-serialized.md)、[lsq-local-reset-full16](contracts/lsq-local-reset-full16.md)、[lsq-local-reset-retained-uncache](contracts/lsq-local-reset-retained-uncache.md)、[lsq-runtime-summary-performance](contracts/lsq-runtime-summary-performance.md) |
| 方法与账本 | [instruction-source-mapping](contracts/instruction-source-mapping.md)、[kind-outcome-matrix](contracts/kind-outcome-matrix.md)、[interaction-semantics](contracts/interaction-semantics.md)、[lsq-coverage-gap-schema](contracts/lsq-coverage-gap-schema.md)、[fail-review-v1](contracts/fail-review-v1.md)、[native-case-coverage-diagnosis](contracts/native-case-coverage-diagnosis.md) |

其余按模块/阶段命名的合同仍在该目录；新增 DUT 应同步更新合同、`function_points` 行和 `manifest/critical-fields.json`。

## 4. 设计确认与未确认边界

- 合同中的“状态”通常描述用例前定义或覆盖进展，不等于设计确认。历史报告明确给出的设计/ISA 依据才作为确认线索。
- **未证明**：向量首次路由是否真能以向量形式发起（`NMIX-INSTR`）；跨页 Store 第二页在 UQ 释放后的整核可见性（[IWL-UQ-SECOND-PAGE](../verification/README.md)）；`ColdDownThreshold=0` 参数域（`GAP-6688`）；AMO 与 Sbuffer 排空的 MemBlock 组合义务（`GAP-AMO-OBLIGATION`）。
- **接口边界而非正常流量**：`LQU-MMIO-IF-001`、`VSQ-REDIR-IF-001` 只证明声明的接口压力；不扩大为合法 ROB/Backend 流量可达。
- 设计行为需要变更时，应先更新合同、证据范围和受影响功能 ID，再修改 RTL 或测试；本目录不修改 RTL。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

沿用既有工程功能合同；本表补充当前源码、生成名与实际放置位置。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `freelist_rar` | `FreeList` | `src/main/scala/xiangshan/mem/lsqueue/FreeList.scala:25` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueRAR.freeList` | 已有实现；新基线未验收 |
| `freelist_raw` | `FreeList_1` | `src/main/scala/xiangshan/mem/lsqueue/FreeList.scala:25` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueRAW.freeList` | 已有实现；新基线未验收 |
| `freelist_replay` | `FreeList_2` | `src/main/scala/xiangshan/mem/lsqueue/FreeList.scala:25` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueReplay.freeList` | 已有实现；新基线未验收 |
| `freelist_uncache` | `FreeList_3` | `src/main/scala/xiangshan/mem/lsqueue/FreeList.scala:25` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.freeList` | 已有实现；新基线未验收 |
| `cam_rar` | `LqPAddrModule` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueData.scala:136` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueRAR.paddrModule` | 已有实现；新基线未验收 |
| `cam_raw` | `LqPAddrModule_1` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueData.scala:136` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueRAW.paddrModule` | 已有实现；新基线未验收 |
| `cam_mask` | `LqMaskModule` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueData.scala:210` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueRAW.maskModule` | 已有实现；新基线未验收 |
| `age_replay` | `AgeDetector_36` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala:113` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueReplay.ageOldest_age` | 已有实现；新基线未验收 |
| `virtual_load_queue` | `VirtualLoadQueue` | `src/main/scala/xiangshan/mem/lsqueue/VirtualLoadQueue.scala:35` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.virtualLoadQueue` | 已有实现；新基线未验收 |
| `load_queue_rar` | `LoadQueueRAR` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueRAR.scala:29` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueRAR` | 已有实现；新基线未验收 |
| `load_queue_raw` | `LoadQueueRAW` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueRAW.scala:32` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueRAW` | 已有实现；新基线未验收 |
| `load_queue_uncache` | `LoadQueueUncache` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:268` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer` | 已有实现；新基线未验收 |
| `load_queue_replay` | `LoadQueueReplay` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala:211` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.loadQueueReplay` | 已有实现；新基线未验收 |
| `enter_sbuffer_queue` | `EnterSbufferQueue` | `src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:749` | `XSTop.core_with_l2.core.memBlock.inner_lsq.storeQueue.physicalQueue.deqModule.dataQueue` | 已有实现；新基线未验收 |
| `unalign_queue` | `UnalignQueue` | `src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1500` | `XSTop.core_with_l2.core.memBlock.inner_lsq.storeQueue.physicalQueue.unalignQueue` | 已有实现；新基线未验收 |
| `forward_module` | `ForwardModule` | `src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:256` | `XSTop.core_with_l2.core.memBlock.inner_lsq.storeQueue.physicalQueue.forwardModule` | 已有实现；新基线未验收 |
| `virtual_store_queue` | `VirtualStoreQueue` | `src/main/scala/xiangshan/mem/lsqueue/VirtualStoreQueue.scala:43` | `XSTop.core_with_l2.core.memBlock.inner_lsq.storeQueue.virtualStoreQueue` | 已有实现；新基线未验收 |
| `deq_module` | `DeqModule` | `src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:869` | `XSTop.core_with_l2.core.memBlock.inner_lsq.storeQueue.physicalQueue.deqModule` | 已有实现；新基线未验收 |
| `physical_store_queue` | `PhysicalStoreQueue` | `src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1702` | `XSTop.core_with_l2.core.memBlock.inner_lsq.storeQueue.physicalQueue` | 已有实现；新基线未验收 |
| `store_queue` | `StoreQueue` | `src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:2198` | `XSTop.core_with_l2.core.memBlock.inner_lsq.storeQueue` | 已有实现；新基线未验收 |
| `load_queue` | `LoadQueue` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueue.scala:165` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue` | 已有实现；新基线未验收 |
| `lsq_wrapper` | `LsqWrapper` | `src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala:87` | `XSTop.core_with_l2.core.memBlock.inner_lsq` | 已有实现；新基线未验收 |
| `uncache_entry_0` | `UncacheEntry` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_0` | 已有实现；新基线未验收 |
| `uncache_entry_1` | `UncacheEntry_1` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_1` | 已有实现；新基线未验收 |
| `uncache_entry_2` | `UncacheEntry_2` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_2` | 已有实现；新基线未验收 |
| `uncache_entry_3` | `UncacheEntry_3` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_3` | 已有实现；新基线未验收 |
| `uncache_entry_4` | `UncacheEntry_4` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_4` | 已有实现；新基线未验收 |
| `uncache_entry_5` | `UncacheEntry_5` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_5` | 已有实现；新基线未验收 |
| `uncache_entry_6` | `UncacheEntry_6` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_6` | 已有实现；新基线未验收 |
| `uncache_entry_7` | `UncacheEntry_7` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_7` | 已有实现；新基线未验收 |
| `uncache_entry_8` | `UncacheEntry_8` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_8` | 已有实现；新基线未验收 |
| `uncache_entry_9` | `UncacheEntry_9` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_9` | 已有实现；新基线未验收 |
| `uncache_entry_10` | `UncacheEntry_10` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_10` | 已有实现；新基线未验收 |
| `uncache_entry_11` | `UncacheEntry_11` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_11` | 已有实现；新基线未验收 |
| `uncache_entry_12` | `UncacheEntry_12` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_12` | 已有实现；新基线未验收 |
| `uncache_entry_13` | `UncacheEntry_13` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_13` | 已有实现；新基线未验收 |
| `uncache_entry_14` | `UncacheEntry_14` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_14` | 已有实现；新基线未验收 |
| `uncache_entry_15` | `UncacheEntry_15` | `src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:34` | `XSTop.core_with_l2.core.memBlock.inner_lsq.loadQueue.uncacheBuffer.entries_15` | 已有实现；新基线未验收 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
