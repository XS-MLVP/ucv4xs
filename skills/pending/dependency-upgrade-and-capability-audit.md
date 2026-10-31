---
name: dependency-upgrade-and-capability-audit
description: 升级项目虚拟环境与锁定依赖，处理 Python 分发名变化、源码补丁和原生 ABI 校验，并确认框架实际提供的能力。适用于依赖落后、需要引入新框架能力或核对环境是否可复现时。
---

# 依赖升级与能力核对（待审核）

## 何时使用、准备什么

- 虚拟环境的框架版本落后于上游发布版；
- 需要确认某个能力（例如 UNCERTAIN、Agent、覆盖统计）是否真的由框架提供；
- 上游把 Python 分发名改了（`pytoffee` → `uc-toffee`、`xspcomm` → `uc-xcomm`）；
- 原生构建缓存身份会因为工具版本变化而变化，需要提前说明重建范围。

准备：可用的网络或镜像、仓库根目录、`.venv`、`.tools/sources/`、以及一次新的结果目录。
先记录当前事实，不要先改锁：

```sh
.venv/bin/python -m pip freeze > /tmp/venv-before.txt
git -C .tools/sources/toffee log -1 --format='%H %d %s'
git -C .tools/sources/xcomm log -1 --format='%H %d %s'
cat dependencies/versions.json
```

## 第一步：确认上游版本与分发名

查 PyPI 和源码 tag，不要只看 `pip list`：

```sh
.venv/bin/python -m pip index versions uc-toffee
.venv/bin/python -m pip index versions uc-xcomm
git -C .tools/sources/toffee ls-remote --tags origin | tail -20
git -C .tools/sources/xcomm ls-remote --tags origin | tail -20
```

本轮事实：`uc-toffee 2.1.0`（tag `v2.1.0`）已发布 UNCERTAIN、`toffee.outcomes`
和 `toffee._pytest_outcomes`；`uc-xcomm 1.1.1`（tag `v1.1.1`）保持
`native_abi=3`、`coverage_protocol=5`。分发名和导入名不同：安装名是
`uc-toffee`/`uc-xcomm`，导入名仍是 `toffee`/`xspcomm`。

## 第二步：更新锁，而不是先装包

同时更新：

- `dependencies/versions.json`：完整 commit、`distribution`、`package_version`、
  `native_abi`、`coverage_protocol`、补丁清单与哈希；
- `dependencies/python.txt`：基础测试与构建依赖，按 `pyproject.toml` 的约束选择
  最高兼容版本（例如 `setuptools-scm` 若上游要求 `<10`，不能盲升到 10）；
- `.tools/sources/<name>`：精确检出到锁定的 commit；有补丁时先确认补丁能在新版本上
  `git apply --check`，再让 `ucv setup` 应用并写入 `.ucv-patches.json`。

原生 DUT 的缓存身份包含工具锁。升级工具后，已有 DUT 构建可能全部需要重建；这必须在
记录中说明，不能把旧 DUT 的 PASS 当成新工具链的 PASS。若升级只影响运行时且不影响
生成/构建，才考虑调整缓存身份；调整本身要有独立理由和验证。

## 第三步：处理分发名与安装接口

升级前先移除旧分发，避免两个发行版同时提供同一个导入包：

```sh
.venv/bin/python -m pip uninstall -y pytoffee xspcomm
.venv/bin/python -m pip install -U -r dependencies/python.txt
.venv/bin/ucv setup --jobs 64
```

`ucv setup` 需要与新分发名一致：

- setuptools-scm 的版本环境变量按规范化分发名生成，例如
  `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_UC_XCOMM`；
- `.tools` 的 CMake 版本参数使用锁定的 `package_version`，不要再写死旧版本；
- `ucv.runtime` 读取版本时使用 `distribution`，保留旧名只作为显式兼容回退；
- pytest 插件名从 `toffee._outcomes` 更新为 `toffee._pytest_outcomes`。

源码补丁要重新核对，不可因为“版本升了”就假定补丁仍生效。用干净检出验证：

```sh
patch_file="$(pwd)/dependencies/patches/<patch>"
mkdir -p .cache/tmp
tmp=$(mktemp -d .cache/tmp/xcomm-patch-check.XXXXXX)
git -C .tools/sources/xcomm archive <commit> | tar -x -C "$tmp"
git -C "$tmp" init -q
git -C "$tmp" apply --check "$patch_file"
```

## 第四步：核对实际能力，不靠文档猜

```sh
.venv/bin/python -c "import toffee, xspcomm; print(toffee.__file__); print(xspcomm.abi_version(), xspcomm.XTriggerEngine.CoverageVersion())"
.venv/bin/python -c "import toffee; print([n for n in dir(toffee) if not n.startswith('_')])"
.venv/bin/python -c "import importlib.util; print(importlib.util.find_spec('toffee._pytest_outcomes'))"
.venv/bin/python -c "import importlib.metadata as m; print(m.version('uc-toffee'), m.version('uc-xcomm'))"
```

能力核对表（入口存在已核对；不代表对所有 API 的完整行为认证）：

| 能力 | 入口 | 工程侧责任 |
|---|---|---|
| UNCERTAIN 分类与 pytest 显示 | `toffee.outcomes`、`toffee._pytest_outcomes` | 只写声明，不伪造证据；真实 FAIL 优先 |
| Agent + 响应检查 | `toffee.Agent`、`Scoreboard` | 端口绑定、接受条件、参考模型 |
| 单/多周期驱动 | `SyncSingleCycleDriver`、`AsyncSingleCycleDriver`、`SyncMultiCycleDriver`、`AsyncDriver` | 协议时序、idle、撤销 |
| 被动采样 | `SamplingMonitor`、`ReadyValidMonitor` | 有效条件、解码、快照类型 |
| 功能覆盖 | `CoverGroupDef`、`CoverPointDef`、`CrossDef` | 覆盖点语义 |
| 原生行/分支覆盖 | `toffee run` + 原生 collector | 闭包映射与报告口径 |

## 第五步：验收与证据边界

```sh
.venv/bin/python -m pytest -q tests
.venv/bin/ucv list public --require-unified-baseline
.venv/bin/ucv doctor bpu
```

再选一个不依赖原生重建的纯模型用例目录（例如 BPU `tests/ubtb/scoreboard`）验证新框架
能收集和执行。需要原生 DUT 时，必须按新缓存身份重建并保留构建/冒烟收据；未重建的
DUT 明确写“未验证”，不能用旧收据补位。

记录：升级前后版本、分发名、commit、补丁哈希、ABI、根测试计数、未重建范围。
