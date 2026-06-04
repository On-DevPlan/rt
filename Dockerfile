# Stage 1: build the React frontend
FROM node:20-alpine AS frontend

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

# Stage 2: FastAPI backend
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

COPY --from=frontend /app/dist /usr/share/nginx/html
COPY supervisord.conf /etc/supervisord.conf
COPY backend/ /app/backend/

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/log /var/run

COPY nginx.conf /etc/nginx/nginx.conf

WORKDIR /app/backend
RUN uv sync --no-dev --frozen

EXPOSE 80

CMD ["sh", "-c", "supervisord -c /etc/supervisord.conf & nginx -g 'daemon off;'"]
