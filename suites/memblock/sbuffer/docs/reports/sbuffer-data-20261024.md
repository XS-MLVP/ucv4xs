# SbufferData：字节级存储/掩码语义 UT

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


## 1. 结论

真实 `SbufferData` DUT 完成 15 个功能用例，**15/15 PASS**。功能覆盖 4 组全部 100%，
toggle **70684/70684 = 100.0%**，分支 **2115/2116**，DUT 的 LCOV 唯一行
**8518/8518 = 100%**、过程语句未覆盖 **0**。唯一未命中分支是生成 RTL 时间零
`initial` 中 `if(reset)` 的 else；没有使用 xfail/skip，没有删分母。

运行目录：`results/sbuffer-data-initial-04/`（manifest committed，
`coverage_complete=true`）。

## 2. 功能点与实现

功能点见 [`../functional-points-sbuffer-data.md`](../functional-points-sbuffer-data.md)。
共 13 组语义：

- 写：字节掩码写、整行 `wline` 广播、16B lane 选择、`wvec` 行位图、无效写、两拍延迟、
  双端口并发、写入累积。
- 清理：按行清 mask 保数据、行位图多行清理、清理与写同拍、无效清理。
- 复位与空闲：复位清 mask 并取消在途写；空闲输出保持。
- 阵列可达性：16 行 × 4 lane × 16 字节 × 两个写端口的完整扫描。

独立参考 `sbufferverify/sbuffer_data/model.py` 只消费公开写请求/清理请求，维护每行
每 lane 的 data/mask/known 账本。环境 `env.py` 先在捕获沿检查“无提前可见”，再在提交沿
逐字节比较 mask 和所有已知数据；失败立即抛 AssertionError，覆盖采样发生在比较成功之后。

## 3. 用例与覆盖对应

| 用例 | 覆盖的语义 |
|---|---|
| `test_reset_initializes_masks_and_idle_is_stable` | 复位、空闲保持 |
| `test_single_byte_each_lane` | 单字节 mask、两拍延迟、空 mask |
| `test_wline_broadcasts_payload_to_whole_line` | 整行写（零/非零载荷）、部分 mask 被忽略 |
| `test_wline_both_ports_all_lines` | 两个端口、全部 16 行的 wline 与 lane 切换 |
| `test_vword_offset_selects_low_two_bits_only` | lane 只取低 2 位，高位 2..43 全部别名 |
| `test_wvec_multi_line_broadcast` | 多行同拍写入、多行清理 |
| `test_all_lines_and_lanes_are_independent` | 16×4 全阵列写、全行清理 |
| `test_dual_port_combinations` | 异行、同行异 lane、同 lane 不重叠、同字节覆盖 |
| `test_back_to_back_writes_accumulate` | 连续写累积、部分 mask 覆盖 |
| `test_flush_single_two_many_all` | 单行/双行/多行/全行清理、无效清理 |
| `test_flush_and_write_same_cycle` | 清理与写同行/异行并发 |
| `test_invalid_requests_do_nothing` | 无效写、无效清理 |
| `test_reset_contexts` | 空闲复位、清理同拍复位、在途写复位 |
| `test_exhaustive_cell_and_port_sweep` | 每行/lane/字节 × 两个端口 × 互补数据，全阵列 mask 清 |
| `test_random_legal_traffic` | 合法随机混合（seed `0x5B0F2026`） |

## 4. 覆盖率

| 指标 | 结果 |
|---|---|
| Verilator line points | 1027 / 3108（33.0%） |
| Verilator toggle | **70684 / 70684（100.0%）** |
| Verilator branch | 2115 / 2116（99.95%） |
| LCOV DUT 唯一行 | **8518 / 8518（100%）** |
| LCOV DUT 过程语句未命中 | **0** |
| Picker harness 唯一行（不计入 DUT） | 0 / 6226 |
| 功能覆盖 | 4 组均 100% |

Verilator 的 line point 统计包含声明/赋值点，不能直接当作“过程行覆盖率”；本报告以
LCOV 逐行分类为准。

### 未覆盖项定位

| 项 | 数量 | 分类 |
|---|---:|---|
| `initial` 中 `if (reset)` 的 else | 1 branch | **时间零初始化分支**：`initial` 只在仿真时间 0 执行一次；本 DUT 构建在此路径上覆盖了 reset 分支，else 分支不可由运行期激励到达。周期 reset 由 always 块覆盖 |
| Picker harness 行 | 0 / 6226 | 生成的端口连线顶层，不属于 DUT；保留原始分母，不计入 DUT 闭合 |

没有“已有功能点缺失情况”或“整体功能点缺失”导致的未覆盖过程行；DUT 文件本身已达到
100% 行覆盖。

## 5. 关键实现边界

- `SbufferData` 的写请求是 Valid-only，固定两拍后生效；测试按“捕获沿不提前可见、提交沿
  精确匹配”检查。
- 双端口同一字节重叠时 1 号端口覆盖 0 号端口；这是模块级优先级，父块正常不会制造该
  重叠。测试记录但未把它当作父块合法并发域。
- `wvec`/`maskFlushReq` 在父块实际是 one-hot，但模块合同允许行位图；测试覆盖了多行。
- 父块只在 `cbo.zero` 产生 `wline` 且 payload 恒为 0；本模块用例中的非零 payload 广播
  只验证 `SbufferData` 自身的广播能力，明确不是父块可达行为，不计入父块证据。
- `dataOut` 未写过的字节是未初始化值，模型只比较 known 字节。

## 6. 复现

```sh
cd memblock-hash/sbuffer
python3 tools/run.py --name sbuffer-data-repro-01 --workers 1 tests/sbuffer_data
python3 tools/coverage_audit.py sbuffer-data-repro-01
```

（`sbuffer-data-initial-04` 是本次报告使用的最终运行；重新运行应使用新目录名。）
