from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.api.deps import get_semantic_segmenter_provider
from app.core.config import get_settings
from app.core.errors import APIError
from app.services.semantic_segmenter import (
    MockSemanticSegmenterProvider,
    SemanticSegmentCandidate,
    ZhipuSemanticSegmenterProvider,
)


def _build_transcript_segments() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            sort_order=1,
            start_time=0.0,
            end_time=40.0,
            speaker="Speaker 1",
            text="Brand team explains the current long-video review workflow.   ",
        ),
        SimpleNamespace(
            sort_order=2,
            start_time=40.0,
            end_time=82.0,
            speaker="Speaker 2",
            text="  The team then discusses manual search cost and missing context.",
        ),
        SimpleNamespace(
            sort_order=3,
            start_time=82.0,
            end_time=120.0,
            speaker="Speaker 1",
            text="Finally they explain how structured metadata helps reuse.",
        ),
    ]


def _build_long_transcript_segments() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            sort_order=1,
            start_time=0.0,
            end_time=60.0,
            speaker="Speaker 1",
            text="Section one covers brand video processing background and source material.",
        ),
        SimpleNamespace(
            sort_order=2,
            start_time=60.0,
            end_time=120.0,
            speaker="Speaker 2",
            text="Section two focuses on manual search cost and missing context problems.",
        ),
        SimpleNamespace(
            sort_order=3,
            start_time=120.0,
            end_time=180.0,
            speaker="Speaker 1",
            text="Section three explains why transcription should happen before segmentation.",
        ),
        SimpleNamespace(
            sort_order=4,
            start_time=180.0,
            end_time=240.0,
            speaker="Speaker 2",
            text="Section four explains how semantic segments help review and reuse.",
        ),
        SimpleNamespace(
            sort_order=5,
            start_time=240.0,
            end_time=300.0,
            speaker="Speaker 1",
            text="Section five summarizes MVP scope and the next product steps.",
        ),
    ]


def _build_short_video_transcript_segments() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            sort_order=1,
            start_time=0.0,
            end_time=16.0,
            speaker="Speaker 1",
            text="Short intro about the campaign background.",
        ),
        SimpleNamespace(
            sort_order=2,
            start_time=16.0,
            end_time=32.0,
            speaker="Speaker 2",
            text="Short explanation of the immediate action item.",
        ),
        SimpleNamespace(
            sort_order=3,
            start_time=32.0,
            end_time=48.0,
            speaker="Speaker 1",
            text="Short wrap-up on the final deliverable.",
        ),
    ]


def _build_fake_zhipu_client(
    *,
    content: str,
    captured: dict[str, object] | None = None,
):
    class FakeCompletions:
        def create(self, **kwargs):
            if captured is not None:
                captured["kwargs"] = kwargs
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=content),
                    )
                ]
            )

    return SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
    )


def test_get_semantic_segmenter_provider_defaults_to_mock(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "semantic_segmenter_provider", "mock")

    provider = get_semantic_segmenter_provider()

    assert isinstance(provider, MockSemanticSegmenterProvider)


def test_get_semantic_segmenter_provider_rejects_unknown_provider(
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "semantic_segmenter_provider", "unknown")

    with pytest.raises(APIError) as exc_info:
        get_semantic_segmenter_provider()

    assert exc_info.value.code == "invalid_semantic_segmenter_provider"
    assert "mock, zhipu" in exc_info.value.message


def test_get_semantic_segmenter_provider_requires_zhipu_api_key(
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "semantic_segmenter_provider", "zhipu")
    monkeypatch.setattr(settings, "zhipu_api_key", "")

    with pytest.raises(APIError) as exc_info:
        get_semantic_segmenter_provider()

    assert exc_info.value.code == "zhipu_api_key_missing"
    assert "ZHIPU_API_KEY" in exc_info.value.message


def test_zhipu_prompt_requires_faithful_output() -> None:
    captured: dict[str, object] = {}
    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: _build_fake_zhipu_client(
            content=(
                '{"segments":['
                '{"start_time":0.0,"end_time":120.0,'
                '"title":"Workflow background",'
                '"summary":"Stays on the transcripted workflow and manual review pain.",'
                '"topic":"Workflow background",'
                '"keywords":["brand","workflow","review"],'
                '"transcript_text":"Brand team explains the current long-video review workflow. The team then discusses manual search cost and missing context. Finally they explain how structured metadata helps reuse.",'
                '"confidence":0.9,'
                '"reason":"This range stays on one complete workflow discussion before the next topic boundary."}'
                ']}'
            ),
            captured=captured,
        ),
    )

    provider.segment(_build_transcript_segments())

    messages = captured["kwargs"]["messages"]
    system_prompt = messages[0]["content"]
    user_prompt = messages[1]["content"]

    assert "只基于 transcript_segments" in system_prompt
    assert "不要纠正、扩写、脑补或发明" in system_prompt
    assert "summary 必须忠实描述 transcript_text" in user_prompt
    assert "reason 只解释为什么这里是语义边界" in user_prompt
    assert "不能虚构实体名" in user_prompt
    assert "如果相邻内容主题相近，应合并" in user_prompt
    assert "1 分钟以内视频 1-3 段" in user_prompt
    assert "3-8 分钟视频 4-6 段" in user_prompt
    assert "keywords 提供 3-6 个" in user_prompt
    assert "只输出 JSON" in user_prompt
    assert "The team then discusses manual search cost and missing context." in user_prompt
    assert "  The team then discusses manual search cost and missing context." not in user_prompt


def test_zhipu_segmenter_parses_valid_segments() -> None:
    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: _build_fake_zhipu_client(
            content=(
                '{"segments":['
                '{"start_time":0.0,"end_time":82.0,'
                '"title":"Brand workflow background",'
                '"summary":"Explains the current long-video review workflow and manual search cost.",'
                '"topic":"Workflow background",'
                '"keywords":["brand","video","review"],'
                '"transcript_text":"Brand team explains the current long-video review workflow. The team then discusses manual search cost and missing context.",'
                '"confidence":0.92,'
                '"reason":"The first two transcript ranges stay on the same business problem and form a complete topic."},'
                '{"start_time":82.0,"end_time":120.0,'
                '"title":"Structured reuse value",'
                '"summary":"Explains how structured transcript metadata helps downstream reuse.",'
                '"topic":"Reuse value",'
                '"keywords":["summary","keywords","reuse"],'
                '"transcript_text":"Finally they explain how structured metadata helps reuse.",'
                '"confidence":0.88,'
                '"reason":"The last transcript range closes on the downstream value of structured output."}'
                ']}'
            )
        ),
    )

    candidates = provider.segment(_build_transcript_segments())

    assert candidates == [
        SemanticSegmentCandidate(
            start_time=0.0,
            end_time=82.0,
            title="Brand workflow background",
            summary="Explains the current long-video review workflow and manual search cost.",
            topic="Workflow background",
            keywords=["brand", "video", "review"],
            transcript_text=(
                "Brand team explains the current long-video review workflow. "
                "The team then discusses manual search cost and missing context."
            ),
            confidence=0.92,
            reason=(
                "The first two transcript ranges stay on the same business problem "
                "and form a complete topic."
            ),
        ),
        SemanticSegmentCandidate(
            start_time=82.0,
            end_time=120.0,
            title="Structured reuse value",
            summary="Explains how structured transcript metadata helps downstream reuse.",
            topic="Reuse value",
            keywords=["summary", "keywords", "reuse"],
            transcript_text="Finally they explain how structured metadata helps reuse.",
            confidence=0.88,
            reason=(
                "The last transcript range closes on the downstream value of "
                "structured output."
            ),
        ),
    ]


def test_zhipu_segmenter_timeout_error_message_is_clear() -> None:
    class TimeoutCompletions:
        def create(self, **kwargs):
            raise httpx.TimeoutException("Request timed out.")

    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: SimpleNamespace(
            chat=SimpleNamespace(completions=TimeoutCompletions())
        ),
    )

    with pytest.raises(APIError) as exc_info:
        provider.segment(_build_long_transcript_segments())

    assert exc_info.value.code == "semantic_segmenter_timeout"
    assert "ZHIPU_TIMEOUT_SECONDS" in exc_info.value.message
    assert "Request timed out." in exc_info.value.message


def test_zhipu_segmenter_rejects_invalid_json() -> None:
    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: _build_fake_zhipu_client(
            content="not-json"
        ),
    )

    with pytest.raises(APIError) as exc_info:
        provider.segment(_build_transcript_segments())

    assert exc_info.value.code == "semantic_segmenter_invalid_json"


def test_zhipu_segmenter_rejects_invalid_segment_shape() -> None:
    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: _build_fake_zhipu_client(
            content=(
                '{"segments":['
                '{"start_time":10,"end_time":5,"title":"","summary":"bad",'
                '"topic":"bad","keywords":"bad","transcript_text":"","confidence":2,'
                '"reason":""}'
                ']}'
            )
        ),
    )

    with pytest.raises(APIError) as exc_info:
        provider.segment(_build_transcript_segments())

    assert exc_info.value.code == "semantic_segmenter_invalid_output"


def test_zhipu_segmenter_rejects_too_many_segments_for_long_video() -> None:
    segment_payload = ",".join(
        [
            (
                '{"start_time":0.0,"end_time":30.0,"title":"Segment 1",'
                '"summary":"Topic 1 summary","topic":"Topic 1",'
                '"keywords":["k1","k2","k3"],"transcript_text":"A",'
                '"confidence":0.8,"reason":"Boundary 1"}'
            ),
            (
                '{"start_time":30.0,"end_time":60.0,"title":"Segment 2",'
                '"summary":"Topic 2 summary","topic":"Topic 2",'
                '"keywords":["k1","k2","k3"],"transcript_text":"B",'
                '"confidence":0.8,"reason":"Boundary 2"}'
            ),
            (
                '{"start_time":60.0,"end_time":90.0,"title":"Segment 3",'
                '"summary":"Topic 3 summary","topic":"Topic 3",'
                '"keywords":["k1","k2","k3"],"transcript_text":"C",'
                '"confidence":0.8,"reason":"Boundary 3"}'
            ),
            (
                '{"start_time":90.0,"end_time":120.0,"title":"Segment 4",'
                '"summary":"Topic 4 summary","topic":"Topic 4",'
                '"keywords":["k1","k2","k3"],"transcript_text":"D",'
                '"confidence":0.8,"reason":"Boundary 4"}'
            ),
            (
                '{"start_time":120.0,"end_time":150.0,"title":"Segment 5",'
                '"summary":"Topic 5 summary","topic":"Topic 5",'
                '"keywords":["k1","k2","k3"],"transcript_text":"E",'
                '"confidence":0.8,"reason":"Boundary 5"}'
            ),
            (
                '{"start_time":150.0,"end_time":180.0,"title":"Segment 6",'
                '"summary":"Topic 6 summary","topic":"Topic 6",'
                '"keywords":["k1","k2","k3"],"transcript_text":"F",'
                '"confidence":0.8,"reason":"Boundary 6"}'
            ),
            (
                '{"start_time":180.0,"end_time":210.0,"title":"Segment 7",'
                '"summary":"Topic 7 summary","topic":"Topic 7",'
                '"keywords":["k1","k2","k3"],"transcript_text":"G",'
                '"confidence":0.8,"reason":"Boundary 7"}'
            ),
            (
                '{"start_time":210.0,"end_time":240.0,"title":"Segment 8",'
                '"summary":"Topic 8 summary","topic":"Topic 8",'
                '"keywords":["k1","k2","k3"],"transcript_text":"H",'
                '"confidence":0.8,"reason":"Boundary 8"}'
            ),
            (
                '{"start_time":240.0,"end_time":300.0,"title":"Segment 9",'
                '"summary":"Topic 9 summary","topic":"Topic 9",'
                '"keywords":["k1","k2","k3"],"transcript_text":"I",'
                '"confidence":0.8,"reason":"Boundary 9"}'
            ),
        ]
    )
    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: _build_fake_zhipu_client(
            content=f'{{"segments":[{segment_payload}]}}'
        ),
    )

    with pytest.raises(APIError) as exc_info:
        provider.segment(_build_long_transcript_segments())

    assert exc_info.value.code == "semantic_segmenter_invalid_output"
    assert "too_many_segments" in exc_info.value.message


def test_zhipu_segmenter_rejects_many_too_short_segments_for_long_video() -> None:
    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: _build_fake_zhipu_client(
            content=(
                '{"segments":['
                '{"start_time":0.0,"end_time":15.0,"title":"Segment 1","summary":"Summary 1","topic":"Topic 1","keywords":["k1","k2","k3"],"transcript_text":"A","confidence":0.8,"reason":"Boundary 1"},'
                '{"start_time":15.0,"end_time":30.0,"title":"Segment 2","summary":"Summary 2","topic":"Topic 2","keywords":["k1","k2","k3"],"transcript_text":"B","confidence":0.8,"reason":"Boundary 2"},'
                '{"start_time":30.0,"end_time":45.0,"title":"Segment 3","summary":"Summary 3","topic":"Topic 3","keywords":["k1","k2","k3"],"transcript_text":"C","confidence":0.8,"reason":"Boundary 3"},'
                '{"start_time":45.0,"end_time":120.0,"title":"Segment 4","summary":"Summary 4","topic":"Topic 4","keywords":["k1","k2","k3"],"transcript_text":"D","confidence":0.8,"reason":"Boundary 4"},'
                '{"start_time":120.0,"end_time":135.0,"title":"Segment 5","summary":"Summary 5","topic":"Topic 5","keywords":["k1","k2","k3"],"transcript_text":"E","confidence":0.8,"reason":"Boundary 5"},'
                '{"start_time":135.0,"end_time":300.0,"title":"Segment 6","summary":"Summary 6","topic":"Topic 6","keywords":["k1","k2","k3"],"transcript_text":"F","confidence":0.8,"reason":"Boundary 6"}'
                ']}'
            )
        ),
    )

    with pytest.raises(APIError) as exc_info:
        provider.segment(_build_long_transcript_segments())

    assert exc_info.value.code == "semantic_segmenter_invalid_output"
    assert "segments_too_short" in exc_info.value.message


def test_zhipu_segmenter_rejects_fragmented_opening_segments() -> None:
    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: _build_fake_zhipu_client(
            content=(
                '{"segments":['
                '{"start_time":0.0,"end_time":8.0,"title":"Segment 1","summary":"Summary 1","topic":"Topic 1","keywords":["k1","k2","k3"],"transcript_text":"A","confidence":0.8,"reason":"Boundary 1"},'
                '{"start_time":8.0,"end_time":18.0,"title":"Segment 2","summary":"Summary 2","topic":"Topic 2","keywords":["k1","k2","k3"],"transcript_text":"B","confidence":0.8,"reason":"Boundary 2"},'
                '{"start_time":18.0,"end_time":28.0,"title":"Segment 3","summary":"Summary 3","topic":"Topic 3","keywords":["k1","k2","k3"],"transcript_text":"C","confidence":0.8,"reason":"Boundary 3"},'
                '{"start_time":28.0,"end_time":90.0,"title":"Segment 4","summary":"Summary 4","topic":"Topic 4","keywords":["k1","k2","k3"],"transcript_text":"D","confidence":0.8,"reason":"Boundary 4"},'
                '{"start_time":90.0,"end_time":150.0,"title":"Segment 5","summary":"Summary 5","topic":"Topic 5","keywords":["k1","k2","k3"],"transcript_text":"E","confidence":0.8,"reason":"Boundary 5"},'
                '{"start_time":150.0,"end_time":220.0,"title":"Segment 6","summary":"Summary 6","topic":"Topic 6","keywords":["k1","k2","k3"],"transcript_text":"F","confidence":0.8,"reason":"Boundary 6"},'
                '{"start_time":220.0,"end_time":300.0,"title":"Segment 7","summary":"Summary 7","topic":"Topic 7","keywords":["k1","k2","k3"],"transcript_text":"G","confidence":0.8,"reason":"Boundary 7"}'
                ']}'
            )
        ),
    )

    with pytest.raises(APIError) as exc_info:
        provider.segment(_build_long_transcript_segments())

    assert exc_info.value.code == "semantic_segmenter_invalid_output"
    assert "opening_segments_too_fragmented" in exc_info.value.message


def test_zhipu_segmenter_allows_short_video_short_segments() -> None:
    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: _build_fake_zhipu_client(
            content=(
                '{"segments":['
                '{"start_time":0.0,"end_time":12.0,"title":"Intro","summary":"Covers the campaign background.","topic":"Background","keywords":["campaign","intro","brand"],"transcript_text":"Short intro about the campaign background.","confidence":0.84,"reason":"The opening is a self-contained introduction."},'
                '{"start_time":12.0,"end_time":24.0,"title":"Action item","summary":"Covers the immediate action item.","topic":"Action item","keywords":["action","task","delivery"],"transcript_text":"Short explanation of the immediate action item.","confidence":0.83,"reason":"The middle range shifts to a concrete next step."},'
                '{"start_time":24.0,"end_time":48.0,"title":"Wrap-up","summary":"Covers the final deliverable.","topic":"Wrap-up","keywords":["wrap-up","delivery","result"],"transcript_text":"Short wrap-up on the final deliverable.","confidence":0.85,"reason":"The ending range closes on the deliverable."}'
                ']}'
            )
        ),
    )

    candidates = provider.segment(_build_short_video_transcript_segments())

    assert len(candidates) == 3
    assert [candidate.title for candidate in candidates] == [
        "Intro",
        "Action item",
        "Wrap-up",
    ]


def test_zhipu_segmenter_accepts_reasonable_topic_segments() -> None:
    provider = ZhipuSemanticSegmenterProvider(
        api_key="test-key",
        model="glm-4-flash",
        temperature=0.2,
        timeout_seconds=300,
        client_factory=lambda api_key, timeout_seconds: _build_fake_zhipu_client(
            content=(
                '{"segments":['
                '{"start_time":0.0,"end_time":90.0,"title":"Workflow background","summary":"Explains the current process and manual search pain.","topic":"Workflow background","keywords":["brand","review","context"],"transcript_text":"Section one covers brand video processing background and source material. Section two focuses on manual search cost and missing context problems.","confidence":0.9,"reason":"The first two transcript ranges stay on the same business problem."},'
                '{"start_time":90.0,"end_time":180.0,"title":"Why transcription comes first","summary":"Explains why transcript generation should happen before segmentation.","topic":"Processing strategy","keywords":["transcript","segmentation","pipeline"],"transcript_text":"Section three explains why transcription should happen before segmentation.","confidence":0.88,"reason":"This section is a self-contained explanation of the processing order."},'
                '{"start_time":180.0,"end_time":300.0,"title":"Review reuse and next steps","summary":"Explains review value, reuse value, and the next MVP step.","topic":"Reuse value","keywords":["review","reuse","mvp"],"transcript_text":"Section four explains how semantic segments help review and reuse. Section five summarizes MVP scope and the next product steps.","confidence":0.87,"reason":"The last two transcript ranges stay on downstream review value and planning."}'
                ']}'
            )
        ),
    )

    candidates = provider.segment(_build_long_transcript_segments())

    assert len(candidates) == 3
    assert [candidate.title for candidate in candidates] == [
        "Workflow background",
        "Why transcription comes first",
        "Review reuse and next steps",
    ]
