# 在 macOS 上准备环境

本指南用于在 Apple Silicon（arm64/aarch64）或 Intel（x86_64）Mac 上安装项目工具链、
从完整香山 RTL 发布包构建 DUT 并运行 UT。所有项目命令在仓库根目录执行。
工具、Python 环境和生成结果分别保存在 `.tools/`、`.venv/` 和忽略的缓存/结果目录。

## 准备宿主依赖

安装当前 Xcode Command Line Tools，并准备 Homebrew：

```sh
xcode-select --install
brew install python@3.12 cmake swig autoconf bison flex help2man pkg-config zlib lz4
```

已有 Command Line Tools 时无需重复安装。C++ 编译器需支持 C++20，SWIG 需 ≥ 4.2；
Python 必须是 3.12。若 Homebrew 的 Python 未进入 PATH，将其 `bin` 加入当前 shell：

```sh
export PATH="$(brew --prefix python@3.12)/bin:$PATH"
python3.12 --version
uname -sm
```

Apple Silicon 上 `uname -m` 通常为 `arm64`，项目将其规范为 `aarch64`。
使用与当前 Python 进程架构一致的编译器和 Homebrew；不要混用 Rosetta 的 Intel 工具与原生 ARM Python。
`ucv` 自动查询 `brew --prefix`，让安装于该前缀的 Bison/Flex、头文件和库在项目子进程中可见；
不需要覆盖系统的 `/usr/bin/bison`，也不修改用户的 shell 配置。

## 安装并检查

```sh
bash scripts/ucv setup --jobs 4
.venv/bin/ucv doctor bpu --stage rtl
.venv/bin/ucv doctor bpu --stage run
```

`setup` 从 `dependencies/versions.json` 的锁定源码构建 xcomm、Picker 与 Verilator，
安装锁定的 Python 包，不依赖 Linux wheel。构建并行度按本机内存调整。
安装日志位于 `.tools/setup.log`，成功收据位于 `.tools/receipt.json`，其中记录 `Darwin` 与实际架构。
缺少宿主工具会在开始安装前列出。
锁定的工具补丁处理 Flex 头文件接口与 FST 的 lz4 依赖；C++ DUT 不需要额外安装 SystemC。
Mill/firtool 在临时目录中下载并完成检查后才安装；下载失败可直接重试，不会把半文件当作
已安装工具。Verilator 仅在工具锁、宿主和二进制哈希均与收据一致时复用，需重建时提前检查源码构建依赖。

## 构建并运行一个 DUT

以下是 BPU/MainBTB 示例，默认从 `baselines/rtl-releases.json` 下载锁定的完整香山 RTL，
再提取 MainBTB 闭包，不需要 Java 或本机生成整芯片 RTL：

```sh
.venv/bin/ucv build bpu --dut mbtb --jobs 4
.venv/bin/ucv run bpu --dut mbtb --workers 1 --seed 1 \
  --output results/mbtb-macos-first -- \
  testbenches/mbtb/tests/testcase/test_reset.py::test_reset_completes_before_cold_lookup
.venv/bin/ucv report results/mbtb-macos-first
```

输出目录必须尚不存在。此处的单用例不构成 BPU 整体功能验收；报告中的开放问题、
真实 FAIL/ERROR/UNCERTAIN 与覆盖边界仍按既有合同解释。

macOS 上仿真动态库是 `libUT<export_name>.dylib`，Python 扩展仍为 `_UT_<export_name>.so`。
项目按这两个不同后缀检查完整包，并运行独立进程冒烟。

## 可选：从 Chisel 生成 RTL

Apple Silicon 可自动下载锁定的 `firtool-1.149.0` macOS arm64 包：

```sh
brew install openjdk@17
export JAVA_HOME="$(brew --prefix openjdk@17)/libexec/openjdk.jdk/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"
bash scripts/ucv setup --profile full --jobs 4
.venv/bin/ucv doctor bpu --stage generate
.venv/bin/ucv prepare bpu --dut mbtb --rtl-source source --jobs 4
```

完整生成的内存要求见[构建经验](../lessons/build-and-toolchain.md)。
Intel macOS 没有该 firtool 版本的发布包，应使用默认 RTL release 路线，或通过
`.ucv/local.json` 的 `firtool` 字段提供本机编译的同版本工具。
预编译 `firtool` / `verilator_seed` 同时检查 Mach-O 格式和架构；universal binary 包含本机架构即可。
Linux ELF 即使也是 ARM64 也会被拒绝。

## 切换平台与排错

不要把别的平台或旧绝对路径的 `.venv/`、`.tools/` 当作新环境复用。
保留旧环境到独立备份位置，再在当前检出中重新 `setup`。
原生 DUT 缓存身份包含操作系统、架构及构建流水线版本；跨系统/架构必须重新构建。
完整 RTL 发布包不含本机原生库，可在核验哈希后继续使用。

| 现象 | 处理 |
|---|---|
| `Missing host build tools: ...` | 按第一节安装缺少的依赖，确认 Homebrew 在 PATH 中 |
| `Expected a macOS Mach-O binary` / `built for ...` | 换成本机系统与架构的 seed，或从源码重建；不要复制 Linux 二进制 |
| `Installed tools were built for Linux ... Darwin` | 保留旧环境后在 Mac 上重新安装 |
| `No published firtool for Darwin x86_64` | 使用 RTL release 或配置本机同版本 firtool |
| `library 'lz4' not found` | 安装 Homebrew lz4，确认使用同一架构的 Homebrew |

平台安装、DUT 构建/冒烟与硬件功能判定是独立结论。实际核验范围见[当前状态](../status.md)。
