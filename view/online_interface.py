# coding:utf-8
"""
在线界面（参数设置 + 三维散点实时展示）

概述
----
提供在线定位参数设置与三维散点实时展示控件。
"""
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect
from qfluentwidgets import FluentIcon

import numpy as np

from view.Ui_OnlineInterface import Ui_OnlineInterface

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from typing import Optional, cast


class OnlineInterface(Ui_OnlineInterface, QWidget):
    """
    在线定位相关卡片集合的界面封装。

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
        self.playPushButton.setIcon(FluentIcon.PLAY)

        self._fig: Optional[Figure] = None
        self._canvas: Optional[FigureCanvas] = None
        self._ax: Optional[Axes3D] = None

        # add shadow effect to card
        self.setShadowEffect(self.setCard)
        self.setShadowEffect(self.playCard)
        self.setShadowEffect(self.stateCard)
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

    def initScatter(self):
        """
        初始化 3D 散点图组件。

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