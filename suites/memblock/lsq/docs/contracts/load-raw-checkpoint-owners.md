# 正常Load的RAW全池元数据：原UID违例、恢复与重执行

先定义本合同，再实现新用例。固定893e1580b开源RTL/Chisel、Picker/X Reactor、
所有冻结参考/actor和全部旧FAIL保持。叶子RAW已有全池checkpoint高低值及唯一
store回读证据，本轮复核该证据，不重复叶子测试；新增重点为真实LQ和Wrapper。

## 1. 从当前缺口到功能点

1457节点after-02的`LoadQueueRAW.sv`，LQ/Wrapper分别仍有6922/4295个toggle缺口，
其中checkpoint相关4574/3930，内部56项checkpoint存储本身3298/2776。不是新的
功能门类，而是RAW-ROLLBACK、LQ-RAW.all_slots、LSQ-RAW.conflict等已有功能点
缺少全宽身份、容量、真实生产者和恢复生命周期的情形。

| 功能点 | 必需行为与真实检查 |
|---|---|
| RAW-OWNER.populate | 一个原本无地址的老普通Store，最多57个年轻Load；前56个经S0/S1/S2/S3实际执行。SQ地址就绪前缀不越过老Store，因此56个已执行Load仍占真实RAW池。不得用私有ID、model.free或统计对象决定刺激。 |
| RAW-OWNER.full | 第57个Load也经过同样真实流水，S2实际RAW ready=0、RAR ready=1，S3为C_RAW(bit10)、updateAddrValid=0且正确revoke；不是伪造full或仅在空闲valid=0时观察ready（源码此时ready恒true）。 |
| RAW-OWNER.original | 老Store只发一次与所选原Load相同的真实STA；每个目标序号0..55分别有独立用例。N+2实际rollback逐字段比较Load ROB/FTQ/RVC/64位checkpoint和原STA身份、MDP训练。 |
| RAW-OWNER.recover | 对实际返回的原Load执行外部ROB flushSelf；已经LSQ本地完成但未架构提交的年轻Load也属于ROB取消后缀。检查真实LQ恢复指针/停顿，Replay中的溢出Load取消，老Store幸存，不能靠reset排空。 |
| RAW-OWNER.retry | 全部被取消的程序后缀以新UID重新派发，原ROBorder可复用，但LQ使用真实恢复尾。源正确S0/S1/S2/S3后实际LQ释放。Wrapper在原同址新Load检查老Store真实转发字节；最后原Store真实Sbuffer消费/出队，不以ROB许可代替完成。 |
| RAW-OWNER.payload | 四个连续池生命周期0/all1/逐原序号图样/互补图样，无中途reset；前两轮强制64位双方向，后两轮区别相邻owner，不让全相同payload掩盖串身份。每个目标用例均实际rollback读回该目标四轮payload。 |

## 2. 正常接口生产者与证据边界

- 每个程序始终只有1个未执行STA的老Store，每次只发射1个Load；最大58条ROB
  程序项（1Store+57Load），不依靠56个未执行Store占据仅32项STA IQ，也不超过
  此处64项发行窗。Load随派发实际执行，不能先把56个未执行Load宣称驻留IQ。
- 每个目标的STA固定使用target%2通道，四轮都由同一通道实际读回0/all1/图样/
  互补，保证该通道payload方向来自已知写入而非启动随机值；56目标覆盖两个
  STA通道。Load lane按序号和轮次轮换，已有叶子双通道选择证据仍独立保留。
- Store地址/数据/ROB/SQ身份不可变；四轮各是不同原Store UID、不同位置。不像
  旧unit-interface RAW探针那样让同ROB Store依次换56个地址。56个目标是参数化
  程序选择，不是一个Store在同一个生命周期改变地址。
- 地址均低canonical、8B对齐、普通cacheable，mask255，源异常0。Wrapper首次
  无地址Store无字节命中；末端新UID同址Load必须真实得到原Store字节。实际
  DCache/上游TLB/ROB不是本DUT，按固定NewLoadUnit输入关系投影，不声称全核
  或Cache读数据返回端口已验证。LQ本身不含Forward/StoreQueue，不借Wrapper结果。
- 声明一个4B非压缩指令流，每4条一个16B FTQ块、offset按半字单位0/2/4/6，
  FTQ指针只在64块处换flag；不为了覆盖翻转而逐条任意改变FTQ flag/RVC。
- 正常命中S2的RAR/RAW dataValid=1；S3 alignedType=3、lastBeat来自原PA，正常
  updateAddrValid=1。溢出C_RAW的S3不完成，最后的重执行不沿用旧replay slot。
- rollback输出三级流水，在原STA接受边沿N后N+2比较；外部redirect使用其完整
  ROB身份，不从私有候选得到答案。所有已定义公开输出仍由原完整参考逐拍检查。
- 56原Load已LSQ释放，并不意味着在老Store前架构提交。取消与本地完成分开
  计数；不把这类已经释放的UID捏造成仍占LQ，不强制恢复到其已释放物理槽。
- 没有公开RAW物理slot号；56项完整分配和逐目标输出是外部所有权证据，native
  dat另证明各物理寄存器位方向。不会声称从隐藏slot读取了刺激或保存了逐拍trace。

## 3. 层次、运行和验收

1. 先复核既有RAW叶子证据、当前1457节点35报告/345原件SHA。
2. LQ→Wrapper各56个目标程序，目标0/55先探测，保留任何实际失败，再跑全目标。
   每一例四轮独立owner；分散参数化而不是把所有目标塞入单个超长case。
3. 每层baseline/after同source/build/点全集，旧选择保留。完整后续仍纳入原八build
   FULL_PATHS全部贡献与192个旧FAIL，预计1457+112=1569节点，以实际collect为准。
4. 比较line/toggle/branch及checkpoint存储/选择/输出的精确源路径、前后集合，
   不以定向命中回填统一regression15，不OR dat，不删任何分母或失败。
5. 旧SID/strict/disabled、头许可、release-wait、跨页/总线、完整核资源历史和最终
   38-DUT统一回归继续开放；本补例不替代它们。性能缓存默认关闭，不让优化
   对照成为原验证行为的隐式变化。默认仅摘要/compact witness/失败/覆盖/命令。

### 完整运行的复用与调度约束（启动前追加）

- 不重跑已完成1457节点基线。实际逐组恢复其全部159份验证库、195份测试文件
  聚合SHA，只排除明确列出的新增helper/plugin/三份测试文件后，两组与原基线
  **精确相等**；旧配置和native build仍核对，不能只凭“好像未改”复用基线。
- 原计划尝试pytest-xdist3.8.0的`--dist=worksteal`，但锁定X Reactor CLI:28..39
  明确禁止转发该参数并固定`--dist=load`。第一次full01在CLI阶段exit2、0.268秒，
  无DUT执行，命令/console/source聚合保留。不得绕过或修改工具库；full02回到
  runner管理的默认调度。不拆分单例、不删节点、不缩短等待预算。
- 新增112例会影响墙钟，不能把与旧运行的耗时差归因于一个未获工具支持的
  调度选项。完整scope仍是原八build FULL_PATHS，不略过历史失败或变更覆盖分母。

### 正常ROB投影的补强（formal02实现前）

固定`RobDeqPtrWrapper.scala:59..96`每次只在CommitWidth=8的一行内前移；
`Rob.scala:1248..1258`将pending及pendingNext分别寄存。首轮formal01直接把
pending从程序头跳至+58，只能保留为接口域UT，**不能验收为正常ROB提交历史**。
raw dat/原59与65 PASS不改，但正常投影主张收回，另列域限制。

formal02在全部重执行Load完成后，按下一8项提交行边界逐拍推进；每次先给出
pendingNext，再下一拍pending跟随，并允许提交停顿。记录每一对推进输入，逐拍
检查delta<=8、不跨提交行、pending等于上一拍pendingNext。声明4B访存uop不做
ROB压缩；这仍是输入投影而非上游ROB原生DUT验收。正常Store消费/empty检查保留。
