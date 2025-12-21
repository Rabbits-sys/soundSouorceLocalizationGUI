"""
USB 扬声器驱动封装

概述
----
基于 ``sounddevice`` 选择并驱动多块 USB 声卡进行单声道播放；
管理设备列表、启用上限（最多 4 个）、音量与并发播放；
提供资源内置测试音的一次/依次播放。

Notes
-----
- 本模块不做 GUI 逻辑，仅专注音频播放与设备管理；
- 并发播放通过线程 join 等待全部完成。
"""

import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from typing import Optional, List

from io import BytesIO

from PyQt5.QtCore import QFile


class SpeakerDevice(object):
    """
    单个声卡设备抽象，支持单声道缓冲播放。

    Parameters
    ----------
    deviceId : int
        ``sounddevice`` 设备索引。
    deviceName : str
        设备名称。

    Attributes
    ----------
    _usage : bool
        是否启用。
    _volume : int
        音量（0-100）。
    _stream : Optional[sd.Stream]
        输出流句柄。
    """
    def __init__(self, deviceId, deviceName):
        self._deviceId = deviceId
        self._deviceName = deviceName
        self._usage = False
        self._volume = 100

        self._stream: Optional[sd.Stream] = None
        self._threadEvent = threading.Event()

    def getDeviceId(self):
        """
        返回设备 ID。

        Returns
        -------
        int
        """
        return self._deviceId

    def getDeviceName(self):
        """
        返回设备名称。

        Returns
        -------
        str
        """
        return self._deviceName

    def getUsage(self):
        """
        返回是否被启用。

        Returns
        -------
        bool
        """
        return self._usage

    def getVolume(self):
        """
        返回播放音量。

        Returns
        -------
        int
            0-100。
        """
        return self._volume

    def setUsage(self, usage):
        """
        设置启用状态。

        Parameters
        ----------
        usage : bool
        """
        self._usage = usage

    def setVolume(self, volume):
        """
        设置音量。

        Parameters
        ----------
        volume : int
            0-100。
        """
        self._volume = volume

    def playBuffer(self, soundSigal, sampleRate, **kwargs):
        """
        按当前音量播放单声道 int16 缓冲。

        Parameters
        ----------
        soundSigal : np.ndarray
            形状 ``(N, 1)`` 或 ``(N,)``。
        sampleRate : int
            采样率（Hz）。
        **kwargs
            透传给 ``sounddevice.OutputStream`` 的参数。

        Returns
        -------
        None

        Notes
        -----
        - 使用回调将数据推送到设备；
        - 数据播放完毕或错误时通过线程事件退出；
        - 函数在播放完成后返回（阻塞）。
        """
        self._threadEvent.clear()
        idx = 0

        sd_buffer = (soundSigal / 100 * self._volume).astype(np.int16)

        def callback(outdata, frame_count, time_info, status):
            nonlocal idx
            if status:
                print(status)
            remainder = len(sd_buffer) - idx
            if remainder == 0:
                outdata[:] = 0
                self._threadEvent.set()
                raise sd.CallbackStop

            valid_frames = frame_count if remainder >= frame_count else remainder
            outdata[:valid_frames] = sd_buffer[idx:idx + valid_frames]
            outdata[valid_frames:] = 0
            idx += valid_frames

        self._stream = sd.OutputStream(callback=callback, dtype="int16",
                                       channels=1, device=self._deviceId, samplerate=sampleRate, **kwargs)

        self._stream.start()
        self._threadEvent.wait()
        self._stream.close()

    def stopBuffer(self):
        """
        停止当前播放（若存在），并解除等待。

        Returns
        -------
        None
        """
        if self._stream:
            self._stream.stop()
        if not self._threadEvent.is_set():
            self._threadEvent.set()

    def __del__(self):
        self.stopBuffer()


class SpeakerDriver(object):
    """
    多声卡设备管理与并发播放。

    Attributes
    ----------
    _maxDeviceUsageNum : int
        允许启用的最大设备数。
    _deviceItemList : list of SpeakerDevice
        已发现设备列表。
    _deviceUsedNum : int
        已启用设备数。
    _usedDeviceIndexList : list of int
        已启用设备索引列表（相对于 ``query_devices`` 序号）。
    _testSignalWav : np.ndarray
        单声道测试音数据。
    _testSignalSampleRate : int
        测试音采样率。
    """
    def __init__(self):
        self._maxDeviceUsageNum = 4

        self._deviceItemList: List[SpeakerDevice] = []
        self._deviceUsedNum = 0
        self._usedDeviceIndexList = []

        # 从资源读入测试音频（单声道）
        testSignalFile = QFile(':/music/test.wav')
        if not testSignalFile.open(QFile.ReadOnly):
            raise RuntimeError("Cannot open test signal file")
        testSignalData = testSignalFile.readAll()
        testSignalFile.close()
        testSignalStream = BytesIO(bytes(testSignalData))

        testSignalWav, self._testSignalSampleRate = sf.read(testSignalStream, dtype='int16')
        self._testSignalWav = (testSignalWav[:, 0])[..., None]  # Use only one channel

    def getDeviceItemList(self):
        """
        返回 ``SpeakerDevice`` 列表。

        Returns
        -------
        list of SpeakerDevice
        """
        return self._deviceItemList

    def getDeviceUsedNum(self):
        """
        返回已启用设备数。

        Returns
        -------
        int
        """
        return self._deviceUsedNum

    def getUsedDeviceIndexList(self):
        """
        返回已启用设备的索引列表。

        Returns
        -------
        list of int
        """
        return self._usedDeviceIndexList

    @staticmethod
    def filterUsbSoundcard(deviceInfo: (int, dict)):
        """
        过滤 USB 声卡。

        Parameters
        ----------
        deviceInfo : tuple[int, dict]
            ``(id, info_dict)`` 二元组，来自 ``sounddevice.query_devices`` 枚举。

        Returns
        -------
        tuple[int, str] | bool
            满足 USB 声卡特征则返回 ``(id, name)``，否则返回 ``False``。
        """

        deviceId, fuzzInfo = deviceInfo

        if fuzzInfo["hostapi"] == 0 and fuzzInfo["max_output_channels"] > 0:
            return deviceId, fuzzInfo["name"]
        return False

    def searchUsbSoundcard(self):
        """
        刷新并枚举 USB 声卡设备列表。

        Returns
        -------
        None
        """
        sd._terminate()
        sd._initialize()
        deviceList = list(filter(lambda x: x is not False, map(self.filterUsbSoundcard, [indexInfo for indexInfo in enumerate(sd.query_devices())])))
        self._deviceItemList = [SpeakerDevice(deviceId, deviceName) for deviceId, deviceName in deviceList]

    def addDeviceUsage(self, deviceIndex):
        """
        启用一个设备（若未超出上限且未启用）。

        Parameters
        ----------
        deviceIndex : int

        Returns
        -------
        bool
            是否成功。
        """
        if deviceIndex not in self._usedDeviceIndexList and self._deviceUsedNum < self._maxDeviceUsageNum:
            self._deviceUsedNum += 1
            self._deviceItemList[deviceIndex].setUsage(True)
            self._usedDeviceIndexList.append(deviceIndex)
            return True
        else:
            return False

    def subDeviceUsage(self, deviceIndex):
        """
        关闭一个已启用设备。

        Parameters
        ----------
        deviceIndex : int

        Returns
        -------
        bool
            是否成功。
        """
        if deviceIndex in self._usedDeviceIndexList and self._deviceUsedNum > 0:
            self._deviceUsedNum -= 1
            self._deviceItemList[deviceIndex].setUsage(False)
            self._usedDeviceIndexList.remove(deviceIndex)
            return True
        else:
            return False

    def resetDeviceUsage(self):
        """
        清空启用列表并重置计数。

        Returns
        -------
        None
        """
        self._usedDeviceIndexList.clear()
        self._deviceUsedNum = 0

    def playTestSingle(self, deviceIndex, **kwargs):
        """
        在指定设备播放内置测试音。

        Parameters
        ----------
        deviceIndex : int
        **kwargs
            透传给播放流的参数。

        Returns
        -------
        bool
            成功返回 True。
        """
        self._deviceItemList[deviceIndex].playBuffer(self._testSignalWav, self._testSignalSampleRate, **kwargs)
        return True

    def playTestMulti(self, **kwargs):
        """
        在所有启用设备上依次播放内置测试音。

        Parameters
        ----------
        **kwargs
            透传给播放流的参数。

        Returns
        -------
        bool
            成功返回 True。
        """
        for deviceIndex in self._usedDeviceIndexList:
            self.playTestSingle(deviceIndex, **kwargs)
        return True

    def playBufferSync(self, bufferList, sampleRate, **kwargs):
        """
        在所有启用设备上并发播放各自缓冲，等待全部完成。

        Parameters
        ----------
        bufferList : list of np.ndarray
            与启用设备一一对应的单通道音频。
        sampleRate : int
            采样率（Hz）。
        **kwargs
            透传给播放流的参数。

        Returns
        -------
        bool
            成功返回 True。
        """
        speakerWorkerList = []
        for usedDeviceIndex, buffer in zip(self._usedDeviceIndexList, bufferList):
            speakerWorkerList.append(threading.Thread(target=self._deviceItemList[usedDeviceIndex].playBuffer, args=(buffer, sampleRate)))
        for speakerWorker in speakerWorkerList:
            speakerWorker.start()

        for speakerWorker in speakerWorkerList:
            speakerWorker.join()

        return True

import resource_rc