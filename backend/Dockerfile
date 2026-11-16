# syntax=docker/dockerfile:1.7

FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS base

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY . .

FROM base AS dev

RUN addgroup --system station \
    && adduser --system --ingroup station station \
    && mkdir -p /app/staticfiles \
    && chown -R station:station /app /tmp
USER station
CMD ["sleep", "infinity"]

FROM base AS test

COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-dev.txt
RUN python -m ruff check .
RUN pytest
RUN echo "pytest passed" > /tmp/pytest-passed

FROM base AS runtime
COPY --from=test /tmp/pytest-passed /tmp/pytest-passed
RUN addgroup --system station \
    && adduser --system --ingroup station station \
    && mkdir -p /app/staticfiles \
    && chown -R station:station /app /tmp
USER station

CMD ["sleep", "infinity"]
