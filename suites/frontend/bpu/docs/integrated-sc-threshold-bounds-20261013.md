# 集成SC阈值：整个更新的越界拒绝，不是普通保持

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


本文的64格、255/1964来源和8阶段描述属于已发布的旧检查清单版本。
当前工作树正在改为真实来源关联的事件覆盖，并新增内部/边界混合票抵消义务；
两种分母不能直接比较。见 [硬件事件语义与迁移边界](hardware-event-functional-points-20261013.md)。

起点为已发布的 `production-neutral-ras-correction-20261013-v1`：BPU33129/46541。
集成`rtl/bpu/Sc.sv:1491,1531,1571`缺的是候选阈值不在640..5040时保留**整个旧值**。
net-zero、correct-used保持或把更新钳位到边界，都不等价于这个功能。
way0分支已有原生计数也不能代替有效反馈下的行为证明。

## BPU-INT-070：八个逻辑寄存器/边界上下文

SC有四个独立全局阈值寄存器，不是四个待枚举的SRAM bank。每个只使用一个
硬件bank和一个固定PC自循环，选择两条不同位置但映射到同一全局阈值的分支。
不展开bank×set×地址矩阵。PC由零PHR路径哈希方程得到，三个其他阈值必须始终保持初值1130。

[`输入模型`](../bpu/model/sc/bounds.py) 从范围/初值计算工作量，而不是
写死settle周期：下界先用真实双NT反馈将SC准备为低置信度负向，目标阈值为1132；
上界使用冷态正向SC、阈值1130。进入641/5039的过程，第一笔单票确定奇偶性，
其余笔为两条不同分支的同拍投票。

| 阶段 | 下界预期 | 上界预期 |
| --- | --- | --- |
| 接近边界 | 1132→641 | 1130→5039 |
| 两票整体越界，重复4次 | 641−2=639，保留641而非钳位640 | 5039+2=5041，保留5039而非钳位5040 |
| 向内恢复 | 641→642 | 5039→5038 |
| 含边界合法 | 642→641→640 | 5038→5039→5040 |
| 边界向外单票 | 640保持 | 5040保持 |
| 边界向内单票 | 640→641 | 5040→5039 |

每场景先收集255笔（下界）或1964笔（上界）**不同接受时刻**的真实公开预测，再
集中返回尚未反馈的请求。原metadata不修改、不复制某一次快照代替全部来源；
源码检查来源tick唯一，消费索引一一对应。反馈两条不同conditional均NT，只有
最早失配分支带mispredict；随后向内恢复只反馈一条真实分支。单笔驱动的64提交
容量直接来自现有AsyncDriver，case按容量分块，不展示gather、task或信号边沿。

这里是集成BPU公开反馈端口的延迟反馈契约，**不声称1964笔同时在完整FTQ中合法**。
独立BPU未包含FTQ队列、索引/代次/深度约束；这项范围必须保留，不能偷换成完整
程序验证。IMLI是实际捕获的输入、训练hash会独立推导，但未宣称完整IMLI状态参考。

## 完整检查与有界记录

[`case`](../bpu/case/sc/bounds.py) 复用既有AsyncDriver、FullScMonitor与
FullScChecker，逐周期比较全部四阈值、十个SC SRAM/shadow/PLRU、T0/T1/T2资格和
完整反馈payload。PHR52位/76个fold及真实metadata关联从reset持续比较，CommonHR
GHR/BW状态和SC路由也由独立参考检查。TAGE真实provider身份/计数在反馈期保持。
最终新请求的两份公开SC方向/above/use必须等于reset-derived SRAM计算，非直接
采信实际SC方向；所有dirty、请求及写效果排空后才导出8阶段×4寄存器×2边界的64格。

新增可选`record_limit`只限制诊断窗口，不限制比较次数，不关闭比较，也不将累计
预算变成窗口长度。默认仍完整保留，既有fresh-reset replay不受影响。PHR redirect
接受关联改用实际tick窗口，避免deque淘汰后用旧列表下标找不到事件。
长场景只留64帧内存窗口，最终导出阶段计数/语义summary，不输出逐周期JSON。

## 准备失败与已完成的原型证据

最初候选被驱动的“一笔至多一个mispredict”门禁拒绝，未放宽门禁；随后按最早
失配分支编码。第二次尝试在安装后retarget conditional来形成自循环，MainBTB的
静态conditional目标并未因此改变，候选超时。现由provider-pair准备API的显式
targets参数从最初冷安装就建立正确自循环，默认目标不变；两次失败均保留，不新增XFAIL。

way1的未压缩下界原型1 PASS；优化为双票接近边界后，上下界2 PASS，共221.97秒。
加入最终fresh公开检查、四寄存器完整上下文后，
[`八场景原型`](../results/integrated-sc-bounds-all-contexts-20261013-v1/evidence.json)
8 PASS，190.88秒（8进程）；下界约1195–1202观察周期，上界约6519–6527周期。
公开SC决策全部与参考一致。相关保留/模型/来源契约2573 PASS；新纯契约83项。
相关完整默认/有界兼容检查2931 PASS；随后为长反馈加入既有bounded保护，
并在v2重新资格验证八场景。超时周期是
故障预算，不是每笔必须等待的时间，避免ready故障使新长场景无限等待。

[`首次冻结资格`](../results/integrated-sc-threshold-bounds-qualified-20261013-v1/exit.json)
8 PASS、64/64语义格，1763文件epoch。专用
[`单功能点矩阵差分`](../results/integrated-sc-threshold-bounds-qualified-20261013-v1/functional-line-delta.json)
重新验证8收据/8功能输入，要求所有8个测试精确对应同一个PASS功能点070，不与
其他功能点混合归因。原生新增17键：SC3、TAGE14；17键旧全物理范围也未见。
这份资格随后增加了既有bounded故障保护；
[`最终v2资格`](../results/integrated-sc-threshold-bounds-qualified-20261013-v2/exit.json)
8 PASS、64/64检查清单格。完整
[`生产回归`](../results/production-sc-threshold-bounds-20261013-v1/exit.json)
已退出0并发布：15160 PASS、7既有strict XFAIL、0 SKIP，304功能点297 PASS，
215个功能组203满目标；pytest459.52秒、完整670.94秒，64进程。
BPU33129→33146/46541，精确重现17键，十DUT零旧键回退。

TAGE14个键位于`t2_fire`推进下的候选provider/alternate counter计算；
`Tage.scala:487`整体寄存trainInfoVec，`:576–579`后续才用每entry的valid与
needUpdate选择真正写表。因此原生算术arm命中不等于有效counter写入；高反馈槽
无效时仍可能发生候选计算。本场景不提供这14个arm各自的有效写入资格证明，
不把它们叫14个新增TAGE功能或宣称完整TAGE训练参考。直接闭合的是SC的三个
范围拒绝行与64个checked语义格，原生17与功能结论分开报告。

现有7项strict XFAIL、ITTAGE跨region零置信重写普通FAIL和shadow upper1普通FAIL
均不因本需求通过而被豁免。更广的覆盖率归因与完整验证目标仍开放。
