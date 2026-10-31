# 十工程布局迁移与 Pin Schema（2026-10-31）

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


> 同日复核更正：本文保留该轮改动与历史运行结果，但“端口别名替换等于事务迁移”、
> “pin fields=0”与“fixture 条目数等于 owner 数”的结论撤回。修正审计仍发现六工程
> 有引脚级耦合；真实构建/回归结果不改写。见
> [目录与 skill 复核](structure-skill-review-20261031.md)。

## 原问题

上一轮只迁移了 BPU 与 ICache。其余七个工程仍各自维护 fixture 与物理端口名：

- IFU：`pytest_plugins` 导入 fixture 模块，测试直接写 `io_*` 和 `harness.read("io_*")`；
- LSQ：11 个 `tests/<dir>/conftest.py`，根 conftest 与子目录同名 fixture 并存；
- MMU：387 处 `execution(env.dut)`，33 处 `env.dut.RefreshComb()` 与整片端口扫描；
- DCache：`ProbeEnv`/`WbqEnv` 定义在 testcase 文件里，环境直接用 `self.dut.Step()`；
- LSU/Sbuffer/VAGQ：fixture 在工程根 `conftest.py`，不在 pytest 根；
- 所有工程都缺少统一的 `selftest` 注册。

直接症状是“测试在写引脚”，但根因是边界没有可执行契约：没有一条命令能同时回答
“fixture 是否唯一、测试是否还在碰 native DUT、自检是否混入硬件 credit”。

## 修正

1. **单一根 fixture 表。** BPU/FTQ/ICache/LSQ/VAGQ 用 `tests/conftest.py`；DCache/LSU/MMU/
   Sbuffer 把 fixture 从工程根 `conftest.py` 移入 `tests/conftest.py`，工程根只保留
   `sys.path` 设置与插件注册。
2. **LSQ 嵌套 conftest 合并。** 11 个目录的 conftest 内容移到
   `lsqverify/<dir>/fixtures.py`；根 conftest 用同名 dispatcher 按测试路径分派，
   所以测试参数名（`lsq`、`raw`、`replay`）完全不变。
3. **Pin schema。** 新增 `common/pins.py`：常量 `P.p_<name>` 与 `P.io(...)`。
   迁移用 Python 3.12 token 逐字符串替换，f-string 按
   `FSTRING_START/MIDDLE/END` 处理；不能整文件正则替换。
4. **原生访问收口。** `execution(env.dut)` → `execution(env)`；`step/refresh/set_reset`
   放进 `common/runtime.py`；MMU 的结构性 bit sweep 移入 `runtime.sweep_inputs()`；
   VAGQ 的 `NativeSplit` 移入 `vagqverify/split/native.py`；DCache 的 `ProbeEnv`/`WbqEnv`
   移入 `dcacheverify/<dut>/env.py`。
5. **selftest 统一。** 新增共享插件 `src/ucv/pytest_selftest.py`，按 `framework/`、
   `checkers/`、`selftest/`、`diagnostics/` 路径自动标记；删除 BPU/ICache 各自的插件副本。
6. **门禁。** `scripts/audit-suite-layout.py` 只读审计；`tests/test_suite_layout.py`
   把它固化为根测试（9 项），`--strict` 全工程返回 0。

## 审计前后

```sh
.venv/bin/python scripts/audit-suite-layout.py
```

| 指标 | 迁移前 | 迁移后 |
|---|---:|---:|
| 有原生访问的功能用例文件 | 33 | 0 |
| 嵌套 conftest | 11 | 0 |
| 未注册 selftest 的工程 | 7 | 0 |
| 功能用例中的 pin 字面量 | 约 1080 | 0 |

## 真实判定（保留，不改写）

| 工程 | 结果 |
|---|---|
| 根 `tests/` | 67 PASS |
| IFU | 144 PASS / 2 FAIL / 1 UNCERTAIN |
| LSU | 522 PASS / 7 FAIL |
| DCache | 210 PASS / 3 XFAIL |
| MMU | 408 PASS |
| Sbuffer | 31 PASS |
| ICache | 291 PASS / 3 XFAIL |
| FTQ | 109 PASS / 2 XFAIL |
| VAGQ | 433 PASS / 1 FAIL / 33 SKIP |
| LSQ | 2325 PASS / 250 FAIL（与迁移前同集合，manifest committed、覆盖完整） |

失败项与迁移前同一集合：IFU 的 `FrontendTrigger tdata2` 宽度缺陷、LSU 的 7 项上游
接口/静态断言、VAGQ 的 MaskGen `elemActiveMask` 独立窗口模型偏差。

LSQ 首次统一运行（`results/ucv-lsq-20261031`）已得到 2325 PASS / 250 FAIL，但运行期间
仓库源码被本轮其他编辑改动，`ucv report` 按设计判为
`Run integrity error: verification source changed during execution`，因此该目录不作为
接收凭据。冻结源码后在新目录 `results/ucv-lsq-final-20261031` 重跑，得到相同计数，
manifest `committed`、`coverage_complete=true`、`ucv report` 无产物缺口。XFAIL 均为已登记
strict 缺陷，未转成 PASS。

## 构建

`ucv build public --require-unified-baseline --jobs 64` 完成 118 个公开 DUT；
BPU `tage`、`bpu` 顶层随后 `BUILT + SMOKE PASS`；`ucv build vagq` 完成 12 个 internal
DUT；`ucv build sbuffer` 完成 2 个。合计 132 个 DUT 都有本次冒烟收据，旧收据未被复用。

## 未证明范围

- 本轮没有重跑 VAGQ 的 exhaustive/ISA audit 长集合（`vagq_exhaustive`、`vagq_isa_audit`
  标记）；33 个 SKIP 保持 SKIP。
- 覆盖率只按各工程既有采样，未做跨工程统一合并与缺口重算。
- 布局迁移不改变任何功能判定；它证明的是接线与访问边界，不是硬件正确性。
