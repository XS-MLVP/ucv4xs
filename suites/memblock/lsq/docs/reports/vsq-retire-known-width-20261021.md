# 已知64flow退休批宽：三层补例、完整1180节点和原172失败保持

**整体仍为 `ACTIVE_NOT_ACCEPTED`。** 完整六-build fresh运行结果为
**1180节点：1008 PASS / 172 FAIL，0 ERROR/SKIP**，实际2606.52秒。
原1177节点结果与172份失败全文保持，新增三节点均PASS。

## 1. 功能点先于用例，父级保留真实下级

[已知退休批宽合同](../contracts/vsq-retire-known-width.md)先定义1flow预热、
64flow大批、16flow和1flow后续小批的微架构语义，再新增三层用例：

- `tests/vsq/test_retire_known_width.py`：外部producer管理独立UID/ROB/end，
  不读取参考模型或内部计数作控制。1×1→8×8→8×2→1×1四批公开retiredPtr
  依次为0→1→65→81→82，每批只有一次完整物理尾增量；正常退休后才由外部
  PSQ代理每拍最多消费2flow。实际18虚拟Store uop、82flow正常完成。
- `tests/store_queue/test_retire_known_width.py`：真实VSQ/PSQ保持连接，八个
  多flow uop全部STA/STD及S2完成前不给ROB越头许可；Sbuffer背压时没有任何
  提前消费。许可后仍背压10拍检查非空，再逐片段检查原PA/mask/字节、实际
  fire及延迟正常出队。18个uop/82flow、82个Sbuffer片段均正常完成。
- `tests/lsq_wrapper/test_retire_known_width.py`：真实LoadQueue、VSQ、PSQ、
  Forward保留。每批同ROB连续8/2flow分组，Store退休边界只前进到批末Load的
  ROB，不一次跳过9个活跃ROB项；每批Load在最后Store取原PA有效字节并走
  原S3。18个Store uop/82flow、82个片段和4个原Load正常完成。

四批之间没有reset/取消，没有驱动17..31flow。所有物理发行窗口≤64；每个
uop≤16flow。1flow预热先产生已知退休写入，后续bit6/bit4下降不靠启动随机态。
未复位寄存器高位边界继续保留。只保存compact各批UID/分组/原Load/公开尾见证。

## 2. 三层fresh baseline/after，不回填统一分母

| DUT | PASS前→后 | raw line前→后/分母 | raw toggle前→后/分母 | raw branch前→后/分母 |
|---|---:|---:|---:|---:|
| VSQ | 13→14 | 8→8/8 | 7481→7550/10060（+69） | 355→358/364（+3） |
| StoreQueue | 8→9 | 156→156/223 | 73445→73605/102374（+160） | 2083→2086/2198（+3） |
| LsqWrapper | 7→8 | 230→230/3654 | 122000→123867/322010（+1867） | 8075→8137/18670（+62） |

各组同source aggregate、build、固定源和三类点全集，原节点/primary流与旧
命中保持。所选`retireReqNumReg[4,6]`四个方向点，三层after均4/4命中。
已有32flow叶子用例、4..128取消用例和原失败都没有被重写或替换。

父级没有该内部计数的公开读口；本轮测试只驱动/检查真实公开生命周期，内部
方向以各自native dat证明。不能把叶子命中回填父级，也不能只凭“分配64flow”
而没有原字节消费就称父级批宽完成。

## 3. 完整六-build贡献范围实际重跑

```sh
python3 -B tools/run_summary.py --name vsq-retire-known-width-contributor-regression-01 --workers 8 -- tests/forward tests/psq tests/store_queue tests/lsq_wrapper tests/local_reset tests/normal_mixed/test_original_seeds.py tests/sq_endpoint/test_ldu_joint_phases.py tests/sq_endpoint/test_wrapper_raw_boundary.py tests/unalign/test_basic.py tests/unalign/test_extended.py tests/unalign/test_page_pairs.py tests/vsq
```

完整范围1177+3=1180，没有旧dat OR、绿色子集替代或遗漏Wrapper主目录外41个
既有贡献者。source launch/end aggregate相同，三个成功witness与各自directed
完全相同；原三层取消成功witness也保持。

| DUT | 完整toggle前→后/分母 | 新增 | 完整branch命中/分母 | LCOV原始源码行 |
|---|---:|---:|---:|---:|
| ForwardModule | 37654→37654/40034 | 0 | 54/54 | 253/253 |
| PSQ | 83018→83018/86318 | 0 | 1830/1834 | 5817/5817 |
| StoreQueue | 95883→95960/102374 | 77 | 2191/2198 | 8968/8968 |
| LsqWrapper | 277877→277962/322010 | 85 | 18592/18670 | 59595/59602 |
| UQ | 836→836/908 | 0 | 17/18 | 44/44 |
| VSQ | 9217→9237/10060 | 20 | 361/364 | 3125/3125 |

完整新增toggle为182点，完整line/branch没有新增；directed的68个新branch
已在既有完整贡献范围中命中，不能再声称完整新增68。三类全集和所有旧命中
保持，Forward/PSQ/UQ的原dat字节SHA也相同。

原生贡献数Forward186→186、PSQ70→70、SQ88→89、Wrapper742→743、
UQ42→42、VSQ49→50。原primary摘要保持，Wrapper原2226份public/check/
actor摘要全等；锁定Verilator5.052分析器、artifact/build及共享actor SHA核验。

## 4. 原失败不豁免、上游静态审查不冒充动态增益

完整172份失败前后SHA均为：
`d4ee3e12378aab0576a3288db37012e26247e2b513155108d8249e2cf37e8e87`。

头preCommit/flushSelf原节点仍FAIL；tick932的Sbuffer输出仍属于旧UID315/
SQ254/VA3629056，失败见证SHA及该节点public/actor/check流与上一完整运行相同。
它继续`required=true/waived=false`，在全局及SQ矩阵行显式可见。

另完成[固定源上游域审查](sq-head-permit-domain-20261021.md)：14份源与固定
Git对象相同，131072组unsafe/member mask及每组8种控制组合只证明含Store
项的IRQ关闭；ROB还有非IRQ exception/replay等head self-flush路径，因此没有
证明原节点在全部真实上游域非法。导出EnterSbufferQueue没有redirect输入，
只能解释已入队请求的持久性，不能冒称重建未保留逐拍数据。该静态审计动态
增益为0，原失败没有被修改、豁免或改成PASS。

## 5. 统一索引、审计幂等和剩余范围

执行两次全链：

```sh
python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15
```

两次均exit0；25份关键派生报告SHA幂等，43个历史/本轮运行的249份manifest/
JUnit/native dat字节保持，重复审计没有生成重复archive；43份补例/辅助源无
skip/xfail。机器证据：
`results/lsq-progress-regression-15/vsq-retire-known-width-round-post-audit-v1.json`。

当前38-DUT矩阵列37条独立directed报告。coverage monotonicity门禁PASS且
required/未豁免，但这只是证据与旧覆盖保持，**不是172失败的功能验收通过**。
统一regression15仍2330节点2103PASS/227FAIL，20条line边界、235610个toggle
缺口、563个branch缺口不回填。当前完整六build的剩余toggle独立为：VSQ823、
SQ6414、Wrapper44048、PSQ3300、Forward2380、UQ72。

本轮已关闭目标计数下降/上升情形，但整体仍开放：SQ cancelCount[7]对应128
虚拟uop的真实上游producer域、Wrapper退休bit7的合法容量/时序域、15850
release-wait、头许可自取消的非IRQ完整合法性、未复位高位初值，以及异常/
总线/跨页Load、扩大统一回归与最终全范围审计。不得以当前六build收尾整项目标。

专项入口：`python3 -B tools/audit_vsq_retire_known_width_v1.py --full`。结果在
各`*-retire-known-width-after-01/vsq-retire-known-width-evidence-v1.json`和
`results/vsq-retire-known-width-contributor-regression-01/vsq-retire-known-width-contributor-evidence-v1.json`。
`committed`只指X Reactor产物终态，没有执行Git commit/push。
