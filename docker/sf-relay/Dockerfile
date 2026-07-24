FROM python:3.11-slim

LABEL maintainer="sf-relay"
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY docker/sf-relay/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sf_token_relay.py .

EXPOSE 5000

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

CMD ["python3", "sf_token_relay.py", "--host", "0.0.0.0", "--port", "5000"]
