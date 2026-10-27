# 源正确的联合容量转移/CBO与串行补例：27例21 PASS/6 FAIL，整体未验收

**本轮实际最终目录`lsq-ldu-joint-phases-05`：27例21 PASS / 6 FAIL，475启动/结束源一致。**
真实53文件Picker DUT、xreactor连续严格458输出检查不变。原6个SID反例普通保留，
不skip/xfail，不用正条件替代原8类型/种子完整随机。独立原UID/源关系审计与自身
DA分类分开记录；本体114/114不能代替完整验收。

## 1. 先纠正旧联合快照的整体关系遗漏

旧joint04六PASS及5456 UID/DA原件保留。但[独立公开历史拒绝](../../results/lsq-joint-capacity-04/joint-producer-audit-v1.json)
在六个初始快照发现720次Replay S3无原查询revoke、624次错拍/换lane S3、96次无S2。
96个RAR原UID与120个LRQ原owner长期双占是该接口驱动的结果，不是正常标量生产者的
稳定全池证据。另有预分配CBO违反NoSpec/BlockBack，包字段正确不能豁免。

这属于旧联合驱动遗漏的**整体跨块关系**：S3决定查询撤销/写回，进而改变RAR、RAW、
Replay同时保留的义务；CBO又受真实ROB许可约束。先定义
[容量转移合同](../contracts/lsq-ldu-joint-phases.md)，再新增源正确程序，不降低容量。

## 2. 新程序与真实检查

单代程序序：`16 NC Load + 40 cached Load + 64 Store + 64 cached Load + 64 Store`。
未回包NC保留VLQ头；Store前40个cached没有未来RAW依赖，Store后56个cached保留真实
RAW，另8个容量Replay。SQ头地址缺口保留，第二64物理窗口不提前执行。

| 阶段 | 实际公开历史重建的容量与义务 |
|---|---|
| 第一静稳峰 | SQ128/LQ120/RAR96/RAW56/LRQ24/Uncache16，RAR与原Replay UID不双占 |
| 转移 | 原NC真实响应、grant/bypass/原slot反馈，VLQ释放112；保留128个老Store |
| 第二静稳峰 | 补112个新Load，SQ128/LQ120/LRQ120/RAW56，RAR已回收；ROB活动跨度304<320 |
| 公平服务 | 真实STA/STD当前64窗口、SQ就绪解除、原slot再执行、Sbuffer消费和SQ释放分账 |
| CBO | 完整ROB空时单派CBO0..3，真实退休后才派年轻Load，不在满程序中预分配 |

Load的S0/S1/S2/S3、首次NC/原bypass再执行及revoke遵循新S3源关系。RAW半环128仅使用
已定义的向前Load-exclusive opt-in，公开程序序核对确有128个老Store；共享半环拒绝
不放宽。RAW物理记录slot未公开，只用原查询完整signature，不虚构slot索引。

六个正条件为两payload/稀疏dispatch种子×普通/共享redirect/共同系统reset；各三代，
每例ROB1104、SQ396、LQ708，覆盖完整ROB640/SQ256/LQ240编码。共同reset中止外部job
明确列为abort，不伪造响应；redirect偿还真实旧请求，取消/reset同槽新UID实际完成。

## 3. 普通失败与驱动错误严格分开

| 目录 | 实际结果 | 定位与处理 |
|---|---|---|
| 01 | 6 FAIL / 465源 | 驱动只回原16包，没接收RAR满引起的NC重试新job；最后300拍req.valid而ready0，15原UID欠新义务。保留为驱动失败，非RTL死锁 |
| 02 | 6 FAIL / 466源 | 补持续accept/ack/resp后全部真实bypass s2原数据污染；独立UID审计定位原job，不读known-issues |
| 03 | 4 PASS/8 FAIL / 467源 | 原period1六SID失败不变；额外period8六正条件中两redirect受100拍服务上限停止，实际只回13/16包、仍欠3包，属驱动上限错误 |
| 04 | 6 PASS/6 FAIL / 470源 | 上限按16包×固定节拍计算；六正条件完整三代/CBO，period1原raw/失败主签名与02精确相等 |
| 05 | 21 PASS/6 FAIL / 475源 | 保留原12节点，再按自身DA增加15个正常串行总线补例；六SID反例继续保留 |

period8只是独立固定外部回包节拍，SID仍在resp后立即可分给新job，没有延长到旧Load
消费，也没有用消费状态过滤响应。它用来继续验证失败后的必需容量/CBO关系，不能
替代period1、原八类型随机或把其FAIL抵消。测试中额外clean/唯一PA为明确正条件，
完整随机的错误、别名、split、sticky CBO和SID立即复用均未删。

## 4. 独立证据与可复现入口

```sh
python3 -B tools/run.py --name <新目录> --workers 4 -- tests/sq_endpoint/test_ldu_joint_phases.py tests/lsq_wrapper/test_ldu_joint_serial.py --tb=short
python3 -B tools/capture_end_sources.py <新目录>
python3 -B tools/coverage_audit.py <新目录>
python3 -B tools/audit_lsq_ldu_joint_v3.py lsq-ldu-joint-phases-05
python3 -B tools/audit_lsq_ldu_joint_coverage_v2.py lsq-ldu-joint-phases-05
python3 -B tools/audit_lsq_ldu_joint_negative_v1.py
```

原件：04的[源/UID/池审计](../../results/lsq-ldu-joint-phases-04/ldu-joint-audit-v3.json)、
05的[完整27例独立审计](../../results/lsq-ldu-joint-phases-05/ldu-joint-audit-v3.json)、
05的[原DA](../../results/lsq-ldu-joint-phases-05/line-audit.json)和
[逐行覆盖审计](../../results/lsq-ldu-joint-phases-05/ldu-joint-coverage-audit-v2.json)。
04已独立核验40622条记录、10096 UID＝6630完成＋992取消＋992共同reset＋1482失败保留。
六正条件**6624原UID全部完成、992取消/reset同槽新UID全部完成**；18个LRQ120转移峰、
32个第一峰（含失败/恢复前缀）、2016次真实向前exclusive128查询；72正常CBO/WB、54次
Cache往返和2322实际Sbuffer片段。失败尾部数据失配拍与已checked前缀分别记录，不把
返回信用当完成。05独立审计已实际完成：原12节点与04逐拍原raw相等，再加15例993条
记录、30原UID全部完成、15方向ack/响应、9原Load bypass/slot反馈、3 IO Store实际WB。
合计**41615条记录、10126 UID＝6660完成＋992取消＋992共同reset＋1482失败保留**；
两层统计口径不同但分别守恒，不把失败尾部当完成。不是从04追溯提高05。

五个内存副本负对照拒绝缺revoke、首次Uncache伪更新、虚增VLQ credit、把exclusive128
重绑旧head及CBO提前分配，原raw不改，见[负对照](../../results/lsq-ldu-joint-phases-04/ldu-joint-negative-controls-v1.json)。
旧审计器v1的同指针代际去重、v2离开峰值再验证及错误猜12包的拒绝均保留，v3只修
公开UID代际区分/实际13包元数据，不改任何RTL、刺激、观察值、旧FAIL或容量规则。

## 5. 逐行缺口→补例→真实提升

- 03自身**50902/59602**，剩8700逐行定位；04自身**52999/59602**，新增2097、丢失0。
- 顶层1505/1507/1508定位为既有串行总线情形遗漏，不是新功能。先定义
  [串行补例合同](../contracts/lsq-ldu-joint-serial.md)，再加五类型×三入口：NC/MMIO/IO
  Load与NC/IO Store均真实请求/ack/响应、源S3或WB/SQ完成，再完成年轻cached Load。
- 05自身**53079/59602**，新增**80**、丢失**0**：顶层3、Deq12、LQU42、Replay2、VLQ21；
  本体111→114/114。这是本次原生运行实际分子，不借历史59595或叶子行满。
- 05剩**6523**全逐行保留源/行/上下文/功能：Replay3159、VLQ1540、各FreeList614、
  RAR314、RAW224、LQU291、PSQ260，其余121；既有功能的入口/flow/原因/标签、release/
  冲突、跨页/恢复缺少情形继续补，未动态到达不等于不可达，不删原分母。

## 6. 当前边界与完整目标

27例的coverage schema未自行标记原82总项，当前本目录0/82 checked，避免用定向正
条件代替STRESS总验收；独立合同点的原UID/源/覆盖检查见审计。原六完整混合种子、
SID、RAR前拍release、disabled strict、Forward、CBO/WB/zero等普通失败均保留。
完整随机全域、S4异常分域、其他128歧义与恢复、local-only旧响应及最终层次请求→
证据/缺口/边界审计仍必需，目标active，整体NOT_PASS。

## 7. 本轮请求→实际产物检查清单（非整体目标完成清单）

| 用户要求/合同点 | 用例与真实检查证据 | 结果边界 |
|---|---|---|
| 先定义人可读功能 | JPH-SHARED/AGE/STAGES/TRANSFER/WINDOW/FAIR/CBO/RECOVERY/EPOCH及五种串行类型，合同在开发例前保存 | 不把硬件组合枚举当功能描述 |
| 实际Picker+xreactor及真实下级 | 05的committed manifest、53原RTL/build哈希、475源及27节点日志 | 未改目标RTL，无叶子替身 |
| 跨块容量和原生命周期 | 原12节点函数与六正条件18完整代，32/18两类静稳峰、2016真实128端点、6624原UID完成 | 原period1六个必需FAIL不抵消 |
| 取消/reset与代际 | 六正条件992个原UID均有同物理槽新UID真正完成；redirect旧job真实回包、共同reset显式abort | local-only旧响应另未证明 |
| CBO真实许可与副作用 | 72个原CBO逐NoSpec/BlockBack、QB包、Cache/zero/WB/SQ完成；旧老Sbuffer/WB失败仍在原例 | 不能由包字段独立推断合法ROB流 |
| 逐行缺口分类 | 03/04/05原DA，8700→6603→6523逐行源文本/上下文/功能；整体关系遗漏和已有情形遗漏分开 | 分母59602不删，无假不可达 |
| 补例重跑实际提升 | `test_ldu_joint_serial.py`五类型×三lane全部15 PASS/30原UID完成，新增80行、旧命中0丢失 | 顶层行满不等于82总项验收 |
| 审计器敏感性 | 五个内存副本负对照全部拒绝；S3另八个负对照拒绝 | 非新增native DUT例/RTL FAIL |
| 剩余完整范围 | 原8种子六FAIL、S4异常、其他128/恢复/local-only边界、扩大全范围回归和最终审核 | 目标active，未关闭 |
