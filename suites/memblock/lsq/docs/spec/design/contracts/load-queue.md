# LoadQueue：五个真实队列的反馈与共享流水合同

状态：**用例前合同；尚未进行本层功能验收。** 本层保留真实
VirtualLoadQueue、LoadQueueRAR、LoadQueueRAW、LoadQueueReplay、LoadQueueUncache
及其全部下级；既有叶子测试/行覆盖不替代组合检查。目标来自开源
`893e1580b705d81f113c30c7a05734e09a08050e`，连接依据
`LoadQueue.scala:229-326`；原始 `LoadQueue.sv` SHA256
`13b06fefd522bc26b7574dcb4186db51548bcc6e0676b7e543f4fa45c6c03e7a`。

## 1. 真实观察和控制边界

- 原SV除clock共622输入、266输出。8路dispatch、3路RAR/RAW查询、3路共享
  LDU S3反馈、2路store地址和2路store数据、4路store唤醒、SQ就绪指针/位图、
  ROB当前/下一head、两memory channel refill/L2 hint、TLB hint、Uncache总线、
  3路bypass和3路replay为实际接口。必须逐个端口核验，不以默认补零掩盖漏适配。
- 本top没有 `ldin.ready`、enq.ready/canAccept/resp、lqFull、lq_rep_full、
  lqDeqPtr、rarValidCount、debugTopDown、TLB delay控制或wakeCancel端口。
  不制造可驱动反馈或可观察寄存器；上游合法容量由独立外部账本约束。
- `VLQ.ldWbPtr → RAR/Replay`、`RAR/RAW.full → Replay`、
  `Uncache.mmioWakeup/ncWakeup → Replay`为真实内部连线。刺激只能改变外部
  业务使其产生，参考根据公开事务历史重建；不得直接poke或读取内部信号作答案。
- 保留的输出包括VLQ消费/恢复/empty、RAR响应、RAW恢复及MDP训练、Replay完整
  payload/allocate/specialMode、Uncache请求/bypass/异常及27路perf。
  无valid payload和DontCare不比较；常量或优化删除字段不算动态覆盖。

## 2. 合法生产者与生命周期

1. 外部UID账本先按程序序分配连续LQ区间（120项、非2幂、8个dispatch入口，
   每uop 0..16 flow），LDU/RAR查询引用仍活动的完整LQ/ROB身份。相同低index的
   新一代不是旧事务；实际 `lqDeq` 和恢复响应才能释放/回退外部区间。
2. 共享 `ldin` 同时送VLQ和Replay，只有 `rep_info.mmioOrNc` 才送Uncache。
   VLQ只有 `!need_rep && updateAddrValid` 才完成，正常反馈不分配新Replay项；
   Replay输出握手只是再次执行，不是完成，必须用公开 `replayQueueIdx` 反馈
   `isLoadReplay/schedIndex` 后释放或更新同一owner。
3. 需要Replay时cause为真实LDU的0..11单hot；cause12含assert，不能当合法普通流量。
   Uncache等待cause、NC/MMIO标签及总线/bypass遵循实际Uncache生产者时序；
   不能重复S3 valid导致重复Uncache分配，也不能把未取得真实总线响应当数据可用。
4. RAR只为LQ head之后的load占记录；内部VLQ head前进应自动回收旧记录。
   RAR release合同继续要求当前/前一拍完整line窗口和已记录hash相交；原release
   时序缺陷作为严格失败保留，不改本层期望迎合RTL。
5. RAW由SQ地址就绪指针决定保留期；store冲突比较字节相交、partial PA和ROB年龄，
   两路恢复和MDP训练应保留load/store各自身份，TLB miss不产生恢复。
6. Replay依赖RAR/RAW容量时必须由真实池满/回收唤醒；依赖Uncache时必须由真实
   bus response后的内部wake唤醒。VLQ head优先选择、SQ地址/数据、hint/refill、
   disabled valid与strict依赖均仍是义务，不以叶子已通过豁免。
7. MMIO需要匹配当前ROB head，NC不被无关ROB head阻塞；SID在resp.fire归还后可
   被新请求复用。旧bypass未消费数据不能因同SID新回包被覆盖。错误保持至消费，
   全16 entry及三bypass通道都须实际数据/错误比较。
8. 一个redirect同时影响五个真实子块；取消年轻后缀、抑制旧输出/分配并完成多拍
   VLQ恢复。已经发出的Uncache仍须接收回包安全清理。取消/reset后复用checked
   必须由同物理槽新UID实际完成证明，不能仅靠有新请求或恢复指针变化。
9. reset时外部事务静默，旧UID记作中止而非完成；reset后新UID仍须完整业务完成。
   正常producer在recoverStall期间不dispatch；同拍dispatch/redirect边界单列，
   不将接口边界自动扩大为真实上游可达或架构缺陷。
10. 公平总线、replay与bypass代理最终允许握手且恰好回一次合法响应。随机测试
    结束应排空外部UID、未反馈Replay、未回总线和bypass数据，不以固定拍数结束。

## 3. 用例前语义目录

功能覆盖区分reached（真实执行进入情形）与checked（所有对应业务/生命周期比较完成）。
以下为本层组合义务，不是简单端口枚举；具体用例会在实现时绑定目录中的情形。

| 组 | 情形 | 人类可读的微架构行为及检查 |
|---|---|---|
| LQ-RESET | initial / active / waiting | 初始空闲；活动/等回包reset中止，无幽灵输出，同槽新UID完成 |
| LQ-ALLOC | sparse / multi_flow / all_lanes / wrap / capacity | 稀疏dispatch压紧、uop多flow、8入口、120项回绕及满池不覆盖 |
| LQ-COMPLETE | prefix / out_of_order / replay_blocks / address_blocks | S3共享输入只在完成条件满足时推进连续完成前缀，年轻完成不越头 |
| LQ-HEAD | rar_release / replay_priority / rollover | 真实VLQ head前进回收RAR并改变Replay头优先，跨120边界身份正确 |
| LQ-RAR | release / previous_release / nc / revoke / all_slots | 真实RAR记录的release冲突、NC预标记、两拍撤销和完整96槽 |
| LQ-RAW | collision / negative / dual_store / train / revoke / all_slots | RAW真实56槽比较、双store恢复及训练精确身份，负对照和撤销 |
| LQ-CAPACITY | rar_block / rar_wake / raw_block / raw_wake / replay_pool | Replay因真实RAR/RAW满阻塞，实际回收才唤醒，120 Replay owner守恒 |
| LQ-REPLAY | causes / feedback / update / backpressure / metadata / banks | 原因/三bank/完整元信息、输出背压、真实反馈更新与完成，不重复释放 |
| LQ-STORE | address / data / strict / disabled | SQ指针/位图、STA/STD唤醒及strict门控；disabled输入不能解除依赖 |
| LQ-HINT | refill / l2 / tlb / fast_tlb | 两channel实际refill/L2、慢/快TLB的标签与延迟正反例 |
| LQ-UNCACHE | nc / mmio / wake / bypass / errors / all_entries / sid_reuse / full | S3进入真实Uncache，经bus回包与内部wake使Replay再执行，bypass消费及错误身份 |
| LQ-RECOVER | partial / all / concurrent / reuse / sent_uncache | 五队列共享取消与多拍恢复，已发总线安全清理，同槽新UID完成 |
| LQ-SPECIAL | threshold / head_change | 真实ROB下一head控制2048边界specialMode，head改变撤销 |
| LQ-CONCURRENT | directed / seeded / fair_drain | 多分支同时活动，共享S3/redirect/hint不串单，固定种子与公平排空 |

## 4. 检查结构与覆盖闭环

- 先核验原样45文件传递闭包、Picker导出/走钟及622/266端口双向codec，再建五块
  公开历史阶段参考；同拍advance必须使用旧状态产生内部反馈，不能顺序调用新状态
  造成参考的零拍捷径。独立外部UID actor不读模型内部状态决定完成/刺激。
- 第一轮先进行跨块定向功能检查，保存全部连续pre/post引脚及预期；分析本体和
  所有真实下级的每条未覆盖DA。逐行区分既有功能缺少情形或遗漏整体功能，先补
  合同/目录，再补用例重跑。保存前后原始分母，六条LQU guarded default需本层
  哈希/结构重新证明，不从别层直接移除分母。
- 父本体很少DA不代表组合语义完成；line满不等于分支/表达式或任意参数穷尽。
  发现的缺陷保留普通FAIL，不skip/xfail、不读问题清单作oracle、不修改目标RTL。
- 每轮独立目录、启动/结束源码SHA、artifact/build哈希、独立公开UID/字节审计；
  所有尚未执行/未checked情形保持未完成。LoadQueue本层不替代LsqWrapper整体。

## 5. 首次运行发现的初始化检查合同纠正

`lq-initial-01`17例均在fixture第一拍pre-edge报ERROR，未进入业务；保留该运行，
不把它计作17个RTL反例。原SV存在resetless历史：VLQ:22220–22234的两拍redirect
历史及第三拍恢复输出；RAR:11884–11886的一拍response valid；LQU:2749/3014等
的一拍s1及两拍s2 valid，还有消费异常报告与父级两拍perf。这些值在首次公开时钟前
没有定义。参考应按具体历史长度建立knownness（RAR/s1/异常1、s2/VLQ消费2、
VLQ恢复3、child perf+父两拍4、RAW恢复汇总最多5），不是用随机初始化值作期望。
只在会话首次时钟建立历史，后续active reset不重开该屏蔽；所有原始pre/post仍保存，
没有skip/xfail，不能借初始化边界放宽业务数据、错误或生命周期检查。

活动reset补例的`lq-recovery-initial-01`中4例先命中参考异步相位遗漏：Replay的
allocated、selection valid及special状态在reset上升时已异步清空，不能等到
下一posedge才期望replayAllocate/valid归零。按原SV异步reset块纠正这些确切输出
的pre-edge期望；不重开首次knownness，不屏蔽reset历史、恢复、数据或业务失败。
旧6 PASS/4 FAIL及279份结束源证据保留，必须冻结重跑确认。

下一轮选中但受背压的reset又暴露父参考遗漏：Replay perf是无reset两级事件历史，
不能随allocated/selection一起清零。保留reset前已进入perf流水的事件并按两级
延迟输出；reset后的新事件为0，不重置任何knownness或屏蔽perf。原阶段结果保留，
 与SID复用的真实异常污染失败分开记录。

## 6. 顶层Uncache背压与entry发送边界

`LoadQueueUncache.scala:447-459`的NC仲裁输出接真实`PipelineRegModule`；该弹性
寄存器没有redirect输入（`PipelineRegModule.sv:46-75,92-97`）。因此entry已向
内部流水握手、但顶层`uncache.req.ready=0`的请求可以在redirect后继续保持valid。
这不同于entry尚未发送的请求立即取消。外部代理必须保持ready公平性，接受原
mid/PA，提供idResp和唯一resp；其旧UID已取消，后续不得留下Replay/bypass义务。
`lq-pool-recovery-01`的23 PASS/1 helper FAIL、285份结束源保持不变：失败是用例
错误要求这条已缓冲请求立刻消失，并未命中逐拍严格参考。纠正后仍逐拍比较全部
已定义输出，再验证稳定请求、唯一回包和真实16entry重填/新UID完成，不跳过时序。
