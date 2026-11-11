# 退出标准与残余登记

## 完成判定

本工程在以下条件同时满足时视为当前单元范围交付：

- 三个 DUT 在 `public-a0c2a26cb` / DefaultConfig 上 `BUILT + SMOKE PASS`；
- 功能点账本无 `NOT_RUN`，所有硬件点有用例；真实 FAIL/ERROR 原样保留；
- 每个功能点有独立 oracle、driver、monitor、checker 和用例；
- 完整集合至少一个定向 seed 与一个独立 seed 的结果记录，nodeid 可对账；
- 覆盖闭环：逐 DUT line/branch/toggle，未覆盖项逐项归因；
- 根 pytest、布局/技能/资产门禁通过；
- 结论不超出 InstrUncache 单元，不把叶子通过写成 Frontend/芯片验收。

## 当前状态

| 项 | 状态 |
|---|---|
| prepare/build/smoke | 3/3 PASS |
| seed 1 完整集合 | 68 PASS / 0 UNCERTAIN / 0 FAIL / 0 ERROR（68 nodeid） |
| seed 2 完整集合 | 68 PASS / 0 UNCERTAIN / 0 FAIL / 0 ERROR（68 nodeid） |
| 硬件功能点 | 13/13 PASS |
| 环境功能点 | 4/4 PASS（含 `INC-FLUSH-012` 结构证据） |
| 覆盖 | line 100%、branch 13/14、toggle Entry 628/664、顶层 1165/1230 |
| `ucv report` | `run_status=PASS`、**`hardware_verdict=INCOMPLETE`**（`FRONTEND-FLUSH-CONNECT` blocking/open）、`migration_acceptance=NOT_CERTIFIED` |
| 根门禁 | pytest 270 PASS；layout/skills/assets 通过 |

`hardware_verdict=INCOMPLETE` 是用户确认的保守口径：DefaultConfig 下可达的单元行为
全部 PASS，但 `Frontend` 把 `instrUncache.io.flush` 恒接 `false.B` 的设计决定没有
owner 签字、也没有 Frontend 级集成验证（`FRONTEND-FLUSH-CONNECT`）；因此不能读成
“flush 已验证”或硬件 PASS。`migration_acceptance=NOT_CERTIFIED` 是仓库级既有口径，
需要单独的迁移/重建验收证据。

上述 `ucv report` 字段对应 2026-11-08 的冻结运行。当前运行不再读取旧计划残余，
报告按实际用例和 `docs/bugs/` 问题快照判定。
[FRONTEND-FLUSH-CONNECT](../../bugs/open/FRONTEND-FLUSH-CONNECT.md) 已按 `kind=spec`
正式登记并保持当前基线 open；带 `acceptance_source='issue-records'` 的新运行因此
保留纯 PASS 用例计数，但汇总为 `INCOMPLETE`。本规格中的其余边界仍须逐项核对。

## R-FLUSH 收口（2026-11-08）

**最终分类：out-of-domain / accepted-limited。** 依据：

- `Frontend.scala:266` 是 `instrUncache.io.flush := false.B`；全仓库唯一实例在
  `Frontend.scala:125`；`SimFrontendInlinedImp` 也把整个 `instrUncache.io` 接 0，
  且 `EnableSimFrontend` 默认 false；
- Entry 的 `flush` 端口、`needFlush` 寄存器以及受它门控的响应/转移分支
  （`InstrUncacheEntry.scala:41,58-63,100,162`）在生成闭包中被完全裁剪；
- `InstrUncache.sv`、`InstrUncacheEntry.sv` 均无 `flush`/`needFlush` 文本，
  `Frontend.sv` 的 `inner_instrUncache` 实例（L2763）也没有 flush 连接；
- 机器证据与哈希在 [`docs/spec/verification/evidence/flush-closure.json`](evidence/flush-closure.json)，
  由 `tools/audit_flush_closure.py` 复核。

这不是“结构不可达 = 已验证”：`INC-FLUSH-012` 现在是**验证环境分区**的结构检查点，
只验证裁剪事实与哈希一致，不是行为验证；它不再以 `uncertain` 形式登记，也不计入
硬件通过率。flush 期间/迟响应的取消语义仍未证明。

**用户已确认保守口径**：即使单元可达行为全部 PASS，`Frontend` 把
`instrUncache.io.flush` 恒接 `false.B` 的设计决定没有设计 owner 签字，也没有
Frontend 级集成验证，因此新增 `FRONTEND-FLUSH-CONNECT`（blocking/open，owner
`frontend/design`），整体 `hardware_verdict` 保持 **INCOMPLETE**。只有设计 owner
确认 `false.B` 是永久意图并入合同，或补上真实 flush 连接/删除端口后，才能重新
评估该残余。

跨配置边界：本分类只对 `public-a0c2a26cb` / DefaultConfig 成立。其他配置或后续
RTL 若把 flush 接实、改变 `nMmioEntry`/`MmioBusWidth`/PMA 上限，或重新生成导致
哈希变化，必须重新 prepare/build、重跑双 seed、更新证据文件并单独标注。

## 残余登记

工程根的 `verification_plan.json` 已删除；下表保留已有范围标识、结构证据和待确认项，
由本规格与合同维护。`UNCERTAIN` 不是 PASS，`NOT_RUN` 不是通过；accepted-limited
记录的是已接受的验证边界，不是“关闭后自动变成 PASS”。真实缺陷及复验状态进入
[问题记录](../../bugs/README.md)，不把结构出域或设计待确认直接归为 RTL 缺陷。

| ID | 行为/缺口 | 类别 | blocking | 验收 |
|---|---|---|---|---|
| `R-FLUSH` | DefaultConfig 下 flush 恒 0，Entry 的 flush/needFlush 取消路径不可达；仅证明结构裁剪，不验证行为 | out-of-domain | 否 | accepted-limited |
| `FRONTEND-FLUSH-CONNECT` | Frontend 恒接 `false.B` 的设计决定无 owner 签字、无 Frontend 级集成验证 | out-of-domain | **是** | open |
| `R-READY-PRUNED` | response/D/grant ready 恒 1，合法反压不可构造 | structural | 否 | accepted-limited |
| `R-A-CONST` | A 的 opcode/param/size/source/mask/data/corrupt/echo 由 `edge.Get` 与 8B 对齐固定 | structural | 否 | accepted-limited |
| `R-DATA-X` | corrupt/denied 响应的 data 为 don't-care，不比较 | observation-limitation | 否 | accepted-limited |
| `R-ADDR47` | A 地址 bit47 固定 0；合法 PMA 上限 2^43 | out-of-domain | 否 | accepted-limited |
| `R-SRC-OUT-OF-RANGE` | source=1 是唯一 source 0 之外的鲁棒性对照 | out-of-domain | 否 | accepted-limited |
| `R-COV-INIT` | 初始化块 `if (reset)` else 在仿真中不可达 | structural | 否 | accepted-limited |
| `R-COV-TOOL` | 顶层结构模块/纯组合 Arbiter 无 line/branch 插桩 | coverage-limit | 否 | accepted-limited |
| `R-COV-TOGGLE` | 地址高位/对齐常量不产生 toggle | coverage-limit | 否 | accepted-limited |

## 关闭/重开条件

- `R-FLUSH` 保持 accepted-limited；若未来要在本单元声称 flush 行为，必须出现
  可驱动的 flush 配置（不在当前基线），并重新给出 flush 期间/响应返回后的取消与
  迟响应证据，同时更新 `docs/spec/verification/evidence/flush-closure.json` 和配置边界说明；
- 任何新 RTL FAIL 必须保留反例并在 `docs/bugs/open/` 记录调查与归因，不能删除反例、放宽断言或
  登记 XFAIL 换取全绿；
- 覆盖提升必须来自合法场景或结构证据，不能用非法高位地址/非对齐激励刷 toggle；
- `tools/audit_flush_closure.py` 或 `testbenches/instr_uncache/tests/framework/test_flush_closure_evidence.py`
  失败时，先重新审查 R-FLUSH，而不是改写期望或删除检查。

## 明确不在范围

Frontend 的 flush/redirect 组合、ICache/IFU 集成、真实 L2/TileLink 反压、
`nMmioEntry > 1`、其他基线/配置、芯片级验收。
