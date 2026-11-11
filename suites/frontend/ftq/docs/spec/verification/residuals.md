# FTQ 残余与退出状态（2026-10-30，2026-11-08 新基线更新）

本文件按 [退出与残余](../../../../../../skills/design/closure-and-residuals.md) 的字段记录。
“已执行”不等于“整个 FTQ 无缺陷”；下面每项都有证据或明确未验证原因。

**2026-11-08 更新**：下表 R-01..R-09 的 2026-10-30 数字和源码仍按
`public-893e1580b` 保留。`public-a0c2a26cb` 复检结论：

- R-01 仍在：`ResolveQueue.sv`/`.scala` 字节相同；可达性追踪确认每拍
  3 backend + 1 IFU、跨拍 9 条和“6+3”同拍组都是合法生产者序列；两个 strict
  XFAIL 以 `--runxfail` 仍真实 FAIL
  （`results/ftq-a0c2a26cb-closeout-runxfail-20261108`）。
- R-03 同类初始化 else 新增 `PrefetchQueue.sv:468`；运行期复位不可达。
- R-04 更新为 `resolve_queue` 17587/19708、`commit_queue` 1364/1364、
  `ftq` 128620/152622（新增队列 toggle 已纳入归因）。
- R-07 已执行本轮上游差分：仅 `4b9f938b7`（软件预取）和 `b716aade5`（PC guard）
  触及 FTQ；R-01 未被修复。
- **R-09 已关闭**：三个顶层 mux 臂不是结构不可达，已由
  `test_ftq_ifu_backend_merge.py` 在合法序列下覆盖；旧分类是测试台假设错误。

当前完整判定为 **931 PASS / 2 XFAIL**（933 nodeid，seed1/seed2 一致），
剩余 **6** 个分支计数（4 个 distinct 初始化 reset else；leaf 与 Ftq 闭包重复计），
未覆盖行 0。完整判定和覆盖见[新基线适配记录](reports/baseline-adaptation-a0c2a26cb.md)。

| ID | 行为/类 | 缺口类别 | 影响 | 证据 | 承接/下一动作 | 阻塞 |
|---|---|---|---|---|---|---|
| R-01 | ResolveQueue 分支槽 > 8 条 | 真实 RTL 缺陷（`confirmed-rtl`） | 第 9 条/同拍超量会覆盖已有分支，BPU 训练载荷错误 | `docs/bugs/open/resolve-queue-branch-overflow.md`；两个 strict XFAIL | 设计修复后增加容量守卫；重跑两个 XFAIL、全量与覆盖 | 对“超容量正确丢弃”是；对其余队列语义否 |
| R-02 | Ftq 顶层闭包中 ResolveQueue 的 IFU 命中 fallback | **已关闭**（2026-10-30） | 上一轮顶层行覆盖 97.4% | `results/ftq-final-20261030b/coverage-report/coverage.json`：`ftq` 行 51996/51996 = 100.0%；顶层矩阵用例逐物理槽 × 分支槽 × 来源枚举 | 若以后新增 RTL/端口，仍需按新闭包重跑矩阵 | 否 |
| R-03 | 三个 DUT 的 `initial` reset else | 测试台不可达初始化分支 | 不影响运行期功能；三个模块行覆盖均 100% | `ResolveQueue.sv:12172`、`CommitQueue.sv:4089`、`Ftq.sv:110836`（2026-10-30 记为 110865；行号按当前闭包更正），2026-11-08 新增 `PrefetchQueue.sv:468` | 不补；它是 Verilator 初始化块语义 | 否 |
| R-04 | Toggle 残余（RQ 2121、Ftq 24002） | 未覆盖 payload/高位方向 | 不改变已检查的控制/所有权语义；可能掩盖高位数据通路问题 | 2026-11-08 `coverage-gaps`：`resolve_queue` 17587/19708、`commit_queue` 1364/1364、`ftq` 128620/152622 | 若要求 100% toggle，按信号位补全 1/0；当前保留 | 仅对“100% toggle”目标 |
| R-05 | 生成 RTL 未保留 `XSError` 等断言 | 观察点限制 | 非法输入不会被 RTL 自检；外部指针监视器只覆盖所有权不变量 | 三份闭包 `grep $fatal` 均为 0；`suites/frontend/ftq/testbenches/shared/env/monitors/cycle.py` 的 `InvariantMonitor` | 保持外部监视器；若需要保留断言，评估 firtool 选项并更新缓存身份 | 对“非法输入自检”是；对合法域功能否 |
| R-06 | 异常标记在第二个 fetch block 的检查 | 合同内不可达/疑似冗余 | `backendFlagPtr === pfPtr(1)/fetchPtr(1)` 在当前 `pnr ≤ bpu` 与重定向复位 fetch 的合同下未构造出合法序列 | 分析见 `requirements-boundary.md`；两个检查在 RTL 中存在但未单独命中 | 保留为分析项；若上游合同变化再补可达性证明 | 否（当前配置） |
| R-07 | 上游差分 | **已执行（2026-11-08，限 FTQ 路径）** | 未修复 R-01；FTQ 行为只受 `4b9f938b7`（软件预取队列）和 `b716aade5`（PC guard）影响，ResolveQueue/CommitQueue 字节不变 | `public-a0c2a26cb` 检出；`git log 893e1580b..a0c2a26cb -- src/main/scala/xiangshan/frontend/ftq`；本轮 RTL/Scala 差分 | 结论只对锁定 commit 成立；不据此外推其他前端模块 | 对“与最新上游一致”是 |
| R-08 | ICache/IFU/BPU/后端的消费行为 | 当前 DUT 边界外 | FTQ 输出正确不等于整机取指/预测训练正确 | 只验证 FTQ 边界；上层模型/检查器不在本工程 | 由对应工程承接；不把本工程 PASS 扩成整机结论 | 对整机验收是 |
| R-09 | 顶层 3 个同拍 IFU 合并 mux 臂 | **已关闭（2026-11-08，原分类错误）** | 旧结论把“IFU resolve 经 `RegNext`”误当成“同 `ftqIdx` 不可同拍”。实际 IFU 重定向后一拍的后端同索引报告可与其共同创建 entry，`hitPrevious(3)` 选中 `enqIndex(0/1/2)` | `test_ftq_ifu_backend_merge.py` 的 1 个四源控制 + 3 个 lane 参数化用例；`ftq` 分支 1718/1722，`ResolveQueue.sv:2587/2589/2591` 已命中 | 保留用例；若后续 RTL 改变 IFU resolve 时延，重新评估 | 否（已关闭） |

## 退出判断

- 本工程当前约定范围：三个 DUT 的合法输入功能点、时序竞争、复位、重定向、背压、
  容量（8 分支以内）和 64 索引 meta。
- 在该范围内：`109 PASS`，`2 XFAIL`（R-01 的两个独立表现），`0 FAIL`，`0 SKIP`。
- 顶层闭包行覆盖已达到 **100.0%**（R-02 关闭）；`Ftq` 自身未覆盖行保持 0。
- 不能宣称“FTQ 无缺陷”或“整机取指正确”：R-01 是已确认 RTL 缺陷；R-04 是
  toggle 缺口；R-05/R-07/R-08 是观察、上游、上层边界；R-09 已关闭（原分类错误）。
- 若验收门槛包含“超容量解析绝不破坏已有训练分支”，当前状态为未通过，需修复 RTL
  后重跑；若门槛是“顶层闭包行 100%”，本轮已满足，但必须连同 2 个 XFAIL 一起陈述。
