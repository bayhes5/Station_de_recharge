# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY . .

FROM base AS dev

CMD ["sleep", "infinity"]

FROM base AS test

COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-dev.txt
RUN python -m ruff check .
RUN pytest
RUN echo "pytest passed" > /tmp/pytest-passed

FROM base AS runtime
COPY --from=test /tmp/pytest-passed /tmp/pytest-passed

CMD ["sleep", "infinity"]
