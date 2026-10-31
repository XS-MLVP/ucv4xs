# MicroBTB（UBTB）迁移适配与覆盖率闭环（2026-10-29）

本文记录整芯片 DefaultConfig RTL 下 MicroBTB 单 DUT 的第一轮语义功能点闭环。运行目录均为新目录，输入为用户当前仓库的整芯片生成缓存。

## 语义功能点与用例

已有功能点 BPU-UBTB-001..017 保持。依据整芯片实际端口和 toggle 缺口新增/扩展的语义点：

1. **整芯片裁剪后的预测有效性**：MicroBTB 恒为 taken 预测器，整芯片优化删除了未被父模块使用的
   `io_prediction.valid`。有效性等于“使能且存在 taken 预测”。测试 `test_global_disable_blocks_fast_train_without_erasing_entry`、
   `test_cold_lookup_misses_and_enable_suppresses_a_hit` 及语义监视器按此定义检查，未引入内部信号或伪造 valid。
2. **常量状态端口**：`io.sramResetDone` 与 `io.trainReady` 在 Scala 中恒为 `true.B`，整芯片优化后不再存在。适配层按声明常量绑定，测试 `test_reset_reports_prediction_and_training_ready` 仍检查复位后可用。
3. **FastTrain 无 mispredict 叶**：`HasFastTrainIO` 的 `BranchInfo.mispredict` 未被 MicroBTB 消费而裁剪；S3 fastTrain 的语义就是纠正，适配层在解码时补 `mispredict=1`，resolve 仍使用真实位。
4. **五 bit 位置域**：DefaultConfig 取指块 64 字节，`cfiPosition` 为 0..31。原编码器沿用 16 位置上限，导致 16..31 无法驱动且 position[4] 永不 toggle。已改为 5 bit，并新增边界用例（位置 16、31）与 32 项容量向量。
5. **完整条目存储与复位清除**（新用例 `tests/ubtb/testcase/test_storage_payload.py`）：
   - 复位清除所有条目的 tag/target/position/type/RAS/usefulness，复位后必须先重新学习；
   - 32 个条目的全部字段按互补位型写入、复位、再写互补值、再复位，验证写入不截断/不串扰且全宽清除；
   - 使能空闲周期不改变替换状态：miss 后让 s1_hit 为 0，空闲 4 拍，再填满容量，除合法受害者外全部命中。
6. **查询/复位生命周期**：复位断言优先于尚在 s0→s1 的响应。监视器在复位引脚为高的边界不比较预测；`reset-after-launch` 场景先等待语义接受再复位。`reset-ended`/`responded` 判定仍由独立模型给出，不按 DUT 实际值反推。

## 运行与判定

```sh
.venv/bin/ucv run bpu --workers 2 --output results/ut-ubtb-gap2-20261029 -- tests/ubtb
```

- 原生 UBTB：49 PASS，0 FAIL。
- 同次纯模型分区：168 PASS，0 FAIL。
- 功能覆盖组（ubtb.prediction / usefulness / enable / reset-lifetime / pipeline-ownership / resolve-slots / resolve-arbitration / bypass-recovery）均为 100%。

## RTL 覆盖率

覆盖数据：`results/ut-ubtb-gap2-20261029/bpu-ubtb/native/218b9923.../coverage.{dat,info}`。

| 对象 | 行 | 分支臂 | toggle 完整位 |
|---|---|---|---|
| `MicroBtb.sv`（编译副本 `UbtbDut.v`，仅模块名不同） | 805/806 (99.88%) | 102/104 | 2019/2020 |
| `MicroBtbReplacer.sv` | 61/61 (100%) | 70/72 | 110/110 |

`UbtbDut_top.sv` 是 picker 生成的引脚 shim（`module UbtbDut_top()` + public_flat_rw 声明），不是设计源；其行覆盖率不计入设计判定。`UbtbDut.v` 与 `rtl/ubtb/MicroBtb.sv` 在模块名之外逐字节一致。

### 未覆盖项定位（全部为结构不可达，不新增功能点）

| 项 | 局部依据 |
|---|---|
| `MicroBtb.sv:722`（`(|usefulCnt)? cnt-1 : 3` 的 else 臂） | `t1_hitOH` 的每个候选都含 `(|entries_i_usefulCnt_value)`，命中时 useful≠0，故该臂不可达。 |
| `MicroBtb.sv:1649` else | `initial` 块内 `if (reset)`；本 DUT 在时间 0 即断言复位，else 分支不可达。 |
| `MicroBtbReplacer.sv:279` else | 外层条件为 `predTouch \| trainTouch`；内层 else 要求 trainTouch=0 且 predTouch=0，与外层矛盾。 |
| `MicroBtbReplacer.sv:296` else | 同上，`initial` 内时间 0 复位分支。 |
| `s1_startPc_addr[49]` toggle | 公共 API 的 50-bit 字节地址编码为 49-bit 半字，寄存器最高位恒为 0。 |

## 结论边界

- 本轮只证明 MicroBTB 模块级语义、复位、替换与存储端口；不代表完整 BPU 组合或 FTQ 时序已闭环。
- 覆盖率结论基于当前整芯片生成 RTL 与 Picker mem-direct 构建；源码/工具变更后需重建并重跑。
- 真实 FAIL/XFAIL/SKIP 未删除或放宽；本轮没有需要登记的 UBTB FAIL。
