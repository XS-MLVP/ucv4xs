# 普通LD的S4异常源准入：PF/AF而非任意外部元数据（补例前纠正）

进一步核对TLB.scala553和NewLoadUnit251/409：普通operation6不是HLV，isHyper必须为0；
TLB非叶元数据仅在特定GPF有意义。旧S4错误定向的tail_hyper=1/任意nonleaf以及首次
scalar便给TL-D poison，最多是LSQ接口压力及给定输入下的源投影，**不足以正常上游
准入**。旧80/6和epoch运行、原UID/覆盖原件保留；不把输入关系投影检查当完整可达性。
S3准确DCache错误仍因固定EnableAccurateLoadError=false关闭。

新增独立普通LD profile，保持全部13种head/tail行为和三lane/两布局，但将有真实
TLB/PMP来源的PF(13)/AF(5)分别作为不同异常：TLB权限page fault保留给定PA但kill真实
Forward/DCache；S2 tag_error产生AF。isHyper=0、非GuestFault的nonleaf=0。异常向量
head优先，其他写回/原因/撤销/MSHR及原grant/反馈/精确trap/同槽新UID完全保留。

被kill的DCache响应无有效义务，其bits仍被原nukeQuery粗略组合读取；输入明确选择
miss=0的保留值，dataValid=1，必须下一拍精确revoke，不能把不准确query当完成。
TLB/DCache依然是DUT外部、在S0前选择的刺激，不宣称native upstream DUT执行。

该78例不是删掉旧HWE字段UT：旧含毒转发profile继续保留为接口/准入受限证据；正常
S4 HWE还需真实cache-miss/forward请求合同，不能凭一个TL-D输入valid自封正常。
原八类型随机的完整输入合法性也不能由fullva/gpaddr两字段gate独自推断，其他上游
字段合同继续列未验证。新普通profile正常时序与原UID效果、每条原DA及覆盖补例分别核验。
