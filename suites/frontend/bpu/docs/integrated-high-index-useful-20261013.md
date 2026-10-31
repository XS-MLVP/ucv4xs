# 集成 MicroTAGE 高 index useful：从行缺口到真实学习场景

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


`BPU-UTAGE-023` 已证明模块接口可以分离 index PC 和 tag PC，但这不自动证明
集成 BPU 能通过正常预测、公开 metadata 和真实反馈完成同一操作。
`BPU-INT-066` 补这一层需求，不扫描剩余383个 high index，不把独立 DUT 的结果
重复算入 BPU，也不把 same-PC tag-width 缺陷宣称已经修复。

## 两条不同的 ancestry

输入为 A/B/C/D=`0x40010006/16/80/1e2`，单位均为 halfword Pc.addr。
A 的条件分支 position6 和稍后的 unconditional fallback position10 都到 B；
B→C→D→A 为真实安装的 unconditional 分支。

对稳态 A 请求，lower index 的祖先是较早的 C→D，index PC 为 D、fold6为44，
产生 index462。tag 的祖先是随后 D→A，tag PC 为 A，完整 tag208 可放入8位存储。
正、负两个方向的 upper index 分别为11、266，upper tag分别为125、75；
**266是 index，不是超宽 tag**，不能假定 upper 必然 tag miss。
独立标量52位 PHR、完整 PHR 模型和 fire-based index pipeline 联合检查224步。

## 增长不等于反复发送相同方向

useful 的 increase 需要 provider 正确且 base 错误。只改变 MainBTB 方向时，
base 往往也已学会正确方向：真实候选只触发 allocation/decrease/agreement-hold，
继续等周期不能构造缺失的语义。全部候选普通 FAIL 保留，未改成 XFAIL。

只新增一个返回节点 E=C+32，把 B 临时 retarget 到 E，形成 A→B→E→D→A。
它仍使用同一个完整 ABTB index200，却把 lower index462变为478，同时分离 upper
index。通过真实 backend feedback 修改 B 的目标，不新增 bank/set 矩阵。
运行时还必须资格检查真正的 alias A 请求：完整 index/tag 输入上下文、公开训练
folds、ABTB bankMask/setIdx 和真实 conditional source。纯模型别名推导不能替代它。

工作顺序为：

1. 安装真实分支，反向阶段分配 lower provider，并学习 counter0、保持 useful。
2. 用别名路径将同一 base counter 训练到 taken 饱和，要求原 key 在整个别名窗口
   **没有任何训练**、原 useful 不变。
3. 恢复原 B→C 及真实 C→D checkpoint，正确的 not-taken lower provider 对抗错误
   taken base，实际 useful 1→2。
4. 最后才把真实 MainBTB 方向变为 taken，错误 lower provider 触发 useful 2→1。
   若提前执行这步，upper provider 的分配可能遮挡后续 lower 场景；这不是等待不足。
5. 排空全部已接受任务，再进行全记录 shadow 重放及覆盖导出。

初次 readback 还发现验证端的时间关联错误：状态目标达到前已有旧 A miss 排队。
现在必须消费目标状态之后新接受的、按输入资格筛选的请求，不能把旧 miss 与新状态
比较，也不能按实际 hit/provider 筛选“会通过”的返回。

## 分层和检查边界

[`testcase`](../tests/bpu/testcase/test_high_index_useful.py) 只声明功能点并调用场景。
[`输入模型`](../bpu/model/bypass/high_index.py) 推导程序、容量和别名；
[`environment`](../bpu/env/bypass/sparse.py) 处理 genuine capture、retarget、
redirect 和 drain。warm capture 是 opt-in，原 INT-064/065 的 cold 行为保持默认。
从 C checkpoint 恢复到 D，而不是直接到 A，保留较早的正常 index 请求关系。

[`case`](../bpu/case/bypass/high_index.py) 组织语义阶段，复用既有完整检查器：
PHR、1024 ABTB counter、256 PLRU、两表全部 shadow/status/useful/pointer、独立上游
allocation/update/useful 策略和 SRAM 端口/读回。两个正常 lower 返回比较完整公开
ways/metadata、训练 folds、position10 fallback 和 target B。
这不是完整 ABTB SRAM 写产生参考或整个 BPU 的独立预测参考，也不宣称完整 FTQ 合法性。

[`coverage collector`](../bpu/coverage/bypass/high_index.py) 从真实 reset 重放
两表全部状态。useful 操作属于**已寄存 T1 index**，不能归到当前 T0 read index；
只有下一 rising 观测完整比较通过后才记录角色。最终没有观测到 effect 的 write 不计。
allocation、实际 increase、实际 decrease、agreement-hold 均为必需断言；别名上下文、
原 key 保持、公开返回和完整 drain/replay 合计十项契约，全部通过才导出十个语义 bin。

最终纯契约组合84 PASS（64个 high-index 契约及20个既有 sparse-boundary 契约）。
覆盖完整16种 cold offset 几何、warm C/D 真来源和 redirect 边界、别名输入故障、
registered T1/T0 index 关联、九种晚期观测故障、非法范围、scope误归属和十项缺失契约。
没有内部状态写入、VPI、gather、时钟边沿操作或默认逐周期 JSON。

资格、精确行增量与完整生产发布分别记录；隔离 PASS 不直接替换正式覆盖率。

## 隔离资格与精确增量

[`最终冻结资格`](../results/integrated-high-index-useful-qualified-20261013-v1/exit.json)
实际退出0，1 PASS，完整刷新57.80秒，十项契约10/10；没有替换正式报告。
[`逐键行差分`](../results/integrated-high-index-useful-qualified-20261013-v1/functional-line-delta.json)
相对 RAS-retirement 生产基线新增 **70** 个 BPU 原生键，SF/DA分母仍46541：
AheadBtb21、AheadBtbReplacer30、lower shadow8、upper shadow4、ReplacerState6及其_4实例1。
这些是整条已检查场景的行增量，不能都叫作70个新 useful 功能点。

[`旧物理范围交集`](../results/integrated-high-index-useful-qualified-20261013-v1/legacy-scope-attribution.json)
进一步分离：66键是旧全物理范围曾命中的恢复路径；4键连旧范围也未命中，均为
lower useful 的非分配更新体：index462 的6796/6799、别名 index478 的6828/6831。
两者在本场景均有真实分配和更新，原生行不替代 index462 四种必需角色的独立断言。
其余旧范围损失仍需继续归因，不能自动视为重复的物理 clone。

## 完整生产发布

[`production-integrated-high-index-useful-20261013-v1`](../results/production-integrated-high-index-useful-20261013-v1/exit.json)
实际退出0并发布：14,874 PASS、7既有strict XFAIL、0 SKIP，300功能点全执行
（293 PASS/7 XFAIL），211组中199组完整覆盖。pytest451.41秒、完整刷新664.22秒。
BPU32957→33027/46541，十DUT无旧命中丢失；新增集合精确等于隔离资格的70键。
其余9 DUT不变。旧物理范围仍有7428键当前未命中，另158个旧缺失当前已命中，
不把范围差异隐藏为“零回退”，零回退仅指相同生产范围的基线。

[`发布一致性复核`](../results/production-integrated-high-index-useful-20261013-v1/high-index-increment-audit.json)
重新验证64份worker收据、969份功能输入、相同1736文件epoch、全部原生SF/DA
分母/命中集合、JSON/HTML/canonical LCOV及production索引哈希。全量角色见证
与资格运行完全相同，新组10/10。shadow选择cross仍29/30，独立UTAGE仍9904/11053。
这些一致性检查不冒充独立完整动态审查；formal_current和goal_complete仍为false。

相对上一回归新增64项纯契约及1个DUT case，移除1项已过时的“slot1参数非法”
guard（slot1现在有显式诊断支持，完整场景因dirty冲突普通FAIL）。没有删除任何
旧DUT case，也没有增加XFAIL或SKIP。
