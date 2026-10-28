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

## 修改工程与公共工具

新增工程在相应 `suites/<group>/` 下建立独立验证包、pytest 根、`tests/` 和 `ucv.json`，并在根注册。每个 DUT 配方声明真实 RTL top 和 Python 导出类。领域模型与检查器留在工程中，公共层负责路径、基线、调度和报告。

变更构建语义时同步缓存身份。公共工具或工具补丁变更运行根 `tests/`；工程语义变更运行相关用例与必要对照。文档和配置查看只做相应检查，不默认重跑八工程。

```sh
python3.12 scripts/audit-assets.py
.venv/bin/python -m pytest -q tests
```

分别报告实际执行的构建/冒烟、功能判定和覆盖缺口；缺少依赖、未执行和历史结果均明确说明。真实失败按原判定保留，不用修改模型对齐 RTL 或扩大 XFAIL 来取得通过。

## 产物与经验

Git 中保留配方、锁定版本、补丁、验证代码和经验。`.cache/`、`results/`、`.history/`、本地环境和 internal 证据按 [维护约定](../../docs/maintenance.md) 管理。按任务授权回收文件时核对活动状态和用途，记录删除清单；此 skill 本身不授权额外删除或远端写入。

新增构建或验证经验链接到 [经验总入口](../../docs/lessons/README.md)，保留原问题、修正依据和实际检查证据。历史日期与适用基线沿用原含义。
