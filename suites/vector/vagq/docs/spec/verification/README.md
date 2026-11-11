# VAGQ Verification spec

状态：**现有验证资产的统一入口，完整性待审查**。本页是 12 个 DUT 的**共享逐 DUT
验证资料入口**：`workspace.json` 对每个 VAGQ DUT 的 `verification_spec` 都指向本页，
§2.1 按 DUT 链接已有公开参考模型、模型/协议测试和独立预期依据。这些链接指向验证实现与
测试，**不能代替设计依据**；设计要求见 [Design spec](../design/README.md)，架构语义仍以
RVV/ISA 与公开协议为准。VAGQ 适用 internal `d4566d58a5ace1f6a5df4409b37a84b971f48e43`；
与公开 `public-*` 工程使用不同基线，混合基线运行会被统一基线检查拒绝。

历史记录：`results/ucv-vagq-20261031`，**433 PASS / 1 FAIL / 33 SKIP**，保留其日期与范围。
2026-11-10 事务适配独立验收覆盖 10 个受影响 DUT 的当前构建/冒烟；最后调用修复定向
**48 PASS / 1 SKIP**，`hardware_verdict=INCOMPLETE`。此前冻结原 463 项判定一致，
既有 MaskGen 失败、8 项缺外部历史文件和 SKIP 均不因本轮修复豁免；没有最终全 476 项
统一回归。完整过程在 `results/transaction-adapters-20261110/vagq/`。当前状态以根
[docs/status.md](../../../../../../docs/status.md) 为准。

## 1. 验证范围与假设

- 验证 12 个实际 DUT：VAGQ 顶层、EntryTable、Manager、Arbiter、AddrGen、MaskGen、
  SplitCtrl、MergeCtrl、StoreDataCtrl、OrderedPermitCtrl 和两个 pipeline。
- 三层证据分开：纯参考模型/ISA 参考、真实 native DUT、公开边界外部环境/虚拟系统。
  纯模型测试证明语义和检查器灵敏度，不自动计为硬件 ISA 通过。
- 顶层只通过公开 `AddrPacket/DataPacket/Beat` 边界驱动；不复制 internal 源码、生成
  产物或包含 internal 源码的证据到公共仓库。
- 独立期望来自 RVV v1.0 架构参考、公开协议、场景矩阵和组件参考模型；不把 DUT 输出
  或生成 RTL 查表当作架构期望。
- 现有 FAIL/SKIP 保持原判定；显式 campaign 的 SKIP 不当作通过，也不为了全绿删除。
- 普通回归不等于完整 exhaustive campaign；生产 decoder 的合法域和 standalone 注入
  能力需要分别说明。

## 2. 验证层与测试入口

### 2.1 DUT 与本地入口

| DUT | 独立参考/模型 | 公开边界测试 | 备注 |
|---|---|---|---|
| `VAGQ` | [testbenches/vagq/model.py](../../../testbenches/vagq/model.py)、[testbenches/vagq/env/isa_reference.py](../../../testbenches/vagq/env/isa_reference.py) | [testbenches/vagq/tests](../../../testbenches/vagq/tests) | 顶层 public `AddrPacket/DataPacket/Beat` 边界 |
| `VAGQEntryTable` | [testbenches/entrytable/model.py](../../../testbenches/entrytable/model.py) | [testbenches/entrytable/tests](../../../testbenches/entrytable/tests) | 8 项生命周期与 flush/exception |
| `VAGQManager` | [testbenches/manager/model.py](../../../testbenches/manager/model.py)、[testbenches/manager/env/cases.py](../../../testbenches/manager/env/cases.py) | [testbenches/manager/tests](../../../testbenches/manager/tests) | 环形分配与 release/recovery |
| `VAGQArbiter` | [testbenches/arbiter/model.py](../../../testbenches/arbiter/model.py)、[testbenches/arbiter/env/schema.py](../../../testbenches/arbiter/env/schema.py) | [testbenches/arbiter/tests](../../../testbenches/arbiter/tests) | 最老优先、native 共发和 lane 选择 |
| `AddrGen` | [testbenches/addrgen/env/reference.py](../../../testbenches/addrgen/env/reference.py) | [testbenches/addrgen/tests](../../../testbenches/addrgen/tests) | strided/indexed 地址生成与回绕 |
| `MaskGen` | [testbenches/maskgen/env/reference.py](../../../testbenches/maskgen/env/reference.py)、[testbenches/maskgen/env/architectural.py](../../../testbenches/maskgen/env/architectural.py) | [testbenches/maskgen/tests](../../../testbenches/maskgen/tests) | element window、active/masked/tail |
| `SplitCtrl` | [testbenches/split/model.py](../../../testbenches/split/model.py) | [testbenches/split/tests](../../../testbenches/split/tests) | 三 lane 拆分、fault/redirect |
| `MergeCtrl` | [testbenches/merge/model.py](../../../testbenches/merge/model.py) | [testbenches/merge/tests](../../../testbenches/merge/tests) | old vd 合并、ack/nack/exception |
| `StoreDataCtrl` | [testbenches/storedata/model.py](../../../testbenches/storedata/model.py) | [testbenches/storedata/tests](../../../testbenches/storedata/tests) | 两槽 store data、SQ 偏移、EEW |
| `OrderedPermitCtrl` | [testbenches/ordered/model.py](../../../testbenches/ordered/model.py) | [testbenches/ordered/tests](../../../testbenches/ordered/tests) | per-entry permit 与 handoff |
| `NewPipelineConnectPipe` | [testbenches/pipeline/model.py](../../../testbenches/pipeline/model.py)、[testbenches/pipeline/env/specs.py](../../../testbenches/pipeline/env/specs.py)（`PIPE1`） | [testbenches/pipeline/tests](../../../testbenches/pipeline/tests) | 完整 LSU metadata payload |
| `NewPipelineConnectPipe_3` | [testbenches/pipeline/model.py](../../../testbenches/pipeline/model.py)、[testbenches/pipeline/env/specs.py](../../../testbenches/pipeline/env/specs.py)（`PIPE3`） | [testbenches/pipeline/tests](../../../testbenches/pipeline/tests) | 紧凑 `issueMask` payload；生成名映射见 Design spec |

命名形如 `testbenches/<dut>/tests/test_model.py`、`test_reference.py`、`test_encoding.py` 的文件
承载纯模型/参考检查；`testbenches/<dut>/tests/testcase/` 承载真实 native DUT 协议。模型 PASS 不
自动计为硬件 ISA 通过，native 组件 PASS 不自动证明顶层组合或生产译码可达。

### 2.2 验证层

| 层 | 内容 | 入口 |
|---|---|---|
| 纯模型/参考 | AddrGen、MaskGen、Arbiter、EntryTable、Merge、Ordered、Pipeline、Split、StoreData、Manager 的生命周期和优先级 | `testbenches/<dut>/tests/test_model.py`、`testbenches/<dut>/tests/test_reference.py`、`testbenches/<dut>/tests/test_encoding.py` |
| 真实 native DUT | 各组件和顶层的公开端口协议、背压、异常、redirect、响应/写回 | `testbenches/<dut>/tests/testcase/`、[testbenches/vagq/tests/test_protocol.py](../../../testbenches/vagq/tests/test_protocol.py) |
| 外部环境 | 用 VRF/SQ/ROB/LSQ 代理驱动真实顶层，覆盖 latency、NAK、hold、fault、redirect 和八入口压力 | [testbenches/vagq/tests/test_external_environment.py](../../../testbenches/vagq/tests/test_external_environment.py)、[testbenches/vagq/env/external_env.py](../../../testbenches/vagq/env/external_env.py) |
| 虚拟系统 | 纯事件调度、LSQ/VRF/SQ/ROB 交互和覆盖，不加载 native DUT | [testbenches/vagq/tests/test_virtual_system.py](../../../testbenches/vagq/tests/test_virtual_system.py)、[testbenches/vagq/env/virtual_system.py](../../../testbenches/vagq/env/virtual_system.py) |
| RVV ISA audit | 架构 element/window/ordering 与 DUT 边界对照；边界样本与 public-DUT 覆盖分开 | [testbenches/vagq/tests/test_isa_audit.py](../../../testbenches/vagq/tests/test_isa_audit.py)、[test_isa_boundary.py](../../../testbenches/vagq/tests/test_isa_boundary.py)、[test_isa_dut_matrix.py](../../../testbenches/vagq/tests/test_isa_dut_matrix.py)、[test_isa_reference.py](../../../testbenches/vagq/tests/test_isa_reference.py) |
| 覆盖/结构 | 场景矩阵、结构 sweep、显式 exhaustive shape 和 sparse canary | [testbenches/vagq/tests/test_scenario_matrix.py](../../../testbenches/vagq/tests/test_scenario_matrix.py)、[test_structural_coverage.py](../../../testbenches/vagq/tests/test_structural_coverage.py)、[test_isa_exhaustive_shape.py](../../../testbenches/vagq/tests/test_isa_exhaustive_shape.py)、[test_sparse_segment_canary.py](../../../testbenches/vagq/tests/test_sparse_segment_canary.py) |

公共边界包和驱动/模型/检查器见 [testbenches/vagq/transactions/__init__.py](../../../testbenches/vagq/transactions/__init__.py)、
[testbenches/vagq/env/driver.py](../../../testbenches/vagq/env/driver.py)、[testbenches/vagq/model.py](../../../testbenches/vagq/model.py)、
[testbenches/vagq/checker.py](../../../testbenches/vagq/checker.py)、[testbenches/vagq/env/probe.py](../../../testbenches/vagq/env/probe.py)。
组件环境由 [conftest.py](../../../conftest.py) 注册。

### 2.3 事务边界与观察 API

顶层与组件功能用例只提交不可变的 `AddrPacket`/`DataPacket`/`Beat`，并断言
`Observation`、`AdmissionStatus` 等唯一归属的不可变快照。`Observation` 由
[probe.decode](../../../testbenches/vagq/env/probe.py) 在绑定点把公开端口一次解码为
load/store/empty/VRF/STD/writeback/wakeup 事务。生成 schema 登记的必需 leaf 必须实际
出现在样本中，缺失即报错；只有 schema 明确裁剪的 leaf（例如 STA payload 无公开 PC/
vecWen）按 `PRUNED_OUTPUT_REASONS` 返回有依据的常量 0，不把“缺观察”当裁剪。

`response_beat(observation)` 的 ACK 需要同拍证据：payload 有效（LSU/STA 还需 metadata
valid）且目标 ready 为真。快照的 ready 证据是三态：`None` 表示未采样到该拍握手；元组
（包括全 False）表示确知该拍握手。显式传入的同一拍 `beat` 与快照携带的证据都是正证据，
二者冲突时抛错拒绝，不能用参数覆盖已采样值；只有单一来源时按该来源；两者都无时按全
False 处理。因此缺少握手证据只会产生零 ACK，已知背压也不会被默认 ready 覆盖。
`base` 只提供下一拍输入，不替代本拍握手；`base` 中放宽的 ready 永远不会为当前采样拍
制造 ACK。需要“先阻塞、下一拍释放”的场景必须把本拍 `beat` 作为握手证据、把释放后的
ready 放进 `base`，例如测试侧 `_responses_for_ready(outputs, current_beat,
next_beat=...)`：ACK 只依据 `current_beat`，`next_beat` 仅决定下一拍输入。把下一拍的
release ready 当作本拍 `beat` 传入会与快照携带的当前证据冲突并被拒绝；不得删除携带
证据或吞掉该错误来绕过。功能用例不再读取端口字典、`.driver`、`.sample`、`.model` 或
`.checker`；纯模型自检仍可直接检查自身内部账本（见下方 selftest 分类）。

- `Env.cycle(beat, admit=...)` 是时钟化顶层的事务周期；`Env.present(beat)` 用于只观察
  公开请求/回应的独立审计探针，不代测试确认请求。两者返回的 `Observation.cycle` 是
  本次采样序号：`reset()` 归零后每次观察递增一次；直接操作 driver 的路径不属于该观察
  边界，不伪造序号。native 推进/相位未改变。
- `Observation` 将调用方的请求/回应序列复制成 tuple，并校验固定 lane 形状与
  load/store 身份；`AdmissionStatus` 的发射集合为 frozenset，调用方无法通过修改传入
  列表改写快照。
- `Env.observation_only()` 明确关闭集成模型比较并保留独立 oracle 的断言；它不是把
  功能用例标为自检。`Env.admission_status(entry)` 返回只读完成/发射账本。
  `Env.restart_entry(entry)` 只接受该 attempt 已实际观察到 exception writeback 的情形；
  写回还必须与当前 admitted addr 的 entry、ROB flag/value、uopIdx 身份一致，错身份
  写回明确抛错且不归给当前 plan；提前 restart、重复 restart、重复完成、以及把成功写回
  伪装成异常都会被拒绝。原 vstart 异常重启场景以真实异常写回为前提继续合法。
- Arbiter 的“native load/store 旁路 + ROB 身份 + 确定性 payload pattern”由
  [arbiter/env/native.py](../../../testbenches/arbiter/env/native.py) 构造不透明请求：
  功能用例只选择 load/store、valid、ROB flag/value 与 pattern seed；生成字段枚举、
  逐 leaf 位宽掩码和物理 ROB 编码留在适配层，不返回 live schema/ports。
- 波形读取的物理 leaf 映射集中在
  [env/waveform.py](../../../testbenches/vagq/env/waveform.py)；Arbiter 生成 payload
  leaf/宽度由 [env/schema.py](../../../testbenches/arbiter/env/schema.py) 提供。
- 纯编码/模型/checker 自检保留物理字段断言时显式标记 `selftest`：
  `pipeline/tests/test_encoding.py`、`arbiter/tests/test_model.py`、`vagq/tests/test_model.py`。
  它们不贡献硬件功能 credit。编码自检使用独立物理期望常量（`P.p_in_bits_pc` 等），
  不从被测 `Spec.fields` 推导期望，交换 pc/vaddr wire 时必须失败。
- 结构随机扫描的引脚级机制集中在
  [shared/env/structural.py](../../../testbenches/shared/env/structural.py)，测试只保留
  DUT 选择、seed 和周期参数；使用随机引脚扫描的 9 个参数显式标记 `selftest`。VAGQ、
  EntryTable、OrderedPermitCtrl 的合法生命周期扫描仍走各自公开 env，并保持非自检分类。
- 组件环境提供 `assert_clean()`/`assert_coverage()`（Manager 另有 `checked_cycles`、
  `checked_count`、`override_comparison()`），功能用例不再直接查询 checker 内部状态。

## 3. 场景矩阵与覆盖计划

- [scenario_matrix.py](../../../testbenches/vagq/env/scenario_matrix.py) 用 RVV/public-boundary 术语生成
  合法公开特征空间：**8352** 个 case；测试确认每个 case 的 operation、vsew、vlmul、
  data/index eew、nf 和 uop_count 唯一。
- 代表执行集：**80** 个 pairwise covering case；覆盖 **742/742** pairwise token 和
  **700/700** pairwise cross。该集合是执行计划，不是“所有合法 shape 都已在整芯片
  运行”的声明。
- fault generator 对每个 shape 覆盖每个架构 element 的 fault position（`vlmax` 范围），
  并保留 `1 <= uop_count <= 8` 的生产者 uop 约束。
- [testbenches/vagq/tests/test_structural_coverage.py](../../../testbenches/vagq/tests/test_structural_coverage.py) 对 12 个 DUT 做确定性 public-leaf sweep；
  [test_isa_exhaustive_shape.py](../../../testbenches/vagq/tests/test_isa_exhaustive_shape.py) 只在 `RUN_VAGQ_EXHAUSTIVE=1` 时运行完整 shape 序列。
- ISA audit 覆盖组 `vagq.rvv_isa_audit_v1` 把 operation、LMUL、data/index EEW、element
  window、segment MOP、地址边界、ordering、restart protocol 和 audit outcome 分开；
  `boundary` 实例记录 unit-stride 等 VAGQ 根之外或不可观察的语义，不贡献 public-DUT
  覆盖。

## 4. 当前未关闭项与已知边界

- [VAGQ-MASKGEN-ELEMENT-WINDOW-56](../../bugs/open/VAGQ-MASKGEN-ELEMENT-WINDOW-56.md)：
  当前记录的 1 FAIL；`test_segment_element_windows_and_policies` 报告 56/9024 native
  policy mismatch（`elemActiveMask` 与独立窗口模型不一致）。未登记 XFAIL，根因待确认。
- [VAGQ-SPARSE-SEGMENT-MASK-CANARY](../../bugs/open/VAGQ-SPARSE-SEGMENT-MASK-CANARY.md)：
  显式 sparse-segment canary 默认 SKIP；外部复盘记录未解决的 RTL 反例，本次未重新执行，
  不复制 internal 证据。
- 两个 hard skip 保留为未验证义务，不计入 433 PASS：
  `test_ordered_store_final_memory_effects_follow_element_order` 需要真实
  SQ/Sbuffer/DCache 或 Uncache 的内存效果，standalone root 只暴露地址请求；
  `test_wide_segment_production_path_covers_each_architectural_memory_byte` 需要生产
  DecodeStage 的 nf>0 路径，当前生产译码只启用 nf=0。强制端口的观测不能替代这些
  集成义务。
- 生产 decoder 是否产生 segment uop 的边界见 `manifest/source-contract.json` 与 Design
  spec；standalone 注入能力不等于生产可达性。
- 未纳入普通回归的显式 campaign（exhaustive、failure review、boundary assessment、
  NF0 focus、reference-qualified RTL review 等）保留各自开关、fresh evidence 目录和
  原判定；不能用普通 PASS 数替代。外部历史证据工作区未接入时，依赖 `history://` 的
  failure-review 校验按环境失败处理，不改写成产品判定。
- **native 身份边界**：12 个 DUT 的既有 artifact/receipt 与同一 internal
  `d4566d58a` 基线一致，旧 receipt 哈希复核通过；但其 cache_key 来自旧算法/旧
  `recipe.tests`，按当前配方（`pipeline_version=2`，含增强 RTL 来源校验）重算不相等。
  这些旧 artifact 只能作为同基线对账证据，不能表述为“当前构建链已验证”。
- 主 agent 的官方当前构建收据
  `independent-current-native-identity.json` 覆盖 10 个 DUT（VAGQ、VAGQArbiter、
  VAGQManager、VAGQEntryTable、OrderedPermitCtrl、SplitCtrl、MergeCtrl、
  StoreDataCtrl、NewPipelineConnectPipe、NewPipelineConnectPipe_3）：current key 与
   active/recorded 一致、smoke PASS、RTL 与旧 artifact 逐字节相同；native 经过真实重建，
   文件身份不同（未单独归因，不能仅凭哈希变化声称工具版本不同）。该收据属于主 agent 的独立构建证据，本工程只引用、未运行
  或修改；AddrGen/MaskGen 不在该 current-key 列表中，仍只有旧 artifact 对账。
- 不得手改 receipt、缓存或激活旧基线；历史收据保持原字节，修补使用新收据名。
- internal 源码、生成 RTL/native 包和包含 internal 源码的证据保持外部接入；本仓库
  只保留可公开的验证代码、清单和结论引用。

## 5. 完成条件

- 当前 internal 基线的 prepare/build/smoke 与所选运行有可核验收据；结果和覆盖按
  DUT/口径分开，不跨基线拼接。
- 1 FAIL 完成根因判定和修复/反例处置；sparse canary 和外部反例有可复核结论。
- 场景矩阵、独立参考、检查器灵敏度和 explicit campaign 的边界均有登记；SKIP 不冒充
  PASS。
- 生产 decoder 合法域、standalone 注入边界和未观察内部语义明确写入 Design spec。
- 全绿不是目标；真实 FAIL、SKIP 和未验证范围必须保留。

## 6. 外部证据入口

本工程不设泛化 history 目录。历史复盘通过根
[经验索引 VAGQ 外部证据](../../../../../../docs/lessons/README.md#vagq-external-evidence)
访问，文件保持外部接入；索引中的 SHA-256/大小/可用性由根历史证据分片记录。证据使用
说明见 [evidence/README.md](evidence/README.md)。
