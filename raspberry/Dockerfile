# syntax=docker/dockerfile:1.7

FROM python:3.11-slim

WORKDIR /app

COPY app/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY app/ .

RUN addgroup --system station \
    && adduser --system --ingroup station station \
    && chown -R station:station /app /tmp

USER station

ENV OFFLINE_DB_PATH=/tmp/offline_cache.sqlite3
ENV CHARGE_STATE_DB_PATH=/tmp/charge_state.sqlite3
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "main.py"]
