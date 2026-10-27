# L2TLBWrapper 组合层验证报告（2026-10-25）

> **可信度复核更正（2026-10-25）**：本报告保留旧 run 的历史指标；当前归因以
> `verification-soundness-20261025.md` 为准。原 5 个 strict XFAIL 的 DUT 缺陷归因
> 已被验证侧反证推翻；“100% sampled bins”不等于功能验收或不可达证明。


## 1. 结论摘要

| 项 | 结果 |
|---|---|
| DUT | `L2TLBWrapper`（48 个 L2TLB 闭包文件 + wrapper 本体，共 49 个真实 RTL 文件） |
| 最终 run | `l2tlbwrapper-final-05` |
| 用例 | **46 PASS + 1 strict XFAIL**（无 skip） |
| 功能覆盖 | **100%**（235 samples；event/page/port/stage 全满） |
| 包装层本体行覆盖 | **40 / 40 = 100%**（0 未覆盖行） |
| 组合 DUT 总行覆盖 | **17697 / 22289 = 79.398%** |
| branch | **4444 / 6304** |
| toggle | **102301 / 260640** |
| manifest | `state=committed`、`coverage_complete=true`、`pytest_exitstatus=0` |

结论：包装层本体所有可执行行已覆盖，功能点全部由用例对应；残余覆盖全部位于
真实子块内部，已逐类归因。共享叶子表 back-to-back miss 的停顿以 strict XFAIL
固定；第二阶段把根因隔离到零间隔 prefetch/LLPTW 交接，并新增 1 个空闲周期的
正例 `test_wrapper_shared_leaf_one_cycle_gap`；>2 outstanding 仍为 strict XFAIL。
未虚报闭合。

功能点见 [functional-points-l2tlbwrapper.md](../functional-points-l2tlbwrapper.md)。

## 2. DUT 与构建

- 真实层次：

  ```text
  L2TLBWrapper
    └─ L2TLB（唯一子实例，所有 IO 1:1 连接）
         ├─ PtwCache / PTW / HPTW / LLPTW
         ├─ Bitmap / BitmapCache / PMP
         ├─ L2TlbMissQueue / L2TlbPrefetch
         └─ arbiters / SRAM / ClockGate
  ```

- RTL 闭包：`rtl/l2tlbwrapper`（49 个 `.sv`，逐字节取自 `soc-split/rtl`）；
  哈希清单 `manifest/l2tlbwrapper-rtl.sha256`。
- 构建：`results/builds/20261025T004040447536Z-l2tlbwrapper`，`ok=true`，
  无缺失模块。
- Picker `2.0.0-HEAD-4dd442c`、Verilator `5.052`、toffee
  `2.0.0.dev12+g3017293a7`。
- 只驱动公开端口；MBIST/DFT 输入保持 0；无波形、无 internal signal config。

## 3. 功能点与用例矩阵

44 个用例覆盖 12 组组合语义（W-01..W-12）：

| 组 | 内容 | 代表用例 |
|---|---|---|
| 透明翻译 | 1GB/2MB/4KB、noS2/onlyS1/onlyS2/allStage | 全部 walk 用例 |
| 故障 | 无效 PTE、PBMT、保留位、未对齐、PMP | fault/PMP 用例 |
| 缓存 | 单条重放、4 条驻留、64 页 working set | `test_wrapper_64_page_working_set` |
| 失效 | 全地址/ASID/地址、走表中、satp+sfence | sfence 用例 |
| 并发 | 双端口、同拍、两个在途 | port/outstanding 用例 |
| 背压 | payload 稳定、事件不丢 | `test_response_backpressure` 等 |
| 内存时序 | A/D 双 beat、延迟、source | `test_memory_latency_and_two_outstanding` |
| WFI | idle/outstanding/阻塞新 A | `test_wrapper_wfi_*` |
| 分布式 CSR | PMP deny/allow 动态生效 | `test_wrapper_distributed_csr_pmp` |
| bitmap | BME/CMODE/BMA、BCLEAR、allStage | bitmap 用例 |
| 性能事件 | 19 路单拍脉冲、2 级额外延迟 | `test_wrapper_perf_*` |
| 复位/DFT | 空闲、perf 冲刷、BIST 静态 | `test_wrapper_reset_and_idle_pipeline` |

## 4. 覆盖率闭环

| 阶段 | run | 用例 | 行覆盖 | branch | toggle | 功能 |
|---|---|---:|---:|---:|---:|---:|
| 首轮（34 个 L2TLB 用例直接跑 wrapper） | `l2tlbwrapper-tests-01` | 34 PASS | 17015/22289 = 76.338% | 4294/6304 | 99389/260640 | 84.09%* |
| 补 9 个 wrapper 专项 | `l2tlbwrapper-tests-03` | 43 PASS | 17050/22289 = 76.495% | 4304/6304 | 100103/260640 | 100% |
| 补 64 页 working set | `l2tlbwrapper-tests-04` | 44 PASS | 17449/22289 = 78.285% | 4423/6304 | 101349/260640 | 100% |
| 第一阶段最终 | `l2tlbwrapper-final-01` | 44 PASS + 1 XFAIL | 17689/22289 = 79.362% | 4442/6304 | 101986/260640 | 100% |
| 第二阶段中期 | `l2tlbwrapper-final-04` | 45 PASS + 2 XFAIL | 17689/22289 = 79.362% | 4442/6304 | 102220/260640 | 100% |
| **第二阶段最终** | **`l2tlbwrapper-final-05`** | **46 PASS + 1 XFAIL** | **17697/22289 = 79.398%** | **4444/6304** | **102301/260640** | **100%** |

\* 首轮功能 84.09% 是因为 wrapper 专用 event bin（perf/wfi/backpressure/pmp/
bitmap/csr/reset）尚未采样；补专项用例后达到 100%。

关键补测与收益：

| 缺口/目标 | 补测 | 结果 |
|---|---|---|
| 包装层 perf/WFI/CSR/PMP/bitmap 语义未验证 | 9 个 wrapper 专项用例 | 功能从 84.09% 到 100% |
| PtwCache 只用到少量 L0 set/way | 64 页 4KB working set，覆盖 64 个 set、8 个 lane、4 个 way | PtwCache +399 行，总行 +2.8 个百分点 |
| 背压时事件是否丢失 | 长 ready=0 下记录 LLPTW 事件脉冲 | 事件不丢、payload 稳定 |
| 性能事件是否只是计数器 | 逐拍 trace 检查 19 路输出 | 均为单拍脉冲 |

### 4.1 wrapper 性能事件等价性证据

用同一复位和同一 1GB leaf 激励分别运行 `L2TLB` 与 `L2TLBWrapper`，逐拍记录
所有响应字段、A 通道、WFI 和 19 路 perf：

- 功能字段 22 拍逐拍完全一致；
- 19 路 perf 全部满足 `wrapper[t] == l2tlb[t-2]`（忽略前 4 拍初始随机流水线），
  即 wrapper 在 L2TLB 内部已有 2 级 `RegNext` 之上再加 2 级；
- 比较结果：`docs/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-comparison.json`，
  **PASS 0 failures**。

## 5. 未覆盖项逐项分类

组合 DUT 共 4600 未覆盖行。包装层本体为 0；全部位于真实子块，分类如下：

| 文件 | 未覆盖行 | 归因 | 处理 |
|---|---:|---|---|
| `PtwCache.sv` | 1641 | 顶层集成只通过 VPN 间接选择 set/way，部分替换/预取/sfence 组合不可由公开端口精确指定；独立叶级 `ptwcache-final-02` 已覆盖到 99.949% | 已有功能点的情况枚举；叶级已闭合，组合层不再重复造激励 |
| `PMP.sv` | 733 | PMA/PMP 锁和高位 entry 组合；独立叶级 `pmp-final-04` 行 100% | 已有功能点；组合层只验证 allow/deny/TOR/CSR |
| `LLPTW.sv` | 916 | stage2/HPTW 多 entry、cache-retry；独立叶级为部分闭合 | 整体功能点缺口（已记录 `LLPTW-STAGE2-CACHE-UNVERIFIED`），组合层不替代叶级验收 |
| `Bitmap.sv` | 726 | deny/多 miss 并发；独立叶级未闭合 | 已有功能点情况枚举缺失；组合层只验证 allow-all |
| `L2TLB.sv` | 641 | 顶层状态/arbiter 组合，需要更细的并发/预取序列 | 已有功能点情况枚举；未虚报 |
| `PMPChecker.sv` | 68 | PMA 边界；独立 PMP 叶级已覆盖主要配置 | 情况枚举 |
| `BitmapCache.sv` | 75 | set/refill 状态；独立叶级 `bitmapcache-final-06` 已闭环 | 情况枚举 |
| `Mbist*` / SRAM | 约 30 | MBIST/DFT 端口未使能、SRAM 宏复位/初始 | 结构性，非功能点 |
| 其他 (PTW/HPTW/MissQueue 等) | 0 | — | — |

没有“包装层整体功能点缺失”。`L2TLBWrapper.sv` 的 40 行可执行代码全部覆盖，
包括 19×2 个 perf 寄存器和所有 1:1 连接赋值。

### 5.1 显式未闭合范围

- **多于 2 个在途请求**：8 个 back-to-back 4KB 请求的探针没有产生内存读/响应，
  原因未隔离；最终只声明 2 个在途和 64 页“带间隔”的序列。未用模型替代。
- **共享叶子表 back-to-back miss**：见 §6.1。
- **LLPTW stage2/cache-retry**：独立叶级未闭合；组合层 allStage 用例只证明
  真实 RTL 能完成该路径，不能替代叶级验收。

## 6. 已知问题/观察

### 6.1 `L2TLB-PREFETCH-SHARED-LEAF-STALL`（候选行为缺口）

三个 4KB miss 使用同一叶子表、连续发出，前两个完成后第三个在预取相邻页时停顿，
600 拍内无响应；请求序列显示叶表读地址落在相邻 64B 行（0x40/0xC0），不是
请求 VPN 对应的 0x80。相同三页加入 8 拍空闲间隔后全部成功，64 页 working set
也全部成功。因此：

- 不以“RTL 缺陷”定性，也不忽略；
- 以 strict XFAIL `test_wrapper_back_to_back_shared_leaf_miss` 固定；
- 用例 W-10 明确插入 8 拍间隔并在注释中指向本问题；
- 需要设计确认是 LLPTW/prefetch 的 turnover 约束还是响应/仲裁问题。

### 6.2 `L2TLBWRAPPER-PERF-NO-RESET`（结构观察）

wrapper 的 19×2 个 perf 寄存器没有同步复位；复位后前 4 拍输出可能是 Verilator
随机初值，之后被真实事件流水线冲刷。`test_wrapper_reset_and_idle_pipeline`
在 10 拍后检查“仅 PTW idle 事件为 1”，不假设 perf 复位为 0。功能通路本身
有复位。

### 6.3 `L2TLBWRAPPER-MULTI-OUTSTANDING-UNVERIFIED`（范围缺口）

只验证了 2 个在途请求（带延迟）和 64 页带间隔序列；8 个连续请求的探针未完成，
原因未隔离。多 outstanding >2 不在本次已验收范围。

### 6.4 子块既有缺口

satp 无 sfence 的旧翻译、sfence rs1=0/rs2=0 重走、bitmap deny、PMA、PTW 高 VPN、
MBIST/DFT 等已在 `manifest/known-issues.json` 中记录，组合层不改变其状态。

## 7. 复现

```sh
cd memblock-hash/mmu
python3 tools/build_dut.py l2tlbwrapper --jobs 8
python3 tools/run.py --name l2tlbwrapper-final-05 --workers 1 tests/l2/test_l2tlbwrapper.py
python3 tools/coverage_audit.py l2tlbwrapper-final-05
python3 tools/verify_delivery.py
```

性能事件等价性复现：

```sh
MMU_PERF_TRACE=$PWD/docs/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-l2tlbwrapper.json \
  python3 tools/run.py --name l2tlbwrapper-perf-trace --workers 1 tools/trace/test_perf_trace_l2tlbwrapper.py
MMU_PERF_TRACE=$PWD/docs/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-l2tlb.json \
  python3 tools/run.py --name l2tlb-perf-trace --workers 1 tools/trace/test_perf_trace_l2tlb.py
python3 tools/compare_wrapper_perf_trace.py \
  docs/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-l2tlb.json \
  docs/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-l2tlbwrapper.json \
  --out docs/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-comparison.json
```

资源：最终 run 约 96 MB；compact 审计与 trace 证据约 2.2 MB；无波形。


## 第二阶段更新（2026-10-25）

- 根因隔离：零间隔 3 个共享 leaf 表 4KB miss 时，第三个 demand 行
  `0x800A2080` 被相邻预取行 `0x800A20C0`（source 2）取代，demand 从未发出；
  请求间插入 1 个 service 周期后，demand 行 `0x800A2080` 由 LLPTW（source 1）
  发出，三个页面全部完成。正向用例为 `test_wrapper_shared_leaf_one_cycle_gap`，
  零间隔仍为 strict XFAIL。
- `test_wrapper_four_outstanding`：4 个不同 4KB 翻译在 mem_latency=7 下全部完成；
  零延迟模型丢失第二个 D beat 已隔离为 harness 时序问题，不再作为 RTL 边界。
- 最终 run `l2tlbwrapper-final-05`：46 PASS + 1 XFAIL，行 17697/22289=79.398%，
  branch 4444/6304，toggle 102301/260640，功能 100%。
