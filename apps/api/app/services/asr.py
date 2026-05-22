from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TranscriptResultSegment:
    start_time: float
    end_time: float
    speaker: str | None
    text: str


class ASRProvider(Protocol):
    def transcribe(
        self,
        audio_object_name: str,
    ) -> list[TranscriptResultSegment]:
        ...


class MockASRProvider:
    def transcribe(
        self,
        audio_object_name: str,
    ) -> list[TranscriptResultSegment]:
        if not audio_object_name.strip():
            raise RuntimeError("Audio object name is empty.")

        return [
            TranscriptResultSegment(
                start_time=0.0,
                end_time=40.0,
                speaker="林晓",
                text="大家好，今天我们复盘的是品牌团队处理长视频内容的方式，重点是如何从整场发布会和访谈里快速找到完整话题。",
            ),
            TranscriptResultSegment(
                start_time=40.0,
                end_time=82.0,
                speaker="周明",
                text="现在团队找素材还是主要靠人工从头看视频，遇到一个小时以上的内容，查找成本会非常高。",
            ),
            TranscriptResultSegment(
                start_time=82.0,
                end_time=124.0,
                speaker="陈薇",
                text="不仅要反复拖时间轴，还要手动记下每段内容的大意，最后再整理成能给内容运营和剪辑使用的说明。",
            ),
            TranscriptResultSegment(
                start_time=124.0,
                end_time=166.0,
                speaker="周明",
                text="如果只抓几句高光金句，往往会丢掉上下文，所以我们更需要知道完整话题是从哪里开始，到哪里结束。",
            ),
            TranscriptResultSegment(
                start_time=166.0,
                end_time=208.0,
                speaker="林晓",
                text="因此第一步不是做热点剪辑，而是先把视频里的说话内容转成可理解的文本，再基于文本做语义分段。",
            ),
            TranscriptResultSegment(
                start_time=208.0,
                end_time=250.0,
                speaker="刘洋",
                text="产品链路可以先从上传视频、提取音频、生成转写开始，把基础处理能力跑通，后面再接入真实模型。",
            ),
            TranscriptResultSegment(
                start_time=250.0,
                end_time=292.0,
                speaker="陈薇",
                text="有了转写之后，团队就能直接检索主题，看到每段文本对应的时间范围，这样人工审核也会轻很多。",
            ),
            TranscriptResultSegment(
                start_time=292.0,
                end_time=336.0,
                speaker="刘洋",
                text="后续语义分段只需要在转写基础上判断话题边界，再给每段生成标题、摘要和关键词。",
            ),
            TranscriptResultSegment(
                start_time=336.0,
                end_time=378.0,
                speaker="周明",
                text="这样同一条品牌视频就能被拆成多个内容单元，既能支持检索，也能给后续剪辑和复用提供依据。",
            ),
            TranscriptResultSegment(
                start_time=378.0,
                end_time=420.0,
                speaker="林晓",
                text="所以本阶段的目标很明确，先把音频提取和转写链路跑通，用 Mock ASR 验证接口和数据结构是否合理。",
            ),
        ]
