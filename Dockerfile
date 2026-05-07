FROM node:20-alpine AS build

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

FROM python:3.11-alpine

RUN apk add --no-cache nginx supervisor

RUN pip install --no-cache-dir edge-tts aiohttp

WORKDIR /app
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
COPY tts/ /app/tts/

RUN mkdir -p /var/log /var/run && \
    chown -R nginx:nginx /var/log /var/run

EXPOSE 80

CMD ["sh", "-c", "supervisord -c /app/tts/supervisord.conf & nginx -g 'daemon off;'"]
