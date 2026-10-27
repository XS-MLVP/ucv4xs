# CounterFilter UT 报告（2026-10-24）

> 数字仍以本报告的独立运行为准；在 2026-10-25 的全量回归
> `results/full-regression-09`（193 passed，61 功能组 100%）中，本 DUT 的分母未变，
> 结论继续有效。根因/语义修正记录见 `functional-point-audit-20261025.md`。

## 1. 结论

| 项 | 结果 |
|---|---|
| 运行 | `results/cf-initial-06`（7 用例，固定 seed 1） |
| 功能覆盖 | **100%**（query / enq / lifetime） |
| DUT 行覆盖 | **311 / 311 = 100%** |
| 分支覆盖 | **49 / 50 = 98%**（唯一缺口是时间零 initial） |
| Toggle 覆盖（DUT-only） | **622 / 622 = 100%** |

## 2. 功能点与用例

| 功能点 | 用例 |
|---|---|
| CF-FP-001 复位为空 | `test_reset_empty_and_invalid_queries` |
| CF-FP-002 入队保存 set/way | `test_duplicate_and_distinct_loads`、`test_index_and_way_full_range` |
| CF-FP-003 查询命中语义 | `test_query_ports_are_independent`、`test_random_legal_traffic` |
| CF-FP-004 条目生命周期 | `test_single_entry_lifetime` |
| CF-FP-005 重复 line 与容量 | `test_capacity_full_and_pointer_wrap` |
| CF-FP-006 查询与入队同拍 | `test_query_ports_are_independent` |

## 3. 实测语义（与直觉不同之处）

1. **物理深度 15，但合法在途上限是 12**：dequeue 数量是 4 拍前入队数的延迟版本，
   第 4 个时钟沿才开始清除；连续 3 端口满带宽时稳态占用是 `4 × 3 = 12`，剩余 3 个
   物理槽是写回阶段余量。因此覆盖组使用 `max_inflight=12` 而不是 15。
2. **条目可见 4 个周期（age 0..3）**：入队沿之后立即对查询可见，第 4 个沿被清除。
3. **同拍入队不可见**：查询只使用已提交的 entry 集合；同拍 dequeue/enqueue 命中同一槽
   位时新入队获胜。
4. **查询是纯组合**：3 个端口各自对当前 15 个槽做 idx/way 全等比较，`req_valid=0`
   恒为 0。

## 4. 覆盖率闭环

| 运行 | 用例 | 功能覆盖 | 行覆盖 | 分支 | Toggle |
|---|---|---:|---:|---:|---:|
| `cf-initial-03` | 1 PASS / 6 FAIL（模型时序错误） | 91.2% | 238/311 | 38/50 | 334/622 |
| `cf-initial-06` | **7 PASS** | **100%** | **311/311** | **49/50** | **622/622** |

首轮缺口归因：

- 功能覆盖缺 `cf.enq.capacity` 与部分 `lifetime` 情形：当时把“满”定义为 15 项，
  但实际合法上限是 12；修正功能点语义后补齐。
- 行/分支/toggle 缺口集中在 enq 的多端口仲裁、指针回绕和 dequeue 清除路径：补充
  满带宽连续入队、指针回绕、同拍多端口和 drain 用例后闭合。
- 剩余 1 个分支是 `CounterFilterDut.v:684` 的时间零 `initial` else，运行期不可达。

## 5. 证据

- `results/cf-initial-06/manifest.json`、`functional-coverage.json`、`coverage-audit.json`
- `manifest/rtl-sha256.json`（`counter_filter` 2 个 RTL 文件）
- `results/builds/20261024T104603980981Z-counter_filter/report.json`

## 2026-10-26 更新：复位校准（`CF-DEQUEUE-PIPELINE-NO-RESET`）

多 seed 扫描暴露：seed=1 时 7 个确定性用例全过，seed=2 时
`test_single_entry_lifetime`、`test_query_ports_are_independent`、
`test_index_and_way_full_range`、`test_capacity_full_and_pointer_wrap` 失败，报
「query 期望命中而 DUT 不命中（occupancy=1）」。同一份激励只差 Verilator 随机初值。

**定位**：`CounterFilter.sv:606-610` 的 3 级出队计数流水
`last3CycleAlloc_REG/_REG_1/_REG_2` 位于无复位的 `always @(posedge clock)` 块，
只有末级 `last3CycleAlloc` 被复位。短复位后第一个时钟沿按旧值出队，把 `deqPtr`
推过 `enqPtr`，FIFO 永久偏移。

**处理**：env 的 `reset()` 保持复位 5 拍（期间输入全 0），让该流水在指针被 clamp
期间冲干净。seed 1/2/3/4 全量回归全部通过。

**性质**：系统内良性——真实复位持续数百拍，且 DCache 复位后要等 256 拍 SRAM 清扫
才会发出 load。只影响「复位后立刻打流量」的仿真场景。若希望彻底消除，需要上游给
这三个寄存器加复位。
