# 大后缀取消与全槽新UID：覆盖增益和新增SQ头许可失败

**整体仍为 `ACTIVE_NOT_ACCEPTED`。** 最新完整六-build运行1177节点：
**1005 PASS / 172 FAIL，0 ERROR/SKIP**。原1173节点和171失败全文保持；
新增三个正对照通过，同时新增一个必须保留的SQ头许可/flushSelf失败。
不能把正对照通过或覆盖门禁绿当作取消恢复已整体验收。

## 1. 合同、层次和公开生命周期

用例前定义 [vsq-cancel-capacity合同](../contracts/vsq-cancel-capacity.md)。
固定开源RTL/Chisel、Picker native build、X Reactor、共享actor和参考模型未改。

| 层次 | 实际功能检查 | 完成/取消/复用见证 |
|---|---|---|
| VSQ | 公开redirect一次取消4/8/16/32/64/128个虚拟uop，恢复exclusive物理尾正确、stall内不派发，所有取消虚拟槽用不同UID复用并真实退休 | 446正常虚拟UID、252取消UID、252逐槽复用；正常物理382flow |
| StoreQueue未许可对照 | ROB头保持在首Store之前，实际STA/STD后取消4..64Store，保留旧字节、取消UID无Sbuffer消费，每个位置新UID真实消费/出队 | 318正常Store、124取消/复用位置、318实际Sbuffer片段 |
| LsqWrapper | 16Store部分取消和64Store全取消；真实两支恢复尾，原幸存Load字节和S3完成，被取消Load的槽由新Load实际查询/S3完成，所有取消Store位置用新UID消费 | 126正常Store、80取消/复用位置、3正常Load、2取消Load |

VSQ128-uop窗口使用0/1-flow交替，只有64个物理flow。Leaf独立生产者自己维护
UID、虚拟位置、ROB与physical end，参考模型不作为控制决策来源。取消后允许
被取消ROB槽重用，但UID必须新分配，避免人为制造超ROB半环年龄跨度。Leaf
只有在公开retired end可见后，才由外部PSQ代理每拍最多消费两个flow。

窗间采用普通Store正常消费，不以reset/取消代替排空。父级保留真实下级连接；
没有将128虚拟项解释为128个物理Store可同时STA/STD，也不宣称父级128零flow
uop域已验收。所有witness是compact公开尾/stall/逐槽UID与完成摘要，不是逐拍trace。

## 2. Directed fresh baseline/after

| DUT | PASS前→后 | raw line前→后/分母 | raw toggle前→后/分母 | raw branch前→后/分母 |
|---|---:|---:|---:|---:|
| VSQ | 12→13 | 8→8/8 | 6629→7481/10060 | 355→355/364 |
| StoreQueue未许可对照 | 7→8 | 156→156/223 | 71514→73445/102374 | 2077→2083/2198 |
| LsqWrapper | 6→7 | 230→230/3654 | 120901→122000/322010 | 8063→8075/18670 |

各组同source aggregate、同build和三类点全集，旧节点/primary流及覆盖命中保持。
VSQ新bin checked0→6，SQ新bin0→5；Wrapper沿用`LSQ-RECOVER.reuse`，6→7。
VSQ cancelCount[4..7]的8个方向0→8命中；SQ[2..6]的10个方向0→10；Wrapper
定向[4,6]四方向0→4，但这些Wrapper点在此前完整运行中已命中，不当作完整新增点。

## 3. 不能被正对照替代的真实FAIL

原节点：
`tests/store_queue/test_cancel_capacity.py::test_real_cancel_capacity_old_bytes_and_every_new_UID_normal_consumption[True]`

- `vsq-cancel-capacity-probe-01` 实际2PASS/1FAIL；原轨迹允许ROB头等于第一条
  Store，随后在SQ254处全取消64项。`actor.drain()`的严格消费者遇到无法匹配
  当前新UID的公开Sbuffer输出，抛出StopIteration，原异常与JUnit/native dat保留。
- `probe-02` 新增未给头许可的独立对照，实际3PASS/1FAIL；原节点仍失败，未改
  输入序列或放宽消费者。原失败节点的public、actor、check摘要在两次probe和
  完整运行中均相同。
- 失败瞬间tick932，Sbuffer lane0的有效输出匹配**旧UID315、位置254、
  VA3629056**；PA、mask255和所有有效字节也匹配被取消的旧owner，且不匹配
  替代新UID。这不是只有一个名称/UID归属断言而没有实际payload证据。
- 该边界是否能由真实上游在已给preCommit许可后发出同类flushSelf，仍须审查。
  当前分类为`OPEN_HEAD_PRECOMMIT_FLUSHSELF_BOUNDARY`，**required=true、
  waived=false**；不先验称其为架构RTL缺陷，也不以“可能非法producer”豁免。

诊断保存在完整运行失败case目录的`vsq-cancel-capacity-failure.json`，只包含
失败时公开端口和外部旧/新producer记录；捕获后原异常继续抛出，未skip/xfail。
未许可对照是独立正例，不覆盖或删除原失败节点；本轮完整运行必须包括两者。

## 4. 完整六-build真实重跑

```sh
python3 -B tools/run_summary.py --name vsq-cancel-capacity-contributor-regression-01 --workers 8 -- tests/forward tests/psq tests/store_queue tests/lsq_wrapper tests/local_reset tests/normal_mixed/test_original_seeds.py tests/sq_endpoint/test_ldu_joint_phases.py tests/sq_endpoint/test_wrapper_raw_boundary.py tests/unalign/test_basic.py tests/unalign/test_extended.py tests/unalign/test_page_pairs.py tests/vsq
```

实际运行**2531.48秒**、1177节点1005PASS/172FAIL。范围为原1173+新4，
其中三个新节点PASS、一个新增必保留FAIL。原171失败原样保持：
`ee31498630cb268f734a4db9f48d19a35ef6f4cb11255193dda16aa313a019e3`；
包含新增FAIL的当前172失败SHA：
`d4ee3e12378aab0576a3288db37012e26247e2b513155108d8249e2cf37e8e87`。

| DUT | 完整toggle前→后/分母 | 新增 | 完整branch | LCOV原始源码行 |
|---|---:|---:|---:|---:|
| ForwardModule | 37654→37654/40034 | 0 | 54/54 | 253/253 |
| PSQ | 83018→83018/86318 | 0 | 1830/1834 | 5817/5817 |
| StoreQueue | 95219→95883/102374 | 664 | 2191/2198 | 8968/8968 |
| LsqWrapper | 277863→277877/322010 | 14 | 18592/18670 | 59595/59602 |
| UQ | 836→836/908 | 0 | 17/18 | 44/44 |
| VSQ | 8681→9217/10060 | 536 | 361/364 | 3125/3125 |

完整line/branch没有新增命中，三类点全集保持，旧命中均无丢失。SQ gain包括该
完整范围里的正例与失败轨迹，不擅自把所有增益归给正对照。完整运行不是旧dat OR，
native贡献数为Forward186→186、PSQ70→70、SQ86→88、Wrapper741→742、
UQ42→42、VSQ48→49；Wrapper主目录外41个旧贡献者仍在实际命令中。

原primary摘要及Wrapper2223份public/check/actor摘要全等，三个成功新witness与
directed对应者相同；原失败case的三种摘要与两次probe全等。native artifact、
固定build及共享actor SHA、锁定Verilator5.052分析器、各运行source launch/end
均核验。当前coverage monotonicity为PASS/required=true/waived=false；它只证明
证据/旧覆盖保持，不表示这次172失败的功能验证通过。

## 5. 统一链与后续边界

统一38-DUT矩阵现列34条独立directed报告；新增头许可FAIL在全局与SQ行的
`required_new_functional_failures`中显式列出，未藏在正例摘要里。统一regression15
仍为2330节点、2103PASS/227FAIL；563 branch、235610 toggle缺口库存不回填。

当前剩余非wrapper toggle：VSQ843、SQ6491、Wrapper44133、PSQ3300、
Forward2380、UQ72。15850 release-wait、头许可flushSelf上游合法性、父级128
虚拟uop域、未复位退休计数初值、异常/总线/跨页Load等仍开放。整体目标不关闭。

机器证据：各层`*-cancel-capacity-after-01/vsq-cancel-capacity-evidence-v1.json`、
`results/vsq-cancel-capacity-contributor-regression-01/vsq-cancel-capacity-contributor-evidence-v1.json`。
审计入口：`python3 -B tools/audit_vsq_cancel_capacity_v1.py --full`，以及统一
`python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15`。无逐拍JSON、
波形、完整源码副本或Git commit/push声明。
