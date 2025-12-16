"""
在线定位任务

概述
----
采集线程持续从采集卡读取数据帧，放入队列；主处理循环从队列取帧，
��用定位算法（当前为 GCC-PHAT）并通过 ``step`` 信号上报；提供开始/停止控制并清理资源。

线程模型
--------
- 生产者线程：``producerThreadFunction``
- 消费者：在本对象绑定的 QThread 上运行（由 ``FunctionLoopWorker`` 调用 ``startOnlineTask``）。
"""

import threading
import queue

from PyQt5.QtCore import pyqtSignal

from driver.hkusb_driver import HkDriver
from method.gcc_phat import GccPhat


class OnlineParam(object):
    """
    在线任务参数。

    Attributes
    ----------
    _frameLenList : list of int
        可选帧长列表。
    _frameLenCode : int
        当前帧长索引。
    _methodCode : int
        算法代码（0: GCC-PHAT）。
    """
    def __init__(self):
        self._frameLenList = [512, 1024, 2048, 4096, 8192]
        self._frameLenCode = 2

        self._methodCode = 0

    def _reset(self):
        """
        重置为默认参数。

        Returns
        -------
        None
        """
        self._frameLenCode = 2
        self._methodCode = 0

    def getFrameLenList(self):
        """
        返回可选帧长列表。

        Returns
        -------
        list of int
        """
        return self._frameLenList

    def getFrameLenCode(self):
        """
        返回当前帧长索引。

        Returns
        -------
        int
        """
        return self._frameLenCode

    def getMethodCode(self):
        """
        返回算法代码。

        Returns
        -------
        int
            0 表示 GCC-PHAT。
        """
        return self._methodCode

    def setFrameLenCode(self, frameLenCode):
        """
        设置帧长索引。

        Parameters
        ----------
        frameLenCode : int
        """
        self._frameLenCode = frameLenCode

    def setMethodCode(self, methodCode):
        """
        设置算法代码。

        Parameters
        ----------
        methodCode : int
        """
        self._methodCode = methodCode

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
            frameLenCode = int(config.value("ONLINE/FRAME_LEN_CODE", -1))
            methodCode = int(config.value("ONLINE/METHOD_CODE", -1))
        except:
            return False
        else:
            if frameLenCode == -1 or methodCode == -1:
                return False
            if frameLenCode not in [0, 1, 2, 3, 4]:
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
        self._frameLenCode = int(config.value("ONLINE/FRAME_LEN_CODE", 2))
        self._methodCode = int(config.value("ONLINE/METHOD_CODE", -1))

    def saveParamToConfig(self, config):
        """
        保存参数到 QSettings。

        Parameters
        ----------
        config : QSettings
        """
        config.setValue("ONLINE/FRAME_LEN_CODE", self._frameLenCode)
        config.setValue("ONLINE/METHOD_CODE", self._methodCode)

    def resetParamOfConfig(self, config):
        """
        重置为默认并保存。

        Parameters
        ----------
        config : QSettings
        """
        self._reset()
        self.saveParamToConfig(config)


class OnlineTask(object):
    """
    在线采集与定位任务。

    Parameters
    ----------
    hkDriver : HkDriver
        采集卡驱动实例。

    Attributes
    ----------
    param : OnlineParam
        任务参数对象。
    _startFlag : bool
        运行标志。
    _drawFlag : bool
        是否绘图（避免 UI 频繁刷新导致阻塞）。
    _dataQueue : queue.Queue
        数据缓冲队列（生产者-消费者）。
    _gccPhat : GccPhat
        当前算法实现。
    """
    def __init__(self, hkDriver: HkDriver):
        self._hkDriver = hkDriver
        self._gccPhat = GccPhat()

        self.param = OnlineParam()

        self._startFlag = False
        self._drawFlag = True

        self._dataQueue = queue.Queue(maxsize=3)

    def getStartFlag(self):
        """
        是否处于运行状态。

        Returns
        -------
        bool
        """
        return self._startFlag

    def setDrawFlag(self, drawFlag):
        """
        设置是否绘图。

        Parameters
        ----------
        drawFlag : bool
        """
        self._drawFlag = drawFlag

    def producerThreadFunction(self, sampleNum):
        """
        生产者线程：采样并推入队列。

        Parameters
        ----------
        sampleNum : int
            帧长度（点）。

        Returns
        -------
        None
        """
        while self._startFlag:
            try:
                # Simulate data acquisition
                dataBuffer = self._hkDriver.sampleBuffer(sampleNum)
                self._dataQueue.put(dataBuffer, block=True, timeout=0.5)
            except:
                break

    def startOnlineTask(self, stepSignal: pyqtSignal(object)):
        """
        启动在线任务的主循环（由 ``FunctionLoopWorker`` 在线程中调用）。

        Parameters
        ----------
        stepSignal : pyqtSignal
            外层传入的 ``step`` 信号，用于上报中间定位结果。

        Returns
        -------
        bool
            任务是否正常结束。
        """
        method = None
        producerThread = None
        try:
            self._dataQueue.queue.clear()
            retOpen = self._hkDriver.openUsb()
            if retOpen != 0:
                self._hkDriver.closeUsb()
                return False
            self._startFlag = True
            sampleRate = self._hkDriver.param.getSampleRate()
            sampleNum = self.param.getFrameLenList()[self.param.getFrameLenCode()]
            if self.param.getMethodCode() == 0:
                method = self._gccPhat
                method.clearFilter()

            producerThread = threading.Thread(target=self.producerThreadFunction, args=(sampleNum, ))

            producerThread.start()

            while self._startFlag:
                dataBuffer = self._dataQueue.get(timeout=1.0)
                if not dataBuffer:
                    raise queue.Empty()
                if method:
                    result = method.onlineProcessData(dataBuffer, sampleRate, sampleNum)
                    if self._drawFlag:
                        stepSignal.emit(result)
                self._dataQueue.task_done()
        except:
            self._startFlag = False
            if producerThread:
                producerThread.join()
            self._dataQueue.queue.clear()
            self._hkDriver.closeUsb()
            return False
        else:
            self._startFlag = False
            if producerThread:
                producerThread.join()
            self._dataQueue.queue.clear()
            self._hkDriver.closeUsb()
            return True

    def stopOnlineTask(self):
        """
        请求停止任务（安全停止）。

        Returns
        -------
        None
        """
        self._startFlag = False

    def __del__(self):
        self.stopOnlineTask()