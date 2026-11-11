# ICache 验证规格

状态：`public-a0c2a26cb` / DefaultConfig 的 11 个 DUT 已完成统一基线构建、双 seed
完整回归和覆盖复核；**不是整机或硬件签核**。本页是当前验证入口，详细证据和逐项
归因链接到各正文。

## 范围与假设

- DUT：`waylookup`、`replacer`、`mshr`、`databank`、`metabank`、`metaarray`、
  `dataarray`、`missunit`、`mainpipe`、`prefetchpipe`、`icache`。
- 整块 `ICache` 与子块平级验证；闭包保留真实子模块 RTL。其他配置、Frontend/后端
  消费、真实 L2 和芯片验收不在本层。
- 功能要求、参考模型、合法激励和观察点边界维护在既有规格、事务合同与覆盖正文，见
  [设计规格](../design/README.md)与[错误复核](error-review.md)。
- 工程根的 `verification_plan.json` 已删除；下方 142 个功能点的统计属于原回归，
  由相应报告追溯，不是删除计划后新增的执行证据。

## 当前结果

| 项 | 结果 |
|---|---|
| prepare/build | 11/11 `PREPARED`，11/11 `BUILT + SMOKE PASS` |
| seed 1 | **572 PASS / 1 XFAIL**，exit 0（573 节点 = 571 硬件 + 2 selftest） |
| seed 2 | **572 PASS / 1 XFAIL**，exit 0，逐 nodeid 判定与 seed 1 相同 |
| 功能点 | 142/142 有用例判定 |
| 唯一非 PASS | `WAYLOOKUP-020` strict XFAIL，真实 RTL 缺陷仍在 |

`ICACHE-012`（stale `vSetIdx`）已由上游 `4b9f938b7`（#6691）修复，改为普通正向用例；
`ICACHE-030`（软预取合并未接受 FTQ 请求）的接口退役，nodeid 保留并改写为 FTQ
`PrefetchQueue` 承接的“未完成握手不得触达内存”合同。两者的历史失败记录保留在
[错误复核](error-review.md)与[新基线记录](reports/baseline-update-a0c2a26cb.md)，不重标。

## 验证内容

| 主题 | 入口 |
|---|---|
| 构建身份、RTL 差分、逐 nodeid 对账、事务与覆盖 | [新基线适配记录](reports/baseline-update-a0c2a26cb.md) |
| 错误复核、模型修正与 RTL/结构边界 | [错误复核](error-review.md) |
| 整块 ICache 覆盖闭环 | [icache-coverage-closure](coverage/icache-coverage-closure.md) |
| line / branch / toggle 三类覆盖 | [coverage-line-toggle-branch](coverage/coverage-line-toggle-branch.md) |
| 子块覆盖闭环 | [WayLookup](coverage/waylookup-coverage-closure.md)、[Replacer](coverage/replacer-coverage-closure.md)、[MissUnit](coverage/missunit-coverage-closure.md)、[MainPipe/PrefetchPipe](coverage/mainpipe-prefetchpipe-coverage-closure.md)、[SRAM 类 DUT](coverage/sram-dut-coverage-limitation.md) |
| DataBank/MetaBank 事务适配 | [DataBank](transactions/databank-transaction-adaptation.md)、[MetaBank/SRAM](transactions/metabank-transaction-adaptation.md) |
| 历史交付报告（893e1580b） | [verification-report](reports/verification-report.md) |
| 历史工程快照（893e1580b） | [legacy README](evidence/legacy-readme-20261031.md) |
| 通用验证经验 | [verification-lessons](lessons/verification-lessons.md) |
| 问题状态 | [问题索引](../../bugs/README.md) |

## 完成条件与缺口

- 当前唯一 blocking 功能缺陷是 `WAYLOOKUP-020`；未修复前不得把 ICache 写成全绿。
  整块 ICache 中该路径不可达，但模块级合同仍被违反，strict XFAIL 必须保留。
- 覆盖率残余的分类和处置见各覆盖闭环；toggle 大量未覆盖位属于 payload/存储位或
  合法域外，不得用非法激励追数字。
- 全仓 `--require-transaction-boundary` 仍因其他工程既有债务 exit 1；本工程自身为
  0 pin/signal/owner 访问，不据此声称全仓事务闭合。
- 结果目录不进入 Git；结论只对锁定基线、DefaultConfig RTL、实际源码/原生包和相应
  seed 成立。
