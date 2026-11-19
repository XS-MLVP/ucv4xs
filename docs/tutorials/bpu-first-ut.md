# 第一次运行 BPU UT：MainBTB

本教程从 clone 开始，依次找到规格和源码、从源码准备 RTL、构建一个 DUT、运行现有
复位/冷查询用例并读懂报告。例子固定为 BPU 工程中的 `mbtb`，真实 RTL top 是 `MainBtb`。
完成后，你会得到一次有源码、基线和构建身份的运行记录；不需要修改 RTL、模型或用例。

## 开始前

- 仿真宿主为 Linux x86_64 或 Linux aarch64（见 [ARM 主机准备](../how-to/linux-arm-host.md)），
  准备 Python 3.12（含 venv/开发头文件）、Java 17、Git、Make、CMake、
  C++20 编译器、SWIG ≥ 4.2，以及构建 Verilator 所需的 Autoconf/Flex/Bison。
- 首次获取依赖、编译工具和完整生成香山 RTL 需要网络、磁盘、内存和编译时间；
  `setup --profile full` 安装锁定的 Mill/firtool 及仿真工具。生成资源要求见
  [构建经验](../lessons/build-and-toolchain.md)。
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

## 3. 安装工具并准备 RTL

当前默认基线 `public-e716c7658` 已登记锁定 RTL release（`xiangshan-e716c7658`）。
本教程先按 release 路线准备，最后给出显式从源码生成的做法。
依赖和工具安装到当前检出的 `.venv/`、`.tools/`。

```sh
./scripts/ucv setup --jobs 2
./scripts/ucv doctor bpu --stage rtl
./scripts/ucv prepare bpu --dut mbtb
```

默认（`--rtl-source auto`）优先复用经核验的本机完整生成，否则下载
`baselines/rtl-releases.json` 锁定的 release 包并核对压缩包与逐文件 SHA-256，
再提取 MainBTB 闭包。需要 Java 17 的源码生成路线是显式操作：

```sh
./scripts/ucv setup --profile full --jobs 2
./scripts/ucv doctor bpu --stage generate
./scripts/ucv prepare bpu --dut mbtb --rtl-source source
```

`--rtl-source source` 检出锁定源码和子模块并完整生成 DefaultConfig RTL；
已有匹配生成缓存时先核验逐文件哈希。预期输出都是 `bpu/mbtb: PREPARED`。查看：

```text
suites/frontend/bpu/rtl/mbtb/MainBtb.sv
suites/frontend/bpu/rtl/mbtb/filelist.f
suites/frontend/bpu/rtl/mbtb/source.json
```

生成结果记录在 `.cache/generated/`，闭包的 `source.json` 记录其基线和来源。
下一步编译该 DUT 的原生仿真库。其它已登记匹配 release 的基线可按
[release 获取指南](../how-to/workspace.md#使用-release-rtl)操作。

## 4. 构建 MainBTB

```sh
./scripts/ucv doctor bpu --stage run
./scripts/ucv build bpu --dut mbtb --jobs 2 --rtl-source source
```

`--jobs 2` 限制编译并发。若 `doctor` 报缺工具，
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

你已经走过“资料定位 → 源码生成 RTL → DUT 构建/冒烟 → 一个现有用例 → 有身份的报告”。
保留 `results/mbtb-first-ut/`；它是一次有限选择的证据，不是完整 BPU 的验收报告。

- 换 DUT、选参数、比较两次运行：[运行指南](../how-to/run-tests.md)。
- 本机生成或新增 DUT：[工作空间指南](../how-to/workspace.md)。
- 开始修改用例或规格：先读 [CONTRIBUTING.md](../../CONTRIBUTING.md) 和
  [文档维护](../how-to/maintain-docs.md)，在已有 MainBTB 实现和合同内工作。
