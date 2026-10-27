# 本地源码和历史证据

可选 `.ucv/local.json` 不纳入 Git。源码镜像用于加速获取，仍按版本清单检出精确提交；不会直接在镜像或历史工作区构建。

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

历史证据以 `history://<suite>/<relative-path>` 标识，索引记录 SHA-256、字节数、可用性和已解析的 JUnit 判定。`historical_roots` 负责解析本机位置。索引中的 `external-present` 是导入时状态；文件移动或丢失时应报告不可用，不能把旧判定当作本次运行结果。

公开发布只包含 Git 跟踪的验证代码、配方、文档和哈希索引。发布前执行 `git ls-files` 资产审计，勿直接打包整个工作目录。
