from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.core.constants import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    PROCESSING_JOB_TYPE_MOCK_PIPELINE,
    VIDEO_STATUS_COMPLETED,
    VIDEO_STATUS_FAILED,
    VIDEO_STATUS_PROCESSING,
)
from app.core.errors import APIError
from app.models import ProcessingJob, SemanticSegment, TranscriptSegment, Video


@dataclass(frozen=True)
class TranscriptSeed:
    start_time: float
    end_time: float
    speaker: str
    text: str


@dataclass(frozen=True)
class SemanticSeed:
    start_time: float
    end_time: float
    title: str
    summary: str
    topic: str
    keywords: list[str]
    confidence: float
    reason: str


def run_mock_pipeline(db: Session, video: Video) -> dict[str, Any]:
    video_id = video.id
    job = _get_or_create_mock_pipeline_job(db, video_id)

    transcript_seeds = _build_transcript_seeds()
    semantic_seeds = _build_semantic_seeds()

    try:
        job.status = JOB_STATUS_RUNNING
        job.error_message = None
        video.status = VIDEO_STATUS_PROCESSING
        db.add_all([job, video])
        db.commit()

        db.execute(
            delete(SemanticSegment).where(SemanticSegment.video_id == video_id)
        )
        db.execute(
            delete(TranscriptSegment).where(TranscriptSegment.video_id == video_id)
        )

        transcript_segments = [
            TranscriptSegment(
                video_id=video_id,
                start_time=seed.start_time,
                end_time=seed.end_time,
                speaker=seed.speaker,
                text=seed.text,
                sort_order=index,
            )
            for index, seed in enumerate(transcript_seeds, start=1)
        ]
        db.add_all(transcript_segments)

        semantic_segments = [
            SemanticSegment(
                video_id=video_id,
                start_time=seed.start_time,
                end_time=seed.end_time,
                title=seed.title,
                summary=seed.summary,
                topic=seed.topic,
                keywords=seed.keywords,
                transcript_text=_collect_transcript_text(
                    transcript_segments,
                    start_time=seed.start_time,
                    end_time=seed.end_time,
                ),
                confidence=seed.confidence,
                reason=seed.reason,
                sort_order=index,
            )
            for index, seed in enumerate(semantic_seeds, start=1)
        ]
        db.add_all(semantic_segments)

        job.status = JOB_STATUS_COMPLETED
        job.error_message = None
        video.status = VIDEO_STATUS_COMPLETED
        db.commit()

        return {
            "video_id": str(video_id),
            "transcript_segments_created": len(transcript_segments),
            "semantic_segments_created": len(semantic_segments),
            "job_status": job.status,
        }
    except Exception as exc:
        db.rollback()
        _mark_pipeline_failed(
            db=db,
            video_id=video_id,
            job_id=job.id,
            error_message=str(exc),
        )
        raise APIError(
            500,
            "mock_pipeline_failed",
            "Failed to run mock pipeline.",
        ) from exc


def _get_or_create_mock_pipeline_job(db: Session, video_id: UUID) -> ProcessingJob:
    job = db.scalars(
        select(ProcessingJob)
        .where(
            ProcessingJob.video_id == video_id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_MOCK_PIPELINE,
        )
        .order_by(desc(ProcessingJob.created_at))
        .limit(1)
    ).first()

    if job is None:
        job = ProcessingJob(
            video_id=video_id,
            job_type=PROCESSING_JOB_TYPE_MOCK_PIPELINE,
            status=JOB_STATUS_PENDING,
            error_message=None,
        )
        db.add(job)
        db.flush()

    return job


def _mark_pipeline_failed(
    *,
    db: Session,
    video_id: UUID,
    job_id: UUID,
    error_message: str,
) -> None:
    try:
        video = db.get(Video, video_id)
        job = db.get(ProcessingJob, job_id)

        if video is not None:
            video.status = VIDEO_STATUS_FAILED
        if job is not None:
            job.status = JOB_STATUS_FAILED
            job.error_message = error_message[:1000]

        db.commit()
    except Exception:
        db.rollback()


def _collect_transcript_text(
    transcript_segments: list[TranscriptSegment],
    *,
    start_time: float,
    end_time: float,
) -> str:
    lines = [
        segment.text
        for segment in transcript_segments
        if segment.start_time < end_time and segment.end_time > start_time
    ]
    return " ".join(lines).strip()


def _build_transcript_seeds() -> list[TranscriptSeed]:
    return [
        TranscriptSeed(
            start_time=0.0,
            end_time=38.0,
            speaker="林晓",
            text="大家好，今天这场会主要聚焦品牌部正在处理的一类内容资产，包括发布会全程视频、高管访谈、线下活动复盘和产品介绍这类时长比较长的视频素材。",
        ),
        TranscriptSeed(
            start_time=38.0,
            end_time=76.0,
            speaker="周明",
            text="目前只要有同事想找一段可用素材，基本都要从完整视频重新开始看，同一条一小时的视频会被不同团队反复打开，只为了确认某个话题到底从哪里开始、到哪里结束。",
        ),
        TranscriptSeed(
            start_time=76.0,
            end_time=118.0,
            speaker="陈薇",
            text="这就让内容团队的人工处理变成明显瓶颈，剪辑和运营同学需要反复拖时间轴、做笔记、记重点，才能把会议、直播和产品演示里可能有价值的部分整理出来。",
        ),
        TranscriptSeed(
            start_time=118.0,
            end_time=162.0,
            speaker="周明",
            text="而且如果我们只按金句或高光片段去找，经常会把上下文丢掉，最后虽然截到了那一句话，但前后完整解释没有保留下来，审核时还得重新回到原视频再看一遍。",
        ),
        TranscriptSeed(
            start_time=162.0,
            end_time=206.0,
            speaker="林晓",
            text="所以我们第一步最需要的不是高光打点，而是先做语义分段，让系统先理解视频里每一段到底在讲什么，再按完整话题去拆分，而不是只抓零散的句子。",
        ),
        TranscriptSeed(
            start_time=206.0,
            end_time=252.0,
            speaker="刘洋",
            text="产品流程其实很清晰，先上传原始视频，然后生成转写文本，再基于转写做语义分段，最后把建议好的内容边界交给人工审核，这样就能很快形成可用的内容结构。",
        ),
        TranscriptSeed(
            start_time=252.0,
            end_time=298.0,
            speaker="陈薇",
            text="进入审核阶段之后，团队还需要能够直接修改标题，按需要合并相邻段落、拆分过长段落，或者微调起止时间，让机器建议和人工判断可以顺畅地结合在一起。",
        ),
        TranscriptSeed(
            start_time=298.0,
            end_time=344.0,
            speaker="刘洋",
            text="这样做还有一个很重要的价值，就是每一段内容都能带上标题、摘要、主题、关键词和原文片段，不再只是一个大视频文件，而是可以被搜索和管理的内容单元。",
        ),
        TranscriptSeed(
            start_time=344.0,
            end_time=388.0,
            speaker="周明",
            text="从品牌运营角度看，同一条发布会或访谈视频就可以进一步拆出社媒短内容、销售讲解素材、渠道合作演示片段和内部复盘资料，不需要每次都重新人工整理一遍。",
        ),
        TranscriptSeed(
            start_time=388.0,
            end_time=420.0,
            speaker="林晓",
            text="所以这个 MVP 阶段的目标很明确，先把上传、转写、语义分段和查询闭环跑通，等产品路径验证完成后，再逐步接入真实 ASR 和真实 LLM 分段能力。",
        ),
    ]


def _build_semantic_seeds() -> list[SemanticSeed]:
    return [
        SemanticSeed(
            start_time=0.0,
            end_time=76.0,
            title="品牌长视频处理背景",
            summary="团队先说明品牌部正在处理发布会、访谈和活动复盘等长视频，并指出不同团队反复从完整视频中找素材已经成为日常工作负担。",
            topic="品牌长视频处理背景",
            keywords=["品牌部", "长视频", "素材检索"],
            confidence=0.96,
            reason="这一段内容集中在品牌长视频的业务场景和重复回看完整视频的现实问题，主题连续且边界清晰。",
        ),
        SemanticSeed(
            start_time=76.0,
            end_time=162.0,
            title="人工观看与剪辑效率瓶颈",
            summary="团队详细描述了人工拖时间轴、记笔记和找话题边界的成本，并进一步说明只截金句会丢掉上下文，导致审核返工。",
            topic="人工观看与剪辑效率瓶颈",
            keywords=["人工剪辑", "时间轴", "上下文缺失"],
            confidence=0.94,
            reason="这一段持续围绕人工处理低效和高光截取缺少上下文的问题展开，没有切换到其他主题。",
        ),
        SemanticSeed(
            start_time=162.0,
            end_time=252.0,
            title="为什么要先做语义分段",
            summary="团队明确提出应先理解视频内容，再按完整话题做切分，并同步说明从上传、转写到语义分段和人工审核的核心产品流程。",
            topic="为什么要先做语义分段",
            keywords=["语义分段", "完整话题", "产品流程"],
            confidence=0.97,
            reason="这一段从问题自然过渡到解决方案，重点始终是语义分段优先于高光切片的产品逻辑。",
        ),
        SemanticSeed(
            start_time=252.0,
            end_time=344.0,
            title="审核调整与内容元数据管理",
            summary="团队讨论审核阶段需要支持改标题、合并、拆分和微调时间边界，同时强调标题、摘要、主题、关键词和原文能构成后续搜索与管理的元数据层。",
            topic="审核调整与内容元数据管理",
            keywords=["审核调整", "元数据", "内容管理"],
            confidence=0.91,
            reason="这一段完整聚焦在审核动作和内容元数据的管理价值，信息密度高且内部关联紧密。",
        ),
        SemanticSeed(
            start_time=344.0,
            end_time=420.0,
            title="内容复用价值与 MVP 下一步",
            summary="最后一段把语义分段和跨渠道内容复用联系起来，并明确当前 MVP 的目标是先跑通闭环，再逐步接入真实模型能力。",
            topic="内容复用价值与 MVP 下一步",
            keywords=["内容复用", "品牌运营", "MVP"],
            confidence=0.95,
            reason="收尾内容持续讨论内容复用收益与下一阶段规划，形成自然的结论性话题段落。",
        ),
    ]
