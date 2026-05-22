from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, Protocol

import httpx

from app.core.config import Settings
from app.core.errors import APIError

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


class ZhipuSemanticSegmenterProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float,
        timeout_seconds: int,
        client_factory: Callable[[str, int], Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        factory = client_factory or _build_zhipu_client
        self._client = factory(self.api_key, self.timeout_seconds)

    def segment(
        self,
        transcript_segments: list["TranscriptSegment"],
    ) -> list[SemanticSegmentCandidate]:
        ordered_segments = sorted(
            transcript_segments,
            key=lambda segment: segment.sort_order,
        )
        if not ordered_segments:
            raise APIError(
                500,
                "semantic_segmenter_invalid_output",
                "No transcript segments were provided to the semantic segmenter.",
            )

        transcript_payload = _build_transcript_payload(ordered_segments)
        total_duration_seconds = _get_total_transcript_duration_seconds(ordered_segments)
        system_prompt = _build_zhipu_system_prompt()
        user_prompt = _build_zhipu_user_prompt(
            transcript_payload=transcript_payload,
            total_duration_seconds=total_duration_seconds,
        )

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise _build_zhipu_request_error(exc) from exc

        raw_content = _extract_response_content(response)
        segment_payloads = _parse_segment_payloads(raw_content)
        candidates = _validate_segment_payloads(
            segment_payloads=segment_payloads,
            transcript_segments=ordered_segments,
        )
        return candidates


def create_semantic_segmenter_provider(settings: Settings) -> SemanticSegmenterProvider:
    provider_name = settings.semantic_segmenter_provider.strip().lower()

    if provider_name == "mock":
        return MockSemanticSegmenterProvider()

    if provider_name == "zhipu":
        if not settings.zhipu_api_key.strip():
            raise APIError(
                500,
                "zhipu_api_key_missing",
                "ZHIPU_API_KEY is required when SEMANTIC_SEGMENTER_PROVIDER=zhipu.",
            )
        try:
            return _get_cached_zhipu_semantic_segmenter_provider(
                api_key=settings.zhipu_api_key,
                model=settings.zhipu_model,
                temperature=settings.zhipu_temperature,
                timeout_seconds=settings.zhipu_timeout_seconds,
            )
        except RuntimeError as exc:
            raise APIError(
                500,
                "semantic_segmenter_provider_unavailable",
                str(exc),
            ) from exc

    raise APIError(
        500,
        "invalid_semantic_segmenter_provider",
        (
            f"Unsupported SEMANTIC_SEGMENTER_PROVIDER "
            f"'{settings.semantic_segmenter_provider}'. "
            "Supported values: mock, zhipu."
        ),
    )


@lru_cache
def _get_cached_zhipu_semantic_segmenter_provider(
    *,
    api_key: str,
    model: str,
    temperature: float,
    timeout_seconds: int,
) -> ZhipuSemanticSegmenterProvider:
    return ZhipuSemanticSegmenterProvider(
        api_key=api_key,
        model=model,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
    )


def _build_zhipu_client(api_key: str, timeout_seconds: int) -> Any:
    client_cls = _load_zhipu_client_cls()
    return client_cls(
        api_key=api_key,
        timeout=httpx.Timeout(timeout_seconds),
    )


def _load_zhipu_client_cls() -> type[Any]:
    try:
        from zhipuai import ZhipuAI
    except ImportError as exc:
        raise RuntimeError(
            "zhipuai is not installed. Install apps/api requirements or set SEMANTIC_SEGMENTER_PROVIDER=mock."
        ) from exc

    return ZhipuAI


def _build_transcript_payload(transcript_segments: list["TranscriptSegment"]) -> str:
    lines = []
    for segment in transcript_segments:
        speaker = segment.speaker or "Unknown"
        text = " ".join(segment.text.split())
        lines.append(
            f"- sort_order={segment.sort_order}, "
            f"start_time={segment.start_time:.3f}, "
            f"end_time={segment.end_time:.3f}, "
            f"speaker={speaker}, "
            f"text={text}"
        )
    return "\n".join(lines)


def _build_zhipu_system_prompt() -> str:
    return (
        "你是品牌视频语义切片规划助手，不是逐句摘要工具。"
        "你的任务是基于 transcript_segments 规划适合后续剪辑、审核和内容复用的完整话题段，"
        "而不是按每句话切分。"
        "你必须只基于 transcript_segments 中已经出现的信息生成结果，"
        "不要纠正、扩写、脑补或发明 ASR 文本里没有的事实。"
        "如果 ASR 文本疑似有错字或识别错误，也不要自行修正事实，只能保守概括。"
    )


def _build_zhipu_user_prompt(
    *,
    transcript_payload: str,
    total_duration_seconds: float,
) -> str:
    return (
        "请基于下方带时间戳的 transcript_segments，为品牌视频规划语义完整、可剪辑的片段：\n"
        f"- 当前视频/转写总时长约 {total_duration_seconds:.1f} 秒\n"
        "- 只输出 JSON，不要输出 Markdown，不要输出解释文本\n"
        "- 顶层结构可以是 {\"segments\": [...]} 或直接 [...]\n"
        "- 每个 segment 必须包含 start_time, end_time, title, summary, topic, keywords, transcript_text, confidence, reason\n"
        "- 你不是逐句摘要工具，不要按每句话拆分\n"
        "- 结果必须只基于 transcript_segments 里出现的信息，不要纠正、扩写、脑补或发明原文没有的事实\n"
        "- 如果 ASR 文本疑似错字或误识别，也不要自行修正事实，只能保守概括\n"
        "- summary 必须忠实描述 transcript_text，不要加入原文没有明确表达的判断\n"
        "- reason 只解释为什么这里是语义边界，不要添加新事实\n"
        "- title/topic 要概括该段主题，但不能虚构实体名、品牌名、人名或事件名\n"
        "- transcript_text 必须来自对应 transcript_segments 的文本拼接或简洁摘录，不要引用无关内容\n"
        "- 每个 segment 应对应完整话题、完整讨论点、完整场景或完整讲述单元，优先能作为品牌视频切片候选\n"
        "- 如果相邻内容主题相近，应合并为一个段落\n"
        "- 不要连续生成多个 5-10 秒碎片，除非视频极短且话题确实切换很快\n"
        "- start_time/end_time 必须来自或贴近 transcript_segments 的时间范围，不要从句子中间切开\n"
        "- 分段数量建议：1 分钟以内视频 1-3 段；1-3 分钟视频 2-4 段；3-8 分钟视频 4-6 段；8 分钟以上视频 5-8 段\n"
        "- 时长建议：1 分钟以内视频可以出现 8-20 秒段落；3 分钟以上视频每段优先 30 秒以上\n"
        "- 3-8 分钟视频优先输出 4-6 个完整话题段；无论如何不要超过 8 段\n"
        "- title 不超过 30 字\n"
        "- summary 不超过 120 字\n"
        "- reason 不超过 120 字\n"
        "- keywords 提供 3-6 个\n"
        "- confidence 必须是 0 到 1 的数字\n"
        "- 不要生成空 title、空 summary、空 topic、空 reason、空 transcript_text\n\n"
        "transcript_segments：\n"
        f"{transcript_payload}"
    )


def _extract_response_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except Exception as exc:
        raise APIError(
            500,
            "semantic_segmenter_invalid_output",
            f"Zhipu response did not contain message content: {exc}",
        ) from exc

    if isinstance(content, str):
        return _strip_json_fence(content.strip())

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        joined_content = "".join(parts).strip()
        if joined_content:
            return _strip_json_fence(joined_content)

    raise APIError(
        500,
        "semantic_segmenter_invalid_output",
        "Zhipu response content was empty or not a supported text format.",
    )


def _strip_json_fence(value: str) -> str:
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return value


def _parse_segment_payloads(raw_content: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise APIError(
            500,
            "semantic_segmenter_invalid_json",
            f"Failed to parse semantic segmenter JSON: {exc}",
        ) from exc

    if isinstance(parsed, dict):
        segment_payloads = parsed.get("segments")
    else:
        segment_payloads = parsed

    if not isinstance(segment_payloads, list):
        raise APIError(
            500,
            "semantic_segmenter_invalid_output",
            "Semantic segmenter output must be a list or an object with a segments list.",
        )

    normalized_payloads: list[dict[str, Any]] = []
    for payload in segment_payloads:
        if not isinstance(payload, dict):
            raise APIError(
                500,
                "semantic_segmenter_invalid_output",
                "Each semantic segment must be an object.",
            )
        normalized_payloads.append(payload)

    return normalized_payloads


def _validate_segment_payloads(
    *,
    segment_payloads: list[dict[str, Any]],
    transcript_segments: list["TranscriptSegment"],
) -> list[SemanticSegmentCandidate]:
    if not segment_payloads:
        raise APIError(
            500,
            "semantic_segmenter_invalid_output",
            "no_segments_generated: Zhipu semantic segmenter produced no segments.",
        )

    min_start = min(segment.start_time for segment in transcript_segments)
    max_end = max(segment.end_time for segment in transcript_segments)

    candidates: list[SemanticSegmentCandidate] = []
    for payload in segment_payloads:
        start_time = _coerce_float(payload, "start_time")
        end_time = _coerce_float(payload, "end_time")
        confidence = _coerce_float(payload, "confidence")
        title = _coerce_non_empty_str(payload, "title")
        summary = _coerce_non_empty_str(payload, "summary")
        topic = _coerce_non_empty_str(payload, "topic")
        transcript_text = _coerce_non_empty_str(payload, "transcript_text")
        reason = _coerce_non_empty_str(payload, "reason")
        keywords = _coerce_keywords(payload)

        if start_time >= end_time:
            raise APIError(
                500,
                "semantic_segmenter_invalid_output",
                "Semantic segment start_time must be smaller than end_time.",
            )

        if not 0.0 <= confidence <= 1.0:
            raise APIError(
                500,
                "semantic_segmenter_invalid_output",
                "Semantic segment confidence must be between 0 and 1.",
            )

        if start_time < (min_start - 5.0) or end_time > (max_end + 5.0):
            raise APIError(
                500,
                "semantic_segmenter_invalid_output",
                "Semantic segment times fall outside the transcript range.",
            )

        candidates.append(
            SemanticSegmentCandidate(
                start_time=start_time,
                end_time=end_time,
                title=title,
                summary=summary,
                topic=topic,
                keywords=keywords,
                transcript_text=transcript_text,
                confidence=confidence,
                reason=reason,
            )
        )

    candidates.sort(key=lambda candidate: (candidate.start_time, candidate.end_time))
    _validate_segment_granularity(
        candidates=candidates,
        transcript_segments=transcript_segments,
    )
    return candidates


def _validate_segment_granularity(
    *,
    candidates: list[SemanticSegmentCandidate],
    transcript_segments: list["TranscriptSegment"],
) -> None:
    total_duration_seconds = _get_total_transcript_duration_seconds(transcript_segments)
    if total_duration_seconds < 180.0:
        return

    if len(candidates) > 8:
        raise APIError(
            500,
            "semantic_segmenter_invalid_output",
            f"too_many_segments: Long video produced {len(candidates)} segments.",
        )

    short_segment_count = sum(
        1 for candidate in candidates if (candidate.end_time - candidate.start_time) < 20.0
    )
    if short_segment_count > (len(candidates) / 2):
        raise APIError(
            500,
            "semantic_segmenter_invalid_output",
            (
                "segments_too_short: More than half of the generated segments are "
                "shorter than 20 seconds for a long video."
            ),
        )

    if len(candidates) >= 3:
        opening_duration_seconds = sum(
            candidate.end_time - candidate.start_time for candidate in candidates[:3]
        )
        if opening_duration_seconds < 30.0:
            raise APIError(
                500,
                "semantic_segmenter_invalid_output",
                (
                    "opening_segments_too_fragmented: The first three generated "
                    "segments cover less than 30 seconds for a long video."
                ),
            )


def _get_total_transcript_duration_seconds(
    transcript_segments: list["TranscriptSegment"],
) -> float:
    return max(segment.end_time for segment in transcript_segments) - min(
        segment.start_time for segment in transcript_segments
    )


def _build_zhipu_request_error(exc: Exception) -> APIError:
    detail = str(exc).strip() or exc.__class__.__name__
    if _is_timeout_error(exc, detail):
        return APIError(
            500,
            "semantic_segmenter_timeout",
            (
                "\u667a\u8c31\u8bed\u4e49\u5206\u6bb5\u8bf7\u6c42\u8d85\u65f6\uff0c"
                "\u8bf7\u7a0d\u540e\u91cd\u8bd5\uff0c\u6216\u7f29\u77ed\u89c6\u9891/"
                "\u589e\u52a0 ZHIPU_TIMEOUT_SECONDS\u3002 "
                f"\u539f\u59cb\u9519\u8bef: {detail}"
            ),
        )

    return APIError(
        500,
        "semantic_segmenter_request_failed",
        f"\u667a\u8c31\u8bed\u4e49\u5206\u6bb5\u8bf7\u6c42\u5931\u8d25\uff1a{detail}",
    )


def _is_timeout_error(exc: Exception, detail: str) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True

    normalized = detail.lower()
    return "timed out" in normalized or "timeout" in normalized


def _coerce_float(payload: dict[str, Any], field_name: str) -> float:
    value = payload.get(field_name)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise APIError(
            500,
            "semantic_segmenter_invalid_output",
            f"Semantic segment field {field_name} must be a number.",
        ) from exc


def _coerce_non_empty_str(payload: dict[str, Any], field_name: str) -> str:
    value = str(payload.get(field_name, "")).strip()
    if not value:
        raise APIError(
            500,
            "semantic_segmenter_invalid_output",
            f"Semantic segment field {field_name} must be a non-empty string.",
        )
    return value


def _coerce_keywords(payload: dict[str, Any]) -> list[str]:
    keywords = payload.get("keywords")
    if not isinstance(keywords, list):
        raise APIError(
            500,
            "semantic_segmenter_invalid_output",
            "Semantic segment keywords must be a list of strings.",
        )

    normalized_keywords = [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
    if not normalized_keywords:
        raise APIError(
            500,
            "semantic_segmenter_invalid_output",
            "Semantic segment keywords must contain at least one non-empty string.",
        )

    return normalized_keywords


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
