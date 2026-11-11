# LSU-HWPF-MISS-001：硬件预取已经 miss，性能事件却永远报 0

**结论：已确认的 RTL 性能事件缺陷，未修改 RTL、未完成修复复测。** 固定版本为公开 `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e`。这是 **1 个独立根因**；多次运行、多个种子不重复计数。

## 1. 用一句话理解

模块先规定“预取不需要普通 Load 的重放原因”，随后又要求“预取必须同时带着普通 Load 的缓存 miss 重放原因”才报告预取 miss。两个条件互相排斥，于是这项性能事件永远计不到。

类似于先把货车排除在“客车登记表”之外，再要求货车必须出现在客车登记表里才统计货车数量。

## 2. 正常应该怎样工作

`LoadUnitS2` 接收 Load/预取的访问属性与 DCache 结果。`s2_hw_pf_access` 统计硬件预取访问，`s2_hw_pf_miss` 应在有效、未取消的硬件预取发生 DCache miss 时产生事件。

这里检查的是**有流水延迟的事件脉冲**，不是每次应永久加一的累加寄存器；`io_perf_3_value` 输出宽度为 6，但当前生成实现承载一个延迟布尔值。测试等待两级事件寄存器，不在无效拍比较随机初始值。

预期还得到同文件既有调试计数的支持：`prefetch_miss` 使用原始 DCache miss，而不是普通 Load 的 replay cause。硬件预取可以 miss，但不应因此伪造 ROB 异常或普通 Load 的重放。

## 3. 有问题的 Scala 实现

文件：`XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala`。以下均为固定提交原文，不是建议修复代码。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala:1059-1061 -->
```scala
  val alwaysWriteback = exception || isMMIOReplay
  // 1. Trouble maker
  val troubleMaker = !isPrefetch && !alwaysWriteback
```

<!-- source: XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala:1120-1120 -->
```scala
  cause(C_DM) := troubleMaker && needDCacheAccess && dcacheMiss
```

<!-- source: XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala:1280-1286 -->
```scala
  val perfEvents = Seq(
    ("s2_in_fire", pipeIn.fire),
    ("s2_dcache_miss", pipeIn.fire && !kill && cause(C_DM)),
    ("s2_hw_pf_access", pipeIn.fire && isHwPrefetch),
    ("s2_hw_pf_miss", pipeIn.fire && isHwPrefetch && !kill && cause(C_DM))
  )
  generatePerfEvent()
```

`package.scala:98–99` 定义 `isHwPrefetch = isPrefetch && ...`。因此：

```text
isHwPrefetch => isPrefetch
cause(C_DM) => troubleMaker => !isPrefetch
isHwPrefetch && cause(C_DM) == false
```

同文件 `NewLoadUnit.scala:1266` 的另一套统计口径：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala:1266-1266 -->
```scala
  XSPerfAccumulate("prefetch_miss", fire && isPrefetch && io.dcacheResp.bits.miss)
```

生成 RTL 也保留同一根因：`rtl/load_s2/LoadUnitS2.sv:549–550,573–575,865–866,1137`。Scala 文件 SHA-256 为 `c649adc99c0bb67b10f51cddf4b849b0f7d9145e27bdf2f477879d1ea4c87b45`；S2 RTL SHA-256 为 `bf12b3a3de582b101366347bbcbcd7f4afecdd163cd4ffc2ce6e49712cd49d0a`。

## 4. 怎样激励

独立 `LoadUnitS2` 原生 DUT，使用合法硬件预取类别：

1. reset 后输入一个有效高置信预取，`entrance=0x10`、`instrType=4`、`pftType=0`、`mask=0`。这些编码依据 `package.scala:61–71,90–101`；不使用已消除的父块预取端口。
2. TLB 已命中，无 redirect、kill、异常或 replay，DCache 返回 `miss=1`。
3. 再走一个时钟，观察延迟事件。
4. 同样运行 `miss=0` 的命中负对照。

| 输入/观察 | miss=0 负对照 | miss=1 反例 |
|---|---:|---:|
| `io_perf_2_value`，硬件预取 access | 1 | 1 |
| `io_perf_3_value`，应有的硬件预取 miss | 0 | **1** |
| `io_perf_3_value`，实际 | 0 | **0** |
| 用例结果 | PASS | **普通 FAIL** |

种子 **1、17、123** 的独立运行均为 `1 PASS / 1 FAIL`。命中对照与 access=1 排除“激励根本没到”“事件延迟采错拍”两类常见误报；布尔互斥证明排除换种子后偶然正确。

## 5. 为什么不是测试误报

- 预期来自事件语义、访问类别定义及旁边的原始 miss 统计，**没有把 RTL 的死条件复制成规范预期**。
- 采样实际公开引脚；旧模型即使继续期望 perf3=0，新规范断言仍失败。
- 没有修改 DUT、注入 readback 故障或替换任何真实硬件子模块。
- 失败不依赖对无效 payload 的比较、不依赖特殊背压，也不是运行器/构建错误。

## 6. 后果和证明边界

- **已证明**：该固定 S2 实现不能输出硬件预取 miss 事件，影响性能统计与调优判断。
- `NewLoadUnit.sv:1152–1153,4011` 将 S2 perf3 再延迟后送到父块 perf7；这是同根因的静态传播，不另计一个 Bug。
- **未证明**：访存数据错误、死锁、整核 ISA 失败或 CSR 软件可见后果。本次生成父块的直接硬件预取入口已被消除，未声称在该父块上注入了不存在的输入；直接动态反例是 S2 UT。
- 修复方向：让命名为 hw-prefetch miss 的事件使用符合定义的有效预取与 DCache miss 条件；不能靠把规范预期也改为 0“修复”。本轮不修改目标 RTL。

## 7. 现有复现和证据

工作目录：`memblock-hash/lsu/`。工具链与原生 DUT 已安装时：

```sh
python3 -B tools/run.py --name hwpf-miss-repro-fresh --workers 1 tests/load_s2/test_spec_prefetch_miss.py
python3 -B tools/coverage_audit.py hwpf-miss-repro-fresh
```

必须换全新运行名；原 RTL 下退出码应为 **1**，不是修复通过命令。失败节点为 `test_hw_pf_miss_event_counts_a_real_cache_miss[1]`，实际 `0 != 1`。

- `results/recheck-prefetch-spec-02/`：种子1，JUnit、console、manifest、provenance、原生 coverage、覆盖审计齐备。
- `results/recheck-prefetch-seed-17-01/`、`results/recheck-prefetch-seed-123-01/`：不同种子的命中/未命中对照。
- `results/failure-recheck-final-03/`：当时全套增强回归 **582 PASS / 1 FAIL**，唯一失败就是此节点。上游核查后当前回归为 `upstream-review-regression-02`：**582 PASS / 7 FAIL**。
- `review/failure_recheck_20261026/fixed-source/NewLoadUnit.scala`：从固定提交提取的源码。

## 8. 上游和修复状态

本轮没有查询 GitHub 是否已有同根因报告，没有提交 Issue/PR，也不声称“最新上游仍未修复”。结论仅绑定本报告的固定提交与生成 RTL。
