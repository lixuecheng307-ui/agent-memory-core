FROM python:3.11-slim

WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir -e .
CMD ["memory-core", "benchmark"]
