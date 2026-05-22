# ai-video-semantic-segmenter

Project skeleton for an AI video semantic segmentation system focused on splitting long-form video transcripts into semantic content segments for brand teams.

This repository currently includes:

- SQLAlchemy models and Alembic migrations for the core MVP tables
- A backend upload API that stores original videos in MinIO
- A configurable ASR transcription API that can use `MockASRProvider` or local Faster-Whisper
- A synchronous mock transcript and semantic segmentation pipeline
- A frontend MVP for upload, list, and detail flows
- A synchronous backend audio extraction API that downloads source video from MinIO, runs local FFmpeg to extract mono 16 kHz WAV audio, uploads the extracted audio back to MinIO, and stores audio metadata on the `videos` row

## Repository Layout

```text
apps/
  api/                FastAPI service
  web/                Next.js + TypeScript frontend
workers/
  video_worker/       Celery worker
infra/
  docker-compose.yml  PostgreSQL, Redis, MinIO
docs/
  api.md              Minimal API documentation
packages/
  shared/             Shared TypeScript package placeholder
```

## Prerequisites

- Python 3.10+
- Node.js 16.14+
- npm 8+
- Docker Desktop
- FFmpeg and ffprobe available on `PATH`

## Environment Setup

1. Copy `.env.example` to `.env`.
2. Adjust credentials or ports if needed.
3. Confirm `BACKEND_CORS_ORIGINS` includes your frontend origin, such as `http://localhost:3000`.
4. Keep `ASR_PROVIDER=mock` for normal development, or switch to `ASR_PROVIDER=faster_whisper` only when you want local real ASR.

## Install Dependencies

### Web

```powershell
npm install
```

### API

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r apps/api/requirements.txt
```

### Worker

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r workers/video_worker/requirements.txt
```

## Start Infrastructure

```powershell
docker compose -f infra/docker-compose.yml --env-file .env up -d
```

Services:

- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`
- PostgreSQL and Redis include Docker healthchecks in `docker-compose.yml`
- MinIO does not yet include a compose healthcheck to keep the setup simple
- The API expects MinIO to be available before video uploads

## Start Services

### API

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location apps/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Database Migrations

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location apps/api
alembic upgrade head
```

To create a future migration:

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location apps/api
alembic revision --autogenerate -m "describe_change"
```

### Database Verification

```powershell
cd apps/api
alembic upgrade head
alembic downgrade base
alembic upgrade head
pytest
```

Health check:

```powershell
Invoke-WebRequest http://localhost:8000/health
```

Upload example:

```powershell
curl -X POST http://localhost:8000/api/videos/upload ^
  -F "file=@C:\path\to\example.mp4"
```

Audio extraction example:

```powershell
curl -X POST http://localhost:8000/api/videos/{video_id}/jobs/extract-audio
```

Mock transcription example:

```powershell
curl -X POST http://localhost:8000/api/videos/{video_id}/jobs/transcribe-audio
```

Mock semantic segmentation example:

```powershell
curl -X POST http://localhost:8000/api/videos/{video_id}/jobs/semantic-segmentation
```

The audio extraction endpoint requires local `ffmpeg` and `ffprobe`.
The transcription endpoint supports `ASR_PROVIDER=mock` or `ASR_PROVIDER=faster_whisper`.
The semantic segmentation endpoint currently uses `MockSemanticSegmenterProvider` only.
This round does not run any paid ASR, real LLM semantic segmentation, clip export, or Celery tasks.

### Web

```powershell
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Or from the repository root:

```powershell
npm run dev:web
```

Open `http://localhost:3000`.

The frontend reads `NEXT_PUBLIC_API_BASE_URL` from `apps/web/.env.local`. The default value is `http://localhost:8000`.
The backend reads allowed browser origins from `BACKEND_CORS_ORIGINS` in the repository root `.env`.
If browser requests fail, first confirm the API is running on `http://localhost:8000` and that `BACKEND_CORS_ORIGINS` includes the frontend origin you are using.

## MVP Demo Flow

1. Start infrastructure with Docker Compose.
2. Start the FastAPI service.
3. Start the Next.js frontend.
4. Open the home page in the browser.
5. Upload a demo video file.
6. Enter the video detail page after upload.
7. Click the audio extraction button.
8. Click the transcription button.
9. Click the semantic segmentation button.
10. Review the generated transcript list and semantic segment results.
11. Optionally click the `Run Mock Pipeline` button to inspect the existing all-in-one demo flow.

## Processing Flow

Current synchronous processing path:

1. Upload video
2. Extract audio
3. Generate transcript with the configured ASR provider
4. Generate semantic segments with `MockSemanticSegmenterProvider`

## Local Faster-Whisper ASR

Default development mode keeps `ASR_PROVIDER=mock`, which avoids local model loading and is better for API and UI debugging.

To enable local real ASR, set the following values in the repository root `.env`:

```dotenv
ASR_PROVIDER=faster_whisper
FASTER_WHISPER_MODEL_SIZE=base
FASTER_WHISPER_DEVICE=cpu
FASTER_WHISPER_COMPUTE_TYPE=int8
FASTER_WHISPER_LANGUAGE=zh
FASTER_WHISPER_BEAM_SIZE=5
```

Notes:

- `faster_whisper` runs locally and does not create paid API usage.
- The first run may download or load the selected model, so startup latency depends on model size and machine performance.
- If your machine is weaker, start with `tiny` or `base`.
- For routine development and smoke tests, `mock` remains the safer default.
- On Windows, confirm `ffmpeg` and `ffprobe` are already available on `PATH` before trying the real ASR flow.
- Depending on your Python environment, `faster-whisper` may require compatible local runtime libraries from its upstream dependencies.

## Audio Extraction Smoke Test

1. Confirm FFmpeg is available:

```powershell
ffmpeg -version
ffprobe -version
```

2. Start infrastructure, backend, and frontend.
3. Upload a new video from the home page. Use a newly uploaded video so `original_object_name` is guaranteed to exist.
4. Open the video detail page and click the audio extraction button.
5. Confirm the page shows non-empty `audio_url`, `audio_object_name`, and `duration_seconds`.
6. Confirm the `extract_audio` job status becomes the completed audio extraction state.
7. Open the MinIO Console at `http://localhost:9001` and verify `videos/{video_id}/audio/audio.wav` exists.

### Celery Worker

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location workers/video_worker
celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo
```

The `--pool=solo` flag is used for local Windows compatibility.

### Ping Task

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location workers/video_worker
celery -A app.celery_app.celery_app call app.tasks.ping
```

## Run Tests

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location apps/api
pytest
```

## API Notes

- `GET /health` returns a minimal success payload.
- Core SQLAlchemy tables are defined for videos, transcript segments, semantic segments, video clips, and processing jobs.
- Alembic includes the initial core tables migration and the video audio metadata migration.
- `POST /api/videos/upload` stores the original video in MinIO, creates a `videos` record, and creates one pending `mock_pipeline` processing job.
- `POST /api/videos/{video_id}/jobs/extract-audio` downloads the original MinIO object, extracts mono 16 kHz WAV audio with FFmpeg, uploads the generated audio back to MinIO, and stores audio metadata on the `videos` row.
- `POST /api/videos/{video_id}/jobs/transcribe-audio` reads `audio_object_name`, then uses the configured ASR provider to write transcript rows into `transcript_segments`.
- `POST /api/videos/{video_id}/jobs/semantic-segmentation` reads `transcript_segments`, runs `MockSemanticSegmenterProvider`, and writes semantic rows into `semantic_segments`.
- `POST /api/videos/{video_id}/jobs/mock-pipeline` runs a synchronous mock transcript and semantic segmentation pipeline for product-loop validation.
- `GET /api/videos` lists uploaded videos ordered by `created_at` descending.
- `GET /api/videos/{video_id}` returns one video record.
- `GET /api/videos/{video_id}/transcript` returns transcript segments in `sort_order` order, or an empty array when none exist.
- `GET /api/videos/{video_id}/segments` returns mock semantic segments in `sort_order` order.
- `GET /api/videos/{video_id}/jobs` returns processing jobs for the video.
- The frontend MVP includes `/`, `/videos`, and `/videos/{id}` pages that call the existing backend APIs directly.
- The frontend can now trigger synchronous audio extraction, configured ASR transcription, and mock semantic segmentation from the detail page.
- The frontend expects `NEXT_PUBLIC_API_BASE_URL` to point at the running FastAPI service.
- Celery wiring is scaffolded, but no real video-processing tasks are implemented.

Detailed API note: see `docs/api.md`.

## Current Limitations

- Real transcription currently supports local Faster-Whisper only; no paid cloud ASR is integrated
- Default development transcription still uses `MockASRProvider`
- No real semantic segmentation AI workflow yet
- Semantic segmentation uses `MockSemanticSegmenterProvider` only and does not call any real LLM service
- No video clip export pipeline yet
- Uploading a video only creates a pending `mock_pipeline` job until the mock pipeline endpoint is called
- Audio extraction runs synchronously in the API process and is not queued through Celery yet
- The mock pipeline produces synthetic transcript and semantic segment data for product validation only
- No real video preview or player
- No real background processing pipeline
- No AI integrations
