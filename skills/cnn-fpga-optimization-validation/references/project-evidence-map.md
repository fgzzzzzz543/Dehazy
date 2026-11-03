# 项目经验与本地证据定位

以下为本用户项目中实际存在的阶段和2026-11-03已归档记录。它们是定位线索而非未来实验的参数默认值、固定通过阈值或连续同一模型的证明。继续工作前读取对应源码、协议、checkpoint及结果状态。

## 1. CNN轻量化阶段（相对工作目录）

工作目录：`C:/Users/30384/Documents/ChatGPT/论文修改`。

| 路径 | 实际方法与可迁移经验 |
| --- | --- |
| `controlled_dehaze/README_zh.md` | 场景隔离、清晰图去重/别名排除、同数据/增强/预算的A3t与Nano对照；额外物理监督单独标注 |
| `controlled_dehaze_widthscan/README_zh.md` | 宽度3/2从头训练50轮，与已冻结宽度4/5条件核验；只用验证集筛选，不选择最佳种子 |
| `controlled_dehaze_width34_multiseed_100/README_zh.md` | 宽度3/4在固定划分下做3训练种子、100轮；报告所有种子、均值/标准差和配对差值 |
| `route_a_lowres/README_zh.md` | 640×480输出保持全尺寸DCP/重建，仅筛320×240、160×120、80×60的CNN分支；不把旧720×480质量值当同基线 |
| `route_a_deployment/protocol.json`、`README_zh.md` | 训练集校准、混合精度整数参考、逐层夹具、OOC及160微调pilot；同时检查降分辨率后的增量/累计损失 |
| `deployment_quant_stability_20261029/README.md` | 只读冻结数值实现的CPU量化稳定性核验；明确没有训练、QAT、综合或板测，质量失败不等于程序没执行 |
| `route_a_iteration4/README_zh.md` | 64位突发行缓存、对齐/尾拍/4KB边界和BRAM单写入口；小图与完整图分开验收 |
| `route_a_pipeline/README_zh.md` | 互斥周期分类→量化突发写→消费与装载解耦，后续双缓冲/局部融合/数值格式/真实DDR为独立阶段 |
| `deployment_resource_review_20261029/README_zh.md` | 软件逐位回放、OOC/整核资源与真实整板条件分开；活跃作业和文件不能粗暴干预 |

这些材料不证明已完成模型知识蒸馏、结构化剪枝或QAT。若未来采用，应建立新的受控协议。旧的320×240/640×480研究线与最终36×24 CNN/720×480视频工程不能不核对变换链就视为相同算法版本。

## 2. 当前归档实现与证据

- QSPI工程：`E:/Dehazy_final_QSPI_V5_20261103`。
- 历史算法/JTAG参考：`E:/Dehazy_final`。
- 完整交付包：`E:/Dehazy_V5_Package_20261103`。
- 原始采样：QSPI工程下 `runtime_metrics_20261103_0239/samples.csv`、`RESULT.json`、`session.log`。
- Flash工具读回：`flash_program_20261103_0218/FLASH_VERIFICATION.json`。
- 后续启动/动态画面：`reports/BOOT_DISPLAY_OBSERVATION_20261103_0228.json`、`CAMERA_MOTION_OBSERVATION_20261103_0236.json`。
- 改动与身份：`reports/SOURCE_CHANGES.patch`、`SOURCE_BASELINE.json`；BIT/XSA、应用、FSBL、BOOT在`delivery/`。
- 工具资源/时序/CDC在`hardware/`；功耗在`hardware/project/unified_video.runs/impl_1/board_video_top_power_routed.rpt`。

本地已有独立源码集合和交付型skill，但它们不替代当前模型/镜像/数据身份核对。此skill自带运行复算工具，不依赖交付型skill加载。

## 3. 需要记住但不能外推的历史边界

- 最终归档是RTL + PS C，无独立HLS kernel；目标xc7z020clg484-2、Vivado/Vitis2020.2。CNN150MHz，视频计时50MHz；不能跨工程照抄。
- 当前归档`source_v5`与历史工程65个源码/资产文件同哈希，提供算法关联，不等于新QSPI已做500张逐图板测。
- BOOT SHA256：`4a55586d07e2c58a0f0792305e71b3b627bf5f29b1c55bb7928a9909d932f7a9`；工具对4,248,144字节读回比较通过，不代表完整冷启动/整片转储已验证。
- 原始运行窗口2026-11-03 02:42:54—02:43:54，UTC+08:00；13样本、12区间。详细算例见运行计数参考，不能沿用作以后新测量。
- 仍有4条Critical CDC；用户动态画面反馈和QSPI模式记录不补出独立完整断电过程或长稳时长。
- 历史500对主机整数参考PSNR23.9853dB/SSIM0.880749，与当前现场摄像头质量和全新盲测有别。
- 部分老README仍写固定输入31.317695FPS或“JTAG-only/未烧写”。它们是当时状态，不作为当前指标或当次操作权限。

## 4. 脚本沿用说明

本skill的`audit_v5_runtime.py`从已经通过真实样本复算及安全测试的本地工具复制，代码在新skill内自包含，未改动旧skill。它的既有测试只覆盖**V5离线计数复算和文件安全**，不证明CNN轻量化、RTL或板卡测试已经重新执行。
