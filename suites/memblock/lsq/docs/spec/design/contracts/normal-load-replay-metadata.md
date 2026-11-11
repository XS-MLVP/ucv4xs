# 正常标量Load的Replay地址、指令语义与外部依赖身份

本合同先于新增helper/用例。固定开源`893e1580b`原样RTL/Chisel、Picker真实DUT、
X Reactor原完整参考与全部历史FAIL不改。上轮43报告/670原件已核验，不重复RAW
1569节点或叶子全池checkpoint测试。本轮不是所有Load类别的替代验收。

## 1. 从实际缺口到已有功能点的缺失情形

最新完整`load-raw-owners-contributor-regression-02`的`LoadQueueReplay.sv`，
LQ/Wrapper余20447/11577个toggle；vaddr5141/3586、fuOpType1351/1073、MSHR
933/814、TLB hint718/757。补充LRQ/LQ/LSQ既有PAYLOAD、HINT、REPLAY功能点的
**正常标量、全公开slot生命周期与非匹配生产者**组合；不是把任意全宽bits
当作合法指令。600个注册exception位的有效写后恒0有独立精确源证明，仍保留
分母和未命中，不用源异常加普通replay原因刷这些位。

| 功能点 | 实际行为与必需检查 |
|---|---|
| NORMAL-REPLAY.identity | 每条原Load只有一个外部UID和不可变VA、opcode、ROB/LQ/SQ、FTQ、目的寄存器及checkpoint。实际公开Replay逐字段核对，不从model slot或隐藏寄存器决定反馈。 |
| NORMAL-REPLAY.scalar | LB/LBU/LH/LHU/LW/LWU/LD的opcode分别0/16/2/18/4/20/6，size来自opcode[3:1]，mask为真实16B bank中对应字节。alignedType、PA lastBeat与原访问一致，rfWen=1，FP/vector/v0=0。不驱动Q或非法all-ones opcode。 |
| NORMAL-REPLAY.address | 8轮完整slot生命周期，先VA=0、再负canonical最高字节地址，再合法正/负互补图样和不同size/offset，最后回0；VA50从Sv48规范地址低位截取，首次fullva为64位canonical，PA保留页内偏移。每轮120个**顺序完成**Load，实际公开slot集合必须0..119，无reset。 |
| NORMAL-REPLAY.cache | 普通C_DM且handledByMSHR=1、dataValid=0，错误MSHR的refill/L2 hint不能使当前Load出现Replay；匹配生产者才放行。refill覆盖两个channel；L2覆盖keyword与真实PA bit6决定的先/后beat边沿。 |
| NORMAL-REPLAY.translation | C_TM来自首次TLB miss，tlb_full=0、special=0。先发不同活跃filter ID的fast/slow hint，等待后原Load仍阻塞；匹配fast或slow ID后才出现原UID。无replay_all替代ID匹配。 |
| NORMAL-REPLAY.hold | 正确唤醒后消费者持续背压3拍，同一公开slot及全部已定义payload不变。实际ready握手后仍有Replay占用，不能把发出当作完成。 |
| NORMAL-REPLAY.finish | 父级首次S3为单一C_DM/C_TM、updateAddrValid=0并同lane revoke；重放握手与原bank LDU的S0同拍，接S1/S2/S3，S3原slot反馈cause0/update1，实际LQ连续前缀释放后才完成。叶子只声明真实Replay feedback释放，不借父级VLQ完成。 |

## 2. 合法生产者投影及范围

- 4种独立路径：`refill`、`l2`、`tlb-fast`、`tlb-slow`。每层每路径8轮×120
  原UID=960条。每轮都必须观察到全部120公开slot；顺序完成不声称同时满池，
  也不预派发120条未执行Load使其假驻留IQ。最大1个活动LSQ/ROB Load、无Store。
- 外部DCache/PTW不是DUT。声明16项MSHR及16项load filter的有界身份域；每事务
  台账绑定当前原Load和另一不同地址/VPN的活跃decoy外部请求。先使decoy回应，
  核验当前Load仍阻塞，再使current回应。当前与decoy绝不占同ID，响应来自其
  声明的活跃身份，不把垃圾/未分配ID当作“真实生产者”。每例仅两项活跃，
  总量不超16，但**不声称验证了上游native分配器如何选择这些ID**。
- profile0/1/7分别将当前依赖ID设0/15/0，已知写入后双方向；中间轮按原序号
  轮换0..15，通道交替。Cache数据本身没有在这些LSQ端口返回，不伪造Cache
  数据值已验证；Wrapper SQ为空时核对Forward valid、mask0和无错误。
- Sv48首次canonical地址的50位投影必须满足bits49:48等于bit47；高负地址不是
  非canonical全宽灌数。4K物理映射保留VA[11:0]，读均自然对齐、不跨16B bank，
  不把翻译故障/不对齐/跨页混成普通Cache命中。本轮最终重执行无异常。
- 固定LRQ源码公开`fullva := replay_req_vaddr`，仅零扩展已存VA50，**不能宣称
  其64位fullva等于首次负地址canonical fullva**。实际Replay输出按源检查零扩展，
  正常Replay不做first-issue fullva检查；重执行S3 fullva按重放TLB响应投影，
  与首次fullva分开记录。上游TLB全64位canonical检查本身不在本DUT验收内。
- 首次cache miss的S2 RAW/RAR dataValid=0；TLB miss允许源码所述粗查询：选择
  DCache early miss=0/bankConflict=0、fullForward=0，因此dataValid=1，随后S3
  cause C_TM且准确revoke。Wrapper首次TLB miss在S1驱动真实Forward s1Kill=1，
  不要求被kill的Forward产生valid。重执行TLB成功、DCache hit的dataValid=1。
- 外部ROB只在实际本地完成后逐条提交；pendingNext提前一拍，下一拍pending跟随，
  不跨8项提交行。ROB/LQ回绕均按实际160/120，
  不从DUT输出抄入预期身份。中途无reset、无redirect捷径、无削弱参考比较。

## 3. 时序、层次及证据

1. 层次Replay叶子→真实LQ→真实Wrapper；用三层真实fixture保留完整参考。先每层
   每路径小探测，再四路径完整960UID。probe失败原样保留，不把局部PASS替代层次。
2. 匹配pulse边沿N后的首次公开valid：fast TLB为N，慢TLB/refill为N+2，L2 first
   beat为N+1、last beat为N+2。实际tick每周期+2；从源码独立推导并与原参考双检，
   不因出现差异放宽检查。消耗前3拍背压、完成前至少一拍检查占用保留。
3. 每层fresh baseline/after同build/source/三类点全集，旧选择保留；保存精确路径
   vaddr/opcode/MSHR/TLB存储和public输出前后集合、known-write功能witness，不OR。
4. 完整整合仍保留八build全部既有贡献、192 FAIL及Replay原贡献与真实失败；需
   单独核对新增Replay build完整范围，不能只给绿色定向子集就声称9build验收。
   完整当前基线1569不重跑；若要新增旧Replay贡献，先audit全部实际节点映射。
5. 默认摘要、compact原UID witness、命令、失败、native dat/LCOV；无逐拍JSON、
   波形、新完整源码副本，性能缓存关闭。任何上游源/参数证明或时序发现均保留。

## 4. 不由本轮关闭的义务

FP/vector/hypervisor/跨页/异常、SID复用、strict与disabled反馈、真正同时满池、
取消/replay cause迁移、混合排空、头许可、release-wait、完整核资源历史和全部
38-DUT扩展回归继续开放。每个点的配置/工具/有效写后不变边界仍要精确证据；
本合同限定一次补例输入域，不缩小整体LSQ目标或删任何原功能/分母。

## 5. 实际贡献者与Frontend投影更正（formal02前）

完整Replay旧贡献者实际181节点：统一回归179（含主目录外48 endpoint）之外，
还需两条既有全宽元数据/全池checkpoint PASS用例。首次审计因预计180而exit1，
原日志SHA保留，181节点实际177PASS/4原FAIL不重跑；未来完整9build基线集合
1569+181=1750，after预计1762，1566PASS/196FAIL，以实际运行核对。

第一次12/12 probe及三层19/16/13 PASS真实保留，但其新helper沿用了16B块与
offset0/2/4/6投影，不能据此验收本合同的直线4B前端历史。固定
`FrontendParameters.scala:28`块64B，`InstrCompact.scala:53..65`对非压缩指令取
第二半字offset，`ibuffer/Bundles.scala:152..162`直接令ftqOffset=instrEndOffset。

formal02声明从64B块边界开始的4B直线Load程序：每16条一个FTQ，pointer由
ordinal//16产生，offset=2*(ordinal%16)+1，即结束半字1/3/.../31。新增compact
witness保存FTQ flag/value/end-offset并逐UID独立审计；无擅自随机翻转。仅改
本轮新helper，冻结旧RAW/模型/actor/测试不动。原01报告须显式保留FTQ投影限制；
必要新02三层fresh before/after核对不冒称是中断重试或抹去原功能结果。
