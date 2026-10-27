# 仓库结构与扩展方式

本仓库的结构版统一工程组织、源码基线、命令入口和产物归属。硬件失败和 BPU 的后续适配单独登记在 [阶段状态](status.md)。

```text
xiangshan-verify/
├── ucv.json                    # 根基线、工程注册、public/full 集合
├── baselines/                  # 完整命名基线与递归源码锁
├── dependencies/               # Python/原生工具锁与带哈希的工具补丁
├── recipes/bpu/                # DefaultConfig 独立 Chisel 生成入口
├── src/ucv/                    # 公共编排、路径、运行记录与报告
├── suites/
│   ├── frontend/{bpu,icache}/
│   ├── memblock/{lsq,dcache,mmu,sbuffer,lsu}/
│   └── vector/vagq/
├── tests/                      # 编排层与工具补丁的检查
├── scripts/                    # 启动入口、资产审计、历史比较
└── docs/                       # 维护约定、状态、历史哈希索引
```

每个工程保留 `ucv.json`、`pytest.ini`、独立验证包、`tests/` 和领域文档。共享层不导入任何工程的领域模型；各工程通过 `ucv.runtime` 解析项目工具、有效源码和历史证据路径。历史 `manifest/` 和审计文档保留原基线含义，当前构建以缓存中的 `source.json`、`generation.json`、`build.json` 为准。

| 层 | 配置与职责 |
|---|---|
| 根 | `ucv.json` 注册工程、集合、根默认基线 |
| 硬件分组 | `suites/<group>/ucv.json` 可引用命名基线 |
| 工程 | `ucv.json` 声明生成方式、DUT top、导出类、测试目录，可覆盖基线 |
| DUT | 继承整个工程的基线，不提供单 DUT commit/config override |

引用最近一级显式基线，不合并命名基线的内部字段。三个初始分组均继承根；VAGQ 单独引用 internal 基线。新增基线要复制完整定义并更新名称、commit、递归 gitlink、生成配置、工具版本和补丁哈希。所有当前工程使用 DefaultConfig。

命令链为 `setup → prepare → build → run → report`。`list` 和 `doctor` 用于确认选择、继承来源和环境。`prepare` 获取独立源码、生成 RTL、提取闭包；`build` 构建并在独立进程冒烟；`run` 按工程隔离进程，BPU 进一步按 DUT 分区，共享一个 worker 预算。显式用例路径替代默认测试目录，`-k`/`-m` 作用于默认集合。构建与运行共享工程锁，避免活动链接在回归期间被切换。

所有安装、源码和产物都属于当前检出：`.venv/`、`.tools/`、`.cache/`、`results/` 均忽略；工程中的 `rtl/`、`dut/`、`XiangShan` 是运行时创建的相对链接。`.ucv/local.json` 保存机器配置，Git 中没有通往旧工作区的链接。源目录移动后应重新建立虚拟环境和工具，不复用含绝对路径的二进制缓存。

新增工程时，在对应分组创建目录、验证包和 pytest 配置，在根注册工程，并声明完整 DUT 配方。公共编排变更运行根 `tests/`；工程内部检查通过 `ucv run <suite>` 运行。更改构建语义时应更新缓存身份中的 `pipeline_version`，不复用旧构建凭据。第一版不配置 CI。

公开文件边界检查：

```sh
python3 scripts/audit-assets.py
```

该检查不需要安装原生工具，验证源码边界、旧框架导入、工程入口和历史索引哈希。历史索引按工程拆为 JSONL，主索引保存数量和哈希；内容文件仍通过 `history://` 外部定位。简短的历史审计与缺陷文档可以留在 Git 中，大结果、覆盖率原始数据和内部 RTL 保持外部接入。
