# 当前完整38DUT/1808例统一回归07

**结果：1649 PASS / 159 FAIL，NOT_PASS；整体目标仍active。** 这是全部当前已实施
范围的真实统一运行，首次同时包含36个独立子块、真实LoadQueue和LsqWrapper。
不将159个失败称为159个独立架构缺陷，也不以叶子通过/行覆盖高替代上级验收。

## 1. 冻结运行与证据

- 运行：`results/lsq-progress-regression-07/`，完整命令为
  `python3 -B tools/run.py --name lsq-progress-regression-07 --workers 4 -- tests --tb=short`。
  无筛选、跳过或xfail；真实pytest非零退出。原样Picker原生DUT和X Reactor连续采样。
- **1808节点、38原生build、76 reached/checked功能组**；350份启动/结束源SHA
  相等。committed manifest、coverage_complete、cleanup_complete、全部artifact/
  build文件SHA和各源快照均经`audit_progress_run_v8.py`核验。
- 固定开源`kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e`；当前Wrapper
  14轮另重新核验53份原RTL、真实闭包及干净开源HEAD。没有目标RTL/Chisel修改，
  不使用XiangShan-internal，不声称fresh Chisel elaboration或Backend/ISA结果。

## 2. 按实际family的结果，不合并分母

| 当前范围 | 例数 | PASS | FAIL |
|---|---:|---:|---:|
| 四FreeList | 52 | 52 | 0 |
| 三CAM | 24 | 24 | 0 |
| AgeDetector_36 | 11 | 11 | 0 |
| VirtualLoadQueue | 22 | 22 | 0 |
| LoadQueueRAR | 54 | 47 | 7 |
| LoadQueueRAW | 32 | 32 | 0 |
| 全16个UncacheEntry | 384 | 384 | 0 |
| LoadQueueUncache | 72 | 64 | 8 |
| LoadQueueReplay | 131 | 127 | 4 |
| EnterSbufferQueue | 26 | 26 | 0 |
| UnalignQueue | 41 | 41 | 0 |
| ForwardModule | 184 | 165 | 19 |
| VirtualStoreQueue | 42 | 40 | 2 |
| DeqModule | 92 | 67 | 25 |
| PhysicalStoreQueue | 66 | 45 | 21 |
| StoreQueue | 79 | 55 | 24 |
| **LoadQueue** | **199** | **187** | **12** |
| **LsqWrapper** | **297** | **260** | **37** |
| **合计** | **1808** | **1649** | **159** |

所有节点/结果精确等于已冻结的`lsq-progress-regression-06`1312例＋`lq-expanded-06`
199例＋`lsq-expanded-14`297例的并集，159个失败原主断言均保持。比对仅归一化Python
对象的`at 0x...`进程地址，不归一化实际数据/hex payload。失败仍为普通FAIL，
接口边界和模块producer合同不擅自提升成架构可达性证明。

每个DUT自己的**逐源/逐行原DA集合及动态命中集合**分别等于上述对应基线：
LoadQueue为50513/50520、LsqWrapper为59595/59602，LQU为3169/3175；这些剩余行
有各自层级窄证明且保留分母。其余DUT各自插桩行闭合，但真实失败仍NOT_PASS。
不能把独立子块的DA合并成Wrapper或跨层相加伪造总覆盖。

## 3. 原始历史证据及未保留信息

`evidence-check-v8.json`独立核验 **1721份原始逐拍日志、270210条记录**，以完整
input/pre/post/tick及实际pins字段的规范SHA多重集合逐family对照旧基线；参考
expected/change/known-issues不作为这些原始历史的正确答案。959份日志包含nodeid，
再额外核验逐节点轨迹SHA；其他日志明确只声称完整family多重集合匹配。

基础87例（FreeList52、CAM24、Age11）原fixture没有持久逐拍JSON日志。它们有
真实运行时连续被动采样/检查、测试节点/结果、功能bin、native覆盖/产物/build/
源SHA，但**不虚构1721之外的原始历史，也不将缺失日志称为逐节点原始轨迹匹配**。
这项边界同样适用于对应旧基线，未通过选择性删日志或降低本轮门禁产生。

首版`audit_progress_run_v7.py`在原始历史/节点/失败签名检查之后，因错误地读取
叶子没有的冗余`closure_line_hit`字段而KeyError退出。原器SHA
`4be1811748f36775cd8de6b337d36d21fc446879a3bf7265d75184b33d63e488`
及失败原因保存在v8报告/审计器目录。v8复用原严格历史核心，明确区分父块/叶子
元数据，逐个实际LCOV源/行验证DA集合及命中集合；未改变测试结果、输入或RTL。

## 4. 不能据此关闭目标

- Wrapper仍80 reached/76 checked。SID复用、前拍release、disabled strict真实
  失败未验收；三个STRESS情形没有完整合法混合随机/联合容量/公平排空验收。
- 28个DUT全部PASS不能抵消另10个DUT的失败。各层故障、protocol-only探针及删除/
  未定义端口边界继续由各自详细报告解释，不借整批统计重新标绿。
- 这次统一回归已真实完成**当前1808例范围**；未来随机/恢复范围新增后仍须相应
  完整重跑及最终请求→证据审核。当前不含LsqEnqCtrl/ExceptionInfoGen相邻专项，
  不扩大为MemBlock、Backend、任意参数或本地单独reset后迟到旧响应系统合同。

可重审：

```sh
python3 -B tools/audit_progress_run_v8.py lsq-progress-regression-07
```

Wrapper新增44例的原UID/PA/Replay/Bus/CBO与1124条DA增量、最后7条本层窄证明，
见[最新Wrapper报告第10节](lsq-wrapper-20261019.md#10-余量驱动的44个严格补例以及当前38dut统一回归)。
