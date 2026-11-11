# 基线之后的上游变更复核（2026-10-29）

> **2026-11-07 后续**：本文件记录的 `b716aade` 已随基线 `public-a0c2a26cb` 并入。
> 该基线相对 `893e1580b` 前进 63 个提交（`git rev-list --count` = 63），其中触及
> `frontend/` 的只有 4 个：`b716aade5`（PC guard 位）、`4b9f938b7`（iprefetch part 1）、
> `05f65879a`（MBTB hidden VBTB）、`4381195af`（TLB needGpa 冻结）。IFU 七个 DUT 中
> 六个 `.sv` 逐字节不变，`Ifu.sv` 只差 3 条赋值的 PC 位宽/截断（见下）。
> **R-08 已关闭**：`IFU-ENV-005` 由“记录截断”改为正向对照，并新增第二块 block-select
> 与“仅 bit50 不同”的区分对照；硬件 PASS 不再排除 guard=1 的重定向 PC。
> 下面的 2026-10-29 记录保持原日期与原结论，作为历史证据。

对固定基线 `public-893e1580b` 的 IFU 相关路径做一次有界复核。目的不是升级基线，
而是回答：

1. 基线之后上游是否改过本工程验证的 IFU 行为？
2. 若有，本层观察点能否复现该变化？
3. 当前 PASS 结论是否需要收缩适用范围？

## 查询记录

| 项目 | 值 |
|---|---|
| 查询日期 | 2026-10-29 |
| 本地基线 | `893e1580b705d81f113c30c7a05734e09a08050e`（2026-10-16，`perf(param): enlarge ROB size to 160 (#6730)`） |
| 本地缓存引用 | `.cache/sources/972e31a…` 的 `origin/kunminghu-v3` 与基线相同，无更晚引用 |
| 上游查询 | GitHub API `commits?path=src/main/scala/xiangshan/frontend/ifu&since=2026-10-16` 与 `compare/893e1580b...b716aade` |
| 比较结果 | `status=ahead, ahead_by=57, behind_by=0`，`merge_base_commit` 即基线 |

## 候选表

| 问题/提交 | 本地/上游版本 | 祖先/补丁检查 | 涉及本工程的行为 | 探针及结果 | 原用例盲点 |
|---|---|---|---|---|---|
| `b716aade` `fix(core): carry true PC guard bit (#6751)`，2026-10-27 | 本地为 pre-image；上游为 post-image | 基线是 merge base，该提交在其后 57 个提交中；补丁 pre-image 与本地逐行一致（`Ifu.scala:665`、`:739` 的 `toUInt(VAddrBits - 1, 0)`；`frontend/Bundles.scala:139` 的 `pc: UInt = UInt(VAddrBits.W)`） | 前端重定向 PC 丢失 `GuardedPc` 的 guard 位：写回重定向与非缓存重定向都会把 51 位 PC 截成 50 位后交给 FTQ；`FrontendRedirect.pc` 同时仍是 50 位 | `tests/ifu/test_ifu_guard_handoff.py`：输入 `startVAddr = GuardedPc(2^51-2)`（guard=1），DUT 输出 `wbRedirect.pc = 0x3FF_FFFF_FFFF_FE`（低 50 位），而模型 PC 为 `0x7FF_FFFF_FFFF_FE`；同拍 51 位 `target` 仍正确 | 原有 `IFU-TOP-005/009` 用例的取指 PC 全部 guard=0，未覆盖 guard 位交接 |

## 结论等级

- 该候选为 **out-of-domain（本 DUT 交接面限制）**：在本基线上 `pc` 端口只有 50 位，
  DUT 无法表达带 guard 的正确值，因此不能把“观察到截断”判成 IFU 行为违规。
- 上游补丁与提交信息（`mepc has a spurious bit 50`、错误值
  `0x0007ffffffffffc0` vs 正确 `0x0003ffffffffffc0`）说明该截断在系统层会生成错误
  PC；这是“上游已修、本地未含”，不是本地动态确认的 RTL 违规。
- 因此本工程硬件 PASS 的适用范围明确排除“guard=1 的重定向 PC 交接”；该限制以
  `IFU-ENV-005` 记录，不计入硬件功能点通过率。
  （以上为 2026-10-29 在 `893e1580b` 上的结论；2026-11-07 升级到含 `b716aade` 的
  `public-a0c2a26cb` 后已改为正向对照，R-08 关闭，见文首注记。）

## 未纳入本次的候选

- 查询只覆盖 `frontend/ifu` 路径与其直接交接（`frontend/Bundles.scala`、
  `frontend/ftq/IfuRedirectReceiver.scala`）。更早的提交或 `Frontend.scala`、
  `ftq/` 其他文件未逐一评估，列为下一轮：
  同样方法查询 `frontend/ftq`、`frontend/icache` 路径，确认 IFU 输入侧
  （ICache 请求/异常编码、FTQ 重定向）是否有基线后变化。
- open issue 未查询；提交名相似不等于已修，本表只接受“补丁 pre-image 与本地一致”
  的候选。

## 下一步

1. ~~若计划升级基线~~ **已于 2026-11-07 执行**：`public-a0c2a26cb` 含 `b716aade`，
   RTL 已重新生成、7 个 DUT 已重建、完整回归已重跑；`pc` 端口为 51 位，
   `tests/ifu/test_ifu_guard_handoff.py` 已改为“保留 guard”的正向断言并新增两条
   对照，端口宽度断言按下述机制强制重判（旧断言按 50 位写成，基线一变即失败，
   本轮先以 `test_signal_schema_confirms_the_halfword_address_unit` 报出，已同步更新）。
2. 若不升级：在残余登记中保留该限制与上游证据，不以“已 PASS”覆盖。
3. 每次升级后复核本轮 `docs/spec/verification/coverage/coverage-loop.md` 中的结构常量结论是否仍成立。
