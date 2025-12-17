# coding:utf-8
"""
在线界面（参数设置 + 三维散点实时展示）

概述
----
提供在线定位参数设置与三维散点实时展示控件，包含具体任务逻辑实现。
"""
from typing import Optional

from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QVBoxLayout, QFrame
from qfluentwidgets import FluentIcon, InfoBar, InfoBarPosition

import numpy as np

from view.Ui_OnlineInterface import Ui_OnlineInterface

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from typing import cast

from thread_manager import FunctionLoopWorker


class OnlineInterface(Ui_OnlineInterface, QWidget):
    """
    在线定位相关卡片集合的界面封装。

    Parameters
    ----------
    parent : QWidget | None, optional
        父级窗口。

    Signals
    -------
    playSpinBoxValueChanged : pyqtSignal(int)
        playSpinBox值变化时发射。
    """

    # 自定义信号
    playSpinBoxValueChanged = pyqtSignal(int)  # playSpinBox值变化

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        # 保存主窗口引用
        self._mainWindow = parent

        # 工作线程
        self.onlineTaskWorker: Optional[FunctionLoopWorker] = None

        # 任务和驱动引用（由主窗口注入）
        self.onlineTask = None
        self.arrayTask = None
        self.hkDriver = None
        self.datasetDriver = None
        self.paramConfig: Optional[QSettings] = None

        self.setReloadButton.setIcon(FluentIcon.CANCEL)
        self.setSaveButton.setIcon(FluentIcon.SAVE)
        self.setStartButton.setIcon(FluentIcon.PLAY)
        self.playPushButton.setIcon(FluentIcon.PLAY)

        self._fig: Optional[Figure] = None
        self._canvas: Optional[FigureCanvas] = None
        self._ax: Optional[Axes3D] = None

        # 坐标轴范围（用于滚轮缩放和数据过滤）
        self._xlim = [-1.5, 1.5]
        self._ylim = [-1.5, 1.5]
        self._zlim = [-1.0, 1.0]
        self._scale_factor = 1.1  # 缩放因子

        # add shadow effect to card
        self.setShadowEffect(self.setCard)
        self.setShadowEffect(self.playCard)
        self.setShadowEffect(self.stateCard)
        self.setShadowEffect(self.showCard)

    def setOnlineTask(self, onlineTask, arrayTask):
        """
        设置在线任务引用。

        Parameters
        ----------
        onlineTask : OnlineTask
            在线任务对象。
        arrayTask : ArrayTask
            阵列任务对象。
        """
        self.onlineTask = onlineTask
        self.arrayTask = arrayTask

    def setDrivers(self, hkDriver, datasetDriver):
        """
        设置驱动引用。

        Parameters
        ----------
        hkDriver : HkDriver
            采集卡驱动。
        datasetDriver : DatasetDriver
            数据集驱动。
        """
        self.hkDriver = hkDriver
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
        self.setReloadButton.clicked.connect(self.onlineReloadButtonClicked)
        self.setSaveButton.clicked.connect(self.onlineSaveButtonClicked)
        self.setComboBox_1.currentIndexChanged.connect(self.onlineComboBox1Changed)
        self.setComboBox_2.currentIndexChanged.connect(self.onlineComboBox2Changed)
        self.setStartButton.toggled.connect(self.onlineStartButtonClicked)

        self.playSpinBox.valueChanged.connect(self.onlinePlaySpinBoxChanged)
        # playPushButton的clicked连接在主窗口中处理，因为它调用的是datasetInterface的方法

    def initScatter(self):
        """
        初始化 3D 散点图组件。

        Returns
        -------
        None
        """
        self._fig = Figure(figsize=(2, 2))
        self._fig.patch.set_facecolor('#F9F9F9')  # 设置图形背景色

        self._canvas = FigureCanvas(self._fig)
        self._ax = cast(Axes3D, self._fig.add_subplot(111, projection='3d'))
        self._ax.set_facecolor('#F9F9F9')  # 设置坐标轴背景色

        colors = np.linspace(0.1, 1, 1)
        self._scatter = self._ax.scatter([0], [0], [0], c=colors, cmap='tab20b', s=30, alpha=0.9)

        self._ax.set_xlim(self._xlim[0], self._xlim[1])
        self._ax.set_ylim(self._ylim[0], self._ylim[1])
        self._ax.set_zlim(self._zlim[0], self._zlim[1])
        self._ax.view_init(30, -60)
        self._fig.tight_layout()

        # 连接滚轮事件
        self._canvas.mpl_connect('scroll_event', self._onScroll)

        # 创建圆角容器
        self._scatterContainer = QFrame()
        self._scatterContainer.setStyleSheet("""
            QFrame {
                background-color: #F9F9F9;
                border-radius: 6px;
                border: 1px solid #E0E0E0;
            }
        """)
        containerLayout = QVBoxLayout(self._scatterContainer)
        containerLayout.setContentsMargins(5, 5, 5, 5)
        containerLayout.addWidget(self._canvas)

        self.showVerticalLayout.addWidget(self._scatterContainer)
        self._canvas.draw()

    def _onScroll(self, event):
        """
        处理滚轮事件，按比例缩放坐标轴范围。
        Parameters
        ----------
        event : matplotlib.backend_bases.MouseEvent
            滚轮事件对象。
        """
        if event.button == 'up':
            # 滚轮向上，放大（缩小范围）
            scale = 1.0 / self._scale_factor
        elif event.button == 'down':
            scale = self._scale_factor
        else:
            return

        # 计算各轴的中心和半宽
        x_center = (self._xlim[0] + self._xlim[1]) / 2
        y_center = (self._ylim[0] + self._ylim[1]) / 2
        z_center = (self._zlim[0] + self._zlim[1]) / 2

        x_half = (self._xlim[1] - self._xlim[0]) / 2 * scale
        y_half = (self._ylim[1] - self._ylim[0]) / 2 * scale
        z_half = (self._zlim[1] - self._zlim[0]) / 2 * scale

        # 更新范围
        self._xlim = [x_center - x_half, x_center + x_half]
        self._ylim = [y_center - y_half, y_center + y_half]
        self._zlim = [z_center - z_half, z_center + z_half]

        # 应用新范围
        if self._ax is not None:
            self._ax.set_xlim(self._xlim[0], self._xlim[1])
            self._ax.set_ylim(self._ylim[0], self._ylim[1])
            self._ax.set_zlim(self._zlim[0], self._zlim[1])
            self._canvas.draw()

    def updateScatter(self, xData, yData, zData):
        """
        更新散点图数据。

        Parameters
        ----------
        xData, yData, zData : array-like
            三维坐标序列。

        Returns
        -------
        None
        """
        colors = np.linspace(0.1, 1, len(xData))

        if self._ax is None:
            return
        self._scatter.remove()
        self._scatter = self._ax.scatter(xData, yData, zData, c=colors, cmap='tab20b', s=30, alpha=0.9)

        self._canvas.draw()

    def clearScatter(self):
        """
        清空散点图（重置为原点）。

        Returns
        -------
        None
        """
        colors = np.linspace(0.1, 1, 1)
        if self._ax is None:
            return
        self._scatter.remove()
        self._scatter = self._ax.scatter([0], [0], [0], c=colors, cmap='tab20b', s=30, alpha=0.9)
        self._canvas.draw()

    def initValueOnline(self):
        """
        初始化在线实验相关下拉框。
        """
        self.setComboBox_1.addItems([str(frameLen) for frameLen in self.onlineTask.param.getFrameLenList()])
        self.setComboBox_2.addItems(['GCC-PHAT单声源定位'])

    def displayValueOnline(self):
        """
        回显在线实验参数。
        """
        self.setComboBox_1.setCurrentIndex(self.onlineTask.param.getFrameLenCode())
        self.setComboBox_2.setCurrentIndex(self.onlineTask.param.getMethodCode())

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

    # setCard 槽函数
    def onlineReloadButtonClicked(self):
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
                parent=self._mainWindow
            )
            self.onlineTask.param.resetParamOfConfig(self.paramConfig)
        self.displayValueOnline()

    def onlineSaveButtonClicked(self):
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
                self.setStartButton.setEnabled(False)

                self.setStartButton.blockSignals(True)
                self.setStartButton.setChecked(False)
                self.setStartButton.blockSignals(False)

        else:
            if self._mainWindow.hardwareInterface.sampleBusyFlag:
                InfoBar.warning(
                    title='[在线实验]',
                    content='采集卡被占用，请稍后再试。',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self._mainWindow
                )
                self.setStartButton.blockSignals(True)
                self.setStartButton.setChecked(True)
                self.setStartButton.blockSignals(False)
            else:
                if self.hkDriver.param.getUsage() != 1:
                    InfoBar.warning(
                        title='[在线实验]',
                        content='采集卡未启用。',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self._mainWindow
                    )
                    self.setStartButton.blockSignals(True)
                    self.setStartButton.setChecked(True)
                    self.setStartButton.blockSignals(False)
                else:
                    self._mainWindow.hardwareInterface.sampleBusyFlag = True
                    self._mainWindow.sampleRelatedCardFrozen()
                    self._mainWindow.arrayRelatedCardFrozen()
                    self.setStartButton.setEnabled(True)
                    # create a thread to test the sample card

                    self.onlineTaskWorker = FunctionLoopWorker(self.onlineTask.startOnlineTask, self.arrayTask.param.getMicCoords())
                    self.onlineTaskWorker.signals.result.connect(self.onlineStartButtonThreadFinished)
                    self.onlineTaskWorker.signals.error.connect(self.onlineStartButtonThreadError)
                    self.onlineTaskWorker.signals.step.connect(self.drawOnlineStep)
                    self.onlineTaskWorker.start()

    def onlineStartButtonThreadFinished(self, result):
        self._mainWindow.hardwareInterface.sampleBusyFlag = False
        self._mainWindow.sampleRelatedCardUnfrozen()
        self._mainWindow.arrayRelatedCardUnfrozen()
        self.setStartButton.blockSignals(True)
        self.setStartButton.setChecked(True)
        self.setStartButton.blockSignals(False)

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
                parent=self._mainWindow
            )
        else:
            InfoBar.error(
                title='[在线实验]',
                content='硬件故障, 请检查硬件连接',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )

    def onlineStartButtonThreadError(self):
        self._mainWindow.hardwareInterface.sampleBusyFlag = False
        self._mainWindow.sampleRelatedCardUnfrozen()
        self._mainWindow.arrayRelatedCardUnfrozen()

        self.setStartButton.blockSignals(True)
        self.setStartButton.setChecked(True)
        self.setStartButton.blockSignals(False)

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
            parent=self._mainWindow
        )

    def drawOnlineStep(self, step: list):
        self.onlineTask.setDrawFlag(False)
        try:
            xData, yData, zData = [0], [0], [0]
            for loc in step:
                # 使用当前坐标轴范围进行数据过滤
                if loc[0] < self._xlim[0] or loc[0] > self._xlim[1]:
                    continue
                if loc[1] < self._ylim[0] or loc[1] > self._ylim[1]:
                    continue
                if loc[2] < self._zlim[0] or loc[2] > self._zlim[1]:
                    continue
                xData.append(loc[0])
                yData.append(loc[1])
                zData.append(loc[2])
            self.updateScatter(xData, yData, zData)
        except:
            self.onlineTask.setDrawFlag(True)
        else:
            self.onlineTask.setDrawFlag(True)

    # playCard 槽函数
    def onlinePlaySpinBoxChanged(self, value: int):
        playTextBrowserMarkdown = self.getPlayTextBrowserMarkdown(value)
        self.playTextBrowser.setMarkdown(playTextBrowserMarkdown)
        self.playSpinBoxValueChanged.emit(value)

    # UI冻结/解冻方法
    def setCardFrozen(self):
        self.setComboBox_1.setEnabled(False)
        self.setComboBox_2.setEnabled(False)
        self.setStartButton.setEnabled(False)

    def setCardUnfrozen(self):
        self.setComboBox_1.setEnabled(True)
        self.setComboBox_2.setEnabled(True)
        self.setStartButton.setEnabled(True)

    def playCardFrozen(self):
        self.playSpinBox.setEnabled(False)
        self.playPushButton.setEnabled(False)

    def playCardUnfrozen(self):
        self.playSpinBox.setEnabled(True)
        self.playPushButton.setEnabled(True)
