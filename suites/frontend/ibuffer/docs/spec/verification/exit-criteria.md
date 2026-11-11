# 退出标准与残余

## 退出条件

本工程在以下条件同时满足时视为本层闭环：

1. 两个 DUT 均完成统一基线 `prepare/build` 和独立进程冒烟，闭包保留真实
   `VTypeGen`/`VSetFuncUnit` RTL。
2. 功能点账本 23/23 有独立 oracle、定向用例和区分性错误对照；硬件 19/19 PASS，
   环境 4/4 PASS。
3. seed 1 与 seed 2 完整回归实际执行，nodeid 一致，无 FAIL/ERROR/XFAIL/XPASS/
   SKIP/UNCERTAIN。
4. 覆盖逐 DUT 输出 line/branch/toggle；未覆盖项按情形缺失、功能点缺失、结构
   不可达或工具边界归因，补点后重跑。
5. 根门禁、布局 strict、技能 strict、资产审计通过；严格事务边界既有 exit 1
   保留，本工程自身为 exit 0。
6. 结论边界明确为 `IBuffer`/`VTypeGen`、DefaultConfig、`public-a0c2a26cb`。

当前状态：以上 1–6 均满足；残余全部非阻塞，`migration_acceptance=NOT_CERTIFIED`
是因为它不是 Frontend/芯片验收，而不是本层有未解释的失败。

## 残余登记

| 残余 | 类别 | blocking | acceptance | 证据与下一步 |
|---|---|---|---|---|
| `R-OBS-PERF` | coverage-limit | 否 | accepted-limited | 9 个 `io_perf_*` 是性能事件计数器；没有公开的逐周期累加合同。需要时另立性能 oracle |
| `R-OBS-PC` | observation-limitation | 否 | accepted-limited | `pc/isLastInFtqEntry/debug_seqNum` 不在生成输出端口；需要观察点时另加导出 |
| `R-LANE-PAD` | structural | 否 | accepted-limited | IFU `FetchBlockInstNum=32`，36-lane 的 32..35 是 padding，不产生有效载荷 |
| `R-EXC-SINGLE` | out-of-domain | 否 | accepted-limited | `FetchToIBuffer` 只有一组前端异常；同拍多异常不是合法 IFU 激励 |
| `R-VILL-PAYLOAD` | observation-limitation | 否 | accepted-limited | keep-vl 保留情形只置 `illegal=1` 并保留 payload；本层把 vill 下 payload 视为接口 don't-care，CSR 清零属于 Backend/CSR |
| `R-TOPDOWN` | structural | 否 | accepted-limited | `btbMissBubble/scMissBubble` 未导出，模型按 0 处理；导出后需扩展 |
| `R-VSETVL-OVERLAP` | out-of-domain | 否 | accepted-limited | VSETVL（funct7=0）是 VSETVLI 子模式；VTypeGen 不区分，提交时冲刷丢弃 |
| `R-COV-INIT` | structural | 否 | accepted-limited | `ENABLE_INITIAL_REG_` 的 `if (reset)` else 在 time 0 不可达 |
| `R-FRONTEND` | out-of-domain | 否 | accepted-limited | Frontend redirect/FTQ/ICache、`satpFlushFirstFetchFault` 消费者、后端 vtype 消费不在本层 |
| `R-CONFIG` | out-of-domain | 否 | accepted-limited | 只覆盖 DefaultConfig（1 core、VLEN=128、ELEN=64、Size=48、EnqueueWidth=36） |

这些条目说明当前配置的验证适用范围和观察限制，未登记为已确认缺陷。工程根的
`verification_plan.json` 已删除，运行不再要求该副本或残余一致性门禁。
新缺陷及复验状态维护在[问题记录](../../bugs/README.md)；上述边界继续由本节与合同说明，
删除旧计划不扩大本层 PASS 的适用范围。

## 明确不证明的范围

- Frontend 级 redirect/flush 与 IBuffer 的交互；本工程只验证 IBuffer 的 `io_flush`
  输入及其内部效果。
- FTQ/ICache 产生的 `prevInstrCount`、`exceptionMask`、beats 的真实时序；本工程
  按合法 IFU 域建模并驱动。
- `satpFlushFirstFetchFault`、`backendException`、`crossPageIPFFix`、vtype/specvtype
  在 Backend/CSR 的消费和架构可见性。
- 其他配置（不同 VLEN/ELEN、IBuffer Size、EnqueueWidth、bank 数）和芯片验收。

这些不是本层 PASS 可以覆盖的内容，不能把本工程结果写成 Frontend 或后端验收。
