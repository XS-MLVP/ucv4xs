# 验证包布局审计与迁移（2026-10-30）

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


## 原问题

BPU 与 ICache 都采用“每个 DUT 一个验证子包”的目录，但 pytest 接线分散：

- BPU：`bpuverify/<dut>/env/pytest.py` 定义 agent fixture，`tests/<dut>/conftest.py` 只做转发；
- ICache：同样是 11 个 `env/pytest.py` 加 11 个转发 conftest；
- 功能 testcase 仍直接使用 `agent.dut.clock` 或 level driver，测试与物理引脚没有边界；
- 公共自检没有 `selftest` 标记，容易被当成硬件功能用例。

这不是目录美观问题：fixture 分散会让新增 DUT 复制接线，直接引脚访问会让测试无法只靠
事务复现，也无法用布局审计发现“观测到了但没有比较”。

## 修正

1. 把 BPU 10 个 DUT、ICache 11 个 DUT 的 agent fixture 收敛到各自 `tests/conftest.py`；
   非 agent 的产物 fixture 移到 `common/pytest/artifacts.py` 插件；删除
   `bpuverify/*/env/pytest.py`、`icacheverify/*/env/pytest.py` 及所有子目录转发 conftest。
2. 给 `tests/framework` 自动加 `pytest.mark.selftest`，并在 `pytest.ini` 注册 marker；
   既有功能点报告分类规则不变，`selftest` 只用于硬件验收时排除环境自检。
3. 补 agent API：BPU `wait_cycles`；ICache `write_with_flush`。功能 testcase 不再直接
   数 `dut.clock`、操作 level driver。
4. 新增只读审计脚本 `scripts/audit-suite-layout.py`；BPU/ICache 的
   `test_repository_layout.py` 加入根 fixture 唯一、无嵌套 conftest、功能用例无直接
   `.dut.`/`.pins.` 的检查。

## 审计结果

```sh
.venv/bin/python scripts/audit-suite-layout.py
```

| 工程 | 状态 | 说明 |
|---|---|---|
| BPU | ok | 11 个根 fixture；397 个功能用例；无直接访问 |
| FTQ | ok | 3 个根 fixture；20 个功能用例；无直接访问 |
| ICache | ok | 11 个根 fixture；44 个功能用例；无直接访问 |
| IFU | backlog | 旧 harness 仍以扁平 `ifu` fixture 为主，testcase 使用公开端口名/宽度探针 |
| DCache / MMU / LSQ / LSU / Sbuffer / VAGQ | backlog | 旧环境仍有直接 `dut`、物理端口或嵌套 conftest；本次未迁移 |

backlog 不是通过项。迁移这些工程前，要保留现有功能判定和已知 FAIL/XFAIL，先建立
agent 事务 API，再改测试；不能为了审计变绿删掉真实端口观察。

## 验证

- 根测试：`58 passed`（新 `uc-toffee 2.1.0`，无 SKIP）。
- BPU：`tests/ubtb/testcase` 原生 **45 PASS**、`tests/ras/testcase/test_push_pop.py`
  **5 PASS**、`tests/sc/testcase/test_directions.py` **2 PASS**；`tests/ubtb/scoreboard`
  纯模型 **132 PASS**；BPU 布局与指定框架测试 **8 + 172 PASS**，ICache 布局测试
  **9 PASS**。
- ICache：`tests/waylookup/testcase/test_flush.py` **7 PASS / 1 XFAIL**（既有 strict
  XFAIL 保留）；全工程收集 **293** 项。
- BPU 8 个 DUT（abtb/ittage/mbtb/ras/sc/ubtb/uras/utage）、`icache/waylookup` 和
  Sbuffer 两个 DUT 均 `BUILT + SMOKE PASS`。
- 统一入口 `ucv run sbuffer --workers 1` **31 PASS**，manifest `committed`、
  `coverage_complete=true`，`ucv report` PASS 且无产物缺口。

未完成：BPU 的 `tage` 与 `bpu` 顶层在构建窗口内未完成，仍指向旧缓存；其余 121 个
DUT 未重建；全工程原生回归、全量覆盖率合并未执行。工具锁变化会改变构建缓存身份，旧
DUT 收据不能替代新构建，结论只适用于本轮实际运行的范围。
