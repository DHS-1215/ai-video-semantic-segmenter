\# AGENTS.md



\## Project Goal



This project is an AI video semantic segmentation system for brand teams.



The first-stage goal is not viral highlight clipping. The goal is to understand all spoken content in a video and split the video into semantically complete segments based on topic changes.



The system should:

1\. Accept uploaded videos.

2\. Extract audio.

3\. Transcribe speech into timestamped transcript segments.

4\. Analyze transcript semantics.

5\. Detect topic boundaries.

6\. Generate semantic video segments.

7\. Allow users to preview, adjust, and export segments as video clips.



\## Core Concepts



Use these domain concepts carefully:



\- video: the original uploaded video.

\- transcript\_segment: a timestamped piece of speech text from ASR.

\- semantic\_segment: an AI-generated content section based on semantic topic boundaries.

\- video\_clip: an exported video file generated from a semantic segment.



Do not confuse semantic\_segment with video\_clip.



A semantic\_segment is an AI recommendation.

A video\_clip is an exported media file.



\## MVP Scope



Build the MVP in this order:



1\. Project skeleton.

2\. Video upload.

3\. Database models.

4\. Mock transcription.

5\. Mock semantic segmentation.

6\. Segment list UI.

7\. Real audio extraction.

8\. Real ASR integration.

9\. Real LLM semantic segmentation.

10\. Segment export using FFmpeg.



\## Tech Stack



\- Frontend: Next.js + TypeScript

\- Backend: Python FastAPI

\- Database: PostgreSQL

\- ORM: SQLAlchemy

\- Migration: Alembic

\- Queue: Redis + Celery

\- Video processing: FFmpeg

\- Object storage: MinIO for local development

\- Testing: pytest for backend



\## Backend Rules



1\. Keep the MVP simple.

2\. Use clear service boundaries.

3\. Every API should have consistent response structure.

4\. Every new backend feature should include basic tests.

5\. Do not hardcode credentials.

6\. Use environment variables.

7\. Mock external AI services before adding real integrations.

8\. Do not implement viral highlight scoring unless explicitly requested.

9\. The primary AI output is semantic\_segments, not clips.



\## Required Tables



\### videos



\- id

\- filename

\- original\_url

\- preview\_url

\- duration\_seconds

\- status

\- created\_at

\- updated\_at



\### transcript\_segments



\- id

\- video\_id

\- start\_time

\- end\_time

\- speaker

\- text

\- sort\_order

\- created\_at



\### semantic\_segments



\- id

\- video\_id

\- start\_time

\- end\_time

\- title

\- summary

\- topic

\- keywords

\- transcript\_text

\- confidence

\- reason

\- sort\_order

\- created\_at

\- updated\_at



\### video\_clips



\- id

\- video\_id

\- semantic\_segment\_id

\- start\_time

\- end\_time

\- clip\_url

\- subtitle\_url

\- export\_status

\- created\_at

\- updated\_at



\### processing\_jobs



\- id

\- video\_id

\- job\_type

\- status

\- error\_message

\- created\_at

\- updated\_at



\## Definition of Done



A task is done only when:



1\. Code runs locally.

2\. Tests pass, or failures are clearly documented.

3\. README is updated if setup changes.

4\. New APIs are documented.

5\. Limitations are clearly stated.

