# NewLoadUnit 族验证报告（2026-10-26）

> **失败复核更正：本报告的全绿与所有缺口已正确归因表述为历史口径，当前不再成立。**
> 固定RTL确认 `LSU-HWPF-MISS-001`（S2硬件预取miss性能事件恒0）；增强全套回归
> 为582 PASS / 1 FAIL。父块旧360个toggle缺口中的22个已实际覆盖，当前
> **39686/40024**，剩余338。功能bin100%不代表独立reached/checked全部完成。
> 现行结论与证据见 `../bug-reports-20261026/README.md`，本文件以下表格绑定旧run。

## 1. 范围与结论

本报告覆盖 NewLoadUnit 族的 **9 个独立 DUT**，全部使用 Picker 导出的真实生成 RTL
（`--rw mem_direct -c`，无内部信号、无 VPI），按真实层次自底向上逐个完成：

```
Arbiter7_LoadStageIO ─┐
MemTrigger            ├─> LoadUnitS0 ──┐
LoadUnitDataPath      │   LoadUnitS1   │
                      │   LoadUnitS2   ├─> NewLoadUnit（父块，保留全部真实子模块）
                      │   LoadUnitS3   │
                      └─  LoadUnitS4 ──┘
```

结论：**9/9 DUT 原生构建 PASS、用例 0 FAIL（本族 264 例）、功能覆盖 9/9 100%、
行覆盖合计 1717/1717、分支 1355/1366（剩余 11 个均为 initial reset 臂）、
toggle 73742/74230**。所有剩余点逐项归因为结构常量或工具边界，见 `docs/gaps/load_*.json`。

不声称 LSU 整体、MemBlock 顶层或整核已验收；外部 LSQ/DCache/Uncache/TLB/PMP/Sbuffer/
Backend 只作为协议代理，不作为这些子系统已验证的证据。

## 2. 逐 DUT 结果

绑定统一回归 `results/unified-regression-02`（种子 1，Picker 2.0.0-HEAD-4dd442c，
Verilator 5.052，toffee 2.0.0.dev12+g3017293a7）。

| DUT | 层 | 用例 | 功能 | 行 | 分支 | toggle |
|---|---|---:|---:|---:|---:|---:|
| `Arbiter7_LoadStageIO` | leaf | 21 | 100% | 195/195 | 346/346 | 3702/3702 |
| `MemTrigger`（load 变体） | leaf | 21 | 100% | 33/33 | 10/10 | 762/762 |
| `LoadUnitDataPath` | leaf | 24 | 100% | 122/122 | 17/18 | 3928/3928 |
| `LoadUnitS0` | stage | 38 | 100% | 285/285 | 387/388 | 8546/8582 |
| `LoadUnitS1` | stage | 35 | 100% | 128/128 | 33/34 | 6338/6376 |
| `LoadUnitS2` | stage | 46 | 100% | 108/108 | 5/6 | 4234/4280 |
| `LoadUnitS3` | stage | 32 | 100% | 84/84 | 55/56 | 5400/5408 |
| `LoadUnitS4` | stage | 7 | 100% | 0/0（纯 assign） | 0/0 | 1168/1168 |
| `NewLoadUnit` | parent | 40 | 100% | 762/762 | 502/508 | 39664/40024 |

`NewLoadUnit` 的 762 行覆盖包含父块与全部真实子模块（生成 RTL 闭包），因此其行/分支
分母显著大于单个 stage；这与"逐 DUT 保留原始分母、不跨 DUT 合并"并不冲突：
每个 DUT 的数字来自它自己的 build 与自己的 run 条目。

## 3. 关键语义发现（均有源码与实测证据）

1. **`LoadUnitS0`**
   - 五 lane 仲裁的 entrance 编码：`0x01` 尾段、`0x02` 高优先级 replay、
     `0x04|S3` 快重放、`0x08` 低优先级 replay、`0x40` 标量；**hi-confidence/
     lo-confidence prefetch lane 在本构建中被常量消除**（无 `prefetchReq` 端口）。
   - 低优先级 replay 只在比同拍 `ldin` 更老时存在；更年轻时该拍被丢弃。
   - `fastReplay` lane **不发起 TLB 请求**，且不参与 S0 的 TLB 地址选择。
   - `paddr` 只有 fast replay lane 保留，其余源恒 0（`DontCarePAddr` 折叠）。
2. **`LoadUnitS1`**
   - 三级 redirect：`redirect`、1 拍延迟、2 拍延迟；**第 2 级只 kill tail 注入**
     （`entrance[0]` 门控）。
   - 被 kill 的 head **仍会注入 tail**；tail 在下一拍被第 2 级 redirect 再 kill。
   - `tlbReqKill = kill | specialModeRequest`，与传统 `noQuery` 无关；
     `dcacheKill` 额外包含 TLB miss/异常/special mode；uncache forward 只看 kill。
   - 断点（trigger bp）不 kill DCache；`shouldFastReplay = tail 注入 & ~tail_ready &
     ~miss & ~(fault|bp)`。
3. **`LoadUnitS2`**
   - `fullForward` 要求**所有 load 字节被 forward mask 覆盖**（`(~mask & load_mask)==0`），
     加上 `~sqDataInvalid`；MSHR mask 单列一项；TLD 整拍完成。
   - `cause_3 = troubleMaker & tlbAccessResult[2] | specialModeRequest`（special 不受门控）。
   - fast replay 四条路径：MSHR nack 单独、bank conflict 单独、nuke-first 抵消 cause_2、
     SQ data invalid + stdDataWrite 匹配；均要求 `fastReplayEligible`。
   - **`perf_3` 结构恒0，但这是已确认的性能事件缺陷，不是正常设计边界**：
     `isHwPrefetch` 与 `troubleMaker` 互斥。旧模型期望同样的0，形成漏报。
4. **`LoadUnitS3`**
   - `pipeOutValid` 只在 head/tail 合并（`cancel = head.unalignHead & tail_valid`）时有效；
     普通 load 的写回走组合的 `ldout/vldout`。
   - RF 写只看 `shouldWakeup`，不看写回 arming；LQ/ROB 写受 arming/cancel 门控。
   - LQ 的 replay cause one-hot 只有 11 位可编码（无 cause 7/12）。
   - 异常会屏蔽 RAR violation 与 match-invalid。
5. **`LoadUnitDataPath`**
   - `s3ShiftHead` 是**逻辑右移**（零填充），不是字节旋转；只有 offset=15 项把最高字节
     填到最低位。
   - TLD 分支是整拍 valid、无 per-byte mask；uncache forward 还要求 `isNCReplay`。
6. **`NewLoadUnit`（父块）**
   - 实测时序：`ldin` t0 → S1 t1 → S2 t2 → **S3 组合写回 t2**（3 个时钟沿）。
   - TLB 响应必须在 beat 处于 **S1** 的那一拍给出；提前/错后都会产生 `cause_3` replay。
   - 跨 16B：S1 在 t1 注入 tail，tail 经 S0→S1→S2→S3；head 的 S4 环回与 tail 的 S3
     拍相遇，合并数据 = `head >> 8*offset | tail << 8*(16-offset)`，LQ 写用 head 行地址与
     head mask，尾段溢出字节掩码只用于数据通路。
   - fast replay 被接受时该 beat **不写 LQ**，随后从 S0 重新进入流水线并最终提交。

## 4. 覆盖缺口归因（逐 DUT）

| DUT | 缺口 | 归因 |
|---|---|---|
| arbiter | 无 | 100% |
| trigger | 无 | 100% |
| datapath | 1 branch | `ENABLE_INITIAL_REG_` reset 臂（工具边界） |
| S0 | 1 branch / 36 toggle | reset 臂；`cmd/instrtype` 常量位、scalar accessType 常量、fast entrance bit2 恒 1 |
| S1 | 1 branch / 38 toggle | reset 臂；perf 位宽、tail 地址低 4 位恒 0、tail mask bit15 恒 0、entrance 常量 |
| S2 | 1 branch / 46 toggle | reset 臂；perf 位宽；**perf_3 恒 0**（结构互斥） |
| S3 | 1 branch / 8 toggle | reset 臂；LQ cause bit7/12 不存在 |
| S4 | 无 | 100%（纯 assign，行分母 0） |
| NewLoadUnit | 6 branch / 360 toggle | 6 个 reset 臂；perf 位宽与死计数器 174；entrance 常量码 65；tail 行对齐位 54；DCache cmd/instrtype 常量位 24；LQ cause 7/12 12；训练标志常量 6；scalar accessType 常量 3；子实例端口复制 21；RR 脉冲下降沿 1 |

每个 DUT 的 gap 文件都记录原始分母、未覆盖点清单、源码证据与 `required_supplement`。

## 5. 复现

```
python3 tools/run.py --name <fresh> --workers 2 tests
python3 tools/coverage_audit.py <fresh>
python3 tools/verify_delivery.py
```

- `results/unified-regression-02/manifest.json`：518 PASS、`coverage_complete=true`、
  两个 worker 的 receipt。
- `results/unified-regression-02/trace-policy.json`：未开波形、无逐周期 dump。
- `results/unified-regression-02/delivery-audit.json`：交付审计 PASS。
