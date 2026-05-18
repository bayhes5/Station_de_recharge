# syntax=docker/dockerfile:1.7

FROM python:3.14-slim@sha256:7a500125bc50693f2214e842a621440a1b1b9cbb2188f74ab045d29ed2ea5856 AS base

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
