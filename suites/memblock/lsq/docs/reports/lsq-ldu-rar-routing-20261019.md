# LDU生产者纠正与正常RAR闭环：18例15 PASS/3 FAIL，整体仍在进行

> 后续S3源审计发现：本03的324次S3默认alignedType0，177次lastBeat错误，六次明确
> Replay伪更新。原18例15/3、路由/身份/DA真实，不追溯改结果，但不足以称完整正常
> 生产者，须按[S3纠正及端点报告](lsq-raw-exclusive-20261019.md)修复重跑。

**本轮成果是定位旧混合超时的生产者循环等待，并实际完成两轮覆盖补例。不是完整随机通过，
不是新RTL死锁，也不是整个LSQ验收。** 所有目标RTL/Chisel、参考模型、knownness和比较掩码未改。

## 1. 旧串行混合的“正常域”只通过了CBO许可，未通过完整LDU合同

这项纠正优先于[先前串行CBO报告](lsq-serialized-cbo-20261019.md)第4节对混合流“合法”的宽泛描述。
NoSpec/BlockBack、QB包门禁本身仍成立；不能把它们提升成整段LDU流水/程序合法。
原8个种子、8个FAIL、原始记录和审计器都保留，未追溯改结果。

独立[生产者审计v3](../../results/lsq-serialized-mixed-01/ldu-rar-producer-audit-v3.json)
仅使用公开dispatch、输入、引脚、pre/post历史和固定开源`NewLoadUnit.scala`：

- 旧流1278次可关联查询/S3，实际查询到所报S3相隔2..7边沿，不是原生下一拍；78次还换了lane。
- 1150次Replay的原查询在原生下一拍没有对应RAR/RAW revoke。
- [v1](../../results/lsq-serialized-mixed-01/ldu-rar-producer-audit-v1.json)另识别1076次
  cached RAR nuke被误作cause11、15次MMIO返回bypass后仍发RAR查询。
- 种子28928的最老**UID97/LQ22**实际1023次RAR查询，其中1021次nuke、1021次C_NK反馈。
  年轻**UID101/LQ26**在tick810查询，tick814以SMF Replay返回而缺少原生tick812撤销；
  tick936再次查询，tick940以原slot32真正正常反馈。同line在tick894..1180有release，
  VLQ头仍22。驱动让老Load等待RAR nuke消失，又让年轻reader等待老Load推进头；
  真实生产者应对RAR nuke产生原ROB的`flushAfter`，不能继续制造C_NK循环。

因此UID97..114这18个未完成者仍真实未完成，但不能把该超时定性成新RTL死锁。
其他混合终点也须在完整正确LDU生产者下重跑；孤立正常串行CBO的实际WB/zero反例
仍由其独立定向证明，不借旧混合前缀扩大生产者合法性。

审计器自己的拒绝也保留：v2说明用的S3列表只按ROB筛选，把tick372的旧UID63/LQ23
误放到UID101的说明里；v3按真实dispatch UID+ROB+LQ重建，拒绝该条，原1150等完整键
流水统计不变。不覆盖v2原件，也不把“同编码ROB”当同一代事务。

## 2. 先补可读功能点，再开发正常定向

[用例前合同](../contracts/lsq-ldu-rar-routing.md)新增/纠正：

- S0 Forward → S1 PA → S2 RAR/RAW → 下一拍同lane S3；Replay同时撤销该原查询。
- RAR violation走原Load ROB `flushAfter`，保留老UID、取消年轻UID；恢复后同物理LQ槽新UID真正完成。
- `C_NK`必须来自同一真实较老Store的STA及重叠PA/mask；Store同时进入真实PSQ/RAW，
  Replay grant不释放slot，原slot反馈和原Store Sbuffer消费/SQ释放分开核对。
- 96个年轻真实读者保留到最老Load完成，满RAR池时最老Load无需新增记录仍可查询，
  全97原Load最终dequeue；三种入口轮换均完成完整程序，不是只计硬件组合命中。

其中**RAR正冲突恢复的旧语义本身错误**，是此前生产者功能关系遗漏/误述，需要独立
合同与用例，不能只当又少一种lane枚举。随后发现的未写RAR记录/入口路径，则是
已有容量/身份功能缺少具体情形，不是又遗漏整类硬件功能。

实现见[正常LDU代理](../../tests/lsq_wrapper/ldu_rar_owners.py)、
[路由/撤销用例](../../tests/lsq_wrapper/test_ldu_rar_routing.py)、
[满池补例](../../tests/lsq_wrapper/test_ldu_rar_capacity.py)。只在这批短小、不跨ROB回绕
的对齐cached程序复用`RecoveryOwners`，不把它的raw ROB排序放大成完整随机代理。

## 3. 三轮实际运行，不借旧覆盖分子

| 独立冻结运行 | 实际结果 | 启动/结束源一致 | RAR本体 | 本批自己的53份闭包DA |
|---|---|---:|---:|---:|
| `lsq-ldu-rar-routing-01` | 15例：12 PASS/3 FAIL | 415 | 2283/3898 | 26902/59602 |
| `lsq-ldu-rar-routing-02` | 16例：13 PASS/3 FAIL | 418 | 2822/3898 | 29161/59602 |
| `lsq-ldu-rar-routing-03` | 18例：15 PASS/3 FAIL | 419 | 3898/3898 | 30237/59602 |

都是实际Picker+xreactor、真实全部下级。结束自动立即捕获SHA，没有skip/xfail。
01→02新增完整96-reader程序；02→03保留原15例、再补三种入口轮换。
[独立实际效应审计](../../results/lsq-ldu-rar-routing-03/ldu-rar-routing-audit-v2.json)
核验前轮全部16个节点到本轮的精确公开记录映射：原15例不变，原满池程序对应rotation0也不变。
参考实现源集合与前轮完全相同，新增功能采样不改变DUT引脚历史。

第三轮**1836条记录，1833条完整周期比较一致**；3条停止样本保留确切失配。
**324原UID = 315完成 + 3取消 + 6失败停留**，不把停止前缀虚构成随后完成。

- 三个满池程序共**291个原Load真正完成**，每个峰值96个RAR公开义务，未读内部slot作答案。
- 三次原RAR `flushAfter`、三组取消同物理LQ槽新UID实际完成，LQ/SQ恢复指针均核对。
- 六次真实Replay grant与六次原slot S3反馈；六次下一拍同lane RAR/RAW revoke。
- 三次cause11均绑定真实较老并发STA，而非RAR响应；三个原Store实际Sbuffer消费并SQ释放。
- 本批仅**9/82 reached、8/82 checked**。`previous_release` reached-only，三个STRESS总项均未checked。
  前两轮0/82是当时实际功能采样结果，不因后续独立审计而追溯填绿。

## 4. 真实FAIL：三lane的前拍release仍漏nuke

三个`previous-*`例均在**tick38**的老Load S2响应停止：实际`nuke=0`、语义期望1。
严格全输出参考已经拒绝，没有给这些停止前缀补老Load S3、恢复或后续新UID完成。
同拍release的三个完整恢复例和无release对照通过，不抵消前拍release的必需FAIL。

这是已知RAR-REL行为在正确LDU时序中的补证，不因RAR本体行满就宣布RAR验收。

## 5. 覆盖缺口逐行分类与补例提升

[覆盖闭环审计](../../results/lsq-ldu-rar-routing-03/ldu-rar-coverage-audit-v1.json)
逐源/行/原文/上下文保存三轮全部缺口与原生DA集合，不合并旧317例或独立叶子分子：

1. 第一轮32700条未命中逐项映射；RAR的1615条都是原ROB/LQ记录从不同入口保存的缺少情形。
2. 增加96-reader正常程序，**新增2259**：RAR539、真实RAR CAM190、FreeList173、VLQ1357；丢失0。
3. RAR还剩1076条其他入口的身份保存分支；三个完整程序轮换后**再新增1076**，全部在RAR；丢失0。

总计自身闭包**新增3335**，原分母59602不变。剩余**29365**条仍逐项保留并映射到已有
总线、Replay、RAW、Store、split、恢复等功能的本子集未运行情形；不是不可达证明。
本体Wrapper109/114剩5条共享bus状态，本批不发外部bus；不能据此删去这些功能。
RAR本体3898/3898也不能代替其前拍release时序失败或完整Wrapper覆盖。

## 6. 可复现命令与未完范围

```sh
python3 -B tools/run.py --name <新的独立目录> --workers 2 -- tests/lsq_wrapper/test_ldu_rar_routing.py tests/lsq_wrapper/test_ldu_rar_capacity.py --tb=short
python3 -B tools/capture_end_sources.py <新的独立目录>
python3 -B tools/coverage_audit.py lsq-ldu-rar-routing-03
python3 -B tools/audit_lsq_ldu_rar_routing_v2.py lsq-ldu-rar-routing-03
python3 -B tools/audit_lsq_ldu_rar_coverage_v1.py lsq-ldu-rar-routing-03
python3 -B tools/audit_lsq_ldu_rar_source_v3.py lsq-serialized-mixed-01
```

回归09仍为独立38DUT/1882范围；本报告写入时没有结束通知，最近实际manifest为running，
不能用门禁预期1691/191当实际结果。本轮只增加09启动时不存在的验证文件，未改它的启动源；
结束后仍须立即捕获、覆盖审计及v10精确基线并集核验。

完整正确LDU全类型随机仍须保持原8种子、八类型/权重、别名/split、SID复用、错误和恢复；
MMIO replay禁止RAR/RAW、NC重新查询/异常、matchInvalid的flush、S4撤销等均不能以本cached
小定向代替。合法联合容量/CBO分阶段、其余RAW等exact128合同、完整恢复/fair同槽义务、
扩大后的统一回归和最终请求→实际产物审计仍必需。目标保持active，整体范围不变。

后续更新：回归09现已实际1882例1691/191并完成v10精确门禁，见[09报告](lsq-progress-regression-09-20261019.md)。
新正确LDU全类型混合为原8种子2PASS/6FAIL；两PASS完成600/fair及全部148取消同槽新UID，
但不替代其余必需失败和联合容量范围，见[新混合报告](lsq-ldu-mixed-20261019.md)。
