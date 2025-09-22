"""
批量实验任务

概述
----
依据参数与数据集，驱动多个 USB 扬声器并发播放，同时可选地从采集卡采样；
每个语料索引完成后通过 ``step`` 信号上报进度；如开启采样，则将数据保存为 ``npz``。

并发模型
--------
- 使用 ``ThreadPoolExecutor`` 提交播放与采集任务；
- 等待播放全部完成后读取采样结果并保存。
"""

import os
from datetime import datetime

import numpy as np
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED

from PyQt5.QtCore import pyqtSignal

from driver.hkusb_driver import HkDriver
from driver.speaker_driver import SpeakerDriver
from driver.dataset_driver import DatasetDriver


class BatchParam(object):
    """
    批量实验参数。

    Attributes
    ----------
    _sampleTime : float
        每次采样时长（秒）。
    _speakerDataIndexString : str
        语料 ID 列表的字符串表示，如 ``"[0,1,2]"``。
    """
    def __init__(self):
        self._sampleTime = 5
        self._speakerDataIndexString = str(list(range(20)))

    def _reset(self):
        """
        重置为默认参数。

        Returns
        -------
        None
        """
        self._sampleTime = 5
        self._speakerDataIndexString = str(list(range(20)))

    def getSampleTime(self):
        """
        获取每次采样时长。

        Returns
        -------
        float
            单位：秒。
        """
        return self._sampleTime

    def getSpeakerDataIndexString(self):
        """
        获取语料 ID 字符串。

        Returns
        -------
        str
        """
        return self._speakerDataIndexString

    def setSampleTime(self, sampleTime):
        """
        设置每次采样时长。

        Parameters
        ----------
        sampleTime : float
            单位：秒。
        """
        self._sampleTime = sampleTime

    def setSpeakerDataIndexList(self, speakerDataIndexString):
        """
        设置语料 ID 字符串。

        Parameters
        ----------
        speakerDataIndexString : str
        """
        self._speakerDataIndexString = speakerDataIndexString

    @staticmethod
    def validParamOfConfig(config):
        """
        校验 QSettings 中参数合法性。

        Parameters
        ----------
        config : QSettings

        Returns
        -------
        bool
        """
        try:
            sampleTime = float(config.value("BATCH/SAMPLE_TIME", -1))
            speakerDataIndexString = str(config.value("BATCH/SPEAKER_DATA_INDEX", "-1"))
        except:
            return False
        else:
            if sampleTime == -1 or speakerDataIndexString == "-1":
                return False
            if sampleTime < 0.0 or sampleTime > 10.0:
                return False
            return True

    def validSpeakerDataIndexString(self):
        """
        解析并校验语料 ID 字符串。

        Returns
        -------
        tuple[bool, list[int]]
            ``(合法标志, 列表)``。
        """
        speakerDataIndexString = self._speakerDataIndexString.replace('\n', '')
        if not (speakerDataIndexString.startswith('[') and speakerDataIndexString.endswith(']')):
            return False, []
        speakerDataIndexContent = speakerDataIndexString[1:-1].strip()
        if speakerDataIndexContent == "":
            return True, []
        try:
            speakerDataIndexElements = [elem.strip() for elem in speakerDataIndexContent.split(',')]
        except:
            return False, []
        speakerDataIndexList = []
        for elem in speakerDataIndexElements:
            if elem == "":
                continue
            if not elem.isdigit():
                return False, []
            try:
                num = int(elem)
            except ValueError:
                return False, []
            if num < 0 or num > 200:
                return False, []
            else:
                speakerDataIndexList.append(num)
        return True, speakerDataIndexList

    def loadParamFromConfig(self, config):
        """
        从 QSettings 加载参数。

        Parameters
        ----------
        config : QSettings
        """
        self._sampleTime = float(config.value("BATCH/SAMPLE_TIME", 5))
        self._speakerDataIndexString = str(config.value("BATCH/SPEAKER_DATA_INDEX", str(list(range(20)))))

    def saveParamToConfig(self, config):
        """
        保存参数到 QSettings。

        Parameters
        ----------
        config : QSettings
        """
        config.setValue("BATCH/SAMPLE_TIME", self._sampleTime)
        config.setValue("BATCH/SPEAKER_DATA_INDEX", self._speakerDataIndexString)

    def resetParamOfConfig(self, config):
        """
        重置为默认并保存。

        Parameters
        ----------
        config : QSettings
        """
        self._reset()
        self.saveParamToConfig(config)


class BatchTask(object):
    """
    批量播放与可选采样的任务。

    Parameters
    ----------
    hkDriver : HkDriver
    speakerDriver : SpeakerDriver
    datasetDriver : DatasetDriver

    Attributes
    ----------
    param : BatchParam
        参数对象。
    _startFlag : bool
        运行标志。
    """
    def __init__(self, hkDriver: HkDriver, speakerDriver: SpeakerDriver, datasetDriver: DatasetDriver):
        self._hkDriver = hkDriver
        self._speakerDriver = speakerDriver
        self._datasetDriver = datasetDriver
        self.param = BatchParam()

        self._startFlag = False

    def getStartFlag(self):
        """
        是否处于运行状态。

        Returns
        -------
        bool
        """
        return self._startFlag

    def startBatchTask(self, stepSignal: pyqtSignal(object), speakerDataIndexList):
        """
        启动批量任务（由 ``FunctionLoopWorker`` 在线程中调用）。

        Parameters
        ----------
        stepSignal : pyqtSignal
            进度上报信号。
        speakerDataIndexList : list[int]
            语料 ID 列表。

        Returns
        -------
        bool
            任务是否正常结束。
        """
        saveDir = ""
        speakerFutures = []
        sampleFuture = None
        try:
            if self._hkDriver.param.getUsage() == 1:
                saveDir = "./record/Test_" + datetime.now().strftime("%Y_%m_%d_%H_%M") + "/"
                os.makedirs(saveDir, exist_ok=True)
                retOpen = self._hkDriver.openUsb()
                if retOpen != 0:
                    self._hkDriver.closeUsb()
                    return False

            self._startFlag = True
            workerNum = self._hkDriver.param.getUsage() + self._speakerDriver.getDeviceUsedNum()
            usedDeviceIndexList = self._speakerDriver.getUsedDeviceIndexList()
            deviceItemList = self._speakerDriver.getDeviceItemList()

            dataSampleRate = self._datasetDriver.getSampleRate()

            numSamples = int(self.param.getSampleTime() * self._hkDriver.param.getSampleRate())

            with ThreadPoolExecutor(max_workers=workerNum) as executor:
                for taskIndex, speakerDataIndex in enumerate(speakerDataIndexList):
                    speakerFutures = []
                    sampleFuture = None
                    if not self._startFlag:
                        break

                    speakerDataList = self._datasetDriver.getSpeakerDataList(speakerDataIndex)
                    for usedDeviceIndex, speakerData in zip(usedDeviceIndexList, speakerDataList):
                        speakerFutures.append(executor.submit(deviceItemList[usedDeviceIndex].playBuffer, speakerData, dataSampleRate))
                    if self._hkDriver.param.getUsage() == 1:
                        sampleFuture = executor.submit(self._hkDriver.sampleBuffer, numSamples)
                    if speakerFutures:
                        wait(speakerFutures, return_when=ALL_COMPLETED)
                    if sampleFuture:
                        dataBuffer = sampleFuture.result()
                        saveFileName = saveDir + str(speakerDataIndex) + ".npz"
                        dataBuffer = (np.array(dataBuffer).reshape(-1, 8)[:, :5]).T
                        dataDict = {
                            'SAMPLE_RATE': self._hkDriver.param.getSampleRate(),
                            'DATA': dataBuffer,
                        }
                        np.savez_compressed(saveFileName, **dataDict)
                    stepSignal.emit(taskIndex)
        except:
            self._startFlag = False
            if speakerFutures:
                wait(speakerFutures, return_when=ALL_COMPLETED)
            if sampleFuture:
                sampleFuture.result()
            self._hkDriver.closeUsb()
            return False
        else:
            self._startFlag = False
            self._hkDriver.closeUsb()
            return True

    def stopBatchTask(self):
        """
        请求停止任务。

        Returns
        -------
        None
        """
        self._startFlag = False

    def __del__(self):
        self.stopBatchTask()