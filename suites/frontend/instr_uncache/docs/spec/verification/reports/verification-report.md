# InstrUncache 验证报告

日期：2026-11-08  
基线：`public-a0c2a26cb`（commit `a0c2a26cbe3c862175174bad03a1a23c406315ed`）  
设计配置：DefaultConfig，1 core  
结论边界：`InstrUncache` / `InstrUncacheEntry` / `Arbiter1_InstrUncacheResp`；
**不是** Frontend、ICache/IFU 或芯片验收。

## 1. 环境与工具

| 项 | 版本/身份 |
|---|---|
| Python | 3.12.3 |
| uc-toffee | 2.1.0，source `f57150021791535d4b2fd01056c106f0cad53177` |
| Picker | source `4dd442c4a80c92549381e417c608836e3b78a8e9` |
| uc-xcomm | 1.1.1，source `2e4a4a99293360c2a642025000c6948b24cf8e88`，native ABI 3 / coverage 5 |
| Verilator | 5.052（`verilator_bin` sha256 `ccf4908b…`） |
| firtool | 1.149.0 |
| Chisel / mill / Java | 7.13.0 / 0.12.17 / 17 |
| 整芯片生成缓存 | `d7c6bc4d17651fc1bd92ac39c469410a6bb91215f46c1efcfaf1ec66a72e972d` |
| 源码缓存 | `.cache/sources/f3ac6022d07c5c05d28869ac811f91038f9103677796dd6f051bd1981408be9b` |

生成命令（缓存 `generation.json` 记录）为完整 DefaultConfig TopMain：
`--config DefaultConfig --num-cores 1 --target systemverilog --split-verilog
--firtool-binary-path .tools/bin/firtool --firtool-opt -O=release
--default-layer-specialization=disable --fpga-platform --reset-gen --issue E.b
--llc OpenLLC`。本轮没有改 RTL，也没有新增生成入口。

## 2. 实际命令

```sh
.venv/bin/ucv doctor instr_uncache --require-unified-baseline
.venv/bin/ucv prepare instr_uncache --require-unified-baseline --jobs 4
.venv/bin/ucv build instr_uncache --require-unified-baseline --jobs 4
.venv/bin/ucv run instr_uncache --workers 1 --seed 1 \
  --require-unified-baseline --output results/instr-uncache-seed1-flush-closure
.venv/bin/ucv run instr_uncache --workers 1 --seed 2 \
  --require-unified-baseline --output results/instr-uncache-seed2-flush-closure
.venv/bin/python suites/frontend/instr_uncache/tools/coverage_report.py \
  --manifest results/instr-uncache-seed1-flush-closure/instr_uncache/manifest.json \
  --output results/instr-uncache-seed1-flush-closure/coverage.json \
  --markdown results/instr-uncache-seed1-flush-closure/coverage.md
.venv/bin/python suites/frontend/instr_uncache/tools/audit_flush_closure.py
```

`prepare` 输出：三个 DUT 均 `PREPARED`。`build` 输出：三个 DUT 均
`BUILT + SMOKE PASS`（独立进程 smoke，包含 ABI/coverage 版本和零输入冒烟）。

## 3. RTL 与构建身份

| DUT | cache key | RTL 文件 | sha256 |
|---|---|---|---|
| `instr_uncache_entry` | `83b12cd2069c1f68fd7dedb133a9b5a94ce4d276dea676348152e3cf68fca797` | `InstrUncacheEntry.sv` | `7c1fec63a64b9619ffea39e1a4d0711628f235c8e56676fca6550fc89185d7b6` |
| `instr_uncache_resp_arbiter` | `96f1766d822a76583acbeed6a03ffafc08e90e632898c36ac4633c84db0b1f47` | `Arbiter1_InstrUncacheResp.sv` | `35a2b18d15340af9f07908943cf87497b2fa49ebd592017b6d494d70712f36f3` |
| `instr_uncache` | `e3c7b2f318c3e16f1a8bdcb292e77d06636dc5814e48f644181493bb879c9eb9` | `InstrUncache.sv` | `a91b3c2cd2744a91a14ae1a952cc6f65de236c85877687aab2da5ff2377ceb14` |
|  |  | `InstrUncacheEntry.sv` | `7c1fec63a64b9619ffea39e1a4d0711628f235c8e56676fca6550fc89185d7b6` |
|  |  | `Arbiter1_InstrUncacheResp.sv` | `35a2b18d15340af9f07908943cf87497b2fa49ebd592017b6d494d70712f36f3` |

三个 RTL 哈希与整芯片生成缓存 `generation.json` 的 `rtl` 清单逐字节一致；顶层
闭包包含真实 Entry/Arbiter，不是 Python 模型替代。native 产物哈希保存在各次运行的
`instr_uncache-builds.json`：

- Entry：`_UT_InstrUncacheEntryDut.so` `532ce7d4…`、`libUT…so` `1692fdfd…`；
- Arbiter：`_UT_InstrUncacheRespArbiterDut.so` `550de0ef…`、`libUT…so` `cb5ef2e0…`；
- 顶层：`_UT_InstrUncacheDut.so` `733f9cbd…`、`libUT…so` `b592fb6f…`。

## 4. 运行结果

| 运行 | seed | nodeid | PASS | UNCERTAIN | FAIL | ERROR | XFAIL/SKIP | 源码前后稳定 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `results/instr-uncache-seed1-flush-closure` | 1 | 68 | 68 | 0 | 0 | 0 | 0 | 是（`064f4f44…`） |
| `results/instr-uncache-seed2-flush-closure` | 2 | 68 | 68 | 0 | 0 | 0 | 0 | 是（`064f4f44…`） |
| `results/instr-uncache-seed1-incomplete-20261108` | 1 | 68 | 68 | 0 | 0 | 0 | 0 | 是（`064f4f44…`） |

前两轮 nodeid 完全一致。**用户确认保守口径后，最终 `summary.json` 为
`run_status=PASS`、`hardware_verdict=INCOMPLETE`**（`FRONTEND-FLUSH-CONNECT`
blocking/open）、`migration_acceptance=NOT_CERTIFIED`；`gaps` 只有这一条阻塞残余，
`residual_summary.blocking_open=1`。单元可达行为为 68 PASS，但 flush 连接的设计
决定未被验证，不能读成“flush 已验证”或硬件 PASS。`migration_acceptance` 仍是
仓库级 `NOT_CERTIFIED`，需要单独验收证据。

功能点报告（每次运行复制到结果目录 `feature-points.json`）：

| 分区 | planned | executed | PASS | UNCERTAIN | FAIL/ERROR | consistency errors |
|---|---:|---:|---:|---:|---:|---:|
| hardware | 13 | 13 | 13 | 0 | 0 | 0 |
| environment | 4 | 4 | 4 | 0 | 0 | 0 |

nodeid 对账（相对收口前 `results/instr-uncache-seed1-final2`，66 项）：**新增 2、
删除 0**，即两个闭包证据用例；唯一判定变化是
`tests/instr_uncache_entry/test_entry.py::test_flush_path_is_structurally_pruned`
由 `UNCERTAIN` 变为 `PASS`。该变化属于**环境结构检查**（裁剪与哈希一致），
不是 flush 行为 PASS，也不改变硬件功能点计数（13/13 在收口前后都是可达行为的
功能点，原先唯一未决点是环境结构项的 UNCERTAIN）。

## 5. 逐 DUT 判定

| DUT | 构建/冒烟 | 定向 | 随机（seed 1/2） | 判定 |
|---|---|---|---|---|
| `instr_uncache_entry` | PASS | 请求/对齐/4B 抽取/resend/跨页/异常/WFI/单 outstanding/reset/响应丢失全部通过 | 各 320 拍逐拍模型比较 | **PASS**（flush 行为不在范围） |
| `instr_uncache_resp_arbiter` | PASS | 6 个恒等向量 + 8 组错误位组合全部通过 | 各 400 向量 | **PASS** |
| `instr_uncache` | PASS | 端到端、地址/窗口、resend、跨页、异常、WFI、单 outstanding、source 过滤、reset 全部通过 | 各 320 拍组合模型比较 | **PASS**（不含 flush/Frontend 交互） |

这里的 PASS 是三个模块的单元合同判定，不是 Frontend 或芯片验收。

## 6. 失败分类

- 新 RTL FAIL：**0**。
- ERROR：**0**。
- XFAIL/XPASS/SKIP：**0**。
- UNCERTAIN：**0**。原 `INC-FLUSH-012` 的 UNCERTAIN 已按结构证据分类为环境检查点，
  不是改写成硬件 PASS：flush 行为仍未验证，见下节。
- 未确认的新缺陷：0。没有用 XFAIL 或删除反例换取通过。

### R-FLUSH 收口（2026-11-08）

**最终分类：out-of-domain / accepted-limited。** 证据链：

| 证据 | 值 |
|---|---|
| 唯一实例 | `Frontend.scala:125` `LazyModule(new InstrUncache)` |
| flush 固定 | `Frontend.scala:266` `instrUncache.io.flush := false.B` |
| Entry 透传/使用 | `InstrUncacheImp.scala:65`；`InstrUncacheEntry.scala:41,58-63,100,162` |
| 其他实例路径 | `EnableSimFrontend=false`（`Parameters.scala:632`）；`SimFrontend.scala:195` 整个 io 接 0 |
| 生成 Top | `InstrUncache.sv`，24 端口，无 `flush`/`needFlush`，sha256 `a91b3c2c…` |
| 生成 Entry | `InstrUncacheEntry.sv`，23 端口，无 `flush`/`needFlush`，sha256 `7c1fec63…` |
| 生成 Frontend 实例 | `Frontend.sv:2763` `inner_instrUncache`，无 `.io_flush`，block sha256 `3b09cd6e…` |
| 机器证据 | `docs/spec/verification/evidence/flush-closure.json`，`tools/audit_flush_closure.py` 可复核 |

因此 `R-FLUSH` 在本单元从 blocking/open 改为 out-of-domain / accepted-limited
（只登记结构事实）；同时新增 `FRONTEND-FLUSH-CONNECT`（blocking/open，owner
`frontend/design`）：`false.B` 的设计决定没有 owner 签字，也没有 Frontend 级集成
验证，确认前整体 `hardware_verdict=INCOMPLETE`。
`INC-FLUSH-012` 从硬件 UNCERTAIN 转为环境分区的结构检查点：
`test_flush_path_is_structurally_pruned`、
`test_flush_closure_recorded_evidence_matches_active_design`、
`test_generated_closure_has_no_flush_port_or_register`。它们只验证“恒 0 + 裁剪 +
哈希一致”，不驱动 flush，**不是行为验证，也不写成硬件 PASS**。

跨配置边界：该分类只对 `public-a0c2a26cb` / DefaultConfig 成立。其他配置若把 flush
接实，或改变 `nMmioEntry`/`MmioBusWidth`/PMA 上限或重新生成导致哈希变化，必须重跑
双 seed、更新证据文件并单独标注；`INC-FLUSH-012` 会在证据失配时失败。

## 7. 覆盖率

| DUT / 文件 | line | branch | toggle |
|---|---|---|---|
| Entry `InstrUncacheEntryDut.v` | 37/37 (100%) | 13/14 (92.86%) | 628/664 (94.58%) |
| Arbiter `InstrUncacheRespArbiterDut.v` | 0/0 N/A | 0/0 N/A | 144/144 (100%) |
| Top `InstrUncacheDut.v` | 0/0 N/A | 0/0 N/A | 395/422 |
| Top `InstrUncacheEntry.sv` | 37/37 (100%) | 13/14 (92.86%) | 626/664 |
| Top `Arbiter1_InstrUncacheResp.sv` | 0/0 N/A | 0/0 N/A | 144/144 |
| Top 合计（真实 RTL） | 37/37 (100%) | 13/14 (92.86%) | 1165/1230 (94.72%) |

未覆盖行 **0**；唯一未覆盖分支是 `InstrUncacheEntry.sv:161` 的初始化块
`if (reset)` else（`R-COV-INIT`）。未覆盖 toggle 全部是合法地址上限/对齐常量
（`R-COV-TOGGLE`）。Picker `*_top.sv` DPI 行不进入 RTL 覆盖（`R-COV-TOOL`）。
R-FLUSH 收口没有新增或改变任何激励，因此 branch 分母保持 **13/14**，未用非法
高位地址或非对齐激励刷 toggle；两个 seed 的覆盖数字与收口前一致（差值 0）。
完整说明见 [覆盖率闭环](../coverage/coverage-loop.md)。

## 8. 门禁

在仓库根执行（2026-11-08）：

| 命令 | 结果 |
|---|---|
| `.venv/bin/python -m pytest -q tests` | **272 passed** |
| `.venv/bin/python scripts/audit-suite-layout.py --strict` | exit 0；全部注册工程 `ok`（含并发新增工程） |
| `.venv/bin/python scripts/audit-suite-layout.py --strict --require-transaction-boundary --suite instr_uncache` | exit 0；本工程 0 pin/signal/owner 访问 |
| `.venv/bin/python scripts/audit-skills.py --strict --check-framework` | exit 0，`PASS`，errors `[]` |
| `python3.12 scripts/audit-assets.py` | `PASS`；12 suites / 137 DUT / 5015 source files，errors `[]` |
| `.venv/bin/ucv doctor public --require-unified-baseline` | 当前 public 集合（含本工程）同一 `public-a0c2a26cb`，`UNIFIED BASELINE` |

根 `tests/test_suite_layout.py` 的注册集合包含 `instr_uncache`；共享树中并发新增的
工程由其会话自行登记，本报告不改写它们的结论。全局严格事务边界命令仍因 dcache、
lsq、lsu、mmu、vagq 的既有债务返回非零（本次 RC=1），本工程单独的强事务审计
exit 0；不把其他工程的历史债务归到本工程，也不删除其他工程的反例。

## 9. 残余与剩余范围

| 残余 | 类别 | blocking | 处置 |
|---|---|---|---|
| `FRONTEND-FLUSH-CONNECT` | out-of-domain | **是（open）** | Frontend 把 `instrUncache.io.flush` 恒接 `false.B`，设计决定无 owner 签字、无 Frontend 级集成验证；需设计 owner 确认或补连接/删端口 |
| `R-FLUSH` | out-of-domain | 否 | DefaultConfig 下 flush 恒 0，取消路径不可达；仅登记结构事实，不声称验证行为 |
| `R-READY-PRUNED` | structural | 否 | response/D/grant ready 恒 1，无合法反压场景 |
| `R-A-CONST` | structural | 否 | A 的 opcode/size/source/mask 等由 `edge.Get` 固定 |
| `R-DATA-X` | observation-limitation | 否 | corrupt/denied 时 data 为 don't-care，不比较 |
| `R-ADDR47` | out-of-domain | 否 | A bit47 固定 0；合法 PMA 上限 2^43 |
| `R-SRC-OUT-OF-RANGE` | out-of-domain | 否 | source=1 仅作过滤鲁棒性对照 |
| `R-COV-INIT` | structural | 否 | 初始化块 reset else 不可达 |
| `R-COV-TOOL` | coverage-limit | 否 | 顶层结构/纯组合 Arbiter 无 line/branch 插桩 |
| `R-COV-TOGGLE` | coverage-limit | 否 | 地址高位/对齐常量不跳变 |

未证明：flush 期间/迟响应的取消语义、Frontend 级 flush/redirect 时序、真实 TL
反压、L2 实际 D 响应时序、`nMmioEntry > 1`、其他配置、ICache/IFU 集成、芯片验收。

本轮不改 RTL、不改其他工程功能代码、未 push。
