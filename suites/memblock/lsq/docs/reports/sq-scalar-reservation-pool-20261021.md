# 128标量预留池：真实父级动态覆盖与完整核可达性边界分离

**整体仍为 `ACTIVE_NOT_ACCEPTED`。** 最新完整六-build fresh运行
**1182节点：1010 PASS / 172 FAIL，0 ERROR/SKIP**，实际2595.99秒。
原1180节点及172份失败全文保持，新增SQ/Wrapper两节点均PASS。

本轮域为 **`UNIT_INTERFACE_LSQ_CAPACITY`**。真实Picker父级、X Reactor、
独立参考及原始字节检查均执行，但不把模块128项接口容量测试冒称固定完整核
已经可以产生相同上游资源历史；不缩小原目标，也不豁免原失败。

## 1. 合同与输入域先于用例

[预留池合同](../contracts/sq-scalar-reservation-pool.md)先定义容量、取消和逐槽复用，
再实现`tests/store_queue/test_scalar_reservation_pool.py`与
`tests/lsq_wrapper/test_scalar_reservation_pool.py`。目标RTL/Chisel、共享actor和
参考模型未修改，父级保留所有真实下级。

- 每层两轮，绝对起点0/128；每轮预留128个独立单flow Store uop，只在当前
  64项物理窗执行前64项，后64项没有STA/STD。每拍最多两个Store dispatch。
- ROB头始终在所有Store之前的一个非访存分支。该更老分支flushAfter取消128项，
  stall内不派发，恢复exclusive尾为0/128；不是取消已经获头preCommit的Store。
- 每个取消的绝对逻辑位置都用不同、更大的新UID占用，所有新Store的原PA/
  mask/字节实际Sbuffer fire并延迟正常出队。不能只用64位低槽号证明128项复用。
- 每层正常完成256新Store、取消256旧Store、逐绝对位置复用256次；无reset。
  Wrapper还取消2个未执行旧Load，以相同LQ槽的新Load在末Store取原PA字节，
  并完成原S3。Wrapper分两个64窗口推进，ROB每拍最多越过8个Store项。

只保存compact恢复/stall/旧64已执行与64未执行/逐位置UID/新完成摘要，不保存
逐拍JSON、波形或完整新源码副本。

## 2. 能证明的LSQ规则，不能扩大成完整核可达性

`tools/audit_sq_scalar_reservation_domain_v1.py`核验固定开源Git对象与utility
gitlink `eb8e12b00a33e4716e7778175f6dd45b7a3a9ede`，检查Rename单flow、
Dispatch/EnqCtrl的尾准入、128虚拟项、64物理发行与ROB年龄比较源范围。
对256种SQ起点×256种距离共65536组比较，正的1..128距离满足Dispatch
严格after，VSQ的下一拍非满准入只在0..127范围成立；不非法加第129项刷覆盖。

**资源限制必须同时保留：** 固定Parameters的STA0/STA1各16-entry IQ，共32项。
本例有64项未执行STA，不能直接宣布它们都能驻留在32-entry IQ。上游其他流水/
重放/配置的完整资源历史未证明，也没有证明所有配置下全局不可达。

因此动态指标只称LSQ模块容量接口域覆盖；`normal_full_core_producer_proven=false`
在directed证据、完整证据、全局门禁及SQ/Wrapper矩阵行均显式保存。

## 3. 首探测checker错误保留，不冒充RTL失败

`sq-scalar-reservation-probe-01`实际2FAIL：新测试错误期望`sqFull=1`。
它不是VSQ canAccept/full：`NewStoreQueue.scala:1549/2076/2150`及原样
`PhysicalStoreQueue.sv:16123`精确为寄存预留flow数**>128**，恰好128仍为0。

只把新测试的这项期望纠正为0；所有参考、旧新字节、恢复与副作用检查保持。
`probe-02`实际2PASS。原probe-01的失败全文、JUnit、native dat及manifest保留，
专项和统一失败保持审计核对它们的SHA；不声称重放了未保留的逐拍输入前缀。

## 4. Fresh定向前后：同源、同build、同三类点全集

| DUT | PASS前→后 | raw line前→后/分母 | raw toggle前→后/分母 | raw branch前→后/分母 |
|---|---:|---:|---:|---:|
| StoreQueue | 9→10 | 156→156/223 | 73605→73844/102374（+239） | 2086→2086/2198 |
| LsqWrapper | 8→9 | 230→230/3654 | 123867→126161/322010（+2294） | 8137→8140/18670（+3） |

原节点、primary流及旧命中保持。两层`cancelCount[7]`两方向均从定向基线0
变为2次命中。SQ新功能点`SQ-INTERFACE.scalar_pool` checked0→2；Wrapper
沿用原82项功能目录，不删或扩写原分母，并在补例元数据显式记录接口域。

## 5. 完整六-build真实执行，不OR旧dat

```sh
python3 -B tools/run_summary.py --name sq-scalar-reservation-contributor-regression-01 --workers 8 -- tests/forward tests/psq tests/store_queue tests/lsq_wrapper tests/local_reset tests/normal_mixed/test_original_seeds.py tests/sq_endpoint/test_ldu_joint_phases.py tests/sq_endpoint/test_wrapper_raw_boundary.py tests/unalign/test_basic.py tests/unalign/test_extended.py tests/unalign/test_page_pairs.py tests/vsq
```

| DUT | 完整toggle前→后/分母 | 新增 | 完整branch命中/分母 | LCOV原始源码行 |
|---|---:|---:|---:|---:|
| ForwardModule | 37654→37654/40034 | 0 | 54/54 | 253/253 |
| PSQ | 83018→83018/86318 | 0 | 1830/1834 | 5817/5817 |
| StoreQueue | 95960→96084/102374 | 124 | 2191/2198 | 8968/8968 |
| LsqWrapper | 277962→278078/322010 | 116 | 18592/18670 | 59595/59602 |
| UQ | 836→836/908 | 0 | 17/18 | 44/44 |
| VSQ | 9237→9237/10060 | 0 | 361/364 | 3125/3125 |

完整新增240toggle，line/branch没有新增，所有旧命中与三类全集保持；其余四build
的原dat字节SHA也相同。Wrapper的该计数在此前完整运行已命中，本轮只是计数
8→10，不把它当完整新点。定向3个branch增益也不冒称完整范围新增。

原生贡献数Forward186、PSQ70、SQ89→90、Wrapper743→744、UQ42、VSQ50。
原Wrapper2229份public/check/actor摘要全等，主目录外41贡献者仍实际执行。
新成功witness与directed完全相同，既有64flow退休三层witness保持。固定build/
artifact/共享actor SHA、锁定Verilator5.052分析器及source launch/end均核验。

原172份失败前后SHA均为
`d4ee3e12378aab0576a3288db37012e26247e2b513155108d8249e2cf37e8e87`。
旧SQ头许可flushSelf在tick932的输出仍匹配旧UID315/SQ254/VA3629056及原PA
有效字节，继续required/未豁免；本例更老分支成功取消不能替代这个失败。

## 6. 统一索引与剩余工作

全链`python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15`
连续两次exit0；29份关键报告SHA幂等，50个运行的277份manifest/JUnit/native
dat字节保持，没有重复archive；46份补例/辅助源无skip/xfail。38-DUT矩阵现列
39条独立directed报告，接口域限制在全局与两个父级行显式可见。

机器guard：`results/lsq-progress-regression-15/sq-scalar-reservation-round-post-audit-v1.json`。
专项：`python3 -B tools/audit_sq_scalar_reservation_pool_v1.py --full`。
逐层与完整证据位于各`*-scalar-reservation-after-01/sq-scalar-reservation-evidence-v1.json`
及`results/sq-scalar-reservation-contributor-regression-01/sq-scalar-reservation-contributor-evidence-v1.json`。

coverage门禁PASS仅为证据/旧覆盖保持，不是172失败功能通过。统一regression15仍
2330节点2103PASS/227FAIL，20条line边界、235610toggle与563branch缺口不回填。
当前六build剩余toggle为SQ6290、Wrapper43932、VSQ823、PSQ3300、Forward2380、UQ72。

完整核128项producer资源历史、退休bit7、release-wait和头许可非IRQ自取消仍开放；
接下来必须继续正常Load响应/错误/异常和跨页S3域、其他模块及扩大统一回归，
不得以本接口池补例或六build覆盖审计结束整体目标。未执行Git commit/push。
