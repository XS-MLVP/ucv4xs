# BPU 输入合法性与 SoC 可达性

模块能够接受某组引脚值，不代表 SoC 会产生它们；模块在这组值下丢更新，也不自动证明正常软件会触发缺陷。本页记录生产者的实际约束，供各问题报告共同引用。

本文检查了前端 BPU、IFU、FTQ，以及后端指令分类、提交和 CSR 控制。补充运行的是现有完整 BPU DUT，不是包含 IFU、FTQ、后端与 CSR 执行的整核仿真。

## 先分清三种训练和控制来源

| 接口 | 真实生产者 | 不能擅自假定的内容 |
|---|---|---|
| MicroBTB、AheadBTB、MicroTAGE 的 fastTrain | BPU 的 S3 最终预测 | 不是任意执行结果；PC、分支、元数据必须来自同一流水实例 |
| MainBTB、TAGE、SC、ITTAGE 等的 train | FTQ 保存的预测元数据，加 IFU／后端送来的分支结果 | 不能给已经被重定向杀掉的年轻原预测继续训练 |
| RAS 推测／纠正／提交 | BPU S3／FTQ redirect／后端提交队列 | 组合操作编码、预测生命周期及提交年龄必须一致 |

MicroBTB 还会接受真实执行误预测纠正，优先级高于 fastTrain。不能因为同一组分支字段可以来自执行纠正，就认定把它放到 fastTrain 上也合法。

来源：[Bpu.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bpu.scala)、[FastTrain／Train 定义](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bundles.scala)、[MicroBtb.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/ubtb/MicroBtb.scala)。

## 已确认的上游约束

### 不跳转 fastTrain 不是“一条条件分支实际不跳”

BPU S3 没有选出跳转分支时，选择 FallThroughPredictor 的完整结果，再生成 fastTrain：

- `taken=0`。
- `attribute=BranchAttribute.None`，不是保留原条件分支类型。
- position 是取指块／页边界的结束位置。
- target 是顺序取指地址，不是该条件分支的跳转目标。

因此 08 原用例把 `taken=0` 与旧条件分支类型、旧位置、变化后的分支目标同时送到 fastTrain，这个组合违反真实生产者约束。

依据：[Bpu.scala 的 S3 选择及 fastTrain 连接](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bpu.scala)、[FallThroughPredictor.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/FallThroughPredictor.scala)。

### MicroTAGE 不能拿任意 ABTB 向量和历史训练

预测元数据只将 ABTB 的条件分支标为可训练，并排除重定向后的特定窗口。BPU 随后按 S1 选择的首跳位置裁剪元数据，首跳之后的槽不再有效。

fastTrain 使用随同该预测流过 S2、S3 的元数据。单元测试直接给定历史和完整向量，还不足以证明这个历史序列及有效掩码能由真实 PHR、ABTB、S1 选择共同生成。

这不意味着 02 的“同位置被晚阶段纠正成非条件跳转”必然非法：ABTB 与 MainBTB 可以不一致，同位置不会被“首跳之后”的裁剪自动清除。但仍要用真实 S3 生成来证明具体复现序列。

依据：[MicroTage.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/MicroTage.scala)、[Bpu.scala 的 s2_realUtageMeta](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bpu.scala)。

### FTQ 不是任意元数据回放器

FTQ 会屏蔽同一次训练中首个误预测之后的分支。ResolveQueue 还会过滤后端正确的直接跳转和纯返回，并按重定向年龄过滤已经失效的年轻反馈；FTQ 的训练缓存也处理同类清除。

因此：

- 真实保存过的元数据，不等于现在仍可用于训练。
- 较老分支误预测后，不能继续回放被它杀掉的年轻原预测。
- 自己给 BPU 送了 mispredict 训练，却省略对应重定向和 FTQ 年龄处理，不能算完整 SoC 见证。
- 乱序执行可能允许年轻反馈先训练、较老反馈随后到达；不能据某个准备顺序非法就断言所有重复记录都不可达。

06 的现有集成准备先保存多个冷原预测，再顺序训练；它没有把真实 FTQ 的上述约束完整纳入。因此“完整 BPU 测试失败”仍不等于“完整 SoC 可达”。

依据：[ResolveQueue.scala](../../XiangShan/src/main/scala/xiangshan/frontend/ftq/ResolveQueue.scala)、[Ftq.scala 的 trainCache 和 trainFirstMispredictMask](../../XiangShan/src/main/scala/xiangshan/frontend/ftq/Ftq.scala)、[当前清理场景准备代码](../../bpu/env/main_duplicate_cleanup.py)、[teach／send_input](../../bpu/env/bounded_sources.py)。

### 禁用 RAS 不会让 BPU 停止产生调用输入

`RAS_ENABLE` 是软件可写 CSR 字段。BPU 用它控制 RAS、MicroRAS 的 enable，但没有用它禁止 MainBTB 预测调用，也没有在 `ras.specIn.valid := s3_fire` 外再加同一个 enable。

MicroRAS 的 S1 返回目标消费者检查了“是返回且目标可用”，没有额外检查 rasEnable。因此不能用“父模块已经过滤”排除 04、05。

依据：[SbpctlBundle](../../XiangShan/src/main/scala/xiangshan/backend/fu/NewCSR/CSRCustom.scala)、[CSR 输出](../../XiangShan/src/main/scala/xiangshan/backend/fu/NewCSR/NewCSR.scala)、[Frontend 连接](../../XiangShan/src/main/scala/xiangshan/frontend/Frontend.scala)、[Bpu.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bpu.scala)。

### 返回并调用是真实指令能产生的操作

例如 `jalr x1, 0(x5)`，目的寄存器和源寄存器都是链接寄存器且不同。IFU 的 BranchAttribute.decode 会产生 `PopAndPush=3`。

后端将它识别为 `CoRoutineSwap`，isPush、isPop 均为真；CtrlBlock 把两位送到 callRetCommit，CommitQueue 只排除 None，不会把编码 3 过滤掉。因此 10 不是一个仅因枚举里存在、真实软件却产生不了的编码。

依据：[BranchAttribute.decode](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bundles.scala)、[PreDecode.scala](../../XiangShan/src/main/scala/xiangshan/frontend/ifu/PreDecode.scala)、[Itype.jumpTypeGen](../../XiangShan/src/main/scala/xiangshan/backend/trace/Interface.scala)、[CtrlBlock.scala](../../XiangShan/src/main/scala/xiangshan/backend/CtrlBlock.scala)、[CommitQueue.scala](../../XiangShan/src/main/scala/xiangshan/frontend/ftq/CommitQueue.scala)。

## 本次补充的动态见证

通过现有 BpuAgent 操作 BPU 顶层接口，用真实输出元数据训练一个自循环调用，并发送对应的重定向；然后让 BPU 自然选择预测、生成 fastTrain 和 RAS 输入。没有直接驱动子模块端口、S3 fire 或内部状态。

见证使用现有 `dut/bpu` 包，生成 RTL 的 SHA-256 前 12 位为 `0543aa17dc07`，完整身份见 [build-provenance.json](../../dut/bpu/build-provenance.json)。采样到 20 个有效 S3 事件：

| 观察 | 结果 |
|---|---|
| 不跳转的 fastTrain | kind=0、position=15，target 为顺序地址；未出现不跳转且 kind 非零 |
| RAS enable=0 时的自然调用 | specIn.valid=1、rasAction=2，确认父模块没有屏蔽调用 |
| 同一关闭状态下的 MicroRAS 输出 | isCanUse=1，确认可用标志问题也存在于完整 BPU |

这证明的是 BPU 集成边界；没有执行整核 CSR 指令流，也没有证明一次具体 RET 已跳到错误目标。

另将 08 的字段改为当前配置的真实 fall-through 形式：`taken=0, kind=0, position=15, target=PC+32字节`。连续训练后仍观察到有效预测，但这只是**合法字段形态**，并未证明这组连续同 PC 事件能经真实 S3、重定向及执行纠正仲裁自然产生，不能据此升级为 SoC 复现。

## 各报告的输入审核结论

| 报告 | 合法性／可达性结论 | 尚缺什么 |
|---|---|---|
| 01 | FTQ 没有按 MainBTB rawHit 过滤漏预测条件分支的反馈；这种输入形态允许 | 尚未执行包含 FTQ 的整核反例 |
| 02 | 晚阶段同位置属性纠正未被现有裁剪自动排除 | 真实 ABTB、PHR、S3 共同生成的完整反例 |
| 03 | 丢更新机理已见；直接指定历史和反馈顺序不是 SoC 可达证明 | 真实 PHR 与 S3 流产生相同槽复用冲突 |
| 04 | BPU 已实际产生禁用期间的调用输入，CSR 也允许该配置 | 整核程序级影响；禁用期间更新策略仍应由接口约定明确 |
| 05 | 完整 BPU 已见禁用期间可用标志为 1，上游消费者没有补充 enable 门控 | 真实 RET 消费并造成错误预测的见证 |
| 06 | 错 way 写回已见，但旧／年轻原预测的 FTQ 生命周期未闭环 | 包含真实重定向年龄处理的准备和复现 |
| 07 | 未找到“启用切换必清空所有旧训练”的保证，不能直接判输入非法 | CSR、FTQ 时序见证，以及允许训练还是应忽略的设计约定 |
| 08 | 原 fastTrain 字段组合不合法；合法字段变体仍有模块差异 | 能自然产生连续事件的真实 fastTrain／resolve 序列 |
| 09 | 缓冲误合并已见，单元测试未证明两份更新的真实 S3 来源及 flush／history 时序 | 两个独立真实预测实例生成的纠正流及持续同 bank 读压力 |
| 10 | 合法指令能产生，IFU、后端、FTQ 提交路径均保留该编码 | 整核运行反例；部分单元“提交属性纠正”准备仍不能代替真实提交 |

07 的 CSR 审核也不能简单假设“写控制 CSR 一定全流水线刷新”：NewCSR 的 flushPipe 条件没有为 SBPCTL 列出专用刷新，FTQ 也没有按这个 CSR 建立预测 epoch。其他通用序列化行为仍需纳入整核时序验证。

## 判定边界

“未证明可达”不等于“已证明不可达”；“合法字段”也不等于“合法的整条事件序列”。

当前不更改原 pytest FAIL/XFAIL，也不修改 RTL 或把模型改成追随 DUT。后续应为高层功能点补上生产者约束和原预测生命周期检查，把无约束模块压力测试与正常 SoC 行为验证分开计入报告。
