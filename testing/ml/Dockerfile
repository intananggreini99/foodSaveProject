# Build dari root proyek: docker build -f ml/Dockerfile .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MLFLOW_DISABLE_AGENT_HINT=1
WORKDIR /app
COPY ml/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /opt/shared
RUN pip install --no-cache-dir --no-deps /opt/shared
COPY ml/foodsave_ml ./foodsave_ml
COPY dataset/raw/train.csv ./seed/train.csv
RUN groupadd --system foodsave && useradd --system --gid foodsave --create-home foodsave
USER foodsave
CMD ["python", "-m", "foodsave_ml.pipeline"]
