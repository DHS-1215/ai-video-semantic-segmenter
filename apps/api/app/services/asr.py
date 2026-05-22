from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from app.core.config import Settings
from app.core.errors import APIError


@dataclass(frozen=True)
class TranscriptResultSegment:
    start_time: float
    end_time: float
    speaker: str | None
    text: str


class ASRProvider(Protocol):
    requires_local_file: bool

    def transcribe(
        self,
        audio_source: str,
    ) -> list[TranscriptResultSegment]:
        ...


class MockASRProvider:
    requires_local_file = False

    def transcribe(
        self,
        audio_source: str,
    ) -> list[TranscriptResultSegment]:
        if not audio_source.strip():
            raise RuntimeError("Audio source is empty.")

        return [
            TranscriptResultSegment(
                start_time=0.0,
                end_time=40.0,
                speaker="\u6797\u6653",
                text=(
                    "\u5927\u5bb6\u597d\uff0c\u4eca\u5929\u6211\u4eec\u590d\u76d8\u7684\u662f"
                    "\u54c1\u724c\u56e2\u961f\u5904\u7406\u957f\u89c6\u9891\u5185\u5bb9\u7684"
                    "\u65b9\u5f0f\uff0c\u91cd\u70b9\u662f\u5982\u4f55\u4ece\u6574\u573a\u53d1"
                    "\u5e03\u4f1a\u548c\u8bbf\u8c08\u91cc\u5feb\u901f\u627e\u5230\u5b8c\u6574"
                    "\u8bdd\u9898\u3002"
                ),
            ),
            TranscriptResultSegment(
                start_time=40.0,
                end_time=82.0,
                speaker="\u5468\u660e",
                text=(
                    "\u73b0\u5728\u56e2\u961f\u627e\u7d20\u6750\u8fd8\u662f\u4e3b\u8981\u9760"
                    "\u4eba\u5de5\u4ece\u5934\u770b\u89c6\u9891\uff0c\u9047\u5230\u4e00\u4e2a"
                    "\u5c0f\u65f6\u4ee5\u4e0a\u7684\u5185\u5bb9\uff0c\u67e5\u627e\u6210\u672c"
                    "\u4f1a\u975e\u5e38\u9ad8\u3002"
                ),
            ),
            TranscriptResultSegment(
                start_time=82.0,
                end_time=124.0,
                speaker="\u9648\u6587",
                text=(
                    "\u4e0d\u4ec5\u8981\u53cd\u590d\u62d6\u65f6\u95f4\u8f74\uff0c\u8fd8\u8981"
                    "\u624b\u52a8\u8bb0\u4e0b\u6bcf\u6bb5\u5185\u5bb9\u7684\u5927\u610f\uff0c"
                    "\u6700\u540e\u518d\u6574\u7406\u6210\u80fd\u7ed9\u5185\u5bb9\u8fd0\u8425"
                    "\u548c\u526a\u8f91\u4f7f\u7528\u7684\u8bf4\u660e\u3002"
                ),
            ),
            TranscriptResultSegment(
                start_time=124.0,
                end_time=166.0,
                speaker="\u5468\u660e",
                text=(
                    "\u5982\u679c\u53ea\u6293\u51e0\u53e5\u9ad8\u5149\u91d1\u53e5\uff0c"
                    "\u5f80\u5f80\u4f1a\u4e22\u6389\u4e0a\u4e0b\u6587\uff0c\u6240\u4ee5\u6211\u4eec"
                    "\u66f4\u9700\u8981\u77e5\u9053\u5b8c\u6574\u8bdd\u9898\u662f\u4ece\u54ea\u91cc"
                    "\u5f00\u59cb\uff0c\u5230\u54ea\u91cc\u7ed3\u675f\u3002"
                ),
            ),
            TranscriptResultSegment(
                start_time=166.0,
                end_time=208.0,
                speaker="\u6797\u6653",
                text=(
                    "\u56e0\u6b64\u7b2c\u4e00\u6b65\u4e0d\u662f\u505a\u70ed\u70b9\u526a\u8f91\uff0c"
                    "\u800c\u662f\u5148\u628a\u89c6\u9891\u91cc\u7684\u8bf4\u8bdd\u5185\u5bb9\u8f6c\u6210"
                    "\u53ef\u7406\u89e3\u7684\u6587\u672c\uff0c\u518d\u57fa\u4e8e\u6587\u672c\u505a"
                    "\u8bed\u4e49\u5206\u6bb5\u3002"
                ),
            ),
            TranscriptResultSegment(
                start_time=208.0,
                end_time=250.0,
                speaker="\u5218\u6d0b",
                text=(
                    "\u4ea7\u54c1\u94fe\u8def\u53ef\u4ee5\u5148\u4ece\u4e0a\u4f20\u89c6\u9891\u3001"
                    "\u63d0\u53d6\u97f3\u9891\u3001\u751f\u6210\u8f6c\u5199\u5f00\u59cb\uff0c"
                    "\u628a\u57fa\u7840\u5904\u7406\u80fd\u529b\u8dd1\u901a\uff0c\u540e\u9762\u518d"
                    "\u63a5\u5165\u771f\u5b9e\u6a21\u578b\u3002"
                ),
            ),
            TranscriptResultSegment(
                start_time=250.0,
                end_time=292.0,
                speaker="\u9648\u6587",
                text=(
                    "\u6709\u4e86\u8f6c\u5199\u4e4b\u540e\uff0c\u56e2\u961f\u5c31\u80fd\u76f4\u63a5"
                    "\u68c0\u7d22\u4e3b\u9898\uff0c\u770b\u5230\u6bcf\u6bb5\u6587\u672c\u5bf9\u5e94\u7684"
                    "\u65f6\u95f4\u8303\u56f4\uff0c\u8fd9\u6837\u4eba\u5de5\u5ba1\u6838\u4e5f\u4f1a"
                    "\u8f7b\u5f88\u591a\u3002"
                ),
            ),
            TranscriptResultSegment(
                start_time=292.0,
                end_time=336.0,
                speaker="\u5218\u6d0b",
                text=(
                    "\u540e\u7eed\u8bed\u4e49\u5206\u6bb5\u53ea\u9700\u8981\u5728\u8f6c\u5199"
                    "\u57fa\u7840\u4e0a\u5224\u65ad\u8bdd\u9898\u8fb9\u754c\uff0c\u518d\u7ed9"
                    "\u6bcf\u6bb5\u751f\u6210\u6807\u9898\u3001\u6458\u8981\u548c\u5173\u952e\u8bcd\u3002"
                ),
            ),
            TranscriptResultSegment(
                start_time=336.0,
                end_time=378.0,
                speaker="\u5468\u660e",
                text=(
                    "\u8fd9\u6837\u540c\u4e00\u6761\u54c1\u724c\u89c6\u9891\u5c31\u80fd\u88ab\u62c6\u6210"
                    "\u591a\u4e2a\u5185\u5bb9\u5355\u5143\uff0c\u65e2\u80fd\u652f\u6301\u68c0\u7d22\uff0c"
                    "\u4e5f\u80fd\u7ed9\u540e\u7eed\u526a\u8f91\u548c\u590d\u7528\u63d0\u4f9b\u4f9d\u636e\u3002"
                ),
            ),
            TranscriptResultSegment(
                start_time=378.0,
                end_time=420.0,
                speaker="\u6797\u6653",
                text=(
                    "\u6240\u4ee5\u672c\u9636\u6bb5\u7684\u76ee\u6807\u5f88\u660e\u786e\uff0c"
                    "\u5148\u628a\u97f3\u9891\u63d0\u53d6\u548c\u8f6c\u5199\u94fe\u8def\u8dd1\u901a\uff0c"
                    "\u7528 Mock ASR \u9a8c\u8bc1\u63a5\u53e3\u548c\u6570\u636e\u7ed3\u6784"
                    "\u662f\u5426\u5408\u7406\u3002"
                ),
            ),
        ]


class FasterWhisperASRProvider:
    requires_local_file = True

    def __init__(
        self,
        *,
        model_size: str,
        device: str,
        compute_type: str,
        language: str,
        beam_size: int,
        whisper_model_cls: type[Any] | None = None,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self._whisper_model_cls = whisper_model_cls or _load_whisper_model_cls()
        self._model = self._whisper_model_cls(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

    def transcribe(
        self,
        audio_source: str,
    ) -> list[TranscriptResultSegment]:
        segments, _ = self._model.transcribe(
            audio_source,
            language=self.language,
            beam_size=self.beam_size,
            vad_filter=True,
        )

        transcript_results: list[TranscriptResultSegment] = []
        for segment in segments:
            text = str(getattr(segment, "text", "")).strip()
            if not text:
                continue

            transcript_results.append(
                TranscriptResultSegment(
                    start_time=float(getattr(segment, "start")),
                    end_time=float(getattr(segment, "end")),
                    speaker="Speaker 1",
                    text=text,
                )
            )

        if not transcript_results:
            raise RuntimeError("Faster-Whisper returned no valid transcript segments.")

        return transcript_results


def create_asr_provider(settings: Settings) -> ASRProvider:
    provider_name = settings.asr_provider.strip().lower()

    if provider_name == "mock":
        return MockASRProvider()

    if provider_name == "faster_whisper":
        try:
            return _get_cached_faster_whisper_provider(
                model_size=settings.faster_whisper_model_size,
                device=settings.faster_whisper_device,
                compute_type=settings.faster_whisper_compute_type,
                language=settings.faster_whisper_language,
                beam_size=settings.faster_whisper_beam_size,
            )
        except RuntimeError as exc:
            raise APIError(
                500,
                "asr_provider_unavailable",
                str(exc),
            ) from exc

    raise APIError(
        500,
        "invalid_asr_provider",
        (
            f"Unsupported ASR_PROVIDER '{settings.asr_provider}'. "
            "Supported values: mock, faster_whisper."
        ),
    )


@lru_cache
def _get_cached_faster_whisper_provider(
    *,
    model_size: str,
    device: str,
    compute_type: str,
    language: str,
    beam_size: int,
) -> FasterWhisperASRProvider:
    return FasterWhisperASRProvider(
        model_size=model_size,
        device=device,
        compute_type=compute_type,
        language=language,
        beam_size=beam_size,
    )


def _load_whisper_model_cls() -> type[Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Install apps/api requirements or set ASR_PROVIDER=mock."
        ) from exc

    return WhisperModel
