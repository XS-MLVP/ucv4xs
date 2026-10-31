# IFU 退出标准与残余处置

按 [退出与残余方法](../../../../skills/design/closure-and-residuals.md) 在交付时逐项
对账。本文件是**验收合同**，不是结果宣传：结论受基线、参数、观察点与运行范围约束。

## 1. 验收范围

| 项目 | 值 |
|---|---|
| DUT | `RvcExpander`、`InstrBoundary`、`PredChecker`、`IfuUncacheUnit`、`FrontendTrigger`、`IfuPerfAnalysis`、`Ifu`（七个） |
| 源码基线 | `public-893e1580b705d81f113c30c7a05734e09a08050e` |
| 设计配置 | DefaultConfig（单核、C 扩展、F/D 开启、`FetchPorts=2`、`IBufferEnqueueWidth=36`、`AlignWidth=4`） |
| 工具 | 原生构建保留 picker 4dd442c、xcomm 0.3.0、Verilator；当前运行为 `.venv-uc-toffee` 的 `uc-toffee 2.0.1.dev1+uncertain.a886d1c12444`、`uc-xcomm 1.1.1`；[完整身份](uncertain-migration-20261030.md) |
| 观察边界 | 生成 RTL 的端口；不使用 VPI、不修改 RTL、不读内部层次信号 |
| 运行证据 | `results/20261030T-uncertain-uc-toffee`（UNCERTAIN 框架迁移复验，保留 R-13 反例） |

## 2. 交付要求（分别判定，不互相替代）

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

每个功能点的判定、用例与残余见
[功能点语义](functional-points.md) 与 `verification_plan.json`（含
`metadata.traceability`）。汇总：

- 硬件 55 项，全部有动态检查（真实 DUT + 独立模型），无静态勾选；
- 环境 5 项，覆盖 pruned 端口、负对照、双向追溯、激励合法性、交接面探测；
- 每个组件至少一条完整实现记录（requirement / oracle / observations / controls /
  tests / residual），记录中的 nodeid 由 `tests/framework/test_traceability.py` 校验存在。

## 4. 残余登记

**残余不是测试状态。** PASS/FAIL/XFAIL/SKIP 都描述“已执行的用例”；“没构造这个输入”、
“端口装不下”、“本层不负责”没有对应用例，塞进 PASS 会放大结论，塞进 XFAIL 则需要
一条不可能失败的假用例。因此残余单独登记在 `verification_plan.json` 的 `residuals`
（机器可读，插件校验结构并写入功能点报告），每个残余必须带 id、行为、类别、证据、
承接方、下一动作、是否阻塞、接受状态；阻塞项还必须指名它所影响的功能点。

插件的一致性门禁：
- 存在 `blocking && acceptance=open` 的残余时，硬件功能点不允许全 PASS；
- 出现 FAIL 功能点时，必须存在 blocking 残余，防止失败被“就地解释”掉。

残余同时进入运行报告（不只停留在本文件）：

- `ucv run` 把工程 `verification_plan.json` 的 `residuals` 写进 `run.json` 的 suite 记录；
- `ucv report` 汇总为 `summary.json` 的 `residuals` / `residual_summary`，并在
  `summary.md` 增加“Residual register (unproven scope; not a test status)”一节，逐条
  列出 `id[类别, blocking]`；
- 若所有用例 PASS 但存在 `blocking + open` 残余，硬件判定降为 `INCOMPLETE`，原因写入
  `Verification gaps`。本轮 IFU 有 FAIL，所以判定本身就是 FAIL；这条门禁是为“只差
  残余就全绿”的情况准备的。

| id | 行为/类 | 缺口类别 | 影响 | 证据 | 承接与下一动作 | 阻塞？ | 接受依据 |
|---|---|---|---|---|---|---|---|
| R-01 | 各 DUT `ENABLE_INITIAL_REG_` 初始化块的复位 else 臂（每 DUT 1 个分支） | 结构不可达 | 无功能影响 | 初始化块在时刻 0 复位必为高；所有 DUT 同形 | 不适用 | 否 | 生成代码语义；已逐项定位 |
| R-02 | `RvcExpander` `load_opc[5:6]` 从不跳变 | 结构常量 | 无 | 选择子只取 `7'h3`/`7'h1F`，两值 bit5/6 相同；负对照证明其余位会比较 | 不适用 | 否 | 同上 |
| R-03 | `InstrBoundary` `blockSel[0]` 条件臂、各 lane 偏移高位、slot31 cross 端口删除 | 结构常量/宽度截断 | 无 | 槽 0 必属第一块；5 位偏移对低 lane 高位恒 0；模型全扫证明 slot31 恒 0 | 不适用 | 否 | `tests/framework/test_pruned_ports.py` + 模型扫描 |
| R-04 | `PredChecker` lane35 PC 的 3 个数据位、lane34 cross 端口删除 | 数据相关 / 结构 | 无功能影响 | lane35 无指令端口；lane34 只对应 index 31，模型全扫 + lane33 可跨块对照 | 不适用 | 否 | `tests/framework/test_pruned_ports.py` |
| R-05 | `Ifu` 第 36 lane 恒 0、`blockSel[0]` 臂 | 结构常量 | 无 | IFU 显式把 padding lane 置 0；入队掩码 bit35 恒 0 | 不适用 | 否 | `tests/framework/test_pruned_ports.py` |
| R-06 | `Ifu` 逐 lane PC/数据位、`toIBuffer.topdownInfo` 部分理由位 | 覆盖成本/端口限制 | 可能隐藏单 lane 位级缺陷 | 需每 lane 每位双向跳变；topdown 仅部分理由位被驱动 | 若要追平：按 lane 位扫描 + 理由位注入；当前不阻塞 | 否 | 成本声明，不称已覆盖 |
| R-07 | `IfuPerfAnalysis` 272 个理由位恒 0 | 端口裁剪 | 无（本配置无此数据源） | 76 个理由位只有 10 个有驱动端口，可达位已 100% | 基线改变时重评 | 否 | 可达位全覆盖 |
| R-08 | `toFtq.wbRedirect.pc` 丢失 guard 位 | **DUT 交接面限制（out-of-domain）** | guard=1 的重定向 PC 在 FTQ 侧被错误重装 | 探测：输入 `0x7FF_FFFF_FFFF_FE`，输出 `0x3FF_FFFF_FFFF_FE`；同拍 51 位 target 正确；上游 `b716aade` 已修，本地基线是其 pre-image | 升级基线后重跑并改为正向断言；当前硬件 PASS 明确不覆盖该交接 | **是（限定范围）** | [上游复核](upstream-review-20261029.md)、`IFU-ENV-005` |
| R-09 | `Ifu` 跨块 split 仅在最后一个槽验证 | 情况枚举已覆盖（split 1..30），窗口末端 carry 只验证一种 | 低 | `test_cross_block_split_position_sweep` 与 `test_instruction_split_across_two_fetch_windows_is_assembled` | 若需更强：随机化 carry 位置与指令类别 | 否 | 已覆盖边界邻域 |
| R-10 | 上游 `frontend/ftq`、`frontend/icache` 路径未做差分复核 | 证据不足 | 输入侧行为可能已变 | 本轮只查 `frontend/ifu` 与直接交接 | 下一轮按同方法查询并记录 | 否（本轮范围外） | 明确标注未验证 |
| R-11 | `isBackendException` / `hasSatpFlush` 的语义消费 | 当前 DUT 边界外 | IFU 只负责把 block-0 标记挂到第一条指令；IBuffer/后端的 `satpFlushFirstFetchFault` 等消费不在本层 | 逐拍比较 + 三组定向标记用例已通过；消费逻辑见 `ibuffer/Bundles.scala:150` | 由 IBuffer/后端承接；“后端异常 + 跨页异常同拍”组合仍可补 | 否 | 转发已验证，消费未验证 |
| R-12 | `toIBuffer.pc/isLastInFtqEntry/prevIBufEnqPtr` 未导出 | 观察点缺失 | 无法直接比较，只能间接覆盖 | 同 §1/§5 | 需要导出点时补直接观察；当前用 foldpc/指令字/ftqPtr 间接覆盖 | 否 | 间接覆盖，明确不称直接验证 |
| R-13 | `FrontendTrigger` 只比较 `tdata2[49:0]`，而 CSR `tdata2` 是 `RW(63,0)` 的 64 位字段 | **真实 RTL 缺陷（`confirmed-rtl`）** | tdata2 高位被写入却被忽略：EQ/GE 产生虚假 breakpoint/debug，LT 漏命中；只影响 tdata2 ≥ 2^50 的配置 | 复现与根因见 [FrontendTrigger tdata2 宽度](bugs/frontend-trigger-tdata2-width.md)；`test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc`、`test_tdata2_above_the_address_space_is_greater_for_less_than` 两条 FAIL；EQ 在 `tdata2=2^50+pc` 时 lane 10 命中，LT 在 `tdata2=2^50` 时 36 lane 全不命中 | 修复方向二选一：(a) 比较全 64 位（PC 零扩展）；(b) CSR 把 tdata2 高位做成 WARL 只读 0，并在合同中声明只比较低 50 位；修复后重跑两条用例 | **是** | RISC-V Sdtrig 语义 + `Tdata2Bundle.ALL = RW(63,0)`；模型原先把 tdata2 掩码到 50 位，已改为全宽以暴露差异 |

“不适用”与“成本声明”不等于已验证。本轮唯一**阻塞**项是 R-13（`blocking=true`,
`acceptance=open`）；R-08 是限定声明范围的**披露**项（`accepted-limited`），它不阻塞
本层判定，但阻塞“IFU 已完整交接 51 位 PC”这一更强的结论。

### 观察点精度扫描（按 [观察点精度方法](../../../../skills/design/observation-precision.md)）

筛选门默认留下“正确性未建立”的字段，关闭必须有消费者合同或结构证明；不得用
“端口就这么多位”关闭。当前已识别的窄化字段：

| id | 字段 | 内部语义 | 观察端口 | 消费者需要 | 判断 | 关闭条件 | 承接 | 影响 |
|---|---|---|---|---|---|---|---|---|
| R-08 | `toFtq.wbRedirect.pc` | 51 位 `GuardedPc`（bit50=guard） | 50 位 | FTQ 用 `GuardedPcInit` 重建，需要 guard | **留下**（交接面限制） | 端口加宽到 51 位后改为正向断言 | FTQ；上游已修、本地未含 | 硬件 PASS 不含 guard=1 的 PC 交接 |
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
| guard=1 的重定向 PC | R-08 | 硬件 PASS 不含此项 |

## 6. 结论

- 本轮约定范围内（`public-893e1580b` + DefaultConfig + 上述观察点）**未达到**交付标准：
  144 PASS、2 FAIL、1 UNCERTAIN；硬件 53/55 PASS + 1 FAIL（`IFU-TR-002`）+ 1 UNCERTAIN（`IFU-TOP-011`）、环境 5/5。失败是真实 RTL
  行为（R-13），不是环境问题；不登记 XFAIL，不删除反例。
- 该结论**不能**扩写为“IFU 没有缺陷”或“整个系统已验收”：R-08 的交接面限制在
  系统层会产生错误 PC，只是本层端口无法表达；R-06/R-09/R-10 是明确的未证明范围。
- 任何基线、参数、工具或观察点变化后，受影响项重新打开，不沿用本轮 PASS。
- R-13 修复前，`FrontendTrigger` 的功能结论只覆盖“tdata2 高 14 位为 0”的配置；
  不能声称 Sdtrig PC 匹配已完整验证。

历史第三轮 `results/20261030T022604Z-107cb685` 使用 `pytoffee 2.0.1.dev1+g4a09d21`
与旧 `.venv`，结果为 144 PASS / 2 FAIL / 1 声明式 INCOMPLETE。原报告保持原判定；
本轮只迁移证据不足状态并复验，不将旧结果改名或借框架迁移关闭残余。
