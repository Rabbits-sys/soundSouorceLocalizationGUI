"""
数据集驱动（CMU ARCTIC）

概述
----
封装 ``pyroomacoustics`` 的 ``CMUArcticCorpus``，提供说话人选择/顺序维护与文本、波形数据访问。

Notes
-----
本驱动聚焦于数据组织与访问，不涉及音频播放或硬件操作。
"""

import pyroomacoustics as pra


class DatasetDriver:
    """
    CMU ARCTIC 数据集访问器。

    Attributes
    ----------
    _sampleRate : int
        输出数据采样率（Hz）。
    _corpus : CMUArcticCorpus
        语料封装。
    _speakerUsedNum : int
        当前启用的说话人人数。
    _usedSpeakerIndexList : list of int
        启用的说话人索引队列（右侧为最新）。
    _correspondingSpeakerNameList : list of str
        索引到说话人代号的映射。
    _dataModeCode : int
        数据模式（目前仅 0）。
    """

    def __init__(self):
        self._sampleRate = 16000
        # 不触发下载，要求用户已就绪 CMU_ARCTIC 目录
        self._corpus = pra.datasets.cmu_arctic.CMUArcticCorpus(download=False, speaker=['bdl', 'slt', 'clb', 'rms'])
        self._corpus.build_corpus()

        self._speakerUsedNum = 0
        self._usedSpeakerIndexList = []
        self._correspondingSpeakerNameList = ['bdl', 'slt', 'clb', 'rms']

        self._dataModeCode = 0

    def getSampleRate(self):
        """
        获取语音数据采样率。

        Returns
        -------
        int
            采样率（Hz）。
        """
        return self._sampleRate

    def getSpeakerUsedNum(self):
        """
        获取当前启用的说话人人数。

        Returns
        -------
        int
        """
        return self._speakerUsedNum

    def getUsedSpeakerIndexList(self):
        """
        获取当前启用的说话人索引队列。

        Returns
        -------
        list of int
        """
        return self._usedSpeakerIndexList

    def getCorrespondingSpeakerNameList(self):
        """
        获取索引到说话人代号的映射表。

        Returns
        -------
        list of str
        """
        return self._correspondingSpeakerNameList

    def setDataModeCode(self, dataModeCode):
        """
        设置数据模式（暂仅支持 0）。

        Parameters
        ----------
        dataModeCode : int
        """
        self._dataModeCode = dataModeCode

    def initSpeakerUsage(self, speakerNum):
        """
        根据外部使用的扬声器数量，初始化启用说话人列表。

        Parameters
        ----------
        speakerNum : int
            启用数量（0-4）。
        """
        self._speakerUsedNum = speakerNum
        self._usedSpeakerIndexList = list(range(speakerNum))

    def addSpeakerUsage(self, speakerIndex):
        """
        切换/追加某个说话人的使用状态，保持队列长度不超过已用数量。

        Parameters
        ----------
        speakerIndex : int
            说话人索引（0..3）。

        Notes
        -----
        - 若该索引未启用，则弹出队首并加入队尾；
        - 若该索引已启用，则从队列移除并加入队尾（置为最新）。
        """
        if self._speakerUsedNum == 0:
            return
        if speakerIndex not in self._usedSpeakerIndexList:
            self._usedSpeakerIndexList.pop(0)
        else:
            self._usedSpeakerIndexList.remove(speakerIndex)
        self._usedSpeakerIndexList.append(speakerIndex)

    def getSpeakerTextList(self, dataIndex):
        """
        根据数据索引，返回当前启用说话人的文本列表。

        Parameters
        ----------
        dataIndex : int
            语料编号。

        Returns
        -------
        list of str
        """
        speakerTextList = []
        if self._dataModeCode == 0:
            for offset, speakerIndex in enumerate(self._usedSpeakerIndexList):
                speakerTextList.append(self._corpus.samples[dataIndex * self._speakerUsedNum * 4 + offset * 4 + speakerIndex].meta.__dict__['text'])

        return speakerTextList

    def getSpeakerDataList(self, dataIndex):
        """
        根据数据索引，返回当前启用说话人的语音波形列表。

        Parameters
        ----------
        dataIndex : int
            语料编号。

        Returns
        -------
        list of np.ndarray
            每条为 ``shape=(N, 1)``。
        """
        speakerDataList = []
        if self._dataModeCode == 0:
            for offset, speakerIndex in enumerate(self._usedSpeakerIndexList):
                speakerDataList.append(
                    self._corpus[dataIndex * self._speakerUsedNum * 4 + offset * 4 + speakerIndex].data[:, None])

        return speakerDataList