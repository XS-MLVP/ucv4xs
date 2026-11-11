# ICache 运行时归档（2026-11-10）

本页记录 schema2 归属复核中确认没有活动消费者的 helper。归档是按“冻结源码 + 逐文件
SHA-256”保留，不是验证计划，也不改变任何历史报告、断言、期望或标记。

## 判定方法

扫描范围仅限活动源码：`suites/frontend/icache/`、根 `tests/`、`scripts/`、`src/` 及其他
工程源码。以下位置被明确排除，不能当作活动引用：`results/`、`build/`、`.history/`、
`docs/history/`、`.cache/`、`.tools/`、`XiangShan/`、`__pycache__/`。对每个候选同时检查：

1. 静态 `import` / `from ... import`，包括相对导入；
2. 字符串形式的模块名（根 `conftest.py` 的 `pytest_plugins`、动态导入字符串）；
3. 根插件注册链；
4. 跨工程源码消费者（根测试、其他 suite）；
5. 文件自身是否有显式 CLI 入口（`main` / `argparse` / `__main__`）。

判定结果保存在 `results/testbenches-all-20261110/icache/ownership-scan.json`；归档清单和
逐文件哈希在 `results/testbenches-all-20261110/icache/archive-manifest.json` 与
`archive/SHA256SUMS`。

## 归档清单

归档副本位于本机 `results/testbenches-all-20261110/icache/archive/`，不进入 Git；
下表的 hash 是归档时冻结的字节身份。`原始 runtime hash` 来自迁移前的
`source-before.json`，用于追溯，不等同于当前字节。本轮已执行
`cd results/testbenches-all-20261110/icache/archive && sha256sum -c SHA256SUMS`，
10 个归档副本全部校验成功。另有 2 个仅注释 runtime 空壳
（`runtime/checkers/__init__.py`、`runtime/model_parameters.py`）在首次迁移时删除，
记录在 `removed-files.json` 的 `removed` 字段，不在本轮归档目录。

| 原 runtime 路径 | 最后 suite 路径 | 当前 SHA-256 | 原始 runtime SHA-256 | 无活动消费者的依据 |
|---|---|---|---|---|
| `runtime/coverage/local_guards.py` | `testbenches/shared/coverage/local_guards.py` | `a260060a661d96b7…` | `e829e3f1e8ad14e5…` | 无 import、无动态字符串、无根插件、无 CLI、无跨工程消费者；BPU 保留自己的活动实现 |
| `runtime/coverage/replay.py` | `testbenches/shared/coverage/replay.py` | `08342825657ba837…` | 同左 | `CoverageReplay` 无 import/动态引用/CLI |
| `runtime/ports/activity.py` | `testbenches/shared/env/bundle/activity.py` | `caf21916c93ee93e…` | `2da44220ef96e119…` | `bind_activity` 从未被调用 |
| `runtime/drivers/handshake.py` | `testbenches/shared/env/driver/handshake.py` | `5d0f5e2ecdcefd55…` | `24e4f5fa0626cb8f…` | `HandshakeDriver` 无消费者；WayLookup 明确使用 `LevelDriver` 并说明逐端口握手驱动会交错共享沿 |
| `runtime/monitors/activity.py` | `testbenches/shared/env/monitor/activity.py` | `cdd9a93b5b1b32bc…` | `d4b94144665816fd…` | `ActivityMonitor` 无 import/动态引用/CLI |
| `runtime/monitors/__init__.py` | `testbenches/shared/env/monitor/__init__.py` | `1c7e7c7ce36c9495…` | `4fa49ce02aa53ac8…` | 仅包 docstring；`CycleMonitor` 迁回 WayLookup 后 shared monitor 无实现 |
| `runtime/paths.py` | `testbenches/shared/env/paths.py` | `5a0d70e426b46c57…` | 同左 | 仅 `REPO_ROOT` 别名，无消费者；工程 ROOT 统一从包入口解析 |
| `runtime/timing.py` | `testbenches/shared/env/timing.py` | `0e4dd4b60c1cc99e…` | 同左 | `CaseTiming` 无 import/动态引用/CLI |
| `runtime/wait.py` | `testbenches/shared/env/wait.py` | `bca634abb7040f1b…` | 同左 | 唯一消费者是已归档的 `ActivityMonitor`；无其他活动路径 |
| `runtime/coverage/phase_audit.py` | `tools/coverage_phase_audit.py` | `d103bc1e7a6f72d5…` | `1de3978282e0ea0a…` | 有显式 CLI，但硬编码输入 `rtl/tage/WriteBuffer.sv` 与 `tools/coverage_phase_repro.cpp` 在本工程不存在；无 import/文档命令；BPU 保留自己的活动工具 |

## DUT 归属回归

`runtime/monitors/cycle.py` 的 `CycleMonitor` 是唯一仍有活动消费者的 monitor。排除未使用的
`ActivityMonitor` 后，唯一直接消费者是 `testbenches/waylookup/env/agent/main.py`，因此
迁到 `testbenches/waylookup/env/monitor/cycle.py`，由 WayLookup 的 env 所有；不再作为
shared 组件。文件字节除类 docstring/注释中去除 BPU/TAGE 措辞外未改变，行为未改。

## 保留的活动 shared 组件

归档后，`testbenches/shared/` 下的每个实现都有至少一个实际活动通道：多 DUT import
（如 `array_agent.py`、`sram.py`、`bindings.py`）、统一 loader（`dut.py`、`memory_direct.py`）、
根插件注册链（`pytest_plugins/*`、`trace.py`、`artifacts.py`、`validation.py`），或
tools 共享机制（`coverage/verilator.py` 由 native 运行时和 `tools/rtl_coverage.py` 共同使用）。
逐项 importers 和 DUT 复用证据见 `ownership.json`。

## 明确未恢复的事实

旧 `modules/`、`runtime/` 下删除的 249 个 `.pyc` 仍没有逐文件缓存清单。一次性迁移脚本在
写逐目录 manifest 前因过宽的 pyc 断言中止，未留下逐文件哈希；本页和
`removed-files.json` 保留这一限制，不伪造恢复。源码文件的逐文件哈希和归档哈希不受影响。
