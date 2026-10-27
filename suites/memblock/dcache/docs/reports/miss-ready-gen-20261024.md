# MissReadyGen UT 报告（2026-10-24）

> 数字仍以本报告的独立运行为准；在 2026-10-25 的全量回归
> `results/full-regression-11`（202 passed + 3 xfailed，61 功能组 100%）中，本 DUT 的分母未变，
> 结论继续有效。根因/语义修正记录见 `functional-point-audit-20261025.md`。

## 1. 结论

| 项 | 结果 |
|---|---|
| 运行 | `results/mrg-initial-02`（5 用例，固定 seed 1） |
| 功能覆盖 | **100%**（channel / field / independence） |
| DUT 行覆盖 | 无行点（纯组合 assign 网表，0/0） |
| 分支覆盖 | 无分支点（0/0） |
| Toggle 覆盖（DUT-only） | **3512 / 3512 = 100%** |

DUT 没有时钟、复位或内部状态；Verilator 对连续赋值的线网不产生 line/branch 点，
因此以 toggle 与逐位功能比较作为覆盖证据。

## 2. 功能点与用例

| 功能点 | 用例 |
|---|---|
| MRG-FP-001 四路请求直通 | `test_zero_vector_is_transparent`、`test_random_vectors` |
| MRG-FP-002 ready 反向直通 | `test_ready_matrix_is_per_channel` |
| MRG-FP-003 通道间独立 | `test_valid_patterns_and_independence` |
| MRG-FP-004 位域保真（含 512-bit store_data） | `test_walking_bit_all_payload_fields` |
| MRG-FP-005 零状态组合语义 | `test_valid_patterns_and_independence`、`test_zero_vector_is_transparent` |

## 3. 覆盖率闭环

| 运行 | 状态 | 功能覆盖 | Toggle DUT-only |
|---|---|---:|---:|
| `mrg-initial-01` | 5 PASS | 100% | 3304 / 3512 = 94.08% |
| `mrg-initial-02` | 5 PASS | 100% | **3512 / 3512 = 100%** |

缺口归因：首轮只对通道 0/1 做了 walking-bit 扫描，通道 2/3 的 48-bit `addr` 与
50-bit `vaddr` 高位从未翻转；把同一 walking-bit 用例扩展到 4 个通道后补齐，没有新增
功能点，属于已有功能点 MRG-FP-004 的情形缺失。

## 4. 证据

- `results/mrg-initial-02/manifest.json`、`functional-coverage.json`、`coverage-audit.json`
- `manifest/rtl-sha256.json`（`miss_ready_gen` 2 个 RTL 文件）
- `results/builds/20261024T104603980962Z-miss_ready_gen/report.json`
