# 真实 FPS、重复显示、拒收与错误计数

## 1. 先写清每个计数在何种事件递增

以匹配RTL/软件寄存器定义为准。本案V5的分类：

| 指标 | 解释 | 不能混为 |
| --- | --- | --- |
| `displayed_new_frames` | 新处理帧真正成功消费显示 | 所有面板刷新次数 |
| `completed_frames` | 处理路径提交成功的帧 | 已在面板显示的新帧 |
| `repeated_frames` | 成功刷新但复用旧输出 | 新处理吞吐 |
| `frontend_capture_ends` | 前端帧结束事件 | 所有输入均被完整处理 |
| `captured_good` / `bad_captures` | 调度接收后成功/坏帧 | 被调度拒收的帧 |
| `rejected_captures` | 新采集请求未获得接收 | FIFO drop、处理失败或显示下溢 |
| 8类错误/前端drop/下溢 | 见下文明确字段 | 全部帧损失或完整健康证明 |

8类为 `bad_captures`、`failed_frames`、`protocol_errors`、`axi_errors`、`frontend_errors`、`display_errors`、`frontend_drops`、`frontend_underflows`。某些是累计历史状态：区分“整个采样点始终为0”和“本窗口没有新增”。

## 2. 完整窗口与对应时间基准

```text
midpoint_i = (read_start_us_i + read_end_us_i) / 2
T_display = (last_display_midpoint - first_display_midpoint) / 1e6
T_pipeline = (last_pipeline_midpoint - first_pipeline_midpoint) / 1e6
new_fps = Δdisplayed_new_frames / T_display
completed_fps = Δcompleted_frames / T_pipeline
presentation_rate = (Δdisplayed_new_frames + Δrepeated_frames) / T_display
repeat_rate = Δrepeated_frames / T_display
reject_fraction = Δrejected_captures / (Δcaptured_good + Δbad_captures + Δrejected_captures)
```

- 采样N点得到N−1个区间；主指标取完整端点窗口，停滞也进分母，不挑最快区间或删掉无新帧时段。
- 新帧与处理计数有独立读取窗口；因端点在途帧/分组读取而差一，不强行改计数配平。
- 重复呈现率不是去雾吞吐。摄像头输入率、显示扫描刷新率、CPU benchmark、RTL折算FPS和现场新帧FPS分别命名。
- 时钟倒退、计数倒退和显示时间原点改变时先查复位/溢出/异常；没有证据不自动加2^32或重新截短窗口。
- 请求数为0时拒收比例不可计算，不伪装成0%；非法或零时间分母拒绝输出虚假的FPS。

硬件事件参考可用 `Δnew_frames / ((last_event_cycle_end − last_event_cycle_start)/clock_hz)`，但频率必须来自匹配设计。其分母是两端最后一次新帧事件跨度，不等于完整主机采样窗，也不是独立晶振校准。

## 3. 守恒、错误与边界

在本案计数定义下检查：

```text
Δfrontend_capture_ends = Δcaptured_good + Δbad_captures + Δrejected_captures
```

先确认定义才推广到别的工程；差值非0时检查非原子采样和具体事件含义，不填“其他帧”补齐。

报告至少包含：时间/时区/样本数、完整窗口、镜像身份、输入负载、新帧/处理/呈现/重复率、拒收增量及比例、错误起止/增量、区间波动和观察时长。8类错误为0但拒收非0，必须同时披露，不能写“零丢帧”。

长稳、去雾画质、冷启动和仪器功耗没有在该采样任务中测量时明确未验证。DMA或显示完成计数也不能独立证明肉眼面板效果。

## 4. 可执行的纯离线复算

使用本skill内 `scripts/audit_v5_runtime.py`，仅适配本案的字段与定义：

```powershell
python <skill目录>/scripts/audit_v5_runtime.py --samples <原始CSV> --reference-result <原始RESULT.json> --clock-hz <确认的Hz> --boot-image <本地BOOT.bin> --out <新的结果JSON>
```

- `--samples`必填；其余可选。无输出路径时只打印；指定输出必须为不存在的文件，不覆写原证据。
- 不给`--clock-hz`就不复算硬件事件FPS，并明确列出未比较的参考字段；禁止为了补齐字段假设50MHz。
- 对照归档窗口/速率/计数；本地镜像哈希匹配不等于当前板卡镜像已被读取验证。
- 拒收、已有错误或守恒差异作为显式观察保留；`AUDIT_COMPLETE`只代表离线计算完成，`operational_acceptance`保持`NOT_ASSESSED`。
- 脚本无网络、烧写或调试器调用。来自不同schema/语义的数据要先明确映射并验证，不能改列名就冒称同口径。

## 5. 历史算例，不是新项目默认值

本案2026-11-03原始记录：1398新帧 / 60.013188s = 23.2948797854 FPS；处理1397帧，对应60.012892s = 23.2783315958 FPS。呈现3608次含重复2210次；拒收389/1786 = 21.7805151%，8类错误为0。

固定输入100帧的31.317695 FPS、约60次/s的显示呈现和上述摄像头新帧FPS不是同一指标。它们可以同时成立，但不能互相替换成“最新真实端到端FPS”。后续实验须从自己的原始样本重算。
