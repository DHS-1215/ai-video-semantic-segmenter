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

### `GET /api/videos/{video_id}/transcript`

Returns transcript segments ordered by `sort_order` ascending. If the video exists but no transcript has been created yet, the endpoint returns an empty array.

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

### `GET /api/videos/{video_id}/segments`

Returns semantic segments ordered by `sort_order` ascending.

### `GET /api/videos/{video_id}/jobs`

Returns processing jobs ordered by `created_at` descending.

## Scope

- This round does not implement ASR, real LLM semantic segmentation, FFmpeg, Celery processing, or clip export.
- The transcript and semantic segment data returned by the mock pipeline are synthetic Chinese fixtures for product loop validation in a brand-team scenario only.
- Uploading a video only stores the original file and creates a pending `mock_pipeline` job for future processing stages.
