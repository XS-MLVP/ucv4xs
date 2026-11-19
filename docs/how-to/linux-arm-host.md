# 在 Linux aarch64 主机上准备环境

本指南用于在一台 Linux aarch64（ARM64）主机上构建 DUT 并运行 UT。
目标是得到与 x86_64 同等性质的构建和运行，不是把旧结果搬到新架构。
命令都在仓库根目录执行。

## 适用与不适用

| 目标 | 本机是否可行 |
|---|---|
| 从锁定源码安装工具链、构建 DUT、运行 UT | 可行 |
| 从源码生成整芯片 RTL（`ucv prepare --rtl-source source`） | **不可行**，见[生成路线](#生成路线没有-linux-arm64-的-firtool) |
| 使用已发布 RTL 包构建（默认路线或 `--rtl-source release`） | 可行 |

`ucv setup` 和 `ucv doctor --stage run` 接受 `Linux x86_64` 与 `Linux aarch64`；
其他系统或架构在安装和运行前直接拒绝，不会留下半成品环境。

## 1. 准备宿主依赖

与 x86_64 相同的宿主工具，按本发行版安装：

```
Java 17、Git、Make、CMake、C++20 编译器、SWIG >= 4.2
Autoconf、Flex、Bison（Verilator 源码构建需要）
Python 3.12 及其 venv、开发头文件
```

确认架构与解释器：

```sh
uname -sm          # 期望 Linux aarch64
python3.12 -V      # 期望 Python 3.12.x
```

## 2. 安装项目工具链

```sh
PYTHONPATH=src python3.12 -m ucv setup --jobs 8
```

这一步在 `.venv/` 与 `.tools/` 内完成，全部从 `dependencies/versions.json`
的锁定 commit 构建，因此没有预编译 wheel 的架构限制：

- `uc-xcomm` 从源码用 CMake + SWIG 构建（PyPI 上没有 aarch64 wheel，不需要）
- `picker` 连同 slang / fmt / yaml-cpp 从源码构建
- `verilator` 没有可复用的 seed 时从源码构建

`ucv setup` 会核对原生库的架构身份。若在 `.ucv/local.json` 里配了
`verilator_seed`，该 seed 必须是本机架构的 ELF，否则在复制前报错：

```
.../verilator_bin is built for x86_64, but this host is aarch64;
provide a seed or build it from source for this architecture
```

## 3. 安装生成工具（可选）

```sh
PYTHONPATH=src python3.12 -m ucv setup --profile full --jobs 8
```

`mill` 使用 Maven 上的架构中立启动脚本，脚本自己解析平台（含 aarch64）。
`firtool` 在 aarch64 上没有已发布构建，见下一节。

## 生成路线：没有 linux-arm64 的 firtool

CIRCT 的 `firtool-1.149.0` 只发布 `linux-x64` 与 `macos-arm64`，**没有 linux-arm64**。
因此在 aarch64 上从 Chisel 生成 RTL 需要额外准备，二选一：

1. **使用已发布 RTL 盘**（推荐）：`public-e716c7658`（`xiangshan-e716c7658`）与
   `public-a0c2a26cb` 已登记在 `baselines/rtl-releases.json`，默认
   `ucv prepare <suite>` 就会取包，不调用 firtool；`--rtl-source release` 可显式指定。
2. **自建 firtool**：把本机编译的 firtool 路径写进 `.ucv/local.json` 的 `firtool`，
   `ucv setup --profile full` 会复制并校验它是本机架构的 ELF。

没有可用 firtool 时，`ucv doctor --stage generate` 会报明原因，
`ucv setup --profile full` 也会在下载前失败，不会留下半个工具目录。

## 4. 构建并运行

```sh
.venv/bin/ucv doctor public --stage run
.venv/bin/ucv build sbuffer --dut sbuffer --jobs 8
.venv/bin/ucv run lsq --dut deq_module --seed 1 --workers 1
```

## 5. 记录结论时必须写清架构

构建缓存身份包含机器架构（`machine`），所以 x86_64 与 aarch64 的 DUT 包
互不命中，也不会互相覆盖。副作用是**同一个 DUT 在两个架构上必须分别构建**。

因此：

- x86_64 的 PASS 不能当作 aarch64 的 PASS，反之亦然
- 报告里写明主机架构、基线、工具版本和 seed，与既有报告的做法一致
- 仓库当前**没有** aarch64 的构建或运行记录；本指南描述的是可用路径，
  不构成已验证结论

## 常见失败

| 现象 | 原因与处理 |
|---|---|
| `The locked environment requires Linux x86_64 or aarch64` | 宿主架构不在支持集合，或不在 Linux 上 |
| `... is built for x86_64, but this host is aarch64` | 复用了他架构的 `verilator_seed`；换成源码构建或本机 seed |
| `No published firtool for aarch64` | 见上文生成路线，改用 RTL 发布包或自建 firtool |
| DUT 目录不命中缓存 | 正常：架构是缓存身份的一部分，需在本机重新 `ucv build` |
