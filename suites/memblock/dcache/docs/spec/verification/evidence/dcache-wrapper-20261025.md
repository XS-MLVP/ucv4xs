# DCacheWrapper UT 报告（2026-10-25）

## 1. 结论

| 项 | 结果 |
|---|---|
| DUT | `DCacheWrapper`（`soc-split/rtl/DCacheWrapper.sv`，内部 1 个 `DCache` 实例） |
| 运行 | `results/full-regression-15` 的 `dcache_wrapper` 构建（早期单模块运行为 `dw-main-03`） |
| 用例 | **33 passed + 1 xfailed**（9 个 wrapper 专属 + 25 个 DCache 场景回放） |
| 功能覆盖 | **14 个功能组全部 100%**（6 个 wrapper 语义组 + 8 个 DCache 组，后者由 25 个场景原样回放采样） |
| DUT 行覆盖 | **50453 / 51265 = 98.42%**（其中 `DcacheWrapperDut.v` **86 / 86 = 100%**） |
| 分支 | 19033 / 20504 = 92.83% |
| Toggle（DUT-only） | 181196 / 349062 = 51.91% |
| trace policy | PASS（无波形、无逐周期 dump） |
| 构建 | `results/builds/20261025T042153523859Z-dcache_wrapper/report.json`（Picker mem_direct + `-c`，smoke PASS） |

## 2. 先说清楚 wrapper 是什么（这决定验证目标）

`DCacheWrapper.sv` 里只有一个实例：`DCache dcache (...)`。861 个端口与 `DCache` 的
861 个端口一一对应：

| 类别 | 数量 | 说明 |
|---|---:|---|
| 同名直连 | 766 | `auto_client_nodes_out_0/1_*`、`io_lsu_*`、`io_lqEmpty` 等 |
| 改名端口 | 53 | 14 个 `auto_cacheCtrlOpt_in_*` → `auto_uncache_in_*`；39 个 `auto_spec_fabric_source_out_*` → `auto_dcache_spec_fabric_source_out_*` |
| perf 输出 | 42 | wrapper 自己的两级寄存器：`_dcache_io_perf_N_value` → `REG` → `REG_1` → `io_perf_N_value` |

**wrapper 内没有** Uncache 数据通路、没有 uncache/DCache 仲裁、没有第三条 L2 通道、
没有 flush/drain 状态机。真实的 `Uncache` 在 `MemBlock.sv:7891` 与 `DCacheWrapper`
**平级**实例化，仲裁在 MemBlock 层。

因此本 UT 的验证目标是"**边界保真 + 端到端可用**"，不虚构不存在的逻辑：

1. 端口映射完整、1:1、无遗漏（从 RTL 自动提取）；
2. 两个改名端口组都实际走通（cache-control 寄存器读写、speculative fabric 透传）；
3. wrapper 唯一自有时序（perf 两级延迟）行为固定；
4. **同一套 DCache 场景在 wrapper 端口上重放，断言不变、结果一致**。

## 3. 功能点与用例

| 功能点 | 行为 | 用例 |
|---|---|---|
| WFP-001 | 861 端口 1:1 结构等价（766 identity + 53 rename，0 重复、0 悬空） | `test_portmap_is_complete_and_one_to_one` |
| WFP-002 | `auto_uncache_in_*`（原 cacheCtrlOpt）读写 DCache 控制寄存器：ctrl/delay/tagMask/dataMask，AccessAck/AccessAckData，字节掩码语义 | `test_cache_control_register_access_through_wrapper` |
| WFP-003 | speculative-miss fabric 透传：空闲为 0、committed 注入被接受、冷 load 在 S1 产生一拍 candidate（block 地址/grow/channel 正确） | `test_speculative_fabric_ports_are_transparent` |
| WFP-004 | 核心 DCache 行为经 wrapper 不变（hit、miss/refill、store、probe、eviction、atomic、CMO、error） | 9 个 wrapper 专属用例 + 19 个回放用例 |
| WFP-005 | 双 L2 通道按 `paddr[6]` 选择，A/D `source` 保持不变 | `test_reset_and_dual_channel_through_wrapper` |
| WFP-006 | perf 计数在 wrapper 边界两级寄存：接受拍不变、随后变化 | `test_perf_outputs_are_two_cycle_delayed` |
| WFP-007 | 复位/清扫后边界可用，无悬空 valid | `test_reset_and_dual_channel_through_wrapper` |

### 3.1 回放用例（WFP-004 的直接证据）

`tests/dcache_wrapper/test_wrapper_dcache_regression.py` 用 importlib 载入
`tests/dcache/test_dcache.py` 的全部 19 个测试函数，只替换 `dc` fixture 为
`DcacheWrapperEnv`（DUT 换成 wrapper，激励与断言**一行没改**）。覆盖的场景：

- 冷 miss → AcquireBlock → 2×GrantData → 重放命中（逐字节比对）
- 3 lane 命中、同/异行、partial load mask
- 双通道选择、MSHR 耗尽、lq 非空 miss
- store 写后读、store 掩码形态、store miss（整行 AcquirePerm / 部分掩码合并）
- dirty / clean victim 的 C 通道 Release(Data)
- AMO swap/add 命中、AMO miss 完整往返
- CMO 三操作 × 三响应
- denied / corrupt refill 的错误上报

19 个用例全部在 wrapper 上通过，说明 wrapper 不改数据、不吞事件、不改变时序。

## 4. 覆盖率结果与归因

### 4.1 wrapper 自己的代码 100%

`DcacheWrapperDut.v` 86 / 86 行 = **100%**：包含 42 个 perf 两级寄存器、53 条改名连线、
其余直连赋值。这是"wrapper 层逻辑已全覆盖"的直接证据。

### 4.2 剩余 15620 行全部来自内部 DCache

| 类别 | 行数 | 占比 | 归因 |
|---|---:|---:|---|
| 4 个大容量 SRAM 阵列未全扫 | 9208 | 58.9% | `L1PrefetchSourceArray` 3065、`L1RefillLatencyArray` 3059、`L1ErrorMetaArray` 2056、`L1CohMetaArray` 1028。按 set×way 展开的读写译码，仅访问实际用到的 set/way。**范围限制**。 |
| 生成的 `DCache.sv` 宽连线 | 5572 | 35.7% | 顶层把数百条端口/内部 wire 逐位展开，大量恒定/未用连线的 `else if` 臂。**工具/生成代码限制**。 |
| 内联子模块（已有独立 UT，含 `L1FlagMetaArray` 6 行） | 824 | 5.3% | `MainPipe.sv` 285、`MissQueue.sv` 237、`CounterFilter.sv` 129、`MissTrack.sv` 66、`BankedDataArray.sv` 32、`CtrlUnit.sv` 31 等。同一份 RTL 已在独立构建验证（MainPipe 100%、MissQueue 79.7%…）。**不是新增缺口**。 |
| MBIST / 测试逻辑 | 16 | 0.1% | `MbistPipeDcacheTag/Data`。**范围限制**。 |

分支缺口 8027 个方向，同样集中在 SRAM 译码臂与生成代码默认臂；MissQueue/MainPipe 等
的缺口与各自独立报告一致。

### 4.3 Toggle 39-44%

未翻转点：48-bit paddr、50-bit vaddr、512-bit 数据、16 项 MSHR 宽状态、42 个 perf 计数器
的高位、未激活的 forward/spec 端口。功能检查按字段/字节比对，不要求每个数据位双向翻转。

## 5. 与 DCache 顶层运行的关系（避免重复计数）

| 运行 | DUT | 行覆盖（DUT-only） | 说明 |
|---|---|---:|---|
| `full-regression-09` 的 DCache 构建 | `DCache` | 35452 / 51179 = 69.3% | 生成顶层文件名为 `DcacheDut.v` |
| 同一次运行的 wrapper 构建 | `DCacheWrapper` | 50453 / 51265 = 98.42% | 生成顶层文件名为 `DCache.sv` |

两个构建的分母只差 86 行（wrapper 自己的 `DcacheWrapperDut.v`）。命中数差 193 行的构成：
wrapper 自身 +86、内部 DCache 多覆盖 +107（`NewPipelineConnectPipe_9` +64、
`CtrlUnit` +11、`ProbeQueue`/`ProbeEntry` 各 +10、`Queue1_RegMapperInput_6` +8、
`MissQueue` +4、`MainPipe` −3 等）。原因是 wrapper 专属用例（控制寄存器读写、
spec fabric、perf 观察）带来了 DCache 顶层用例没有的激励组合，属正常差异；
两个运行**分别保留分母，不合并计算**。

## 5.1 覆盖率变化（补例重跑记录）

| 运行 | 用例 | 功能组 | 行（DUT-only） | 变化原因 |
|---|---:|---:|---:|---|
| `dw-main-01` | 9 | 61.16% | 35230 / 51265 = 68.72% | 首版：9 个 wrapper 用例；继承的 7 个 DCache 组只被少量场景采样（eviction/atomic/cmo 为 0），`portmap` 组交叉 bin 未填满。 |
| `dw-main-02` | 9 | 100% | 35230 / 51265 = 68.72% | 覆盖口径修正：wrapper 只使用自己的 6 个语义组（不再继承 DCache 组以避免重复计数），`portmap` 交叉只定义语义合法组合。行覆盖未动（无新增场景）。 |
| `dw-main-03` | **28** | **100%（13 组）** | **35645 / 51265 = 69.53%** | 补 19 个 DCache 场景原样回放（同一断言、只换 fixture），行覆盖 +415，其中 wrapper 自身仍 86/86。 |
| `full-regression-11` | **31 + 1 xfail** | **100%（14 组）** | 36013 / 51265 = 70.25% | DCache 场景增加到 23 个（写回阻塞、约束随机、store-merge 缺陷），wrapper 自身仍 86/86。 |
| `full-regression-14` | 32 + 1 xfail | 100%（14 组） | 48360 / 51265 = 94.33% | 继承 DCache 的 256 set × 4 way + 4 端口扫描用例，wrapper 自身仍 86/86。 |
| `full-regression-15` | **33 + 1 xfail** | **100%（14 组）** | **50453 / 51265 = 98.42%** | 再继承 prefetch 装入 + demand 清标记扫描；wrapper 自身仍 86/86。 |

补例的直接依据：`dw-main-01` 的组明细暴露出 `dcache.eviction/atomic/cmo = 0%`，
说明 9 个 wrapper 用例只抽样了少数核心行为；因此把 DCache 顶层全部 19 个场景搬到
wrapper 端口重放，而不是为覆盖率单独构造激励。

## 6. 未纳入范围（及正确的下一步入口）

| 目标 | 现状 |
|---|---|
| Uncache 与 DCache 的 A/D 仲裁、返回 | `DCacheWrapper` 内无此逻辑；`Uncache` 与它平级在 `MemBlock`。需要 `MemBlock` DUT。 |
| flush / drain | DCache 无独立 flush 端口，wrapper 不新增。 |
| CSR / 中断 | wrapper 只暴露控制寄存器 TL slave（WFP-002 已覆盖）。 |
| L2 协议规范一致性 | 由 DCache 内部各队列与 A/D 通道用例覆盖。 |

## 7. 证据

- 运行：`results/dw-main-03/`（`manifest.json`：`state=committed`、28 PASS；
  `coverage-audit.json/.md`；`trace-policy.json` PASS）
- 构建：`results/builds/20261025T042153523859Z-dcache_wrapper/report.json`，
  Picker 构建 ID `68a3f2fcc69cdb4fac8890ae33a13f077b0a03470d62c50acb432e1c7ce22ef9`，
  `ok=true`、`missing=[]`、smoke PASS
- 覆盖率数据：`results/dw-main-03/native/68a3f2…/coverage.dat`，
  SHA-256 `c5e1a66d01d958cfb8be6faabf4bbfcd7cdd17c3c5c4a7c3c8e59b254be6b9cf`
- 端口映射：`manifest/dcache-wrapper-portmap.json`（由 `tools/wrapper_portmap.py` 生成，
  861 连接 / 766 identity / 53 rename / 42 internal / 0 重复 / 0 悬空）
- RTL 哈希：`manifest/rtl-sha256.json`（`dcache_wrapper` 闭包 59 个文件）
- 工具：Picker `2.0.0-HEAD-4dd442c`、Verilator `5.052`、toffee
  `2.0.0.dev12+g3017293a7`、xspcomm `0.3.0.dev3`
