# coding:utf-8
"""
数据集界面（CMU ARCTIC 播放预览）

概述
----
用于选择说话人组合、显示对应文本、触发"试播"操作；包含实际播放逻辑。
"""
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect
from qfluentwidgets import FluentIcon, InfoBar, InfoBarPosition

from view.Ui_DatasetInterface import Ui_DatasetInterface
from thread_manager import FunctionWorker


class DatasetInterface(Ui_DatasetInterface, QWidget):
    """
    数据集相关卡片集合的界面封装。

    Parameters
    ----------
    parent : QWidget | None, optional
        父级窗口。

    Signals
    -------
    stateChanged : pyqtSignal
        状态变化时发射，用于通知其他界面更新状态显示。
    playSpinBoxChanged : pyqtSignal(int)
        播放SpinBox值变化时发射。
    """

    # 自定义信号
    stateChanged = pyqtSignal()  # 状态变化
    playSpinBoxValueChanged = pyqtSignal(int)  # playSpinBox值变化

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        # 保存主窗口引用
        self._mainWindow = parent

        # 运行状态标志（通过主窗口访问）
        self.speakerBusyFlag = False

        # 工作线程
        self.datasetPlayWorker: Optional[FunctionWorker] = None

        # 驱动引用（由主窗口注入）
        self.datasetDriver = None
        self.speakerDriver = None

        self.playPushButton.setIcon(FluentIcon.PLAY)
        # add shadow effect to card
        self.setShadowEffect(self.signalCard)
        self.setShadowEffect(self.playCard)
        self.setShadowEffect(self.stateCard)

    def setDrivers(self, datasetDriver, speakerDriver):
        """
        设置驱动引用。

        Parameters
        ----------
        datasetDriver : DatasetDriver
            数据集驱动。
        speakerDriver : SpeakerDriver
            扬声器驱动。
        """
        self.datasetDriver = datasetDriver
        self.speakerDriver = speakerDriver

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
        # signalCard 相关
        self.signalCheckBox_1.clicked.connect(self.datasetSignalCheckBox1Changed)
        self.signalCheckBox_2.clicked.connect(self.datasetSignalCheckBox2Changed)
        self.signalCheckBox_3.clicked.connect(self.datasetSignalCheckBox3Changed)
        self.signalCheckBox_4.clicked.connect(self.datasetSignalCheckBox4Changed)
        self.signalComboBox.currentIndexChanged.connect(self.datasetSignalComboBoxChanged)

        # playCard 相关
        self.playSpinBox.valueChanged.connect(self.datasetPlaySpinBoxChanged)
        self.playPushButton.clicked.connect(self.datasetPlayPushButtonClicked)

    def initValueDataset(self):
        """
        初始化数据集相关下拉框。
        """
        self.signalComboBox.addItems([
            '扬声器-不同说话人不同语料',
            '扬声器-不同说话人相同语料',
            '扬声器-相同说话人不同语料',
            '扬声器-相同说话人相同语料'
        ])
        self.signalComboBox.setCurrentIndex(0)

    def displayValueDataset(self):
        """
        回显数据集参数。
        """
        usedSpeakerIndexList = self.datasetDriver.getUsedSpeakerIndexList()

        self.signalCheckBox_1.setChecked(0 in usedSpeakerIndexList)
        self.signalCheckBox_2.setChecked(1 in usedSpeakerIndexList)
        self.signalCheckBox_3.setChecked(2 in usedSpeakerIndexList)
        self.signalCheckBox_4.setChecked(3 in usedSpeakerIndexList)

        speakerTextIndex = self.playSpinBox.value()

        playTextBrowserMarkdown = self.getPlayTextBrowserMarkdown(speakerTextIndex)
        self.playTextBrowser.setMarkdown(playTextBrowserMarkdown)
        self.playSpinBoxValueChanged.emit(speakerTextIndex)
        return playTextBrowserMarkdown

    def getPlayTextBrowserMarkdown(self, value: int) -> str:
        """
        获取播放文本浏览器的Markdown内容。

        Parameters
        ----------
        value : int
            语料索引。

        Returns
        -------
        str
            Markdown格式的文本。
        """
        playTextBrowserMarkdown = ""
        usedSpeakerIndexList = self.datasetDriver.getUsedSpeakerIndexList()
        speakerTextList = self.datasetDriver.getSpeakerTextList(value)
        correspondingSpeakerNameList = self.datasetDriver.getCorrespondingSpeakerNameList()
        for usedSpeakerIndex, speakerText in zip(usedSpeakerIndexList, speakerTextList):
            playTextBrowserMarkdown += "#### **" + correspondingSpeakerNameList[usedSpeakerIndex] + "**: " + speakerText + "\n"
        return playTextBrowserMarkdown

    # signalCard 槽函数
    def datasetSignalCheckBox1Changed(self):
        self.datasetDriver.addSpeakerUsage(0)
        self.displayValueDataset()
        self.stateChanged.emit()

    def datasetSignalCheckBox2Changed(self):
        self.datasetDriver.addSpeakerUsage(1)
        self.displayValueDataset()
        self.stateChanged.emit()

    def datasetSignalCheckBox3Changed(self):
        self.datasetDriver.addSpeakerUsage(2)
        self.displayValueDataset()
        self.stateChanged.emit()

    def datasetSignalCheckBox4Changed(self):
        self.datasetDriver.addSpeakerUsage(3)
        self.displayValueDataset()
        self.stateChanged.emit()

    def datasetSignalComboBoxChanged(self, currentIndex: int):
        if currentIndex == -1:
            InfoBar.warning(
                title='[数据集设置]',
                content='请选择语料选取方法',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
            self.signalComboBox.setCurrentIndex(0)
        else:
            self.datasetDriver.setDataModeCode(currentIndex)
            # 切换模式会重置数据集内部的“扬声器-说话人”映射关系，这里同步刷新显示
            self.displayValueDataset()
            self.stateChanged.emit()

    # playCard 槽函数
    def datasetPlaySpinBoxChanged(self, value: int):
        playTextBrowserMarkdown = self.getPlayTextBrowserMarkdown(value)
        self.playTextBrowser.setMarkdown(playTextBrowserMarkdown)
        self.playSpinBoxValueChanged.emit(value)

    def datasetPlayPushButtonClicked(self):
        if self._mainWindow.hardwareInterface.speakerBusyFlag:
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
            self._mainWindow.hardwareInterface.speakerBusyFlag = True
            self._mainWindow.speakerRelatedCardFrozen()
            # create a thread to test the speaker

            speakerTextIndex = self.playSpinBox.value()
            speakerDataList = self.datasetDriver.getSpeakerDataList(speakerTextIndex)
            dataSampleRate = self.datasetDriver.getSampleRate()

            self.datasetPlayWorker = FunctionWorker(self.speakerDriver.playBufferSync, speakerDataList, dataSampleRate)
            self.datasetPlayWorker.signals.result.connect(self.datasetPlayPushButtonThreadFinished)
            self.datasetPlayWorker.signals.error.connect(self.datasetPlayPushButtonThreadError)
            self.datasetPlayWorker.start()

    def datasetPlayPushButtonThreadFinished(self):
        self._mainWindow.hardwareInterface.speakerBusyFlag = False
        self._mainWindow.speakerRelatedCardUnfrozen()
        self.datasetPlayWorker.signals.result.disconnect()
        self.datasetPlayWorker.signals.error.disconnect()
        self.datasetPlayWorker = None
        InfoBar.success(
            title='[数据集]',
            content='数据集试播完成',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self._mainWindow
        )

    def datasetPlayPushButtonThreadError(self):
        self._mainWindow.hardwareInterface.speakerBusyFlag = False
        self._mainWindow.speakerRelatedCardUnfrozen()
        self.datasetPlayWorker.signals.result.disconnect()
        self.datasetPlayWorker.signals.error.disconnect()
        self.datasetPlayWorker = None
        InfoBar.error(
            title='[数据集]',
            content='数据集试播失败',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self._mainWindow
        )

    # UI冻结/解冻方法
    def signalCardFrozen(self):
        self.signalCheckBox_1.setEnabled(False)
        self.signalCheckBox_2.setEnabled(False)
        self.signalCheckBox_3.setEnabled(False)
        self.signalCheckBox_4.setEnabled(False)
        self.signalComboBox.setEnabled(False)

    def signalCardUnfrozen(self):
        self.signalCheckBox_1.setEnabled(True)
        self.signalCheckBox_2.setEnabled(True)
        self.signalCheckBox_3.setEnabled(True)
        self.signalCheckBox_4.setEnabled(True)
        self.signalComboBox.setEnabled(True)

    def playCardFrozen(self):
        self.playSpinBox.setEnabled(False)
        self.playPushButton.setEnabled(False)

    def playCardUnfrozen(self):
        self.playSpinBox.setEnabled(True)
        self.playPushButton.setEnabled(True)
