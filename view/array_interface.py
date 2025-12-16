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
from qfluentwidgets import FluentIcon, InfoBar, InfoBarPosition

import os
import numpy as np

from view.Ui_ArrayInterface import Ui_ArrayInterface

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from typing import cast

from thread_manager import FunctionWorker


class ArrayInterface(Ui_ArrayInterface, QWidget):
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
        self.arrayTaskWorker: Optional[FunctionWorker] = None

        # 任务引用（由主窗口注入）
        self.arrayTask = None
        self.paramConfig: Optional[QSettings] = None

        self.setReloadButton.setIcon(FluentIcon.CANCEL)
        self.setSaveButton.setIcon(FluentIcon.SAVE)
        self.setStartButton.setIcon(FluentIcon.PLAY)

        self.condReloadButton.setIcon(FluentIcon.CANCEL)
        self.condSaveButton.setIcon(FluentIcon.SAVE)
        self.condStartButton.setIcon(FluentIcon.PLAY)

        self._fig: Optional[Figure] = None
        self._canvas: Optional[FigureCanvas] = None
        self._ax: Optional[Axes3D] = None

        # 坐标轴范围（用于滚轮缩放和数据过滤）
        self.colors = None
        self._xlim = [-1.5, 1.5]
        self._ylim = [-1.5, 1.5]
        self._zlim = [-1.0, 1.0]
        self._scale_factor = 1.1  # 缩放因子

        # add shadow effect to card
        self.setShadowEffect(self.setCard)
        self.setShadowEffect(self.condCard)
        self.setShadowEffect(self.showCard)

    def setArrayTask(self, arrayTask):
        """
        设置离线任务引用。

        Parameters
        ----------
        arrayTask : ArrayTask
            阵列任务对象。
        """
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
        self.setReloadButton.clicked.connect(self.arrayReloadButtonClicked)
        self.setSaveButton.clicked.connect(self.arraySaveButtonClicked)
        self.setStartButton.clicked.connect(self.arraySetStartButtonClicked)

        self.condReloadButton.clicked.connect(self.arrayReloadButtonClicked)
        self.condSaveButton.clicked.connect(self.arraySaveButtonClicked)
        self.condStartButton.clicked.connect(self.arrayCondStartButtonClicked)

    def initSetTable(self):
        """
        初始化结果表格显示属性与列头。

        Returns
        -------
        None
        """
        self.setTableWidget.setBorderVisible(True)
        self.setTableWidget.setBorderRadius(8)

        self.setTableWidget.setWordWrap(False)
        self.setTableWidget.setRowCount(5)
        self.setTableWidget.setColumnCount(4)
        self.setTableWidget.setHorizontalHeaderLabels(['麦克风编号', 'X (m)', 'Y (m)', 'Z (m)'])
        self.setTableWidget.verticalHeader().hide()
        self.setTableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setTableWidget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        micCoords = self.arrayTask.param.getMicCoords()
        for i, coord in enumerate(micCoords):
            self.setTableWidget.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self.setTableWidget.item(i, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setTableWidget.setItem(i, 1, QTableWidgetItem(f"{coord[0]:.3f}"))
            self.setTableWidget.setItem(i, 2, QTableWidgetItem(f"{coord[1]:.3f}"))
            self.setTableWidget.setItem(i, 3, QTableWidgetItem(f"{coord[2]:.3f}"))

    def updateSetTable(self):
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
        self.setTableWidget.clearContents()
        self.setTableWidget.setRowCount(5)

        micCoords = self.arrayTask.param.getMicCoords()
        for i, coord in enumerate(micCoords):
            self.setTableWidget.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.setTableWidget.item(i, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setTableWidget.setItem(i, 1, QTableWidgetItem(f"{coord[0]:.3f}"))
            self.setTableWidget.setItem(i, 2, QTableWidgetItem(f"{coord[1]:.3f}"))
            self.setTableWidget.setItem(i, 3, QTableWidgetItem(f"{coord[2]:.3f}"))

    def initCondTable(self):
        """
        初始化结果表格显示属性与列头。

        Returns
        -------
        None
        """
        self.condTableWidget.setBorderVisible(True)
        self.condTableWidget.setBorderRadius(8)

        self.condTableWidget.setWordWrap(False)
        self.condTableWidget.setRowCount(4)
        self.condTableWidget.setColumnCount(3)
        self.condTableWidget.setHorizontalHeaderLabels(['约束', '上界/数值', '下届/无'])
        self.condTableWidget.verticalHeader().hide()
        self.condTableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.condTableWidget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        # self.condTableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        scanConstraints = self.arrayTask.param.getConstraints()
        scanStep = self.arrayTask.param.getStep()
        self.condTableWidget.setItem(0, 0, QTableWidgetItem("X 轴"))
        self.condTableWidget.item(0, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.condTableWidget.setItem(0, 1, QTableWidgetItem(f"{scanConstraints[0][1]:.3f}"))
        self.condTableWidget.setItem(0, 2, QTableWidgetItem(f"{scanConstraints[0][0]:.3f}"))
        self.condTableWidget.setItem(1, 0, QTableWidgetItem("Y 轴"))
        self.condTableWidget.item(1, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.condTableWidget.setItem(1, 1, QTableWidgetItem(f"{scanConstraints[1][1]:.3f}"))
        self.condTableWidget.setItem(1, 2, QTableWidgetItem(f"{scanConstraints[1][0]:.3f}"))
        self.condTableWidget.setItem(2, 0, QTableWidgetItem("Z 轴"))
        self.condTableWidget.item(2, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.condTableWidget.setItem(2, 1, QTableWidgetItem(f"{scanConstraints[2][1]:.3f}"))
        self.condTableWidget.setItem(2, 2, QTableWidgetItem(f"{scanConstraints[2][0]:.3f}"))
        self.condTableWidget.setItem(3, 0, QTableWidgetItem("步长"))
        self.condTableWidget.item(3, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.condTableWidget.setItem(3, 1, QTableWidgetItem(f"{scanStep:.3f}"))
        self.condTableWidget.setItem(3, 2, QTableWidgetItem("-"))
        self.condTableWidget.item(3, 2).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

    def updateCondTable(self):
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
        self.condTableWidget.clearContents()
        self.condTableWidget.setRowCount(4)

        scanConstraints = self.arrayTask.param.getConstraints()
        scanStep = self.arrayTask.param.getStep()
        self.condTableWidget.setItem(0, 0, QTableWidgetItem("X 轴"))
        self.condTableWidget.item(0, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.condTableWidget.setItem(0, 1, QTableWidgetItem(f"{scanConstraints[0][1]:.3f}"))
        self.condTableWidget.setItem(0, 2, QTableWidgetItem(f"{scanConstraints[0][0]:.3f}"))
        self.condTableWidget.setItem(1, 0, QTableWidgetItem("Y 轴"))
        self.condTableWidget.item(1, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.condTableWidget.setItem(1, 1, QTableWidgetItem(f"{scanConstraints[1][1]:.3f}"))
        self.condTableWidget.setItem(1, 2, QTableWidgetItem(f"{scanConstraints[1][0]:.3f}"))
        self.condTableWidget.setItem(2, 0, QTableWidgetItem("Z 轴"))
        self.condTableWidget.item(2, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.condTableWidget.setItem(2, 1, QTableWidgetItem(f"{scanConstraints[2][1]:.3f}"))
        self.condTableWidget.setItem(2, 2, QTableWidgetItem(f"{scanConstraints[2][0]:.3f}"))
        self.condTableWidget.setItem(3, 0, QTableWidgetItem("步长"))
        self.condTableWidget.item(3, 0).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.condTableWidget.setItem(3, 1, QTableWidgetItem(f"{scanStep:.3f}"))
        self.condTableWidget.setItem(3, 2, QTableWidgetItem("-"))
        self.condTableWidget.item(3, 2).setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

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

        self.colors = np.linspace(0.1, 1, 5)
        micCoords = self.arrayTask.param.getMicCoords()

        self._scatter = self._ax.scatter(micCoords[:, 0], micCoords[:, 1], micCoords[:, 2], c=self.colors, cmap='tab20b', s=30, alpha=0.9)

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

    def updateScatter(self):
        """
        更新散点图数据。

        Returns
        -------
        None
        """
        if self._ax is None:
            return
        self._scatter.remove()
        micCoords = self.arrayTask.param.getMicCoords()
        self._scatter = self._ax.scatter(micCoords[:, 0], micCoords[:, 1], micCoords[:, 2], c=self.colors, cmap='tab20b', s=30, alpha=0.9)

        self._canvas.draw()


    # setCard 槽函数
    def arrayReloadButtonClicked(self):
        if self.arrayTask.param.validParamOfConfig(self.paramConfig):
            self.arrayTask.param.loadParamFromConfig(self.paramConfig)
        else:
            InfoBar.warning(
                title='[参数加载]',
                content='麦克风阵列参数非法改动，已重置',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
            self.arrayTask.param.resetParamOfConfig(self.paramConfig)
        self.updateSetTable()
        self.updateCondTable()
        self.updateScatter()


    def arraySaveButtonClicked(self):
        self.arrayTask.param.saveParamToConfig(self.paramConfig)

    def arraySetStartButtonClicked(self):
        """
        从 setTableWidget 中读取用户输入的麦克风坐标，校验并更新参数。
        若不符合要求则使用 InfoBar 警告提示用户。
        """
        try:
            # 从表格读取麦克风坐标
            mic_coords = []
            for i in range(5):
                x_item = self.setTableWidget.item(i, 1)
                y_item = self.setTableWidget.item(i, 2)
                z_item = self.setTableWidget.item(i, 3)
                if x_item is None or y_item is None or z_item is None:
                    raise ValueError("表格数据不完整")
                x = float(x_item.text())
                y = float(y_item.text())
                z = float(z_item.text())
                mic_coords.append([x, y, z])

            # 获取当前约束参数用于校验
            xlim, ylim, zlim = self.arrayTask.param.getConstraints()
            step = self.arrayTask.param.getStep()

            # 使用 validParamOfGiven 校验参数
            from task.array_task import ArrayParam
            if ArrayParam.validParamOfGiven(mic_coords, xlim, ylim, zlim, step):
                # 校验通过，更新参数
                self.arrayTask.param.setMicCoords(mic_coords)
                InfoBar.success(
                    title='[参数设置]',
                    content='麦克风阵列坐标更新成功',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self._mainWindow
                )
            else:
                # 校验不通过，警告用户
                InfoBar.warning(
                    title='[参数设置]',
                    content='麦克风阵列坐标不满足几何约束！\n',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=4000,
                    parent=self._mainWindow
                )
                return
        except ValueError as e:
            InfoBar.error(
                title='[参数设置]',
                content=f'输入格式错误!',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
            return
        except Exception as e:
            InfoBar.error(
                title='[参数设置]',
                content=f'参数读取失败!',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
            return

        self.updateScatter()

    def arrayCondStartButtonClicked(self):
        """
        从 condTableWidget 中读取用户输入的约束参数，校验并启动条件数扫描任务。
        若不符合要求则使用 InfoBar 警告提示用户。
        """
        try:
            # 从表格读取约束参数
            xlim_upper = float(self.condTableWidget.item(0, 1).text())
            xlim_lower = float(self.condTableWidget.item(0, 2).text())
            ylim_upper = float(self.condTableWidget.item(1, 1).text())
            ylim_lower = float(self.condTableWidget.item(1, 2).text())
            zlim_upper = float(self.condTableWidget.item(2, 1).text())
            zlim_lower = float(self.condTableWidget.item(2, 2).text())
            step = float(self.condTableWidget.item(3, 1).text())

            xlim = [xlim_lower, xlim_upper]
            ylim = [ylim_lower, ylim_upper]
            zlim = [zlim_lower, zlim_upper]

            # 获取当前麦克风坐标用于校验
            mic_coords = self.arrayTask.param.getMicCoords()

            # 使用 validParamOfGiven 校验参数
            from task.array_task import ArrayParam
            if not ArrayParam.validParamOfGiven(mic_coords, xlim, ylim, zlim, step):
                InfoBar.warning(
                    title='[参数设置]',
                    content='约束参数不满足要求：下界须小于等于上界，步长须在(0,1]范围内',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=3000,
                    parent=self._mainWindow
                )
                return

            # 校验通过，更新参数
            self.arrayTask.param.setConstraints(xlim, ylim, zlim)
            self.arrayTask.param.setStep(step)

        except ValueError:
            InfoBar.error(
                title='[参数设置]',
                content='输入格式错误！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
            return
        except Exception:
            InfoBar.error(
                title='[参数设置]',
                content='参数读取失败！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )
            return

        # 冻结相关卡片，启动任务线程
        self._mainWindow.arrayRelatedCardFrozen()

        self.arrayTaskWorker = FunctionWorker(self.arrayTask.startArrayTask)
        self.arrayTaskWorker.signals.result.connect(self.arrayCondStartButtonThreadFinished)
        self.arrayTaskWorker.signals.error.connect(self.arrayCondStartButtonThreadError)
        self.arrayTaskWorker.start()

    def arrayCondStartButtonThreadFinished(self, result):
        """
        条件数扫描任务完成后的回调。

        Parameters
        ----------
        result : bool
            任务执行结果，True 表示成功。
        """
        self._mainWindow.arrayRelatedCardUnfrozen()

        self.arrayTaskWorker.signals.result.disconnect()
        self.arrayTaskWorker.signals.error.disconnect()
        self.arrayTaskWorker = None

        if result:
            InfoBar.success(
                title='[条件数扫描]',
                content=f'扫描完成，共 {self.arrayTask.getDataLen()} 个数据点，报告已保存',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3000,
                parent=self._mainWindow
            )
        else:
            InfoBar.error(
                title='[条件数扫描]',
                content='扫描失败，请检查参数设置',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self._mainWindow
            )

    def arrayCondStartButtonThreadError(self):
        """
        条件数扫描任务出错时的回调。
        """
        self._mainWindow.arrayRelatedCardUnfrozen()

        self.arrayTaskWorker.signals.result.disconnect()
        self.arrayTaskWorker.signals.error.disconnect()
        self.arrayTaskWorker = None

        InfoBar.error(
            title='[条件数扫描]',
            content='扫描任务执行出错',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self._mainWindow
        )

    # UI冻结/解冻方法
    def setCardFrozen(self):
        self.setTableWidget.setEnabled(False)
        self.setStartButton.setEnabled(False)

    def setCardUnfrozen(self):
        self.setTableWidget.setEnabled(True)
        self.setStartButton.setEnabled(True)

    def condCardFrozen(self):
        self.condTableWidget.setEnabled(False)
        self.condStartButton.setEnabled(False)

    def condCardUnfrozen(self):
        self.condTableWidget.setEnabled(True)
        self.condStartButton.setEnabled(True)

