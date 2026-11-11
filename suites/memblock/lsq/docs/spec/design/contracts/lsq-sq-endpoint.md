# SQ满容量端点：独占边界128不是第129个Store

此合同先于新最小用例/参考修正建立，补充既有LSQ-ALLOC/FORWARD/REPLAY行为，
不改变原82项完成标准，不豁免任何RTL失败，也不扩成Backend原生UT。

## 人类可读的行为

- 正常分配恰好128个未完成Store flow后，更年轻Load记录的SQ指针是这些Store
  **之后的独占边界**，不是当前物理窗口中一个可STA/STD的Store。相对当前
  `sqDeq`的距离可以等于128；第129个未完成Store仍不允许。
- Forward S0应对这个Load使用当前64项物理窗口，与127端点遵守相同的来源、
  最年轻候选和精确身份语义。不能因模256差值正好半环就在参考中拒绝实际
  生产者允许的端点，也不能一般性取消任意两个SQ指针半环比较的歧义检查。
- strict Load在尚有虚拟老Store未进入物理窗口时仍必须等待，不能把返回的
  暂存字节称为Load完成；原Load应进入真实Replay，原slot获得grant后才反馈。
  当前物理64项之外不得提前STA/STD，不伪造ready位图/RAW/RAR许可。
- 非strict查询仍按当前物理候选检查实际字节；此必要条件用例使用不重叠的
  其他Store，不等于忽略未来未知地址的一般程序内存安全证明。
- 必须先完成第一物理窗口的真实Sbuffer消费/连续释放，再发第二窗口的STA/STD，
  最终全部127/128个原Store与原Load都完成。不能用取消/reset清空来冒充完成。
- 排空第一窗口时ROB头最多到第64个Store；第二窗口尚未STA/STD时不准先移到
  最后的Load。`lsq-normal-cbo-02`的12个绿色端点执行被独立审计据此拒绝，原件
  保留；只纠正这个未执行先退休的输入，不改128容量或放宽审计条件。

## 真实开源边界依据

固定`893e1580b705d81f113c30c7a05734e09a08050e`：

1. `backend/dispatch/Dispatch.scala:710-726`按Store的**end**指针`> sqDeqIdx`
   判容量，Load只按自己的LQ end检查；`594-597`的实际ready使用此allowDispatch。
   不能误读成`>=`或把仅用于perf的`lsqCanAccept`当额外实际ready。
2. `utility/MultiFlagCircualQueuePtr.scala:100-104`的`>`是first_flag异或
   operation_value比较。head为h、end为h+128时，operation_value相等且first_flag
   相异，比较结果为真；h+129为假。`133-135`也将差128识别为full，而非overflow。
3. `mem/lsqueue/LSQWrapper.scala:184,200`与`VirtualStoreQueue.scala:158`令Load
   的SQ记录来自同一分配起点。没有新Store flow的Load可持有满池后的exclusive tail。
4. `NewStoreQueue.scala:390-409`把超出物理upper的Load裁剪到当前物理窗口；
   `s0LoadOutOfRange`不是UT人为制造的ready。exact128处query>upper也由上述
   真实指针比较判真。
5. `LoadQueueReplay.scala:853-858`将SMF/RAW的blockSqIdx设为Load原exclusive SQ；
   `520-523`的SMF只有该边界`isNotAfter(sqDeq)`才解除等待。在差128时真实`<=`
   为假，必须继续阻塞，不是参考异常或提前grant。RAW的`507-510`也比较exclusive
   边界与真实address-ready前缀；不能将普通Store依赖的通用sq_after半环拒绝全删。

### SMF补充行为（先于新例/参考修正）

在同一16B范围的两个老Store只各覆盖部分Load字节，三lane均应看到真实multi-match
重放。原Load以cause1进入Replay，保存独占127/128边界，必须等全部原Store真实
消费/释放到该边界才获得grant，然后用原slot反馈完成。新最小例不伪造sqEmpty、
head或内部ready，不因半环异常减少为127；先保留原参考的拒绝，再窄修SMF/RAW
exclusive比较。一般Store依赖的sq_after与Forward after仍保留半环拒绝。

## 新例与验收限制

先以127对照/128端点、三查询lane、strict/普通两类运行原生Wrapper。历史
`lsq-normal-cbo-01`的28934保持ValueError首失败；修正前新最小运行与修正后新目录
分别冻结，不改旧结果。若后续确需参考端点扩展，只允许已锚定dequeue的
`new_job`距离0..128；通用`after`半环拒绝、所有expected/knownness/比较掩码
及独立PA安全检查必须保持。新终点若暴露RTL失配继续普通FAIL，不降流或skip。
