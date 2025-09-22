"""
HKUSB6203 采集卡驱动封装

概述
----
提供参数对象 ``HkParam`` 用于保存/校验/读写配置（QSettings），以及 ``HkDriver`` 封装 DLL 接口：
打开/关闭、连续采样、USB 连通测试与采样自检回放。

Notes
-----
- 依赖项目根目录的 ``Usb_Daq_V52_Dll.dll``。
- 播放测试依赖 ``sounddevice``。
- 异常通常由上层线程封装捕获，此处不抛出。
"""

import time

import numpy as np
import sounddevice as sd
from ctypes import *


epsilon = 1e-8


class HkParam(object):
    """
    HKUSB6203 参数管理器。

    Attributes
    ----------
    _usage : int
        是否启用采集（0/1）。
    _rangeCode : int
        量程代码（0: ±5V, 1: ±10V）。
    _sampleRate : int
        采样率（Hz, 100~100000）。
    """
    def __init__(self):
        # Initialize parameters for HKUSB6203
        self._usage = 0         # 是否使用采集卡（0 关闭 / 1 开启）
        self._rangeCode = 0     # 量程代码
        self._sampleRate = 100000

    def _reset(self):
        """
        重置为默认参数。

        Returns
        -------
        None
        """
        self._usage = 0
        self._rangeCode = 0
        self._sampleRate = 100000

    def getUsage(self):
        """
        返回是否启用采集卡。

        Returns
        -------
        int
            0/1
        """
        return self._usage

    def getRangeCode(self):
        """
        返回量程代码。

        Returns
        -------
        int
            0 表示 ±5V，1 表示 ±10V。
        """
        return self._rangeCode

    def getSampleRate(self):
        """
        返回采样率。

        Returns
        -------
        int
            采样率（Hz）。
        """
        return self._sampleRate

    def setUsage(self, usage):
        """
        设置是否启用采集卡。

        Parameters
        ----------
        usage : int
            0/1。
        """
        self._usage = usage

    def setRangeCode(self, rangeCode):
        """
        设置量程代码。

        Parameters
        ----------
        rangeCode : int
            0 表示 ±5V，1 表示 ±10V。
        """
        self._rangeCode = rangeCode

    def setSampleRate(self, sampleRate):
        """
        设置采样率。

        Parameters
        ----------
        sampleRate : int
            采样率（Hz）。
        """
        self._sampleRate = sampleRate

    @staticmethod
    def validParamOfConfig(config):
        """
        校验 QSettings 中保存的参数是否合法。

        Parameters
        ----------
        config : QSettings

        Returns
        -------
        bool
            合法返回 True。
        """
        try:
            usage = int(config.value("HK/USAGE", -1))
            rangeCode = int(config.value("HK/RANGE_CODE", -1))
            sampleRate = int(config.value("HK/SAMPLE_RATE", -1))
        except:
            return False
        else:
            if usage == -1 or rangeCode == -1 or sampleRate == -1:
                return False
            if usage not in [0, 1]:
                return False
            if rangeCode not in [0, 1]:
                return False
            if sampleRate < 100 or sampleRate > 100000:
                return False
            return True

    def loadParamFromConfig(self, config):
        """
        从 QSettings 加载参数。

        Parameters
        ----------
        config : QSettings
        """
        self._usage = int(config.value("HK/USAGE", 0))
        self._rangeCode = int(config.value("HK/RANGE_CODE", 0))
        self._sampleRate = int(config.value("HK/SAMPLE_RATE", 100000))

    def saveParamToConfig(self, config):
        """
        将当前参数保存至 QSettings。

        Parameters
        ----------
        config : QSettings
        """
        config.setValue("HK/USAGE", self._usage)
        config.setValue("HK/RANGE_CODE", self._rangeCode)
        config.setValue("HK/SAMPLE_RATE", self._sampleRate)

    def resetParamOfConfig(self, config):
        """
        重置为默认参数并保存。

        Parameters
        ----------
        config : QSettings
        """
        self._reset()
        self.saveParamToConfig(config)


class HkDriver(object):
    """
    HKUSB6203 设备驱动。

    Attributes
    ----------
    _daqDll : ctypes.WinDLL
        底层 DLL 句柄。
    param : HkParam
        参数对象。
    """
    def __init__(self):
        # Initialize driver for HKUSB6203
        self._daqDll = WinDLL("./Usb_Daq_V52_Dll.dll")
        self.param = HkParam()

    def openUsb(self):
        """
        打开设备。

        Returns
        -------
        int
            DLL 返回码（0 表示成功）。
        """
        return self._daqDll.openUSB()

    def closeUsb(self):
        """
        关闭设备。

        Returns
        -------
        int
            DLL 返回码（0 表示成功）。
        """
        return self._daqDll.closeUSB()

    def sampleBuffer(self, numSample):
        """
        连续采样。

        Parameters
        ----------
        numSample : int
            采样点数；返回缓冲长度为 ``numSample*8``。

        Returns
        -------
        ctypes.Array
            浮点数组（c_float * N）。
        """
        bufferLen = numSample * 8
        dataBuffer = (c_float * bufferLen)()
        # 通道数固定为 8，参数由硬件定义
        self._daqDll.ad_continu(0, 0, self.param.getRangeCode(), self.param.getSampleRate(), 0, 0, 0, 0, bufferLen, byref(dataBuffer))
        return dataBuffer

    def testUsbConnect(self):
        """
        USB 连通性测试：打开-等待-关闭。

        Returns
        -------
        bool
            均返回 0 视为成功。
        """
        retOpen = self.openUsb()
        time.sleep(0.5)
        retClose = self.closeUsb()
        return not (retOpen or retClose)

    def testSampleBuffer(self):
        """
        采样并回放 5 路通道的简易自检。

        步骤
        ----
        1. 打开设备；
        2. 连续采样 2 秒；
        3. 将 8 路转为 (5, N) 并幅度归一；
        4. 逐路播放并等待结束；
        5. 关闭设备。

        Returns
        -------
        bool
            成功返回 True。
        """
        retOpen = self.openUsb()
        if retOpen != 0:
            self.closeUsb()
            return False
        try:
            numSample = 2 * self.param.getSampleRate() # 2s
            dataBuffer = self.sampleBuffer(numSample)
            signal = np.array(dataBuffer).reshape((-1, 8)).T
            signal = (signal - np.mean(signal, axis=1)[..., None]) / (np.max(np.abs(signal)) + epsilon)
            # play the signals obtained by five channels one by one
            for i in range(5):
                sd.play(signal[i, :], self.param.getSampleRate())
                sd.wait()
                time.sleep(0.5)
        except:
            self.closeUsb()
            return False
        else:
            retClose = self.closeUsb()
            if retClose != 0:
                return False
            return True

    def __del__(self):
        # 析构时尝试关闭设备，忽略返回值
        ret = self._daqDll.closeUSB()