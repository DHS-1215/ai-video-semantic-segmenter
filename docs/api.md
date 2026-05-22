# API

## Endpoints

### `GET /health`

Returns a minimal, consistent JSON payload for service health.

Example response:

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "api",
    "environment": "development"
  }
}
```

### `POST /api/videos/upload`

Accepts a multipart file upload using the `file` field.

Behavior:

- Validates file extension against `mp4`, `mov`, `webm`, `mkv`
- Validates size against `MAX_UPLOAD_SIZE_MB`
- Uploads the original file to MinIO
- Creates a `videos` row
- Creates a pending `processing_jobs` row with `job_type = "mock_pipeline"`
- Stores `original_object_name` for later real media processing

Example success response:

```json
{
  "success": true,
  "data": {
    "video_id": "d828ea75-bd27-4cbf-9fd3-4c480d9a577c",
    "status": "pending",
    "filename": "example.mp4",
    "original_url": "http://localhost:9000/videos/videos/d828ea75-bd27-4cbf-9fd3-4c480d9a577c/original/example.mp4"
  }
}
```

Development note:

- `original_url` currently stores a local MinIO access URL for development convenience.
- Future workers should prefer `bucket + object_name` or an internal object key instead of depending on `original_url`.

Example error response:

```json
{
  "success": false,
  "error": {
    "code": "unsupported_file_type",
    "message": "Only mp4, mov, webm, and mkv uploads are supported."
  }
}
```

### `GET /api/videos`

Returns uploaded videos ordered by `created_at` descending.

Query params:

- `limit`: default `20`, max `100`

### `GET /api/videos/{video_id}`

Returns a single video record. Missing IDs return:

```json
{
  "success": false,
  "error": {
    "code": "video_not_found",
    "message": "Video not found."
  }
}
```

The detail payload now also includes:

- `original_object_name`
- `audio_url`
- `audio_object_name`

### `GET /api/videos/{video_id}/transcript`

Returns transcript segments ordered by `sort_order` ascending. If the video exists but no transcript has been created yet, the endpoint returns an empty array.

Current sources of transcript rows:

- `POST /api/videos/{video_id}/jobs/transcribe-audio` via the configured ASR provider
- `POST /api/videos/{video_id}/jobs/mock-pipeline` via the existing demo pipeline

### `POST /api/videos/{video_id}/jobs/mock-pipeline`

Runs a synchronous mock semantic segmentation pipeline for one uploaded video.

Behavior:

- Replaces existing transcript and semantic segment rows for the target video
- Reuses or creates a `mock_pipeline` processing job
- Sets job status `running -> completed`
- Sets `video.status` to `completed` on success
- The generated transcript and semantic segment content is Chinese mock business data for brand team demos

Example response:

```json
{
  "success": true,
  "data": {
    "video_id": "d828ea75-bd27-4cbf-9fd3-4c480d9a577c",
    "transcript_segments_created": 10,
    "semantic_segments_created": 5,
    "job_status": "completed"
  }
}
```

### `POST /api/videos/{video_id}/jobs/extract-audio`

Downloads the original video from MinIO, extracts mono 16 kHz WAV audio with local `ffmpeg`, uploads the extracted audio back to MinIO, and records the resulting audio metadata on the `videos` row.

Requirements:

- `video.original_object_name` must exist, otherwise the API returns `400 missing_original_object`
- `ffmpeg` and `ffprobe` must be installed locally and available on `PATH`

Behavior:

- Reuses or creates a `processing_jobs` row with `job_type = "extract_audio"`
- Sets job status `running -> completed` on success
- Stores `audio_url`, `audio_object_name`, and `duration_seconds` on the `videos` row
- Returns `500 audio_extraction_failed` if MinIO download, `ffmpeg`, upload, or final database persistence fails
- This round only extracts audio; it does not run ASR, LLM segmentation, clip export, or Celery jobs

Example success response:

```json
{
  "success": true,
  "data": {
    "video_id": "d828ea75-bd27-4cbf-9fd3-4c480d9a577c",
    "job_status": "completed",
    "audio_url": "http://localhost:9000/videos/videos/d828ea75-bd27-4cbf-9fd3-4c480d9a577c/audio/audio.wav",
    "audio_object_name": "videos/d828ea75-bd27-4cbf-9fd3-4c480d9a577c/audio/audio.wav",
    "duration_seconds": 420.0
  }
}
```

### `POST /api/videos/{video_id}/jobs/transcribe-audio`

Reads the extracted audio reference from `video.audio_object_name`, calls the configured ASR provider, and stores transcript rows into `transcript_segments`.

Requirements:

- `video.audio_object_name` must exist, otherwise the API returns `400 missing_audio_object`

Behavior:

- Reuses or creates a `processing_jobs` row with `job_type = "transcribe_audio"`
- Sets job status `running -> completed` on success
- Replaces existing transcript rows for the target video before writing the new transcript results
- Returns `500 audio_transcription_failed` if the provider or final persistence fails
- Supports `ASR_PROVIDER=mock` or `ASR_PROVIDER=faster_whisper`
- `mock` uses `MockASRProvider` and does not touch local model files
- `faster_whisper` uses a local Faster-Whisper model and does not produce external API usage fees
- When `faster_whisper` is enabled, the backend downloads the extracted audio to a local temp file before transcription
- The first Faster-Whisper run may need to download or load the selected model, so startup latency depends on machine performance and model size

Example success response:

```json
{
  "success": true,
  "data": {
    "video_id": "d828ea75-bd27-4cbf-9fd3-4c480d9a577c",
    "transcript_segments_created": 10,
    "job_status": "completed"
  }
}
```

### `POST /api/videos/{video_id}/jobs/semantic-segmentation`

Reads the current `transcript_segments` for the target video, calls `MockSemanticSegmenterProvider`, and stores semantic rows into `semantic_segments`.

Requirements:

- The video must already have transcript rows, otherwise the API returns `400 missing_transcript_segments`

Behavior:

- Reuses or creates a `processing_jobs` row with `job_type = "semantic_segment"`
- Sets job status `running -> completed` on success
- Replaces existing semantic segment rows for the target video before writing the new segmentation results
- Returns `500 semantic_segmentation_failed` if the provider or final persistence fails
- This round uses `MockSemanticSegmenterProvider` only. It does not call any real LLM vendor or local model

Example success response:

```json
{
  "success": true,
  "data": {
    "video_id": "d828ea75-bd27-4cbf-9fd3-4c480d9a577c",
    "semantic_segments_created": 5,
    "job_status": "completed"
  }
}
```

### `GET /api/videos/{video_id}/segments`

Returns semantic segments ordered by `sort_order` ascending.

Current sources of semantic segment rows:

- `POST /api/videos/{video_id}/jobs/semantic-segmentation` via `MockSemanticSegmenterProvider`
- `POST /api/videos/{video_id}/jobs/mock-pipeline` via the existing demo pipeline

### `GET /api/videos/{video_id}/jobs`

Returns processing jobs ordered by `created_at` descending.

## Scope

- This round adds synchronous FFmpeg-based audio extraction, configurable synchronous ASR transcription, and synchronous mock semantic segmentation.
- This round does not implement any paid ASR provider, real LLM semantic segmentation provider, Celery processing, or clip export.
- The transcript and semantic segment data returned by the mock pipeline are synthetic Chinese fixtures for product loop validation in a brand-team scenario only.
- Uploading a video only stores the original file and creates a pending `mock_pipeline` job for future processing stages.
- Audio extraction, configured ASR transcription, and mock semantic segmentation remain separate API steps and are not chained automatically.
