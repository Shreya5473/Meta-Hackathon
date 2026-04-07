# Multi-stage Dockerfile for Hugging Face Spaces
# Stage 1: Build frontend with Node.js
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend source
COPY frontend/package*.json ./

# Clean up package-lock.json and node_modules to fix native binding errors
RUN rm -f package-lock.json && rm -rf node_modules

RUN npm install --force

COPY frontend ./
RUN npm run build

# Stage 2: Python backend with built frontend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY app ./app
COPY config ./config
COPY db ./db
COPY alembic ./alembic
COPY scripts ./scripts

# NOTE: We intentionally do NOT copy inference.py or other helper scripts
# They are not needed for the FastAPI app and cause asyncio conflicts
# OpenEnv will fetch inference.py from GitHub separately for evaluation

# Copy built frontend from stage 1 into backend directory
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose port 7860 for Hugging Face Spaces
EXPOSE 7860

# Run FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
