# coding:utf-8
"""
离线界面（文件选择 + 结果展示）

概述
----
提供离线算法的文件选择、方法设置与启动按钮；表格与 3D 散点用于回放定位结果。
包含具体任务逻辑实现。
"""
from typing import Optional

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QHeaderView, QTableWidgetItem, QAbstractItemView, QFileDialog, QVBoxLayout, QFrame
from qfluentwidgets import FluentIcon, PushSettingCard, InfoBar, InfoBarPosition
from qfluentwidgets import FluentIcon as FIF

import os
import numpy as np

from view.Ui_OfflineInterface import Ui_OfflineInterface

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from typing import cast

from thread_manager import FunctionWorker


class OfflineInterface(Ui_OfflineInterface, QWidget):
    """
    离线任务相关卡片集合的界面封装。

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
        self.offlineTaskWorker: Optional[FunctionWorker] = None

        # 任务引用（由主窗口注入）
        self.offlineTask = None
        self.arrayTask = None
        self.paramConfig: Optional[QSettings] = None

        self.setReloadButton.setIcon(FluentIcon.CANCEL)
        self.setSaveButton.setIcon(FluentIcon.SAVE)
        self.setStartButton.setIcon(FluentIcon.PLAY)

        self.setChooseFileCard = PushSettingCard(
            text='选择文件',
            icon=FIF.DOWNLOAD,
            title="目标实验文件",
            content=os.getcwd(),
        )

        self.setVerticalLayout_2.addWidget(self.setChooseFileCard)

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
        self.setShadowEffect(self.resultCard)
        self.setShadowEffect(self.showCard)

    def setOfflineTask(self, offlineTask, arrayTask):
        """
        设置离线任务引用。

        Parameters
        ----------
        offlineTask : OfflineTask
            离线任务对象。
        arrayTask : ArrayTask
            阵列任务对象。
        """
        self.offlineTask = offlineTask
        self.arrayTask = arrayTask

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
        self.setReloadButton.clicked.connect(self.offlineReloadButtonClicked)
        self.setSaveButton.clicked.connect(self.offlineSaveButtonClicked)
        self.setChooseFileCard.clicked.connect(self.offlineSetChooseFileClicked)
        self.setStartButton.clicked.connect(self.offlineSetStartButtonClicked)
        self.resultHorizontalSlider.valueChanged.connect(self.offlineResultHorizontalSliderChanged)

    def initTable(self):
        """
        初始化结果表格显示属性与列头。

        Returns
        -------
        None
        """
        self.resultTableWidget.setBorderVisible(True)
        self.resultTableWidget.setBorderRadius(8)

        self.resultTableWidget.setWordWrap(False)
        self.resultTableWidget.setRowCount(0)
        self.resultTableWidget.setColumnCount(5)
        self.resultTableWidget.setHorizontalHeaderLabels(['声源编号', 'X (m)', 'Y (m)', 'Z (m)', 'D (m)'])
        self.resultTableWidget.verticalHeader().hide()
        self.resultTableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.resultTableWidget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.resultTableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def updateTable(self, xData, yData, zData):
        """
        根据传入坐标数据刷新表格。

        Parameters
        ----------
        xData, yData, zData : array-like
            三维坐标序列。

        Returns
        -------
        None
        """
        self.resultTableWidget.clearContents()
        self.resultTableWidget.setRowCount(len(xData))
        for i, (x, y, z) in enumerate(zip(xData, yData, zData)):
            self.resultTableWidget.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self.resultTableWidget.setItem(i, 1, QTableWidgetItem(f"{x:.2f}"))
            self.resultTableWidget.setItem(i, 2, QTableWidgetItem(f"{y:.2f}"))
            self.resultTableWidget.setItem(i, 3, QTableWidgetItem(f"{z:.2f}"))
            d = np.sqrt(x**2 + y**2 + z**2)
            self.resultTableWidget.setItem(i, 4, QTableWidgetItem(f"{d:.2f}"))

    def clearTable(self):
        """
        清空表格内容。

        Returns
        -------
        None
        """
        self.resultTableWidget.clearContents()
        self.resultTableWidget.setRowCount(0)

    def initScatter(self):
        """
        初始化结果 3D 散点图。

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

    def initValueOffline(self):
        """
        初始化离线实验相关下拉框。
        """
        self.setComboBox.addItems(['GCC-PHAT单声源定位'])

    def displayValueOffline(self):
        """
        回显离线实验参数。
        """
        self.setComboBox.setCurrentIndex(self.offlineTask.param.getMethodCode())

    # setCard 槽函数
    def offlineReloadButtonClicked(self):
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
                parent=self._mainWindow
            )
            self.offlineTask.param.resetParamOfConfig(self.paramConfig)
        self.displayValueOffline()

    def offlineSaveButtonClicked(self):
        self.offlineTask.param.saveParamToConfig(self.paramConfig)

    def offlineSetChooseFileClicked(self):
        fileName, _ = QFileDialog.getOpenFileName(
            self._mainWindow,
            '选择数据文件',
            os.getcwd(),
            'Data files (*.npz)'
            )
        if fileName:
            self.offlineTask.param.setDataFilePath(fileName)
            self.setChooseFileCard.setContent(fileName)

    def offlineSetStartButtonClicked(self):
        if not self.offlineTask.param.getDataFilePath():
            InfoBar.warning(
                title='[文件选择]',
                content='未选择数据文件',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
        else:
            self.offlineTaskRelatedCardFrozen()
            self._mainWindow.arrayRelatedCardFrozen()

            self.resultHorizontalSlider.setValue(0)
            # create a thread to test the sample card
            self.offlineTaskWorker = FunctionWorker(self.offlineTask.startOfflineTask, self.arrayTask.param.getMicCoords())
            self.offlineTaskWorker.signals.result.connect(self.offlineStartButtonThreadFinished)
            self.offlineTaskWorker.signals.error.connect(self.offlineStartButtonThreadError)
            self.offlineTaskWorker.start()

    def offlineStartButtonThreadFinished(self, result):
        self.offlineTaskRelatedCardUnfrozen()
        self._mainWindow.arrayRelatedCardUnfrozen()

        self.resultHorizontalSlider.setValue(0)
        self.offlineTaskWorker.signals.result.disconnect()
        self.offlineTaskWorker.signals.error.disconnect()
        self.offlineTaskWorker = None
        if result:
            self.resultHorizontalSlider.setMaximum(self.offlineTask.getDataLen())
            InfoBar.success(
                title='[离线实验]',
                content='离线实验完成',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
        else:
            self.resultHorizontalSlider.setMaximum(0)
            InfoBar.error(
                title='[离线实验]',
                content='输入数据有误, 请检查输入文件选择',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )

    def offlineStartButtonThreadError(self):
        self.offlineTaskRelatedCardUnfrozen()
        self._mainWindow.arrayRelatedCardUnfrozen()

        self.resultHorizontalSlider.setMaximum(0)

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
            parent=self._mainWindow
        )

    def offlineResultHorizontalSliderChanged(self, value):
        self.resultChooseLabel.setText(f"数据帧: {value} / {self.offlineTask.getDataLen()}")
        if value == 0:
            self.clearScatter()
            self.clearTable()
        else:
            dataFrame = self.offlineTask.getDataHolder()[..., value - 1]
            try:
                xData, yData, zData = [0.0], [0.0], [0.0]
                for loc in dataFrame:
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
                self.updateTable(xData[1:], yData[1:], zData[1:])
            except:
                self.clearScatter()
                self.clearTable()

    # UI冻结/解冻方法
    def setCardFrozen(self):
        self.setChooseFileCard.setEnabled(False)
        self.setComboBox.setEnabled(False)

    def setCardUnfrozen(self):
        self.setChooseFileCard.setEnabled(True)
        self.setComboBox.setEnabled(True)

    def resultCardFrozen(self):
        self.resultHorizontalSlider.setEnabled(False)

    def resultCardUnfrozen(self):
        self.resultHorizontalSlider.setEnabled(True)

    def offlineTaskRelatedCardFrozen(self):
        self.setCardFrozen()
        self.resultCardFrozen()

    def offlineTaskRelatedCardUnfrozen(self):
        self.setCardUnfrozen()
        self.resultCardUnfrozen()
