"""
麦克风阵列条件数扫描任务

概述
----
针对五元麦克风阵列进行条件数扫描，评估定位精度随声源位置的变化。

功能
--------
- 麦克风阵列坐标配置
- 搜索空间约束设置
- 条件数网格扫描
- 扫描结果保存为 Excel 报告
"""

import os
import numpy as np
import pandas as pd

# 声速参数（单位：m/s），简化温度修正
t = 22
c = 331.45 * np.sqrt(1 + t / 273.16)
# 其他参数
epsilon = 1e-8

class ArrayParam(object):
    """
    麦克风阵列条件数扫描参数。

    Attributes
    ----------
    _micCoords : np.ndarray
        麦克风坐标 (5, 3)。
    _xlim : list of float
        X 轴搜索范围。
    _ylim : list of float
        Y 轴搜索范围。
    _zlim : list of float
        Z 轴搜索范围。
    _step : float
        网格搜索步长。
    """
    def __init__(self):
        self._micCoords = np.array([
            [0.0, 0.0, 0.0],
            [0.32, 0.0, 0.0],
            [0.0, 0.32, 0.0],
            [0.128, 0.128, 0.0],
            [0.0, 0.0, 0.32]
        ])

        self._xlim = [-1.0, 1.0]
        self._ylim = [-1.0, 1.0]
        self._zlim = [-1.0, 1.0]
        self._step = 0.02

    def _reset(self):
        """
        重置为默认参数。

        Returns
        -------
        None
        """
        self._micCoords = np.array([
            [0.0, 0.0, 0.0],
            [0.32, 0.0, 0.0],
            [0.0, 0.32, 0.0],
            [0.128, 0.128, 0.0],
            [0.0, 0.0, 0.32]
        ])

        self._xlim = [-1.0, 1.0]
        self._ylim = [-1.0, 1.0]
        self._zlim = [-1.0, 1.0]
        self._step = 0.02

    def getMicCoords(self):
        """
        返回麦克风坐标。

        Returns
        -------
        np.ndarray
            形状为 ``(5, 3)`` 的麦克风坐标。
        """
        return self._micCoords

    def setMicCoords(self, micCoords):
        """
        设置麦克风坐标。

        Parameters
        ----------
        micCoords : np.ndarray
            形状为 (5, 3) 的麦克风坐标数组。
        """
        self._micCoords = np.array(micCoords)

    def getConstraints(self):
        """
        获取搜索空间约束。

        Returns
        -------
        tuple of list
            ``(xlim, ylim, zlim)``
        """
        return self._xlim, self._ylim, self._zlim

    def setConstraints(self, xlim, ylim, zlim):
        """
        设置搜索空间约束。

        Parameters
        ----------
        xlim : list of float
        ylim : list of float
        zlim : list of float
        """
        self._xlim = xlim
        self._ylim = ylim
        self._zlim = zlim

    def getStep(self):
        """
        获取网格搜索步长。

        Returns
        -------
        float
        """
        return self._step

    def setStep(self, step):
        """
        设置网格搜索步长。

        Parameters
        ----------
        step : float
        """
        self._step = step

    @staticmethod
    def validParamOfConfig(config):
        """
        校验 QSettings 中的参数合法性。

        Parameters
        ----------
        config : QSettings

        Returns
        -------
        bool
        """
        try:
            # 读取麦克风坐标
            mic_coords_str = str(config.value("ARRAY/MIC_COORDS", ""))
            if not mic_coords_str:
                return False

            # 读取约束范围
            xlim_str = str(config.value("ARRAY/XLIM", ""))
            ylim_str = str(config.value("ARRAY/YLIM", ""))
            zlim_str = str(config.value("ARRAY/ZLIM", ""))
            step = float(config.value("ARRAY/STEP", -1))

            if not xlim_str or not ylim_str or not zlim_str:
                return False
            if step <= 0 or step > 1.0:
                return False

            # 尝试解析麦克风坐标
            mic_coords = eval(mic_coords_str)
            if len(mic_coords) != 5:
                return False
            for coord in mic_coords:
                if len(coord) != 3:
                    return False

            # 尝试解析约束范围
            xlim = eval(xlim_str)
            ylim = eval(ylim_str)
            zlim = eval(zlim_str)
            if len(xlim) != 2 or len(ylim) != 2 or len(zlim) != 2:
                return False

        except:
            return False
        else:
            return True

    @staticmethod
    def validParamOfGiven(mic_coords, xlim, ylim, zlim, step=None):
        """
        校验外部传入的参数是否满足要求。

        规则：
        1. 麦克风 4 必须不在麦克风 0、1、2 构成的平面上（即不共面）。
        2. 麦克风 3 必须在由麦克风 0、1、2、4 构成的四面体内部。
        3. 约束范围的下界必须小于等于上界（xlim[0] <= xlim[1] 等）。

        Parameters
        ----------
        mic_coords : array-like
            形状应为 (5, 3) 的麦克风坐标列表或数组。
        xlim, ylim, zlim : sequence of two floats
            每个轴的搜索范围 [lower, upper]。
        step : float, optional
            网格步长（若提供则检查为 (0, 1]）。

        Returns
        -------
        bool
            满足所有条件返回 True，否则 False。
        """
        try:
            mic = np.array(mic_coords, dtype=float)
            if mic.shape != (5, 3):
                return False

            # 检查约束范围的格式
            if not (hasattr(xlim, '__len__') and hasattr(ylim, '__len__') and hasattr(zlim, '__len__')):
                return False
            if len(xlim) != 2 or len(ylim) != 2 or len(zlim) != 2:
                return False

            # 规则3: 检查上下界关系
            if float(xlim[0]) > float(xlim[1]) or float(ylim[0]) > float(ylim[1]) or float(zlim[0]) > float(zlim[1]):
                return False

            # 可选：检查 step 合法性
            if step is not None:
                s = float(step)
                if s <= 0 or s > 1.0:
                    return False

            # 准备几何检验
            a = mic[0]
            b = mic[1]
            c = mic[2]
            p3 = mic[3]
            p4 = mic[4]

            # 规则1: 检查 0,1,2 是否能构成平面（即不共线），并且 p4 不在该平面上
            v1 = b - a
            v2 = c - a
            normal = np.cross(v1, v2)
            norm_len = float(np.linalg.norm(normal))
            if norm_len <= epsilon:
                # 0,1,2 共线或退化，无法定义平面 -> 不合法
                return False
            # 判断 p4 到平面的距离（用点乘判断是否在平面上）
            dist_plane = float(np.dot(normal, (p4 - a)))
            # 使用容忍度进行判断
            if abs(dist_plane) <= epsilon * max(1.0, norm_len):
                # p4 在平面上 -> 不合法
                return False

            # 规则2: 检查 p3 是否在由 a,b,c,p4 构成的四面体内部
            # 解线性方程：p3 = a + u*(b-a) + v*(c-a) + w*(p4-a)
            M = np.column_stack((b - a, c - a, p4 - a))
            detM = np.linalg.det(M)
            if abs(detM) <= epsilon:
                # 四面体退化 -> 不合法
                return False

            uvw = np.linalg.solve(M, p3 - a)
            u, v, w = float(uvw[0]), float(uvw[1]), float(uvw[2])
            tol = epsilon
            # 在四面体内部的充要条件：u,v,w >= 0 且 u+v+w <= 1
            if not (u >= -tol and v >= -tol and w >= -tol and (u + v + w) <= 1.0 + tol):
                return False

        except Exception:
            return False
        else:
            return True

    def loadParamFromConfig(self, config):
        """
        从 QSettings 加载参数。

        Parameters
        ----------
        config : QSettings
        """
        try:
            mic_coords_str = str(config.value("ARRAY/MIC_COORDS", ""))
            if mic_coords_str:
                self._micCoords = np.array(eval(mic_coords_str))

            xlim_str = str(config.value("ARRAY/XLIM", ""))
            ylim_str = str(config.value("ARRAY/YLIM", ""))
            zlim_str = str(config.value("ARRAY/ZLIM", ""))

            if xlim_str:
                self._xlim = list(eval(xlim_str))
            if ylim_str:
                self._ylim = list(eval(ylim_str))
            if zlim_str:
                self._zlim = list(eval(zlim_str))

            step = float(config.value("ARRAY/STEP", 0.02))
            self._step = step

            # 校验加载的参数是否满足几何约束
            if not ArrayParam.validParamOfGiven(self._micCoords, self._xlim, self._ylim, self._zlim, self._step):
                self._reset()
        except:
            self._reset()

    def saveParamToConfig(self, config):
        """
        保存参数到 QSettings。

        Parameters
        ----------
        config : QSettings
        """
        config.setValue("ARRAY/MIC_COORDS", str(np.array(self._micCoords).tolist()))
        config.setValue("ARRAY/XLIM", str(self._xlim))
        config.setValue("ARRAY/YLIM", str(self._ylim))
        config.setValue("ARRAY/ZLIM", str(self._zlim))
        config.setValue("ARRAY/STEP", self._step)

    def resetParamOfConfig(self, config):
        """
        重置为默认并保存。

        Parameters
        ----------
        config : QSettings
        """
        self._reset()
        self.saveParamToConfig(config)


class ArrayTask(object):
    """
    麦克风阵列条件数扫描任务。

    Attributes
    ----------
    param : ArrayParam
        任务参数。
    _dataHolder : np.ndarray | None
        条件数扫描结果缓存在内存，形状 ``(N, 4)``，每行为 ``[x, y, z, cond]``。
    _dataLen : int
        数据点数 ``N``。
    _startFlag : bool
        运行标志。
    """
    def __init__(self):
        self.param = ArrayParam()
        self._dataHolder = None
        self._dataLen = 0

        self._startFlag = False

    def getStartFlag(self):
        """
        是否处于运行状态。

        Returns
        -------
        bool
        """
        return self._startFlag

    def getDataHolder(self):
        """
        获取条件数扫描结果缓存。

        Returns
        -------
        np.ndarray | None
            形如 ``(N, 4)``，每行为 ``[x, y, z, cond]``。
        """
        return self._dataHolder

    def getDataLen(self):
        """
        返回数据点数。

        Returns
        -------
        int
            数据点数 ``N``。
        """
        return self._dataLen

    def startArrayTask(self, reportPath=None):
        """
        执行条件数扫描任务。

        Parameters
        ----------
        reportPath : str | None, optional
            报告文件保存路径，默认为当前目录下的 cond_report.xlsx。

        Returns
        -------
        bool
            成功返回 True。
        """
        result = None
        self._startFlag = True

        if self._startFlag:
            result = self.arrayScanCond()
        self._startFlag = False
        if result is not None and len(result) > 0:
            self._dataHolder = result
            self._dataLen = result.shape[0]
            # 保存报告到 Excel 文件
            if reportPath is None:
                reportPath = os.path.join(os.getcwd(), "cond_report.xlsx")
            self.saveReport(result, reportPath)

            return True
        else:
            self._dataHolder = None
            self._dataLen = 0
            return False

    def arrayScanCond(self):
        """
        执行条件数扫描。

        通过在搜索空间内网格化遍历声源位置，计算每个位置的定位矩阵条件数。
        条件数越小，定位精度越高。

        Returns
        -------
        np.ndarray of shape (N, 4)
            条件数扫描结果，每行为 ``[x, y, z, cond]``。
        """
        micCoords = np.array(self.param.getMicCoords())
        xlim, ylim, zlim = self.param.getConstraints()
        step = self.param.getStep()
        matrixQ = np.zeros((4, 4), dtype=np.float32)
        matrixQ[:, 0] = micCoords[1:, 0] - micCoords[0, 0]
        matrixQ[:, 1] = micCoords[1:, 1] - micCoords[0, 1]
        matrixQ[:, 2] = micCoords[1:, 2] - micCoords[0, 2]
        # 生成搜索网格
        xRange = np.arange(xlim[0], xlim[1] + 0.5 * step, step)
        yRange = np.arange(ylim[0], ylim[1] + 0.5 * step, step)
        zRange = np.arange(zlim[0], zlim[1] + 0.5 * step, step)
        gridPoints = np.stack(np.meshgrid(xRange, yRange, zRange, indexing='ij'), axis=-1).reshape(-1, 3)

        gridDist = np.zeros((gridPoints.shape[0], 4), dtype=np.float32)
        for idx, dloc in enumerate(gridPoints):
            if not self._startFlag:
                break
            dist = np.linalg.norm(micCoords - dloc, axis=1)
            for pairIdx in range(4):
                gridDist[idx, pairIdx] = float(dist[0] - dist[pairIdx + 1])
        results = []
        for idx, dloc in enumerate(gridPoints):
            if not self._startFlag:
                break
            dist = np.linalg.norm(micCoords - dloc, axis=1)
            if np.min(dist) < 0.05:  # 最小距离阈值
                continue
            gridDist = np.zeros((4,), dtype=np.float32)
            for pairIdx in range(4):
                gridDist[pairIdx] = float(dist[0] - dist[pairIdx + 1])
            matrixQ[:, 3] = gridDist
            # 计算条件数
            cond = np.linalg.cond(matrixQ, np.inf)
            if cond is not None and not np.isinf(cond) and not np.isnan(cond):
                results.append([*dloc, cond])

        if len(results) == 0:
            return None
        return np.array(results)

    @staticmethod
    def saveReport(data, filePath):
        """
        将条件数扫描结果保存为 Excel 报告。

        Parameters
        ----------
        data : np.ndarray of shape (N, 4)
            条件数扫描结果。
        filePath : str
            保存路径。
        """
        df = pd.DataFrame(data, columns=['X (m)', 'Y (m)', 'Z (m)', '条件数'])
        df = df.sort_values(by='条件数', ascending=True)
        df.to_excel(filePath, index=False, engine='openpyxl')

    def stopArrayTask(self):
        """
        请求停止任务（安全停止）。

        Returns
        -------
        None
        """
        self._startFlag = False

    def __del__(self):
        self.stopArrayTask()
