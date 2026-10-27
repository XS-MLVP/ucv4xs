# 编译、构建与工具链经验

本页集中记录重建入口、已遇到的工具问题、处理依据和日志位置。具体命令由仓库代码与版本清单生成；历史经验保留原基线与工具版本的适用范围。

## 需要长期保留的构建资产

| 内容 | 仓库位置 | 用途 |
|---|---|---|
| 源码、递归子模块、生成配置和生成工具版本 | [baselines/](../../baselines/) | 确定本轮实际硬件输入 |
| toffee、Picker、xcomm、Verilator 版本及工具补丁 | [版本清单](../../dependencies/versions.json)、[Python 依赖](../../dependencies/python.txt)、[patches/](../../dependencies/patches/) | 在项目内安装一致的工具链 |
| 安装与源码生成 | [setup.py](../../src/ucv/setup.py)、[sources.py](../../src/ucv/sources.py) | 获取精确版本、安装、Chisel 到 RTL |
| 闭包提取、Picker 导出与独立进程冒烟 | [build.py](../../src/ucv/build.py) | 从完整 RTL 构建各 DUT |
| 各 DUT 的 top、导出类和构建选择 | 各工程 `ucv.json`，例如 [Sbuffer](../../suites/memblock/sbuffer/ucv.json) | 随工程维护模块边界 |
| 已做过的重建与差异检查 | [结构重建记录](../history/structure-update-20261027.json)、[公开 RTL 差异](../history/public-rtl-rebuild-comparison.json) | 将结论绑定到对应产物与哈希 |

生成 RTL、FIRRTL、原生库、完整编译日志及波形保留在忽略目录或外部证据存储。Git 保存配方、版本、补丁、经验和必要的来源凭据。历史 BPU 的 [DUT 重建记录](../../suites/frontend/bpu/docs/dut-rebuild.md) 及各工程 `tools/` 中的构建脚本也已保留；当前统一入口是 `ucv`。

## 当前完整构建入口

在仓库根目录执行。宿主依赖及项目内安装要求见 [README](../../README.md)，镜像和 internal 源码接入见 [本地配置](../local-configuration.md)。

```sh
PYTHONPATH=src python3.12 -m ucv setup --jobs 8
.venv/bin/ucv doctor public --require-unified-baseline
.venv/bin/ucv prepare public --require-unified-baseline --jobs 8
.venv/bin/ucv build public --require-unified-baseline --jobs 8
```

统一链路是：命名基线 → 完整香山 DefaultConfig → 按实际实例关系提取 DUT 闭包 → Picker/Verilator → 原生包冒烟 → UT。`build` 会先调用所需的 `prepare` 阶段；同基线共享完整 RTL，成功缓存命中仍核对文件哈希。

只排查一个 DUT 时可以缩小构建范围：

```sh
.venv/bin/ucv build sbuffer --dut sbuffer_data --jobs 4
```

`--dut` 使用工程配方中的键。VAGQ 通过本地配置提供 internal 来源后单独执行 `ucv prepare vagq` / `ucv build vagq`。`full` 当前含两个不同基线，严格统一基线检查会按设计拒绝该集合。

## 已遇到的具体问题与保留的处理

| 问题或容易误用的地方 | 当前处理与边界 | 依据 |
|---|---|---|
| 只固定香山主仓 commit，子模块、生成参数或工具却不一致 | 命名基线包含递归 gitlink、配置、firtool 参数和版本；工具补丁保存 SHA-256 | [基线说明](../baselines.md)、[sources.py](../../src/ucv/sources.py) |
| 历史 `make verilog` 会把 `$fatal` 替换成依赖宏的调用，直接拿旧文件构建可能缺少宏；同 commit 也未必得到逐字节相同的历史 RTL | 当前调用基线记录的完整生成 top，保留 Chisel/CIRCT 原始 `$fatal`；闭包只复制与核验，不进行硬件逻辑改写。历史差异单列 | [原 soc-split 说明](../history/build-notes/soc-split.original.md)、[RTL 差异记录](../history/public-rtl-rebuild-comparison.json) |
| BPU 独立生成与整芯片生成的配置、优化后端口不同，旧模型不能直接套用 | 所有工程使用 DefaultConfig；BPU 从完整香山产物提取。模型与用例适配实际端口，旧独立入口保留为历史材料 | [基线说明](../baselines.md)、[阶段状态](../status.md) |
| internal VAGQ 直接套公开 XSTop 发布参数会裁掉所需 assertion-layer 输入与 difftest 元数据 | internal 基线记录 `top.XiangShanSim`、`xiangshan.test.runMain`、difftest 和启用的 layer；仍是完整香山生成 | [生成观察记录](../history/internal-generation-observation.json)、[internal 基线](../../baselines/internal-d4566d58a.json) |
| Verilator 5.052 将 trace 初始化拆成多个调用，旧 Picker 解析会丢失 scope | 锁定并应用 trace 调用图补丁；未知拆分调用报错；保留顺序变化与旧格式检查 | [Picker 补丁](../../dependencies/patches/picker-trace-callgraph.patch)、[对应测试](../../tests/test_picker_trace.py) |
| 宽信号的 trace 表达式必须按实际 32-bit word 读取，并保持实时性、边界和只读约束 | xcomm 锁定补丁处理宽字读取，保留原生检查 | [xcomm 补丁](../../dependencies/patches/xcomm-wide-trace-word.patch)、[对应测试](../../tests/test_xcomm_wide_trace.py) |
| Picker 将 Python 保留字端口直接输出成属性语法 | 构建时只修正 Python 绑定为 `getattr` / `setattr`，记录修正前后哈希；RTL 和信号名保持原样 | [repair_python_keywords](../../src/ucv/build.py) |
| 可执行文件、模板、Python wrapper 和原生库来自不同安装，可能出现 ABI 或 memory-direct 不匹配 | 使用项目内 `.venv/` 与 `.tools/`；核对锁定工具，并在独立进程检查 ABI 3、coverage protocol 5、信号配置基址、行覆盖能力及复位/步进/结束 | [旧 BPU 重建经验](../../suites/frontend/bpu/docs/dut-rebuild.md)、[setup.py](../../src/ucv/setup.py)、[build.py](../../src/ucv/build.py) |
| 仓库搬家后，旧虚拟环境、CMake 状态和原生二进制可能带原绝对路径 | 在新目录建立环境并重新构建原生包。2026-10-27 搬迁保留旧环境到 `.history/`，新原生包单独构建；该轮完整 RTL 缓存经哈希核对复用 | [搬迁与重建记录](../history/structure-update-20261027.json) |
| 只看到编译返回成功或目录存在，就把半成品当成可用 DUT | 检查 Python 入口、signals、offset 和两份原生库，再运行独立进程冒烟；失败包保留到 `failed-dut-*`，无成功凭据不能命中成功构建 | [build.py](../../src/ucv/build.py) |

`--jobs` 控制构建并行预算；源码生成代码当前配置 JVM 堆上限为 64G、线程栈为 64m，`--jobs` 不调整这两个值。同一源码检出的 Mill 生成串行执行。增加并行度前需结合宿主内存与 DUT 规模，不把线程数视为唯一资源约束。

## 出问题时从哪里找记录

以下路径相对仓库根目录；`<key>` 是有效输入计算出的缓存标识。

| 阶段 | 日志与凭据 |
|---|---|
| 安装 | `.tools/setup.log`、`.tools/receipt.json`、`.tools/installed-python.txt` |
| 源码与子模块 | `.cache/logs/source-<key>.log`、`.cache/logs/submodule-*.log`、源码检出中的 `.ucv-source.json` |
| Chisel → RTL | `.cache/generated/<key>/generate.log`、`generation.json`；包含实际命令和 RTL 文件哈希 |
| DUT 闭包 | `.cache/duts/<key>/rtl/source.json`、`filelist.f` |
| Picker / Verilator | `.cache/duts/<key>/build.log`、`smoke.log`、`build.json`、`dut/provenance.json` |
| 本次批量构建 | `.ucv/last-build.json`；各 DUT 的 PASS / ERROR 与错误说明 |

失败时先保留对应日志和输入版本，确定失败发生在源码、生成、闭包、编译还是导入冒烟阶段。缓存报哈希不一致时应先追查内容来源；改变基线、配方或工具补丁后使用对应的新缓存身份。构建语义变化同时按 [维护约定](../architecture.md) 更新 `pipeline_version`。

当前源码版本、历史构建记录和新运行结果分别绑定。构建与冒烟通过证明工具链和最小 DUT 操作可用，功能与覆盖结论由实际回归给出。

## 历史来源

- [soc-split 原始生成说明](../history/build-notes/soc-split.original.md)：原文件逐字节保存，旧命令、目录、计数与状态保留原意；[来源哈希](../history/build-notes/source-notes.json)。
- [BPU DUT 重建与工具链记录](../../suites/frontend/bpu/docs/dut-rebuild.md)：保留历次工具组合、memory-direct 迁移与重建经历；其中旧绝对路径和旧框架命令只用于溯源。
- [2026-10-27 结构重建记录](../history/structure-update-20261027.json)：记录 122 个 DUT 的构建和冒烟，以及当轮使用的共享 RTL 缓存与本地归档。

本页整理构建方法与已有经验，没有新增一轮硬件构建或验收。
