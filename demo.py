# coding:utf-8
"""
应用入口与主窗口

Overview
--------
使用 ``qfluentwidgets`` 的 ``SplitFluentWindow`` 构建五个子界面（硬件/数据集/批量/在线/离线），
子界面各自管理自己的业务逻辑，主窗口负责界面组装、参数加载与跨界面协调。

Notes
-----
- 界面代码与业务解耦：driver/ 提供设备层，task/ 提供任务层，method/ 提供算法层，view/ 提供 UI 及业务逻辑。
- 资源文件在 ``resource/`` 下，由 ``resource_rc.py`` 提供访问。
"""

import os
import sys
from typing import Optional

from PyQt5.QtCore import Qt, QSize, QSettings, QEventLoop, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme, SplitFluentWindow, FluentTranslator, SplashScreen, InfoBar, InfoBarPosition
from qfluentwidgets import FluentIcon as FIF

from view.hardware_interface import HardwareInterface
from view.dataset_interface import DatasetInterface
from view.experiment_interface import ExperimentInterface
from view.array_interface import ArrayInterface
from view.online_interface import OnlineInterface
from view.offline_interface import OfflineInterface

from driver.hkusb_driver import HkDriver
from driver.speaker_driver import SpeakerDriver
from driver.dataset_driver import DatasetDriver

from task.batch_task import BatchTask
from task.array_task import ArrayTask
from task.online_task import OnlineTask
from task.offline_task import OfflineTask

import resource_rc


class Window(SplitFluentWindow):
    """
    主窗口，负责界面组装、参数加载与跨界面协调。

    Attributes
    ----------
    hardwareInterface, datasetInterface, experimentInterface, onlineInterface, offlineInterface : QWidget
        五个子界面实例。
    hkDriver : HkDriver
        采集卡驱动。
    speakerDriver : SpeakerDriver
        扬声器驱动。
    datasetDriver : DatasetDriver
        数据集驱动。
    batchTask : BatchTask
        批量任务。
    onlineTask : OnlineTask
        在线任务。
    offlineTask : OfflineTask
        离线任务。

    Notes
    -----
    生命周期：
    1) 构造界面与导航 -> 2) 读取参数并回显 -> 3) 绑定槽函数 -> 4) 等待用户操作。
    """

    def __init__(self):
        super().__init__()

        # create sub interface
        self.hardwareInterface = HardwareInterface(self)
        self.datasetInterface = DatasetInterface(self)
        self.experimentInterface = ExperimentInterface(self)
        self.arrayInterface = ArrayInterface(self)
        self.onlineInterface = OnlineInterface(self)
        self.offlineInterface = OfflineInterface(self)

        # create navigation
        self.initNavigation()

        # set the main interface
        self.initWindow()

        # create splash screen and show window
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(102, 102))
        self.show()
        loop = QEventLoop(self)
        QTimer.singleShot(200, loop.quit)
        loop.exec()

        # set the param
        self.paramConfig: Optional[QSettings] = None
        self.hkDriver = HkDriver()
        self.speakerDriver = SpeakerDriver()
        self.datasetDriver = DatasetDriver()

        self.batchTask = BatchTask(self.hkDriver, self.speakerDriver, self.datasetDriver)
        self.arrayTask = ArrayTask()
        self.onlineTask = OnlineTask(self.hkDriver)
        self.offlineTask = OfflineTask()

        # 注入驱动和任务到各个子界面
        self.injectDependencies()

        self.initParam()
        self.initDisplay()
        self.initSlot()

        # close splash screen
        self.splashScreen.finish()

    def initSettings(self):
        self.paramConfig = QSettings('config.ini', QSettings.IniFormat)
        # 更新各个子界面的paramConfig引用
        self.hardwareInterface.setParamConfig(self.paramConfig)
        self.experimentInterface.setParamConfig(self.paramConfig)
        self.arrayInterface.setParamConfig(self.paramConfig)
        self.onlineInterface.setParamConfig(self.paramConfig)
        self.offlineInterface.setParamConfig(self.paramConfig)

    def injectDependencies(self):
        """
        将驱动和任务注入到各个子界面。
        """
        # HardwareInterface
        self.hardwareInterface.setDrivers(self.hkDriver, self.speakerDriver, self.datasetDriver)

        # DatasetInterface
        self.datasetInterface.setDrivers(self.datasetDriver, self.speakerDriver)

        # ExperimentInterface
        self.experimentInterface.setBatchTask(self.batchTask)

        # ArrayInterface
        self.arrayInterface.setArrayTask(self.arrayTask)

        # OnlineInterface
        self.onlineInterface.setOnlineTask(self.onlineTask, self.arrayTask)
        self.onlineInterface.setDrivers(self.hkDriver, self.datasetDriver)

        # OfflineInterface
        self.offlineInterface.setOfflineTask(self.offlineTask, self.arrayTask)

    def initNavigation(self):
        # add sub interface
        self.addSubInterface(self.hardwareInterface, FIF.DEVELOPER_TOOLS, '硬件设置', )
        self.addSubInterface(self.datasetInterface, FIF.MEDIA, '语音数据集设置')
        self.addSubInterface(self.experimentInterface, FIF.ROTATE, '批量实验')
        self.addSubInterface(self.arrayInterface, FIF.MICROPHONE, '麦克风阵列设置')
        self.addSubInterface(self.onlineInterface, FIF.CLOUD, '在线实验')
        self.addSubInterface(self.offlineInterface, FIF.PAGE_RIGHT, '离线实验')

        self.navigationInterface.setExpandWidth(280)

    def initWindow(self):
        self.resize(900, 700)
        self.setWindowIcon(QIcon(':/images/logo.ico'))
        self.setWindowTitle('浮力工业')

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def initParam(self):
        # load settings
        if not os.path.exists('config.ini'):
            InfoBar.info(
                title='[参数加载]',
                content='创建配置文件 config.ini',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=-1,
                parent=self
            )

            self.initSettings()
            # init the paramConfig
            self.hkDriver.param.resetParamOfConfig(self.paramConfig)
            self.batchTask.param.resetParamOfConfig(self.paramConfig)
            self.onlineTask.param.resetParamOfConfig(self.paramConfig)
            self.offlineTask.param.resetParamOfConfig(self.paramConfig)
        else:
            self.initSettings()

            if self.hkDriver.param.validParamOfConfig(self.paramConfig):
                self.hkDriver.param.loadParamFromConfig(self.paramConfig)
            else:
                InfoBar.warning(
                    title='[参数加载]',
                    content='HK驱动参数不合法，已重置',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=-1,
                    parent=self
                )
                self.hkDriver.param.resetParamOfConfig(self.paramConfig)

            if self.batchTask.param.validParamOfConfig(self.paramConfig):
                self.batchTask.param.loadParamFromConfig(self.paramConfig)
            else:
                InfoBar.warning(
                    title='[参数加载]',
                    content='批量实验参数不合法，已重置',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=-1,
                    parent=self
                )
                self.batchTask.param.resetParamOfConfig(self.paramConfig)

            if self.arrayTask.param.validParamOfConfig(self.paramConfig):
                self.arrayTask.param.loadParamFromConfig(self.paramConfig)
            else:
                InfoBar.warning(
                    title='[参数加载]',
                    content='麦克风阵列参数不合法，已重置',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=-1,
                    parent=self
                )
                self.arrayTask.param.resetParamOfConfig(self.paramConfig)

            if self.onlineTask.param.validParamOfConfig(self.paramConfig):
                self.onlineTask.param.loadParamFromConfig(self.paramConfig)
            else:
                InfoBar.warning(
                    title='[参数加载]',
                    content='在线实验参数不合法，已重置',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=-1,
                    parent=self
                )
                self.onlineTask.param.resetParamOfConfig(self.paramConfig)

            if self.offlineTask.param.validParamOfConfig(self.paramConfig):
                self.offlineTask.param.loadParamFromConfig(self.paramConfig)
            else:
                InfoBar.warning(
                    title='[参数加载]',
                    content='离线实验参数不合法，已重置',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=-1,
                    parent=self
                )
                self.offlineTask.param.resetParamOfConfig(self.paramConfig)

    def initDisplay(self):
        # 初始化各个子界面的显示
        self.arrayInterface.initSetTable()
        self.arrayInterface.initCondTable()
        self.arrayInterface.initScatter()
        self.onlineInterface.initScatter()
        self.offlineInterface.initTable()
        self.offlineInterface.initScatter()

        # 回显参数
        self.hardwareInterface.displayValueHK()
        self.datasetInterface.initValueDataset()
        self.datasetInterface.displayValueDataset()
        # 同步显示到onlineInterface
        playTextBrowserMarkdown = self.datasetInterface.getPlayTextBrowserMarkdown(self.datasetInterface.playSpinBox.value())
        self.onlineInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)

        self.stateCardDisplay()
        self.experimentInterface.displayValueBatch()
        self.onlineInterface.initValueOnline()
        self.onlineInterface.displayValueOnline()
        self.offlineInterface.initValueOffline()
        self.offlineInterface.displayValueOffline()

    def initSlot(self):
        # 初始化各个子界面的槽函数
        self.hardwareInterface.initSlot()
        self.datasetInterface.initSlot()
        self.experimentInterface.initSlot()
        self.arrayInterface.initSlot()
        self.onlineInterface.initSlot()
        self.offlineInterface.initSlot()

        # 跨界面信号连接
        # HardwareInterface信号
        self.hardwareInterface.speakerDeviceChanged.connect(self.onSpeakerDeviceChanged)
        self.hardwareInterface.stateChanged.connect(self.stateCardDisplay)

        # DatasetInterface信号
        self.datasetInterface.stateChanged.connect(self.stateCardDisplay)
        self.datasetInterface.playSpinBoxValueChanged.connect(self.onDatasetPlaySpinBoxChanged)

        # OnlineInterface的playSpinBox变化需要同步到DatasetInterface
        self.onlineInterface.playSpinBoxValueChanged.connect(self.onOnlinePlaySpinBoxChanged)

        # OnlineInterface的playPushButton复用DatasetInterface的播放功能
        self.onlineInterface.playPushButton.clicked.connect(self.datasetInterface.datasetPlayPushButtonClicked)

    def onSpeakerDeviceChanged(self):
        """
        扬声器设备变化时的处理。
        """
        playTextBrowserMarkdown = self.datasetInterface.displayValueDataset()
        self.onlineInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)

    def onDatasetPlaySpinBoxChanged(self, value: int):
        """
        DatasetInterface的playSpinBox值变化时，同步到OnlineInterface。
        """
        self.onlineInterface.playSpinBox.blockSignals(True)
        self.onlineInterface.playSpinBox.setValue(value)
        self.onlineInterface.playSpinBox.blockSignals(False)

        playTextBrowserMarkdown = self.datasetInterface.getPlayTextBrowserMarkdown(value)
        self.onlineInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)

    def onOnlinePlaySpinBoxChanged(self, value: int):
        """
        OnlineInterface的playSpinBox值变化时，同步到DatasetInterface。
        """
        self.datasetInterface.playSpinBox.blockSignals(True)
        self.datasetInterface.playSpinBox.setValue(value)
        self.datasetInterface.playSpinBox.blockSignals(False)

        playTextBrowserMarkdown = self.datasetInterface.getPlayTextBrowserMarkdown(value)
        self.datasetInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)

    def stateCardDisplay(self):
        """
        更新各个界面的状态卡显示。
        """
        sampleUsage = self.hkDriver.param.getUsage()
        sampleRangeCode = self.hkDriver.param.getRangeCode()
        sampleRate = self.hkDriver.param.getSampleRate()

        usedDeviceIndexList = self.speakerDriver.getUsedDeviceIndexList()
        deviceItemList = self.speakerDriver.getDeviceItemList()

        usedSpeakerIndexList = self.datasetDriver.getUsedSpeakerIndexList()
        correspondingSpeakerNameList = self.datasetDriver.getCorrespondingSpeakerNameList()
        stateBrowserMarkdown = ""
        if sampleUsage == 1:
            stateBrowserMarkdown += "#### 🎛️**采集卡电压范围**: "
            if sampleRangeCode == 1:
                stateBrowserMarkdown += "±10 V\n"
            else:
                stateBrowserMarkdown += "±5 V\n"
            stateBrowserMarkdown += "#### 🎚️**采集卡采样率**: " + str(sampleRate) + " Hz\n"

        for usedDeviceIndex, usedSpeakerIndex in zip(usedDeviceIndexList, usedSpeakerIndexList):
            stateBrowserMarkdown += "#### 🔈️**扬声器**: " + str(usedDeviceIndex) + " ,"+ deviceItemList[usedDeviceIndex].getDeviceName() + "\n"
            stateBrowserMarkdown += " * 音量: " + str(deviceItemList[usedDeviceIndex].getVolume()) + " | 说话人: " + correspondingSpeakerNameList[usedSpeakerIndex] + "\n"
        self.datasetInterface.stateBrowser.setMarkdown(stateBrowserMarkdown)
        self.experimentInterface.stateBrowser.setMarkdown(stateBrowserMarkdown)
        self.onlineInterface.stateBrowser.setMarkdown(stateBrowserMarkdown)

    # 跨界面的UI冻结/解冻方法
    def sampleRelatedCardFrozen(self):
        self.hardwareInterface.sampleCardFrozen()
        self.hardwareInterface.taskCardFrozen()
        self.experimentInterface.batchCardFrozen()
        self.onlineInterface.setCardFrozen()

    def sampleRelatedCardUnfrozen(self):
        self.hardwareInterface.sampleCardUnfrozen()
        self.hardwareInterface.taskCardUnfrozen()
        self.experimentInterface.batchCardUnfrozen()
        self.onlineInterface.setCardUnfrozen()

    def speakerRelatedCardFrozen(self):
        self.hardwareInterface.speakerCardFrozen()
        self.hardwareInterface.taskCardFrozen()
        self.datasetInterface.signalCardFrozen()
        self.datasetInterface.playCardFrozen()
        self.onlineInterface.playCardFrozen()
        self.experimentInterface.batchCardFrozen()

    def speakerRelatedCardUnfrozen(self):
        self.hardwareInterface.speakerCardUnfrozen()
        self.hardwareInterface.taskCardUnfrozen()
        self.datasetInterface.signalCardUnfrozen()
        self.datasetInterface.playCardUnfrozen()
        self.onlineInterface.playCardUnfrozen()
        self.experimentInterface.batchCardUnfrozen()

    def arrayRelatedCardFrozen(self):
        self.arrayInterface.setCardFrozen()
        self.arrayInterface.condCardFrozen()

    def arrayRelatedCardUnfrozen(self):
        self.arrayInterface.setCardUnfrozen()
        self.arrayInterface.condCardUnfrozen()

if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    setTheme(Theme.AUTO)

    app = QApplication(sys.argv)

    # install translator
    translator = FluentTranslator()
    app.installTranslator(translator)

    w = Window()
    w.show()
    app.exec_()
