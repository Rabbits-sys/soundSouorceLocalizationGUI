# coding:utf-8
"""
应用入口与主窗口

Overview
--------
使用 ``qfluentwidgets`` 的 ``SplitFluentWindow`` 构建五个子界面（硬件/数据集/批量/在线/离线），
通过 ``thread_manager`` 中的通用线程封装异步执行硬件操作与算法计算，并将参数持久化到 ``config.ini``。

Notes
-----
- 界面代码与业务解耦：driver/ 提供设备层，task/ 提供任务层，method/ 提供算法层，view/ 提供纯 UI。
- 资源文件在 ``resource/`` 下，由 ``resource_rc.py`` 提供访问。
"""

import os
import sys
from typing import Optional

from PyQt5.QtCore import Qt, QSize, QSettings, QEventLoop, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QFileDialog
from qfluentwidgets import (setTheme, Theme, SplitFluentWindow, FluentTranslator, SplashScreen, InfoBar, InfoBarPosition, InfoBarIcon)
from qfluentwidgets import FluentIcon as FIF

from thread_manager import FunctionWorker, FunctionLoopWorker

from view.hardware_interface import HardwareInterface
from view.dataset_interface import DatasetInterface
from view.experiment_interface import ExperimentInterface
from view.online_interface import OnlineInterface
from view.offline_interface import OfflineInterface

from driver.hkusb_driver import HkDriver
from driver.speaker_driver import SpeakerDriver
from driver.dataset_driver import DatasetDriver

from task.batch_task import BatchTask
from task.online_task import OnlineTask
from task.offline_task import OfflineTask

import resource_rc

class Window(SplitFluentWindow):
    """
    主窗口，负责界面组装、参数加载、信号槽绑定与任务调度。

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
        # running flag
        self.speakerBusyFlag = False
        self.sampleBusyFlag = False

        self.speakerTestSingleWorker: Optional[FunctionWorker] = None
        self.sampleTestUsbWorker: Optional[FunctionWorker] = None
        self.speakerTestMultiWorker: Optional[FunctionWorker] = None
        self.sampleTestSampleWorker: Optional[FunctionWorker] = None
        self.datasetPlatWorker: Optional[FunctionWorker] = None

        self.batchTaskWorker: Optional[FunctionLoopWorker] = None
        self.onlineTaskWorker: Optional[FunctionLoopWorker] = None
        self.offlineTaskWorker: Optional[FunctionWorker] = None

        # create sub interface
        self.hardwareInterface = HardwareInterface(self)
        self.datasetInterface = DatasetInterface(self)
        self.experimentInterface = ExperimentInterface(self)
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
        self.onlineTask = OnlineTask(self.hkDriver)
        self.offlineTask = OfflineTask()

        self.initParam()
        self.initDisplay()
        self.initSlot()

        # close splash screen
        self.splashScreen.finish()

    def initSettings(self):
        self.paramConfig = QSettings('config.ini', QSettings.IniFormat)

    def initNavigation(self):
        # add sub interface
        self.addSubInterface(self.hardwareInterface, FIF.DEVELOPER_TOOLS, '硬件设置', )
        self.addSubInterface(self.datasetInterface, FIF.MEDIA, '语音数据集设置')
        self.addSubInterface(self.experimentInterface, FIF.ROTATE, '批量实验')
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
        self.onlineInterface.initScatter()
        self.offlineInterface.initTable()
        self.offlineInterface.initScatter()

        self.displayValueHK()
        self.initValueDataset()
        self.displayValueDataset()
        self.stateCardDisplay()
        self.displayValueBatch()
        self.initValueOnline()
        self.displayValueOnline()
        self.initValueOffline()
        self.displayValueOffline()

    def initSlot(self):
        # the slots below hardware_interface/sampleCard
        self.hardwareInterface.sampleReloadButton.clicked.connect(self.sampleReloadButtonClicked)
        self.hardwareInterface.sampleSaveButton.clicked.connect(self.sampleSaveButtonClicked)
        self.hardwareInterface.sampleUsageSwitchButton.checkedChanged.connect(lambda checked: self.sampleUsageSwitchButtonChanged(checked))
        self.hardwareInterface.sampleVoltageButton_1.clicked.connect(lambda _: self.sampleVoltageButtonClicked(0))
        self.hardwareInterface.sampleVoltageButton_2.clicked.connect(lambda _: self.sampleVoltageButtonClicked(1))
        self.hardwareInterface.sampleRateSpinBox.valueChanged.connect(lambda value: self.sampleRateSpinBoxChanged(value))

        # the slots below hardware_interface/speakerCard
        self.hardwareInterface.speakerPushButton.clicked.connect(self.speakerPushButtonClicked)
        self.hardwareInterface.speakerComboBox.currentIndexChanged.connect(lambda currentIndex: self.speakerComboBoxChanged(currentIndex))
        self.hardwareInterface.speakerSwitchButton.checkedChanged.connect(lambda checked: self.speakerSwitchButtonChanged(checked))
        self.hardwareInterface.speakerHorizontalSlider.valueChanged.connect(lambda value: self.speakerHorizontalSliderChanged(value))
        self.hardwareInterface.speakerTestButton.clicked.connect(self.speakerTestButtonClicked)

        # the slots below hardware_interface/taskCard
        self.hardwareInterface.taskCard_1.clicked.connect(self.taskCard1Clicked)
        self.hardwareInterface.taskCard_2.clicked.connect(self.taskCard2Clicked)
        self.hardwareInterface.taskCard_3.clicked.connect(self.taskCard3Clicked)

        # the slots below dataset_interface/signalCard
        self.datasetInterface.signalCheckBox_1.clicked.connect(self.datasetSignalCheckBox1Changed)
        self.datasetInterface.signalCheckBox_2.clicked.connect(self.datasetSignalCheckBox2Changed)
        self.datasetInterface.signalCheckBox_3.clicked.connect(self.datasetSignalCheckBox3Changed)
        self.datasetInterface.signalCheckBox_4.clicked.connect(self.datasetSignalCheckBox4Changed)

        # the slots below dataset_interface/playCard
        self.datasetInterface.playSpinBox.valueChanged.connect(lambda value: self.datasetPlaySpinBoxChanged(value))
        self.datasetInterface.playPushButton.clicked.connect(self.datasetPlayPushButtonClicked)

        # the slots below experiment_interface/batchCard
        self.experimentInterface.batchReloadButton.clicked.connect(self.batchReloadButtonClicked)
        self.experimentInterface.batchSaveButton.clicked.connect(self.batchSaveButtonClicked)
        self.experimentInterface.batchDoubleSpinBox.valueChanged.connect(lambda value: self.batchDoubleSpinBoxChanged(value))
        self.experimentInterface.batchPlainTextEdit.textChanged.connect(self.batchPlainTextEditChanged)
        self.experimentInterface.batchStartButton.toggled.connect(lambda checked: self.batchStartButtonClicked(checked))

        # the slots below online_interface/setCard
        self.onlineInterface.setReloadButton.clicked.connect(self.onlineReloadButtonClicked)
        self.onlineInterface.setSaveButton.clicked.connect(self.onlineSaveButtonClicked)
        self.onlineInterface.setComboBox_1.currentIndexChanged.connect(lambda currentIndex: self.onlineComboBox1Changed(currentIndex))
        self.onlineInterface.setComboBox_2.currentIndexChanged.connect(lambda currentIndex: self.onlineComboBox2Changed(currentIndex))
        self.onlineInterface.setStartButton.toggled.connect(lambda checked: self.onlineStartButtonClicked(checked))

        # the slot below online_interface/playCard
        self.onlineInterface.playSpinBox.valueChanged.connect(lambda value: self.onlinePlaySpinBoxChanged(value))
        self.onlineInterface.playPushButton.clicked.connect(self.datasetPlayPushButtonClicked)

        # the slot below offline_interface/setCard
        self.offlineInterface.setReloadButton.clicked.connect(self.offlineReloadButtonClicked)
        self.offlineInterface.setSaveButton.clicked.connect(self.offlineSaveButtonClicked)
        self.offlineInterface.setChooseFileCard.clicked.connect(self.offlineSetChooseFileClicked)
        self.offlineInterface.setStartButton.clicked.connect(self.offlineSetStartButtonClicked)
        self.offlineInterface.resultHorizontalSlider.valueChanged.connect(lambda value: self.offlineResultHorizontalSliderChanged(value))

    def displayValueHK(self):
        # block the signal
        self.hardwareInterface.sampleUsageSwitchButton.blockSignals(True)
        self.hardwareInterface.sampleVoltageButton_1.blockSignals(True)
        self.hardwareInterface.sampleVoltageButton_2.blockSignals(True)
        self.hardwareInterface.sampleRateSpinBox.blockSignals(True)
        # display the values below hardware_interface/sampleCard
        self.hardwareInterface.sampleUsageSwitchButton.setChecked(self.hkDriver.param.getUsage())
        self.hardwareInterface.sampleVoltageButton_1.setChecked(not self.hkDriver.param.getRangeCode())
        self.hardwareInterface.sampleVoltageButton_2.setChecked(self.hkDriver.param.getRangeCode())
        self.hardwareInterface.sampleRateSpinBox.setValue(self.hkDriver.param.getSampleRate())
        # unblock the signal
        self.hardwareInterface.sampleUsageSwitchButton.blockSignals(False)
        self.hardwareInterface.sampleVoltageButton_1.blockSignals(False)
        self.hardwareInterface.sampleVoltageButton_2.blockSignals(False)
        self.hardwareInterface.sampleRateSpinBox.blockSignals(False)

    def initValueDataset(self):
        self.datasetInterface.signalComboBox.addItems(['扬声器-说话人对应(不同说话人不同语料)'])
        self.datasetInterface.signalComboBox.setCurrentIndex(0)

    def displayValueDataset(self):
        usedSpeakerIndexList = self.datasetDriver.getUsedSpeakerIndexList()

        if 0 in usedSpeakerIndexList:
            self.datasetInterface.signalCheckBox_1.setChecked(True)
        else:
            self.datasetInterface.signalCheckBox_1.setChecked(False)
        if 1 in usedSpeakerIndexList:
            self.datasetInterface.signalCheckBox_2.setChecked(True)
        else:
            self.datasetInterface.signalCheckBox_2.setChecked(False)
        if 2 in usedSpeakerIndexList:
            self.datasetInterface.signalCheckBox_3.setChecked(True)
        else:
            self.datasetInterface.signalCheckBox_3.setChecked(False)
        if 3 in usedSpeakerIndexList:
            self.datasetInterface.signalCheckBox_4.setChecked(True)
        else:
            self.datasetInterface.signalCheckBox_4.setChecked(False)

        speakerTextIndex = self.datasetInterface.playSpinBox.value()
        playTextBrowserMarkdown = ""
        usedSpeakerIndexList = self.datasetDriver.getUsedSpeakerIndexList()
        speakerTextList = self.datasetDriver.getSpeakerTextList(speakerTextIndex)
        correspondingSpeakerNameList = self.datasetDriver.getCorrespondingSpeakerNameList()
        for usedSpeakerIndex, speakerText in zip(usedSpeakerIndexList, speakerTextList):
            playTextBrowserMarkdown += "#### **" + correspondingSpeakerNameList[usedSpeakerIndex] + "**: " + speakerText + "\n"
        self.datasetInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)
        self.onlineInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)

    def displayValueBatch(self):
        self.experimentInterface.batchDoubleSpinBox.blockSignals(True)
        self.experimentInterface.batchPlainTextEdit.blockSignals(True)
        self.experimentInterface.batchDoubleSpinBox.setValue(self.batchTask.param.getSampleTime())
        self.experimentInterface.batchPlainTextEdit.setPlainText(self.batchTask.param.getSpeakerDataIndexString())
        self.experimentInterface.batchDoubleSpinBox.blockSignals(False)
        self.experimentInterface.batchPlainTextEdit.blockSignals(False)

    def initValueOnline(self):
        self.onlineInterface.setComboBox_1.addItems([str(frameLen) for frameLen in self.onlineTask.param.getFrameLenList()])
        self.onlineInterface.setComboBox_2.addItems(['GCC-PHAT单声源定位'])

    def displayValueOnline(self):
        self.onlineInterface.setComboBox_1.setCurrentIndex(self.onlineTask.param.getFrameLenCode())
        self.onlineInterface.setComboBox_2.setCurrentIndex(self.onlineTask.param.getMethodCode())

    def initValueOffline(self):
        self.offlineInterface.setComboBox.addItems(['GCC-PHAT单声源定位'])

    def displayValueOffline(self):
        self.offlineInterface.setComboBox.setCurrentIndex(self.offlineTask.param.getMethodCode())

    # the slot functions below hardware_interface/sampleCard
    def sampleReloadButtonClicked(self):
        self.initSettings()
        if self.hkDriver.param.validParamOfConfig(self.paramConfig):
            self.hkDriver.param.loadParamFromConfig(self.paramConfig)
        else:
            InfoBar.warning(
                title='[参数加载]',
                content='HK驱动参数非法改动，已重置',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            self.hkDriver.param.resetParamOfConfig(self.paramConfig)
        self.displayValueHK()
        self.hardwareInterface.taskIcon_3.setIcon(InfoBarIcon.WARNING)
        self.stateCardDisplay()

    def sampleSaveButtonClicked(self):
        self.initSettings()
        self.hkDriver.param.saveParamToConfig(self.paramConfig)
        self.stateCardDisplay()

    def sampleUsageSwitchButtonChanged(self, checked: bool):
        self.hkDriver.param.setUsage(int(checked))
        self.stateCardDisplay()

    def sampleVoltageButtonClicked(self, rangeCode: int):
        self.hkDriver.param.setRangeCode(rangeCode)
        self.hardwareInterface.taskIcon_3.setIcon(InfoBarIcon.WARNING)
        self.stateCardDisplay()

    def sampleRateSpinBoxChanged(self, value: int):
        self.hkDriver.param.setSampleRate(value)
        self.hardwareInterface.taskIcon_3.setIcon(InfoBarIcon.WARNING)
        self.stateCardDisplay()

    # the slot functions below hardware_interface/speakerCard
    def speakerPushButtonClicked(self):
        self.hardwareInterface.speakerComboBox.clear()
        self.speakerDriver.resetDeviceUsage()
        self.speakerDriver.searchUsbSoundcard()
        deviceNameList = [device.getDeviceName() for device in self.speakerDriver.getDeviceItemList()]
        self.hardwareInterface.speakerComboBox.addItems(deviceNameList)
        self.hardwareInterface.speakerComboBox.setCurrentIndex(-1)

        # block the signal
        self.hardwareInterface.speakerSwitchButton.blockSignals(True)
        # init the state of hardware_interface/speakerCard
        self.hardwareInterface.speakerTestButton.setEnabled(False)
        self.hardwareInterface.speakerSwitchButton.setEnabled(False)
        self.hardwareInterface.speakerHorizontalSlider.setEnabled(False)
        # init the value of hardware_interface/speakerCard
        self.hardwareInterface.speakerSwitchButton.setChecked(False)
        self.hardwareInterface.speakerHorizontalSlider.setValue(100)
        # unblock the signal
        self.hardwareInterface.speakerSwitchButton.blockSignals(False)

        self.datasetDriver.initSpeakerUsage(self.speakerDriver.getDeviceUsedNum())
        self.displayValueDataset()
        self.hardwareInterface.taskIcon_2.setIcon(InfoBarIcon.WARNING)
        self.stateCardDisplay()

    def speakerComboBoxChanged(self, currentIndex: int):
        if currentIndex == -1:
            # reinit the state of hardware_interface/speakerCard
            self.hardwareInterface.speakerTestButton.setEnabled(False)
            self.hardwareInterface.speakerSwitchButton.setEnabled(False)
            self.hardwareInterface.speakerHorizontalSlider.setEnabled(False)
        else:
            # change the state of hardware_interface/speakerCard
            self.hardwareInterface.speakerTestButton.setEnabled(True)
            self.hardwareInterface.speakerSwitchButton.setEnabled(True)
            self.hardwareInterface.speakerHorizontalSlider.setEnabled(True)
            self.hardwareInterface.speakerHorizontalSlider.setEnabled(True)

            deviceItemList = self.speakerDriver.getDeviceItemList()
            # block the signal
            self.hardwareInterface.speakerSwitchButton.blockSignals(True)
            # display the value of hardware_interface/speakerCard
            self.hardwareInterface.speakerSwitchButton.setChecked(deviceItemList[currentIndex].getUsage())
            self.hardwareInterface.speakerHorizontalSlider.setValue(deviceItemList[currentIndex].getVolume())
            # unblock the signal
            self.hardwareInterface.speakerSwitchButton.blockSignals(False)

    def speakerSwitchButtonChanged(self, checked: bool):
        deviceIndex = self.hardwareInterface.speakerComboBox.currentIndex()
        if deviceIndex != -1:
            if checked:
                ret = self.speakerDriver.addDeviceUsage(deviceIndex)
                if not ret:
                    # block the signal
                    self.hardwareInterface.speakerSwitchButton.blockSignals(True)
                    # reset the value of switch button
                    self.hardwareInterface.speakerSwitchButton.setChecked(False)
                    # unblock the signal
                    self.hardwareInterface.speakerSwitchButton.blockSignals(False)

                    InfoBar.info(
                        title='[扬声器选取]',
                        content='选取扬声器数量已达上限(4个)，若要选取\n选中扬声器请取消其他扬声器的选择。',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
            else:
                ret = self.speakerDriver.subDeviceUsage(deviceIndex)
                if not ret:
                    # block the signal
                    self.hardwareInterface.speakerSwitchButton.blockSignals(True)
                    # reset the value of switch button
                    self.hardwareInterface.speakerSwitchButton.setChecked(True)
                    # unblock the signal
                    self.hardwareInterface.speakerSwitchButton.blockSignals(False)

                    InfoBar.warning(
                        title='[扬声器选取]',
                        content='非法取消扬声器选中。',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
            self.datasetDriver.initSpeakerUsage(self.speakerDriver.getDeviceUsedNum())
            self.displayValueDataset()
            self.hardwareInterface.taskIcon_2.setIcon(InfoBarIcon.WARNING)
            self.stateCardDisplay()

    def speakerHorizontalSliderChanged(self, value: int):
        deviceIndex = self.hardwareInterface.speakerComboBox.currentIndex()
        if deviceIndex != -1:
            deviceItemList = self.speakerDriver.getDeviceItemList()
            deviceItemList[deviceIndex].setVolume(value)
            self.hardwareInterface.taskIcon_2.setIcon(InfoBarIcon.WARNING)
            self.stateCardDisplay()

    def speakerTestButtonClicked(self):
        deviceIndex = self.hardwareInterface.speakerComboBox.currentIndex()
        if deviceIndex != -1:
            if self.speakerBusyFlag:
                InfoBar.warning(
                    title='[硬件测试]',
                    content='扬声器被占用，请稍后再试。',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
            else:
                self.speakerBusyFlag = True
                self.speakerRelatedCardFrozen()
                # create a thread to test the speaker
                self.speakerTestSingleWorker = FunctionWorker(self.speakerDriver.playTestSingle, deviceIndex)
                self.speakerTestSingleWorker.signals.result.connect(self.speakerTestButtonThreadFinished)
                self.speakerTestSingleWorker.signals.error.connect(self.speakerTestButtonThreadError)
                self.speakerTestSingleWorker.start()

    def speakerTestButtonThreadFinished(self):
        self.speakerBusyFlag = False
        self.speakerRelatedCardUnfrozen()
        self.speakerTestSingleWorker.signals.result.disconnect()
        self.speakerTestSingleWorker.signals.error.disconnect()
        self.speakerTestSingleWorker = None
        InfoBar.success(
            title='[硬件测试]',
            content='扬声器试播完成',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    def speakerTestButtonThreadError(self):
        self.speakerBusyFlag = False
        self.speakerRelatedCardUnfrozen()
        self.speakerTestSingleWorker.signals.result.disconnect()
        self.speakerTestSingleWorker.signals.error.disconnect()
        self.speakerTestSingleWorker = None

        InfoBar.error(
            title='[硬件测试]',
            content='扬声器试播失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    # the slot functions below hardware_interface/taskCard
    def taskCard1Clicked(self):
        if self.sampleBusyFlag:
            InfoBar.warning(
                title='[硬件测试]',
                content='采集卡被占用，请稍后再试。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            self.sampleBusyFlag = True
            self.sampleRelatedCardFrozen()
            # create a thread to test the sample card
            self.sampleTestUsbWorker = FunctionWorker(self.hkDriver.testUsbConnect)
            self.sampleTestUsbWorker.signals.result.connect(lambda result: self.taskCard1ThreadFinished(result))
            self.sampleTestUsbWorker.signals.error.connect(self.taskCard1ThreadError)
            self.sampleTestUsbWorker.start()

    def taskCard1ThreadFinished(self, result):
        self.sampleBusyFlag = False
        self.sampleRelatedCardUnfrozen()
        self.sampleTestUsbWorker.signals.result.disconnect()
        self.sampleTestUsbWorker.signals.error.disconnect()
        self.sampleTestUsbWorker = None
        if result:
            self.hardwareInterface.taskIcon_1.setIcon(InfoBarIcon.SUCCESS)
            InfoBar.success(
                title='[硬件测试]',
                content='采集卡USB测试完成',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            self.hardwareInterface.taskIcon_1.setIcon(InfoBarIcon.WARNING)
            InfoBar.info(
                title='[硬件测试]',
                content='未检测到采集卡',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )

    def taskCard1ThreadError(self):
        self.sampleBusyFlag = False
        self.sampleRelatedCardUnfrozen()
        self.sampleTestUsbWorker.signals.result.disconnect()
        self.sampleTestUsbWorker.signals.error.disconnect()
        self.sampleTestUsbWorker = None
        self.hardwareInterface.taskIcon_1.setIcon(InfoBarIcon.ERROR)
        InfoBar.error(
            title='[硬件测试]',
            content='采集卡USB测试失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    def taskCard2Clicked(self):
        if self.speakerBusyFlag:
            InfoBar.warning(
                title='[硬件测试]',
                content='扬声器被占用，请稍后再试。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            self.speakerBusyFlag = True
            self.speakerRelatedCardFrozen()
            # create a thread to test the speaker
            self.speakerTestMultiWorker = FunctionWorker(self.speakerDriver.playTestMulti)
            self.speakerTestMultiWorker.signals.result.connect(self.taskCard2ThreadFinished)
            self.speakerTestMultiWorker.signals.error.connect(self.taskCard2ThreadError)
            self.speakerTestMultiWorker.start()

    def taskCard2ThreadFinished(self):
        self.speakerBusyFlag = False
        self.speakerRelatedCardUnfrozen()
        self.speakerTestMultiWorker.signals.result.disconnect()
        self.speakerTestMultiWorker.signals.error.disconnect()
        self.speakerTestMultiWorker = None
        self.hardwareInterface.taskIcon_2.setIcon(InfoBarIcon.SUCCESS)
        InfoBar.success(
            title='[硬件测试]',
            content='扬声器依次播放测试完成',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    def taskCard2ThreadError(self):
        self.speakerBusyFlag = False
        self.speakerRelatedCardUnfrozen()
        self.speakerTestMultiWorker.signals.result.disconnect()
        self.speakerTestMultiWorker.signals.error.disconnect()
        self.speakerTestMultiWorker = None
        self.hardwareInterface.taskIcon_2.setIcon(InfoBarIcon.ERROR)
        InfoBar.error(
            title='[硬件测试]',
            content='扬声器依次播放测试失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    def taskCard3Clicked(self):
        if self.sampleBusyFlag or self.sampleBusyFlag:
            InfoBar.warning(
                title='[硬件测试]',
                content='硬件被占用，请稍后再试。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            self.sampleBusyFlag = True
            self.speakerBusyFlag = True
            self.sampleRelatedCardFrozen()
            self.speakerRelatedCardFrozen()
            # create a thread to test the sample card
            self.sampleTestSampleWorker = FunctionWorker(self.hkDriver.testSampleBuffer)
            self.sampleTestSampleWorker.signals.result.connect(lambda result: self.taskCard3ThreadFinished(result))
            self.sampleTestSampleWorker.signals.error.connect(self.taskCard3ThreadError)
            self.sampleTestSampleWorker.start()

    def taskCard3ThreadFinished(self, result):
        self.sampleBusyFlag = False
        self.speakerBusyFlag = False
        self.sampleRelatedCardUnfrozen()
        self.speakerRelatedCardUnfrozen()
        self.sampleTestSampleWorker.signals.result.disconnect()
        self.sampleTestSampleWorker.signals.error.disconnect()
        self.sampleTestSampleWorker = None
        if result:
            self.hardwareInterface.taskIcon_3.setIcon(InfoBarIcon.SUCCESS)
            InfoBar.success(
                title='[硬件测试]',
                content='采集卡2s数据采集测试完成',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            self.hardwareInterface.taskIcon_3.setIcon(InfoBarIcon.WARNING)
            InfoBar.info(
                title='[硬件测试]',
                content='未检测到采集卡',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )

    def taskCard3ThreadError(self):
        self.sampleBusyFlag = False
        self.speakerBusyFlag = False
        self.sampleRelatedCardUnfrozen()
        self.speakerRelatedCardUnfrozen()
        self.sampleTestSampleWorker.signals.result.disconnect()
        self.sampleTestSampleWorker.signals.error.disconnect()
        self.sampleTestSampleWorker = None
        self.hardwareInterface.taskIcon_3.setIcon(InfoBarIcon.ERROR)
        InfoBar.error(
            title='[硬件测试]',
            content='采集卡2s数据采集测试失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    # the slot functions below dataset_interface/signalCard
    def datasetSignalCheckBox1Changed(self):
        self.datasetDriver.addSpeakerUsage(0)
        self.displayValueDataset()
        self.stateCardDisplay()

    def datasetSignalCheckBox2Changed(self):
        self.datasetDriver.addSpeakerUsage(1)
        self.displayValueDataset()
        self.stateCardDisplay()

    def datasetSignalCheckBox3Changed(self):
        self.datasetDriver.addSpeakerUsage(2)
        self.displayValueDataset()
        self.stateCardDisplay()

    def datasetSignalCheckBox4Changed(self):
        self.datasetDriver.addSpeakerUsage(3)
        self.displayValueDataset()
        self.stateCardDisplay()

    def datasetSignalComboBoxChanged(self, currentIndex: int):
        if currentIndex == -1:
            InfoBar.warning(
                title='[数据集设置]',
                content='请选择语料选取方法',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            self.datasetInterface.signalComboBox.setCurrentIndex(0)
        else:
            self.datasetDriver.setDataModeCode(currentIndex)
            self.stateCardDisplay()

    # the slot functions below dataset_interface/playCard
    def datasetPlaySpinBoxChanged(self, value: int):
        self.onlineInterface.playSpinBox.blockSignals(True)
        self.onlineInterface.playSpinBox.setValue(value)
        self.onlineInterface.playSpinBox.blockSignals(False)

        playTextBrowserMarkdown = ""
        usedSpeakerIndexList = self.datasetDriver.getUsedSpeakerIndexList()
        speakerTextList = self.datasetDriver.getSpeakerTextList(value)
        correspondingSpeakerNameList = self.datasetDriver.getCorrespondingSpeakerNameList()
        for usedSpeakerIndex, speakerText in zip(usedSpeakerIndexList, speakerTextList):
            playTextBrowserMarkdown += "#### **" + correspondingSpeakerNameList[usedSpeakerIndex] + "**: " + speakerText + "\n"
        self.datasetInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)
        self.onlineInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)

    def datasetPlayPushButtonClicked(self):
        if self.speakerBusyFlag:
            InfoBar.warning(
                title='[硬件测试]',
                content='扬声器被占用，请稍后再试。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            self.speakerBusyFlag = True
            self.speakerRelatedCardFrozen()
            # create a thread to test the speaker

            speakerTextIndex = self.datasetInterface.playSpinBox.value()
            speakerDataList = self.datasetDriver.getSpeakerDataList(speakerTextIndex)
            dataSampleRate = self.datasetDriver.getSampleRate()

            self.datasetPlatWorker = FunctionWorker(self.speakerDriver.playBufferSync, speakerDataList, dataSampleRate)
            self.datasetPlatWorker.signals.result.connect(self.datasetPlayPushButtonThreadFinished)
            self.datasetPlatWorker.signals.error.connect(self.datasetPlayPushButtonThreadError)
            self.datasetPlatWorker.start()

    def datasetPlayPushButtonThreadFinished(self):
        self.speakerBusyFlag = False
        self.speakerRelatedCardUnfrozen()
        self.datasetPlatWorker.signals.result.disconnect()
        self.datasetPlatWorker.signals.error.disconnect()
        self.datasetPlatWorker = None
        InfoBar.success(
            title='[数据集]',
            content='数据集试播完成',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    def datasetPlayPushButtonThreadError(self):
        self.speakerBusyFlag = False
        self.speakerRelatedCardUnfrozen()
        self.datasetPlatWorker.signals.result.disconnect()
        self.datasetPlatWorker.signals.error.disconnect()
        self.datasetPlatWorker = None
        InfoBar.error(
            title='[数据集]',
            content='数据集试播失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    # the function below dataset_interface/stateCard, experiment_interface/stateCard, online_interface/stateCard
    def stateCardDisplay(self):
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

    # the slot functions below experiment_interface/batchCard
    def batchReloadButtonClicked(self):
        self.initSettings()
        if self.batchTask.param.validParamOfConfig(self.paramConfig):
            self.batchTask.param.loadParamFromConfig(self.paramConfig)
        else:
            InfoBar.warning(
                title='[参数加载]',
                content='批量实验参数非法改动，已重置',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            self.batchTask.param.resetParamOfConfig(self.paramConfig)
        self.displayValueBatch()

    def batchSaveButtonClicked(self):
        self.initSettings()
        self.batchTask.param.saveParamToConfig(self.paramConfig)

    def batchDoubleSpinBoxChanged(self, value):
        self.batchTask.param.setSampleTime(value)

    def batchPlainTextEditChanged(self):
        self.batchTask.param.setSpeakerDataIndexList(self.experimentInterface.batchPlainTextEdit.toPlainText())

    def batchStartButtonClicked(self, checked):
        if checked:
            if self.batchTask.getStartFlag():
                self.batchTask.stopBatchTask()
                self.experimentInterface.batchStartButton.setEnabled(False)

                self.experimentInterface.batchStartButton.blockSignals(True)
                self.experimentInterface.batchStartButton.setChecked(False)
                self.experimentInterface.batchStartButton.blockSignals(False)

        else:
            if self.sampleBusyFlag or self.speakerBusyFlag:
                InfoBar.warning(
                    title='[批量实验]',
                    content='采集卡或麦克风被占用，请稍后再试。',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.experimentInterface.batchStartButton.blockSignals(True)
                self.experimentInterface.batchStartButton.setChecked(True)
                self.experimentInterface.batchStartButton.blockSignals(False)
            else:
                speakerDataIndexFlag, speakerDataIndexList = self.batchTask.param.validSpeakerDataIndexString()
                if not speakerDataIndexFlag:
                    InfoBar.error(
                        title='[批量实验]',
                        content='非法语料ID，请稍重新输入。',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    self.experimentInterface.batchStartButton.blockSignals(True)
                    self.experimentInterface.batchStartButton.setChecked(True)
                    self.experimentInterface.batchStartButton.blockSignals(False)
                else:
                    self.sampleBusyFlag = True
                    self.speakerBusyFlag = True
                    self.sampleRelatedCardFrozen()
                    self.speakerRelatedCardFrozen()
                    self.experimentInterface.batchStartButton.setEnabled(True)
                    # create a thread to test the sample card

                    self.initTqdmCard(len(speakerDataIndexList))

                    self.batchTaskWorker = FunctionLoopWorker(self.batchTask.startBatchTask, speakerDataIndexList)
                    self.batchTaskWorker.signals.result.connect(lambda result: self.batchStartButtonThreadFinished(result))
                    self.batchTaskWorker.signals.error.connect(self.batchStartButtonThreadError)
                    self.batchTaskWorker.signals.step.connect(lambda step: self.showTqdmCard(step))
                    self.batchTaskWorker.start()

    def batchStartButtonThreadFinished(self, result):
        self.sampleBusyFlag = False
        self.speakerBusyFlag = False
        self.sampleRelatedCardUnfrozen()
        self.speakerRelatedCardUnfrozen()
        self.experimentInterface.batchStartButton.blockSignals(True)
        self.experimentInterface.batchStartButton.setChecked(True)
        self.experimentInterface.batchStartButton.blockSignals(False)


        self.batchTaskWorker.signals.result.disconnect()
        self.batchTaskWorker.signals.error.disconnect()
        self.batchTaskWorker.signals.step.disconnect()
        self.batchTaskWorker = None
        if result:
            InfoBar.success(
                title='[批量实验]',
                content='批量实验完成',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            InfoBar.error(
                title='[批量实验]',
                content='硬件故障, 请检查硬件连接',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )

    def batchStartButtonThreadError(self):
        self.sampleBusyFlag = False
        self.speakerBusyFlag = False
        self.sampleRelatedCardUnfrozen()
        self.speakerRelatedCardUnfrozen()

        self.experimentInterface.batchStartButton.blockSignals(True)
        self.experimentInterface.batchStartButton.setChecked(True)
        self.experimentInterface.batchStartButton.blockSignals(False)

        self.batchTaskWorker.signals.result.disconnect()
        self.batchTaskWorker.signals.error.disconnect()
        self.batchTaskWorker.signals.step.disconnect()
        self.batchTaskWorker = None
        InfoBar.error(
            title='[批量实验]',
            content='批量实验失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )
        
    def initTqdmCard(self, maxStep: int):
        self.experimentInterface.tqdmProgressRing.setMaximum(maxStep)
        self.experimentInterface.tqdmProgressRing.setValue(0)

    def showTqdmCard(self, step: int):
        if step < self.experimentInterface.tqdmProgressRing.maximum():
            self.experimentInterface.tqdmProgressRing.setValue(step + 1)

    # the slot functions below online_interface/setCard
    def onlineReloadButtonClicked(self):
        self.initSettings()
        if self.onlineTask.param.validParamOfConfig(self.paramConfig):
            self.onlineTask.param.loadParamFromConfig(self.paramConfig)
        else:
            InfoBar.warning(
                title='[参数加载]',
                content='在线实验参数非法改动，已重置',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            self.onlineTask.param.resetParamOfConfig(self.paramConfig)
        self.displayValueOnline()

    def onlineSaveButtonClicked(self):
        self.initSettings()
        self.onlineTask.param.saveParamToConfig(self.paramConfig)

    def onlineComboBox1Changed(self, currentIndex):
        if currentIndex != -1:
            self.onlineTask.param.setFrameLenCode(currentIndex)

    def onlineComboBox2Changed(self, currentIndex):
        if currentIndex != -1:
            self.onlineTask.param.setMethodCode(currentIndex)

    def onlineStartButtonClicked(self, checked):
        if checked:
            if self.onlineTask.getStartFlag():
                self.onlineTask.stopOnlineTask()
                self.onlineInterface.setStartButton.setEnabled(False)

                self.onlineInterface.setStartButton.blockSignals(True)
                self.onlineInterface.setStartButton.setChecked(False)
                self.onlineInterface.setStartButton.blockSignals(False)

        else:
            if self.sampleBusyFlag:
                InfoBar.warning(
                    title='[在线实验]',
                    content='采集卡被占用，请稍后再试。',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.onlineInterface.setStartButton.blockSignals(True)
                self.onlineInterface.setStartButton.setChecked(True)
                self.onlineInterface.setStartButton.blockSignals(False)
            else:
                if self.hkDriver.param.getUsage() != 1:
                    InfoBar.warning(
                        title='[在线实验]',
                        content='采集卡未启用。',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    self.onlineInterface.setStartButton.blockSignals(True)
                    self.onlineInterface.setStartButton.setChecked(True)
                    self.onlineInterface.setStartButton.blockSignals(False)
                else:
                    self.sampleBusyFlag = True
                    self.sampleRelatedCardFrozen()
                    self.onlineInterface.setStartButton.setEnabled(True)
                    # create a thread to test the sample card

                    self.onlineTaskWorker = FunctionLoopWorker(self.onlineTask.startOnlineTask)
                    self.onlineTaskWorker.signals.result.connect(lambda result: self.onlineStartButtonThreadFinished(result))
                    self.onlineTaskWorker.signals.error.connect(self.onlineStartButtonThreadError)
                    self.onlineTaskWorker.signals.step.connect(lambda step: self.drawOnlineStep(step))
                    self.onlineTaskWorker.start()

    def onlineStartButtonThreadFinished(self, result):
        self.sampleBusyFlag = False
        self.sampleRelatedCardUnfrozen()
        self.onlineInterface.setStartButton.blockSignals(True)
        self.onlineInterface.setStartButton.setChecked(True)
        self.onlineInterface.setStartButton.blockSignals(False)

        self.onlineTaskWorker.signals.result.disconnect()
        self.onlineTaskWorker.signals.error.disconnect()
        self.onlineTaskWorker.signals.step.disconnect()
        self.onlineTaskWorker = None
        if result:
            InfoBar.success(
                title='[在线实验]',
                content='在线实验完成',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            InfoBar.error(
                title='[在线实验]',
                content='硬件故障, 请检查硬件连接',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )

    def onlineStartButtonThreadError(self):
        self.sampleBusyFlag = False
        self.sampleRelatedCardUnfrozen()

        self.onlineInterface.setStartButton.blockSignals(True)
        self.onlineInterface.setStartButton.setChecked(True)
        self.onlineInterface.setStartButton.blockSignals(False)

        self.onlineTaskWorker.signals.result.disconnect()
        self.onlineTaskWorker.signals.error.disconnect()
        self.onlineTaskWorker.signals.step.disconnect()
        self.onlineTaskWorker = None
        InfoBar.error(
            title='[在线实验]',
            content='在线实验失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    def drawOnlineStep(self, step: list):
        self.onlineTask.setDrawFlag(False)
        try:
            xData, yData, zData = [0], [0], [0]
            for loc in step:
                if loc[0] < 0 or loc[0] > 1.5:
                    continue
                if loc[1] < 0 or loc[1] > 1.5:
                    continue
                if loc[2] < -0.5 or loc[2] > 1.0:
                    continue
                xData.append(loc[0])
                yData.append(loc[1])
                zData.append(loc[2])
            self.onlineInterface.updateScatter(xData, yData, zData)
        except:
            self.onlineTask.setDrawFlag(True)
        else:
            self.onlineTask.setDrawFlag(True)

    # the slot functions below online_interface/playCard
    def onlinePlaySpinBoxChanged(self, value: int):
        self.datasetInterface.playSpinBox.blockSignals(True)
        self.datasetInterface.playSpinBox.setValue(value)
        self.datasetInterface.playSpinBox.blockSignals(False)

        playTextBrowserMarkdown = ""
        usedSpeakerIndexList = self.datasetDriver.getUsedSpeakerIndexList()
        speakerTextList = self.datasetDriver.getSpeakerTextList(value)
        correspondingSpeakerNameList = self.datasetDriver.getCorrespondingSpeakerNameList()
        for usedSpeakerIndex, speakerText in zip(usedSpeakerIndexList, speakerTextList):
            playTextBrowserMarkdown += "#### **" + correspondingSpeakerNameList[
                usedSpeakerIndex] + "**: " + speakerText + "\n"
        self.datasetInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)
        self.onlineInterface.playTextBrowser.setMarkdown(playTextBrowserMarkdown)

    # the slot functions below offline_interface/setCard
    def offlineReloadButtonClicked(self):
        self.initSettings()
        if self.offlineTask.param.validParamOfConfig(self.paramConfig):
            self.offlineTask.param.loadParamFromConfig(self.paramConfig)
        else:
            InfoBar.warning(
                title='[参数加载]',
                content='离线实验参数非法改动，已重置',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            self.offlineTask.param.resetParamOfConfig(self.paramConfig)
        self.displayValueOffline()

    def offlineSaveButtonClicked(self):
        self.initSettings()
        self.offlineTask.param.saveParamToConfig(self.paramConfig)

    def offlineSetChooseFileClicked(self):
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            '选择数据文件',
            os.getcwd(),
            'Data files (*.npz)'
            )
        if fileName:
            self.offlineTask.param.setDataFilePath(fileName)
            self.offlineInterface.setChooseFileCard.setContent(fileName)

    def offlineSetStartButtonClicked(self):
        if not self.offlineTask.param.getDataFilePath():
            InfoBar.warning(
                title='[文件选择]',
                content='未选择数据文件',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            self.offlineTaskRelatedCardFrozen()
            self.offlineInterface.resultHorizontalSlider.setValue(0)
            # create a thread to test the sample card
            self.offlineTaskWorker = FunctionWorker(self.offlineTask.startOfflineTask)
            self.offlineTaskWorker.signals.result.connect(lambda result: self.offlineStartButtonThreadFinished(result))
            self.offlineTaskWorker.signals.error.connect(self.offlineStartButtonThreadError)
            self.offlineTaskWorker.start()

    def offlineStartButtonThreadFinished(self, result):
        self.offlineTaskRelatedCardUnfrozen()
        self.offlineInterface.resultHorizontalSlider.setValue(0)
        self.offlineTaskWorker.signals.result.disconnect()
        self.offlineTaskWorker.signals.error.disconnect()
        self.offlineTaskWorker = None
        if result:
            self.offlineInterface.resultHorizontalSlider.setMaximum(self.offlineTask.getDataLen())
            InfoBar.success(
                title='[离线实验]',
                content='离线实验完成',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            self.offlineInterface.resultHorizontalSlider.setMaximum(0)
            InfoBar.error(
                title='[离线实验]',
                content='输入数据有误, 请检查输入文件选择',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )

    def offlineStartButtonThreadError(self):
        self.offlineTaskRelatedCardUnfrozen()

        self.offlineInterface.resultHorizontalSlider.setMaximum(0)

        self.offlineTaskWorker.signals.result.disconnect()
        self.offlineTaskWorker.signals.error.disconnect()
        self.offlineTaskWorker = None
        InfoBar.error(
            title='[离线实验]',
            content='离线实验失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    def offlineResultHorizontalSliderChanged(self, value):
        self.offlineInterface.resultChooseLabel.setText(f"数据帧: {value} / {self.offlineTask.getDataLen()}")
        if value == 0:
            self.offlineInterface.clearScatter()
            self.offlineInterface.clearTable()
        else:
            dataFrame = self.offlineTask.getDataHolder()[..., value - 1]
            try:
                xData, yData, zData = [0.0], [0.0], [0.0]
                for loc in dataFrame:
                    if loc[0] < 0.0 or loc[0] > 1.5:
                        continue
                    if loc[1] < 0.0 or loc[1] > 1.5:
                        continue
                    if loc[2] < -0.5 or loc[2] > 1.0:
                        continue
                    xData.append(loc[0])
                    yData.append(loc[1])
                    zData.append(loc[2])
                self.offlineInterface.updateScatter(xData, yData, zData)
                self.offlineInterface.updateTable(xData[1:], yData[1:], zData[1:])
            except:
                self.offlineInterface.clearScatter()
                self.offlineInterface.clearTable()

    # the frozen and unfrozen function of the cards
    def sampleCardFrozen(self):
        self.hardwareInterface.sampleReloadButton.setEnabled(False)
        self.hardwareInterface.sampleUsageSwitchButton.setEnabled(False)
        self.hardwareInterface.sampleVoltageButton_1.setEnabled(False)
        self.hardwareInterface.sampleVoltageButton_2.setEnabled(False)
        self.hardwareInterface.sampleRateSpinBox.setEnabled(False)

    def sampleCardUnfrozen(self):
        self.hardwareInterface.sampleReloadButton.setEnabled(True)
        self.hardwareInterface.sampleUsageSwitchButton.setEnabled(True)
        self.hardwareInterface.sampleVoltageButton_1.setEnabled(True)
        self.hardwareInterface.sampleVoltageButton_2.setEnabled(True)
        self.hardwareInterface.sampleRateSpinBox.setEnabled(True)

    def speakerCardFrozen(self):
        self.hardwareInterface.speakerPushButton.setEnabled(False)
        self.hardwareInterface.speakerComboBox.setEnabled(False)
        self.hardwareInterface.speakerSwitchButton.setEnabled(False)
        self.hardwareInterface.speakerHorizontalSlider.setEnabled(False)
        self.hardwareInterface.speakerTestButton.setEnabled(False)

    def speakerCardUnfrozen(self):
        self.hardwareInterface.speakerPushButton.setEnabled(True)
        self.hardwareInterface.speakerComboBox.setEnabled(True)
        deviceIndex = self.hardwareInterface.speakerComboBox.currentIndex()
        if deviceIndex != -1:
            self.hardwareInterface.speakerSwitchButton.setEnabled(True)
            self.hardwareInterface.speakerHorizontalSlider.setEnabled(True)
            self.hardwareInterface.speakerTestButton.setEnabled(True)

    def taskCardFrozen(self):
        self.hardwareInterface.taskCard_1.setEnabled(False)
        self.hardwareInterface.taskCard_2.setEnabled(False)
        self.hardwareInterface.taskCard_3.setEnabled(False)

    def taskCardUnfrozen(self):
        if self.sampleBusyFlag or self.speakerBusyFlag:
            return
        self.hardwareInterface.taskCard_1.setEnabled(True)
        self.hardwareInterface.taskCard_2.setEnabled(True)
        self.hardwareInterface.taskCard_3.setEnabled(True)

    def signalCardFrozen(self):
        self.datasetInterface.signalCheckBox_1.setEnabled(False)
        self.datasetInterface.signalCheckBox_2.setEnabled(False)
        self.datasetInterface.signalCheckBox_3.setEnabled(False)
        self.datasetInterface.signalCheckBox_4.setEnabled(False)
        self.datasetInterface.signalComboBox.setEnabled(False)

    def signalCardUnfrozen(self):
        self.datasetInterface.signalCheckBox_1.setEnabled(True)
        self.datasetInterface.signalCheckBox_2.setEnabled(True)
        self.datasetInterface.signalCheckBox_3.setEnabled(True)
        self.datasetInterface.signalCheckBox_4.setEnabled(True)
        self.datasetInterface.signalComboBox.setEnabled(True)

    def playCardFrozen(self):
        self.datasetInterface.playSpinBox.setEnabled(False)
        self.datasetInterface.playPushButton.setEnabled(False)
        self.onlineInterface.playSpinBox.setEnabled(False)
        self.onlineInterface.playPushButton.setEnabled(False)

    def playCardUnfrozen(self):
        self.datasetInterface.playSpinBox.setEnabled(True)
        self.datasetInterface.playPushButton.setEnabled(True)
        self.onlineInterface.playSpinBox.setEnabled(True)
        self.onlineInterface.playPushButton.setEnabled(True)

    def batchCardFrozen(self):
        self.experimentInterface.batchDoubleSpinBox.setEnabled(False)
        self.experimentInterface.batchPlainTextEdit.setEnabled(False)
        self.experimentInterface.batchStartButton.setEnabled(False)

    def batchCardUnfrozen(self):
        if self.sampleBusyFlag or self.speakerBusyFlag:
            return
        self.experimentInterface.batchDoubleSpinBox.setEnabled(True)
        self.experimentInterface.batchPlainTextEdit.setEnabled(True)
        self.experimentInterface.batchStartButton.setEnabled(True)

    def onlineSetCardFrozen(self):
        self.onlineInterface.setComboBox_1.setEnabled(False)
        self.onlineInterface.setComboBox_2.setEnabled(False)
        self.onlineInterface.setStartButton.setEnabled(False)

    def onlineSetCardUnfrozen(self):
        self.onlineInterface.setComboBox_1.setEnabled(True)
        self.onlineInterface.setComboBox_2.setEnabled(True)
        self.onlineInterface.setStartButton.setEnabled(True)

    def offlineSetCardFrozen(self):
        self.offlineInterface.setChooseFileCard.setEnabled(False)
        self.offlineInterface.setComboBox.setEnabled(False)

    def offlineSetCardUnfrozen(self):
        self.offlineInterface.setChooseFileCard.setEnabled(True)
        self.offlineInterface.setComboBox.setEnabled(True)

    def resultCardFrozen(self):
        self.offlineInterface.resultHorizontalSlider.setEnabled(False)

    def resultCardUnfrozen(self):
        self.offlineInterface.resultHorizontalSlider.setEnabled(True)

    def sampleRelatedCardFrozen(self):
        self.sampleCardFrozen()
        self.taskCardFrozen()
        self.batchCardFrozen()
        self.onlineSetCardFrozen()

    def sampleRelatedCardUnfrozen(self):
        self.sampleCardUnfrozen()
        self.taskCardUnfrozen()
        self.batchCardUnfrozen()
        self.onlineSetCardUnfrozen()

    def speakerRelatedCardFrozen(self):
        self.speakerCardFrozen()
        self.taskCardFrozen()
        self.signalCardFrozen()
        self.playCardFrozen()
        self.batchCardFrozen()

    def speakerRelatedCardUnfrozen(self):
        self.speakerCardUnfrozen()
        self.taskCardUnfrozen()
        self.signalCardUnfrozen()
        self.playCardUnfrozen()
        self.batchCardUnfrozen()

    def offlineTaskRelatedCardFrozen(self):
        self.offlineSetCardFrozen()
        self.resultCardFrozen()

    def offlineTaskRelatedCardUnfrozen(self):
        self.offlineSetCardUnfrozen()
        self.resultCardUnfrozen()

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
