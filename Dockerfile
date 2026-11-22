# syntax=docker/dockerfile:1
#
# Telegram bot image. Single Dockerfile for x86_64 (linux/amd64) and ARM64 (linux/arm64):
# python:3.12-slim is multi-arch, and all dependencies (aiogram, docker, aiosqlite,
# python-dotenv) have prebuilt wheels for both platforms, so no compilation is needed.
#
#   Native build:          docker build -t ctf-sandbox-bot .
#   Specific architecture: docker buildx build --platform linux/arm64 -t ctf-sandbox-bot:arm64 --load .
#   Both architectures:    docker buildx build --platform linux/amd64,linux/arm64 -t REGISTRY/ctf-sandbox-bot:latest --push .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DB_PATH=/data/sandbox.db

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bot code + sandbox Dockerfile (the bot builds the ctf-sandbox image from it on first start)
COPY *.py sandbox.Dockerfile ./
COPY bot ./bot
COPY db ./db
COPY tasks ./tasks

# SQLite database lives in a volume
RUN mkdir -p /data
VOLUME ["/data"]

CMD ["python", "main.py"]
