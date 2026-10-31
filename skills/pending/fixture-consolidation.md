---
name: fixture-consolidation
description: 把每 DUT 的 env/pytest.py 和子目录 conftest 收敛到 pytest 根 fixture，补齐 agent 事务 API、selftest 标记和布局审计。适用于测试直接操作引脚、fixture 分散或新增 DUT 时复制接线代码。
---

# Fixture 集中与 agent 边界（待审核）

## 何时使用、准备什么

- 每个 DUT 有一个 `env/pytest.py`，每个 `tests/<dut>/conftest.py` 只是转发；
- 测试在 scenario 或 testcase 中直接写 `agent.dut.clock`、`.pins`、物理端口名；
- 新增 DUT 时复制了上一份 conftest，fixture 名称开始漂移；
- 想确认功能用例是否真的只通过 agent 事务 API 访问 DUT。

准备：该工程的 pytest 根、验证包、`pytest.ini`、当前测试收集结果。先跑审计：

```sh
.venv/bin/python scripts/audit-suite-layout.py
```

只读报告会列每工程的 root fixture、嵌套 conftest、`env/pytest.py` 和直接访问数。
迁移完成后再用 `--strict` 作为门禁。

## 目标布局

```text
suites/<group>/<suite>/
├── __init__.py             # suites.<group>.<suite>，只定义资源根
├── <dut>/                  # agent/ports/driver/monitor/checker/types 等按需落位
├── runtime/                # 跨 DUT 生命周期机制（复杂时才用包）
├── pytest_plugins/         # 项目插件（可无）
├── tests/
│   ├── conftest.py          # 每个 DUT 唯一的 agent fixture
│   └── <dut>/testcase/      # 只调用 agent 事务 API
├── pytest.ini               # feature / selftest / estimated_runtime 标记
└── docs/                         # 工程合同与证据
```

审计入口 `scripts/audit-suite-layout.py` 在仓库根，不在各工程。该示例的包名不是
强制目录拼写；唯一 Python 命名空间和领域职责隔离才是要求。

`env/` 可以保留 DUT 级辅助（例如 reset 序列、目标错误注入），但不再定义 pytest
fixture；非 agent 的 pytest fixture（产物目录、诊断开关）放到
`pytest_plugins/*.py` 插件，并在根 conftest 的 `pytest_plugins` 注册。小工程可直接用
fixtures.py，不为统一外观创建空包。

## 操作步骤

1. **盘点**：列出 `*/env/pytest.py` 和 `tests/*/conftest.py`，确认每个 fixture 的名字、
   依赖和是否被测试使用。输出目录类 fixture 若无人使用，直接删除，不要搬成死代码。
2. **搬 agent fixture**：在 `tests/conftest.py` 导入 agent 类和 `agent_fixture`，
   逐个赋值。保留每个 DUT 的 `max_batch_ticks`，不要统一成一个猜测值。
3. **搬非 agent fixture**：复杂实现放进已有支持模块；简短 fixture 可以留在根
   conftest。只做注册表是偏好，不是 pytest 语法限制，避免为了禁止函数定义多造一层。
4. **删除转发层**：删掉 `tests/*/conftest.py` 和 `<dut>/env/pytest.py`。
   删除前用 `grep -rn 'env.pytest'` 确认没有导入残留。
5. **补 agent API**：测试里的 `agent.dut.clock` 改成 agent 方法（如
   `await agent.wait_cycles(n)`）；需要精确时序的已知缺陷探针，把整段协议封装成
   agent 事务/精确对齐 API；不要把完整场景和所有断言藏进不透明的一次调用。
6. **标 selftest**：注册共享插件 `ucv.pytest_selftest`，它按 `framework/`、`checkers/`、
   `selftest/`、`diagnostics/` 路径自动加 `pytest.mark.selftest`；在 `pytest.ini` 注册
   marker。自检不计硬件功能 credit，但不改写既有功能点报告的分类规则。不要为每个工程
   复制一份插件。
7. **加布局门禁**：把“根 fixture 唯一、无嵌套 conftest、无 env/pytest、功能用例无
   `.dut.`/`.pins.`”写成可执行测试。BPU 的
   `tests/framework/test_repository_layout.py` 是参考实现。
8. **收集与定向运行**：先 `pytest --collect-only`，再跑纯模型目录；原生用例需要重建
   时单独说明，不要把收集成功写成执行通过。

## 验收

```sh
.venv/bin/python scripts/audit-suite-layout.py --strict --suite <suite>
.venv/bin/ucv run <suite> --collect-only
.venv/bin/ucv run <suite> -- tests/<dut>/scoreboard
```

以上从仓库根运行。原生 DUT 生命周期/覆盖依赖 managed runner 的工程不得把直接
pytest 命令当作通用入口。`--strict` 仅结构验收；引脚别名也需事务适配。

检查：

- `tests/conftest.py` 只出现每个 DUT 一次；
- 功能 testcase 中 `.dut.`、`.pins.` 命中为 0；
- 同一引脚重复 claim 在 fixture 边界失败；
- 关闭 monitor 后依赖它的场景失败；
- 新增 DUT 只加一个 fixture 和一个 `<dut>/` 子包，不改其他 DUT 的编码。

## 案例与边界

2026-10-30 把 BPU 10 个 DUT、ICache 11 个 DUT 的 fixture 收敛到各自 pytest 根；BPU 新增
`wait_cycles`、ICache 新增 `write_with_flush`，清掉功能用例的直接时钟/驱动访问。
FTQ 已按同一布局落地。2026-10-31 其余工程也完成 fixture 接线整理；引脚别名替换
不代表事务边界完成，旧工程仍有 pin-level 耦合，见[迁移边界复核](pin-schema-and-suite-migration.md)。
