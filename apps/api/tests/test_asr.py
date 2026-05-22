from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.deps import get_asr_provider
from app.core.config import get_settings
from app.core.errors import APIError
from app.services import asr as asr_service
from app.services.asr import (
    FasterWhisperASRProvider,
    MockASRProvider,
    TranscriptResultSegment,
)


def test_get_asr_provider_defaults_to_mock(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "asr_provider", "mock")

    provider = get_asr_provider()

    assert isinstance(provider, MockASRProvider)
    assert provider.requires_local_file is False


def test_get_asr_provider_rejects_unknown_provider(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "asr_provider", "unknown")

    with pytest.raises(APIError) as exc_info:
        get_asr_provider()

    assert exc_info.value.code == "invalid_asr_provider"
    assert "mock, faster_whisper" in exc_info.value.message


def test_get_asr_provider_reports_missing_faster_whisper(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "asr_provider", "faster_whisper")
    monkeypatch.setattr(
        asr_service,
        "_get_cached_faster_whisper_provider",
        lambda **_: (_ for _ in ()).throw(
            RuntimeError(
                "faster-whisper is not installed. Install apps/api requirements or set ASR_PROVIDER=mock."
            )
        ),
    )

    with pytest.raises(APIError) as exc_info:
        get_asr_provider()

    assert exc_info.value.code == "asr_provider_unavailable"
    assert "ASR_PROVIDER=mock" in exc_info.value.message


def test_faster_whisper_provider_maps_segments_to_transcript_results() -> None:
    captured: dict[str, object] = {}

    class FakeWhisperModel:
        def __init__(self, model_size: str, *, device: str, compute_type: str) -> None:
            captured["init"] = {
                "model_size": model_size,
                "device": device,
                "compute_type": compute_type,
            }

        def transcribe(
            self,
            audio_path: str,
            *,
            language: str,
            beam_size: int,
            vad_filter: bool,
        ):
            captured["transcribe"] = {
                "audio_path": audio_path,
                "language": language,
                "beam_size": beam_size,
                "vad_filter": vad_filter,
            }
            return (
                [
                    SimpleNamespace(start=0.0, end=1.5, text="  第一段转写  "),
                    SimpleNamespace(start=1.5, end=3.0, text=""),
                    SimpleNamespace(start=3.0, end=4.8, text="第二段转写"),
                ],
                SimpleNamespace(language="zh"),
            )

    provider = FasterWhisperASRProvider(
        model_size="base",
        device="cpu",
        compute_type="int8",
        language="zh",
        beam_size=5,
        whisper_model_cls=FakeWhisperModel,
    )

    results = provider.transcribe("C:\\temp\\audio.wav")

    assert provider.requires_local_file is True
    assert captured["init"] == {
        "model_size": "base",
        "device": "cpu",
        "compute_type": "int8",
    }
    assert captured["transcribe"] == {
        "audio_path": "C:\\temp\\audio.wav",
        "language": "zh",
        "beam_size": 5,
        "vad_filter": True,
    }
    assert results == [
        TranscriptResultSegment(
            start_time=0.0,
            end_time=1.5,
            speaker="Speaker 1",
            text="第一段转写",
        ),
        TranscriptResultSegment(
            start_time=3.0,
            end_time=4.8,
            speaker="Speaker 1",
            text="第二段转写",
        ),
    ]
