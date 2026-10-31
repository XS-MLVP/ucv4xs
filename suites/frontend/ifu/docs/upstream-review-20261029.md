# 基线之后的上游变更复核（2026-10-29）

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

## 未纳入本次的候选

- 查询只覆盖 `frontend/ifu` 路径与其直接交接（`frontend/Bundles.scala`、
  `frontend/ftq/IfuRedirectReceiver.scala`）。更早的提交或 `Frontend.scala`、
  `ftq/` 其他文件未逐一评估，列为下一轮：
  同样方法查询 `frontend/ftq`、`frontend/icache` 路径，确认 IFU 输入侧
  （ICache 请求/异常编码、FTQ 重定向）是否有基线后变化。
- open issue 未查询；提交名相似不等于已修，本表只接受“补丁 pre-image 与本地一致”
  的候选。

## 下一步

1. 若计划升级基线：把 `public-893e1580b` 替换为包含 `b716aade` 的命名基线，重新
   生成 RTL、重建 7 个 DUT、重跑本工程；届时 `pc` 端口应为 51 位，
   `test_redirect_pc_drops_the_guard_bit_on_this_baseline` 必须改为“保留 guard”的
   正向断言（该测试会以端口宽度断言失败，正好阻止静默沿用旧结论）。
2. 若不升级：在残余登记中保留该限制与上游证据，不以“已 PASS”覆盖。
3. 每次升级后复核本轮 `docs/coverage-loop.md` 中的结构常量结论是否仍成立。
