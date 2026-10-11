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

# mihomo sidecar（Clash.Meta 内核）：订阅代理边车，仅容器内回环 7890/9090。
# amd64 默认 compatible 构建（老 CPU 安全，慢可忽略）；要极致性能可换 mihomo-linux-amd64-<ver>.gz
ARG MIHOMO_VERSION=v1.19.32
RUN set -eux; arch="$(uname -m)"; \
    case "$arch" in \
      x86_64) a=amd64-compatible ;; \
      aarch64) a=arm64 ;; \
      *) echo "unsupported arch: $arch" && exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/mihomo.gz \
      "https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VERSION}/mihomo-linux-${a}-${MIHOMO_VERSION}.gz"; \
    gzip -d -c /tmp/mihomo.gz > /usr/local/bin/mihomo; \
    chmod +x /usr/local/bin/mihomo; rm -f /tmp/mihomo.gz; \
    /usr/local/bin/mihomo -v

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend /app/dist /usr/share/nginx/html

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend/src
RUN uv sync --no-dev --frozen

# Chromium for Playwright. --with-deps pulls in the runtime shared libs
# (libnss3, libatk, libxcomposite, etc.) the headless shell needs.
RUN uv run --no-dev playwright install --with-deps chromium 2>&1 | tail -5

# 用同一份 Python 源生成 mihomo stub 基础配置（supervisord 首启复制到 /data/mihomo）
RUN uv run --no-dev python -c "from rt_backend.proxy.config_builder import write_base_yaml; write_base_yaml('/app/mihomo-base.yaml', stub=True)"

EXPOSE 80

CMD ["sh", "-c", "supervisord -c /etc/supervisord.conf & nginx -g 'daemon off;'"]
