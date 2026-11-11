# 第一次运行 BPU UT：MainBTB

本教程从 clone 开始，依次找到规格和源码、获取 release RTL、构建一个 DUT、运行现有
复位/冷查询用例并读懂报告。例子固定为 BPU 工程中的 `mbtb`，真实 RTL top 是 `MainBtb`。
完成后，你会得到一次有源码、基线和构建身份的运行记录；不需要修改 RTL、模型或用例。

## 开始前

- 仿真宿主为 Linux x86_64，准备 Python 3.12（含 venv/开发头文件）、Git、Make、CMake、
  C++20 编译器、SWIG ≥ 4.2，以及构建 Verilator 所需的 Autoconf/Flex/Bison。
- 首次下载 RTL、获取依赖和编译工具需要网络、磁盘和编译时间；本教程使用 release，
  不要求本机生成整芯片 RTL，也不要求 Java/Mill/firtool。
- 所有命令从仓库根执行。以下 `results/mbtb-first-ut` 必须尚不存在；再次练习时换一个新名字。

## 1. 打开工作目录

```sh
git clone https://github.com/XS-MLVP/ucv4xs.git
cd ucv4xs
./scripts/ucv info bpu --dut mbtb
```

输出以 `testbench` 显示实现归属，并列出有效基线、精确 commit 的 Chisel 链接、两类规格、
环境、用例和产物路径，以及 shared 工作入口。
新 checkout 中 RTL 和 DUT Python 显示“尚未准备”，这是正常的。

## 2. 找到要运行的行为

打开 [MainBTB 工作入口](../../suites/frontend/bpu/testbenches/mbtb/README.md)，确认它属于
`suites/frontend/bpu/testbenches/mbtb/`，不是根 `tests/`。本次选择的测试在：

```text
suites/frontend/bpu/testbenches/mbtb/tests/testcase/test_reset.py
  ::test_reset_completes_before_cold_lookup
```

阅读该函数及 [MainBTB 事务合同](../../suites/frontend/bpu/docs/spec/verification/contracts/mbtb-transaction-contract.md)
的复位/冷查询条款：用例在复位后发送冷查询，并检查未命中。这里不新增需求或校准模型。
设计背景可在 [MainBTB 设计规格](../../suites/frontend/bpu/docs/spec/design/mbtb.md)中按需查阅。
若只想读源码/写规格，不必继续安装工具，改看[只准备源码](../how-to/workspace.md#只找资料或准备源码)。

## 3. 获取已发布 RTL

```sh
./scripts/ucv doctor bpu --stage rtl
./scripts/ucv prepare bpu --dut mbtb --rtl-source release
```

预期输出 `bpu/mbtb: PREPARED`。工具下载完整 DefaultConfig release，校验压缩包、参数与
逐文件哈希，然后提取 MainBTB 闭包。查看：

```text
suites/frontend/bpu/rtl/mbtb/MainBtb.sv
suites/frontend/bpu/rtl/mbtb/filelist.f
suites/frontend/bpu/rtl/mbtb/source.json
```

RTL 获取只需要 Python 与网络。没有匹配 release 时会明确报错；本地完整生成需要显式
选择 `--rtl-source source`。下载包只提供 RTL，下一步仍需编译该 DUT 的原生仿真库。

## 4. 安装仿真工具并构建 MainBTB

依赖和工具安装到当前检出的 `.venv/`、`.tools/`，不会要求你手工搭另一套验证环境。

```sh
./scripts/ucv setup --profile runtime --jobs 2
./scripts/ucv doctor bpu --stage run
./scripts/ucv build bpu --dut mbtb --jobs 2
```

`runtime` 安装本教程所需的仿真依赖；`--jobs 2` 限制编译并发。若 `doctor` 报缺工具，
先按错误补齐再构建，常见处理见[构建经验](../lessons/build-and-toolchain.md)。

预期输出 `bpu/mbtb: BUILT + SMOKE PASS`：Picker/Verilator 已生成 Python DUT 包，并在
独立进程完成加载、复位和步进。生成绑定位于 `suites/frontend/bpu/dut/mbtb/__init__.py`。

## 5. 运行一个现有功能用例

```sh
./scripts/ucv run bpu --dut mbtb --workers 1 --seed 1 --output results/mbtb-first-ut -- \
  testbenches/mbtb/tests/testcase/test_reset.py::test_reset_completes_before_cold_lookup
./scripts/ucv report results/mbtb-first-ut
```

`--` 后的路径相对 BPU 工程。`--dut mbtb` 只检查 MainBTB 的构建，并限制测试位于
它登记的测试根。BPU 继续按实际 native owner 分进程运行。

用例执行 `reset → predict → assert_miss`；阅读代码时依次看：

1. `testbenches/mbtb/tests/testcase/test_reset.py`：激励和显式断言。
2. `conftest.py`：`mbtb_agent` fixture。
3. `testbenches/mbtb/env/agent/main.py`：事务 API 和组件组合。
4. `testbenches/mbtb/env/bundle/ports.py`、`testbenches/mbtb/checker/assertions.py`：绑定与检查。

打开 `results/mbtb-first-ut/summary.md`，再看同目录 `run.json` 与 `summary.json`。
核对 `selected_duts` 中只有 `mbtb`，种子是 1，pytest 选择是上述完整 nodeid；用例
计数以实际收据为准。`run.json` 还记录基线、源码和任务命令，便于找回这次执行。

**阅读结果时分别看 `run_status`、`counts` 和 `hardware_verdict`。** 报告保留本次实际
用例计数；运行开始冻结的问题快照中，当前基线仍开放或未复验的 open 问题会使纯 PASS
汇总为 `INCOMPLETE`，真实 FAIL/ERROR 优先。BPU 的公开输出观察限制、完整生产者
可达性和未定位失败仍须对照
[验证规格](../../suites/frontend/bpu/docs/spec/verification/README.md)审查。这个用例即使
PASS，也不能据此签核完整 BPU。旧报告因残余清单产生的 `INCOMPLETE` 和退出码只对应
当时运行；新运行的 FAIL、ERROR 和退出原因以本次日志及报告为准。

`run` / `report` 因 `INCOMPLETE` 返回非零并不表示上述命令没有执行；用日志区分真实
断言失败、环境错误与开放问题阻塞。不要通过删问题或改期望让教程变绿。

## 6. 完成与下一步

你已经走过“资料定位 → release RTL → DUT 构建/冒烟 → 一个现有用例 → 有身份的报告”。
保留 `results/mbtb-first-ut/`；它是一次有限选择的证据，不是完整 BPU 的验收报告。

- 换 DUT、选参数、比较两次运行：[运行指南](../how-to/run-tests.md)。
- 本机生成或新增 DUT：[工作空间指南](../how-to/workspace.md)。
- 开始修改用例或规格：先读 [CONTRIBUTING.md](../../CONTRIBUTING.md) 和
  [文档维护](../how-to/maintain-docs.md)，在已有 MainBTB 实现和合同内工作。
