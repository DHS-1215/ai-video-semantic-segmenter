from __future__ import annotations

import subprocess


class FFmpegServiceError(RuntimeError):
    pass


def extract_audio(input_video_path: str, output_audio_path: str) -> float:
    ffmpeg_command = [
        "ffmpeg",
        "-y",
        "-i",
        input_video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        output_audio_path,
    ]
    ffmpeg_result = subprocess.run(
        ffmpeg_command,
        capture_output=True,
        text=True,
    )
    if ffmpeg_result.returncode != 0:
        raise FFmpegServiceError(
            f"ffmpeg failed with code {ffmpeg_result.returncode}: "
            f"{ffmpeg_result.stderr.strip() or ffmpeg_result.stdout.strip()}"
        )

    ffprobe_command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        input_video_path,
    ]
    ffprobe_result = subprocess.run(
        ffprobe_command,
        capture_output=True,
        text=True,
    )
    if ffprobe_result.returncode != 0:
        raise FFmpegServiceError(
            f"ffprobe failed with code {ffprobe_result.returncode}: "
            f"{ffprobe_result.stderr.strip() or ffprobe_result.stdout.strip()}"
        )

    raw_duration = ffprobe_result.stdout.strip()
    try:
        duration_seconds = float(raw_duration)
    except ValueError as exc:
        raise FFmpegServiceError(
            f"ffprobe returned an invalid duration value: {raw_duration or '<empty>'}"
        ) from exc

    if duration_seconds < 0:
        raise FFmpegServiceError(
            f"ffprobe returned a negative duration value: {duration_seconds}"
        )

    return duration_seconds
