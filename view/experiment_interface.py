# coding:utf-8
"""
批量实验界面（参数设置 + 进度显示 + 状态监视）

概述
----
提供批量实验参数设置、开始/停止按钮；圆环进度与状态卡展示硬件与计划进度；
包含具体任务逻辑实现。
"""
from typing import Optional

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect
from qfluentwidgets import FluentIcon, InfoBar, InfoBarPosition

from view.Ui_ExperimentInterface import Ui_ExperimentInterface
from thread_manager import FunctionLoopWorker


class ExperimentInterface(Ui_ExperimentInterface, QWidget):
    """
    批量实验相关卡片集合的界面封装。

    Parameters
    ----------
    parent : QWidget | None, optional
        父级窗口。
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        # 保存主窗口引用
        self._mainWindow = parent

        # 工作线程
        self.batchTaskWorker: Optional[FunctionLoopWorker] = None

        # 任务引用（由主窗口注入）
        self.batchTask = None
        self.paramConfig: Optional[QSettings] = None

        # set the icon of button
        self.batchReloadButton.setIcon(FluentIcon.CANCEL)
        self.batchSaveButton.setIcon(FluentIcon.SAVE)
        self.batchStartButton.setIcon(FluentIcon.PLAY)

        # add shadow effect to card
        self.setShadowEffect(self.batchCard)
        self.setShadowEffect(self.tqdmCard)
        self.setShadowEffect(self.stateCard)

    def setBatchTask(self, batchTask):
        """
        设置批量任务引用。

        Parameters
        ----------
        batchTask : BatchTask
            批量任务对象。
        """
        self.batchTask = batchTask

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
        self.batchReloadButton.clicked.connect(self.batchReloadButtonClicked)
        self.batchSaveButton.clicked.connect(self.batchSaveButtonClicked)
        self.batchDoubleSpinBox.valueChanged.connect(self.batchDoubleSpinBoxChanged)
        self.batchPlainTextEdit.textChanged.connect(self.batchPlainTextEditChanged)
        self.batchStartButton.toggled.connect(self.batchStartButtonClicked)

    def displayValueBatch(self):
        """
        回显批量实验参数。
        """
        self.batchDoubleSpinBox.blockSignals(True)
        self.batchPlainTextEdit.blockSignals(True)
        self.batchDoubleSpinBox.setValue(self.batchTask.param.getSampleTime())
        self.batchPlainTextEdit.setPlainText(self.batchTask.param.getSpeakerDataIndexString())
        self.batchDoubleSpinBox.blockSignals(False)
        self.batchPlainTextEdit.blockSignals(False)

    # batchCard 槽函数
    def batchReloadButtonClicked(self):
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
                parent=self._mainWindow
            )
            self.batchTask.param.resetParamOfConfig(self.paramConfig)
        self.displayValueBatch()

    def batchSaveButtonClicked(self):
        self.batchTask.param.saveParamToConfig(self.paramConfig)

    def batchDoubleSpinBoxChanged(self, value):
        self.batchTask.param.setSampleTime(value)

    def batchPlainTextEditChanged(self):
        self.batchTask.param.setSpeakerDataIndexList(self.batchPlainTextEdit.toPlainText())

    def batchStartButtonClicked(self, checked):
        if checked:
            if self.batchTask.getStartFlag():
                self.batchTask.stopBatchTask()
                self.batchStartButton.setEnabled(False)

                self.batchStartButton.blockSignals(True)
                self.batchStartButton.setChecked(False)
                self.batchStartButton.blockSignals(False)

        else:
            if self._mainWindow.hardwareInterface.sampleBusyFlag or self._mainWindow.hardwareInterface.speakerBusyFlag:
                InfoBar.warning(
                    title='[批量实验]',
                    content='采集卡或麦克风被占用，请稍后再试。',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self._mainWindow
                )
                self.batchStartButton.blockSignals(True)
                self.batchStartButton.setChecked(True)
                self.batchStartButton.blockSignals(False)
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
                        parent=self._mainWindow
                    )
                    self.batchStartButton.blockSignals(True)
                    self.batchStartButton.setChecked(True)
                    self.batchStartButton.blockSignals(False)
                else:
                    self._mainWindow.hardwareInterface.sampleBusyFlag = True
                    self._mainWindow.hardwareInterface.speakerBusyFlag = True
                    self._mainWindow.sampleRelatedCardFrozen()
                    self._mainWindow.speakerRelatedCardFrozen()
                    self.batchStartButton.setEnabled(True)
                    # create a thread to test the sample card

                    self.initTqdmCard(len(speakerDataIndexList))

                    self.batchTaskWorker = FunctionLoopWorker(self.batchTask.startBatchTask, speakerDataIndexList)
                    self.batchTaskWorker.signals.result.connect(self.batchStartButtonThreadFinished)
                    self.batchTaskWorker.signals.error.connect(self.batchStartButtonThreadError)
                    self.batchTaskWorker.signals.step.connect(self.showTqdmCard)
                    self.batchTaskWorker.start()

    def batchStartButtonThreadFinished(self, result):
        self._mainWindow.hardwareInterface.sampleBusyFlag = False
        self._mainWindow.hardwareInterface.speakerBusyFlag = False
        self._mainWindow.sampleRelatedCardUnfrozen()
        self._mainWindow.speakerRelatedCardUnfrozen()
        self.batchStartButton.blockSignals(True)
        self.batchStartButton.setChecked(True)
        self.batchStartButton.blockSignals(False)

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
                parent=self._mainWindow
            )
        else:
            InfoBar.error(
                title='[批量实验]',
                content='硬件故障, 请检查硬件连接',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )

    def batchStartButtonThreadError(self):
        self._mainWindow.hardwareInterface.sampleBusyFlag = False
        self._mainWindow.hardwareInterface.speakerBusyFlag = False
        self._mainWindow.sampleRelatedCardUnfrozen()
        self._mainWindow.speakerRelatedCardUnfrozen()

        self.batchStartButton.blockSignals(True)
        self.batchStartButton.setChecked(True)
        self.batchStartButton.blockSignals(False)

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
            parent=self._mainWindow
        )

    def initTqdmCard(self, maxStep: int):
        """
        初始化进度圆环。

        Parameters
        ----------
        maxStep : int
            最大步数。
        """
        self.tqdmProgressRing.setMaximum(maxStep)
        self.tqdmProgressRing.setValue(0)

    def showTqdmCard(self, step: int):
        """
        更新进度圆环。

        Parameters
        ----------
        step : int
            当前步数。
        """
        if step < self.tqdmProgressRing.maximum():
            self.tqdmProgressRing.setValue(step + 1)

    # UI冻结/解冻方法
    def batchCardFrozen(self):
        self.batchDoubleSpinBox.setEnabled(False)
        self.batchPlainTextEdit.setEnabled(False)
        self.batchStartButton.setEnabled(False)

    def batchCardUnfrozen(self):
        if self._mainWindow.hardwareInterface.sampleBusyFlag or self._mainWindow.hardwareInterface.speakerBusyFlag:
            return
        self.batchDoubleSpinBox.setEnabled(True)
        self.batchPlainTextEdit.setEnabled(True)
        self.batchStartButton.setEnabled(True)
