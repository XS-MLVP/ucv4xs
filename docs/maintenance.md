# 维护与验收

本页解释不同检查能证明什么、不能证明什么。要实际选跑、找日志或比较两次结果，见
[运行指南](how-to/run-tests.md)；报告字段与退出码见[工作空间参考](reference/workspace.md#报告字段与退出码)。
当前工程进展只在[状态页](status.md)维护，不从本页的历史例子推断现状。

## 为什么不能用一个“通过”概括全部结果

| 证据层次 | 可以说明 | 不能单独说明 |
|---|---|---|
| 文档/结构/资产检查 | 登记路径、目录归属、生成入口、跟踪资产符合工具规则 | 合同充分、事务时序正确或硬件无缺陷 |
| build + smoke | 当前身份的 DUT 可构建、加载、复位和步进 | 功能用例、字节来源或覆盖闭环通过 |
| 实际 case 判定 | 本次选择在该基线、源码、种子下的执行结果 | 未选择参数、其它 DUT 或全部需求通过 |
| 事务适配接受 | 已审查调用链保持原合法刺激、采样窗口及独立检查 | 真实 FAIL 已修、整工程硬件签核 |
| 覆盖与工程验收 | 按规格逐项核对需求、观察和证据缺口 | 仅凭行满、模型同答或一个汇总数字自动成立 |

`run_status` 与 `hardware_verdict` 分开：子进程完成且 case 全 PASS 时，开放问题或
覆盖缺口仍可能使硬件汇总为 `INCOMPLETE`。原始 `FAIL/ERROR/XPASS` 优先，不能被较软
的未完成信号降级。`counts` 包含环境/模型自检；自检通过不计硬件功能覆盖提升。
报告中的 `migration_acceptance=NOT_CERTIFIED` 也不会因局部适配审查自动改成全仓认证。

## 维护工作的证据边界

更新 RTL 时新建完整命名基线，先在分组或工程目录显式引用，完成适配后再调整根默认引用。变更源码、子模块、配置、补丁或生成工具版本都会产生新的缓存身份。统一公开验收使用严格基线检查。

开始新模块或修改模型、检查器时，从 [经验索引](lessons/README.md) 查阅相关历史案例。新复盘保留原错误假设、合法与错误成对对照、实际检查入口及证据边界；模块细节放在本工程 `docs/spec/` 或稳定编号的问题记录，跨模块可复用的方法补入 `skills/` 并更新索引。历史文档中的项目策略和结果保留原适用范围。

文档组织与 Bug 生命周期统一遵循[文档维护](how-to/maintain-docs.md)：README 汇总当前入口，
问题只在 `docs/bugs/open/`、`closed/` 维护一份，`ucv docs full --write` 生成汇总，
`ucv check full` 检查关联。工程不新增通用 history 目录；正式迭代由 Git 固定，证据保存于
有身份和哈希的运行存储。已存在的仓库级来源索引继续用于原证据接入。

新增 DUT 使用 `ucv init`，在工程配方中给出真实生成模块名和导出类名。新增测试放在所属
testbench 的 tests；领域模型和检查器留在工程内，共用编排能力放在 `src/ucv/`。

回归失败应保留原始 FAIL、ERROR、XFAIL 和 XPASS，不为取得全绿而扩大 xfail 或删除测试。判定报告分别记录：

- 迁移与重建验收：空缓存生成、所有原生 DUT 冒烟、框架对比、路径与资产完整性、并行行为。
- 硬件验证判定：本次实际执行的逐用例结果、覆盖率和验证缺口。

同一 RTL 的框架迁移要逐用例比较集合与判定；发生设计源码版本变化的工程单列差异。历史 RTL 无法精确复现时，保留差异并独立验收新产物，不能把历史结论改标成新基线结论。

当前优先交付结构整合版，以目录、配置、隔离入口、资产边界和编排层检查作为阶段门槛；已知 FAIL/XFAIL/SKIP 和未完成的 BPU 适配保留在 [阶段状态](status.md)，不阻塞结构版提交。`v0.1.0-structure` 只标识这一阶段，不能作为完整迁移或硬件验收标签。

多人或AI接续开发以 [协作目录约定](../CONTRIBUTING.md) 为统一入口，阶段交接见
[当前状态](status.md)。发布前审查 Git 实际跟踪及拟新增
文件，不把整个工作目录压包；commit/tag 应由实际发布操作确定，文档不预先编造版本哈希。

后续完整迁移与重建验收凭据应同时关联当前验证源码提交、运行报告哈希、完整工具版本、RTL/native 哈希、已登记失败及差异分析。只有证据齐备后才建立验收标签。

公共工具变更的根测试入口为 `.venv/bin/python -m pytest -q tests`。只有使用文档变化
时核对链接、配置、命令和文档检查即可，不为文档维护默认重跑硬件；完整检查选择见
[协作约定](../CONTRIBUTING.md#最小检查集)。

## 结果保留与空间回收

覆盖率当前按每个 worker 累积 16 个输入文件触发合并；默认合并成功后删除已消费输入，完整收尾后清理 worker 中间目录。异常中断会保留未完成数据。按字节限制合并缓冲和异常后的自动回收尚未实现。

在用户要求的清理范围内确认进程不再使用目标，保留判定、必要日志、版本和删除清单。
未完成运行的数据被回收后标明覆盖率输入不可用；原历史状态不改写为成功。
已有回收清单示例见 [2026-10-28](history/storage-reclamation-20261028.json) 和
[2026-10-31](history/storage-reclamation-20261031.json)。

第一版没有 CI。原工作区是迁移前历史对照，不由新工具修改。大量波形、FIRRTL、生成 RTL 和原生库不进入 Git。

## 验证包布局与自检分类

十二工程与新工程使用 schema2 的 `testbenches/<dut>/` 和跨 DUT 的 `testbenches/shared/`；
版本兼容与本轮范围见[目录规范](reference/module-layout.md#schema-版本与本轮范围)。
fixtures/pytest 插件在工程唯一 `conftest.py` 注册，各实现包不另设 pytest 根。
`ucv init` 生成骨架，`ucv check` 按 schema 校验归属与工作入口。功能用例的事务边界还需单独验收：
P.p_* / P.io(...) 别名仍是 pin-level，不能用隐藏端口字面量替代协议适配；物理映射
优先在 DUT 的 env/ports 或 env/bundle；schema2 的真正共享组件放 shared 内对应职责，
DUT 与 shared 同用六职责，单 DUT 专用实现归该 DUT。
工程根本身为 suites.<group>.<suite> 包，不保留 *verify/common 外壳。`selftest` 由共享插件
`ucv.pytest_selftest` 按 `framework/`、`checkers/`、`selftest/`、`diagnostics/` 目录标记，
不计硬件功能 credit，但保留真实执行结果。

```sh
.venv/bin/python scripts/audit-suite-layout.py --strict
.venv/bin/python -m pytest -q tests/test_suite_layout.py
.venv/bin/python scripts/audit-suite-layout.py --require-transaction-boundary
.venv/bin/python scripts/audit-skills.py --strict --check-framework
```

结构 --strict 与事务边界分别报告；命中须按实际功能/自检用途复核，以实际审计为准，不能为全绿
关闭检测、改标签或改写字符串规避。此前将端口别名误当作事务接口的复盘见
[结构与 skill 复核](lessons/structure-skill-review-20261031.md)。

原生 scratch cwd 在执行期 fixture 中切换，不在 pytest_configure 改控制进程 cwd；
默认无显式选择的单/多 worker 收集需要回归，防止从临时目录收集到零项。
原因与反例见[收集与生命周期复盘](lessons/semantic-boundary-repair-20261101.md)。

### 如何理解事务边界检查

**事务适配**是将端口编码、握手、时钟推进、采样和响应关联放进环境适配层，让功能用例
通过公开 agent/env API 表达业务行为，例如发送访存请求、施加背压、接收响应。
实际引脚仍由 driver/ports/monitor 操作；适配需要保持原激励、时序和检查依据。

`audit-suite-layout.py --strict --require-transaction-boundary` 只读扫描 Python 源码，
发现下列表达式后返回 `exit 1`，并标记 `needs-adapter`：

| 列 | 检查什么 | 表达式示例（不是当前残余清单） |
|---|---|---|
| pin expressions | `io_*` 字段、关键字或 `P.p_*` / `P.io(...)` 别名 | 功能场景用物理名字定位输入/观察；普通业务字符串也可能保守命中 |
| signal operations | `.Set()`、`.Step()`、原生句柄等 | 功能场景绕过公开环境直接操作信号或时钟 |
| owner infrastructure | 访问环境内部的 model/driver/checker 或私有 helper | 从参考模型可用槽或预测事件决定下一笔刺激 |

这些数字是**语法命中次数**，同一个用例可有多次命中；它们不等于 RTL 缺陷数、失败用例数，
也不表示测试无法运行。`--strict` 的目录/fixture 检查通过，与这项更强的接口分层要求是
两个检查结果。真实功能判定仍从运行收据读取。

扫描是保守的：按既有自检目录及静态可识别的 `pytest.mark.selftest` 分类，将自检中的
底层访问单列到 JSON 的 `selftest_cases`，保留分类来源、作用域和命中位置。
标记可以放在模块、测试类或单个测试函数上；混合文件中未标记的用例和 helper 仍受检查。
动态标记不能作为排除依据，`toffee_functional_coverage(False)` 也不等于自检。

分类需要核对实际用途：例如 VAGQ 的 `pipeline/tests/test_encoding.py` 专门校验事务到
端口字段的编码，其 `P.p_*` 有合理用途；真实功能场景中的同类访问则需要适配。
检查器不证明分类正确，审查应对照原用例和实际执行链，避免将功能场景误标为自检。
不能把总数直接当成必须改写的测试数量，或只改名字/搬目录消除报告。

对于确认属于功能用例的底层访问，接续工作是补齐公开事务操作及其驱动/采样/比较链，
保留原合法激励和反例并做定向回归。零静态命中也不能单独证明时序、所有权、独立期望
或硬件行为正确。即使人工确认某个业务标签不代表端口访问，原命令的非零退出码也须
保留，人工分类不是扫描PASS。当前结果与范围见[状态页](status.md)。

## 用例判定与未证明范围

用例能够执行，但关键依据、观察能力或覆盖范围尚不足以建立结论时，由 Toffee 显式
声明 `UNCERTAIN`（由锁定的 `uc-toffee 2.1` 正式提供；本地开发版只在显式配置时使用，
见[本地环境](local-configuration.md#本地-toffee-开发环境)）：

```python
@pytest.mark.uncertain(reason="只覆盖窗口末尾一种 carry 位置", reference="R-09")
def test_xxx(dut): ...
```

各阶段正常结束且断言通过后判为 `UNCERTAIN`，不计入 PASS。Toffee 在进度中显示 `U`，
pytest session 摘要单列数量与原因，manifest 记录相同的判定；ucv 复用 Toffee 的判定，
不另造一套标记。断言失败仍是 FAIL，fixture 出错仍是 ERROR，不能与 xfail 叠加。
`reason` 必填，框架的 `reference` 可选且不限格式；需要追溯时引用所属规格条款或问题 ID。
UNCERTAIN 本身不改变退出码，只有 PASS/UNCERTAIN 且没有其他
阻塞或错误时返回 0；**退出码 0 不等于验证全部通过**。

`INCOMPLETE` 留给执行、产物或验收要求未完成，不用于声明“执行完但证据不足”。旧
`@pytest.mark.incomplete` 已停止接受；历史收据里的 `declared_incomplete` 仍按原义读取，
不把旧运行改写为 UNCERTAIN。UNCERTAIN 的覆盖率正常收集，可与
`manifest.state="committed"` 同时出现；进程崩溃或缺阶段不能改标 UNCERTAIN。

测试状态只描述已执行用例；未尝试或无法运行的范围（端口装不下、本层不负责）没有
对应用例判定。功能要求、观察限制、配置适用域和集成缺口维护在工程现有
`docs/spec/verification/`、功能点文档和合同中；真实缺陷及其复验状态维护在
`docs/bugs/`。验收时把实际运行证据与这些条款逐项核对，局部 PASS 不关闭未证明范围。

工程根的 `verification_plan.json` 已删除，当前运行不再要求旧计划或残余清单。
`ucv run` 在开始时冻结现有 `docs/bugs/` 问题记录；对其中位于 `open/` 且在当前基线
仍开放或未复验的问题，`ucv report` 保留实际 case 计数，并将纯 PASS 汇总降为
`INCOMPLETE`，真实 FAIL/ERROR 优先。规格中的配置/观察/集成边界仍须人工核对，
不会仅因未进入问题目录就变成已验证。
该规则只用于显式带 `acceptance_source='issue-records'` 的新运行；没有此标志的
历史运行维持原解释，不追加当前问题的阻塞状态。

功能标记统计来自实际收集标签，显式标为 `scope=collected-test-markers`，只描述该次
所选用例关联的标识，不代表完整计划分母、需求穷尽或未选择功能已经通过。
历史收据中的 `residuals`、`residual_summary`、`Residual register` 以及由此产生的
`INCOMPLETE` 仍是原版本的事实，按原日期、基线和选择范围解释；删除计划不是缺陷修复
或新一轮硬件通过证据。
