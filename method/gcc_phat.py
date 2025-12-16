"""
GCC-PHAT 单声源定位方法实现

概述
----
提供在线/离线两种处理接口：``onlineProcessData`` / ``offlineProcessData``，
从 5 路麦克风阵列的到达时延（TDoA）估计声源三维坐标；在线模式使用中值滤波稳定结果。

Notes
-----
- 输入数据约定：8 通道帧中取前 5 路作为麦克风信号。
- 在线模式以帧为单位处理，离线模式以整段文件为单位处理。
- 使用频域 PHAT 加权互相关，寻找相关峰位置估计时延。

References
----------
- GCC-PHAT, Generalized Cross-Correlation with Phase Transform.
"""

import numpy as np
from nara_wpe.utils import stft


# 麦克风与阵列参数
microphoneNum = 5
armLength = 0.32
armRatio = 0.4
# 声速参数（单位：m/s），简化温度修正
t = 22
c = 331.45 * np.sqrt(1 + t / 273.16)
# 其他参数
epsilon = 1e-8


class GccPhat(object):
    """
    GCC-PHAT 定位器。
    """
    def onlineProcessData(self, dataBuffer, sampleRate, sampleNum, cutoffFreqLow=80, cutoffFreqUp=8000):
        """
        在线处理一帧数据，返回长度为 1 的坐标列表。

        Parameters
        ----------
        dataBuffer : array-like
            单帧采样数据缓冲，长度为 ``sampleNum*8``。
        sampleRate : int
            采样率（Hz）。
        sampleNum : int
            帧长度（采样点）。
        cutoffFreqLow : int, default=80
            频域带通低截止（Hz）。
        cutoffFreqUp : int, default=8000
            频域带通高截止（Hz）。

        Returns
        -------
        list of np.ndarray
            单元素列表，元素为 ``[x, y, z]``（若队列未满返回 ``[0,0,0]``）。
        """
        signal = (np.array(dataBuffer).reshape(-1, 8)).T
        signal = signal[:5]

        # 去均值并幅度归一
        signal = ((signal - np.mean(signal, axis=1, keepdims=True)) /
                  (np.max(np.abs(signal), axis=1, keepdims=True) + epsilon))

        tau = self.onlineGccPhat(signal, sampleRate, sampleNum, cutoffFreqLow, cutoffFreqUp)
        delayList = tau.getMedian() / sampleRate

        loc = self.locFromDelayList(delayList)
        return [loc]

    def offlineProcessData(self, dataFilePath, sampleNum=8192, cutoffFreqLow=80, cutoffFreqUp=8000):
        """
        离线处理整段数据文件（npz）。

        Parameters
        ----------
        dataFilePath : str
            数据文件路径，包含 ``'SAMPLE_RATE'`` 与 ``'DATA'`` 键。
        sampleNum : int, default=8192
            STFT 窗长。
        cutoffFreqLow : int, default=80
            频域带通低截止（Hz）。
        cutoffFreqUp : int, default=8000
            频域带通高截止（Hz）。

        Returns
        -------
        np.ndarray
            形状为 ``(1, 3, T)`` 的轨迹坐标（单声源）。
        """
        data = np.load(dataFilePath)
        data = dict(data.items())
        sampleRate = int(data['SAMPLE_RATE'])
        signal = np.array(data['DATA'])

        signal = ((signal - np.mean(signal, axis=1, keepdims=True)) /
                  (np.max(np.abs(signal), axis=1, keepdims=True) + epsilon))
        tau = self.offlineGccPhat(signal, sampleRate, sampleNum, cutoffFreqLow, cutoffFreqUp)
        delayList = tau / sampleRate
        loc = self.locFromDelayList(delayList)[None, ...]
        return loc

    @staticmethod
    def locFromDelayList(delayList):
        """
        根据 4 个相对时延估计 3D 坐标。

        Parameters
        ----------
        delayList : array-like of shape (4,)
            相对时延（单位：秒），对应固定麦克风对次序。

        Returns
        -------
        np.ndarray of shape (3,)
            估计的三维坐标（单位：米）。
        """
        detValue = delayList[2] - armRatio * delayList[0] - armRatio * delayList[1] + epsilon
        tildeT21 = armLength ** 2 - (c * delayList[0]) ** 2
        tildeT31 = armLength ** 2 - (c * delayList[1]) ** 2
        tildeT41 = 2 * (armRatio * armLength) ** 2 - (c * delayList[2]) ** 2
        tildeT51 = armLength ** 2 - (c * delayList[3]) ** 2

        tildeX = (delayList[2] - armRatio * delayList[1]) * tildeT21 + armRatio * delayList[0] * tildeT31 - delayList[0] * tildeT41
        tildeY = (delayList[2] - armRatio * delayList[0]) * tildeT31 + armRatio * delayList[1] * tildeT21 - delayList[1] * tildeT41
        tildeZ = 2 * armRatio * armLength ** 2 * delayList[3] * (1 - armRatio) + c ** 2 * delayList[3] * (
                -armRatio * delayList[0] ** 2 - armRatio * delayList[1] ** 2 + delayList[2] ** 2) + detValue * tildeT51

        return np.array([tildeX, tildeY, tildeZ]) / (2 * armLength * detValue)

    @staticmethod
    def onlineGccPhat(data, sampleRate, sampleNum, cutoffFreqLow, cutoffFreqUp):
        """
        在线帧内 GCC-PHAT，返回 4 组峰值位置（样本偏移）。

        Parameters
        ----------
        data : np.ndarray of shape (5, N)
            5 路麦克风信号。
        sampleRate : int
            采样率。
        sampleNum : int
            帧长度（点数）。
        cutoffFreqLow : int
            低截止频率（Hz）。
        cutoffFreqUp : int
            高截止频率（Hz）。

        Returns
        -------
        np.ndarray of shape (4,)
            峰值位置相对于中心的偏移（样本）。
        """

        Y = np.fft.rfft(np.blackman(sampleNum)[None, ...] * data, axis=1)

        cutoffIndexLow = int(cutoffFreqLow / sampleRate * sampleNum)
        cutoffIndexUp = int(cutoffFreqUp / sampleRate * sampleNum)

        Y[:, :cutoffIndexLow], Y[:, cutoffIndexUp:] = 0, 0

        absY = np.abs(Y)
        absY[absY < epsilon] = epsilon
        pY = Y / absY

        # 与通道 0 的相干函数，共 4 组
        crossCorrelationMatrix = np.array([np.conj(pY[0]) * pY[i] for i in range(1, microphoneNum)])

        frameGccPhat = np.fft.fftshift(np.fft.irfft(crossCorrelationMatrix, n=sampleNum, axis=1), axes=1)
        peakLoc = np.argmax(np.abs(frameGccPhat), axis=1)

        tau = peakLoc - sampleNum // 2

        return tau

    def offlineGccPhat(self, data, sampleRate, sampleNum, cutoffFreqLow, cutoffFreqUp):
        """
        离线多帧 GCC-PHAT，返回逐帧峰值位置。

        Parameters
        ----------
        data : np.ndarray of shape (5, N)
            5 路麦克风信号。
        sampleRate : int
            采样率。
        sampleNum : int
            STFT 窗长。
        cutoffFreqLow : int
            低截止频率（Hz）。
        cutoffFreqUp : int
            高截止频率（Hz）。

        Returns
        -------
        np.ndarray of shape (4, T)
            每帧的 4 组峰值偏移（样本）。
        """
        stftSize = sampleNum
        stftShift = sampleNum // 2
        numFreq = sampleNum // 2 + 1
        Y = stft(data, stftSize, stftShift)

        cutoffIndexLow = int(cutoffFreqLow / sampleRate * sampleNum)
        cutoffIndexUp = int(cutoffFreqUp / sampleRate * sampleNum)

        Y[:, :, :cutoffIndexLow], Y[:, :, cutoffIndexUp:] = 0, 0

        # 规格 (num_mics, num_frames * num_freq)
        reorderZ = Y.reshape((5, -1))
        # PHAT 加权
        absZ = np.abs(reorderZ)
        absZ[absZ < epsilon] = epsilon
        pZ = reorderZ / absZ
        # 计算互相关矩阵
        cc = []
        for k in range(pZ.shape[1]):
            cc.append(np.dot(pZ[:, None, k], np.conj(pZ[:, None, k]).T))
        # 规格 (num_frames * num_freq, num_mics, num_mics)
        cc = np.array(cc)
        ar = np.arange(5)
        av = ar[:, None]
        # 上三角阵掩膜
        mask_triu = (av < av.T).flatten()
        # shape (num_frames * num_freq, num_mic_pairs)
        ccFlat = cc.reshape((-1,  25))[:, mask_triu]
        # shape (num_frames , num_mic_pairs, num_freq)
        ccFlat = ccFlat.reshape((-1, numFreq, 10)).transpose(0, 2, 1)
        # GCC-PHAT 能量计算
        # 规格 (num_frames, num_mic_pairs, num_freq * 2 - 2)
        gccPhat = np.fft.fftshift(np.fft.irfft(ccFlat, n=stftSize, axis=2), axes=2)
        gccPhat = gccPhat[:, :4, :]
        peakLoc = np.argmax(np.abs(gccPhat), axis=2)
        tau = peakLoc - stftShift
        return tau.T
