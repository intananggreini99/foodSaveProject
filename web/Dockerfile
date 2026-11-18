# Frontend FoodSave (Next.js) di container Linux - rilis lokal (localhost).
# Dijalankan lewat compose (layanan "web"), sehingga tidak terkena kebijakan Windows
# (Smart App Control/WDAC) yang memblokir biner native Next.js di laptop.
FROM node:22-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Alamat layanan lokal yang dibuka browser; ditanam saat build (lihat compose.yaml).
ARG NEXT_PUBLIC_API_URL=http://localhost:8010
ARG NEXT_PUBLIC_MLFLOW_URL=http://localhost:5010
ARG NEXT_PUBLIC_HDFS_URL=http://localhost:9871
ARG NEXT_PUBLIC_MAILPIT_URL=http://localhost:8026
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_MLFLOW_URL=$NEXT_PUBLIC_MLFLOW_URL \
    NEXT_PUBLIC_HDFS_URL=$NEXT_PUBLIC_HDFS_URL NEXT_PUBLIC_MAILPIT_URL=$NEXT_PUBLIC_MAILPIT_URL
RUN npm run build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/package.json /app/package-lock.json /app/next.config.ts ./
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/.next ./.next
USER node
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "-p", "3000", "-H", "0.0.0.0"]
