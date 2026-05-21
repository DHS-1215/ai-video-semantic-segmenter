from app.celery_app import celery_app


@celery_app.task(name="app.tasks.ping")
def ping() -> dict[str, str]:
    return {"status": "ok", "worker": "video_worker"}
