# MetaBank 与 SRAM 控制适配检查点（2026-11-02）

适用基线：`public-893e1580b` / 完整香山 DefaultConfig，真实 top 为
`ICacheMetaInterleavedBank`。这是协作交接检查点，不是整个 ICache、DFT 或硬件覆盖闭环验收。

## 实际配置与独立依据

- `ICacheMetaInterleavedBank.scala`：128 个 set、四个 way，独立 `validArray`；
  `readReqReg` 仅在 read fire 时更新。write **valid** 设置 validity，不以 tag SRAM
  ready 为条件；reset/flushAll 的 validity 清除具有更高优先级。
- `Parameters.scala` 与 `ICacheMetaEntry`：`phyTag=36`、`maybeRvcMap=32`、`code=1`，
  每 way 为 69 bit；`MetaWaySplit=2`，实际有**两个 138-bit SRAM 宏**。
- `SplittedSRAMTemplate` / `SramInfo`：每宏两个 way，MBIST `array` 为真实 1-bit 选择
  0/1，`be` 为 2-bit way 写掩码；8-bit `addr_rd` 在 128-row 宏上取低七位。
  single-port 写同样使用 `addr_rd`；`addr` 保留并检查，但不是本宏的写地址。
- 完整生成裁掉了 standalone per-set flush；当前公开接口只绑定 `flushAll`，不补假端口。
- 独立固定 `modules/metabank/env/bundle/abi.py` 逐叶校验上述几何和宽度。不能从同一份错误 metadata
  同时生成绑定与答案，或沿用旧覆盖报告的“单宏、array 零宽”假设。

上述逻辑来自配置和源码中的明确接口/存储分支，实际生成 RTL 与 native 用于核对
物理实例、端口和采样时序。没有改 RTL、生成配置、native 或构建收据。

## 需求到实现与检查

| 义务 | 实现 | 主要自检入口 |
|---|---|---|
| 输入域、完整性和不可变性 | `transaction/types.py`、`bundle/abi.py` | `modules/metabank/tests/scoreboard/test_metabank_transaction_contract.py` |
| SDK 唯一驱动 | `agent/main.py`、共享 `runtime/drivers/level.py` 与 `ResetDriver` | `test_runtime_obligations.py::test_each_control_plane_has_a_real_sdk_owner` |
| 连续完整双相采样 | `monitor/cycle.py` 的两个 lossless `SamplingMonitor` | `test_runtime_obligations.py` 的关闭 monitor/consumer 控制 |
| 默认读自动比较、首错持久化 | `checker/transactions.py` 与 `agent.read()` | `test_default_read_rejects_a_wrong_return_view_without_expected_polling` |
| 逐输入身份及双来源历史 | `MetaInput`、`MetaReadResult`、`model/storage.py` | 相同 payload、flush/write、MBIST 跨来源控制 |
| reset/取消与严格 finish | 共享 `runtime/array_agent.py`、checked fixture | 首沿前取消、关闭采样、绕过 delivery 控制 |
| 非零 SRAM 控制及实际阶段 | 共享 `runtime/transactions/sram.py`、领域 checker | `test_metabank_dft_controls.py` 与 DataBank 对应文件 |

功能用例已去掉手改 `agent.model`、直接 driver/raw dict 和私有 edge，沿用原 set/way
遍历、随机种子与 16 个原功能用例。新增内容为环境自检，不增加硬件功能点信用。

## 发射、消费、响应和来源

真实 rise-write 输入在 rising `t` 发射；前一个 rising 保留的 UID 在 `t+2` 物理消费，
使用沿前 ready。功能响应在该消费边界采样，不轮询“何时等于 expected”。MBIST 的
ack、宏操作、完整读回分别为 `t+2`、`t+4`、`t+6`；ack 绝不充当读响应。

沿前输入 getter 可能已显示新排队意图，也可能在 fixture/任务切换前已捕获旧电平。
因此沿前输入只允许当前声明或上一已发射声明，rising 发射必须精确匹配当前完整声明；
**消费关联只用上一 rising 的真实来源**。新/旧值不能任意选择来匹配输出。

每个有效输入沿有独立 UID，即使数据完全相同；它是环境身份，不是硬件 tag。
`storage_sources` 和 `validity_sources` 分开记录：MBIST 改 tag 不设置 validity，
flush 清 validity 不抹 tag，hold 可以抑制 tag 写但不抑制 write-valid 的 validity 效果。
reset 前已完成记录不改写；未完成 read/MBIST按实际控制边界取消。

领域 checker 先比较独立存储期望，再记录采样；实际交付必须对应保存的完整 result。
纯采样、正常函数返回或 SDK/环境终态本身不证明 payload 比较已完成。

## 非零 SRAM 控制：适用的是模拟宏合同

DataBank 四个物理组各存一个 way，MetaBank 两组各存两个相邻 way。共享严格类型
`SramControl` / `SramControls` 完整描述七个 1-bit 控制；未知/超宽/布尔值、错误组数在
驱动前拒绝，组列表脱离调用方并冻结。`cycle(controls=...)` 声明显式持久电平，
省略时保持；结束前必须由场景显式声明 idle，finish 不替场景释放它。

| 控制 | 当前 DefaultConfig 模拟实现 |
|---|---|
| `hold` | `finalRamWen = ramWen && !ram_hold`，只抑制最终宏写，不抑制 ready 或 Meta validity |
| `bypass` / `bp_clken` | 已连接模拟宏的 DFT 输入，但 `SramArray1P` 存储函数不使用它们；不能编造硅宏 bypass 功能 |
| `aux_clk` / `aux_ckbp` / `mcp_hold` | `extraHold=false`，本实例没有这条多周期时钟选择逻辑，保持完整输入观察但不虚构效果 |
| `cgen` | DataBank 无 clockgate；MetaBank 打开 gate 测试使能，但宏读写仍受自身 enable 控制 |

依据为锁定的 `utility/sram/SRAMTemplate.scala`、`SramHelper.scala`、`SramProto.scala`、
`utility/mbist/MbistClockGateCell.scala` 和 `utility/ClockGate.scala`；生成宏进一步核对
了不适用输入与真实 gating。控制的物理消费必须用上一 rising 电平，不能把本次释放的
预览电平倒用于上一写入。功能写、MBIST 宏阶段和 reset 清扫均受此约束。

宏阵列**没有 reset pin**。`modules/databank/model/sram_initialization.py` 从声明的 reset 日程推导逐 row
清扫，不从 ready 或返回数据猜清扫位置；MBIST覆盖或 hold 可使某 row 没有实际写零。
这类 cell 保留真正旧祖先，而不是在模型中瞬间清零。未初始化 cell 的内容不被假设为零，
以已知位 mask 显式记录比较边界；validity、输入身份、响应时窗仍照常检查。
这不是硅片 DFT/timing 验证，也没有为未知数据提供硬件功能 PASS 信用。

## 生命周期与证据边界

`ArrayAgent` 只共享两个 DUT 确实共用的 SDK 所有权/采样装配、显式 cycle 调度和收尾，
不包含 DUT 存储或端口解码。唯一采样 consumer 停止必须报错并唤醒等待者；
`finish()` 在任何 drain tick 前拒绝未发射计划、reset 日程、未撤销功能 offer和非 idle
控制，只等待自主清扫/管线尾部。`aclose()` 仅 cleanup，不能替代 finish。

pytest 正文已报告非 PASS 时只 cleanup，正文 PASS/吞错/缺报告时严格 finish；独立
cleanup 错误仍传播。根 `tests/test_icache_checked_fixture.py` 覆盖真实报告桥接。

原 MetaBank runtime 探针修前为 10 FAIL/1 PASS，修后相同十条错误控制均 PASS；
随后 stopped-consumer、hold 错存储、释放相位、reset-sweep hold 均取得真实 native red。
本次协作收尾的两 DUT 定向为 **305 PASS**，source `b48dc54b...`，131 个 native 实例、
12 个构建文件及全部产物/processor hash 已审计，原项无删除/判定变化。
完整工程及第二 seed 的最终数字见
[协作检查点](../../../../../../../docs/collaboration-checkpoint-20261102.md)。

剩余 API/调度组合、直接采样错误/身份反证的进一步系统性复核，以及其余 ICache DUT
继续交接；本文件不声明两个 DUT 的所有组合或整个工程已签核。
