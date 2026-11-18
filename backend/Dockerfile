# Build dari root proyek: docker build -f backend/Dockerfile .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /opt/shared
RUN pip install --no-cache-dir --no-deps /opt/shared
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY backend/app ./app
RUN groupadd --system foodsave && useradd --system --gid foodsave foodsave \
    && mkdir -p /app/storage && chown -R foodsave:foodsave /app/storage
USER foodsave
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
