# 如何构造合法且真正到达 DUT 的激励

## 何时使用、准备什么

开发 fixture/driver、修改特殊操作或归因失败前使用。输入是当前 DUT 的 [合同与生产者约束](../design/requirements-boundary.md)、端口绑定、时序及用例承诺。

## 怎么做

1. 从真实 producer 核实字段编码、size/mask、对齐、互斥、许可、身份/年龄及不可撤回点；把值相同但历史不同的输入分开。
2. 在 fixture 边界校验必需字段、合法编码和字段关系；未知键、必要端口缺失立即失败，不静默忽略或补零。非法输入测试应验证 fixture 拒绝，或另标越域压力，不能冒充正常功能反例。
3. 按合同构造前置状态：分配、许可、部分完成、回绕等必须由合法序列得到，不能仅手填下游字段声称整机可达。
4. 按接口规定保持、撤销或重试请求，记录真正的 fire 与事务 UID；不能把 driver 调用返回当成 DUT 已接受。
5. 从单事务扩展到目标边界、同拍竞争和背压；每次只改变能解释结果差异的因素。必要时使用小范围有界 trace，不默认保存波形。
6. 对关键约束保留合法控制和违反该约束的负例。非法负例的预期由 fixture/接口合同决定，不能凭空要求 DUT 拒绝所有越域输入。

## 产出

生产者来源及版本、准入规则位置、构造序列、driver/monitor 采样点、实际 fire/UID、合法与非法对照的 nodeid/结果，以及生产可达或端口压力的范围标记。

## 如何验收

合法 fixture 可通过准入并到达目标状态；错误编码/未知键能在约定边界被发现。要求最终接受的用例在零接受时失败；允许拒绝的用例则验证拒绝条件和副作用，不机械要求接受。

案例：[十二类踩坑 P01](../../docs/lessons/rtl-verification-soundness-20261026.md)。配套：[checker 与完成性](checker-and-runtime.md)。
生产者合法域和叶子端口压力可使用显式不同入口，但后者不能豁免宽度/所有权/采样/oracle，
也不能冒称CSR可达。反向还要保留合法边界对照，防止准入过严（例如最后一个trigger的chain
位并非被CSR强制0），见[IFU触发器合同](../../suites/frontend/ifu/docs/transaction-adapters.md#producer与端口域压力不能混为一谈)。
只检查size/mask的最大值并不能证明生产可达：non-taken长度也可能有完整fall-through的
等式约束。应从实际选择该字段的producer分支逐项推导，并用合法历史和原端口压力对照；
见[IFU生产者反证与carry模型修复](../../suites/frontend/ifu/docs/bugs/instr-boundary-carry-ftq-owner.md#后续生产者复核原可达性论证不充分)。
该案例收紧了原可达性结论但保留旧FAIL；后续producer类型也不能把之前端口域的carry
或fake reply晋升为完整生产历史，来源须随数据和身份跨事务传播。
事务若同时携带原始字节和派生oracle描述，必须逐项绑定两者；不能仅校验字段各自位宽。
应从实际待驱动字节独立步进起始、宽度、PC/身份及计数，再校验冗余描述；跨事务carry的
低半还须绑定前一个实际输入UID。见[IFU输入描述对账](../../suites/frontend/ifu/docs/observation-coverage.md#3-完成性--账本)。
