# BPU 输入/历史 × 输出结果矩阵扩展（2026-11-03）

本轮从 [基线更新](../evidence/runs/baseline-update-a0c2a26cb.md) 的覆盖复核继续，仍固定
`public-a0c2a26cb` / `DefaultConfig`。旧完整42632项和全部非PASS保持原结论，不重标。
本轮不是“再跑一个seed即覆盖闭环”，也不新增框架、改RTL或扩大豁免。

> 后续[2026-11-08实施检查点](../evidence/runs/closeout-20261108.md)逐格保留21gap及承接方。owner迁移和
> INT041/059的观察适配不自动关闭这些交叉；本页v4双seed仍是其原源码/选择的历史证据。

## Skill 要求的四项产物

1. 来源映射：下表及 `coverage/io_matrix.py::SOURCE_FAMILIES/DUT_RESPONSIBILITIES`。
2. 类别×结果域：`coverage/io_matrix.py::MATRIX`，每格有测试绑定或明确 gap/出域及动作。
3. 未分类/未证明：同文件 `UNCLASSIFIED`，不得归并成隐含“其他”。
4. 可执行门禁：`tests/framework/test_bpu_io_matrix.py`，拒绝新类无行、缺结果域、静态PASS、
   空证据及无后续实验的gap；`resolve()`只能从实际逐nodeid判定产生状态，collection不算。

## 指令/事务来源与责任

| 来源族 | 输入事实及合法域 | 本层/承接 |
|---|---|---|
| 条件分支 | BranchUnit输出taken/NT；NT target是顺序后继。本轮使用2字节指令末位置+1半字 | MainBTB payload/方向，MicroTAGE/TAGE/SC方向学习，Bpu历史；指令译码正确性由IFU/后端承接 |
| JAL/直接分支 | 固定目标、none/call提示；不是所有not-taken都可当合法直接分支结果 | 目标预测/属性；本轮不重做直接跳转矩阵 |
| JALR/间接分支 | 动态目标；none/call/return/pop-push提示，源为IFU/后端解码及真实resolve | 目标归MainBTB/ITTAGE，返回归RAS/MicroRAS；合法ISA hint组合不由本轮任意拼装 |
| None纠正 | IFU错误CFI预测仍可canTrain；taken=false用于清除假命中 | MainBTB失效；不得被conditional-NT保护整批吞掉 |
| 预测lookup | guarded半字PC、reset/enable、fire/hold/flush，真实UID/epoch | Bpu及各子DUT原合同；本轮保留不可变原metadata |
| redirect | FTQ原索引checkpoint；真实guarded指令末地址，taken/NT分别恢复 | Bpu/PHR/CommonHR和RAS；guard≠sign样本仅模块端口压力 |
| commit | 原RAS操作和对应原metadata，而非fresh lookup | RAS提交；本轮不把高guard恢复后pop等同后端退休验证 |
| 总线故障/refill/翻译miss | 本DUT无这类返回接口，不制造虚假的error=0测试 | IFU/ICache/MMU；本轮出域，不表示上层已通过 |

十DUT均在机器责任表中。其余七叶模块这轮只登记责任和历史缺口，**没有继承PASS或声称
扩展了它们的全部矩阵**。真实依赖源码仍是固定commit的`BranchUnit.scala:26-29,73-81`、
`ResolveQueue.scala:76-79,142-145`、`PredChecker.scala:179`、`Ftq.scala:387-392`，见旧报告。
类型纠正的完整FTQ/指令历史尚未构造，本轮声明为模块反馈边界，不冒称自修改代码可达。

## 新定向类与独立输出

| 功能点/类 | 输入/历史维度 | 输出和禁止副作用 | 错误规则/残余 |
|---|---|---|---|
| MBTB033 payload | cold NT / warm conditional NT / indirect→conditional NT / None失效 × 两physical align × 首尾位置1/15；有旧payload时再交叉lower/same/upper区域（40个有效语义类，48个保留参数实例） | 独立属性oracle固定期望；target/type/action/taken/counter及独立邻居完整比较；原UID/epoch快照不变；checked需finish完成 | cold没有旧target，8个冗余region实例保留nodeid但不增加bin；去掉NT保护时原warm conditional不能区分，indirect→conditional必须区分 |
| MBTB034 residency | 原第五槽已暴露 × 仍驻留/正常容量压力后淘汰 × 两align（4项） | 不从actual选择目的地；先验证压力确立声明状态，再用**原**metadata反馈；公开唯一身份应在VBTB或Main | 正常16个独立窗口、每窗六条发现使容量周转；同拍snapshot/读竞争与反馈交叉另列gap |
| INT114 recovery | guard × virtual sign × taken/NT × 空/非零历史（16项） | 非零历史由两次真实taken恢复建立；输入边界、独立历史公式、PHR物理cell/fold、新UID、原metadata及drain | 全预测器禁用的端口/历史实验；活跃预测器学习与S2/S3竞争、长期环回绕仍gap |
| RAS018延伸 | guard/sign四组合+回绕（5项），checkpoint→恢复→年轻push→pop | 同一完整返回地址不仅立即可见，还被后续真实返回消费 | 不新增重复功能点；不是commit或PopAndPush修复 |

`mbtb/model/learning_matrix.py`和`bpu/model/redirect_matrix.py`只定义输入-owned事实/性质，
不从DUT选way、SRAM或actual target建立expected。原时序模型仍是`MbtbReference`、
`PipelineReference`和PHR独立模型；没有另建predictor模拟器。

### 矩阵发现的模型资格遗漏，而非直接宣称12个硬件缺陷

首轮原生 NT 类型纠正的12个实例在counter/taken处失败：模型期望2/1，实际1/0，
type/target并未在同次原始比较中出现差异。沿独立producer再核对：

- `BranchUnit.scala:73-81`的执行resolve明确给出`attribute=Conditional`和真实taken；
  原预测attribute不是指令译码的真值。相同raw-hit身份的明确纠正不能仅因旧预测为indirect
  就被方向学习排除。方向更新与payload改型是两个不同承诺。
- 新性质答案为：同一raw-hit位置、初始counter2，实际conditional NT明确纠正后counter应为1；
  原indirect type/target仍保持；邻居不变。它来自执行结果+饱和方向计数，不从actual重命名owner。
- 旧`test_nonconditional_source_cannot_learn_conditional_direction_without_correction`保留原nodeid
  和期望2；foreign-tag/raw-miss、不同位置和非conditional结果仍不得凭空授予方向资格。

外部同一`test_authoritative_conditional_red.py`修前1FAIL/1PASS、修后2PASS。生产模型只新增
`conditional_direction_update`，区分“原conditional”与“原非conditional但被明确纠正”两类，
继续要求原rawHit和同位置。配对测试冻结旧规则确认新类能拒绝它；不修改缺rawHit污染、
retained-owner、RAS等历史oracle或豁免。原12个FAIL运行仍保留，后续新源码必须单独复验。

### 地址准备的合法域修正

首轮sign=1的8项未到目标场景：将虚拟高地址直接当`resetVector`，该输入实际是物理
`PrunedAddr(PAddrBits)`（`Bpu.scala:52,142`），发生截断而非guard功能反例。第二版改为
低物理地址启动，再通过真实redirect建立高virtual-sign来源；bootstrap低位哈希独立为0，
保持empty历史类不变。nonzero类再用两次真实恢复建立，最终接受数分别2/4。
guard≠sign、以及用于该边界的bootstrap仍仅端口级压力，不借此声称完整FTQ生产可达。
首轮失败不重标，未放宽pipeline目标/reset模型域或修改RTL。

## reached / checked / 错误响应

MBTB的reached在正常训练实际接受且原有driver/monitor来源对账成功后记录；checked在
公开response属性、邻居/目的地、原metadata和有界finish之后记录。Bpu恢复reached在
redirect返回实际接受后记录，checked须真实新消费者、边界比较和两个checker收尾完成。
覆盖组逐case记录，失败时finally仍导出真实部分覆盖，不把fixture启动或参数枚举计为checked。
RAS完整地址后继消费亦有独立的5类reached/checked组，`MATRIX`中有对应行；不只读立即top。
Cold NT的3个region参数不改变输入，不能当成3种语义。新增`coverage_label`将其合并到
`no-original-target`类；保留先前collection的全部nodeid，机器自检强制48参数只有40个
payload语义bin。连同residency4、guard16、RAS5，本轮为**65个不同语义类、73个功能实例**，
不因8个冗余参数增加覆盖信用。

合法输入下的错误响应控制单独置于scoreboard/selftest。输入wire故障、响应观测故障、
纯错误模型规则与RTL mutation分开，不将前两者当作学习规则完整检错证明。本轮不改RTL。

## 执行与剩余

实际回归和证据在完成后追加；源码每次运行内冻结，输出使用新目录，真实FAIL/ERROR保留。
整体矩阵的空白不靠新增用例数关闭：pending-full/read/reset/disable交叉、活跃顶层学习、
guarded target全域、旧SC角色矩阵及缺失内部观察点仍需单独实验。
本轮guard矩阵核对CommonHR恢复输入的49位投影，**没有据此关闭CommonHR内部GHR/BW
状态及旧conditional-prefix反例**；独立物理cell/fold信用属于PHR。指令长度本轮固定压缩
2字节、RAS hint固定none的MainBTB新矩阵也不等于全部长度×hint组合或跨页历史已展开。

### 已保留的中间运行（不是最终结果替代品）

- `results/bpu-io-matrix-probe-v1-20261103`：150 PASS / 20 FAIL，含73原生实例；97纯检查PASS。
  十二项为NT类型资格模型遗漏，八项为高virtual-sign错误物理reset准备。source前后稳定，
  标准构建/manifest/覆盖产物/processor和进程隔离完整性已审计，FAIL未重标。
- `results/bpu-io-matrix-seed1-v2-20261103`：1067 PASS / 12 FAIL，133原生实例；高地址准备
  修后顶层54 PASS，Ras12 PASS，模型资格尚未修。证据脚本首尝试错误要求pure域有HTML，
  已保留异常；只修外部分析脚本（pure无覆盖组时本来不产HTML）后完成原产物审计。
  该脚本异常阻止了当时排队seed2启动，不谎称该版已双seed。
- `results/bpu-io-matrix-seed{1,2}-v3-20261103`：资格修后同源码同选择双seed各
  1154 PASS / 14 FAIL / 1 XFAIL；含旧15反例、原834敏感链和全部新增171节点。
  73功能实例PASS，但cold参数冗余尚未从bin去重，故后续v4单独冻结复验最终语义口径。
- 外部纯诊断`pure-v3.log`的2FAIL/154PASS包含一个定向fault把已为0的方向再次写0（未真正
  注错），以及旧自检依赖suite cwd却从仓库根调用。修正fault为翻转、改回suite入口后的
  `pure-v4.log`为156PASS，未改旧自检的断言/适用范围，未借此签核硬件。
