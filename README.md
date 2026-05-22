# ai-video-semantic-segmenter

Project skeleton for an AI video semantic segmentation system focused on splitting long-form video transcripts into semantic content segments for brand teams.

This repository now includes the current MVP foundation for semantic video segmentation: SQLAlchemy models and Alembic migrations, a backend upload API that stores original videos in MinIO, a synchronous mock transcript + semantic segmentation pipeline, a frontend MVP for upload/list/detail flows, and a synchronous backend audio extraction API that downloads source video from MinIO, runs local FFmpeg to extract mono 16 kHz WAV audio, uploads the extracted audio back to MinIO, and stores audio metadata on the `videos` row.

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

The audio extraction endpoint requires local `ffmpeg` and `ffprobe`. It only extracts audio in this round and does not run ASR, LLM semantic segmentation, clip export, or Celery tasks.

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
7. Click `运行 Mock Pipeline`.
8. Review the Chinese mock transcript and semantic segmentation results.

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
- Alembic includes an initial `create_core_tables` migration.
- `POST /api/videos/upload` stores the original video in MinIO, creates a `videos` record, and creates one pending `mock_pipeline` processing job.
- `POST /api/videos/{video_id}/jobs/extract-audio` downloads the original MinIO object, extracts mono 16 kHz WAV audio with FFmpeg, uploads the generated audio back to MinIO, and stores audio metadata on the `videos` row.
- `POST /api/videos/{video_id}/jobs/mock-pipeline` runs a synchronous mock transcript + semantic segmentation pipeline for product-loop validation.
- `GET /api/videos` lists uploaded videos ordered by `created_at` descending.
- `GET /api/videos/{video_id}` returns one video record.
- `GET /api/videos/{video_id}/transcript` returns transcript segments in `sort_order` order, or an empty array when none exist.
- `GET /api/videos/{video_id}/segments` returns mock semantic segments in `sort_order` order.
- `GET /api/videos/{video_id}/jobs` returns processing jobs for the video.
- The frontend MVP includes `/`, `/videos`, and `/videos/{id}` pages that call the existing backend APIs directly.
- The frontend uses the synchronous mock pipeline and displays Chinese simulated transcript and semantic segment data.
- The frontend expects `NEXT_PUBLIC_API_BASE_URL` to point at the running FastAPI service.
- Celery wiring is scaffolded, but no real video-processing tasks are implemented.

Detailed API note: see `docs/api.md`.

## Current Limitations

- No real ASR pipeline
- No real audio-to-text pipeline yet after extraction
- No real semantic segmentation AI workflow yet
- No video clip export pipeline yet
- Uploading a video only creates a pending `mock_pipeline` job until the mock pipeline endpoint is called
- Audio extraction runs synchronously in the API process and is not queued through Celery yet
- The mock pipeline produces synthetic transcript and semantic segment data for product validation only
- No real video preview or player
- No real background processing pipeline
- No AI integrations
