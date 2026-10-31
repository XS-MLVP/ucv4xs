# IFU 覆盖率闭环记录（2026-10-29）

本文件记录每个模块与顶层组合的“定义语义功能点 → 开发用例 → 运行检查 → 分析未覆盖
缺口 → 补功能点/情况枚举 → 重新运行”的实际数据。数字来自 toffee 运行清单里的原生
`v_line` / `v_branch` / `v_toggle`（`tools/coverage_report.py`），不是 RTL 注释或
人工估算。

- 基线：`public-893e1580b`（根继承），DefaultConfig，七个 DUT 为同一份完整 RTL 的
  实例闭包。
- 环境：`.venv`（picker 4dd442c / pytoffee 2.0.1 / xcomm 0.3.0）+ `.tools/verilator`。
- 判定口径：line 为 `v_line` 的 `l`+`S` 展开后唯一生成 RTL 行；branch 为
  `v_branch` 条件臂；toggle 为 `v_toggle` 位级跳变 bin（另报曾变化的信号位数）。
- 每次运行使用新输出目录；中间目录在 `/tmp/opencode/ifu-*-cov*`，最终证据在
  `results/20261030T022604Z-107cb685`。

## 最新复验：UNCERTAIN 本地框架迁移（2026-10-30）

`results/20261030T-uncertain-uc-toffee` 使用本地 `uc-toffee` 开发版与独立
`.venv-uc-toffee` 重跑：**144 PASS / 2 FAIL / 1 UNCERTAIN**；硬件功能点
53 PASS / 1 FAIL / 1 UNCERTAIN，环境点 5/5。七个原生 DUT 未重建，逐用例集合及
line/branch/toggle 命中数、分母与第三轮相同。只有 carry 用例从旧声明式 INCOMPLETE
改为框架原生 UNCERTAIN，仍不计 PASS；R-13 两条 FAIL 保留。
工具版本、哈希、单/多进程复验见[迁移核验](uncertain-migration-20261030.md)。

## 第三轮结果（历史：`results/20261030T022604Z-107cb685`）

运行：`ucv run ifu --workers 1` → `ifu: FAIL (exit 1)`，144 PASS、**2 FAIL**、**1 INCOMPLETE**；
功能点报告 **硬件 53/55 PASS + 1 FAIL（`IFU-TR-002`）+ 1 INCOMPLETE（`IFU-TOP-011`）、验证环境 5/5 PASS**，两者分开统计
（`suites/frontend/ifu/results/feature-points.json` 的 `summaries`）。

| DUT | line | branch | toggle bin | 曾变化位 |
|---|---|---|---|---|
| `RvcExpander` | 174/174 (100.00%) | 66/66 (100.00%) | 140/146 (95.89%) | 71/73 |
| `InstrBoundary` | 90/90 (100.00%) | 153/154 (99.35%) | 2015/2196 (91.76%) | 1008/1098 |
| `PredChecker` | 105/105 (100.00%) | 23/24 (95.83%) | 15968/15998 (99.81%) | 7996/7999 |
| `IfuUncacheUnit` | 43/43 (100.00%) | 15/16 (93.75%) | 546/546 (100.00%) | 273/273 |
| `FrontendTrigger` | 193/193 (100.00%) | 155/156 (99.36%) | 7602/7982 (95.24%) | 3803/3991 |
| `IfuPerfAnalysis` | 711/711 (100.00%) | 21/22 (95.45%) | 112/644 (17.39%) | 56/322 |
| `Ifu`（顶层） | 4053/4053 (100.00%) | 1648/1652 (99.76%) | 30590/34924 (87.59%) | 15918/17462 |

完整原生表与逐点报告位于忽略目录 `results/20261030T022604Z-107cb685/`（约 29 MB，
不进入 Git）。Git 中保留小而可审计的摘要
[`coverage-summary.md`](coverage-summary.md)（由同一份 `coverage.json` 生成）：逐 DUT
命中/总数、全部未覆盖行与分支臂的原文，以及按信号族归并的未跳变 toggle 位。

证据哈希：`ifu/manifest.json` `ed329e6ac60de482…`、`ifu/coverage.json`
`49078ddec9a6cd01…`、`cases/ifu/cases.json` `ac446744e9534925…`、功能点报告
`4404a60525737b35…`。`coverage-summary.md` 中记录 `coverage.json` 的完整 sha256，
可据此核对重跑结果是否同一份证据；其余哈希在对应运行目录中用 `sha256sum` 复核。

## 逐模块闭环

### RvcExpander

1. 初版 9 个功能点、11 个用例：line 100%、branch 100%、toggle 95.89%。
2. 缺口：`io_out_s_load_opc[5]`、`[6]` 从未跳变。定位为“栈加载 rd=x0 时的保留
   操作码选择”这一情况未枚举（已有功能点 006 的缺失情况）。
3. 补：reserved 用例中交替 `c.lwsp(rd≠0)` 与保留编码，使选择子两态都出现。
4. 重跑仍为 140/146：该 7 位选择子实际只会取 `7'h3`/`7'h1F`，bit5/bit6 在两值中
   相同，属**结构常量**而非漏测。原因记入下方“结构性残留”。

### InstrBoundary——6 个功能点、10 个用例

1. 初版 line 100%、branch 153/154、toggle 91.71%。
2. 缺口：偏移坐标高位在部分 lane 从未变化（每 lane 的 `startOffset[4]` 等只有
   在块内偏移足够大时才非零）。归类为功能点 002/006 的**情况枚举缺失**。
3. 补 offset 坐标扫描（`size0` 从 1 到 32，覆盖每个 lane 的每个块内偏移）。
4. 结果：toggle 2015/2196（91.76%）。剩余为 lane 宽度截断导致的**结构常量**
   （如 lane 0 的偏移高位恒 0）与 `blockSel[0]`（槽 0 必属第一块）。

### PredChecker——7 个功能点、12 个用例

1. 初版：line 101/105（96.19%）、branch 16/24（66.67%）、toggle 60.06%。
2. 缺口定位：
   - 故障位置只落在低 lane → 高 lane 的优先级编码/目标选择未覆盖（功能点 003/006
     情况缺失）；
   - 目标加法只落在低地址 → GuardedPc 高位与溢出未覆盖（功能点 004 情况缺失）；
   - lane 35 的 PC 端口被综合保留但无指令端口 → 该数据通路位固定（结构）；
   - `wbValid` 的复位 `else` 位于 `ENABLE_INITIAL_REG_` 的一次性初始化块（结构）。
3. 补：故障位置 0..34 全扫、窗口尾部各故障类、目标算术跨界（`2^50`、`2^51-2`、
   进位）、lane35 PC 伪随机激励。
4. 迭代结果：96.19→100% line；66.67→95.83% branch；60.06→98.84→99.85% toggle，
   最终 99.81%（lane35 的 3 位随随机序列未再次跳变，属仿真随机性而非结构常量）。

### IfuUncacheUnit——8 个功能点、11 个用例

1. 首轮即 line 100%、branch 15/16、toggle 100%。
2. 唯一未覆盖分支是 `ENABLE_INITIAL_REG_` 初始化块的 `if (reset)` else 臂
   （复位在时刻 0 必为高），结构不可达。
3. 过程中补充的**情况枚举**：非幂等类型组合（isMmio×PBMT）、总线反压/IFU stall、
   corrupt/denied 四种状态、四阶段 flush、空闲期迟到响应、完成当拍接受下一请求。

### FrontendTrigger——7 个功能点、15 个用例

1. 初版：line 100%、branch 99.36%、toggle 43.79%。
2. 缺口定位：
   - PC 只落在低地址 → 比较器高位与 carry 路径未覆盖（功能点 002 情况缺失）；
   - 动作只在少数 lane 命中 → 逐 lane 动作 mux 未覆盖（功能点 006 情况缺失）；
   - 只有 trigger0 被配置 → 其余三个比较器副本未覆盖（功能点 001/003 情况缺失）。
3. 补：PC 全域随机、128 字节边界扫描（跨低/高半 carry）、每个 trigger 副本各自
   配置与 select 门控、动作逐 lane 扫描。
4. 结果：toggle 43.79→93.23→96.34%；第三轮加入“tdata2 超出地址空间”两条定向反例
   并启用 64 位 tdata2 的 `RW(63,0)` 视角后，把随机域收缩到机器可生成地址，读数为
   95.24%。下降来自不再对 DUT 根本不比较的高 14 位做无意义跳变，不是覆盖退化；
   恢复对高位的观察需要先修 R-13。
   branch 在加入随机 PC 后一度降到 80.13%，
   因为随机窗口不再命中“单 trigger 全 lane”分支；逐 lane 扫描后回到 99.36%。
   这条说明 branch 百分比会随场景结构变化，必须结合端点语义判断，不能只追数字。
5. 第三轮按 [观察点精度](../../../../skills/design/observation-precision.md) 重扫
   生产者/消费者宽度：CSR 侧 `Tdata2Bundle.ALL = RW(63,0)` 可写可读回 64 位，而
   `TriggerCmp`/`TriggerCmpConsecutive` 只比较 `tdata2[VAddrBits-1:0]`。原模型也把
   `tdata2 & PC_MASK`，属于照抄实现，所以随机用例从未暴露差异。改为全 64 位比较后
   新增两条定向反例（`2^50+pc` 的 EQ、`2^50` 的 LT），**当前 FAIL**，记为 R-13，
   根因与修复方向见 [bug 记录](bugs/frontend-trigger-tdata2-width.md)。
   这不是覆盖缺口，而是合同不一致；在修复前该 DUT 的功能结论只覆盖 tdata2 高 14 位
   为 0 的配置。

### IfuPerfAnalysis——7 个功能点、9 个用例

1. 首轮：line 100%、branch 95.45%、toggle 17.39%。
2. 缺口定位：DUT 端口只暴露 10 个理由位（FTQ 2/3/5/6/7/8/9、ICache 10、ITLB 11、
   回写 BTB 12），其余 68 个理由位在本配置中**没有任何驱动端口**（SC/BTB 后端端口
   被裁剪）。因此 3×68+68=272 个理由位恒 0，toggle 上限约 17.4%。
3. 验证可达位：stage0 覆盖 {2,3,5,6,7,8,9,12}（10/11 由设计只在 stage1 注入），
   stage1/2 覆盖全部 10 个可达位，输出覆盖全部 10 个。即**可达理由位 100% 覆盖**。
4. 结论：该 DUT 的 toggle 百分比是**端口配置导致的结构上限**，不是用例缺失；
   已在功能点 004 描述中注明 SC/BTB 无端口。

### Ifu 顶层组合——11 个功能点、50 个用例

| 轮次 | 本轮补充 | line | branch | toggle |
|---|---|---|---|---|
| 1 | 基础单/双块、对齐、跳转截断、反压、flush、异常、uncache、trigger | 88.30% | 63.44% | 18.79% |
| 2 | 密集压缩窗、32 lane 满窗、跳转类/条件分支、块1归属 | 99.85% | 74.94% | 43.72% |
| 3 | 随机满窗（地址/数据位）、ECC、uncache 错误与跨页 resend | 99.95% | 81.17% | 47.35% |
| 4 | 随机化压缩程序（地址/数据位大量跳变） | 99.95% | 81.17% | 76.83% |
| 5 | 高 lane 32 位指令、PC 进位 | 100.00% | 81.66% | 77.95% |
| 6 | 指令类别逐 lane 扫描、跨块 split 全扫 | 100.00% | 95.16% | 83.94% |
| 7 | uncache 对齐/属性/间接类、高 lane cross-block、稀疏编码 | 100.00% | 97.15% | 86.27% |
| 8 | uncache 在多次入队后 | 100.00% | 99.46% | 86.77% |
| 9 | uncache 指针回绕、47/48 条边界 | 100.00% | 99.76% | 86.94% |
| 10 | 负对照、pruned 端口审计、双向追溯、激励合法性、guard 交接探测（环境点） | 100.00% | 99.76% | 87.59% |
| 11 | 观察点精度重扫：`tdata2` 全宽比较（模型不再复制 RTL 截断）| 100.00% | 99.76% | 87.59% |
| 12 | 增加“tdata2 超出地址空间”两条定向反例；随机域收缩到机器可生成地址 | 100.00% | 99.76% | 87.59% |
| 13 | 把 `isBackendException`/`hasSatpFlush` 从“仅读取”改为逐拍比较 + 三组定向（R-11 缩窄为“消费不在本层”） | 100.00% | 99.76% | 87.59% |

逐项归类：

- **line 88.30→100%**：缺口全部是“已有功能点的情况枚举不足”，没有发现整个功能点
  缺失。按类：
  1. 跨块/截断取指（功能点 002/011 情况）→ 补 32 lane 满窗、split 1..30 全扫、
     截断窗口 + carry 续取；
  2. 重定向类别（功能点 005）→ 补 direct/conditional/indirect/return/invalid-taken
     在 lane 0..30 的逐位扫描；
  3. uncache 路径（功能点 009）→ 补属性、总线错误、跨页 resend、对齐后写 bank；
  4. 高 lane 归属（功能点 004/002）→ 补 block1 在 lane 32..34、块内 PC 进位；
  5. 逐 lane 压缩展开/预测（功能点 002）→ 补随机满窗与稀疏编码逐 lane。
- **branch 63.44→99.76%**：残留 4 个臂全部结构不可达（见下）。
- **toggle 18.79→87.59%**：残留主要是逐 lane 数据/PC 位与 top-down 理由位；前者
  需要每 lane 每位的两向跳变，后者受端口裁剪限制（顶层 `toIBuffer.topdownInfo`
  只有 76 位理由中的部分位被 PerfAnalysis 驱动）。第 10–12 轮额外提升约 0.65 个百分点来自
  guard 交接探测驱动的 51 位 PC/异常路径，不是删改断言得来的。

### 新增功能点（覆盖分析直接产出）

- `IFU-TOP-011`：跨两个取指窗口的 32 位指令恰好组装一次。原先只有 `IFU-IB-004/005`
  描述“报告半指令 / 跨块一条指令”，但顶层把半指令记录到 `prevEndHalfRviInfo`、下一
  窗口拼装并只入队一条的端到端行为没有功能点，属于**整体功能点缺失**而非情况缺失；
  补点后新增截断窗口 + carry 续取的用例。
- 其余 line 缺口的消除来自情况枚举而非新功能点：`uncache` 跨页 resend 用例（功能点
  009 的情况）消除了 `s1_prevIBufEnqPtrDup`/`s1_prevEndHalfRviInfo` 的 4 条未覆盖行；
  lane 34 的 PC 进位两类用例（功能点 002/004 的情况）消除了最后 2 条未覆盖行。
- `IFU-TOP-008` 的 GPF 地址写回、`IFU-TOP-009` 的跨页 resend 是对已有顶层功能点的
  细化，不新增 ID。
- 第三轮按观察点精度重扫又补了三类：生产者/消费者宽度（`tdata2` 64 位 vs 比较 50 位，
  产出 R-13 两条 FAIL）、只读未比字段（`isBackendException`/`hasSatpFlush` 改为逐拍
  比较）、以及 1 位标量端口的宽度陷阱（`mWidth==0` 但端口存在，`read_pruned` 只按
  属性存在性判断）。
- 第二轮新增 5 个 `IFU-ENV-*` 验证环境功能点（pruned 端口、负对照、追溯、激励合法性、
  交接面探测），与硬件功能点分开统计；它们不提高硬件通过率，只把“检查本身可信”
  变成可执行证据。

## 未证明范围如何进入证据（残余登记）

第一轮把 PASS/FAIL/XFAIL/SKIP 当成全部状态，导致“没测到”的部分不占任何格子：报告
只有 55/55 PASS 和 0 SKIP，读起来像“只剩一个点没测”。现在分两条通道：

1. **用例跑过但只覆盖功能点的一部分** → 当前用 Toffee 的
   `@pytest.mark.uncertain(reason=..., reference=...)` 显式声明，判定为
   `UNCERTAIN`。第三轮使用过 ucv 的声明式 INCOMPLETE，旧记录保留原义。
   本工程 `IFU-TOP-011` 的跨窗口组装用例属于这种：它确实执行并检查了
   “窗口末尾断在低半”的 carry，但其它 carry 位置/指令类别没测，所以不能算 PASS。
   UNCERTAIN 让通过率低于 100%，真实 FAIL/ERROR 永远优先；它本身不改变退出码。
2. **没有用例可跑**（端口装不下、本层不负责、组合未构造）→ 残余登记。

实际未证明项分六类：

| 类别 | 为什么不能进 PASS/FAIL | 例子 |
|---|---|---|
| `defect` | 有 FAIL 用例，但需要一个已登记的缺陷对象 | R-13 `tdata2` 宽度 |
| `unproven-scope` | 行为点存在，但只测了部分组合 | R-09 carry 位置、R-10 输入侧复核 |
| `observation-limitation` | 字段未导出，无法直接比较 | R-12 `toIBuffer.pc` 等 |
| `out-of-domain` | 本层无法表达或消费 | R-08 guard PC、R-11 标记消费 |
| `structural` | 有证明的常量/不可达 | R-01..R-05 |
| `coverage-limit` | 度量上限，不是行为缺口 | R-06、R-07 toggle |

这些项登记在 `verification_plan.json` 的 `residuals`，插件把它们写进功能点报告并做
一致性检查：有 `blocking` 且 `open` 的残余时不允许硬件全 PASS；有 FAIL 时必须存在
blocking 残余。`ucv run` 再把它们写进 `run.json`，`ucv report` 汇总到
`summary.json`/`summary.md` 的“Residual register”一节；因此只读运行摘要的人也能看到
“未证明范围”，而不是只能从 PASS/FAIL 表猜测。若某轮所有用例 PASS 但仍有
`blocking + open` 残余，硬件判定会降为 `INCOMPLETE` 并给出原因。

## 门禁与负对照（第二轮补充）

本轮新增 30 个环境用例（`tests/framework/` 28 个 + `tests/ifu/test_ifu_guard_handoff.py`
2 个），总执行数由 112 增至 142。它们不改变硬件覆盖数字，但把“比较器
真的在比较”“删除端口不是默认 0”“功能点与用例双向可追溯”“非法激励被拒绝”
变成可执行门禁。

第一轮的“全绿”只能证明用例跑过，不能证明比较器会报错，也不能证明被删除的端口
没有被默认为 0。按执行/复核方法补充四个可执行门禁（均为 `IFU-ENV-*`，不计入硬件）：

0. **独立 oracle 的区分力**（`tests/framework/test_oracle_independence.py`，ENV-002）：
   用四个“冻结的错误算法”跑同一组比较——忘记压缩寄存器 +8 重映射的 RVC 解码、
   “每槽都是指令起始”的边界模型、“所有 taken 都合法”的预测合同、
   “所有非缓存访问都等待”的 uncache 顺序——要求 DUT 与正确模型一致、与错误算法
   不一致；并随机 500 字确认错误算法确实在大范围内与正确算法不同。
1. **负对照**（`tests/framework/test_checker_discrimination.py`，ENV-002）：对 7 个
   DUT 分别取真实观测，先确认未篡改期望通过，再注入“期望错误”或“观测错误”，要求
   同一个检查函数抛出 `AssertionError`。覆盖：RVC 展开字与非法位、InstrBoundary 的
   valid/end mask/cross 标记、PredChecker 的 target/重定向 valid、UncacheUnit 的
   req_ready、Trigger 的逐 lane 动作、PerfAnalysis 的理由位、IFU 的 enq/指令字/
   taken。注入层在测试内注明，不冒充 RTL mutation。
2. **pruned 端口审计**（`tests/framework/test_pruned_ports.py`，ENV-001）：harness
   不再提供“缺端口读默认 0”的接口；`read_pruned/set_pruned` 遇到实际存在的端口直接
   失败，并记录声明的常量。三个删除端口各有模型级证明：
   - InstrBoundary 槽 31 的 cross 标记：模型对每个 split、每个起始位置扫描，最后
     一槽恒为 0（跨块指令在 31 槽需要不存在的 32 槽）；端口因此被删除；
   - PredChecker lane 34 的 cross 输入：shift=3 时 lane 34 只对应压缩后的 index 31，
     该 index 不可能跨块；同扫描中 lane 33 可以为 1，证明功能本身是活的；
   - IFU lane 35：对齐填充恒 0，故 `instrEndOffset_35_predTaken` 被删除，入队掩码
     的 bit35 恒 0。
3. **双向追溯**（`tests/framework/test_traceability.py`，ENV-003）：每个功能点必须
   被至少一个测试引用，每个测试必须引用已声明功能点；每个组件至少有一条完整实现
   记录（requirement/oracle/observations/controls/tests/residual），记录里的 nodeid
   必须真实存在。当前 7 个组件各有 1–2 条记录。
4. **激励合法性**（`tests/framework/test_stimulus_legality.py`，ENV-004）：错位 PC、
   压缩位与编码不一致、超过 32 槽、非法 carry-in、异常/属性越界都在夹具边界抛错；
   端口地址单位（PC 为 `[50:1]`、GPA 为字节）由 `signals.json` 断言，防止模型与
   DUT 单位漂移。

## 接口交接残余与上游差分（ENV-005）

上游 `b716aade`（2026-10-27，基线后第 57 个提交）修正了 IFU 的两处 PC 截断并把
`FrontendRedirect.pc` 从 `VAddrBits` 加宽到 `GuardedVAddrBits`。本基线是它的
pre-image（逐行一致），因此：

- 探测（`tests/ifu/test_ifu_guard_handoff.py`）：`startVAddr` 为 guard=1 的
  `GuardedPc(2^51-2)` 时，`toFtq.wbRedirect.pc` 输出低 50 位
  `0x3FF_FFFF_FFFF_FE`，而正确值应为 `0x7FF_FFFF_FFFF_FE`；同拍 51 位 `target`
  仍正确，说明截断只发生在 `pc` 字段。非缓存重定向走同一路径。
- 等级：**out-of-domain（本 DUT 交接面限制）**。端口只有 50 位，DUT 无法表达正确
  值，不能据此判 IFU 行为违规；上游补丁说明该截断在系统层会产生错误 PC。
- 处置：`IFU-ENV-005` 记录探测与适用范围，硬件 PASS 明确不覆盖 guard=1 的 PC
  交接；升级基线后该测试会因端口宽度断言失败，强制重新判定。详见
  [上游差分复核](upstream-review-20261029.md)。

## 证据等级与归因（按复核方法）

| 事项 | 等级 | 原假设 → 证据 → 修正 | 成对复验 |
|---|---|---|---|
| Verilator 复位后寄存器随机化 | `confirmed-verification` | 假设“复位已清 FSM”→ `IfuUncacheUnit` 复位后 `io_req_ready=0`、捕获地址为随机值且 3 次重跑一致 → 实为生成代码 `initial` 块在时刻 0 之后仍施加随机值；改用 `+verilator+rand+reset+0` 并显式复位 | 修前该 DUT 11 个用例全失败；修后全过，且 `read_pruned` 会拒绝把真实端口当常量 |
| GuardedPc/GPA 端口为半字地址 | `confirmed-verification` | 假设“端口是字节地址”→ PredChecker 目标比较得到 `0x4151b594e516` 而非 `0x1000`、GPA 观测值差 2 倍 → 端口字段为 `[N:1]`；模型与激励统一用字节地址、驱动时右移一位 | 修前目标比较失败；修后 51 位目标算术边界用例通过，负对照能拒绝被篡改的 target |
| “预测指向 RVI 前半即为 invalid-taken” | `confirmed-verification` | 假设“只要在指令中间就 invalid”→ 用例失败，模型判定为 not-CFI-taken → 规则是“块在 RVI 前半结束且该位置被预测 taken”才是 invalid；修正用例并保留两条区分性场景（块内结束 vs 窗口末尾） | 两条用例分别断言 invalid-taken=1 / 0，负对照确认比较器会比较该位 |
| uncache 指针回绕需要 47 条以上在飞指令 | `uncovered-functional`（补情况） | 假设“50 条已覆盖回绕”→ 分支仍显示 `_diff>−1` 未命中 → 入队 47/48 条边界各跑一次 | 补后该分支命中，且后续 uncache 重定向目标仍正确 |
| `FrontendTrigger` 的 `tdata2` 只比较 50 位 | `confirmed-rtl`（R-13） | 假设“比较 50 位即可”→ 模型也把 tdata2 掩码到 50 位，随机配置因概率极低从未命中高位差异 → 按“生产者 64 位 / 消费者 50 位”重扫并构造 `tdata2=2^50+pc`、`tdata2=2^50`：EQ 在 pc 处命中、LT 全不命中 | 模型改为全 64 位；同步保留 in-range 随机对照，两条定向用例持续 FAIL，直到 RTL 或 CSR 合同修正 |

第一轮未发现 `confirmed-rtl` 级缺陷；第二轮按观察点精度重扫后，**发现一个真实
RTL 偏差（R-13，`confirmed-rtl`）**：`FrontendTrigger` 只比较 `tdata2[49:0]`，而
CSR 暴露 64 位可写字段。该失败保留为 FAIL，不登记 XFAIL。其余历史失败仍归因为
验证环境/模型/用例假设，并在修正后保留成对对照。结论不能外推为“IFU 无缺陷”。

## 结构性残留（逐项定位，不冒充已覆盖）

| DUT | 残留 | 定位 | 判定 |
|---|---|---|---|
| 全部 | `if (reset)` 的 else 臂（1 个分支/DUT） | `ENABLE_INITIAL_REG_` 的一次性 `initial` 寄存器随机初始化块 | 复位在时刻 0 必为高，else 不可达；与功能行为无关 |
| RvcExpander | `io_out_s_load_opc[5]`、`[6]` | 选择子只取 `7'h3`/`7'h1F`，两值在 bit5/bit6 相同 | 结构常量（负对照证明其余位会比较） |
| InstrBoundary | `blockSel[0]` 条件臂、各 lane 偏移高位 | 槽 0 恒属第一块；5 位偏移字段对低 lane 高位恒 0 | 结构常量/宽度截断；slot 31 另经模型全扫证明（ENV-001） |
| PredChecker | lane35 PC 的 3 个数据位 | lane35 无指令端口，仅 PC 加法器存在 | 数据相关，非结构；已用随机 PC 覆盖其余 50 位 |
| Ifu | `select_35`、`rvcExpanders_35`、L7914 的 `blockSel[0]` 臂 | 第 36 个入队 lane 被 IFU 显式置 0；lane 0 恒属第一块 | 结构常量；lane35 的 predTaken 端口删除经用例证明（ENV-001） |
| Ifu | `toFtq.wbRedirect.pc` 的 guard 位 | 端口 50 位，内部 PC 51 位 | **out-of-domain 接口限制**；上游 `b716aade` 已修、本地未含（ENV-005） |
| Ifu | `gpAddr` 高位、逐 lane PC/数据位、`toIBuffer.topdownInfo` 理由位 | 需每 lane 每位的双向跳变；topdown 只驱动部分理由位 | 覆盖成本高/受端口限制，已记录不追平 |
| IfuPerfAnalysis | 272 个理由位 | 端口只暴露 10 个理由位 | 结构上限；可达位 100% 覆盖 |

## 复现

```sh
# 1) 构建（缓存命中时直接校验哈希）
.venv/bin/ucv build ifu --jobs 8
# 2) 运行并产出 toffee 原生覆盖率清单
.venv/bin/ucv run ifu --workers 1
# 3) 行/分支/toggle 报告（始终在仓库根，替换本次 run 目录）
.venv-uc-toffee/bin/python suites/frontend/ifu/tools/coverage_report.py \
  --manifest results/<run>/ifu/manifest.json \
  --output results/<run>/coverage.json \
  --markdown results/<run>/coverage.md
# 4) 功能点判定汇总（由 pytest 插件写回工程根）
cat suites/frontend/ifu/results/feature-points.json
```

注意：`ucv run` 会记录运行期间的源码哈希；运行前后修改仓库文件会得到
run 状态 `ERROR`、汇总为 `INCOMPLETE`（source changed during execution），不会得到
PASS/UNCERTAIN 正常退出。这是有意的完整性检查，不是覆盖率失败。
