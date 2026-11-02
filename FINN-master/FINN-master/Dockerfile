# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy frontend dependency manifests and install reproducibly
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source code and build production assets
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python runtime
FROM python:3.12-slim
WORKDIR /app

# Install runtime Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source
COPY backend ./backend

# Copy compiled frontend assets from builder stage
COPY --from=frontend-builder /app/backend/static ./backend/static

# Copy verified production database snapshot (only finn.db, no backups or source PDFs)
COPY data/finn.db ./data/finn.db

# Environment configuration
ENV PYTHONPATH=/app/backend
ENV FINN_DB=/app/data/finn.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Start Uvicorn serving both API and frontend on dynamic port
CMD ["sh", "-c", "uvicorn finn.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
