# DCache L2 传输检查边界（2026-11-01）

## 来源与适用配置

适用 public-893e1580b + DefaultConfig：两条 TileLink 通道、64B cache line、
256-bit/32B 数据 beat。原生端口宽度不符立即失败，不静默截断到另一配置。
独立依据来自该基线 rocket-chip 的 tilelink/Monitor.scala：

- C 多拍保持 opcode/param/size/source/address；beat 只能在 valid && ready 的接受沿计数。
- GrantData.denied 必须同时设置 corrupt（Monitor.scala 的 GrantData 检查）。
- AcquirePerm 允许 Grant 或 GrantData；不能把现有 GrantData 响应误报为协议违规。
  MissQueue.scala 的无数据 Grant 分支要求 full_overwrite；本轮另加合法对照覆盖该分支。

## 字段、时序与完成语义

`dcache/tilelink.py` 是对既有同步 Step 适配器的修复，不是新框架：

| 事务 | 独立输入/身份 | 接受与结束 |
|---|---|---|
| Acquire | DUT 输出的 channel/source/address/opcode/size；地址与调用者期望核对 | 只打开选中 A.ready；其他通道保持反压，不产生未登记接受 |
| GrantData | source 回显所记录的 A；data 为调用者提供的两个 256-bit 常量 | A 接受后才发 D；每拍在推进前读 ready；背压保持同一 beat，2 次 fire 完成 |
| Grant | full-overwrite AcquirePerm，无数据 | 1 次 D fire；不将 data 字段作为检查依据 |
| CMessage | 记录实际 C.fire；保持完整头与所有 data beat | Release/ProbeAck 为 1 拍；有数据版本为 2 拍，相同数据不去重，半包不能正常结束 |

异常时撤销 A.ready 和 D.valid/全部 D payload，恢复 C.ready；超时不构造全零成功值。
`last_refill` 仅在整个调用成功后保存不可变结果；其 cycle 是调用内相对位置，不是全局
仿真 tick。`refill_with_releases` 额外打开 C.ready 并在有限窗口内排空/检查完整 C 包。

## 独立检查与反例

dirty eviction 的期望来自测试已提交的完整行 store 数据，允许 victim 在四条已安装
地址中合法选择；用选中的身份查独立 store 账本，不用 DUT 数据反推期望。检查全部
64B，而非仅第一个 64-bit 字。无数据 Release 不比较协议未定义的 payload。

- `tests/checkers/test_l2_responder.py`：ready 沿后升/降、双 A 同时 pending、D 超时、
  denied/corrupt、无数据 Grant、非法行数据/端口宽度、相同 C beat、第二 beat 错误和头变化。
- `tests/dcache/test_l2_protocol.py`：真实 DCache 与 wrapper 各自验证双 pending 通道、
  full-line store + 单拍 Grant，并读回两个半行的六个独立 8B 窗口。
- 两个原有 dirty eviction 用例改比较完整双 beat；clean eviction 只检查无数据消息。

随机流的 dcache/traffic.py 也只在已接受完整 C 事务后按其 source/size 应答 ReleaseAck；
空闲 D.valid 为 0。pump 的同拍快照记录 C 和 D，不因先处理 Ack 就漏 C；结束前检查
Ack 义务与半包，窗口外 C.ready=0，避免手工 Step 消费未记录的 C。L2 refill 内容与
独立 pending-store 期望分开，不能把 golden store 字节直接喂回 DUT 来自证正确。

对检查点 0017350 的旧 service_miss 做冻结函数注入，确认旧代码会误拒绝已接受的 D、
漏掉首个 D beat、消费未记录的第二条 A、发送 denied 但不 corrupt 的数据；新控制修复
这些差异。注入层为 bench transport，不宣称做过 RTL mutation 或完整 ISA oracle 证明。

## 没有完成的事项

本轮未把整个 DCache 工程改为 Toffee SyncDriver/SamplingMonitor/Agent，仍保留既有同步
入口以进行有界语义修复。框架已经提供相关组件，后续应迁移，不认为手工 Step 与框架
生命周期等价。C 观察仅限显式 service 窗口，不证明全程无漏拍；其他 legacy env、raw_dut、
通道字典、引脚所有权冲突和全部未完成义务仍需继续收口。布局门禁必须保留这些缺口。

运行与证据见[本轮复核](../../../../docs/lessons/semantic-boundary-repair-20261101.md)。
