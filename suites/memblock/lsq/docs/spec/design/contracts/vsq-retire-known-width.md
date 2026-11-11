# 已知退休批宽：64flow与后续小批的真实父级下降过渡

先定义本合同，再新增用例。承接1177节点，不重做4..128取消或已有32flow叶子用例。
原始RTL/Chisel、Picker native build、X Reactor、共享参考与actor均保持。

## 功能点和缺失情形

| 层次/既有功能点 | 本轮缺失情形及人类可读行为 |
|---|---|
| VSQ `VSQ-RETIRE.batch_width` | 八个真实uop各含8flow，等到合法ROB退休边界前进后，同批累计64个物理flow；其后小批正常退休必须清除旧的大批高位，不把128虚拟项或启动随机值当成64flow见证。 |
| SQ `SQ-DISPATCH.multi` / `SQ-PERMIT.retired` / `SQ-RETIRE.buffered` | 八个多flow uop的全部64个物理Store先真实STA/STD就绪，ROB头未到且Sbuffer背压时不得消费；ROB以至多八个Store uop的边界前进后，所有原始字节真实输出、消费并正常出队；随后16flow→1flow批次不得残留旧宽度。 |
| Wrapper `LSQ-ALLOC.multi_flow` / `LSQ-RETIRE.multi_flow` / `LSQ-FORWARD.aligned` | 在真实LoadQueue、VSQ、PSQ和Forward连接下执行同样的64/16/1flow退休；每批派发的Load在原Store查得PA有效字节并完成原S3，Store完整消费。不能用单flow Store冒称一个8flow uop，也不能只验证内部计数而不完成Load/Store生命周期。 |

## 外部合法生产者和时序

- 各层固定四批：**1uop×1flow预热 → 8uop×8flow → 8uop×2flow → 1uop×1flow**。
  总18虚拟Store uop、82物理flow；每批物理占用至多64，单uop不超过16flow。
  前一批已正常完成才分配下一批，不用reset、取消、内部写入或非法17..31flow。
- 1flow预热是一次已知退休写入；随后的64/16/1flow过渡来自真实正常退休，
  不依赖`retireReqNumReg`未复位的初值。高位bit8..10的启动缺口不豁免。
- Leaf外部producer自己维护UID、ROB、虚拟位置与physical end，逐拍参考只做
  比较，不作为激励决策来源。真实公开retiredPtr只允许每批0→完整批宽的单次
  物理增量；公开退休完成后，外部PSQ代理每拍至多消费2flow。
- SQ/Wrapper执行期间ROB头保持在本批首Store之前；S2均完成并稳定后才给
  正常退休边界，所有原Store UID在许可前消费片段为零。SQ前进至多8个Store
  uop；Wrapper批内Load占下一个ROB位置，Store退休边界只前进至该Load，
  不为刷覆盖人为跳过9个活跃ROB项。下一批开始时再越过已完成的旧Load。
- SQ用共享StoreActor逐flow原始PA/mask/字节、Sbuffer实际fire和延迟出队检查。
  Wrapper用共享MemoryOwners按同一ROB连续8/2flow分组派发，原Load在本批
  最后一个Store实际取字节并走原S3；每批正常完成后再推进，不改真实下级连接。

## 证据、覆盖和不覆盖范围

每层新增一节点，fresh baseline/after同source aggregate、build与三类点全集，
保留旧节点/主检查摘要/旧命中。目标是VSQ retireReqNumReg[6]双方向、SQ[4]
下降、Wrapper[6]下降；也列出完整位6/4方向和其他实际新增，不预设覆盖增益。
父级没有公开单独retireReqNumReg读口；测试只检查公开行为，实际内部方向以原生
coverage.dat证明，不把推测批宽或叶子覆盖当作父级已命中。

完整六build贡献范围必须从原1177节点加3新增节点，预计1180，实际collect/
manifest核验。保留原172FAIL全文（含头preCommit/flushSelf旧UID315失败）和
Wrapper主目录外41贡献者；新用例有真实失败也必须留下，不skip/xfail、不屏蔽。

只保留compact各批UID/原Load完成/公开尾与完成摘要、失败及原生覆盖。统一
regression15不回填；不OR旧dat冒充新运行。头许可取消上游合法性、128虚拟uop
真实父级域、15850 release-wait、未复位高位初值及异常/总线/跨页Load仍开放。
