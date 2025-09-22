# coding:utf-8
"""
离线界面（文件选择 + 结果展示）

概述
----
提供离线算法的文件选择、方法设置与启动按钮；表格与 3D 散点用于回放定位结果。
"""
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QHeaderView, QTableWidgetItem, QAbstractItemView
from qfluentwidgets import FluentIcon, PushSettingCard
from qfluentwidgets import FluentIcon as FIF

import os
import numpy as np

from view.Ui_OfflineInterface import Ui_OfflineInterface

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from typing import Optional, cast


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

        # add shadow effect to card
        self.setShadowEffect(self.setCard)
        self.setShadowEffect(self.resultCard)
        self.setShadowEffect(self.showCard)


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
        self._canvas = FigureCanvas(self._fig)

        self.showVerticalLayout.addWidget(self._canvas)
        self._ax = cast(Axes3D, self._fig.add_subplot(111, projection='3d'))
        self._ax.set_xlabel('X')
        self._ax.set_ylabel('Y')
        self._ax.set_zlabel('Z')
        self._ax.grid(True)

        colors = np.linspace(0.1, 1, 1)
        self._scatter = self._ax.scatter([0], [0], [0], c=colors, cmap='tab20b', s=30, alpha=0.9)

        self._ax.set_xlim(0, 1.5)
        self._ax.set_ylim(0, 1.5)
        self._ax.set_zlim(-0.5, 1.0)
        self._ax.view_init(30, -60)

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