FROM python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

FROM base AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
RUN pytest
RUN echo "pytest passed" > /tmp/pytest-passed

FROM base AS runtime

COPY --from=test /tmp/pytest-passed /tmp/pytest-passed

CMD ["sleep", "infinity"]
