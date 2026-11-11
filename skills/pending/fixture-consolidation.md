---
name: fixture-consolidation
description: 把旧布局的每 DUT env/pytest.py、子目录 conftest 收敛到工程唯一的 conftest.py fixture/插件注册入口，并整理 testbenches/<dut>/ 的事务 API、shared 六职责、selftest 标记和布局审计。适用于测试直接操作引脚、fixture 分散或新增 DUT 时复制接线代码。
---

# Fixture 集中与 agent 边界（待审核）

## 何时使用、准备什么

- 旧布局中每个 DUT 有一个 `env/pytest.py`，或每个 `tests/<dut>/conftest.py` 只是转发；
- 测试在 scenario 或 testcase 中直接写 `agent.dut.clock`、`.pins`、物理端口名；
- 新增 DUT 时复制了上一份 conftest，或把 `agent/` 放在模块根；
- 想确认功能用例是否真的只通过 agent 事务 API 访问 DUT。

准备：该工程的 workspace schema、pytest 根、实现目录、`pytest.ini`、当前测试收集结果。
版本适用范围见[目录规范](../../docs/reference/module-layout.md#schema-版本与本轮范围)。先跑审计：

```sh
.venv/bin/python scripts/audit-suite-layout.py
```

只读报告会列每工程的 root fixture、嵌套 conftest、旧 `env/pytest.py` 和直接访问数。
迁移完成后再用 `--strict` 作为门禁；`ucv check <suite>` 按 schema 校验当前结构。

## 目标布局（schema2）

```text
suites/<group>/<suite>/
├── __init__.py             # suites.<group>.<suite>，只定义资源根
├── conftest.py             # 工程唯一 fixture / pytest 插件注册入口
├── pytest.ini              # testpaths = testbenches；feature/selftest/estimated_runtime 标记
├── testbenches/<dut>/
│   ├── __init__.py
│   ├── README.md           # ucv docs --write 生成工作入口
│   ├── transactions.py     # 或 transactions/；事务合法域、单位、身份
│   ├── env.py              # 或 env/；agent/ports/driver/monitor 按需落位
│   ├── model.py            # 按需：独立参考计算
│   ├── checker.py          # 按需：比较与不变量
│   ├── coverage.py         # 按需：行为覆盖
│   └── tests/              # 只调用 agent 事务 API；fixtures.py / 插件放 DUT 专用实现
├── testbenches/shared/     # 真正跨 DUT 组件，同用六职责与独立 README
├── tools/                  # 离线审计和报告命令（可无）
└── docs/                   # 工程规格、问题与证据
```

审计入口 `scripts/audit-suite-layout.py` 在仓库根，不在各工程。tests 为目录，其余职责
按需选单文件或同名包，不造空壳；DUT 与 shared 同名职责同义，只保留六类职责，
不放 `agent/`、`conftest.py` 或 `pytest.ini`。旧 `<dut>/`、
`tests/<dut>/` 只是迁移前位置，新工作不写回。

`env/` 可以保留 DUT 级辅助（例如 reset 序列、目标错误注入）。DUT 专用 fixture 与参数
生成放其 `tests/fixtures.py` 或 tests 内插件，跨 DUT 通用插件放
`testbenches/shared/env/pytest_plugins/`，都由工程唯一 conftest 注册；简短 fixture
也可留在根 conftest。shared 只收真正共享的实现，不反向导入具体 DUT 或工程 tools；
shared/tests 可以检查集成引用。shared 是保留名，无独立 DUT、top 或本地原生库。

## 操作步骤

1. **盘点**：列出旧 `*/env/pytest.py` 和 `tests/*/conftest.py`，确认每个 fixture 的名字、
   依赖和是否被测试使用。输出目录类 fixture 若无人使用，直接删除，不要搬成死代码。
2. **搬 agent fixture**：在工程 `conftest.py` 导入 agent 类和 `agent_fixture`，逐个赋值。
   保留每个 DUT 的 `max_batch_ticks`，不要统一成一个猜测值；共享参数化实现按 testbench 登记。
3. **搬非 agent fixture**：DUT 专用实现与参数生成归其 tests/插件；真正通用的插件归
   shared/env/pytest_plugins。简短 fixture 可以留在根 conftest；只做注册表是偏好，不是
   pytest 语法限制，避免为了禁止函数定义多造一层。
4. **删除转发层**：删掉旧 `tests/*/conftest.py`、`<dut>/env/pytest.py` 和模块根
   `agent/`。删除前用 `grep -rn 'env.pytest'` 和 `ucv check <suite>` 确认没有导入或
   结构残留。
5. **补 agent API**：测试里的 `agent.dut.clock` 改成 agent 方法（如
   `await agent.wait_cycles(n)`）；需要精确时序的已知缺陷探针，把整段协议封装成
   agent 事务/精确对齐 API；不要把完整场景和所有断言藏进不透明的一次调用。
6. **标 selftest**：注册共享插件 `ucv.pytest_selftest`，它按 `framework/`、`checkers/`、
   `selftest/`、`diagnostics/` 路径自动加 `pytest.mark.selftest`；在 `pytest.ini` 注册
   marker。自检不计硬件功能 credit，但不改写既有功能点报告的分类规则。不要为每个工程
   复制一份插件。
7. **接入布局门禁**：复用 `ucv check` 和布局审计的通用 schema 规则，检查根 fixture
   唯一、无嵌套 conftest、无旧 env/pytest、实现包根无 `agent/`。工程自检只补具体集成
   约束；功能用例的 `.dut.`/`.pins.` 泄漏另做事务边界审计，不增加工程专属结构豁免。
8. **收集与定向运行**：先 `pytest --collect-only`，再跑纯模型目录；原生用例需要重建
   时单独说明，不要把收集成功写成执行通过。

## 验收

```sh
.venv/bin/python scripts/audit-suite-layout.py --strict --suite <suite>
.venv/bin/ucv check <suite>
.venv/bin/ucv run <suite> --collect-only
.venv/bin/ucv run <suite> -- testbenches/<testbench>/tests
```

以上从仓库根运行。原生 DUT 生命周期/覆盖依赖 managed runner 的工程不得把直接
pytest 命令当作通用入口。`--strict` 与 `ucv check` 仅结构验收；引脚别名也需事务适配。

检查：

- 工程 `conftest.py` 只出现每个 DUT 一次，模块目录没有嵌套 conftest；
- 功能 testcase 中 `.dut.`、`.pins.` 命中为 0；
- 同一引脚重复 claim 在 fixture 边界失败；
- 关闭 monitor 后依赖它的场景失败；
- 新增 DUT 接入 `testbenches/<dut>/` 或显式参数化实现，并在唯一 conftest 注册，不改其他 DUT 的编码；
- 测试与规格没有固定回旧的工程根 `tests/` 或模块根 `agent/`。

## 案例与边界

2026-10-30 把 BPU 10 个 DUT、ICache 11 个 DUT 的 fixture 收敛到各自 pytest 根；BPU 新增
`wait_cycles`、ICache 新增 `write_with_flush`，清掉功能用例的直接时钟/驱动访问。
FTQ 已按同一布局落地。2026-10-31 其余工程也完成 fixture 接线整理；引脚别名替换
不代表事务边界完成，旧工程仍有 pin-level 耦合，见[迁移边界复核](pin-schema-and-suite-migration.md)。
上述日期记录旧 `tests/<dut>` 布局的迁移事实；当前模块归属以工程 `workspace.json`、
`ucv check` 和 [模块目录规范](../../docs/reference/module-layout.md) 为准。
