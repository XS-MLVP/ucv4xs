# IFU 退出标准与残余处置

按 [退出与残余方法](../../../../../../skills/design/closure-and-residuals.md) 在交付时逐项
对账。本文件是**验收合同**，不是结果宣传：结论受基线、参数、观察点与运行范围约束。

**2026-11-08 收口检查点（`public-a0c2a26cb`，R-09 已关闭）**：
在 2026-11-07 基线上只做验证侧扩张（未改 RTL/Scala/生成物）。完整 seed1 为
**939 PASS / 6 FAIL / 0 UNCERTAIN**（945 nodeid，
`results/ifu-a0c2a26cb-carry-sweep-seed1-20261108`）：
相对上一轮 727 nodeid，**无删除**；原 56 条 carry 扫掠替换为 217 条
（16 个奇数 carry 位置 × 7 个非控制流 ISA 类别 × 2 种前导形状，覆盖写 bank
lane 0..3，全部 PASS），新增 1 条 GE 常驻反例，1 条 UNCERTAIN→PASS
（`test_instruction_split_across_two_fetch_windows_is_assembled`，
其 UNCERTAIN 依据 R-09 已由上述扫掠关闭）。PASS→FAIL 与 FAIL→PASS 均为 0
（既有 5 条 FAIL 判定不变，新增 GE 为第 6 条）。
**R-09 关闭**（`acceptance=resolved`）；R-13（3 条 FAIL）与 R-14（3 条 FAIL）仍是
**开放阻塞项**，缺陷文档已补根因行号、最小复现、影响面与上游只读检索记录。
R-08 保持关闭。6 条硬件 FAIL 的逐条归因见 §3。本结论只覆盖 IFU / DefaultConfig /
`public-a0c2a26cb`；**R-13/R-14 未关闭前不得写成硬件通过**。

**2026-11-07 检查点（`public-a0c2a26cb`）**：
七个 DUT 已在新基线 prepare/build 并 7/7 `BUILT + SMOKE PASS`；完整 seed1 为
**721 PASS / 5 FAIL / 1 UNCERTAIN**（727 nodeid，
`results/ifu-a0c2a26cb-full-seed1-final5-20261107`），同源码 seed2 定向（`tests/ifu`、
`tests/uncache_unit`、`tests/frontend_trigger`）为 **132 PASS / 3 FAIL / 1 UNCERTAIN**
（136 nodeid，`results/ifu-a0c2a26cb-seed2-target-final3-20261107`），两轮逐 nodeid
判定一致。R-13（两条 FAIL）与 R-14（三条 FAIL）在
新 RTL 上逐值复现，仍是**开放阻塞项**；R-09 仍是 UNCERTAIN。R-08/`IFU-ENV-005`
已随基线包含 `b716aade` 转为正向对照并关闭。本节结果只覆盖 IFU / DefaultConfig /
`public-a0c2a26cb`；下表及 §1–§6 中 2026-10-30/2026-11-01 的记录保持其原日期、
原基线与原判定。

**2026-11-01更新**：事务适配审计新增真实缺陷R-14（carry被误标cross并错用块1 FTQ），
当前开放阻塞项为R-13、R-14；详见[缺陷复现](../../bugs/open/instr-boundary-carry-ftq-owner.md)及
[活动事务合同](transaction-adapters.md)。当前框架为仓库锁定的uc-toffee2.1.0，以下
范围/结果表保留2026-10-30检查点的环境、判定与覆盖边界，不能当作当前源码验收收据。

**2026-11-07更新**：`public-a0c2a26cb` 已并入上游 `b716aade`，`toFtq.wbRedirect.pc`
由 50 位加宽为 51 位 `GuardedPc`，R-08 关闭（见 §4 与
[上游复核](evidence/upstream-review-20261029.md) 的 2026-11-07 节）。R-13/R-14 未修，
其反例在完整 seed1 与 seed2 定向中原样保持。

## 1. 验收范围（2026-10-30历史检查点）

| 项目 | 值 |
|---|---|
| DUT | `RvcExpander`、`InstrBoundary`、`PredChecker`、`IfuUncacheUnit`、`FrontendTrigger`、`IfuPerfAnalysis`、`Ifu`（七个） |
| 源码基线 | `public-893e1580b705d81f113c30c7a05734e09a08050e` |
| 设计配置 | DefaultConfig（单核、C 扩展、F/D 开启、`FetchPorts=2`、`IBufferEnqueueWidth=36`、`AlignWidth=4`） |
| 工具 | 原生构建保留 picker 4dd442c、xcomm 0.3.0、Verilator；当前运行为 `.venv-uc-toffee` 的 `uc-toffee 2.0.1.dev1+uncertain.a886d1c12444`、`uc-xcomm 1.1.1`；[完整身份](evidence/uncertain-migration-20261030.md) |
| 观察边界 | 生成 RTL 的端口；不使用 VPI、不修改 RTL、不读内部层次信号 |
| 运行证据 | `results/20261030T-uncertain-uc-toffee`（UNCERTAIN 框架迁移复验，保留 R-13 反例） |

## 2. 交付要求（分别判定，不互相替代）

> 本节“本轮状态”列属于 2026-10-30 检查点；2026-11-07 新基线的状态见文首当前检查点。

| 要求 | 判据 | 本轮状态 |
|---|---|---|
| 构建 | 七个 DUT 均 BUILT + SMOKE PASS，包文件齐全且哈希入凭据 | 达成（`ucv build ifu`） |
| 冒烟 | 每个 DUT 独立进程构造、时钟推进、`Finish` 通过 | 达成 |
| 功能判定 | 硬件功能点 53/55 PASS + 1 FAIL（`IFU-TR-002`）+ 1 UNCERTAIN（`IFU-TOP-011`）；环境功能点 5/5 PASS，分区统计 | **未达成**（144 PASS、2 FAIL、1 UNCERTAIN） |
| 行覆盖 | 七个 DUT 的生成 RTL 行 100% | 达成（4053/4053 等） |
| 分支覆盖 | 残留臂逐项定位为结构不可达或有明确残余登记 | 达成（见 §4） |
| toggle 覆盖 | 记录未跳变位；结构上限与成本缺口分别说明 | 达成（见 §4、§5） |
| 未覆盖反馈 | 每个缺口归类为“已有功能点缺枚举 / 整类未定义 / 配置或观察点限制”，并补点或登记 | 达成（新增 `IFU-TOP-011` 与 5 个 `IFU-ENV-*`） |
| 文档 | 功能点语义、责任矩阵、闭环记录、上游复核、覆盖摘要可追溯 | 达成 |

## 3. 必验功能（逐项对账）

每个功能点的要求、实现与观察路径见[功能点语义](../design/functional-points.md)、
[观察覆盖](observation-coverage.md)和[事务合同](transaction-adapters.md)。
工程根的 `verification_plan.json` 已删除；下方日期表保留对应回归的判定。要求汇总：

- 硬件 56 项，全部有动态检查（真实 DUT + 独立模型），无静态勾选；
- 环境 5 项，覆盖 pruned 端口、负对照、双向追溯、激励合法性、交接面探测；
- 每个组件需关联要求、独立 oracle、观察、控制、真实用例和未证明范围，按上述规格
  与实际收集结果核对。

**2026-11-08 逐点判定与 6 条硬件 FAIL 归因（`public-a0c2a26cb`，61 点全覆盖）**：

| 判定 | 功能点 | 归属 |
|---|---|---|
| PASS | `IFU-RVC-001..009` | `RvcExpander.sv` 逐字节不变；ISA 编码表 oracle、激励与用例集合未变 |
| FAIL | `IFU-IB-001..006` | **真实 RTL（R-14 同根因）**：600 窗口用例在 `(137,254,406,477,529)` 五处 `is_cross_block[0]` 期望 0 实际 1；`IFU-IB-005` 另有 leaf 成对反例 |
| PASS | `IFU-PC-001..007` | `PredChecker.sv` 逐字节不变；预测合同与 51 位 GuardedPc 目标算术不变 |
| PASS | `IFU-UC-001..008` | `IfuUncacheUnit.sv` 逐字节不变；MMIO/NC/IO、UID、重发与 flush 语义不变 |
| FAIL | `IFU-TR-002` | **真实 RTL（R-13）**：`Trigger.scala` 只取 `tdata2[49:0]`；EQ lane 10 误命中、LT 36 lane 全漏、GE lane 10..35 误命中（GE 已常驻） |
| PASS | `IFU-TR-001`、`IFU-TR-003..007` | 同一 RTL；原子配置、门控、链、优先级、逐 lane、全零复位对照均通过 |
| PASS | `IFU-PA-001..007` | `IfuPerfAnalysis.sv` 逐字节不变；13 事件与理由位流水比较不变 |
| PASS | `IFU-TOP-001..004`、`IFU-TOP-006..010`、`IFU-TOP-012` | 取指、对齐、反压、flush、异常、uncache、trigger、性能事件均通过 |
| FAIL | `IFU-TOP-005`、`IFU-TOP-011` | **真实 RTL（R-14）**：顶层恢复反例 `ftq[0][1]` 期望 32 实际 33；`IFU-TOP-011` 的 R-09 子例已转 PASS，FAIL 仅由 R-14 反例决定 |
| PASS | `IFU-ENV-001..005` | pruned 端口、比较器区分力、双向追溯、非法激励门禁、51 位 guard 交接正向对照 |

**6 条硬件 FAIL 的逐条归因**（无一项归为模型滞后或观察债务）：

| # | 功能点 | nodeid | 归属 |
|---:|---|---|---|
| 1 | `IFU-TR-002` | `test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc` | 真实 RTL R-13（EQ 截断误命中） |
| 2 | `IFU-TR-002` | `test_tdata2_above_the_address_space_is_greater_for_less_than` | 真实 RTL R-13（LT 截断漏命中） |
| 2b | `IFU-TR-002` | `test_tdata2_above_the_address_space_is_not_greater_for_greater_equal` | 真实 RTL R-13（GE 截断误命中，已常驻） |
| 3 | `IFU-IB-001..006` | `test_random_windows_match_the_model` | 真实 RTL R-14（600 窗口 5 个 cross 反例） |
| 4 | `IFU-IB-005` | `test_carried_upper_half_cannot_acquire_block_one_ownership[upper-half-low11]` | 真实 RTL R-14（leaf 最小复现） |
| 5 | `IFU-TOP-005`、`IFU-TOP-011` | `test_recovered_half_instruction_keeps_its_completing_ftq_block[upper-half-low11]` | 真实 RTL R-14（FTQ 归属错位） |

功能点计 6 个 FAIL 是因为共享用例覆盖多个点（第 3 条计入 `IFU-IB-001..006`，
第 5 条计入 `IFU-TOP-005` 与 `IFU-TOP-011`），不是 6 个独立缺陷。

**2026-11-07 逐点判定（`public-a0c2a26cb`，61 点全覆盖）**（保留原表）：

| 判定 | 功能点 | 依据 |
|---|---|---|
| PASS | `IFU-RVC-001..009` | `RvcExpander.sv` 逐字节不变；ISA 编码表 oracle、激励与用例集合未变 |
| FAIL | `IFU-IB-001..006` | `InstrBoundary.sv` 逐字节不变；共享的 600 窗口用例在原 `(137,254,406,477,529)` 位置因 R-14 失败（`IFU-IB-005` 另有 leaf 成对反例） |
| PASS | `IFU-PC-001..007` | `PredChecker.sv` 逐字节不变；预测合同与 51 位 GuardedPc 目标算术不变 |
| PASS | `IFU-UC-001..008` | `IfuUncacheUnit.sv` 逐字节不变；MMIO/NC/IO、UID、重发与 flush 语义不变 |
| FAIL | `IFU-TR-002` | `FrontendTrigger.sv` 逐字节不变；只比较 `tdata2[49:0]`，两条越界反例原样 FAIL（R-13） |
| PASS | `IFU-TR-001`、`IFU-TR-003..007` | 同一 RTL；原子配置、门控、链、优先级、逐 lane、全零复位对照均通过 |
| PASS | `IFU-PA-001..007` | `IfuPerfAnalysis.sv` 逐字节不变；13 事件与理由位流水比较不变 |
| PASS | `IFU-TOP-001..004`、`IFU-TOP-006..010`、`IFU-TOP-012` | 顶层仅有重定向 PC 位宽变化；取指、对齐、反压、flush、异常、uncache、trigger、性能事件均通过；`IFU-TOP-009` 的 uncache 重定向现已保留 guard 位并 PASS |
| FAIL | `IFU-TOP-005`、`IFU-TOP-011` | 顶层恢复反例仍以 `ftq(0,33)` 而非 `(0,32)` 失败（R-14）；`IFU-TOP-011` 另有 R-09 的 UNCERTAIN 子例，但 FAIL 优先 |
| PASS | `IFU-ENV-001..004` | pruned 端口、比较器区分力、双向追溯、非法激励门禁均通过；`IFU-ENV-004` 的 schema 断言已按 51 位重定向端口更新 |
| PASS | `IFU-ENV-005` | 由截断探测改为正向交接对照：cached/uncache/第二块 + 仅 bit50 不同，四条 PASS，R-08 关闭 |

判定按“该功能点是否有任一分区用例非 PASS”取最严结果；一个共享用例覆盖多个点时，
其失败会计入所有被覆盖点（例如 600 窗口用例覆盖 `IFU-IB-001..006`），不把失败点
藏到“其他点通过”后面。

## 4. 残余登记

**残余不是测试状态。** PASS/FAIL/XFAIL/SKIP 都描述“已执行的用例”；“没构造这个输入”、
“端口装不下”、“本层不负责”没有对应用例，塞进 PASS 会放大结论，塞进 XFAIL 则需要
一条不可能失败的假用例。配置、观察和集成边界继续在本节与所属合同中说明行为、证据、
影响、承接方及下一动作；`R-13`、`R-14` 的具体缺陷与复验状态维护在
[问题记录](../../bugs/README.md)。纯适用范围限制不转写为 RTL 缺陷。

当前运行不再要求旧计划或残余 JSON 清单。验收时需同时核对实际用例结果、本节的
未证明范围和开放问题；局部全 PASS 不能关闭必需义务，FAIL 也不能靠登记“残余”
来解释掉。下表沿用既有标识及证据边界，历史运行中的 `Residual register` 和
`INCOMPLETE` 保持当时含义，不由本次文档调整重算。

| id | 行为/类 | 缺口类别 | 影响 | 证据 | 承接与下一动作 | 阻塞？ | 接受依据 |
|---|---|---|---|---|---|---|---|
| R-01 | 各 DUT `ENABLE_INITIAL_REG_` 初始化块的复位 else 臂（每 DUT 1 个分支） | 结构不可达 | 无功能影响 | 初始化块只写生成代码的寄存器初值：harness 在首个求值前置 reset 时命中 then 臂，else 是否命中随实例首次求值时的 reset 值变化（2026-11-01 命中、2026-11-07 未命中） | 不适用 | 否 | 生成代码语义；已逐项定位 |
| R-02 | `RvcExpander` `load_opc[5:6]` 从不跳变 | 结构常量 | 无 | 选择子只取 `7'h3`/`7'h1F`，两值 bit5/6 相同；负对照证明其余位会比较 | 不适用 | 否 | 同上 |
| R-03 | `InstrBoundary` `blockSel[0]` 条件臂、各 lane 偏移高位、slot31 cross 端口删除 | 结构常量/宽度截断 | 无 | 槽 0 必属第一块；5 位偏移对低 lane 高位恒 0；模型全扫证明 slot31 恒 0 | 不适用 | 否 | `testbenches/ifu/tests/framework/test_pruned_ports.py` + 模型扫描 |
| R-04 | `PredChecker` lane35 PC 的 3 个数据位、lane34 cross 端口删除 | 数据相关 / 结构 | 无功能影响 | lane35 无指令端口；lane34 只对应 index 31，模型全扫 + lane33 可跨块对照 | 不适用 | 否 | `testbenches/ifu/tests/framework/test_pruned_ports.py` |
| R-05 | `Ifu` 第 36 lane 恒 0、`blockSel[0]` 臂 | 结构常量 | 无 | IFU 显式把 padding lane 置 0；入队掩码 bit35 恒 0 | 不适用 | 否 | `testbenches/ifu/tests/framework/test_pruned_ports.py` |
| R-06 | `Ifu` 逐 lane PC/数据位、`toIBuffer.topdownInfo` 部分理由位 | 覆盖成本/端口限制 | 可能隐藏单 lane 位级缺陷 | 需每 lane 每位双向跳变；topdown 仅部分理由位被驱动 | 若要追平：按 lane 位扫描 + 理由位注入；当前不阻塞 | 否 | 成本声明，不称已覆盖 |
| R-07 | `IfuPerfAnalysis` 272 个理由位恒 0 | 端口裁剪 | 无（本配置无此数据源） | 76 个理由位只有 10 个有驱动端口，可达位已 100% | 基线改变时重评 | 否 | 可达位全覆盖 |
| R-08 | `toFtq.wbRedirect.pc` 丢失 guard 位（历史 893e1580b 交接面限制） | **out-of-domain（已关闭）** | 旧基线 guard=1 的重定向 PC 在 FTQ 侧会被错误重装 | 旧基线探测输入 `0x7FF_FFFF_FFFF_FE` 输出 `0x3FF_FFFF_FFFF_FE`；`public-a0c2a26cb` 含 `b716aade` 后端口 51 位，cached/uncache/第二块三条正向对照 PASS，`pc[50]` 双向跳变 | 关闭；后续基线变更时重跑 `IFU-ENV-005` | 否（已关闭） | [上游复核](evidence/upstream-review-20261029.md)、`IFU-ENV-005` |
| R-09 | `Ifu` 跨窗口 carry 续取的位置与指令类别覆盖 | **已关闭（2026-11-08）** | 原先只验证窗口末端一种位置 | `test_carry_position_and_instruction_class_sweep`：可达 carry 位置 1,3,5,9,15,21,27,31（invalid-taken 截断点）+ 窗口末端 32，× 7 个非控制流 ISA 类别（ALU-I/ALU-R/LUI/M/load/store/system），同源码 56 PASS；控制流类别排除理由与 R-14 类别排除理由已写入用例文档 | 已关闭；R-14 修复后复核排除类别 | 否（已关闭） | 位置由归纳覆盖与窗口几何共同确立，不是抽样 |
| R-10 | 上游 `frontend/ftq`、`frontend/icache` 路径未做差分复核 | 证据不足 | 输入侧行为可能已变 | 本轮只查 `frontend/ifu` 与直接交接 | 下一轮按同方法查询并记录 | 否（本轮范围外） | 明确标注未验证 |
| R-11 | `isBackendException` / `hasSatpFlush` 的语义消费 | 当前 DUT 边界外 | IFU 只负责把 block-0 标记挂到第一条指令；IBuffer/后端的 `satpFlushFirstFetchFault` 等消费不在本层 | 逐拍比较 + 三组定向标记用例已通过；消费逻辑见 `ibuffer/Bundles.scala:150` | 由 IBuffer/后端承接；“后端异常 + 跨页异常同拍”组合仍可补 | 否 | 转发已验证，消费未验证 |
| R-12 | `toIBuffer.pc/isLastInFtqEntry/prevIBufEnqPtr` 未导出 | 观察点缺失 | 无法直接比较，只能间接覆盖 | 同 §1/§5 | 需要导出点时补直接观察；当前用 foldpc/指令字/ftqPtr 间接覆盖 | 否 | 间接覆盖，明确不称直接验证 |
| R-13 | `FrontendTrigger` 只比较 `tdata2[49:0]`，而 CSR `tdata2` 是 `RW(63,0)` 的 64 位字段 | **真实 RTL 缺陷（`confirmed-rtl`）** | tdata2 高位被写入却被忽略：EQ/GE 产生虚假 breakpoint/debug，LT 漏命中；只影响 tdata2 ≥ 2^50 的配置 | 复现与根因见 [FrontendTrigger tdata2 宽度](../../bugs/open/frontend-trigger-tdata2-width.md)；`test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc`、`test_tdata2_above_the_address_space_is_greater_for_less_than` 两条 FAIL；EQ 在 `tdata2=2^50+pc` 时 lane 10 命中，LT 在 `tdata2=2^50` 时 36 lane 全不命中 | 修复方向二选一：(a) 比较全 64 位（PC 零扩展）；(b) CSR 把 tdata2 高位做成 WARL 只读 0，并在合同中声明只比较低 50 位；修复后重跑两条用例 | **是** | RISC-V Sdtrig 语义 + `Tdata2Bundle.ALL = RW(63,0)`；模型原先把 tdata2 掩码到 50 位，已改为全宽以暴露差异 |
| R-14（2026-11-01新增） | carry首槽误标cross，使用块1 FTQ身份 | **真实RTL缺陷** | 正常invalidTaken恢复后指令字/PC/endOffset正确但FTQ归属错误 | [正常/错误高半字对照](../../bugs/open/instr-boundary-carry-ftq-owner.md)，原600窗口有5个反例 | 只允许真实起始cross；复核carry重建后归属，重跑leaf/原随机/顶层反例 | **是** | 独立指令起始语义 + 真实两取指恢复；不以修改oracle或扩大XFAIL关闭 |

“不适用”与“成本声明”不等于已验证。2026-10-30检查点唯一**阻塞**项是 R-13（`blocking=true`,
`acceptance=open`）；R-08 当时是限定声明范围的**披露**项（`accepted-limited`），它不阻塞
本层判定，但阻塞“IFU 已完整交接 51 位 PC”这一更强的结论。
2026-11-01新增R-14后，当前阻塞集合为R-13/R-14，旧检查点结果不重标。
2026-11-07：R-08 随 `public-a0c2a26cb` 并入 `b716aade` 转为 `acceptance=resolved`；
R-13/R-14 仍为 blocking + open。
2026-11-08：R-09 由验证侧扩张关闭（`resolved`）；当前阻塞集合仍为 R-13/R-14。

### 观察点精度扫描（按 [观察点精度方法](../../../../../../skills/design/observation-precision.md)）

筛选门默认留下“正确性未建立”的字段，关闭必须有消费者合同或结构证明；不得用
“端口就这么多位”关闭。当前已识别的窄化字段：

| id | 字段 | 内部语义 | 观察端口 | 消费者需要 | 判断 | 关闭条件 | 承接 | 影响 |
|---|---|---|---|---|---|---|---|---|
| R-08 | `toFtq.wbRedirect.pc` | 51 位 `GuardedPc`（bit50=guard） | 51 位（`public-a0c2a26cb`） | FTQ 用 `GuardedPcInit` 重建，需要 guard | **已关闭** | 已完成：端口 51 位且三条正向对照 + 仅 bit50 不同的区分对照 PASS | FTQ；`b716aade` 已并入基线 | 硬件 PASS 现已包含 guard=1 的 PC 交接 |
| R-12 | `toIBuffer.pc/isLastInFtqEntry/prevIBufEnqPtr` | 逐 lane PC/边界/指针 | 未导出 | IBuffer 写入与 FTQ 边界需要 | **留下**（缺观察点） | 有允许的导出点后直接比较 | IBuffer/FTQ | 只有间接覆盖，不称直接验证 |
| R-07 | top-down 理由位 | 76 位 | 10 位有驱动端口 | 性能计数消费全部理由 | **留下**（配置裁剪） | 配置出现新数据源时重评 | 性能分析 | 可达位 100%，其余未激活 |
| R-13 | `tdata2`（FrontendTrigger） | 64 位 CSR 字段 | 64 位端口，但比较只用 50 位 | 软件可写入全部 64 位；仲裁比较需全宽 | **留下并判 FAIL** | 全宽比较，或 CSR 高位 WARL 化并改合同 | FrontendTrigger | 硬件 PASS 不再成立；见残余 R-13 |
| — | 异常元数据/FTQ 指针其余字段 | 待核 | 待核 | 待核 | **待扫描** | 完成逐字段核对后登记或关闭 | — | 当前不能声称已全扫 |

最后一行必须保留：本表是当前已识别项，不是“内部宽/端口窄”已穷尽的证明。

## 5. 允许的范围排除

| 排除项 | 依据 | 影响 |
|---|---|---|
| ICache 内部 hit/miss/流水时序 | 已由 ICache 工程验证；本工程只驱动请求端口 | 本工程的 `Ifu` 结论不覆盖 ICache 实现 |
| InstrUncache/TileLink 通道语义 | 外部协议层，`IfuUncacheUnit` 只负责属性与响应映射 | 非缓存总线顺序未在本工程验证 |
| IBuffer bank 写入/回绕实现 | 后端/IBuffer 责任 | 只验证交接 beat |
| FTQ 训练与恢复 | FTQ 工程 | 只验证重定向字段 |
| 后端 breakpoint/debug 实际入口 | 后端 pre-match 阶段 | 只验证逐 lane 动作标记 |
| top-down 计数器累加与上报 | 性能分析/后端 | 只验证理由位传播 |
| guard=1 的重定向 PC | 已随 `public-a0c2a26cb` 关闭（R-08 resolved） | 不再排除；由 `IFU-ENV-005` 正向对照覆盖 |

## 6. 结论

**2026-11-08 当前结论（`public-a0c2a26cb` + DefaultConfig + 本文件观察点）**：
- 同源码 seed2 定向（`tests/ifu`、`tests/uncache_unit`、`tests/frontend_trigger`，16 workers）
  为 **350 PASS / 4 FAIL / 0 UNCERTAIN**（354 nodeid，
  `results/ifu-a0c2a26cb-carry-sweep-seed2-20261108`）；同 nodeid 子集判定逐条相同，
  4 条 FAIL 仍是 R-13 三条与 R-14 顶层一条。
- 约定范围内**未达到**交付标准：完整 seed1 **939 PASS / 6 FAIL / 0 UNCERTAIN**
  （945 nodeid，`results/ifu-a0c2a26cb-carry-sweep-seed1-20261108`）；硬件功能点
  **47/56 PASS、9 FAIL**（`IFU-TR-002`、`IFU-IB-001..006`、`IFU-TOP-005`、
  `IFU-TOP-011`）、环境功能点 5/5 PASS。6 条用例 FAIL 全部来自**真实 RTL** 缺陷
  R-13（3 条）与 R-14（3 条），不登记 XFAIL、不删除反例、不改期望。
- **R-09 已关闭**：`test_carry_position_and_instruction_class_sweep` 扩为
  16 个奇数 carry 位置 × 7 个非控制流 ISA 类别 × 2 种前导形状，覆盖写 bank
  lane 0..3，同源码 217 PASS；原 UNCERTAIN 用例转 PASS。关闭依据、排除类别
  （控制流与 R-14 上位半字模式）与理由见 §4 与用例文档，不是无证据删除。
- **R-13 仍开放**：根因在 `Trigger.scala` 只取 `tdata2[49:0]`；EQ lane 10 误命中、
  LT 36 lane 全漏、GE lane 10..35 误命中（GE 已常驻）；两个候选修复方向
  （高位守卫 / CSR 高位 WARL）只记录未实施。修复前 `FrontendTrigger` 的结论只
  覆盖“tdata2 高 14 位为 0”的配置。
- **R-14 仍开放**：carry 首槽误标 cross → 完成槽 FTQ 归属错位；leaf 最小复现、
  600 窗口 5 个反例、顶层 `ftq(0,33)` 均保留。修复前 carry 完成槽的 FTQ 归属仍可能
  有误。
- 上游只读检索（截至本地镜像 `2145ba1c9`，基线后 10 个提交）**未发现** R-13/R-14
  的修复提交；未访问网络、未提交 issue/PR/patch。
- 覆盖：七 DUT line 均 100%（Ifu 4053/4053），Ifu 顶层 branch 1647/1652 与上一轮
  相同（新增用例只增加 toggle 命中 30928→31099、曾变化位 16076→16136，未改变任何
  分支分母）；唯一未覆盖臂仍是 `ENABLE_INITIAL_REG_` 的 `if (reset)` else，其余 4 条
  维持原归因。
- 该结论仍**不能**扩写为“IFU 没有缺陷”“硬件通过”或“整个系统已验收”：
  R-13/R-14 未关闭，R-06/R-10 是明确的未证明范围，R-11/R-12 仍受消费/观察点限制，
  `InstrUncache`/TileLink 仍是出域。

以下 2026-10-30/2026-11-01 的历史结论保持原日期与原判定：

- 2026-10-30 检查点（`public-893e1580b` + DefaultConfig + 上述观察点）**未达到**交付标准：
  144 PASS、2 FAIL、1 UNCERTAIN；硬件 53/55 PASS + 1 FAIL（`IFU-TR-002`）+ 1 UNCERTAIN（`IFU-TOP-011`）、环境 5/5。失败是真实 RTL
  行为（R-13），不是环境问题；不登记 XFAIL，不删除反例。
- 该结论**不能**扩写为“IFU 没有缺陷”或“整个系统已验收”：当时 R-08 的交接面限制在
  系统层会产生错误 PC，只是本层端口无法表达；R-06/R-09/R-10 是明确的未证明范围
  （其中 R-09 已于 2026-11-08 由验证侧扩张关闭，见 §4；R-08 已由基线升级关闭）。
- 任何基线、参数、工具或观察点变化后，受影响项重新打开，不沿用本轮 PASS。

历史第三轮 `results/20261030T022604Z-107cb685` 使用 `pytoffee 2.0.1.dev1+g4a09d21`
与旧 `.venv`，结果为 144 PASS / 2 FAIL / 1 声明式 INCOMPLETE。原报告保持原判定；
本轮只迁移证据不足状态并复验，不将旧结果改名或借框架迁移关闭残余。
