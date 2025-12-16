# coding:utf-8
"""
硬件设置界面（采集卡 + 扬声器）

概述
----
提供采集卡与扬声器的参数设置、发现与测试入口；包含界面元素的初始化、阴影效果设置，
以及相关的业务逻辑处理。
"""
from typing import Optional

from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect
from qfluentwidgets import FluentIcon, InfoBarIcon, InfoBar, InfoBarPosition

from view.Ui_HardwareInterface import Ui_HardwareInterface
from thread_manager import FunctionWorker


class HardwareInterface(Ui_HardwareInterface, QWidget):
    """
    硬件设置卡片集合的界面封装。

    Parameters
    ----------
    parent : QWidget | None, optional
        父级窗口。

    Signals
    -------
    speakerDeviceChanged : pyqtSignal
        扬声器设备变化时发射，用于通知其他界面更新。
    stateChanged : pyqtSignal
        硬件状态变化时发射，用于通知其他界面更新状态显示。
    """

    # 自定义信号
    speakerDeviceChanged = pyqtSignal()  # 扬声器设备变化
    stateChanged = pyqtSignal()  # 状态变化

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        # 保存主窗口引用
        self._mainWindow = parent

        # 运行状态标志
        self.speakerBusyFlag = False
        self.sampleBusyFlag = False

        # 工作线程
        self.speakerTestSingleWorker: Optional[FunctionWorker] = None
        self.sampleTestUsbWorker: Optional[FunctionWorker] = None
        self.speakerTestMultiWorker: Optional[FunctionWorker] = None
        self.sampleTestSampleWorker: Optional[FunctionWorker] = None

        # 驱动引用（由主窗口注入）
        self.hkDriver = None
        self.speakerDriver = None
        self.datasetDriver = None
        self.paramConfig: Optional[QSettings] = None

        # set the icon of button
        self.sampleReloadButton.setIcon(FluentIcon.CANCEL)
        self.sampleSaveButton.setIcon(FluentIcon.SAVE)
        self.speakerPushButton.setIcon(FluentIcon.SYNC)
        self.speakerTestButton.setIcon(FluentIcon.PLAY)
        self.taskIcon_1.setIcon(InfoBarIcon.WARNING)
        self.taskIcon_2.setIcon(InfoBarIcon.WARNING)
        self.taskIcon_3.setIcon(InfoBarIcon.WARNING)

        # add shadow effect to card
        self.setShadowEffect(self.sampleCard)
        self.setShadowEffect(self.speakerCard)
        self.setShadowEffect(self.taskCard)

    def setDrivers(self, hkDriver, speakerDriver, datasetDriver):
        """
        设置驱动引用。

        Parameters
        ----------
        hkDriver : HkDriver
            采集卡驱动。
        speakerDriver : SpeakerDriver
            扬声器驱动。
        datasetDriver : DatasetDriver
            数据集驱动。
        """
        self.hkDriver = hkDriver
        self.speakerDriver = speakerDriver
        self.datasetDriver = datasetDriver

    def setParamConfig(self, paramConfig: QSettings):
        """
        设置参数配置。

        Parameters
        ----------
        paramConfig : QSettings
            参数配置对象。
        """
        self.paramConfig = paramConfig

    def setShadowEffect(self, card: QWidget):
        """
        为指定卡片添加阴影效果。

        Parameters
        ----------
        card : QWidget
            目标卡片控件。

        Returns
        -------
        None
        """
        shadowEffect = QGraphicsDropShadowEffect(self)
        shadowEffect.setColor(QColor(0, 0, 0, 15))
        shadowEffect.setBlurRadius(10)
        shadowEffect.setOffset(0, 0)
        card.setGraphicsEffect(shadowEffect)

    def initSlot(self):
        """
        初始化所有槽函数连接。
        """
        # sampleCard 相关
        self.sampleReloadButton.clicked.connect(self.sampleReloadButtonClicked)
        self.sampleSaveButton.clicked.connect(self.sampleSaveButtonClicked)
        self.sampleUsageSwitchButton.checkedChanged.connect(self.sampleUsageSwitchButtonChanged)
        self.sampleVoltageButton_1.clicked.connect(lambda _: self.sampleVoltageButtonClicked(0))
        self.sampleVoltageButton_2.clicked.connect(lambda _: self.sampleVoltageButtonClicked(1))
        self.sampleRateSpinBox.valueChanged.connect(self.sampleRateSpinBoxChanged)

        # speakerCard 相关
        self.speakerPushButton.clicked.connect(self.speakerPushButtonClicked)
        self.speakerComboBox.currentIndexChanged.connect(self.speakerComboBoxChanged)
        self.speakerSwitchButton.checkedChanged.connect(self.speakerSwitchButtonChanged)
        self.speakerHorizontalSlider.valueChanged.connect(self.speakerHorizontalSliderChanged)
        self.speakerTestButton.clicked.connect(self.speakerTestButtonClicked)

        # taskCard 相关
        self.taskCard_1.clicked.connect(self.taskCard1Clicked)
        self.taskCard_2.clicked.connect(self.taskCard2Clicked)
        self.taskCard_3.clicked.connect(self.taskCard3Clicked)

    def displayValueHK(self):
        """
        回显采集卡参数。
        """
        # block the signal
        self.sampleUsageSwitchButton.blockSignals(True)
        self.sampleVoltageButton_1.blockSignals(True)
        self.sampleVoltageButton_2.blockSignals(True)
        self.sampleRateSpinBox.blockSignals(True)
        # display the values
        self.sampleUsageSwitchButton.setChecked(self.hkDriver.param.getUsage())
        self.sampleVoltageButton_1.setChecked(not self.hkDriver.param.getRangeCode())
        self.sampleVoltageButton_2.setChecked(self.hkDriver.param.getRangeCode())
        self.sampleRateSpinBox.setValue(self.hkDriver.param.getSampleRate())
        # unblock the signal
        self.sampleUsageSwitchButton.blockSignals(False)
        self.sampleVoltageButton_1.blockSignals(False)
        self.sampleVoltageButton_2.blockSignals(False)
        self.sampleRateSpinBox.blockSignals(False)

    # sampleCard 槽函数
    def sampleReloadButtonClicked(self):
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
                parent=self._mainWindow
            )
            self.hkDriver.param.resetParamOfConfig(self.paramConfig)
        self.displayValueHK()
        self.taskIcon_3.setIcon(InfoBarIcon.WARNING)
        self.stateChanged.emit()

    def sampleSaveButtonClicked(self):
        self.hkDriver.param.saveParamToConfig(self.paramConfig)
        self.stateChanged.emit()

    def sampleUsageSwitchButtonChanged(self, checked: bool):
        self.hkDriver.param.setUsage(int(checked))
        self.stateChanged.emit()

    def sampleVoltageButtonClicked(self, rangeCode: int):
        self.hkDriver.param.setRangeCode(rangeCode)
        self.taskIcon_3.setIcon(InfoBarIcon.WARNING)
        self.stateChanged.emit()

    def sampleRateSpinBoxChanged(self, value: int):
        self.hkDriver.param.setSampleRate(value)
        self.taskIcon_3.setIcon(InfoBarIcon.WARNING)
        self.stateChanged.emit()

    # speakerCard 槽函数
    def speakerPushButtonClicked(self):
        self.speakerComboBox.clear()
        self.speakerDriver.resetDeviceUsage()
        self.speakerDriver.searchUsbSoundcard()
        deviceNameList = [device.getDeviceName() for device in self.speakerDriver.getDeviceItemList()]
        self.speakerComboBox.addItems(deviceNameList)
        self.speakerComboBox.setCurrentIndex(-1)

        # block the signal
        self.speakerSwitchButton.blockSignals(True)
        # init the state
        self.speakerTestButton.setEnabled(False)
        self.speakerSwitchButton.setEnabled(False)
        self.speakerHorizontalSlider.setEnabled(False)
        # init the value
        self.speakerSwitchButton.setChecked(False)
        self.speakerHorizontalSlider.setValue(100)
        # unblock the signal
        self.speakerSwitchButton.blockSignals(False)

        self.datasetDriver.initSpeakerUsage(self.speakerDriver.getDeviceUsedNum())
        self.speakerDeviceChanged.emit()
        self.taskIcon_2.setIcon(InfoBarIcon.WARNING)
        self.stateChanged.emit()

    def speakerComboBoxChanged(self, currentIndex: int):
        if currentIndex == -1:
            self.speakerTestButton.setEnabled(False)
            self.speakerSwitchButton.setEnabled(False)
            self.speakerHorizontalSlider.setEnabled(False)
        else:
            self.speakerTestButton.setEnabled(True)
            self.speakerSwitchButton.setEnabled(True)
            self.speakerHorizontalSlider.setEnabled(True)

            deviceItemList = self.speakerDriver.getDeviceItemList()
            # block the signal
            self.speakerSwitchButton.blockSignals(True)
            # display the value
            self.speakerSwitchButton.setChecked(deviceItemList[currentIndex].getUsage())
            self.speakerHorizontalSlider.setValue(deviceItemList[currentIndex].getVolume())
            # unblock the signal
            self.speakerSwitchButton.blockSignals(False)

    def speakerSwitchButtonChanged(self, checked: bool):
        deviceIndex = self.speakerComboBox.currentIndex()
        if deviceIndex != -1:
            if checked:
                ret = self.speakerDriver.addDeviceUsage(deviceIndex)
                if not ret:
                    # block the signal
                    self.speakerSwitchButton.blockSignals(True)
                    self.speakerSwitchButton.setChecked(False)
                    self.speakerSwitchButton.blockSignals(False)

                    InfoBar.info(
                        title='[扬声器选取]',
                        content='选取扬声器数量已达上限(4个)，若要选取\n选中扬声器请取消其他扬声器的选择。',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self._mainWindow
                    )
            else:
                ret = self.speakerDriver.subDeviceUsage(deviceIndex)
                if not ret:
                    # block the signal
                    self.speakerSwitchButton.blockSignals(True)
                    self.speakerSwitchButton.setChecked(True)
                    self.speakerSwitchButton.blockSignals(False)

                    InfoBar.warning(
                        title='[扬声器选取]',
                        content='非法取消扬声器选中。',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self._mainWindow
                    )
            self.datasetDriver.initSpeakerUsage(self.speakerDriver.getDeviceUsedNum())
            self.speakerDeviceChanged.emit()
            self.taskIcon_2.setIcon(InfoBarIcon.WARNING)
            self.stateChanged.emit()

    def speakerHorizontalSliderChanged(self, value: int):
        deviceIndex = self.speakerComboBox.currentIndex()
        if deviceIndex != -1:
            deviceItemList = self.speakerDriver.getDeviceItemList()
            deviceItemList[deviceIndex].setVolume(value)
            self.taskIcon_2.setIcon(InfoBarIcon.WARNING)
            self.stateChanged.emit()

    def speakerTestButtonClicked(self):
        deviceIndex = self.speakerComboBox.currentIndex()
        if deviceIndex != -1:
            if self.speakerBusyFlag:
                InfoBar.warning(
                    title='[硬件测试]',
                    content='扬声器被占用，请稍后再试。',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self._mainWindow
                )
            else:
                self.speakerBusyFlag = True
                self._mainWindow.speakerRelatedCardFrozen()
                # create a thread to test the speaker
                self.speakerTestSingleWorker = FunctionWorker(self.speakerDriver.playTestSingle, deviceIndex)
                self.speakerTestSingleWorker.signals.result.connect(self.speakerTestButtonThreadFinished)
                self.speakerTestSingleWorker.signals.error.connect(self.speakerTestButtonThreadError)
                self.speakerTestSingleWorker.start()

    def speakerTestButtonThreadFinished(self):
        self.speakerBusyFlag = False
        self._mainWindow.speakerRelatedCardUnfrozen()
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
            parent=self._mainWindow
        )

    def speakerTestButtonThreadError(self):
        self.speakerBusyFlag = False
        self._mainWindow.speakerRelatedCardUnfrozen()
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
            parent=self._mainWindow
        )

    # taskCard 槽函数
    def taskCard1Clicked(self):
        if self.sampleBusyFlag:
            InfoBar.warning(
                title='[硬件测试]',
                content='采集卡被占用，请稍后再试。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
        else:
            self.sampleBusyFlag = True
            self._mainWindow.sampleRelatedCardFrozen()
            # create a thread to test the sample card
            self.sampleTestUsbWorker = FunctionWorker(self.hkDriver.testUsbConnect)
            self.sampleTestUsbWorker.signals.result.connect(self.taskCard1ThreadFinished)
            self.sampleTestUsbWorker.signals.error.connect(self.taskCard1ThreadError)
            self.sampleTestUsbWorker.start()

    def taskCard1ThreadFinished(self, result):
        self.sampleBusyFlag = False
        self._mainWindow.sampleRelatedCardUnfrozen()
        self.sampleTestUsbWorker.signals.result.disconnect()
        self.sampleTestUsbWorker.signals.error.disconnect()
        self.sampleTestUsbWorker = None
        if result:
            self.taskIcon_1.setIcon(InfoBarIcon.SUCCESS)
            InfoBar.success(
                title='[硬件测试]',
                content='采集卡USB测试完成',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
        else:
            self.taskIcon_1.setIcon(InfoBarIcon.WARNING)
            InfoBar.info(
                title='[硬件测试]',
                content='未检测到采集卡',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )

    def taskCard1ThreadError(self):
        self.sampleBusyFlag = False
        self._mainWindow.sampleRelatedCardUnfrozen()
        self.sampleTestUsbWorker.signals.result.disconnect()
        self.sampleTestUsbWorker.signals.error.disconnect()
        self.sampleTestUsbWorker = None
        self.taskIcon_1.setIcon(InfoBarIcon.ERROR)
        InfoBar.error(
            title='[硬件测试]',
            content='采集卡USB测试失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self._mainWindow
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
                parent=self._mainWindow
            )
        else:
            self.speakerBusyFlag = True
            self._mainWindow.speakerRelatedCardFrozen()
            # create a thread to test the speaker
            self.speakerTestMultiWorker = FunctionWorker(self.speakerDriver.playTestMulti)
            self.speakerTestMultiWorker.signals.result.connect(self.taskCard2ThreadFinished)
            self.speakerTestMultiWorker.signals.error.connect(self.taskCard2ThreadError)
            self.speakerTestMultiWorker.start()

    def taskCard2ThreadFinished(self):
        self.speakerBusyFlag = False
        self._mainWindow.speakerRelatedCardUnfrozen()
        self.speakerTestMultiWorker.signals.result.disconnect()
        self.speakerTestMultiWorker.signals.error.disconnect()
        self.speakerTestMultiWorker = None
        self.taskIcon_2.setIcon(InfoBarIcon.SUCCESS)
        InfoBar.success(
            title='[硬件测试]',
            content='扬声器依次播放测试完成',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self._mainWindow
        )

    def taskCard2ThreadError(self):
        self.speakerBusyFlag = False
        self._mainWindow.speakerRelatedCardUnfrozen()
        self.speakerTestMultiWorker.signals.result.disconnect()
        self.speakerTestMultiWorker.signals.error.disconnect()
        self.speakerTestMultiWorker = None
        self.taskIcon_2.setIcon(InfoBarIcon.ERROR)
        InfoBar.error(
            title='[硬件测试]',
            content='扬声器依次播放测试失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self._mainWindow
        )

    def taskCard3Clicked(self):
        if self.sampleBusyFlag or self.speakerBusyFlag:
            InfoBar.warning(
                title='[硬件测试]',
                content='硬件被占用，请稍后再试。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
        else:
            self.sampleBusyFlag = True
            self.speakerBusyFlag = True
            self._mainWindow.sampleRelatedCardFrozen()
            self._mainWindow.speakerRelatedCardFrozen()
            # create a thread to test the sample card
            self.sampleTestSampleWorker = FunctionWorker(self.hkDriver.testSampleBuffer)
            self.sampleTestSampleWorker.signals.result.connect(self.taskCard3ThreadFinished)
            self.sampleTestSampleWorker.signals.error.connect(self.taskCard3ThreadError)
            self.sampleTestSampleWorker.start()

    def taskCard3ThreadFinished(self, result):
        self.sampleBusyFlag = False
        self.speakerBusyFlag = False
        self._mainWindow.sampleRelatedCardUnfrozen()
        self._mainWindow.speakerRelatedCardUnfrozen()
        self.sampleTestSampleWorker.signals.result.disconnect()
        self.sampleTestSampleWorker.signals.error.disconnect()
        self.sampleTestSampleWorker = None
        if result:
            self.taskIcon_3.setIcon(InfoBarIcon.SUCCESS)
            InfoBar.success(
                title='[硬件测试]',
                content='采集卡2s数据采集测试完成',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
        else:
            self.taskIcon_3.setIcon(InfoBarIcon.WARNING)
            InfoBar.info(
                title='[硬件测试]',
                content='未检测到采集卡',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )

    def taskCard3ThreadError(self):
        self.sampleBusyFlag = False
        self.speakerBusyFlag = False
        self._mainWindow.sampleRelatedCardUnfrozen()
        self._mainWindow.speakerRelatedCardUnfrozen()
        self.sampleTestSampleWorker.signals.result.disconnect()
        self.sampleTestSampleWorker.signals.error.disconnect()
        self.sampleTestSampleWorker = None
        self.taskIcon_3.setIcon(InfoBarIcon.ERROR)
        InfoBar.error(
            title='[硬件测试]',
            content='采集卡2s数据采集测试失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self._mainWindow
        )

    # UI冻结/解冻方法
    def sampleCardFrozen(self):
        self.sampleReloadButton.setEnabled(False)
        self.sampleUsageSwitchButton.setEnabled(False)
        self.sampleVoltageButton_1.setEnabled(False)
        self.sampleVoltageButton_2.setEnabled(False)
        self.sampleRateSpinBox.setEnabled(False)

    def sampleCardUnfrozen(self):
        self.sampleReloadButton.setEnabled(True)
        self.sampleUsageSwitchButton.setEnabled(True)
        self.sampleVoltageButton_1.setEnabled(True)
        self.sampleVoltageButton_2.setEnabled(True)
        self.sampleRateSpinBox.setEnabled(True)

    def speakerCardFrozen(self):
        self.speakerPushButton.setEnabled(False)
        self.speakerComboBox.setEnabled(False)
        self.speakerSwitchButton.setEnabled(False)
        self.speakerHorizontalSlider.setEnabled(False)
        self.speakerTestButton.setEnabled(False)

    def speakerCardUnfrozen(self):
        self.speakerPushButton.setEnabled(True)
        self.speakerComboBox.setEnabled(True)
        deviceIndex = self.speakerComboBox.currentIndex()
        if deviceIndex != -1:
            self.speakerSwitchButton.setEnabled(True)
            self.speakerHorizontalSlider.setEnabled(True)
            self.speakerTestButton.setEnabled(True)

    def taskCardFrozen(self):
        self.taskCard_1.setEnabled(False)
        self.taskCard_2.setEnabled(False)
        self.taskCard_3.setEnabled(False)

    def taskCardUnfrozen(self):
        if self.sampleBusyFlag or self.speakerBusyFlag:
            return
        self.taskCard_1.setEnabled(True)
        self.taskCard_2.setEnabled(True)
        self.taskCard_3.setEnabled(True)
