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
