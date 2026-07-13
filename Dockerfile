FROM python:3.12-slim

LABEL maintainer="Ryan Lieu <github-benzBrake@woai.ru>"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8082

WORKDIR /app

COPY requirements.txt pyproject.toml ./

RUN python -m venv /app/.venv \
    && /app/.venv/bin/pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY resources ./resources
COPY scripts ./scripts

RUN chmod +x ./scripts/run_app.sh ./scripts/kill.sh

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os, sys, urllib.request; port = os.environ.get('PORT', '8082'); url = f'http://127.0.0.1:{port}/health'; response = urllib.request.urlopen(url, timeout=3); sys.exit(0 if response.status == 200 else 1)"

CMD ["./scripts/run_app.sh", "--foreground"]
