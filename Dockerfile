FROM node:24-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

FROM python-base AS test
ENV DATABASE_URL=sqlite:// PYTHONPATH=/app
COPY backend/app/ ./app/
COPY backend/tests/ ./tests/
COPY backend/requirements-dev.txt ./requirements-dev.txt
RUN pip install --no-cache-dir -r requirements-dev.txt
ARG TEST_RUN_ID=0
RUN pytest -q

FROM python-base AS runtime
COPY backend/app/ ./app/
COPY --from=frontend-build /frontend/dist/ ./app/static/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
