# IBuffer / VTypeGen 验证规格

状态：`public-a0c2a26cb` / DefaultConfig 的双 seed 验收已闭环；`NOT_CERTIFIED` 是因为
本工程不是 Frontend/芯片验收，而不是本层有未解释的失败。本页是当前验证入口。

## 范围与假设

- DUT：`vtype_gen`、`ibuffer`；四层/顶层层次与配置见[设计规格](../design/README.md)。
- 顶层闭包保留真实 `VTypeGen`/`VSetFuncUnit` RTL；参考模型只提供期望。
- 合法输入域来自 RISC-V V 规范、IBuffer/VTypeGen 接口合同和 IFU 实际搬运域；
  padding lane、单异常组和多异常同拍不是合法 IFU 激励。
- 功能要求、oracle 与实现关联见[功能点](../design/functional-points.md)及
  [设计合同](../design/contracts.md)，沿用 23 项（硬件 19 + 环境 4）的说明。
- 工程根的 `verification_plan.json` 已删除；下方功能点数字属于原双 seed 回归，
  当前运行的标签统计只覆盖实际收集集合。

## 当前结果

| 项 | 结果 |
|---|---|
| prepare/build | 两个 DUT 均 `BUILT + SMOKE PASS` |
| seed 1 | **83 PASS / 0 FAIL / 0 XFAIL / 0 SKIP / 0 UNCERTAIN** |
| seed 2 | **83 PASS**，nodeid 与 collection SHA 同 seed 1 |
| 功能点 | 23/23 PASS（硬件 19/19，环境 4/4） |
| 覆盖 | `vtype_gen` line 163/163、branch 104/106、toggle 1226/1596；`ibuffer` line 4177/4209、branch 666/726、toggle 18524/20252 |

结果目录：`results/ibuffer-seed1-final5`、`results/ibuffer-seed2-final5`。覆盖口径、
逐文件数字和缺口归因见[覆盖率闭环](coverage/coverage-loop.md)与
[覆盖摘要](coverage/coverage-summary.md)。RTL/工具身份、实际命令和逐 DUT 判定见
[验证报告](reports/verification-report.md)。

## 验证内容

| 主题 | 入口 |
|---|---|
| 合同与合法输入 | [设计合同](../design/contracts.md) |
| 功能点、oracle、driver/monitor/checker | [功能点](../design/functional-points.md) |
| 覆盖率闭环与逐类缺口 | [coverage-loop](coverage/coverage-loop.md) |
| 覆盖数字摘要 | [coverage-summary](coverage/coverage-summary.md) |
| 构建/运行/工具身份 | [verification-report](reports/verification-report.md) |
| 缺陷与设计边界观察 | [defects](defects.md) |
| 退出标准、残余和结论边界 | [exit-criteria](exit-criteria.md) |
| 问题状态 | [问题索引](../../bugs/README.md) |

## 完成条件与缺口

- 本层退出条件 1–6 均已满足：双 DUT 构建/冒烟、23/23 功能点、双 seed 完整回归、
  逐 DUT 覆盖、根门禁与结构检查、明确结论边界。
- 无 blocking/open 残余；`R-FRONTEND`、`R-CONFIG`、`R-LANE-PAD`、`R-OBS-PERF` 等
  为非阻塞边界。完整清单见[退出标准](exit-criteria.md)。
- 未覆盖行/分支/toggle 均有结构不可达、合法域外、工具 don't-care 或随机深度归因；
  没有为了数字驱动非法激励。
- 未证明：Frontend redirect/FTQ/ICache 交互、`satpFlushFirstFetchFault` 消费者、
  真实 CSR vtype 写入、其他 VLEN/ELEN 或 IBuffer 尺寸配置、芯片验收。
