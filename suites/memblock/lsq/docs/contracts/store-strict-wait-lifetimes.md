# Store strict 地址等待、完整身份与真实唤醒生命周期

本合同在新增测试实现前定义。目标缺口是 regression15 中真实 PSQ/SQ/Wrapper
的 Forward `s2LoadWaitStrict` 选择臂及 strict 依赖完整 SQ 身份方向点；
不是重做叶子 smoke，也不以这些补例替代已有别名、越窗、禁用反馈等失败。

## 语义功能点与 oracle

| 功能点 | 人类可读的行为与实际检查 |
|---|---|
| `PSQ-STRICT.lifecycle` | 64 个较老 Store 中只有最后一项尚未收到真实 STA，其余地址和所有数据已就绪。strict Load 必须因这一地址洞阻塞，并报告程序上最后一个较老 Store 的完整双 flag/SQ 值；同地址、同 SQ 上界的非 strict 精确等待 Load，只等待其已就绪预测目标，不被无关洞错误阻塞。真实洞 STA 到达后新 strict 查询解除等待，全部 Store 只能在真实 Sbuffer 消费后正常完成。 |
| `SQ-STRICT.lifecycle` | 上述语义由真实 dispatch→VSQ→PSQ 产生，不外驱内部 ready bitmap、物理上界或退休许可。真正 ROB 前进许可后，每个 flow 的字节消费和真实出队反馈释放虚拟所有权；同物理槽跨四代复用仍返回正确完整依赖身份。 |
| `LSQ-STRICT.lifecycle` | 完整 Wrapper 中分别派发三条 strict、三条非 strict 精确等待 Load。strict 转发失败必须进入真实 Replay 地址依赖等待；精确等待 Load 可正常完成 S3，但不能越过旧 strict Load 释放 VLQ。洞 STA 和同一 Store 的有效执行 wakeup 到达后，只消费真实公开 Replay 授权，重查转发字节，使用实际 replayQueueIdx 反馈，最终完成原 Load/Store UID。 |

Wrapper 的复合情形 ID 记录在本合同及 compact witness；原 82 项主目录不改，
实际 checked 映射到 `LSQ-FORWARD.addr_hole/sqid/wrap` 和 `LSQ-REPLAY.strict/sq_address`，
不以新增复合名称改变旧功能覆盖率分母。PSQ/SQ 则各新增一个本合同的情形 bin。

## 合法输入与时序

- 每代 64 个互不重叠、16B 对齐的普通 8B Store，地址/数据由外部 UID
  台账决定。所有 STD 和前 63 个 STA 通过公开两路 producer 输入到达；
  第 64 个 STA 保持未发行，不伪造地址无效、就绪位或内部状态。
- 四代物理 SQ 起点为 0、64、128、192，Load 独占上界为起点+64。
  被报告的 strict 依赖为上界-1，依次对应 SQ63、127、191、255。
  循环编码只在公开指针处模 256，不使用非法物理索引。
- 查询所需字节来自每代第一个已经 STA/STD 就绪的 Store；洞 Store 与其
  VA/PA 均不重叠。strict 和非 strict 精确等待都带 wait=1，预测目标是
  已就绪的第一个 Store。strict 不能只看预测目标；非 strict 不应等待
  与该目标无关的洞。
- S0 查询后下一拍给相同页偏移的 S1 PA；只在有效 S2 检查结果。
  地址依赖有效时检查完整依赖身份，不把返回数据当作可消费成功；
  解除等待的查询才检查有效 mask、原始 8B 数据及其他 replay/dependency 标志。
- 等待和查询阶段禁止 Store 退休/预提交并保持 Sbuffer ready=0。
  洞填补后仍须检查实际消费、正常出队和 empty，不能用 reset/取消冒充复用。
- Wrapper 的 strict/精确对照属于不同真实 Load UID，保持各自 uop 解码字段
  不变。strict Load 的 S3 地址依赖来自已核验的公开 Forward 响应；后续
  replay grant 与反馈必须绑定原 LQ/ROB/SQ/slot，不能先反馈再补造授权。
- Wrapper 洞唤醒使用真实 STA 与有效 StoreWakeup，同拍指向同一完整 SQ。
  本用例不声明 bitmap-only/disabled-feedback 的 strict 语义已修复；那些
  原有失败继续执行并保留。

## Reset、取消、异常、don't-care 与范围

fixture 只在开头正常 reset；四代之间不 reset、不取消。初始化边界、取消、
CBO、NC/IO、跨 word/page、错误响应以及越物理窗口身份不在本补例的新域内，
原合同及原用例不删减。无效 S2 数据和 addrInvalid.valid=0 时的依赖 payload
为 don't-care，不用它们冒充功能成功或扩展合法域。

## 必须保留的证据

1. 三层独立 fresh baseline/after，baseline 节点全部保留；同 build、同点全集、
   同源集合摘要，逐项比较 line/toggle/branch 与 LCOV 原始源码行。
2. compact witness 包含四代公开依赖身份、三路阻塞/对照/解除等待计数、真实
   Store 完成；Wrapper 另记公开授权 slot、原 Load 反馈/完成和实际 Store wakeup。
3. 对 regression15 缺口只做同 DUT/同 build 的集合交集，不能回填其历史命中。
   若执行目录重跑，单独保存结果，真实 FAIL 不变绿，不屏蔽、不 xfail。
4. 原样 RTL/Chisel、真实下级连接和独立参考模型保持不变。只保留摘要、失败、
   compact witness、覆盖和复现证据，不生成逐拍 JSON、波形或完整源副本。

## 覆盖单调性失败时的隔离诊断

真实四目录重跑若出现旧 toggle 命中丢失，必须保留差集、原源位置与原失败门禁。
不能只报净增益或据此把点归为初始化/don't-care。已有 Wrapper 原 689 节点的
2067 份 public/check/actor stream 摘要相等，只说明已观测/检查流保持相同，
不等于内部寄存器轨迹或 native 覆盖上下文已证明相同。

诊断重复使用原有 `[aligned-0]` Wrapper 节点，不改其代码：A 在单 worker 独立
运行该节点；B 在同一 worker 先运行既有 Forward 空闲、PSQ 校准、SQ reset
三个节点，再执行相同 Wrapper 节点。每对 source aggregate、build、点全集
及 Wrapper 三份 journal 摘要逐项比较，保存真实三类点和计数差异。这是覆盖
复现性诊断，不替代分层 UT 或证明某个业务缺口不可达。根因未建立时门禁继续失败。
