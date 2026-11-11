# WritebackQueue / ProbeQueue UT 报告（2026-10-24）

## 1. 结论

| DUT | 用例 | 功能覆盖 | DUT 行覆盖 | 分支 | Toggle（DUT-only） |
|---|---:|---:|---:|---:|---:|
| WritebackQueue | 5 PASS | 91.67%（release 91.7 / ack 100 / block 100） | 424 / 449 = 94.4% | 195 / 278 = 70.1% | 1773 / 4706 = 37.7% |
| ProbeQueue | 3 PASS | 100% | 103 / 107 = 96.3% | 60 / 96 = 62.5% | 1388 / 4072 = 34.1% |

运行：`results/wbq-probe-07`（toffee runner，8 passed，固定 seed 1）。

## 2. WritebackQueue 功能点与实测语义

| 功能点 | 用例 |
|---|---|
| WQ-FP-001 请求受理 | `test_release_data_and_ack` |
| WQ-FP-002 C 响应类型 | `test_release_data_and_ack`、`test_release_without_data`、`test_probe_ack_merge` |
| WQ-FP-003 通道选择 | `test_channel_selection_by_address_bit6` |
| WQ-FP-004 条目生命周期 | `test_release_data_and_ack` |
| WQ-FP-005 miss 阻塞 | `test_block_matching_miss_requests` |

实测要点：

1. **C 通道 64B ReleaseData 是 2 个 256-bit beat**；只消费一个 beat 时条目不会释放。
2. **D ack 的 source 必须取 C 响应里的 source**；C beat 完成后该输出会变化，必须提前
   捕获。
3. **通道由 `addr[6]` 选择**；两个通道都能独立完成 Release/ReleaseAck。
4. `hasData=1` → opcode 7；`hasData=0 & voluntary=1 & param=0` → opcode 6；
   `hasData=0 & voluntary=0 & param=1` → opcode 4（ProbeAck 合并）。
5. 条目占用期间，同块（addr[47:6]）的 miss 请求被 `io_block_miss_req` 阻塞，其他块
   放行；C 完成并 ack 后阻塞解除。

## 3. ProbeQueue 功能点与实测语义

| 功能点 | 用例 |
|---|---|
| PQ-FP-001 受理与 MainPipe 请求 | `test_probe_to_b_requests_data` |
| PQ-FP-002 权限目标编码 | `test_probe_to_n_and_to_t` |
| PQ-FP-003 LR/SC 阻塞 | `test_lrsc_locked_block_blocks_probe` |
| PQ-FP-004 条目占用 | 由 DCache 顶层 `test_probe_ack` 验证 |

实测要点：

1. B.data[0] 决定 `probe_need_data`；三种 param 原样透传。
2. LR/SC 保留块与 probe 同块时，MainPipe 请求被抑制；清除保留后同一请求放行。
3. 独立 ProbeQueue 的 `pipe_resp` 由父块 perf 事件驱动，无法自闭环响应；端到端
   B→C ProbeAck 在 `results/dc-initial-*` 的 `test_probe_ack` 中验证。

## 4. 缺口归因

### WritebackQueue 分支（83 项未覆盖）

- 多条目仲裁（18 条 release 条目中只用到 2 条）、`delay_release`、miss_id 合并、
  Dirty 与非 Dirty 的 merge 路径、`corrupt` 数据路径、`voluntary` 的其它组合；
- 时间零 `initial` 的 else 与 DFT 广播。
  属于已有功能点（WQ-FP-001/002/005）的情形缺失与工具边界，本轮未补的条目都在
  报告中保留原始分母。

### ProbeQueue 分支（36 项未覆盖）

- 条目响应完成（独立 DUT 无 `pipe_resp` 端口）、`update_resv_set` 的全阻塞拍、
  多条目仲裁、`vaddr` 别名高位的其它组合；
- 时间零 `initial`。
  条目完成语义在 DCache 顶层已由 `test_probe_ack` 覆盖。

### Toggle 残差

WBQ 37.7%、ProbeQueue 34.1%：主要来自未激活的 16 个 release 条目、DFT/时钟门控输入
和未用的高地址位；功能路径的数据/握手位均已双向翻转。

## 5. 证据

- `results/wbq-probe-07/manifest.json`、`functional-coverage.json`、`coverage-audit.json/.md`
- `manifest/rtl-sha256.json`（`writeback_queue` 4 个、`probe_queue` 4 个 RTL 文件）
- `results/builds/20261024T130610093170Z-writeback_queue/report.json`
- `results/builds/20261024T130610093338Z-probe_queue/report.json`

## 2026-10-25 更新（功能覆盖闭环）

补 `test_probe_ack_data_merge`：非主动 probe 且 `hasData=1` 时 C 通道必须发
`ProbeAckData`（opcode 5），与已有 ReleaseData(7)/Release(6)/ProbeAck(4) 一起
覆盖四种 C 响应。更新后的结果（`results/full-regression-08`）：

| DUT | 用例 | 功能 | 行 | 分支 | Toggle（DUT-only） |
|---|---:|---:|---:|---:|---:|
| WritebackQueue | 7 | **100%** | **449/449** | 242/278 | 3099/4706 |
| ProbeQueue | 3 | 100% | 103/107 | 60/96 | 1388/4072 |

此前 91.7% 的缺口是 `release.kind` 缺少 `probe_ack_data` 一个 bin；现已由
`test_probe_ack_data_merge` 补齐，并实测 opcode=5、地址回显与条目 ack 释放。
另外 `test_all_sixteen_entries_occupied` 依次占用 18 个 release entry（不 ack D），
验证第 19 个请求 `req_ready=0`，覆盖了 `WritebackEntry_15.sv` 等高编号条目的
装载/释放路径，使 WBQ DUT-only 行覆盖从 435/449 提升到 449/449。
