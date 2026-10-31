# 本地源码和历史证据

可选 `.ucv/local.json` 不纳入 Git。可以参考根目录 `ucv.local.example.json` 创建该文件；删除不用的镜像条目，不要保留示例占位路径。源码镜像用于加速获取，仍按版本清单检出精确提交；不会直接在镜像或历史工作区构建。

```json
{
  "source_mirrors": {
    "public-893e1580b": "/path/to/XiangShan",
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

工具种子会复制到项目目录，版本与文件哈希进入安装凭据。没有种子时从固定版本获取和构建。VAGQ 必须显式提供 internal 源码路径，缺失时报错。internal 源码、RTL、波形和包含内部源码的报告只能保存在忽略目录或外部存储。

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

## 历史证据与发布边界

历史证据以 `history://<suite>/<relative-path>` 标识。`docs/history/evidence-index.json` 汇总各工程 JSONL 分片及哈希；分片记录每份证据的 SHA-256、字节数、可用性和已解析的 JUnit 判定。`historical_roots` 负责解析本机位置。索引中的 `external-present` 是导入时状态；文件移动或丢失时应报告不可用，不能把旧判定当作本次运行结果。

公开发布只包含 Git 跟踪的验证代码、配方、文档和哈希索引。发布前执行 `git ls-files` 资产审计，勿直接打包整个工作目录。
