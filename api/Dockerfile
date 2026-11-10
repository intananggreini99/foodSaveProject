FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt
COPY requirements-report.txt ./
RUN pip install --no-cache-dir -r requirements-report.txt
COPY alembic.ini ./
COPY api ./api
COPY src/experiment.py ./src/experiment.py
RUN groupadd --system foodsave && useradd --system --gid foodsave foodsave \
    && mkdir -p /app/storage && chown -R foodsave:foodsave /app/storage
USER foodsave
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000"]
