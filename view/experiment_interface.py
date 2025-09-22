# coding:utf-8
"""
批量实验界面（参数设置 + 进度显示 + 状态监视）

概述
----
提供批量实验参数设置、开始/停止按钮；圆环进度与状态卡展示硬件与计划进度；
具体任务逻辑在上层窗口绑定（见 ``demo.Window``）。
"""
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect
from qfluentwidgets import FluentIcon

from view.Ui_ExperimentInterface import Ui_ExperimentInterface


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

        # set the icon of button
        self.batchReloadButton.setIcon(FluentIcon.CANCEL)
        self.batchSaveButton.setIcon(FluentIcon.SAVE)
        self.batchStartButton.setIcon(FluentIcon.PLAY)

        # add shadow effect to card
        self.setShadowEffect(self.batchCard)
        self.setShadowEffect(self.tqdmCard)
        self.setShadowEffect(self.stateCard)

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
