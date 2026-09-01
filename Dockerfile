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

COPY supervisord.conf /etc/supervisord.conf
COPY backend/ /app/backend/

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor ca-certificates curl libatomic1 ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/log /var/run \
    && rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default 2>/dev/null || true

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend /app/dist /usr/share/nginx/html

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend/src
RUN uv sync --no-dev --frozen

# Chromium for Playwright. --with-deps pulls in the runtime shared libs
# (libnss3, libatk, libxcomposite, etc.) the headless shell needs.
RUN uv run --no-dev playwright install --with-deps chromium 2>&1 | tail -5

EXPOSE 80

CMD ["sh", "-c", "supervisord -c /etc/supervisord.conf & nginx -g 'daemon off;'"]
