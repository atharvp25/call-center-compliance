web: uvicorn src.main:app --host 0.0.0.0 --port $PORT
worker: celery -A src.celery_tasks worker --loglevel=info --concurrency=2
