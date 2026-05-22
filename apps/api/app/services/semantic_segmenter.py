from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.models import TranscriptSegment


@dataclass(frozen=True)
class SemanticSegmentCandidate:
    start_time: float
    end_time: float
    title: str
    summary: str
    topic: str
    keywords: list[str]
    transcript_text: str
    confidence: float
    reason: str


class SemanticSegmenterProvider(Protocol):
    def segment(
        self,
        transcript_segments: list["TranscriptSegment"],
    ) -> list[SemanticSegmentCandidate]:
        ...


class MockSemanticSegmenterProvider:
    def segment(
        self,
        transcript_segments: list["TranscriptSegment"],
    ) -> list[SemanticSegmentCandidate]:
        ordered_segments = sorted(
            transcript_segments,
            key=lambda segment: segment.sort_order,
        )
        if not ordered_segments:
            return []

        grouped_segments = _group_transcript_segments(ordered_segments)
        return [
            _build_candidate(
                segment_group=segment_group,
                group_index=group_index,
                total_groups=len(grouped_segments),
            )
            for group_index, segment_group in enumerate(grouped_segments, start=1)
        ]


def _group_transcript_segments(
    transcript_segments: list["TranscriptSegment"],
) -> list[list["TranscriptSegment"]]:
    total_segments = len(transcript_segments)
    if total_segments < 2:
        return [transcript_segments]

    target_group_count = 5 if total_segments >= 8 else 4
    group_count = min(target_group_count, total_segments)
    base_group_size = total_segments // group_count
    remainder = total_segments % group_count

    grouped_segments: list[list["TranscriptSegment"]] = []
    start_index = 0

    for group_index in range(group_count):
        current_group_size = base_group_size + (1 if group_index < remainder else 0)
        end_index = start_index + current_group_size
        grouped_segments.append(transcript_segments[start_index:end_index])
        start_index = end_index

    return grouped_segments


def _build_candidate(
    *,
    segment_group: list["TranscriptSegment"],
    group_index: int,
    total_groups: int,
) -> SemanticSegmentCandidate:
    transcript_text = " ".join(
        segment.text.strip()
        for segment in segment_group
        if segment.text.strip()
    ).strip()
    first_segment = segment_group[0]
    last_segment = segment_group[-1]

    if total_groups == 1:
        title = "\u89c6\u9891\u5185\u5bb9\u603b\u89c8"
        topic = "\u5355\u4e00\u8bdd\u9898\u6982\u89c8"
        summary = (
            f"\u8fd9\u4e00\u6bb5\u8f6c\u5199\u5185\u5bb9\u4e3b\u8981\u56f4\u7ed5"
            f"{_excerpt_text(transcript_text, 30)}\u5c55\u5f00\uff0c\u53ef\u4ee5\u4f5c\u4e3a\u4e00\u4e2a\u5b8c\u6574\u7684\u8bed\u4e49\u5355\u5143\u3002"
        )
        reason = (
            "\u8f93\u5165\u8f6c\u5199\u6bb5\u8f83\u77ed\uff0c\u6682\u65f6\u4e0d\u9700\u8981\u8fdb\u4e00\u6b65\u62c6\u5206\uff0c"
            "\u76f4\u63a5\u4f5c\u4e3a\u5355\u4e00\u8bdd\u9898\u6bb5\u5904\u7406\u66f4\u5408\u7406\u3002"
        )
    else:
        preset = _build_group_preset(group_index, total_groups)
        title = preset["title"]
        topic = preset["topic"]
        summary = (
            f"{preset['summary_prefix']}{_excerpt_text(transcript_text, 34)}"
            "\uff0c\u5f62\u6210\u4e86\u76f8\u5bf9\u5b8c\u6574\u7684\u8ba8\u8bba\u7247\u6bb5\u3002"
        )
        reason = (
            f"\u8fd9\u4e00\u6bb5\u5185\u5bb9\u5728{topic}\u4e0a\u4fdd\u6301\u8fde\u7eed\uff0c"
            "\u4e0e\u524d\u540e\u6bb5\u843d\u7684\u8ba8\u8bba\u91cd\u70b9\u5b58\u5728\u660e\u663e\u533a\u5206\uff0c"
            "\u9002\u5408\u4f5c\u4e3a\u72ec\u7acb\u8bed\u4e49\u6bb5\u3002"
        )

    return SemanticSegmentCandidate(
        start_time=first_segment.start_time,
        end_time=last_segment.end_time,
        title=title,
        summary=summary,
        topic=topic,
        keywords=_build_keywords(transcript_text, group_index),
        transcript_text=transcript_text,
        confidence=_build_confidence(group_index, total_groups),
        reason=reason,
    )


def _build_group_preset(group_index: int, total_groups: int) -> dict[str, str]:
    if total_groups == 4:
        presets = [
            {
                "title": "\u54c1\u724c\u89c6\u9891\u5904\u7406\u80cc\u666f",
                "topic": "\u4e1a\u52a1\u80cc\u666f\u4e0e\u73b0\u72b6",
                "summary_prefix": "\u8fd9\u4e00\u6bb5\u4e3b\u8981\u8bf4\u660e\u54c1\u724c\u90e8\u5904\u7406\u957f\u89c6\u9891\u7684\u73b0\u5728\u505a\u6cd5\uff0c",
            },
            {
                "title": "\u4eba\u5de5\u68c0\u7d22\u4e0e\u4e0a\u4e0b\u6587\u75db\u70b9",
                "topic": "\u4eba\u5de5\u5904\u7406\u75db\u70b9",
                "summary_prefix": "\u8fd9\u4e00\u6bb5\u805a\u7126\u4eba\u5de5\u56de\u770b\u89c6\u9891\u548c\u4e22\u5931\u4e0a\u4e0b\u6587\u7684\u6210\u672c\uff0c",
            },
            {
                "title": "\u97f3\u9891\u8f6c\u5199\u5230\u8bed\u4e49\u5206\u6bb5\u7684\u94fe\u8def",
                "topic": "\u5904\u7406\u94fe\u8def\u8bbe\u8ba1",
                "summary_prefix": "\u8fd9\u4e00\u6bb5\u8ba8\u8bba\u5148\u63d0\u53d6\u97f3\u9891\u3001\u518d\u751f\u6210\u8f6c\u5199\u548c\u8bed\u4e49\u5206\u6bb5\u7684\u987a\u5e8f\uff0c",
            },
            {
                "title": "\u5185\u5bb9\u590d\u7528\u4ef7\u503c\u4e0e\u4ea7\u54c1\u76ee\u6807",
                "topic": "\u590d\u7528\u4ef7\u503c\u4e0e\u9636\u6bb5\u76ee\u6807",
                "summary_prefix": "\u8fd9\u4e00\u6bb5\u8fdb\u4e00\u6b65\u8bf4\u660e\u8f6c\u5199\u548c\u8bed\u4e49\u5206\u6bb5\u5bf9\u540e\u7eed\u590d\u7528\u7684\u4ef7\u503c\uff0c",
            },
        ]
        return presets[group_index - 1]

    presets = [
        {
            "title": "\u54c1\u724c\u957f\u89c6\u9891\u5904\u7406\u80cc\u666f",
            "topic": "\u4e1a\u52a1\u80cc\u666f",
            "summary_prefix": "\u8fd9\u4e00\u6bb5\u4ece\u54c1\u724c\u90e8\u89d2\u5ea6\u4ea4\u4ee3\u957f\u89c6\u9891\u7d20\u6750\u7684\u5904\u7406\u80cc\u666f\uff0c",
        },
        {
            "title": "\u4eba\u5de5\u89c6\u9891\u68c0\u7d22\u7684\u6548\u7387\u95ee\u9898",
            "topic": "\u4eba\u5de5\u68c0\u7d22\u75db\u70b9",
            "summary_prefix": "\u8fd9\u4e00\u6bb5\u805a\u7126\u4eba\u5de5\u68c0\u7d22\u89c6\u9891\u548c\u62d6\u65f6\u95f4\u8f74\u5e26\u6765\u7684\u4f4e\u6548\u95ee\u9898\uff0c",
        },
        {
            "title": "\u4e3a\u4ec0\u4e48\u8981\u5148\u751f\u6210\u8f6c\u5199",
            "topic": "\u8f6c\u5199\u4f18\u5148\u7b56\u7565",
            "summary_prefix": "\u8fd9\u4e00\u6bb5\u5f3a\u8c03\u4e86\u5148\u628a\u8bf4\u8bdd\u5185\u5bb9\u53d8\u6210\u53ef\u7406\u89e3\u6587\u672c\u7684\u5fc5\u8981\u6027\uff0c",
        },
        {
            "title": "\u8bed\u4e49\u5206\u6bb5\u7684\u5ba1\u6838\u4e0e\u5143\u6570\u636e\u4ef7\u503c",
            "topic": "\u5ba1\u6838\u4e0e\u5185\u5bb9\u7ed3\u6784",
            "summary_prefix": "\u8fd9\u4e00\u6bb5\u8fdb\u5165\u5230\u5ba1\u6838\u548c\u5143\u6570\u636e\u7ba1\u7406\u89d2\u5ea6\uff0c",
        },
        {
            "title": "\u590d\u7528\u573a\u666f\u4e0e MVP \u4e0b\u4e00\u6b65",
            "topic": "\u590d\u7528\u4ef7\u503c\u4e0e\u9636\u6bb5\u89c4\u5212",
            "summary_prefix": "\u8fd9\u4e00\u6bb5\u6536\u675f\u5230\u590d\u7528\u573a\u666f\u548c MVP \u89c4\u5212\uff0c",
        },
    ]
    return presets[group_index - 1]


def _build_keywords(transcript_text: str, group_index: int) -> list[str]:
    keyword_candidates = [
        ("\u54c1\u724c", "\u54c1\u724c"),
        ("\u89c6\u9891", "\u89c6\u9891"),
        ("\u8f6c\u5199", "\u8f6c\u5199"),
        ("\u8bed\u4e49\u5206\u6bb5", "\u8bed\u4e49\u5206\u6bb5"),
        ("\u5185\u5bb9", "\u5185\u5bb9"),
        ("\u68c0\u7d22", "\u68c0\u7d22"),
        ("\u5ba1\u6838", "\u5ba1\u6838"),
        ("\u526a\u8f91", "\u526a\u8f91"),
        ("\u97f3\u9891", "\u97f3\u9891"),
        ("Mock ASR", "Mock ASR"),
    ]
    keywords = [
        keyword
        for needle, keyword in keyword_candidates
        if needle in transcript_text
    ]
    if keywords:
        return keywords[:4]

    fallback_keywords = [
        ["\u54c1\u724c\u89c6\u9891", "\u4e1a\u52a1\u80cc\u666f", "\u957f\u89c6\u9891"],
        ["\u4eba\u5de5\u68c0\u7d22", "\u4e0a\u4e0b\u6587", "\u6548\u7387"],
        ["\u8f6c\u5199", "\u5904\u7406\u94fe\u8def", "\u97f3\u9891"],
        ["\u8bed\u4e49\u5206\u6bb5", "\u5ba1\u6838", "\u5143\u6570\u636e"],
        ["MVP", "\u590d\u7528", "\u4ea7\u54c1\u89c4\u5212"],
    ]
    return fallback_keywords[min(group_index - 1, len(fallback_keywords) - 1)]


def _build_confidence(group_index: int, total_groups: int) -> float:
    if total_groups == 1:
        return 0.88

    confidence = 0.97 - ((group_index - 1) * 0.02)
    return max(0.8, min(0.99, confidence))


def _excerpt_text(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}\u2026"
