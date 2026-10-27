# 交付自检（2026-10-26，含 DCacheWrapper）

> 最新一次全量回归：`results/soundness-recheck-03`（**210 passed + 3 xfailed / 219.28 s**，
> 13 个 Picker 构建、61 个功能覆盖组全部 100%、trace policy PASS）。
> 多 seed：`seed-sweep-01..04` 四个种子结果一致。
> 下表为 13 个 DUT 的最终数字（DCacheWrapper 行覆盖含内部 DCache）。

## 1. 工程位置与基线

| 项 | 值 | 证据 |
|---|---|---|
| 工程根 | `/home/xyl/kmh-v3-test/memblock-hash/dcache` | 本 README、`conftest.py`、`pytest.ini` |
| 源码 | XiangShan `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` | `manifest/toolchain.json` |
| RTL | `../../../soc-split/rtl`，13 个 DUT 闭包 174 份拷贝 / 59 个唯一源文件 | `manifest/rtl-sha256.json`；逐文件复核 **59/59** 哈希一致 |
| Picker | `2.0.0-HEAD-4dd442c-2026-10-12` | `picker --version`；各 `results/builds/*/report.json` |
| Verilator | `5.052` | `/opt/verilator-5.052/bin/verilator --version` |
| toffee | `2.0.0.dev12+g3017293a7` | venv `pytoffee`；`manifest/toolchain.json` |
| xspcomm | `0.3.0.dev3` | 同上 |
| 源文件位置 | 原 XiangShan / soc-split 只读输入，不修改 | `manifest/toolchain.json` |

## 2. 用例与功能覆盖

- 最终全量回归：`results/soundness-recheck-03`（toffee main runner，`--workers 4`）
  - `pytest_exitstatus=0`，**210 PASS + 3 XFAIL / 219.28 s**，`coverage_complete=true`；
  - `manifest.json` 记录 `functional_groups=61`，合并功能覆盖 **100.00%**；
  - `trace-policy.json` 为 **PASS**，无 `.fst`、无逐周期 `.jsonl`、无 transaction dump。
  - 3 个 XFAIL 都是同一已确认 RTL 缺陷 `MQ-STORE-MERGE-DATA-PENDING` 的严格复现，
    不计入通过数。
  - 演进：`w0-coverage-01` 162 PASS（覆盖率报告初版交付）→ `w1-fp-audit-01` 165 PASS
    （功能点复核 + 3 个补强用例）→ `full-regression-09` 193 PASS（新增
    DCacheWrapper 28 个用例）→ `full-regression-11` 202 PASS + 3 XFAIL（P0 收口：
    多 seed、约束随机、缺陷复现、非缺陷澄清）→ `full-regression-14` 207 PASS + 3 XFAIL
    （状态空间扫描：256 set × 4 way + 4 端口，DCache 行覆盖 69.99% → 94.11%）→
    `full-regression-15` 209 PASS + 3 XFAIL（prefetch 标记路径，DCache 98.20%）。
- 每个 DUT 的独立运行与报告：

| DUT | 最终运行 | 用例 | 功能 | 行（DUT-only） | 分支 | Toggle（DUT-only） |
|---|---|---:|---:|---:|---:|---:|
| DuplicatedTagArray | full-regression-11 | 9 | 100% | 90/90 | 76/80 | 15010/15428 |
| CtrlUnit | full-regression-11 | 13 | 100% | 244/244 | 85/89 | 11444/12108 |
| MissReadyGen | full-regression-11 | 5 | 100% | 0/0（组合） | 0/0 | 3512/3512 |
| CounterFilter | full-regression-11 | 7 | 100% | 311/311 | 49/50 | 622/622 |
| MissTrack | full-regression-11 | 13 | 100% | 952/952 | 172/174 | 12054/12804 |
| LoadPipe | full-regression-11 | 7 | 100% | 119/119 | 23/25 | 4594/5190 |
| BankedDataArray | full-regression-11 | 21 | 100% | 1843/1843 | 1093/1100 | 90474/105848 |
| MainPipe | full-regression-11 | 36 | 100% | 2095/2095 | 667/674 | 29431/40500 |
| MissQueue | full-regression-14 | 29 | 100% | 1853/2099 | 953/1334 | 23476/47506 |
| WritebackQueue | full-regression-11 | 8 | 100% | 449/449 | 242/278 | 3114/4706 |
| ProbeQueue | full-regression-11 | 3 | 100% | 103/107 | 60/96 | 1388/4072 |
| DCache 顶层 | soundness-recheck-03 | 26（1 xfail） | 100% | 50262/51179 | 18986/20504 | 168471/332370 |
| **DCacheWrapper** | soundness-recheck-03 | **34（1 xfail）** | **100%** | **50455/51265（自身 86/86）** | 19034/20504 | 181196/349062 |

- 功能点文档：`docs/functional-points-<dut>.md` **13 份**（12 个 DCache 内部 DUT +
  DCacheWrapper），均以微架构语义/行为描述，每个功能点在用例中有对应断言。
- 本表统一取最终全量回归 `soundness-recheck-03` 的 13 个构建；逐模块报告中的
  `mp-main-07`/`mq-main-03` 等为当时独立构建的数字，分母可能相差几个点，
  二者各自绑定自己的构建 ID，不混用。
- 覆盖率审计：每个运行目录有 `coverage-audit.json`（主要运行保留原文件，
  历史运行的大文件压缩为 `.json.gz`）与 `coverage-audit.md`；
  `soundness-recheck-03` 为 13 构建合并格式，不跨 DUT 求和。

## 3. 顶层核心行为检查清单

| 要求 | 用例 | 实测 |
|---|---|---|
| reset / SRAM 清扫 | 所有顶层用例的 `DcacheEnv.reset` | 300 拍后发事务；258 拍内 tag/meta ready 为低（此前探针） |
| load 命中 + 3 lane | `test_cold_miss_refill_then_hit`、`test_all_three_load_lanes`、`test_three_lanes_same_line` | data/miss/handled 与行模型一致 |
| miss / refill | `test_cold_miss_refill_then_hit`、`test_dual_channel_selection` | AcquireBlock(6,size6)→2×GrantData→重放命中 |
| store 合并 / 写后读 | `test_store_then_load_observes_data`、`test_store_masks_and_readback`、`test_store_miss_with_refill`、`test_store_mask_classes` | 按字节掩码合并；部分 store miss = L2 行+store 字节 |
| store→load 转发 | 不属 DCache 边界（Sbuffer/LSU 负责）；DCache 侧验证写后读可见 | README/顶层报告已注明边界 |
| probe / writeback | `test_probe_ack`、`test_dirty_eviction_releases_line`、`test_clean_eviction_releases_without_data` | B→C ProbeAck/ProbeAckData；dirty→ReleaseData，clean→Release |
| 错误上报 | `test_refill_denied_reports_error`、`test_corrupt_refill` | denied/corrupt 使 `io_error.valid=1`；paddr 观测为 0（known-issue） |
| flush / CMO | `test_cmo_opcodes_and_responses` | clean/flush/inval × ok/denied/corrupt 9 组 |
| wrapper 边界保真 | `tests/dcache_wrapper/`（9 专属 + 19 回放） | 861 端口 1:1、控制寄存器读写、spec fabric、双通道、perf 延迟、全部 DCache 场景原样重放 |
| atomics | `test_atomic_swap_and_add_hit`、`test_atomic_miss_completes_after_refill` | 命中/refill 完成、旧值返回、写后读 |

## 4. 未关闭项（已在文档中定位）

| ID | 内容 | 状态 |
|---|---|---|
| `MQ-STORE-MERGE-DATA-PENDING` | 同一行第二笔部分 store 被受理但字节丢失（LSU 仍收到成功响应） | **确认 RTL 缺陷**；2 个严格 xfail 用例，修复后自动转 unexpected pass |
| `CF-DEQUEUE-PIPELINE-NO-RESET` | CounterFilter 3 级出队计数流水无复位，短复位会让 FIFO 指针偏移 | 系统内良性（真实复位数百拍）；env 复位保持 5 拍 |
| ~~`BDA-ECC-DELAYED-FLAG`~~ | 之前读到的是从未写过的 SRAM 行 | 关闭：非缺陷，编码写入后 `error_delayed=0` |
| ~~`DCACHE-DENIED-ERROR-PADDR-ZERO`~~ | `io_error.paddr = vaddr[11:0]`（冷行 tag=0） | 关闭：非缺陷，已加用例固化 |
| ~~`DCACHE-REEVICT-BLOCK-REJECTED`~~ | 替换后重访被拒 | 关闭：非缺陷（写回阻塞契约，drain+ack 后恢复） |
| SRAM 阵列未全扫 | 4 个 meta 阵列 256 set×4 way、生成顶层宽连线 | 范围限制；功能组 100% |
| Uncache 仲裁 / flush / CSR | 不在 DCacheWrapper 内（Uncache 与它平级在 MemBlock） | 未纳入，需 MemBlock DUT |
| uncache/WPU/prefetch/伪错误注入 | 顶层未纳入 | 明确未验收，不计入“已通过” |

## 5. 资源与可复现性

- 正常运行的 Picker 构建含 trace 能力但不调用 `SetWaveform`；`tools/run.py` 校验
  无波形/无逐周期 dump，PASS 后才保留结果。
- 结果目录：主证据 `soundness-recheck-03`（13 构建，含 DCacheWrapper）与
  `seed-sweep-01..04`（四种 seed）、`w0-coverage-01`（覆盖率报告初版基数）、
  `dw-main-03`（wrapper 单独运行）、`mp-main-07` / `mq-main-03`（上层单模块）。
  主证据保留 `coverage-audit-summary.json` + `.md` + LCOV `.info.gz`，逐点
  `coverage-audit.json` 压成 `.gz`，原始 `coverage.dat` 删除（可重跑重建）。
  `results/` **约 40 MB**；13 个构建共享 `dut/xspcomm-shared`，工程总计约 600 MB。
- 复现命令：
  ```sh
  python3 tools/prepare_rtl.py <key>
  python3 tools/build_dut.py <key> --jobs 8
  python3 tools/smoke_dut.py <key>
  python3 tools/run.py --name <fresh-name> --workers 4 tests/<dut>
  python3 tools/coverage_audit.py <fresh-name>
  ```

## 6. 自检结论

- 13 个 DUT（含 DCacheWrapper）的测试全部通过；61 个功能覆盖组全部 100%；
  每个 DUT 的 line/toggle/branch 分子分母与未覆盖归因均可追溯。
- 顶层核心端到端行为（reset、命中、miss/refill、store 合并与写后读、probe/writeback、
  dirty/clean eviction 与写回阻塞、AMO、CMO、错误上报）有独立参考模型/断言与实测证据。
- 多 seed（1/2/3/4）结果一致；约束随机流量用 L2 shadow + 未写回字节模型逐笔比对。
- 1 项确认 RTL 缺陷由严格 xfail 固化，未混入“已通过”结论。
- 用例可信度门禁：`tools/audit_test_soundness.py`（收集/恒真/无断言）、
  `tools/audit_output_fields.py`（输出观察）、`tools/selfcheck_checkers.py`
  （注错必须 FAIL，8/8）均为非 0 退出即失败；见
  `docs/reports/soundness-recheck-20261026.md`。
- 交付文档、覆盖率审计、运行 manifest、工具/RTL 哈希与结果目录一一绑定。
- 目标范围内的验证闭环已完成；剩余项为已记录的上游确认项与明确范围外行为。
