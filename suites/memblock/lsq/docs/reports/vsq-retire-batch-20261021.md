# VSQ 退休批宽：8×4 flow、公开尾32→33与真实高位方向

**结果：合法退休批宽补例及六-build完整贡献范围重跑已完成。最新为1173节点，
1002 PASS / 171 FAIL，0 ERROR/SKIP；原1172节点结果、171失败全文和全部旧
覆盖命中保持。整体仍为 `ACTIVE_NOT_ACCEPTED`。**

## 功能合同和实际检查

先扩展 [VSQ恢复/退休合同](../contracts/vsq-release-walk.md) 的
`VSQ-RETIRE.batch_width`：八个连续 uop，每个4个physical flow，总预留32。
公开ROB头越过后，八个原UID在同批正常退休，公开retiredPtr到32；之后再派发
一个新单flow uop，正常退休使尾到33。后续小批使退休计数高位反向回落，而不是
reset、取消或内部寄存器写入。

用例 `tests/vsq/test_retire_batch_width.py` 通过真实Picker/X Reactor fixture，
原有参考模型逐拍核对公开端口；`vsq_semantics.json` 保存八UID同拍checked及
后续第9个UID正常完成的compact事件。叶子只证明虚拟Store退休和公开尾，不
冒充父级物理内存字节消费。既有StoreQueue/Wrapper恢复及真实消费补例保持。

## Directed fresh baseline/after

正式基线/after 为 `vsq-retire-batch-baseline-03` 与
`vsq-retire-batch-after-03`，**3→4 PASS**。同source aggregate、同native build、
三类点全集不变、旧命中无丢失；与锁定Verilator5.052分析器核对raw dat。

| 指标 | 前→后/分母 | 新增命中 |
|---|---:|---:|
| raw line | 4→4/8 | 0 |
| raw toggle | 2088→2173/10060 | 85 |
| raw branch | 188→189/364 | 1 |

目标源位置 `dut/virtual_store_queue/VirtualStoreQueueDut.v:5397`：
`retireReqNumReg[5]:0->1`、`1->0` 各由0变为1；功能bin reached/checked均0→1。
原始源码LCOV行另外核对，不混写为raw line点。机器证据：
`results/vsq-retire-batch-after-03/vsq-retire-batch-evidence-v1.json`。

## 保留的早期错误/不足证据

- `vsq-retire-batch-after-01` 实际 **3 PASS/1 FAIL**：新增测试把physical end与
  virtual uop position相减求和，混用了计量单位，结果116≠32。该Python
  precondition错误及原JUnit/manifest/stack保持，改为独立核对8个flows=4与
  最后physical end32；未删公共端口比较、改模型或把失败标为skip/xfail。
- `after-02` 虽4 PASS，但只有目标上升方向1、下降方向0。该运行不作为双方向
  闭合；随后增加真实单flow正常退休，正式`after-03`才双方向各1。
- 深后缀旧`vsq-deep-suffix-after-01`的bin错误关联被取消UID，checked为0；
  正式`after-02`在取消断言完成后关联正常完成的新UID，reached/checked均1。
  补例实际是**1个新uop UID、3个physical flow**，不是“3个新UID”，不声称8个
  被取消虚拟槽全部复用。早期报告口头误数已纠正，原运行目录不删。

## 六-build完整真实运行

```sh
python3 -B tools/run_summary.py --name vsq-retire-batch-contributor-regression-01 --workers 8 -- tests/forward tests/psq tests/store_queue tests/lsq_wrapper tests/local_reset tests/normal_mixed/test_original_seeds.py tests/sq_endpoint/test_ldu_joint_phases.py tests/sq_endpoint/test_wrapper_raw_boundary.py tests/unalign/test_basic.py tests/unalign/test_extended.py tests/unalign/test_page_pairs.py tests/vsq
```

实际 **1173节点：1002 PASS/171 FAIL，0 ERROR/SKIP**，耗时 **2548.17秒**。
这是单次fresh执行，不是旧coverage OR。原1172节点的结果和171失败全文保持：
`ee31498630cb268f734a4db9f48d19a35ef6f4cb11255193dda16aa313a019e3`。
此前从regression15引入两个VSQ失败的源行196→226说明另见release报告；精确
源diff证明只有一个30行旧release测试的插入，所有旧函数AST保持，不只是注释，
归一化也只允许两个明确节点的一处196/226 frame。

| DUT | toggle 前→后/分母 | 新增 | branch | LCOV 原始源码行 |
|---|---:|---:|---:|---:|
| ForwardModule | 37654→37654/40034 | 0 | 54/54 | 253/253 |
| PSQ | 83018→83018/86318 | 0 | 1830/1834 | 5817/5817 |
| StoreQueue | 95219→95219/102374 | 0 | 2191/2198 | 8968/8968 |
| LsqWrapper | 277863→277863/322010 | 0 | 18592/18670 | 59595/59602 |
| UQ | 836→836/908 | 0 | 17/18 | 44/44 |
| VSQ | 8671→8681/10060 | 10 | 361/364 | 3125/3125 |

完整line/branch无新增命中；六build三类点全集保持。其余五build的原始dat字节SHA
也相同；VSQ贡献47→48，其他build贡献及所有原primary流保持，Wrapper2223份
public/check/actor摘要全等。新节点full与directed的primary摘要及功能事件SHA
相同。source launch/end、artifact/build/固定RTL/锁定分析器均核验。

完整证据：
`results/vsq-retire-batch-contributor-regression-01/vsq-retire-batch-contributor-evidence-v1.json`。

## 当前边界

`all_old_native_hits_retained`保持PASS、required=true、waived=false。统一
regression15仍为2330节点/2103PASS/227FAIL，完整目标没有收缩为这六build。
VSQ剩余toggle1379，StoreQueue7155，Wrapper44147，其他层的合法缺口仍待推进。
`:15850 else` release-wait仍开放；`:15853 else`只有post-reset state3静态证明，
原branch分母和全部未命中点保留，不冒充动态增益。

最终完整统一链已连续两次 **exit0**，日志为统一目录下
`post-regression-vsq-batch-final-02.log` 和
`post-regression-vsq-batch-idempotence-02.log`；16份关键报告SHA幂等，26个运行
目录中的182份受检历史manifest/JUnit/native dat SHA保持，第二次未新增重复
归档；35份补例/辅助源无skip/xfail检查通过，15份本轮Python源语法解析通过。
统一矩阵38行，现收录31条独立补例；统一branch缺口仍563点，其中423为条件
缺例、137为初始化工具边界、3为严格限定post-reset的state3边界；没有动态回填。
当前门禁PASS、未豁免，旧2125点丢失的`FAILED_OPEN`历史仍在。

收尾机器证据为统一目录下 `vsq-round-post-audit-v1.json`，明确标记
`completion_not_claimed=true`；门禁绿不等于整体验收。
本轮无逐拍JSON、波形、完整源码副本或Git commit/push声明。
