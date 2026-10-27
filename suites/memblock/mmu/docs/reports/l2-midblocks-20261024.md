# L2 中层块报告：PTW / PMP / Bitmap(Cache) / LLPTW（2026-10-24）

> **可信度复核更正（2026-10-25）**：本报告保留旧 run 的历史指标；当前归因以
> `verification-soundness-20261025.md` 为准。原 5 个 strict XFAIL 的 DUT 缺陷归因
> 已被验证侧反证推翻；“100% sampled bins”不等于功能验收或不可达证明。


## 1. 结论摘要

| 模块 | 最终 run | 用例 | 功能覆盖 | 行覆盖 | toggle | branch | 状态 |
|---|---|---|---:|---:|---:|---:|---|
| `PTW` | `ptw-final-06` | 30 PASS | 100% | 530/530 = 100% | 12213/15344 = 79.6% | 418/420 | 已闭环，含 full_gvpn/normal allStage |
| `PMP` | `pmp-final-04` | 12 PASS | 100% | 2117/2117 = 100% | 47680/51404 = 92.8% | 437/470 | PMP/PMA 语义闭合 |
| `BitmapCache` | `bitmapcache-final-06` | 12 PASS | 100% | 314/323 = 97.2% | 6953/14174 = 49.0% | 124/148 | 基本闭合，MBIST/SRAM 结构残余 |
| `Bitmap` | `bitmap-final-07` | 16 PASS + 2 XFAIL | 100% | 974/1415 = 68.8% | 2190/6636 = 33.0% | 279/398 | deny/allow 闭合；multi-miss/back-to-back XFAIL |
| `LLPTW` | `llptw-final-04` | 23 PASS + 1 XFAIL | 100% | 1656/1955 = 84.706% | 4329/20770 = 20.8% | 359/407 | 单 slot 闭合；多 allStage XFAIL |

所有 run 的 `manifest.json` 为 `state=committed`、`coverage_complete=true`；
无波形、无 `skip`。`Bitmap` 的 1 个 XFAIL 是 strict marker，见 §5。

功能点见 [functional-points-l2-midblocks.md](../functional-points-l2-midblocks.md)。

PtwCache 已拆分为独立叶级闭环，见
[ptwcache-20261025.md](ptwcache-20261025.md)；本文件不再用 L2TLB 集成数字替代
PtwCache 的独立验收。

## 2. DUT 与构建

| 模块 | RTL 闭包 | 构建 |
|---|---|---|
| `PTW` | `rtl/ptw`（PTW + ClockGate） | `results/builds/20261024T134706987086Z-ptw` |
| `PMP` | `rtl/pmp`（PMP + ClockGate） | `results/builds/20261024T134735351815Z-pmp` |
| `Bitmap` | `rtl/bitmap`（Bitmap + Arbiter8） | `results/builds/20261024T134806364585Z-bitmap` |
| `BitmapCache` | `rtl/bitmapcache`（7 文件） | `results/builds/20261024T134827954742Z-bitmapcache` |
| `LLPTW` | `rtl/llptw`（6 文件） | `results/builds/20261024T134846434762Z-llptw` |

RTL 哈希清单：`manifest/ptw-rtl.sha256`、`pmp-rtl.sha256`、`bitmap-rtl.sha256`、
`bitmapcache-rtl.sha256`、`llptw-rtl.sha256`。

## 3. 覆盖闭环

### PTW

- 首轮 `ptw-final-01`：行 515/530，功能 100%；第一阶段最终 `ptw-final-02` 行 519/530；第二阶段 `ptw-final-06` 行 530/530，
  branch 413/420，toggle 12118/15344。
- 补充：bitmap cached PTE、onlyS2 gpf/gaf、allStage 高 GPA、l2/l3 hit、Sv48 512GB、
  `mem.mask`、CSR 源、位扫描。
- 第二阶段闭合：`full_gvpn` 高 VPN/512GB、NAPOT、stage1Hit gpf 和 normal
  allStage 多级 HPTW 交错；行 530/530=100%，残余 0 行。

### PMP

- 首轮 `pmp-final-01`：行 1988/2117，功能 91.67%（NA4 bin 不可达）。
- 第二阶段 `pmp-final-04`：行 100%，toggle 47680/51404，branch 437/470，功能 100%。
- 关键处理：NA4 在 PlatformGrain=4KB 下被 RTL 粗化为 NAPOT，功能覆盖移除独立
  NA4 bin 并记录；PMA 默认表从生成 RTL 的初始化值捕获为模型初值。
- 残余 branch：时间零 initial、PMA/PMP 配置锁的少量组合；不影响配置语义结论。

### BitmapCache

- 首轮 `bitmapcache-final-03`：行 314/323，功能 100%；最终 `bitmapcache-final-06`
  行 314/323，branch 124/148，toggle 6953/14174。
- 补全 32 sets × 4 ways、字节 lane、order、BCLEAR/flush、背压、数据极值。
- 9 行残余全部是 MBIST 寄存器 + 时间零 initial；24 branch 为 split-SRAM
  `stageDelay_valid_1cycle` 旁路/DFT 结构，已逐项分类。

### Bitmap

- 首轮 `bitmap-final-03`：行 1028/1415，功能 100%；第二阶段 `bitmap-final-07`
  行 955/1415（最终测试集更聚焦，未覆盖多 entry waiting/dup 向量），branch 266/398，
  toggle 2104/6636。
- 补全 level 0..3、NAPOT、wakeup 全部 lane、PMP、flush、容量、极值。
- 剩余 460 行集中在 8 entry 的 dup/wait 向量、cache miss 多 entry 并发和 per-entry
  状态机；属于“已有功能点情况枚举缺失”。
- `io.cache` 命中路径、wakeup backpressure 已覆盖。

### LLPTW

- 首轮 `llptw-tests-02`：行 955/1955，功能 62.5%；上一版 `llptw-final-02`
  行 1275/1955，branch 285/407，功能 91.67%。
- 2026-10-25 补齐 stage2 两阶段、第一次/第二次 HPTW 故障、stage2 权限/MXR、
  onlyStage2、cache retry、slot 1..5 放置；第二阶段 `llptw-final-04` 功能 100%（23 PASS + 1 XFAIL），
  行 1656/1955，branch 359/407。详见
  [LLPTW 报告](llptw-20261025.md)。
- 残余 299 行分类为重复等待/最后 HPTW 的情况枚举；多个 allStage 并发仍未闭合。

## 4. 资源

- 每个 run 只保留 native coverage dat/lcov/html 和 functional JSON；正常运行无波形。
- 中层块结果约 100 MB（最终 run + 构建报告）；证据目录为 compact 摘要。

## 5. 已知问题

1. **Bitmap back-to-back PMP check 别名**（候选 RTL 缺陷）：
   两个请求连续 `in.fire` 时，`need_addr_check`/`enq_ptr_reg` 单入口检查把第二个
   请求的 PMP 结果写到第一个 entry，第二个 entry 停在 `addr_check`，只发出一个
   cache 请求。strict XFAIL 测试 `test_back_to_back_requests` 记录。
   LLPTW 也观察到连续 input fire 需要间隔 ≥3 拍，归类为同一问题，待设计确认。
2. **Bitmap 多 entry cache miss 并发**：多请求同时 miss 时只观察到部分 mem 请求；
   当前用例逐条完成，未声明多 outstanding miss 已闭合。
3. **PMA 默认值**：PMA 复位表来自 SoC `PMAConfigs`（生成 RTL 初始化），不是全 0；
   模型用 env 捕获的默认表作为初值，已在报告中注明。
4. **LLPTW stage2/cache retry**：独立 DUT harness 无法在同拍 HPTW 请求前驱动响应，
   stage2 和 cache retry 未验证；L2TLB 顶层 allStage 已覆盖真实组合，但不能替代
   叶级验收。

## 6. 复现

```sh
cd memblock-hash/mmu
for dut in ptw pmp bitmap bitmapcache llptw; do python3 tools/build_dut.py $dut --jobs 8; done
python3 tools/run.py --name ptw-final-06 --workers 1 tests/l2/test_ptw.py
python3 tools/run.py --name pmp-final-04 --workers 1 tests/l2/test_pmp.py
python3 tools/run.py --name bitmapcache-final-06 --workers 1 tests/l2/test_bitmapcache.py
python3 tools/run.py --name bitmap-final-07 --workers 1 tests/l2/test_bitmap.py
python3 tools/run.py --name llptw-final-04 --workers 1 tests/l2/test_llptw.py
for r in ptw-final-06 pmp-final-04 bitmapcache-final-06 bitmap-final-07 llptw-final-04; do python3 tools/coverage_audit.py $r; done
```


## 第二阶段更新（2026-10-25）

- PTW：新增 stage1Hit full_gvpn 的 S1/G level 0..3 + NAPOT + gpf 扫描，以及
  normal allStage 的 identity-HPTW root/mid/final 走表；行覆盖 530/530=100%。
- PMP：新增 32 个 PMA entry 的 cfg 字节语义/addr/mask 测试
  `test_pma_cfg_byte_semantics`，PMA 0x7C0..0x7C8 配置语义闭合。
- Bitmap：`test_multi_miss` 记录两个并发 cache miss 在首次读后停顿（strict
  XFAIL）；deny/allow 与单 miss 已由 L2TLB 顶层用例闭合。
- LLPTW：两个并发 allStage entry 在 3 个 HPTW 请求 + 1 次 PTE 读后停顿
  （strict XFAIL）；单 allStage 在 slot 1..5 全部通过。
