"""
离线定位任务

概述
----
读取离线数据文件（npz），按选择的方法进行定位计算；暴露结果缓存与长度信息，供界面回放。

数据格式
--------
- npz 包含键 ``'SAMPLE_RATE'`` (int), ``'DATA'`` (shape=(5, N))。
"""

import os
from method.gcc_phat import GccPhat


class OfflineParam(object):
    """
    离线任务参数。

    Attributes
    ----------
    _methodCode : int
        算法代码（0: GCC-PHAT）。
    _dataFilePath : str | None
        数据文件路径。
    """
    def __init__(self):
        self._methodCode = 0
        self._dataFilePath = None

    def _reset(self):
        """
        重置为默认参数。

        Returns
        -------
        None
        """
        self._methodCode = 0

    def getMethodCode(self):
        """
        返回方法代码。

        Returns
        -------
        int
            0 表示 GCC-PHAT。
        """
        return self._methodCode

    def getDataFilePath(self):
        """
        返回数据文件路径。

        Returns
        -------
        str | None
        """
        return self._dataFilePath

    def setMethodCode(self, methodCode):
        """
        设置方法代码。

        Parameters
        ----------
        methodCode : int
        """
        self._methodCode = methodCode

    def setDataFilePath(self, dataFilePath):
        """
        设置数据文件路径。

        Parameters
        ----------
        dataFilePath : str

        Raises
        ------
        FileNotFoundError
            当路径不存在时。
        """
        if not os.path.exists(dataFilePath):
            raise FileNotFoundError(f"Data file path '{dataFilePath}' does not exist.")
        else:
            self._dataFilePath = dataFilePath

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
            methodCode = int(config.value("OFFLINE/METHOD_CODE", -1))
        except:
            return False
        else:
            if methodCode == -1:
                return False
            if methodCode not in [0]:
                return False
            return True

    def loadParamFromConfig(self, config):
        """
        从 QSettings 加载参数。

        Parameters
        ----------
        config : QSettings
        """
        self._methodCode = int(config.value("OFFLINE/METHOD_CODE", -1))

    def saveParamToConfig(self, config):
        """
        保存参数到 QSettings。

        Parameters
        ----------
        config : QSettings
        """
        config.setValue("OFFLINE/METHOD_CODE", self._methodCode)

    def resetParamOfConfig(self, config):
        """
        重置为默认并保存。

        Parameters
        ----------
        config : QSettings
        """
        self._reset()
        self.saveParamToConfig(config)


class OfflineTask(object):
    """
    离线数据定位任务。

    Attributes
    ----------
    param : OfflineParam
        任务参数。
    _dataHolder : np.ndarray | None
        定位结果缓存在内存，形状 ``(1, 3, T)``。
    _dataLen : int
        帧数 ``T``。
    _startFlag : bool
        运行标志。
    """
    def __init__(self):
        self._gccPhat = GccPhat(filterLen=5)

        self.param = OfflineParam()
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
        获取定位结果缓存。

        Returns
        -------
        np.ndarray | None
            形如 ``(1, 3, T)``。
        """
        return self._dataHolder

    def getDataLen(self):
        """
        返回帧数。

        Returns
        -------
        int
            帧数 ``T``。
        """
        return self._dataLen

    def startOfflineTask(self, dataFilePath = None):
        """
        执行离线定位任务。

        Parameters
        ----------
        dataFilePath : str | None, optional
            保留参数，当前未使用（以 ``param`` 中的路径为准）。

        Returns
        -------
        bool
            成功返回 True。
        """
        method = None
        result = None
        self._startFlag = True
        if self.param.getMethodCode() == 0:
            method = self._gccPhat

        if self._startFlag and self.param.getDataFilePath() and method:
            result = method.offlineProcessData(self.param.getDataFilePath())
        self._startFlag = False
        if result is not None:
            self._dataHolder = result
            self._dataLen = result.shape[2]
            return True
        else:
            self._dataHolder = None
            self._dataLen = 0
            return False