---
name: ucv4xs-workflow
description: 维护 ucv4xs 香山单元测试仓库的基线、构建编排和工程接入，使用 ucv 完成项目内安装、完整 RTL 生成、DUT 构建和隔离回归。适用于本仓库的开发与运行任务。
---

# ucv4xs 项目工作流

以包含根 `ucv.json`、`pyproject.toml` 和 `src/ucv/` 的目录为仓库根。遵循 [AGENTS.md](../../AGENTS.md)，从 [阶段状态](../../docs/status.md) 了解当前结构交付与硬件验收边界。

## 按任务选择入口

- 仅查看工程或继承：`PYTHONPATH=src python3.12 -m ucv list public --require-unified-baseline`；不需要为阅读配置启动完整构建。
- 安装、编译或定位工具问题：读取 [编译构建经验](../../docs/lessons/build-and-toolchain.md)。实际配置以 `baselines/`、`dependencies/` 和工程 `ucv.json` 为准。
- 修改源码版本或 override：读取 [基线规则](../../docs/baselines.md)，建立完整命名基线，并在根、分组或整个工程引用。
- 接入镜像、internal 源码或旧证据：读取 [本地配置](../../docs/local-configuration.md)，只在 `.ucv/local.json` 保存机器路径。
- 修改验证语义：先查该工程的功能合同与 [经验来源](../../docs/lessons/README.md)；构建成功不能替代用例判定。

## 构建和回归

从根目录使用以下入口，按当前任务选择需要的阶段和集合：

```sh
PYTHONPATH=src python3.12 -m ucv setup --jobs 8
.venv/bin/ucv doctor public --require-unified-baseline
.venv/bin/ucv prepare public --require-unified-baseline --jobs 8
.venv/bin/ucv build sbuffer --dut sbuffer_data --jobs 4
.venv/bin/ucv run sbuffer --workers 1 -- tests/sbuffer_data/test_sbuffer_data.py::test_reset_initializes_masks_and_idle_is_stable
.venv/bin/ucv report
```

`--jobs` 和 `--workers` 按宿主资源及任务范围选择；`run` 的 `--` 后传 pytest 选择条件。每次回归使用新结果目录。公开集合统一验收启用严格基线检查；当前 `full` 含 internal VAGQ，混合基线会被该检查拒绝。

保持“完整香山 DefaultConfig → RTL → DUT 闭包 → Picker → UT”的链路。各工程按实际优化后端口适配；不添加单 DUT 的源码/配置 override 或 BPU 独立生成入口。缓存中的生成、闭包和构建凭据保存实际命令及哈希；出现不一致先定位输入，避免直接修改生成物绕过校验。

## 验证框架：toffee

所有工程的验证代码运行在 `uc-toffee` 上（导入名 `toffee`）。写 driver、monitor、agent
或新建工程前，先确认框架已提供什么；工程侧重复实现会丢掉框架已有的接受事件、丢拍
报错和原生覆盖自动收集。分层方式见
[验证包 driver/monitor 分层](../execution/package-layout.md)。

| 名称 | 含义 |
|---|---|
| `uc-toffee` | PyPI 分发名（导入名 `toffee`）；版本锁在 `dependencies/versions.json` 与 `dependencies/python.txt` |
| `toffee` | 导入名，例如 `from toffee import Execution, ClockCycles` |
| `XS-MLVP/toffee` | 源码与文档仓库；当前锁定 `v2.1.0`，`main` 是 Toffee 2，`master` 保留 Toffee Legacy |
| `XReactor` | 框架旧名；序列化的 `xreactor-*` 格式 ID 为兼容保留，不是另一套框架 |

锁定的完整源码检出在 `.tools/sources/toffee`，含 `docs/` 用户手册和 `examples/`。
`ucv` 在运行前校验安装包与该检出逐文件一致，因此读这里的文档和示例就是读当前框架：

```sh
ls .tools/sources/toffee/docs/zh/guides
sed -n 1,60p .tools/sources/toffee/docs/zh/guides/drivers.md
sed -n 1,60p .tools/sources/toffee/docs/zh/guides/monitors.md
.venv/bin/python -c "import toffee; print([n for n in dir(toffee) if n[0].isupper()])"
```

运行入口是 `toffee run`（`ucv run` 内部调用），pytest 插件为 `toffee._pytest_plugin`，
UNCERTAIN 插件为 `toffee._pytest_outcomes`，选项形如 `--toffee-output`、
`--toffee-native-coverage-tool`，覆盖标记为 `toffee_functional_coverage`。

`uc-toffee 2.1.0` 已正式提供 `@pytest.mark.uncertain(reason=..., reference=...)`：正常执行
已有检查，证据不足单列 `U`/`UNCERTAIN`，不计 PASS；真实错误优先，UNCERTAIN 本身不改变
退出码。未发布的本地框架开发仍使用[独立运行环境与源码凭据](../../docs/local-configuration.md#本地-toffee-开发环境)，
不改写公共构建锁或伪造原生重建记录。依赖升级和分发名变化的流程见待审核
[依赖升级与能力核对](../pending/dependency-upgrade-and-capability-audit.md)。

框架当前不支持、需要在工程侧补齐的能力。落地时在工程 `docs/` 写明原因、行为差异和
关闭条件，不要把自建版本当成框架等价物：

- **每拍合同谓词（不变量）监视器。** 框架只有事务 monitor。生成 RTL 去掉 `$fatal`
  后，需要工程侧补被动不变量检查，并说明它代替了哪些断言、遗漏什么。
- **monitor 的非消费式快照。** `SamplingMonitor` 只有 `await recv()`，没有 `peek()`；
  “走 N 拍后读当前状态”的用例要自行适配，注意不能因此绕过 monitor 的采样规则。
- **Picker 包加载器。** `InitClock`、`GetInternalSignal`、输入清零等步骤没有独立 API，
  现有写法见 `.tools/sources/toffee/examples/integration/e203/e203_toffee_env.py`。
- **原生覆盖报告口径。** `toffee/_native_coverage.py` 的 `export_lcov` 只导出
  `v_line`/`v_branch` 页面，故意排除 toggle；`coverage_report.parse_lcov` 只读
  `DA/LF/LH`，不读 `BRDA`。需要分支或 toggle 数字时由工程自建报告，并说明与框架
  报告的差异。

升级框架时同时更新 `.tools/sources/toffee` 检出、`dependencies/versions.json` 和
`dependencies/python.txt`；三者不同步会在运行前被哈希校验拒绝。

## 修改工程与公共工具

新增工程在相应 `suites/<group>/` 下建立工程根 Python 包、pytest 根、tests/ 和 ucv.json，
并在根注册。导入名为 suites.<group>.<suite>；不再添加 *verify 或 common 外壳。
每个 DUT 配方声明真实 RTL top 和 Python 导出类。领域模型与检查器留在工程中，公共层
负责路径、基线、调度和报告。共享实现按 native/harness、runtime、drivers、monitors、
pytest_plugins 等职责命名，DUT 专属代码不能因“共享”名义搬入工程根。

结构检查与语义验收分开：当前 fixture 集中在 `tests/conftest.py`，共享插件
`ucv.pytest_selftest` 提供自检分类。物理映射归 DUT 的 ports/bundle 层，只有确实跨 DUT
共享时才进入明确职责模块；不创建 common/pins.py。P.p_* / P.io(...) 只是旧接口
兼容别名，不是事务抽象，不能用消除 io_* 字面量证明迁移完成。事务 API、采样/所有权和
独立 checker 仍须按[正式分层方法](../execution/package-layout.md)逐项验收。
待审核的[迁移边界复核](../pending/pin-schema-and-suite-migration.md)记录本轮反例。

变更构建语义时同步缓存身份。公共工具或工具补丁变更运行根 `tests/`；工程语义变更运行相关用例与必要对照。文档和配置查看只做相应检查，不默认重跑十工程。

```sh
python3.12 scripts/audit-assets.py
.venv/bin/python -m pytest -q tests
.venv/bin/python scripts/audit-suite-layout.py --strict
.venv/bin/python scripts/audit-skills.py --strict --check-framework
```

`audit-suite-layout.py --strict` 只检查结构接线。加 `--require-transaction-boundary`
会报告仍在用例中使用引脚字段/别名的工程；当前存在真实未迁移项，不能为了全绿关闭该检查。

分别报告实际执行的构建/冒烟、功能判定和覆盖缺口；缺少依赖、未执行和历史结果均明确说明。真实失败按原判定保留，不用修改模型对齐 RTL 或扩大 XFAIL 来取得通过。

## 产物与经验

Git 中保留配方、锁定版本、补丁、验证代码和经验。`.cache/`、`results/`、`.history/`、本地环境和 internal 证据按 [维护约定](../../docs/maintenance.md) 管理。按任务授权回收文件时核对活动状态和用途，记录删除清单；此 skill 本身不授权额外删除或远端写入。

新增构建或验证经验链接到 [经验总入口](../../docs/lessons/README.md)，保留原问题、修正依据和实际检查证据。历史日期与适用基线沿用原含义。
