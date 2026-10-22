# Satu image: frontend SIHALAL tiruan (React) + backend FastAPI + agen. Build dari root repo:
#   gcloud run deploy kawalhalal --source .
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV VITE_API_MODE=http
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Operator Kala mengisi web SIHALAL lewat browser tanpa kepala (KALA_OPERATOR=ui)
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw
RUN playwright install --with-deps chromium && chmod -R a+rX /opt/pw
COPY backend/ .
COPY --from=frontend /fe/dist ./static
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser
EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
