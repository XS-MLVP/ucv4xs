# IBuffer / VTypeGen 验证报告

日期：2026-11-08  
基线：`public-a0c2a26cb`（commit `a0c2a26cbe3c862175174bad03a1a23c406315ed`）  
设计配置：DefaultConfig，1 core，`top.TopMain`；`VLEN=128`、`ELEN=64`、
`IBuffer Size=48`、`EnqueueWidth=36`、`DecodeWidth=8`  
结论边界：`IBuffer` / `VTypeGen`；**不是** Frontend、FTQ、ICache 或芯片验收。

## 1. 环境与工具

| 项 | 版本/身份 |
|---|---|
| Python | 3.12 |
| uc-toffee | `2.1.0`，source `f57150021791535d4b2fd01056c106f0cad53177` |
| Picker | source `4dd442c4a80c92549381e417c608836e3b78a8e9` |
| uc-xcomm | `1.1.1`，source `2e4a4a99293360c2a642025000c6948b24cf8e88`，native ABI 3 / coverage 5 |
| Verilator | 5.052 |
| firtool | 1.149.0 |
| Chisel / mill / Java | 7.13.0 / 0.12.17 / 17 |
| 源码缓存 | `.cache/sources/f3ac6022d07c5c05d28869ac811f91038f9103677796dd6f051bd1981408be9b` |
| 整芯片生成缓存 | `.cache/generated/d7c6bc4d17651fc1bd92ac39c469410a6bb91215f46c1efcfaf1ec66a72e972d` |

生成命令（缓存 `generation.json` 记录）为完整 DefaultConfig TopMain：

```text
mill -i -Djvm-xmx=64G -Djvm-xss=64m xiangshan.runMain top.TopMain
  --config DefaultConfig --num-cores 1 --target systemverilog --split-verilog
  --dump-fir --firtool-binary-path .tools/bin/firtool
  --firtool-opt "-O=release ... --default-layer-specialization=disable"
  --fpga-platform --reset-gen --issue E.b --llc OpenLLC
```

本轮不改 RTL、不新增生成入口。

## 2. 实际命令

```sh
.venv/bin/ucv doctor ibuffer --require-unified-baseline
.venv/bin/ucv prepare ibuffer --require-unified-baseline --jobs 4
.venv/bin/ucv build ibuffer --require-unified-baseline --jobs 4
.venv/bin/ucv run ibuffer --workers 1 --seed 1 \
  --require-unified-baseline --output results/ibuffer-seed1-final5
.venv/bin/ucv run ibuffer --workers 1 --seed 2 \
  --require-unified-baseline --output results/ibuffer-seed2-final5
.venv/bin/python suites/frontend/ibuffer/tools/coverage_report.py \
  --manifest results/ibuffer-seed1-final5/ibuffer/manifest.json \
  --output results/ibuffer-seed1-final5/coverage.json \
  --markdown results/ibuffer-seed1-final5/coverage.md
```

`prepare` 输出两个 DUT 均 `PREPARED`；`build` 输出两个 DUT 均
`BUILT + SMOKE PASS`（独立进程冒烟，含 ABI/coverage 版本和零输入冒烟）。
`doctor` 显示 `ibuffer` 与其他公开工程同一 `public-a0c2a26cb`，`UNIFIED BASELINE`。

## 3. RTL 与构建身份

| DUT | cache key | RTL 文件 | sha256 |
|---|---|---|---|
| `vtype_gen` | `fd55f14baed849d4d99a8fede18a215430fbbdcc75d47924bc36af558451cea2` | `VTypeGen.sv` | `09519af25fc05f02c5f0e25a8c2f8693ed654a8e81bcd1e3a64950860941bbcd` |
|  |  | `VSetFuncUnit.sv` | `0fb26fdd7dbd06318b713befaada220732fcfc0ea5698f22077458993fa2d926` |
| `ibuffer` | `015bffca7c4f78c38372a19ec8828d11f2d7e9c3ca1f8170334fef32a20cb991` | `IBuffer.sv` | `f4b8a31d086ba0d3d72306f1f6ce5cce772b0ec0a153f9f9bc8d212179983b96` |
|  |  | `VTypeGen.sv` | `09519af25fc05f02c5f0e25a8c2f8693ed654a8e81bcd1e3a64950860941bbcd` |
|  |  | `VSetFuncUnit.sv` | `0fb26fdd7dbd06318b713befaada220732fcfc0ea5698f22077458993fa2d926` |

三个 RTL 哈希与整芯片生成缓存 `d7c6bc4d…` 的清单逐字节一致；`ibuffer` 闭包保留
真实 `VTypeGen`/`VSetFuncUnit`，不是 Python 模型替代。native 产物哈希（构建收据）：

- `vtype_gen`：`_UT_VTypeGenDut.so` `41e75a63…`、`libUTVTypeGenDut.so` `e2dc6710…`、
  `signals.json` `1a787c58…`；
- `ibuffer`：`_UT_IBufferDut.so` `fe8db08e…`、`libUTIBufferDut.so` `ebfd7609…`、
  `signals.json` `3c4f99881…`。

完整哈希在 `.cache/duts/<key>/build.json` 与各次运行的 `ibuffer-builds.json`。

## 4. 运行结果

| 运行 | seed | nodeid | PASS | FAIL | ERROR | XFAIL | XPASS | SKIP | UNCERTAIN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `results/ibuffer-seed1-final5` | 1 | 83 | 83 | 0 | 0 | 0 | 0 | 0 | 0 |
| `results/ibuffer-seed2-final5` | 2 | 83 | 83 | 0 | 0 | 0 | 0 | 0 | 0 |

两轮 collected nodeid 完全一致，collection SHA 均为
`5bf5301b93b507cfa88430ed9b85c5c89c24db29a83d92e1135401a2e31dca27`；源码身份前后
均为 `bef27be51e59c0abfc63cdf2d74a6f477cae3793ec6664f9db4853ca8527e39f`（运行前后
一致，无源码漂移）。`ucv` 顶层状态 **PASS**，报告 `hardware_verdict=PASS`、
`migration_acceptance=NOT_CERTIFIED`（没有 blocking residual，但仍不是芯片验收）。

功能点报告（`ucv run` 写入 `suites/frontend/ibuffer/results/feature-points.json`，
并复制到结果目录）：

| 分区 | planned | executed | PASS | FAIL/ERROR | consistency errors |
|---|---:|---:|---:|---:|---:|
| hardware | 19 | 19 | 19 | 0 | 0 |
| environment | 4 | 4 | 4 | 0 | 0 |
| all | 23 | 23 | 23 | 0 | 0 |

## 5. 逐 DUT 判定

| DUT | 构建/冒烟 | 定向 | 随机（seed 1/2） | 判定 |
|---|---|---|---|---|
| `vtype_gen` | PASS | 8 lane、vsetvli/vsetivli、SEW/LMUL 全表、保留位、keep-vl、walk/commit/canUpdate、specvtype、reset | 各 240 周期逐周期比较 80 输出 | **PASS** |
| `ibuffer` | PASS | 入队/出队、回绕、全 48 槽 payload、flow control、旁路/旁路上限、窗口追加、flush、异常各位置、walk/commit/resume、stall reason、4 个写 bank 偏移 | 各 300 beat 逐拍完整输出比较 | **PASS**（真实 VTypeGen 子模块） |

这里的 PASS 是两个模块的单元合同判定，不是 Frontend 或芯片验收。

## 6. 失败分类

- 新 RTL FAIL：**0**。
- ERROR：**0**。
- XFAIL/XPASS/SKIP/UNCERTAIN：**0**。
- 已归档缺陷：本轮未确认新的 RTL 缺陷。发现的边界（VSETVL 编码重叠、keep-vl 的
  vill payload、单异常、IFU padding）均有公开规范或接口依据，登记为残余而非缺陷；
  详见 [退出标准](../exit-criteria.md) 和 [缺陷记录](../defects.md)。

## 7. 覆盖率

| DUT / 文件 | line | branch | toggle |
|---|---|---|---|
| `vtype_gen` 合计 | 163/163 (100%) | 104/106 (98.11%) | 1226/1596 (76.82%) |
| `vtype_gen` / `VTypeGenDut.v` | 157/157 (100%) | 99/100 | 1036/1090 |
| `vtype_gen` / `VSetFuncUnit.sv` | 6/6 (100%) | 5/6 | 190/506 |
| `ibuffer` 合计 | 4177/4209 (99.24%) | 666/726 (91.74%) | 18524/20252 (91.47%) |
| `ibuffer` / `IBufferDut.v` | 4014/4046 (99.21%) | 562/620 | 17333/18656 |
| `ibuffer` / `VTypeGen.sv` | 157/157 (100%) | 99/100 | 1020/1090 |
| `ibuffer` / `VSetFuncUnit.sv` | 6/6 (100%) | 5/6 | 171/506 |

未覆盖行 32（`DontCare` 降级为 0）；未覆盖分支按固定输入、初始化 reset-else、
`exceptionMask` 高位、旁路异常槽、指针预回绕、don't-care 和随机深度归因；未覆盖
toggle 按固定输入、IFU padding、mask 高位和随机深度归因。详见
[覆盖率闭环](../coverage/coverage-loop.md) 与 [覆盖摘要](../coverage/coverage-summary.md)。

## 8. 门禁

在仓库根执行（2026-11-08）：

| 命令 | 结果 |
|---|---|
| `.venv/bin/python -m pytest -q tests` | **272 passed** |
| `.venv/bin/python scripts/audit-suite-layout.py --strict` | exit 0；12 个工程全部 `ok`，`ibuffer` 为 `no-static-leak-found` |
| `.venv/bin/python scripts/audit-skills.py --strict --check-framework` | exit 0，`errors: []` |
| `python3.12 scripts/audit-assets.py` | `PASS`；12 suites / 137 DUT / 5012 source files，errors `[]` |
| `.venv/bin/python scripts/audit-suite-layout.py --strict --require-transaction-boundary` | **exit 1**；既有 dcache/lsq/lsu/mmu/vagq 债务，本工程 0 pin/signal/owner 访问 |
| `.venv/bin/ucv doctor public --require-unified-baseline` | 十一个公开工程同一 `public-a0c2a26cb`，`UNIFIED BASELINE` |

严格事务边界的 exit 1 是仓库既有债务，本报告不删除其他工程的反例、不扩大豁免；
`ibuffer` 单独运行该检查为 exit 0。

## 9. 残余与剩余范围

| 残余 | 类别 | blocking | 处置 |
|---|---|---|---|
| `R-OBS-PERF` | coverage-limit | 否 | 9 个性能计数器只绑定/驱动，不做架构比较 |
| `R-OBS-PC` | observation-limitation | 否 | pc/isLastInFtqEntry/debug_seqNum 未导出 |
| `R-LANE-PAD` | structural | 否 | IFU 32..35 padding 不产生有效载荷 |
| `R-EXC-SINGLE` | out-of-domain | 否 | 单异常组；同拍多 lane 异常不是合法 IFU 激励 |
| `R-VILL-PAYLOAD` | observation-limitation | 否 | keep-vl 保留情形保留 payload；CSR 清零在 Backend 边界 |
| `R-TOPDOWN` | structural | 否 | btb/sc bubble 未导出，按 0 建模 |
| `R-VSETVL-OVERLAP` | out-of-domain | 否 | VSETVL 编码重叠 VSETVLI；提交时冲刷丢弃推测 |
| `R-COV-INIT` | structural | 否 | 初始化块 reset-else 不可达 |
| `R-FRONTEND` | out-of-domain | 否 | Frontend/FTQ/ICache/后端消费不在本层 |
| `R-CONFIG` | out-of-domain | 否 | 只覆盖 DefaultConfig |

未证明：Frontend redirect/FTQ/ICache 交互、`satpFlushFirstFetchFault` 的消费者、
真实 CSR vtype 写入、其他 VLEN/ELEN 或 IBuffer 尺寸配置、芯片验收。
