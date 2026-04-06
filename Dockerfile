# ── GeoTrade OpenEnv — Dockerfile for Hugging Face Spaces ────────────────────
#
# Build:  docker build -t geotrade-openenv .
# Run:    docker run -p 7860:7860 \
#           -e API_BASE_URL=https://api.openai.com/v1 \
#           -e MODEL_NAME=gpt-4o-mini \
#           -e HF_TOKEN=sk-... \
#           geotrade-openenv
#
# HF Spaces uses port 7860.

FROM python:3.11-slim

# Minimal system deps
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements_openenv.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements_openenv.txt

# Copy only OpenEnv source (no heavy ML/DB dependencies needed)
COPY openenv/ ./openenv/
COPY openenv.yaml ./
COPY inference.py ./

# Runtime env (override at docker run time)
ENV API_BASE_URL="https://api.openai.com/v1"
ENV MODEL_NAME="gpt-4o-mini"
ENV HF_TOKEN=""
ENV PYTHONPATH="/app"
ENV PORT=7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "openenv.server:app", \
     "--host", "0.0.0.0", "--port", "7860", \
     "--workers", "1", "--log-level", "info"]
