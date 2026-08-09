FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
# Keep dependency-download retries and cache local to this BuildKit build.
# This avoids changing Docker daemon DNS/settings used by other projects.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 10 -r requirements.txt
COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--no-access-log"]
