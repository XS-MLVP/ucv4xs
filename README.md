# ucv4xs

基于 UnityChip 的香山单元测试（UT）仓库。仓库和 Python 发行包名为 `ucv4xs`，命令与 Python 导入名均为 `ucv`。

当前交付为**结构整合版**：工程组织、基线管理与执行入口已落地；完整硬件回归和 BPU DefaultConfig 用例适配继续单独推进。详见 [阶段状态](docs/status.md)。

统一入口是 `ucv`，验证框架是固定提交的 toffee。八个工程保留各自的模型、检查器和 pytest 根目录。默认公开集合包含 BPU、ICache、LSQ、DCache、MMU、Sbuffer、LSU；`full` 另包含外部接入的 VAGQ。

首次安装需要 Linux x86_64、Python 3.12、Java 17、Git、CMake、C++20 编译器、SWIG ≥ 4.2，以及源码下载所需的网络访问。安装均写入仓库内 `.venv/` 和 `.tools/`。

```sh
PYTHONPATH=src python3 -m ucv setup --jobs 16
.venv/bin/ucv doctor public --require-unified-baseline
.venv/bin/ucv list full
.venv/bin/ucv prepare public --require-unified-baseline --jobs 16
.venv/bin/ucv build public --require-unified-baseline --jobs 32
.venv/bin/ucv run public --require-unified-baseline --workers 32
.venv/bin/ucv report
```

选择工程、硬件分组或集合，例如 `ucv build sbuffer`、`ucv run memblock`。`prepare` 和 `build` 的 `--dut` 可以重复指定；`run` 的 `--` 后传入 pytest 用例路径、`-k` 或 `-m` 参数。生产集合由各工程的 `pytest.ini` 定义，BPU 默认使用原有 `production` profile，VAGQ 保留独立 ISA audit 的显式选择方式。

```sh
.venv/bin/ucv run sbuffer --workers 4 --seed 1 -- -k random
.venv/bin/ucv run public --collect-only
.venv/bin/ucv report results/<new-run> --compare results/<prior-run>
```

`--workers` 是一次顶层运行的总 worker 预算。工程运行在独立进程中，BPU 还按冻结的 DUT 分区分别启动进程。每次运行创建新目录，记录用例集合、逐阶段判定、源码哈希、基线、RTL、原生库、工具版本和种子；覆盖率由 toffee 管理。

全部工程使用 DefaultConfig。公开工程共享完整香山 RTL 的生成，BPU 同样只提取模块闭包；每个 DUT 仍单独进行 Picker 构建与 UT。公开七工程默认继承 `893e1580b705d81f113c30c7a05734e09a08050e`。VAGQ 显式使用 internal `d4566d58a5ace1f6a5df4409b37a84b971f48e43`，因此 `ucv run full --require-unified-baseline` 会在执行前报错。

目录职责与扩展方式见 [结构说明](docs/architecture.md)。详细说明见 [基线与构建](docs/baselines.md)、[外部接入](docs/local-configuration.md)、[维护与验收](docs/maintenance.md) 和 [许可](NOTICE.md)。历史证据只能证明对应历史产物，不能代替重建版本的验收。
