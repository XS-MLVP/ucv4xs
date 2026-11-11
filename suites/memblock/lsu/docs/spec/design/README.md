# LSU Design Spec

状态：验证侧整理，依据生成 RTL 的真实实例化层次和固定源码；**未声明设计 owner 批准**。基线、RTL 哈希和工具链见 [`manifest/baseline.json`](../../../manifest/baseline.json)、[`manifest/toolchain.json`](../../../manifest/toolchain.json)。

## 1. 范围

本工程只验证 XiangShan `NewStoreUnit`、`NewLoadUnit`、`StdExeUnit` 三个模块族的独立 UT 和族内真实子模块组合；不包含 AtomicsUnit、跨族联合 harness、LSU/MemBlock 顶层或整核集成。外部 LSQ、DCache/Uncache、TLB、PMP、Sbuffer、Backend/ROB 由协议代理提供，代理行为不作为对应子系统已验证的证据。

## 2. 真实层次

```text
NewStoreUnit
├── StoreUnitS0 → Arbiter3_StoreStageIO
├── StoreUnitS1 → MemTrigger_3
├── StoreUnitS2
├── StoreUnitS3 → DelayPipeline
├── StoreUnitS4
└── NewStoreUnit

NewLoadUnit
├── LoadUnitS0 → Arbiter7_LoadStageIO
├── LoadUnitS1 → MemTrigger
├── LoadUnitS2
├── LoadUnitS3
├── LoadUnitS4
├── LoadUnitDataPath
└── NewLoadUnit

StdExeUnit（无内部子模块）
```

父块 DUT 保留真实下级 RTL；不能用 Python 模型替换子模块后宣称硬件组合通过。

### 源码定义与实例化（public-a0c2a26cb）

`workspace.json` 的 `chisel` 字段按 DUT 登记真实源码路径；`ucv info lsu --dut <key>` 解析固定 commit 的本地路径和在线 URL。关键定义/实例化位置：

- `NewStoreUnit.scala`：`StoreUnitS0`…`StoreUnitS4` 定义在 `:38`/`:255`/`:547`/`:710`/`:837`，`NewStoreUnit` 在 `:891`，`DelayPipeline` 在 `:950`；父块在 `:894-898` 实例化五级流水，`:780` 实例化 `DelayPipeline`，`MemBlock.scala:513` 实例化 `NewStoreUnit`。
- `NewLoadUnit.scala`：`LoadUnitS0`…`LoadUnitS4` 定义在 `:43`/`:498`/`:804`/`:1291`/`:1874`，`LoadUnitDataPath` 在 `:1896`，`NewLoadUnit` 在 `:2063`；父块在 `:2066-2070` 实例化五级流水，`MemBlock.scala:512` 实例化 `NewLoadUnit`。
- `StdExeUnit.scala:44` 定义，`MemBlock.scala:514` 实例化。
- `MemTrigger`：`backend/fu/NewCSR/Debug.scala:301` 定义；`NewStoreUnit.scala:355` 实例化 `MemTrigger_3`，`NewLoadUnit.scala:629` 实例化 `MemTrigger`。
- `Arbiter3_StoreStageIO`/`Arbiter7_LoadStageIO`：模块体来自 Chisel `chisel3.util.Arbiter`（不在本基线源码树内）；实际连接由 `mem/MemBlock.scala:85-96` 的 `arbiter` helper 建立，分别由 `NewStoreUnit.scala:126`、`NewLoadUnit.scala:223` 调用。`workspace.json` 因此登记 helper 与调用者，而不是猜一个同名 Chisel 类。
- `store_trigger`/`load_trigger` 的 top 后缀 `_3` 等是生成名；合同和 `workspace.json` 按实际 top 与实例化位置绑定。

## 3. DUT 合同

19 份合同均在 [contracts/](contracts)。每份合同给出职责、输入合法域、握手/背压/取消/异常/reset、关键时序和可观察结果。

| 族 | 合同 |
|---|---|
| Store 叶子/流水 | [store-arbiter](contracts/store-arbiter.md)、[store-trigger](contracts/store-trigger.md)、[store-delay](contracts/store-delay.md)、[store-s0](contracts/store-s0.md)、[store-s1](contracts/store-s1.md)、[store-s2](contracts/store-s2.md)、[store-s3](contracts/store-s3.md)、[store-s4](contracts/store-s4.md) |
| Store 父块 | [new-store-unit](contracts/new-store-unit.md) |
| Load 叶子/流水 | [load-arbiter](contracts/load-arbiter.md)、[load-trigger](contracts/load-trigger.md)、[load-datapath](contracts/load-datapath.md)、[load-s0](contracts/load-s0.md)、[load-s1](contracts/load-s1.md)、[load-s2](contracts/load-s2.md)、[load-s3](contracts/load-s3.md)、[load-s4](contracts/load-s4.md) |
| Load 父块 | [new-load-unit](contracts/new-load-unit.md) |
| 标量执行 | [std-exe-unit](contracts/std-exe-unit.md) |

## 4. 接口与行为要求

- 所有输入必须满足 DUT 公开端口的合法域；`testbenches/*/env/` 的输入键校验拒绝未知键和错误形状。
- 参考模型来自合同/ISA/微架构语义，不从 RTL 反向复制判定；同源预期问题及修正见 [bugs/evidence/bug-reports-20261026/03-false-negative-review.md](../../bugs/evidence/bug-reports-20261026/03-false-negative-review.md)。
- 真实失败保留为普通 FAIL；功能 bin 的 100% 只表示声明 bin 被采样。
- TLB/PMP/DCache 等外部协议行为仅作为激励/响应；不得据此宣称这些子系统已验证。

## 5. 设计确认状态

- 合同中的微架构行为和异常/reset 边界来自固定源码及生成 RTL 的静态核对，**没有设计 owner 的逐项签核记录**。
- 已确认的 RTL 问题见 [bugs/open](../../bugs/open)；它们是验证观察与规范/源码依据之间的差异，不表示本目录已批准修复方案。
- `LSU-STD-PERF-001` 只有源码静态证据（计数器未导出），不能扩成功能缺陷；其余 6 个有原生 DUT 动态证据。
- 外部代理的合法域限制（LSQ/DCache/TLB/PMP/Sbuffer/Backend/ROB）仍是本工程结论的边界；未做跨族联合或整核可达性证明。
