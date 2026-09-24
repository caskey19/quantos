FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY packages ./packages
COPY config ./config
COPY services ./services
RUN pip install --no-cache-dir ".[postgres]"

EXPOSE 8000
CMD ["python", "-m", "quantos.api"]
