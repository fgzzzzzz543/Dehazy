# Dehazy — 暗通道先验与轻量 CNN 协同的 FPGA 图像去雾

本项目面向资源受限的 FPGA 平台，结合暗通道先验相关预处理、轻量 CNN 和图像重建，实现图像去雾。当前说明对应 **V5 / Dehazy_final 部署版本**，包含主机整数参考实现，以及 AC880 上的 OV5640 摄像头 → ARM 预处理 → PL CNN → ARM 重建 → TFT 显示链路。

> 本文使用截至 2026-11-03 已保存的代码与实验记录，不代表重新进行了实验。真实摄像头链路约 **23 FPS**；历史固定输入的 **31.318 FPS** 不能作为摄像头整机帧率。当前工程是研究与板级功能验证工程，不是通用 Python 软件包。

## 1. 项目功能

- **先验与学习结合**：ARM 执行部署预处理和重建，PL 执行轻量 CNN；部署权重位于 `source_v5/assets/`。
- **摄像头实时处理**：720 × 480 RGB565 图像、36 × 24 CNN 网格、`base_ch=3`，CNN 时钟为 150 MHz。
- **TFT 显示与直通对照**：800 × 480 TFT 扫描，左右各留 40 像素黑边；支持去雾和摄像头直通模式。
- **离线单图去雾**：无需板卡，在 Windows 主机运行与部署算术一致的参考实现，输出去雾图和前后对比图。
- **配对画质评估**：提供 PSNR / SSIM、逐图结果、固定样本可视化、参考引擎自检和结果复核。
- **可追溯交付**：包含源码、构建脚本、已验证 bit / XSA / ELF、SHA-256 清单和历史记录。

本版本与历史全分辨率研究模型不是同一配置。不要混用历史模型参数量、旧版画质、单模块性能和本版本整机结果。包内有部署权重，**不包含原始训练 checkpoint，也不提供完整的重新训练流程**。

## 2. 目录结构

```text
Dehazy_final/
├── README.md
├── source_v5/                 # V5 算法、RTL、ARM 软件与部署权重
├── board_video/
│   ├── rtl/                   # 摄像头与显示适配 RTL
│   ├── vendor/                # 外设及第三方模块
│   ├── constraints/           # 引脚与时序约束
│   ├── software/              # ARM 视频应用适配层
│   ├── scripts/               # Vivado / Vitis 构建入口
│   ├── build_01/              # 归档硬件工程
│   └── vitis_01/              # 归档软件工作区
├── delivery/                  # 已验证产物与 JTAG 启动入口
├── quality_eval/
│   ├── v5_reference.py        # 主机参考引擎
│   ├── process_single_image.py
│   ├── evaluate.py
│   ├── verify_results.py
│   ├── test_quality_eval.py
│   ├── dataset/               # 本地配对数据与清单
│   └── results/               # 画质结果与示例图片
├── scripts/                   # 集成、上板与观测脚本
├── tests/                     # 工程回归测试
├── reports/                   # 板级报告、引脚表与来源记录
├── results/                   # 历史板测记录
├── engineering_eval/          # 资源、时序及工程评估
└── packaging/                 # 原始交付包校验清单与工具
```

这是当前完整本地交付目录，不代表所有大文件、数据和第三方模块均已获准公开。发布精简仓库时需要同步调整目录说明、数据入口和校验流程，不能删去文件后仍声称完整包可复现。

## 3. 环境依赖

### 3.1 离线推理与画质评估

| 依赖 | 归档评估环境 / 用途 |
| --- | --- |
| 操作系统 | Windows；主机 DLL 与部分脚本依赖 Windows |
| Python | 3.11.9 |
| NumPy | 2.4.6；整数 CNN 与数组运算 |
| SciPy | 1.17.1；独立指标复核 |
| Pillow | 12.3.0；图像读取、缩放和保存 |
| scikit-image | 0.26.0；SSIM |
| GCC | Vivado 2020.2 随附 MinGW GCC；编译主机 C DLL |
| 字体 | 单图对比图使用 `C:/Windows/Fonts/msyh.ttc` |

版本来源：[RUN_CONFIG.json](quality_eval/results/SOTS_outdoor_20261102_231532/RUN_CONFIG.json)。这些是归档版本，不是最低版本要求；其他版本未据此宣称验证通过。当前主机推理路径不需要 PyTorch、CUDA 或 GPU。

`quality_eval/v5_reference.py` 中 `GCC` 的默认路径为：

```text
D:/ToolsXilinx/Vivado/2020.2/tps/win64/msys64/mingw64/bin/gcc.exe
```

若安装位置不同，应在独立开发副本中适配路径与校验流程。**不要修改原归档文件后继续把原 SHA-256 清单当作通过依据**；单图入口会先校验原交付包，缺失或改动受保护文件将导致退出。

### 3.2 FPGA 构建与上板

- Vivado 2020.2、Vitis 2020.2 / XSCT，以及器件支持和 JTAG 驱动。
- AC880（XC7Z020）、OV5640 摄像头、配套 TFT 和 JTAG 连接。
- 接线遵循 [PINOUT.csv](reports/PINOUT.csv) 与 `board_video/constraints/`。
- JTAG 入口要求板卡为 JTAG 启动模式，本机硬件服务器可通过 `localhost:3121` 访问。

无需板卡即可离线推理；仅查看已有结果不需要安装 FPGA 工具。

## 4. 快速开始：离线单图去雾

以下命令使用 **PowerShell**，请先进入本项目根目录。所有示例均以根目录为工作目录；仓库地址尚未确定，因此不提供虚构的 `git clone` 地址。

### 步骤 1：创建 Python 环境

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install numpy==2.4.6 scipy==1.17.1 Pillow==12.3.0 scikit-image==0.26.0
```

依赖安装后，还需要满足上文的 GCC 路径和 Windows 字体要求；Python 安装命令不会自动安装 Vivado / Vitis。这里记录的是复现配置，本次文档整理没有重新执行依赖安装。

### 步骤 2：检查完整交付包与参考实现

```powershell
& .\.venv\Scripts\python.exe .\packaging\verify_package.py
& .\.venv\Scripts\python.exe -m unittest discover -s .\quality_eval -p test_quality_eval.py -v
```

完整性检查预期返回 `state: PASS`，单元测试预期全部通过；二者均不连接板卡。若有缺失文件、哈希不一致或测试失败，应先排查，不要跳过检查继续宣称复现成功。完整包校验耗时取决于归档文件总量与磁盘速度。

### 步骤 3：处理一张图片

下面从本地测试集中选择一张输入。也可以将 `$inputImage` 设置为你自己的图片绝对路径。

```powershell
$sample = Get-ChildItem .\quality_eval\dataset\hazy -File | Sort-Object Name | Select-Object -First 1
if ($null -eq $sample) { throw '未找到示例输入，请准备一张有权使用的图片。' }
$inputImage = $sample.FullName
New-Item -ItemType Directory -Path .\demo_output -Force | Out-Null
& .\.venv\Scripts\python.exe .\quality_eval\process_single_image.py "$inputImage" --desktop .\demo_output
```

`--desktop` 是现有脚本的参数名，表示**已经存在的输出目录**，不要求它必须是系统桌面；这里只将输出保存在 `demo_output/`。

运行后会生成：

- `demo_output/` 中的原图副本和去雾 PNG，文件名带时间戳。
- `quality_eval/results/single_image_<时间戳>/comparison.png`：前后对比图。
- 同一结果目录中的 `dehazed_native_720x480.png`、输入/输出 RGB565 数据、`ENGINE_SELFCHECK.json` 和 `RESULT.json`。

**分辨率说明**：实际推理先将图片缩放到 720 × 480；保存到 `demo_output/` 的图像再缩放回原图尺寸。这不是原生高分辨率推理，中间缩放也不保证保持原始纵横比。单张真实照片没有配对清晰真值时，脚本不会伪造 PSNR / SSIM。

## 5. 运行配对画质评估

完整本地包中已有 `quality_eval/dataset/manifest.json`、有雾图和清晰参考。若公开版本未分发数据，应先获取有权使用且与清单一致的数据；`prepare_dataset.py` 依赖历史来源目录，不是通用下载器。

使用新的输出目录运行，避免覆盖冻结结果：

```powershell
$run = Join-Path (Get-Location).Path ('quality_eval/results/reproduce_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
& .\.venv\Scripts\python.exe .\quality_eval\evaluate.py --output "$run"
if ($LASTEXITCODE -ne 0) { throw '画质评估失败，请检查输出日志。' }
& .\.venv\Scripts\python.exe .\quality_eval\verify_results.py "$run"
if ($LASTEXITCODE -ne 0) { throw '结果复核失败，请检查核验记录。' }
```

主要输出为 `SUMMARY.json`、`per_image.csv`、`predictions/`、`RUN_CONFIG.json`，复核后还会生成 `RESULT_VALIDATION.json` 和固定样本对照图。详情见 [画质测试说明](quality_eval/README_画质测试.md)。

## 6. FPGA 上板与重新构建

### 6.1 使用已验证产物

> **硬件操作提醒**：以下命令会复位板卡并重新下载 bit / ELF，中断当前运行会话。请只在确认目标板卡、接线和启动模式后手动执行。本入口是易失 JTAG/DDR 下载，不写 Flash。

在项目根目录执行，并根据本机安装位置调整 XSCT 路径：

```powershell
& 'D:\ToolsXilinx\Vitis\2020.2\bin\xsct.bat' .\delivery\run_live.tcl 0
```

末尾参数 `0` 为持续去雾，改为 `1` 则为摄像头直通。脚本包含原验证板卡的 JTAG 身份检查：更换板卡时需要重新核验并适配，不能直接删除检查来绕过目标身份确认。控制地址与随附 ELF 绑定，**不可直接用于重新编译的 ELF**。

### 6.2 从源码创建新工程

保留历史 `build_01/`、`vitis_01/` 和 `delivery/`，在新的输出目录构建：

```powershell
$projectRoot = (Get-Location).Path
$hardwareBuild = Join-Path $projectRoot 'board_video/build_readme'
$softwareBuild = Join-Path $projectRoot 'board_video/vitis_readme'
if ((Test-Path $hardwareBuild) -or (Test-Path $softwareBuild)) {
    throw '输出目录已存在，请改用新的目录名，不要覆盖历史工程。'
}
& 'D:\ToolsXilinx\Vivado\2020.2\bin\vivado.bat' -mode batch -source .\board_video\scripts\build_board.tcl -log .\vivado_readme.log -journal .\vivado_readme.jou -tclargs "$hardwareBuild"
if ($LASTEXITCODE -ne 0) { throw 'Vivado 构建失败，请检查日志。' }
$xsa = Join-Path $hardwareBuild 'board_video.xsa'
& 'D:\ToolsXilinx\Vitis\2020.2\bin\xsct.bat' .\board_video\scripts\build_app.tcl "$xsa" "$softwareBuild"
if ($LASTEXITCODE -ne 0) { throw 'Vitis 构建失败，请检查日志。' }
```

新产物为 `board_video/build_readme/board_video.bit`、`board_video/build_readme/board_video.xsa` 和 `board_video/vitis_readme/unified_video/Debug/unified_video.elf`。新构建必须重新验证，不能自动继承历史板测结论，也不应直接覆盖 `delivery/`。

不要在当前完整包中直接运行默认的 `scripts/build_integration.py`：它固定使用已有 `build_01/vitis_01` 并拒绝覆盖。旧工作区和部分历史自动化脚本含原机器路径，不保证迁移后可直接增量构建。更多细节见 [完整工程说明](README_Dehazy_final.md)。

## 7. 示例效果与实测结果

### 7.1 固定样本对比

下图来自归档 SOTS outdoor 测试结果，展示有雾输入、V5 去雾结果和清晰参考。样本采用预先固定的零基序号 `0、166、333、499`，不是按最高得分挑选。

![SOTS outdoor 固定四组样本：有雾输入、V5 去雾结果与清晰参考](quality_eval/results/SOTS_outdoor_20261102_231532/comparison_fixed_indices.jpg)

这是**主机参考实现输出**，不是摄像头实拍 TFT 的照片。发布时需要一并提供此相对路径下的图片，并确认图片与数据的公开使用权限。

### 7.2 配对画质结果

| 方法 / 对照 | 平均 PSNR（dB）↑ | 平均 SSIM ↑ |
| --- | ---: | ---: |
| 有雾输入基线（相同 RGB565 量化） | 15.9652 | 0.79766 |
| V5 主机整数参考实现 | **23.9853** | **0.88075** |
| 配对平均变化 | +8.0201 | +0.08309 |

来源：[SUMMARY.json](quality_eval/results/SOTS_outdoor_20261102_231532/SUMMARY.json)、[逐图结果](quality_eval/results/SOTS_outdoor_20261102_231532/per_image.csv) 和 [结果复核](quality_eval/results/SOTS_outdoor_20261102_231532/RESULT_VALIDATION.json)。

评价包含 500 组配对、492 张清晰参考和 453 个内容组，**不是 500 个独立场景**。PSNR 在 492 组上改善，SSIM 在 450 组上改善；所有退化样本均保留，没有据此宣称逐图全部提升。

输入与清晰参考均用 Pillow LANCZOS 缩放至 720 × 480，不裁剪、不自动配准。推理输入/输出经 RGB565 处理，参考保留 RGB888；PSNR 逐图计算后平均。SSIM 使用 RGB、11 × 11 高斯窗、σ=1.5、总体协方差、有效窗口区域和 `data_range=255`。结果不是原生分辨率官方榜单，也不是 500 张图逐张上板测得的画质。

### 7.3 摄像头板级性能

| 测量项目 | 历史记录结果 | 解释 |
| --- | ---: | --- |
| 百帧处理窗口吞吐 | 22.920524 FPS | 100 帧 / 4.362902 秒 |
| 百帧新画面显示帧率 | 23.342774 FPS | 按首末显示时间戳计算，口径不同于处理窗口吞吐 |
| 2026-11-02 保存的持续会话 | 23.051446 FPS | 该会话累计 2,240 个新帧 |

来源：[板级报告](reports/BOARD_REPORT_zh.md)、[板级结果](reports/FINAL_RESULT.json) 和 [持续会话记录](results/realtime_deploy_20261102_234534/FINAL_RUNTIME_RESULT.json)。这些记录不证明长期稳定性、每个采集帧均被处理或每帧全层数值一致。**摄像头整机尚未达到 30 FPS。**

## 8. 已知限制与复现边界

- **平台依赖**：脚本主要面向 Windows、Vivado/Vitis 2020.2 和 AC880；其他系统、器件或工具版本未据此宣称验证通过。
- **训练来源**：完整 V5 训练 checkpoint、训练数据和量化校准来源仍需补齐；SOTS 曾用于历史实验，不能将本结果称为新盲测。
- **硬件签核**：物理 TFT 观感、外部 IO 电气时序、长期稳定性和剩余 4 条 Critical CDC 路径仍需确认；数字链路通过不等于全部工程签核完成。
- **功耗口径**：Vivado 片上功耗估算不是仪器测得的整板功耗。
- **路径与清单**：归档日志、部分脚本和旧工程可能含绝对路径。精简或迁移需要独立验证，不能修改原始证据后继续沿用原通过结论。
- **公开前检查**：作者应明确项目许可证，核查第三方 IP、权重和数据的分发权限，并处理公开包中的设备标识与个人路径。本文不代替许可证，也不表示已完成授权检查。

## 9. 进一步阅读

- [完整工程使用说明](README_Dehazy_final.md)
- [V5 与摄像头/TFT 集成说明](README_集成说明.md)
- [画质测试协议与复核入口](quality_eval/README_画质测试.md)
- [板级测试报告](reports/BOARD_REPORT_zh.md)
- [引脚分配表](reports/PINOUT.csv)

文档整理日期：2026-11-03。。

