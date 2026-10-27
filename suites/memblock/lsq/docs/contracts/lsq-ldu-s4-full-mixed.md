# 完整八类型混合的S4地址源纠正（新独立代理前合同）

新`audit_lsq_s4_fullva_source_v1.py`从公开S0 head/tail与最终S4输入实际发现：旧mixed02
与S3新26例中各18次无异常S4仍把head fullva送到最终包；源码1437/1574在head无异常
时必须取tail fullva，低12位已足够证伪，不需虚构TLB高位或GPAddr。旧2/6、17/9及
UID/输出/DA全部保留，但旧三字段绿色门禁不构成完整S4正常准入。

本轮不能只新增独立异常定向而留下原全域随机的已知错误源关系。因此新增独立
`LduS4MixedOwners`，保留原0x7100..0x7107、八类型权重、600/fair、sticky CBO、split/
别名、立即SID复用、错误和全部恢复；不新增随机调用、不删原类型/结果。仅新增
每段外部TLB地址策略记录并修复最终S4 fullva/gpaddr/异常优先选择；正常当前18个无
异常S4实际只应改变fullva与gpaddr，其他输入、调度、原UID义务必须逐项核对。

TLB翻译是DUT外部生产者假设：head fullva保持原预先选择值，tail fullva为其实际
S0 VA，tail gpaddr在当前连续物理策略下为head gpaddr加实际tail PA偏移，nonleaf/
hyper当前UID内相同。每段假设在其S0前记录；不冒称native TLB/LoadUnit证明。异常
head优先与非连续物理页由独立S4错误定向补齐，不能从旧流未记录的值反推答案。

独立审计需保留完整原UID/效果门禁，仅把旧“所有fullva==vaddr”过窄假设换成源正确
的S4 tail选择，并以精确AST单断言变更证明确无删除其他效果检查；另从预先冻结的
外部输入核对fullva/gpaddr/原引脚。新旧raw除这两项输入外逐字段比较，公开输出变化
必须定位到实际Replay的fullva，不能默认全相等或仅凭FAIL个数不变认定等价。

所有普通FAIL保留，原种子完整通过/取消同槽新UID仍须真实证明。先运行八原种子，
随后自身DA逐行分类/补例；不追溯混入仍运行的2036节点回归11，不修改其480启动源。
