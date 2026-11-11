# 配置本地来源与运行环境

本指南用于接入本机镜像、internal 来源、外部历史证据或可选 Toffee 开发环境。
普通公开工程的 release 路线不要求配置镜像或历史目录；默认运行环境是 `.venv/`。
所有修改只写入被 Git 忽略的 `.ucv/local.json`，不要把个人路径写进基线或工程配方。

## 配置源码镜像与工具来源

1. 用 `./scripts/ucv list <suite> --json` 查询实际命名基线。镜像键使用该名称，不是分支名
   或 DUT 键；根 `ucv.local.example.json` 中的历史基线示例也须按需要替换。
2. 文件不存在时创建 `.ucv/` 和 `local.json`；已有文件时只合并需要的字段，保留其它本地配置。
3. 从下面示例选择实际需要的条目，替换绝对路径并删除不用的字段；不要复制占位路径当成配置。

```json
{
  "source_mirrors": {
    "public-a0c2a26cb": "/path/to/XiangShan",
    "internal-d4566d58a": "/path/to/XiangShan-internal"
  },
  "dependency_mirrors": {
    "toffee": "/path/to/toffee",
    "picker": "/path/to/picker",
    "xcomm": "/path/to/xcomm"
  },
  "historical_roots": {
    "bpu": "/path/to/original-bpu-workspace",
    "lsq": "/path/to/original-lsq-workspace"
  },
  "firtool": "/path/to/firtool-1.149.0/bin/firtool",
  "mill": "/path/to/mill",
  "verilator_seed": "/path/to/verilator-5.052"
}
```

| 字段 | 用途 |
|---|---|
| `source_mirrors` | 按命名基线提供源码镜像；仍在本检出缓存中检出精确 commit、子模块和补丁 |
| `dependency_mirrors` | 按工具名提供 Toffee/Picker/xcomm 来源，加速锁定版本安装 |
| `historical_roots` | 按工程键解析历史证据目录；不是当前源码镜像，也不替代当前构建 |
| `firtool`、`mill`、`verilator_seed` | 完整本地生成/工具安装的可选来源，仍校验版本和哈希 |

工具种子会复制到项目目录，版本与文件哈希进入安装凭据；没有种子时从固定版本获取和
构建。源码镜像用于加速，不直接在镜像或原历史工作区构建。随后可执行
`./scripts/ucv doctor <suite> --stage source` 检查源码任务的宿主前置条件；只有
`prepare <suite> --source-only` 才实际获取并校验源码。

### 接入 internal VAGQ

VAGQ 必须在 `source_mirrors` 中显式提供其有效 internal 基线的实际源码目录；缺失时即使
有旧 native 缓存也会报错。先核对该条目与 `ucv list vagq` 一致，再按
[工作空间指南](how-to/workspace.md#从源码完整生成)准备环境与产物。internal 源码、RTL、
波形和包含内部源码的报告只能保存在忽略目录或外部存储，不进入公开 Git 或 release。
本地路径配置不改变工程基线，也不能让混合基线 `full` 通过统一基线检查。

## 本地 Toffee 开发环境

未提交/未发布的 Toffee 变更可以在独立 venv 中安装，并显式选择为运行环境；不移动已有
venv（其中脚本含绝对路径），不冒充公共版本锁，也不因此重写已有原生 DUT 的构建凭据。
以下字段合并到 `.ucv/local.json`，其他配置保持原样：

```json
{
  "runtime_environment": ".venv-uc-toffee",
  "development_toffee": {
    "source": "/path/to/local/toffee",
    "receipt": ".ucv/toffee-development.json"
  }
}
```

`runtime_environment` 可为仓库相对路径或绝对路径；`ucv run`、运行前校验及运行子进程的
PATH 使用其中的 `bin/python`。默认仍是 `.venv`。直接调试 pytest 时也须使用选中的
Python，而不是仅改变 PATH 后继续调用旧 venv 的绝对路径。

开发安装凭据必须与实际 wheel 和源码一致：记录完整 `base_commit`、分发名与开发版本、
wheel SHA-256、`git ls-files --cached --others --exclude-standard` 的完整文件哈希表
`source_files` 及其规范 JSON SHA-256（`source_sha256`），以及实际安装的 Toffee 包文件
哈希表 `package_files`。当前包文件范围为 `.py/.html/.css/.typed`；另记录
`runtime_binding` 的分发名、版本、`native_abi` 和 `coverage_protocol`。

运行前逐项核对源文件集合、内容、包版本、安装内容和绑定 API；源文件或安装内容变化后
必须重新测试、构建、安装并更新凭据，不能只改哈希绕过校验。运行的
`run.json.installed_tools.runtime` 记录这份开发身份和 wheel 哈希，同时保留原生 DUT
构建所用的锁定工具身份。源码与配置还纳入运行前后完整性校验。

当前公共锁使用 `uc-toffee 2.1.0` 和 `uc-xcomm 1.1.1`（ABI 3、coverage protocol 5）；
UNCERTAIN 已由正式版提供，默认 `.venv` 即可运行。`ucv setup` 从锁定源码安装，并在运行前
逐文件校验。上面的开发运行环境字段只用于尚未发布的本地框架开发，不是默认路径；使用后
必须保留源码、wheel 和安装包哈希凭据，原有 DUT 原生构建收据不改写。含 UNCERTAIN 声明的
用例需要 Toffee 2.1 或等价的开发版。

## 回归seed与原生初始化

统一入口`ucv run <suite> --seed N`将`UCV_SEED`传给工程进程；激励的随机seed和Verilator
寄存器初始化seed是两件事，必须分别确认实际消费入口，不能只看`run.json.seed`。

- 当前FTQ/ICache/IFU加载器使用`ucv.runtime.native_seed()`，不会忽略CLI seed或固定为1。
- DCache/LSU/MMU/Sbuffer的所有native加载入口在**每次构造**解析默认值，不在模块导入时
  固定。优先级为显式`seed=`参数 > `UCV_SEED` > 无CLI seed时的工程旧环境变量
  `<SUITE>_VERILATOR_SEED` > 1。普通fixture不传显式override，因此运行收据中的CLI
  seed不能被工作区旧环境变量悄悄覆盖。
- 显式seed必须是`0..4294967295`内的Python整数，bool/float/字符串不会自动强转。
  构造器参数正反对照见根`tests/test_frontend_runtime_seed.py`、
  `tests/test_ifu_runtime.py`及`tests/test_memblock_runtime_seed.py`。这些是装载边界自检，
  不是硬件功能用例；实际多seed结论仍需对应原生回归收据。
- DCache/LSU/MMU的直接运行工具也调用所属工程的同一`native_seed()`，在启动前冻结并
  校验默认值、以`UCV_SEED`传给子进程、用该保存值写provenance；不再在运行结束后另读
  legacy变量。根`tests/test_memblock_runner_provenance.py`覆盖CLI/legacy冲突、运行后
  环境变化和非法值的无副作用拒绝。这些writer控制使用stub，不代替真实native回归。

此前仅登记CLI seed2、但加载器固定1/忽略参数的历史结果保持其实际功能判定，不能重标成
真实native双seed验收。此修复不改变RTL或重建已有原生库，也不更改旧构建/运行凭据。

## 历史证据与发布边界

需要读取旧证据时，只配置 `historical_roots.<suite>` 为实际保存该次文件的根目录；没有
旧证据时可以不配置。不要指向一份新结果来冒充丢失的历史文件。

历史证据以 `history://<suite>/<relative-path>` 标识。`docs/history/evidence-index.json` 汇总各工程 JSONL 分片及哈希；分片记录每份证据的 SHA-256、字节数、可用性和已解析的 JUnit 判定。`historical_roots` 负责解析本机位置。索引中的 `external-present` 是导入时状态；文件移动或丢失时应报告不可用，不能把旧判定当作本次运行结果。

公开发布只包含 Git 跟踪的验证代码、配方、文档和哈希索引。发布前执行 `git ls-files` 资产审计，勿直接打包整个工作目录。
