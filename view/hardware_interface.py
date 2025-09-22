# coding:utf-8
"""
硬件设置界面（采集卡 + 扬声器）

概述
----
提供采集卡与扬声器的参数设置、发现与测试入口；仅包含界面元素的初始化与阴影效果设置，
具体业务逻辑由上层窗口绑定（见 ``demo.Window``）。
"""
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QButtonGroup
from qfluentwidgets import FluentIcon, InfoBarIcon

from view.Ui_HardwareInterface import Ui_HardwareInterface


class HardwareInterface(Ui_HardwareInterface, QWidget):
    """
    硬件设置卡片集合的界面封装。

    Parameters
    ----------
    parent : QWidget | None, optional
        父级窗口。
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

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
