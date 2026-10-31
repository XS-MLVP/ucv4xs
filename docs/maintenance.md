# 维护与验收

更新 RTL 时新建完整命名基线，先在分组或工程目录显式引用，完成适配后再调整根默认引用。变更源码、子模块、配置、补丁或生成工具版本都会产生新的缓存身份。统一公开验收使用严格基线检查。

开始新模块或修改模型、检查器时，从 [经验索引](lessons/README.md) 查阅相关历史案例。新复盘保留原错误假设、合法与错误成对对照、实际检查入口及证据边界；模块细节放在本工程 `docs/`，跨模块可复用的方法补入 `skills/` 并更新索引。历史文档中的项目策略和结果保留原适用范围。

新增 DUT 时修改工程 `ucv.json` 的 `duts`，给出真实生成模块名和导出类名。新增测试放在对应工程独立的 pytest 根目录中；领域模型和检查器不跨工程共享。共用工具能力放在 `src/ucv/`。

回归失败应保留原始 FAIL、ERROR、XFAIL 和 XPASS，不为取得全绿而扩大 xfail 或删除测试。判定报告分别记录：

- 迁移与重建验收：空缓存生成、所有原生 DUT 冒烟、框架对比、路径与资产完整性、并行行为。
- 硬件验证判定：本次实际执行的逐用例结果、覆盖率和验证缺口。

同一 RTL 的框架迁移要逐用例比较集合与判定；BPU 等发生源码版本变化的工程单列差异。历史 RTL 无法精确复现时，保留差异并独立验收新产物，不能把历史结论改标成新基线结论。

当前优先交付结构整合版，以目录、配置、隔离入口、资产边界和编排层检查作为阶段门槛；已知 FAIL/XFAIL/SKIP 和未完成的 BPU 适配保留在 [阶段状态](status.md)，不阻塞结构版提交。`v0.1.0-structure` 只标识这一阶段，不能作为完整迁移或硬件验收标签。

后续完整迁移与重建验收凭据应同时关联当前验证源码提交、运行报告哈希、完整工具版本、RTL/native 哈希、已登记失败及差异分析。只有证据齐备后才建立验收标签。常规代码测试：

```sh
.venv/bin/python -m pytest tests
```

## 结果保留与空间回收

覆盖率当前按每个 worker 累积 16 个输入文件触发合并；默认合并成功后删除已消费输入，完整收尾后清理 worker 中间目录。异常中断会保留未完成数据。按字节限制合并缓冲和异常后的自动回收尚未实现。

在用户要求的清理范围内确认进程不再使用目标，保留判定、必要日志、版本和删除清单。未完成运行的数据被回收后标明覆盖率输入不可用；原历史状态不改写为成功。2026-10-28 已按要求清理一轮异常 BPU 调试的 224 个覆盖率文件，释放约 25.8 GiB，见 [回收记录](history/storage-reclamation-20261028.json)。

第一版没有 CI。原工作区是迁移前历史对照，不由新工具修改。大量波形、FIRRTL、生成 RTL 和原生库不进入 Git。

## 验证包布局与自检分类

十个工程当前把 fixture 集中在 `tests/conftest.py`，无子目录 conftest 或 env/pytest.py
转发。它是项目默认，不是 pytest 的通用语法限制。功能用例的事务边界还需单独验收：
P.p_* / P.io(...) 别名仍是 pin-level，不能用隐藏端口字面量替代协议适配；物理映射
优先在 DUT 的 ports/bundle，共享机制按 runtime/drivers/monitors 等职责命名。
工程根本身为 suites.<group>.<suite> 包，不保留 *verify/common 外壳。`selftest` 由共享插件
`ucv.pytest_selftest` 按 `framework/`、`checkers/`、`selftest/`、`diagnostics/` 目录标记，
不计硬件功能 credit，但保留真实执行结果。

```sh
.venv/bin/python scripts/audit-suite-layout.py --strict
.venv/bin/python -m pytest -q tests/test_suite_layout.py
.venv/bin/python scripts/audit-suite-layout.py --require-transaction-boundary
.venv/bin/python scripts/audit-skills.py --strict --check-framework
```

结构 --strict 与事务边界分别报告；目前六个工程仍有真实引脚级耦合，不能为全绿
关闭检测。清理只删除无活动使用的可再生产物，保留受管结果、收据与真实失败。
2026-10-31 清理了 22 个松散仿真文件和 596 个缓存目录，297830621 字节，见
[删除清单](history/storage-reclamation-20261031.json)。此前过宽的迁移结论及修正见
[结构与 skill 复核](lessons/structure-skill-review-20261031.md)。

## 残余登记进入运行报告

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
`reason` 必填，框架的 `reference` 可选且不限格式；IFU 为了保持工程追溯，进一步要求
它指向尚未解决的残余。UNCERTAIN 本身不改变退出码，只有 PASS/UNCERTAIN 且没有其他
阻塞或错误时返回 0；**退出码 0 不等于验证全部通过**。

`INCOMPLETE` 留给执行、产物或验收要求未完成，不用于声明“执行完但证据不足”。旧
`@pytest.mark.incomplete` 已停止接受；历史收据里的 `declared_incomplete` 仍按原义读取，
不把旧运行改写为 UNCERTAIN。UNCERTAIN 的覆盖率正常收集，可与
`manifest.state="committed"` 同时出现；进程崩溃或缺阶段不能改标 UNCERTAIN。

测试状态只描述已执行用例；未尝试或无法运行的范围（端口装不下、本层不负责）没有
对应状态。工程可在 `verification_plan.json` 声明 `residuals`，`ucv run` 会把它写入
`run.json` 的 suite 记录，`ucv report` 汇总为 `residuals` / `residual_summary`，并在
`summary.md` 的“Residual register”一节列出。存在 `blocking=true` 且
`acceptance=open` 的残余时，即使全部用例 PASS，硬件判定也降为 `INCOMPLETE` 并在
`Verification gaps` 说明原因——残余不能用登记本身换取通过。
