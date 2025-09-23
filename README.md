# soundSourceLocalizationGUI 项目说明

本项目是一个基于 PyQt5 和 qfluentwidgets 的语音实验 GUI，集成了硬件采集（HKUSB6203）、多 USB 扬声器播放、在线/离线声源定位（GCC-PHAT）与批量实验数据采集。

- 界面层（view/）：硬件设置、数据集设置、批量实验、在线/离线实验页面
- 设备层（driver/）：HK 采集卡、USB 扬声器与 CMU ARCTIC 数据集封装
- 任务层（task/）：批量实验、在线/离线定位任务
- 算法层（method/）：GCC-PHAT 单声源定位
- 线程封装（thread_manager.py）：通用一次性/循环任务线程
- 应用入口（demo.py）：主窗口与整体逻辑调度

## 目录结构

```
soundSouorceLocalizationGUI/
│
├─ demo.py                 # 应用入口与主窗口
├─ thread_manager.py       # 通用线程封装（FunctionWorker/FunctionLoopWorker）
├─ resource_rc.py          # 资源文件（由 Qt 工具生成）
├─ config.ini              # 参数配置（首次运行自动生成）
│  
├─ driver/                 # 设备抽象与驱动封装
│  ├─ dataset_driver.py    # CMU ARCTIC 数据集封装
│  ├─ hkusb_driver.py      # HKUSB6203 采集卡驱动封装
│  └─ speaker_driver.py    # USB 扬声器管理与播放
│  
├─ method/
│  └─ gcc_phat.py          # GCC-PHAT 单声源定位实现
│  
├─ task/
│  ├─ batch_task.py        # 批量实验任务
│  ├─ online_task.py       # 在线定位任务
│  └─ offline_task.py      # 离线定位任务
├─ view/
│  └─ *.py                 # 各子界面（含 Ui_*.py 自动生成文件）
└─ resource/               # 资源（图片、音乐、ui、qrc）
```

> 说明：`view/Ui_*.py` 与 `resource_rc.py` 为自动生成文件，建议不要手动修改；若使用 Qt Designer 重新导出，会覆盖改动。

## 环境与依赖

请先安装 Python 3.8+（建议 3.9/3.10）与以下依赖：

```
pip install -r requirements.txt
```

requirements.txt（已提供）包含：
- PyQt5
- qfluentwidgets
- numpy
- matplotlib
- sounddevice
- soundfile
- pyroomacoustics
- nara_wpe

> Windows 需要可用的音频设备与 WASAPI 支持；HK 采集卡需正确安装驱动，且项目根目录存在 `Usb_Daq_V52_Dll.dll`。

## 数据准备（CMU ARCTIC）

项目默认在工作目录下寻找 `CMU_ARCTIC/` 数据集结构。请从公开渠道下载 CMU ARCTIC 数据集，并解压到本项目根目录，结构示例：

```
CMU_ARCTIC/
  cmu_us_bdl_arctic/
    wav/ ...
    etc/txt.done.data
  cmu_us_slt_arctic/
  cmu_us_clb_arctic/
  cmu_us_rms_arctic/
```

## 运行

在 Windows 命令提示符执行：

```
cd D:\Workplace\QtProjects\sslGui
python demo.py
```

首次运行将自动生成 `config.ini`。各页面功能：
- 硬件设置：HK 采集卡开关/量程/采样率、USB 扬声器枚举/启用/音量、硬件自检
- 数据集设置：选择说话人组合，预览对应文本，试播
- 批量实验：配置采样时长与语料 ID 序列，按计划依次播放并可选采集保存 `record/.../*.npz`
- 在线实验：配置帧长与方法，实时定位并绘制 3D 散点
- 离线实验：选择 npz 文件，定位结果以 3D + 表格回放

## 常见问题

- 扬声器未被发现：请确认 USB 声卡枚举时设备名称中包含 "USB Audio Device"，且拥有输出通道。
- Matplotlib 3D 图异常：请确认已安装 matplotlib，并使用 Qt5Agg 后端（默认）。
- GCC-PHAT 依赖：`nara_wpe` 提供 stft，安装缓慢可换源或预装对应 wheel。
- HK 采集卡：确保 `Usb_Daq_V52_Dll.dll` 位于项目根目录，且驱动安装完成；若打开失败，界面会提示。

## 代码注释说明

- 本次已为核心 Python 文件补充模块/类/方法级文档注释，遵循 NumPy 风格；
- 自动生成文件（`view/Ui_*.py`、`resource_rc.py`）保留其生成注释，避免与再次生成冲突。

## 开发提示

- 若修改 UI（.ui）文件，请使用 `pyuic5` 重新生成对应 `Ui_*.py`，并重新构建 `resource_rc.py`；
- 建议不要在自动生成文件中编写业务逻辑，保持 `view/*.py` 为自定义界面逻辑层。

