"""
数据集驱动（CMU ARCTIC）

概述
----
封装 CMU ARCTIC 语料库，提供说话人选择/顺序维护与文本、波形数据访问。

Notes
-----
本驱动聚焦于数据组织与访问，不涉及音频播放或硬件操作。
基于 pyroomacoustics 的 CMUArcticCorpus 类重写，去除 pyroomacoustics 依赖。
"""

import os
from scipy.io import wavfile


# 说话人代码和属性
cmu_arctic_speakers = {
    "aew": {"sex": "male", "lang": "US English", "accent": "US"},
    "ahw": {"sex": "male", "lang": "US English", "accent": "German"},
    "aup": {"sex": "male", "lang": "US English", "accent": "Indian"},
    "awb": {"sex": "male", "lang": "US English", "accent": "Scottish"},
    "axb": {"sex": "female", "lang": "US English", "accent": "Indian"},
    "bdl": {"sex": "male", "lang": "US English", "accent": "US"},
    "clb": {"sex": "female", "lang": "US English", "accent": "US"},
    "eey": {"sex": "female", "lang": "US English", "accent": "US"},
    "fem": {"sex": "male", "lang": "US English", "accent": "Irish"},
    "gka": {"sex": "male", "lang": "US English", "accent": "Indian"},
    "jmk": {"sex": "male", "lang": "US English", "accent": "Canadian"},
    "ksp": {"sex": "male", "lang": "US English", "accent": "Indian"},
    "ljm": {"sex": "female", "lang": "US English", "accent": "US"},
    "lnh": {"sex": "female", "lang": "US English", "accent": "US"},
    "rms": {"sex": "male", "lang": "US English", "accent": "US"},
    "rxr": {"sex": "male", "lang": "US English", "accent": "Dutch"},
    "slp": {"sex": "female", "lang": "US English", "accent": "Indian"},
    "slt": {"sex": "female", "lang": "US English", "accent": "US"},
}

# 目录结构
speaker_dir = "cmu_us_{}_arctic"


class Meta:
    """
    元数据类，用于存储和匹配样本属性。
    """
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def as_dict(self):
        return self.__dict__.copy()

    def match(self, **kwargs):
        """
        检查是否匹配给定的条件。

        Parameters
        ----------
        **kwargs : 关键字参数
            匹配条件，可以是字符串、列表或可调用对象。

        Returns
        -------
        bool
            如果所有条件都匹配则返回True。
        """
        for key, value in kwargs.items():
            if not hasattr(self, key):
                return False
            attr = getattr(self, key)
            if callable(value):
                if not value(attr):
                    return False
            elif isinstance(value, list):
                if attr not in value:
                    return False
            else:
                if attr != value:
                    return False
        return True


class CMUArcticSentence:
    """
    CMU ARCTIC 语句对象。

    Parameters
    ----------
    path : str
        音频文件路径
    **kwargs :
        元数据关键字参数

    Attributes
    ----------
    data : array_like
        音频信号数据
    fs : int
        采样率
    meta : Meta
        元数据对象
    """

    def __init__(self, path, **kwargs):
        # 读取wav文件
        fs, data = wavfile.read(path)
        self.data = data
        self.fs = fs
        self.meta = Meta(**kwargs)

    def __str__(self):
        """字符串表示"""
        template = "{speaker} ({sex}, {lang}/{accent}); {tag}: {text}"
        return template.format(**self.meta.as_dict())


class CMUArcticCorpus:
    """
    CMU ARCTIC 语料库加载器。

    Attributes
    ----------
    basedir : str
        CMU ARCTIC 语料库所在目录
    samples : list of CMUArcticSentence
        所有语句样本列表
    sentences : list of CMUArcticSentence
        samples 的别名

    Parameters
    ----------
    basedir : str, optional
        CMU ARCTIC 语料库所在目录，默认为 "./CMU_ARCTIC"
    download : bool, optional
        如果语料库不存在是否下载（本实现不支持下载）
    build : bool, optional
        是否构建语料库
    speaker : str or list of str, optional
        要加载的说话人代号列表
    """

    def __init__(self, basedir=None, download=False, build=True, **kwargs):
        self.samples = []
        self.sentences = self.samples
        self._sentences_data = {}

        # 默认基目录
        self.basedir = basedir
        if basedir is None:
            self.basedir = "./CMU_ARCTIC"

        # 如果未指定说话人，使用所有说话人
        if "speaker" not in kwargs:
            kwargs["speaker"] = list(cmu_arctic_speakers.keys())

        speakers = kwargs["speaker"]
        if not isinstance(speakers, list):
            speakers = [speakers]

        # 检查目录是否存在
        if not os.path.exists(self.basedir):
            raise ValueError(
                "语料库目录不存在。请创建目录或设置正确的路径。"
            )

        # 移除无效的说话人
        n_speakers = len(speakers)
        speakers = [
            speaker for speaker in speakers if speaker in cmu_arctic_speakers.keys()
        ]
        if n_speakers != len(speakers):
            import warnings
            warnings.warn(
                "部分无效的说话人已从列表中移除。", RuntimeWarning
            )

        # 遍历说话人目录
        for speaker in speakers:
            sdir = os.path.join(self.basedir, speaker_dir.format(speaker))

            if not os.path.exists(sdir):
                raise ValueError(f"缺少说话人目录: {sdir}。")

        # 填充语句数据结构
        for speaker in speakers:
            sdir = os.path.join(self.basedir, speaker_dir.format(speaker))
            txt_file = os.path.join(sdir, "etc/txt.done.data")

            if os.path.exists(txt_file):
                with open(txt_file, "r", encoding="utf-8") as f:
                    for line in f.readlines():
                        # 提取文件路径
                        tag = line.split(" ")[1]
                        path = os.path.join(sdir, "wav/" + tag + ".wav")
                        text = line.split('"')[1]

                        # 缩短标签用于内部使用
                        tag = tag[-5:]

                        # 添加到语句字典
                        if tag not in self._sentences_data:
                            self._sentences_data[tag] = {
                                "text": text,
                                "paths": {speaker: path},
                            }
                        else:
                            self._sentences_data[tag]["paths"][speaker] = path

        if build:
            self.build_corpus(**kwargs)

    def build_corpus(self, **kwargs):
        """
        根据过滤条件构建语料库。

        Parameters
        ----------
        **kwargs :
            过滤条件（sex, lang, accent, speaker 等）
        """
        self.samples.clear()

        # 遍历所有语句
        for tag, info in self._sentences_data.items():
            # 遍历每个语句的所有说话人
            for speaker, path in info["paths"].items():
                # 创建元数据
                meta = Meta(
                    speaker=speaker,
                    tag=tag,
                    text=info["text"],
                    **cmu_arctic_speakers[speaker]
                )

                # 如果匹配则添加
                if meta.match(**kwargs):
                    self.samples.append(CMUArcticSentence(path, **meta.as_dict()))

    def __getitem__(self, index):
        """获取指定索引的样本。"""
        return self.samples[index]

    def __len__(self):
        """返回样本数量。"""
        return len(self.samples)

    def filter(self, **kwargs):
        """
        过滤语料库，选择匹配条件的样本。

        Parameters
        ----------
        **kwargs :
            过滤条件

        Returns
        -------
        CMUArcticCorpus
            新的过滤后的语料库
        """
        new_corpus = CMUArcticCorpus(basedir=self.basedir, build=False, speaker=[])

        for sample in self.samples:
            if sample.meta.match(**kwargs):
                new_corpus.samples.append(sample)

        return new_corpus


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
        self._corpus = CMUArcticCorpus(download=False, speaker=['bdl', 'slt', 'clb', 'rms'])
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

