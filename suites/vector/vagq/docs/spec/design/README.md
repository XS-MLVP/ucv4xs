# VAGQ Design spec

状态：**整理入口，设计确认待完成**。本页是 12 个 DUT 的**共享逐 DUT 资料入口**；
`workspace.json` 对每个 VAGQ DUT 的 `design_spec` 都指向本页，下表按 DUT 分别给出已有
公开参考模型、验证入口和 internal 源码相对位置。这些代码/测试入口用于定位当前验证依据，
**代码实现不能代替独立设计依据**；设计语义仍以 RVV/ISA、协议合同和仍未签核的设计要求
为准。本页没有把 internal 源码、生成产物或包含 internal 源码的证据复制进公共仓库。
逐 DUT 设计 owner 的确认记录不在本检出中，因此本页描述的是当前验证依据，不等同已签核的
微架构规格。

适用基线：VAGQ 通过本地来源接入 internal `d4566d58a5ace1f6a5df4409b37a84b971f48e43`，
与当前 11 个公开工程的 `public-*` 基线不同。实际源码、RTL 和构建身份以 `ucv info vagq`、
`manifest/source-contract.json` 和运行收据为准。

## 1. 范围与层次

本工程包含 VAGQ 顶层和 11 个独立 DUT。顶层把地址、掩码、拆分、合并、存储数据、
顺序许可、入口表、管理和仲裁组合到 VAGQIO 公共边界；组件 UT 只覆盖各自接口，不能
替代顶层组合或生产译码环境。

| DUT 键 | 顶层 | 当前可归纳的职责 | 公开参考模型 / 测试入口 |
|---|---|---|---|
| `VAGQ` | VAGQ | 顶层公共边界、请求/响应、VRF/SQ/ROB 生命周期 | [testbenches/vagq/model.py](../../../testbenches/vagq/model.py)、[testbenches/vagq/env/__init__.py](../../../testbenches/vagq/env/__init__.py)、[testbenches/vagq/tests](../../../testbenches/vagq/tests) |
| `VAGQEntryTable` | VAGQEntryTable | 8 项入口生命周期（WAIT_A/WAIT_SI/SPLIT/MERGE/WB）、flush/exception | [testbenches/entrytable/model.py](../../../testbenches/entrytable/model.py)、[testbenches/entrytable/tests](../../../testbenches/entrytable/tests) |
| `VAGQManager` | VAGQManager | 8 槽环形分配、release/recovery/walk 和占用更新 | [testbenches/manager/model.py](../../../testbenches/manager/model.py)、[testbenches/manager/env/cases.py](../../../testbenches/manager/env/cases.py)、[testbenches/manager/tests](../../../testbenches/manager/tests) |
| `VAGQArbiter` | VAGQArbiter | load/store 最老优先仲裁、native 共发和 lane 选择 | [testbenches/arbiter/model.py](../../../testbenches/arbiter/model.py)、[testbenches/arbiter/env/schema.py](../../../testbenches/arbiter/env/schema.py)、[testbenches/arbiter/tests](../../../testbenches/arbiter/tests) |
| `AddrGen` | AddrGen | strided/indexed 地址生成、64-bit 回绕和 element/offset 选择 | [testbenches/addrgen/env/reference.py](../../../testbenches/addrgen/env/reference.py)、[testbenches/addrgen/tests](../../../testbenches/addrgen/tests) |
| `MaskGen` | MaskGen | destination element window、active/masked/tail、merge/agnostic 掩码 | [testbenches/maskgen/env/reference.py](../../../testbenches/maskgen/env/reference.py)、[testbenches/maskgen/env/architectural.py](../../../testbenches/maskgen/env/architectural.py)、[testbenches/maskgen/tests](../../../testbenches/maskgen/tests) |
| `SplitCtrl` | SplitCtrl | active/empty pending mask、三 lane 拆分、staged request 和 fault lane 取消 | [testbenches/split/model.py](../../../testbenches/split/model.py)、[testbenches/split/tests](../../../testbenches/split/tests) |
| `MergeCtrl` | MergeCtrl | merge-read、旧 vd 合并、response/ack/nack/exception 和 writeback | [testbenches/merge/model.py](../../../testbenches/merge/model.py)、[testbenches/merge/tests](../../../testbenches/merge/tests) |
| `StoreDataCtrl` | StoreDataCtrl | 两槽 store data、VRF 读、SQ 起始偏移和 EEW 重复 | [testbenches/storedata/model.py](../../../testbenches/storedata/model.py)、[testbenches/storedata/tests](../../../testbenches/storedata/tests) |
| `OrderedPermitCtrl` | OrderedPermitCtrl | ordered load 的 per-entry permit、handoff 和 redirect 清理 | [testbenches/ordered/model.py](../../../testbenches/ordered/model.py)、[testbenches/ordered/tests](../../../testbenches/ordered/tests) |
| `NewPipelineConnectPipe` | NewPipelineConnectPipe | 单槽 decoupled 流水，承载完整 LSU metadata | [testbenches/pipeline/model.py](../../../testbenches/pipeline/model.py)、[testbenches/pipeline/env/specs.py](../../../testbenches/pipeline/env/specs.py)、[testbenches/pipeline/tests](../../../testbenches/pipeline/tests) |
| `NewPipelineConnectPipe_3` | NewPipelineConnectPipe_3 | 单槽 decoupled 流水，承载紧凑 issueMask payload | [testbenches/pipeline/model.py](../../../testbenches/pipeline/model.py)、[testbenches/pipeline/env/specs.py](../../../testbenches/pipeline/env/specs.py)、[testbenches/pipeline/tests](../../../testbenches/pipeline/tests) |

源码路径和导出名由 [ucv.json](../../../ucv.json) 与 `ucv info vagq` 提供；internal
源码检出是外部接入的忽略目录，不在 Git 中。

### 源码定位（internal 外部接入）

以下路径相对于有效 internal 基线源码根。`ucv info vagq --dut <key>` 只展开该有效
baseline 对应的 `.cache/sources/<source_key>` 路径并显示是否存在；该检出由
`ucv prepare vagq --source-only` 按 `.ucv/local.json` 的 `source_mirrors` 接入，`info`
本身不读取 mirror。若尚未 prepare，`info` 会显示路径尚未准备。本页只登记位置，不复制
internal 源码、生成 RTL 或实现细节。

| DUT 键 | Scala 定义 | 实例化/组织来源 |
|---|---|---|
| `AddrGen` | `src/main/scala/xiangshan/backend/vector/vagq/AddrGen.scala` | `SplitCtrl.scala`（active lane 地址生成） |
| `MaskGen` | `src/main/scala/xiangshan/backend/vector/vagq/MaskGen.scala` | `EntryTable.scala`（addr 输入侧 mask 生成） |
| `MergeCtrl` | `src/main/scala/xiangshan/backend/vector/vagq/MergeCtrl.scala` | `Vagq.scala` |
| `NewPipelineConnectPipe` | `src/main/scala/xiangshan/backend/datapath/NewPipelineConnect.scala` | `Vagq.scala` 的 `connectRedirectPipe`（完整 LSU metadata payload） |
| `NewPipelineConnectPipe_3` | 同上（同一泛型类的第二份 payload 特化） | 同上；生成名 `_3` 对应紧凑 `issueMask` payload，不是独立 Scala 类 |
| `OrderedPermitCtrl` | `src/main/scala/xiangshan/backend/vector/vagq/OrderedPermitCtrl.scala` | `Vagq.scala` |
| `SplitCtrl` | `src/main/scala/xiangshan/backend/vector/vagq/SplitCtrl.scala` | `Vagq.scala` |
| `StoreDataCtrl` | `src/main/scala/xiangshan/backend/vector/vagq/StoreDataCtrl.scala` | `Vagq.scala` |
| `VAGQ` | `src/main/scala/xiangshan/backend/vector/vagq/Vagq.scala` | `Backend.scala`（整核）；同文件的 `VAGQMain` 只用于 standalone 生成 |
| `VAGQArbiter` | `src/main/scala/xiangshan/backend/vector/vagq/VAGQArbiter.scala` | `Vagq.scala` |
| `VAGQEntryTable` | `src/main/scala/xiangshan/backend/vector/vagq/EntryTable.scala` | `Vagq.scala` |
| `VAGQManager` | `src/main/scala/xiangshan/backend/vector/vagq/VAGQManager.scala` | `VecOrderQueue.scala`（不由 VAGQ 顶层实例化） |

`NewPipelineConnectPipe` 与 `NewPipelineConnectPipe_3` 的生成名来自同一 Chisel 类在
不同 payload 类型上的两次特化；Python 侧分别在 `testbenches/pipeline/env/specs.py` 以 `PIPE1`/`PIPE3`
绑定端口，不能用同名类猜测 `_3` 的实现。

## 2. 公共接口与合法输入

[testbenches/vagq/transactions/__init__.py](../../../testbenches/vagq/transactions/__init__.py) 定义对外可读的包：

- `AddrPacket`：入口索引、uop 类型、ROB/LQ/SQ/FTQ 身份、基址、v0 字节掩码、deew/ieew/
  emul、vl/vstart/vma/vta、nf、vsew/vlmul 等。
- `DataPacket`：入口/ROB 身份和 `op2_data`；索引或 store 数据由数据包送入。
- `Beat`/`Response`/`EmptyResponse`/`VrfResponse`/`Redirect`：公共请求、响应、
  empty marker、VRF 读写和重定向。
- `FLOW_BYTES = 16`、`VAGQ_SIZE = 8`：公开数据流宽度和入口数量。

设计要求按以下层次拆分：

1. **架构语义**：RVV v1.0 的 element/segment、地址、mask/tail/agnostic 和有序约束
   由 [testbenches/vagq/env/isa_reference.py](../../../testbenches/vagq/env/isa_reference.py) 独立表达；它不导入 MaskGen/AddrGen 参考或 Chisel 派生表。
2. **组件合同**：各 DUT 的 `model.py`/`reference.py` 用公开输入输出描述生命周期、
   优先级、掩码和握手；不复制生成 RTL 的状态机。
3. **集成边界**：顶层的 `IntegrationModel` 只跟踪 VAGQIO 可见的 lifecycle；不把内部
   entry-table/child RTL 状态当成公共合同。

## 3. 行为要求与确认状态

当前可追溯到的最强行为来源是各 DUT 的纯参考模型、公开边界测试和 ISA audit。它们已经
覆盖：

- strided/indexed load/store 的地址生成、indexed 零扩展、负/零/正 stride 和 64-bit 回绕；
- LMUL/EMUL、VLMAX、vstart、v0 active mask、vma/vta、segment nf 和 fractional LMUL；
- split 的三条 active lane、两条 empty lane、ordered load 单 lane、backpressure 和 fault；
- merge 的旧 vd 读、agnostic 字节、write mask、ack/nack/exception 和 stale entry；
- store data 的两槽、SQ 起始偏移、EEW 重复和 redirect 后不复活；
- ordered permit 的 ROB/uop 精确身份、中间完成 handoff、redirect 前后年龄判断；
- entry table 的 address/data 分离到达、同拍到达、bitmap store exception、flush；
- manager 的环形分配、释放不越过同沿分配、walk 不分配、redirect 覆盖其它更新；
- arbiter 的 queue pointer + lane tie、native/VAGQ 共发、std busy 和 ready 独立性；
- pipeline 的 empty/full、backpressure、同拍 fire/flush 和 payload 位宽；
- 顶层 WFI/EMPTY marker、NAK 重试、precise load fault、redirect、八入口压力和
  ordered store 的 SQ 串行化。

**未确认的设计要求**：

- 各 DUT 设计 owner 对上述行为的逐条确认和优先级定义，尤其是握手/背压时序是否属于
  架构合同还是实现选择。
- `manifest/source-contract.json` 已记录的生产译码边界：生产 decoder 将 segment uops
  排除在 VAGQ 之外，直接 standalone 注入仍然可能。该结论来自既有 source audit，
  未在本次整理中重新运行 decoder 仿真；不能把它外推为所有 VAGQ 输入形态的生产可达性。
- internal 源码里的 MOP/entry 布局、native 时序和未公开内部状态不能在公共仓库中复述；
  需要核对时必须通过外部接入和独立签核，不能把验证模型当成设计规格。
- `NewPipelineConnectPipe` 与 `_3` 的字段映射是 native binding 合同，不等同完整流水
  时序规格。

## 4. 依据与待确认问题

- [VAGQ 验证工程](../../../README.md) 和 [Verification spec](../verification/README.md)
  给出当前测试、覆盖和证据边界。
- [manifest/source-contract.json](../../../manifest/source-contract.json) 记录源码/RTL 文件哈希、生产 decoder 范围和迁移说明；
  它不包含 internal 源码正文。
- 根 [经验索引](../../../../../../docs/lessons/README.md#vagq-external-evidence) 指向外部
  复盘文件；这些文件保持外部接入，不在本工程复制。
- 待确认：设计 owner、生产 decoder 对各类 segment 的精确合法域、顶层与组件行为要求的
  逐条确认、以及 internal 时序约束的外部 review 结论。
- 设计要求变更使用 Git review；新增要求分配稳定 ID，并在验证规格中登记场景与证据。
