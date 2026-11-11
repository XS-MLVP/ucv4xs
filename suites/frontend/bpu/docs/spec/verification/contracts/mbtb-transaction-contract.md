# MainBTB 当前事务适配合同（public-a0c2a26cb / DefaultConfig）

状态：**当前验证侧合同；设计 owner 确认待完成**。适用完整香山
`public-a0c2a26cb` / `a0c2a26cbe3c862175174bad03a1a23c406315ed` / DefaultConfig 提取的
`MainBtb`。本页把 2026-11-03 新基线条款与经差分确认未变的来源/UID/所有权/收尾承诺
组织成可直接使用的当前合同；它不是 RTL 规范或设计签核，真实 FAIL 与未确认边界保持
原判定。

> 依据：[2026-11-03 新基线适配](../evidence/runs/baseline-update-a0c2a26cb.md)、
> [2026-11-08 收口检查点](../evidence/runs/closeout-20261108.md)。旧基线
> `public-893e1580b` 的统计/四路训练条款和旧运行数字保存在
> [历史合同原文](../evidence/reviews/mbtb-transaction-contract-893e1580b.md)，不与本页拼接。

## 1. 当前输入、输出与合法域

| 通道 | 当前合同 |
|---|---|
| lookup | 50-bit **半字** `GuardedPc.addr`，可带 guard、允许真实 offset，不当作字节地址 |
| training PC / target | 49-bit **半字** `Pc.addr`；后继对齐窗口在 49 位域回绕 |
| result | 两 align ×（四个 Main way + 一个 Victim），target 为 50-bit guarded 半字 |
| 预测 metadata | 每 align 五槽；Main 槽完整属性/counter/position/rawHit，Victim 无 attribute |
| 训练 metadata | 每 align 四个完整 Main 槽；预测快照的第五槽只投影真实训练 wire 的 `rawHit`（1 位）和 `position`（5 位）；第五槽 counter 是输出观察，不驱动不存在的训练叶 |
| resolve vector | 最多八槽，显式 `None` 空槽保留；位置唯一，最多一个 mispredict |
| 生成端口 | `s3_takenMask` 只保留父模块消费的槽 4/9；预测侧每 bank 五槽完整；训练侧每 bank 四 Main way；`trainReady` 为常量；`stageCtrl` s0..s3/t0 保留 |

缺失第五槽、补造 attribute、混合 lookup 祖先或把已 DCE 的 Victim 训练叶补零均拒绝。
`transaction/types.py` 在驱动前拒绝非法类型、超宽、未知/缺字段和错误形状；
`bundle/abi.py` 独立固定逻辑 schema。输入与输出 metadata 递归只读并脱离调用者的可变
容器；显式 deepcopy 返回新的可变诊断/expected 副本，修改副本不能改原观察。

## 2. 当前训练、暴露与驻留语义

以下条款替代旧版 `public-893e1580b` 的 training metadata/四路训练措辞；其他合法域及
身份合同不放宽。

- API 接收完整两 align × 五槽预测快照。前四槽为 rawHit/position/counter/attribute，
  第五槽为 rawHit/position/counter；真实训练 wire 的第五槽只有 rawHit 和 position。
- “现在在 VBTB 中有副本”和“原预测实际暴露了这个逻辑分支”分别判断。隐藏的较晚分支
  可以分配 Main；原预测暴露、当前仍驻留且身份一致时才在 VBTB 就地更新。
- conditional not-taken 的 resolve target 是顺序后继，只消费方向学习，不能创建、重定向
  或改型预测 payload。非 conditional 的 None/not-taken 假命中纠正不能因此被整体禁用。
- 原预测类型不是执行指令类型的真值。对同一原 raw-hit/位置，明确纠正为 conditional 的
  执行 NT 可以削弱其原方向计数，但仍不能改写旧预测 payload 的类型/target。无类型纠正
  时继续要求原 conditional 资格；foreign-tag/raw-miss 和不同位置一律不能借该规则学习。
- source UID/epoch/PC/offer/response tick 与全部五槽一起对账。深拷贝不赋予新来源信用；
  刻意外部端口输入仍须显式声明，不能冒称完整 FTQ producer。

## 3. owner 与迁移程序（经差分确认未变）

cleanup 使用输入 reset-LRU 计划：original/displacer=3，changed/extra=2，keep2/clear3。
shared-service 两行同 bank，原半字基址改为 `1<<31`、tag 步长 `1<<15`、行步长 `0x80`，
真正实现 tag0/1。旧 `0x40000020+(tag<<11)`、neighbor+64 及 `row>>5&63` 不是当前坐标，
物理激励变化明确保留，不声称字节不变。

current-owner 对照提名/服务 2；old-miss 在声明的 taken-original touch 后提名 1，但纠正
必须找回 retained owner 3。同拍 clear3 属于另一行，四个 retained 槽可容纳两项，仍须
服务两次。checker 完整检查 2 align×4 bank×4 way×4 retained slot、原 feedback、两个请求/
服务的全部字段、前态和 fresh 消费者，不按 DUT 返回 way 重命名 expected。

depth-owner 从输入前史建立 owner3、负 peer2 及 stale nomination1。旧 cold 来源不得令
第二深度目标保持旧值或另创 owner；不论来源都应更新同一 retained 记录并保护负 peer。
外层 semantic cleanup 收据改为真实 keep2/clear3，不能因旧常量 1 挡住非零合法控制。

## 4. 时序、框架复用与收尾（经差分确认未变）

lookup 复用框架异步单周期 Driver 及固定延迟 Scoreboard；独立 S1/S2 尾部来自真实 S0
提交。`DriveStable` 保存 pre-edge ready，实际 `RisingEdge` 才采输入；下一 `DriveStable`
消费保存输入，避免可撤回的沿前预览在取消后变成幻影接受。两个 lossless 订阅始终工作。

`checker/lookup_inputs.py` 在 SDK 提交后、发射前保存原 UID/PC/epoch；核对实际 S0 与 SDK
launch 时刻、逐 UID 的 S1/S2 及输出窗口 frame owner。SDK 仍负责响应句柄关联；custom
expected 不能豁免输入/阶段检查。未发射 cancel 有独立终态，不需要伪造响应或失败 tail。
显式 cleanup scope 的保留 S2 脉冲记录原 frame UID；被显式扣住的 S2 记作**未 offer**，
不是已消费。关闭 scope 与模型/原生自主排空检查仍必需，不用次数相等替代身份。

接受后 reset、S0/S1 之间 disable 与 disabled admission 由 `MbtbLookupDisposition` 交付
原 UID/epoch/reason；它不是 `MbtbPrediction`，其 `.preview` 只是无查询来源信用的只读
诊断。已在控制变化前产生的结果保留为真正响应，不能 reset 后追溯取消。SDK 继续负责
关联，`completed` 含终态交付，不能直接当硬件响应数；`lookup_deliveries` 分列。

独立账本分别记录 `sample_tick` 和真正通过 SDK 比较的 `delivery_tick`，过滤/取消的
`response_tick` 保持 None。自定义 expected 只增加有效响应检查，不能豁免错终态或损坏的
SDK 样本；终态不会调用功能响应 callback。长 reset 等待遇到协议错立即唤醒，经公开
Scoreboard drain 传播同一错误，不改 SDK 私有计数、不清观察队列或继续到溢出。

框架没有 MainBTB reset/enable 的语义，所以工程的 `MbtbPredictionScoreboard` 仅扩展公开
比较 hook；提交、接受事件、固定时窗关联、句柄状态和 monitor 消费仍由 SDK 实现。它不是
新的通用传输层，input-only 入口也不补造 response handle。该扩展须随真实相位/终态控制
验收，不能仅凭 SDK 类名或 COMPLETED 统计签核。

每沿只查当前 due 时窗和未产结果 UID；历史行、metadata 来源及旧 tick 查询索引完整保留。
不能每沿扫描全部已完成历史，也不能通过删除旧行取得速度。完整 finish 仍逐项对账。
旧全历史扫描令 shadow 长矩阵持续变慢，已保留未完成回归并定向中断；不将其中间结果
冒充完整验收。

训练继续复用 SDK 独占 SyncDriver，在发射前为每 beat 分配 UID 并冻结完整期望。实际 wire
的 metadata 为每 align 五个槽：四个 Main way 的完整字段，以及第五槽的 `rawHit`/`position`
（实际训练 wire 只有这两个叶，见 [`bundle/abi.py:19-24`](../../../../testbenches/mbtb/env/bundle/abi.py)、
[`driver/feedback.py:15-18`](../../../../testbenches/mbtb/env/driver/feedback.py)）；第五槽 counter 是预测观察，
不进入训练 wire。上述五槽、两个 PC、八个稀疏 resolve 槽及全部字段都需逐 UID 与计划
一致；disabled/reset/初始化过滤、reset 取消、Python 未发射取消和 local-drained 分开。
local-drained 不等于 FTQ 退休。

`MetadataOrigin` 随实际 lookup 响应提供 UID/epoch/PC/offer/response 来源；deepcopy 保留
该非 wire 声明，同时仍返回可编辑诊断副本。新训练在分配 UID 前对账来源 catalog、当前
epoch、49 位 PC 投影和完整 metadata，不能按相同 payload 寻找一个来源。刻意编辑的端口
压力须用 `declared_metadata(reason=...)`，收据明确不是 lookup/FTQ producer credit。
原生来源验证发现 replacement 场景曾将改写的 expected counter3 冒充原 counter2 快照，
现每次正常 touch 都先取真实 lookup 并用独立 wanted profile 检查；没有修改 oracle 或
缩窄原反馈激励。

`finish(timeout_cycles=...)` 只等待已提交的尾部和自主训练写回，使用显式 cycle 预算、SDK
Scoreboard finish 及两个尾部观察，再核对模型 entry/direction/snapshot/cleanup/offer 债务。
不自动补 reset、enable、training、metadata 或 S2 来清债。关闭 monitor、取消 tail、清空
视图都是 cleanup，不是事务完成。正常 close 先 finish；失败保持粘滞。

根 fixture 读取真实 setup/call 报告：正文已 FAIL/skip 只 cleanup，避免同错变第二个
teardown ERROR；正文 PASS（包括吞错）或缺报告仍严格 finish。各资源的独立 cleanup 错误
传播。该 checked-close 当前只启用于 MainBTB 及 cleanup-reset 派生 agent，不签核其他
九 DUT。

## 5. 当前证据与限制

- 当前基线完整 seed1 的 MainBTB 为 **171 PASS / 9 FAIL**；叶 seed2 为 **166 PASS / 9 FAIL**，
  两者不是同一选择，不能拼成同源码完整验收。
- 新基线定向 MainBTB **7 PASS**（隐藏/暴露 VBTB、NT/None 及第五槽 wire 注错控制）；
  53 个原生输入、构建/覆盖/处理器哈希由分配记录审计。
- 真实 FAIL 保留：shared retained-owner 丢纠正、foreign-tag 同位置计数污染、旧 cold 第二
  深度方向污染、联合 zero-key 清错 owner 及四个满容量同位置计数反例。原对照、metadata
  来源和完整 payload 要求不删，不加 XFAIL、不把错行为改成期望。
- 旧版 cleanup v3、训练账本 v4、2853 PASS/9 FAIL 等数字属于 `public-893e1580b` 和当时
  验证源码，见[历史合同原文](../evidence/reviews/mbtb-transaction-contract-893e1580b.md)；
  不重标为当前结果。
- 覆盖产物完备不等于覆盖闭环；runner 清理过的 raw 覆盖输入不能再被声称可逐份复查。

## 6. 当前与历史边界

- 当前默认 `public-a0c2a26cb`：本页第 1–2 节及经差分确认未变的第 3–4 节。
- 旧默认 `public-893e1580b`：统计、四路训练投影和全部旧运行数字只在
  [历史合同原文](../evidence/reviews/mbtb-transaction-contract-893e1580b.md)；不得把旧
  “仅原 conditional 可学方向”或四槽训练结论用于当前版本。
- 2026-10-30 模块复核的端口/坐标事实可追溯，但其 PASS/FAIL/覆盖数字属于当时验证源码，
  见[模块复核](../evidence/module-reviews/mbtb-module-review-20261030.md)。
