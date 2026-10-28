# ucv4xs

基于 UnityChip 的香山单元测试（UT）仓库，统一组织验证工程、RTL 基线、工具链和回归入口。仓库与 Python 发行包名为 `ucv4xs`，命令及 Python 导入名为 `ucv`，验证框架为锁定版本的 toffee。

当前版本是**结构整合版**：八个工程、122 个 DUT 已接入统一构建与运行链路。BPU 对完整 DefaultConfig RTL 的模型和用例适配、完整生产回归及空缓存全链路验收仍在推进。实际 FAIL、XFAIL、SKIP 和证据边界见 [阶段状态](docs/status.md)；结构标签不代表硬件验收通过。

## 工程与基线

| 分组 | 工程 | DUT 数 | 初始有效基线 |
|---|---|---:|---|
| frontend | BPU / ICache | 10 / 11 | public-893e1580b |
| memblock | LSQ / DCache / MMU / Sbuffer / LSU | 38 / 13 / 17 / 2 / 19 | public-893e1580b |
| vector | VAGQ | 12 | internal-d4566d58a，外部源码接入 |

`public` 集合包含七个公开工程；`full` 另外包含 VAGQ。公开根基线固定为 `893e1580b705d81f113c30c7a05734e09a08050e`，VAGQ 工程显式覆盖为 internal `d4566d58a5ace1f6a5df4409b37a84b971f48e43`。

所有工程使用 **DefaultConfig**。基线按“根 → 硬件分组 → 工程”继承，最近的显式完整命名基线优先；一个工程的所有 DUT 共用基线。源码 commit、递归子模块、生成参数、工具版本和设计补丁均进入版本清单。

```text
完整香山 DefaultConfig → RTL → DUT 模块闭包 → Picker / Verilator → UT
```

同基线共享完整 RTL 生成结果，各 DUT 单独构建。BPU 使用这条完整香山链路；绑定与模型适配整芯片优化后的实际端口。详情见 [基线与构建](docs/baselines.md)。

## 快速开始

支持 Linux x86_64、Python 3.12。宿主需提供 Java 17、Git、Make、CMake、C++20 编译器和 SWIG ≥ 4.2；首次获取源码与依赖需要网络。工具和 Python 环境安装在项目的 `.tools/` 与 `.venv/` 中。

```sh
git clone https://github.com/XS-MLVP/ucv4xs.git
cd ucv4xs

PYTHONPATH=src python3.12 -m ucv setup --jobs 8
.venv/bin/ucv doctor public --require-unified-baseline
.venv/bin/ucv list public
.venv/bin/ucv prepare public --require-unified-baseline --jobs 8
.venv/bin/ucv build public --require-unified-baseline --jobs 8
```

`prepare` 获取精确源码、生成完整 RTL 并提取闭包；`build` 构建原生 DUT 并执行独立进程冒烟。源码生成当前配置 JVM 堆上限为 64G，`--jobs` 控制构建并行预算；根据宿主资源设置并行度。安装与编译问题见 [构建经验和日志位置](docs/lessons/build-and-toolchain.md)。

运行一个工程并查看报告：

```sh
.venv/bin/ucv run sbuffer --workers 4 --seed 1
.venv/bin/ucv report
```

需要本地镜像或 internal 来源时，将 [本地配置示例](ucv.local.example.json) 中需要的字段写入 `.ucv/local.json`，按 [外部接入说明](docs/local-configuration.md) 配置；删除未使用的占位字段。VAGQ 缺少外部源码时会明确报错。`full` 当前是混合基线集合，启用 `--require-unified-baseline` 会拒绝执行。

## 常用命令

| 命令 | 用途 |
|---|---|
| `ucv list` / `ucv doctor` | 工程、DUT、有效基线、继承来源和环境检查 |
| `ucv setup` | 安装版本清单中的项目依赖 |
| `ucv prepare` | 获取源码、生成 RTL、提取 DUT 闭包 |
| `ucv build` | 原生构建与冒烟 |
| `ucv run` | 按工程、分组或集合回归 |
| `ucv report` | 判定、覆盖率、来源与历史差异 |

安装后可使用 `.venv/bin/ucv`；下文以它为例。`--workers` 是顶层运行的总 worker 预算。工程隔离进程执行，BPU 进一步按 DUT 分区；每次运行要求新的结果目录。

```sh
# 构建单个 DUT；--dut 使用工程配方中的键
.venv/bin/ucv build sbuffer --dut sbuffer_data --jobs 4

# 用例选择；-- 后面的参数传给该工程的 pytest
.venv/bin/ucv run sbuffer --workers 1 -- tests/sbuffer_data/test_sbuffer_data.py::test_reset_initializes_masks_and_idle_is_stable

# 只收集公开工程用例，以及执行公开集合的完整回归
.venv/bin/ucv run public --collect-only
.venv/bin/ucv run public --require-unified-baseline --workers 8

# 指定报告或比较两次运行
.venv/bin/ucv report results/<new-run> --compare results/<prior-run>
```

生产集合由各工程的 `pytest.ini` 定义，BPU 使用工程的 `production` profile；VAGQ 的独立 ISA audit 保留显式选择方式。每次运行记录验证源码、用例集合、基线、RTL/native 哈希、工具链和种子，判定按实际结果保留。

## 目录与资产

```text
ucv4xs/
├── ucv.json                   # 根默认基线、工程注册和集合
├── baselines/                 # 完整命名基线
├── dependencies/              # 依赖版本与工具补丁
├── src/ucv/                   # 公共编排工具
├── suites/
│   ├── frontend/{bpu,icache}/
│   ├── memblock/{lsq,dcache,mmu,sbuffer,lsu}/
│   └── vector/vagq/
├── skills/                    # 项目工作流与验证经验
├── docs/                      # 架构、维护、经验和历史索引
├── scripts/                   # 启动、资产检查和历史比较
├── tests/                     # ucv 与工具补丁检查
└── AGENTS.md                  # 仓库内协作约定
```

各工程保留自己的验证包、pytest 根目录、模型和检查器。详细职责见 [结构说明](docs/architecture.md)。

`.cache/` 保存源码检出、生成 RTL/FIRRTL 和 DUT 构建；`results/` 保存运行结果；`.history/` 保存本地迁移备份；`.venv/`、`.tools/`、`.ucv/` 保存本地环境与状态。这些目录均被 Git 忽略。Git 中的 `docs/history/` 保存迁移记录和证据哈希，历史证据内容通过外部 `history://` 来源访问。internal 实现、生成文件和含内部源码的证据保持外部接入。

覆盖率收尾成功时会合并并清理中间输入；异常中断可能留下大量文件。当前按字节限制缓存和异常回收的机制仍待完善，清理记录见 [维护说明](docs/maintenance.md)。

## 文档、经验与开发

- [AGENTS.md](AGENTS.md)：修改本仓库时遵循的结构、基线和验证约定。
- [项目工作流 skill](skills/ucv4xs-workflow/SKILL.md)：基线变更、构建、回归及新增工程的操作入口。
- [skill 索引](skills/README.md) 与 [经验总入口](docs/lessons/README.md)：保留原案例、误报漏检复盘与防复发手册。
- [维护与验收](docs/maintenance.md)、[阶段状态](docs/status.md)：当前工作边界、真实判定和未完成事项。

skills 可按文件路径读取；仓库中存在 skill 文件不表示已向客户端注册或自动加载。第一版没有 CI；本地检查入口为：

```sh
python3.12 scripts/audit-assets.py
.venv/bin/python -m pytest -q tests
```

自有代码和文档采用 [MPL-2.0](LICENSE)，导入文件原有许可声明保留，详见 [NOTICE](NOTICE.md)。
