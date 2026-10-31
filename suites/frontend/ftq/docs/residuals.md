# FTQ 残余与退出状态（2026-10-30）

本文件按 [退出与残余](../../../../skills/design/closure-and-residuals.md) 的字段记录。
“已执行”不等于“整个 FTQ 无缺陷”；下面每项都有证据或明确未验证原因。

| ID | 行为/类 | 缺口类别 | 影响 | 证据 | 承接/下一动作 | 阻塞 |
|---|---|---|---|---|---|---|
| R-01 | ResolveQueue 分支槽 > 8 条 | 真实 RTL 缺陷（`confirmed-rtl`） | 第 9 条/同拍超量会覆盖已有分支，BPU 训练载荷错误 | `docs/bugs/resolve-queue-branch-overflow.md`；两个 strict XFAIL | 设计修复后增加容量守卫；重跑两个 XFAIL、全量与覆盖 | 对“超容量正确丢弃”是；对其余队列语义否 |
| R-02 | Ftq 顶层闭包中 ResolveQueue 的 IFU 命中 fallback | **已关闭**（2026-10-30） | 上一轮顶层行覆盖 97.4% | `results/ftq-final-20261030b/coverage-report/coverage.json`：`ftq` 行 51996/51996 = 100.0%；顶层矩阵用例逐物理槽 × 分支槽 × 来源枚举 | 若以后新增 RTL/端口，仍需按新闭包重跑矩阵 | 否 |
| R-03 | 三个 DUT 的 `initial` reset else | 测试台不可达初始化分支 | 不影响运行期功能；三个模块行覆盖均 100% | `ResolveQueue.sv:12172`、`CommitQueue.sv:4089`、`Ftq.sv:110865` | 不补；它是 Verilator 初始化块语义 | 否 |
| R-04 | Toggle 残余（RQ 2135、Ftq 23532） | 未覆盖 payload/高位方向 | 不改变已检查的控制/所有权语义；可能掩盖高位数据通路问题 | `coverage-gaps.md` 的 `v_toggle` 列表；本次 `resolve_queue` 89.2%、`ftq` 84.4% | 若要求 100% toggle，按信号位补全 1/0；当前保留 | 仅对“100% toggle”目标 |
| R-05 | 生成 RTL 未保留 `XSError` 等断言 | 观察点限制 | 非法输入不会被 RTL 自检；外部指针监视器只覆盖所有权不变量 | 三份闭包 `grep $fatal` 均为 0；`suites/frontend/ftq/monitors/cycle.py` 的 `InvariantMonitor` | 保持外部监视器；若需要保留断言，评估 firtool 选项并更新缓存身份 | 对“非法输入自检”是；对合法域功能否 |
| R-06 | 异常标记在第二个 fetch block 的检查 | 合同内不可达/疑似冗余 | `backendFlagPtr === pfPtr(1)/fetchPtr(1)` 在当前 `pnr ≤ bpu` 与重定向复位 fetch 的合同下未构造出合法序列 | 分析见 `requirements-boundary.md`；两个检查在 RTL 中存在但未单独命中 | 保留为分析项；若上游合同变化再补可达性证明 | 否（当前配置） |
| R-07 | 上游差分 | 按用户要求**有意不执行** | 未检查更新版 XiangShan 是否已修复 R-01 或改变 FTQ 合同；结论只对锁定 commit 成立 | 本次只使用 `public-893e1580b` | 若后续需要判断“上游是否已修”，再按 `review/upstream-diff-and-residuals.md` 建候选表 | 对“与最新上游一致”是 |
| R-08 | ICache/IFU/BPU/后端的消费行为 | 当前 DUT 边界外 | FTQ 输出正确不等于整机取指/预测训练正确 | 只验证 FTQ 边界；上层模型/检查器不在本工程 | 由对应工程承接；不把本工程 PASS 扩成整机结论 | 对整机验收是 |
| R-09 | 顶层 3 个同拍 IFU 合并 mux 臂 | 顶层结构不可达 | `ResolveQueue.sv:2587/2589/2591` 的 `enqIndex_0/1/2` 选择臂在 `Ftq` 中不可同拍触发；不影响顶层已检查的 IFU 重定向/训练语义 | `ftq` 闭包分支 1616/1622；独立 `resolve_queue` 同拍四源用例已覆盖同一 RTL 逻辑，只剩 reset else | 保留为结构不可达分类；若未来 FTQ 改为同拍 IFU resolve，再补顶层用例 | 否（当前配置） |

## 退出判断

- 本工程当前约定范围：三个 DUT 的合法输入功能点、时序竞争、复位、重定向、背压、
  容量（8 分支以内）和 64 索引 meta。
- 在该范围内：`109 PASS`，`2 XFAIL`（R-01 的两个独立表现），`0 FAIL`，`0 SKIP`。
- 顶层闭包行覆盖已达到 **100.0%**（R-02 关闭）；`Ftq` 自身未覆盖行保持 0。
- 不能宣称“FTQ 无缺陷”或“整机取指正确”：R-01 是已确认 RTL 缺陷；R-04 是
  toggle 缺口；R-05/R-07/R-08/R-09 是观察、上游、上层或结构不可达边界。
- 若验收门槛包含“超容量解析绝不破坏已有训练分支”，当前状态为未通过，需修复 RTL
  后重跑；若门槛是“顶层闭包行 100%”，本轮已满足，但必须连同 2 个 XFAIL 一起陈述。
