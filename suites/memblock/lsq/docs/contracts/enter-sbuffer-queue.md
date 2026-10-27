# EnterSbufferQueue：已提交store写请求的两项保序缓冲与真实消费记账

状态：**功能语义与合法域先于用例定义；当前固定配置26/26 PASS、34/34 checked、78/78 DA，独立UT已验收。** 本文保留用例前要求和首轮缺口记录；最终证据见[报告](../reports/enter-sbuffer-queue-20261018.md)。属于Store分支独立叶子，不能用Replay或既有Load子块的结果替代。

## 1. 精确目标和公开接口

- 开源 `XiangShan @ 893e1580b705d81f113c30c7a05734e09a08050e`，源码 `src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:727-845`。
- 原始RTL `soc-split/rtl/EnterSbufferQueue.sv`，单文件闭包298行；两个物理entry、两路DeqModule输入、两路Sbuffer输出。使用原样Picker导出，不加修复wrapper、不替换内部实现。
- 每路有效payload：物理地址48、虚拟地址50、data128、mask16、wline1。输入0另有deqPtrMove，输入1的该字段被常量true优化删除，不能绑定不存在的引脚。
- 输出 `io_deqPtrMove_0/1` 为组合消费脉冲；`io_empty` 表示排队写请求为空。源码full/freeCount、prefetch、vecValid未保留为当前top端口，不声称动态验证。
- 独立参考以按接受顺序排列的请求UID、payload和消费credit标记建模，不读取allocated、物理entry、pointer或flag作为oracle。

## 2. 真实生产者/消费者合法域

1. 输入是**顺序前缀**：lane1 valid时lane0也必须valid；两路都valid但只有0 ready时只接受0，下拍未接受的后项须重排到输入0。依据DeqModule的toSbufferValid前缀和数据选择，`NewStoreQueue.scala:1233-1283`，不是任意稀疏双口队列。
2. Sbuffer ready也是前缀：ready1不能在ready0为假时单独为真。真实生产者断言两个fire须前缀（`NewStoreQueue.scala:1407`），真实Sbuffer `sbuffer/Sbuffer.scala:380-381` 也用ready0门控ready1；不把单独消费第二项的非法输入当作普通随机。
3. 无valid时payload可任意变化，不能写入、产生消费credit或污染排队内容。上游被背压的请求只在真实fire时拥有UID；未握手的尝试不算已分配。
4. 源码接口为Decoupled而不是Irrevocable。缓冲内已接受内容在未消费时必须保留，但两路输出表示当前头部两个顺序请求：若旧lane0消费而旧lane1未消费，后者下一拍移动到lane0，**不错误要求它继续固定在lane1**。
5. 所有进入本队列的请求都已在DeqModule完成可写出判断，不在此层重新实现ROB退休、地址旋转、跨页拆分、CBO FSM或Sbuffer内部合并；它们留到真实DeqModule/PSQ/StoreQueue组合。
6. 无redirect端口；已提交store不因本队列中不存在的redirect而取消。reset是唯一中止全部排队请求的条件，中止不记作Sbuffer消费或SQ释放成功。

非法输入前缀、逆序ready和越宽payload由适配层拒绝，单独记录为静态domain检查；不因此宣称DUT动态检查了非法输入。

## 3. 时序、流控和消费语义

- 在DriveStable采样旧队列：输出0/1 valid分别等价于至少1/2条旧请求存在；有效payload严格对应旧队列头部顺序。无效payload不比较未初始化寄存器。
- 真实输出fire由该拍valid与ready决定。`deqPtrMove_i` 仅在该输出真实fire且该请求保存的credit为真时为1；无valid、背压或credit=false都必须为0。
- 入队ready允许使用**同拍实际出队**腾出的槽位。旧长度n、当拍合法输出fire数d，则可接受的前缀容量为`2-n+d`；ready0/ready1分别检查至少1/2项容量，不以输入valid假设出队。
- RisingEdge完成先消费旧头部，再按输入fire顺序追加新UID；空队列新请求没有组合直通，不能在接受它的同一边沿前向Sbuffer假称消费。满队列同时出入时输出仍是旧payload，新payload仅在边沿后可见。
- empty由当前排队请求数决定：满队列消费并等量补充后不产生伪空拍；最后一次真实输出消费后才为空。
- 输入0的credit=false是合法且重要的微架构行为：跨16B store的第一半写请求或CBO.zero写请求不立即贡献SQ dequeue；第二半在输入1时credit固定true。两半可分拍消费，但总credit应精确为1。这里只检查此缓冲保存/输出标记，不冒充DeqModule拆分算法已验证。
- 数据entry无reset初始化，复位只保证valid/empty/ready和credit门控。先对6拍idle reset做状态清空，再以新UID接受、输出并实际消费证明恢复；活动reset丢弃的旧UID独立记账。

## 4. 用例前可读功能点和观察证明

| 功能组 | 微架构语义 | 计划情形及checked依据 |
|---|---|---|
| ESB-RESET | 复位移除旧写请求及旧消费义务 | initial、one_live、two_live、wrapped；后续新UID真实消费后checked，reset中止单列 |
| ESB-ADMIT | 按DeqModule接受顺序保存一项/两项，不能接受未握手尝试 | single、pair、partial_accept、disabled；比较ready/valid和payload，等待接受UID实际消费 |
| ESB-ORDER | 旧请求先于新请求到达Sbuffer，后一项可随头部压紧移到lane0 | fifo、lane_compaction、wrap；每个UID只消费一次，所有有效字段逐项比较 |
| ESB-HOLD | Sbuffer背压不丢请求、不变内容、不提前报告SQ dequeue | head、both、tail_after_head；稳定比较与之后真实消费，不只数背压拍 |
| ESB-REUSE | 同拍真实消费为新输入提供容量且新旧payload隔离 | one_to_one、two_to_two、one_to_two、two_to_one、full_block、consecutive；旧消费/新分配独立UID守恒 |
| ESB-CREDIT | 写请求消费不必等于SQ条目释放，必须保存真实credit | ordinary、split_pair、split_separate、zero_credit、same_cycle_old_flag；基于原输入标记重算公开脉冲 |
| ESB-PAYLOAD | 地址、128位数据、16位mask及wline完整保留而非重新生成 | data_bits、mask_bits、address_bits、wline、input_lane；walking one/zero及不同lane、不同物理槽回绕的实际输出 |
| ESB-IDLE | 空闲或禁用payload不能产生隐藏占用或消费credit | empty_ready、disabled_noise；观察明确的空/valid/credit检查 |
| ESB-CONCURRENT | 持续合法前缀流量在公平消费下不乱序、不丢失、不重复 | seeded、throughput；记录种子和每拍UID守恒，最终真实排空 |

以上组名在实现时细化为reached/checked情形，不以硬件位组合替代行为。初轮仅基础单项/背压/消费；之后分析真实原始RTL未覆盖行，逐条判断“既有功能的情形不足”或“遗漏整体功能”，再补例并独立目录重跑。即便初轮DA已全命中，也必须完成剩余功能情形和随机，不以行覆盖代替功能验收。

## 5. 运行、证据和验收

使用本工程 `tools/build_dut.py`、`tools/run.py` 和已锁定Picker/xreactor/xcomm/Verilator，真实fixture逐拍采样全部公开输入/输出（包括fixture切换空拍）。每次运行新目录、冻结验证源码、保存原样RTL与包哈希、波形、JUnit、功能覆盖和原生LCOV。

每个成功例最终排空；所有分配必须等于Sbuffer真实消费+reset中止+仍存活UID。普通checked等待实际输出payload比较和消费；单独人工调用mark或只驱动valid不算完成。最终独立公开历史审计重建FIFO及credit，不导入领域模型；审计源、artifact与运行source-evidence哈希，不能只相信绿色manifest。

本模块验收不等于DeqModule、PSQ、StoreQueue或LSQ通过，不能消除Load分支已发现的问题。

## 6. 首轮实际运行与补例前缺口

`results/builds/20261018T074443100290Z-enter_sbuffer_queue/report.json` 确认原样单文件导出与原生实例化走钟PASS，实际fixture绑定除clock外全部16个输入。`enter-sbuffer-initial-01` 两例PASS：空闲消费者ready不伪消费，单项接受/背压/真实消费。逐拍比较和独立FIFO参考已实际运行，不是仅smoke。

首轮原始本体DA **61/78=78.21%**、语义 **7/34 checked**。17条未覆盖行逐条分类为既有功能缺少情况：131～136及147～152为输入1到两个物理槽的保存，共12条；155～159为输入0到物理槽1的保存，共5条。计划补双项前缀、单消费后奇数尾位置、输出lane压紧和同拍满池复用，逐字段比较真实输出及credit。没有发现需新增的整体功能，不剔除任何行；其余27个既定语义情形也需补齐，不能只写第二槽就验收。
