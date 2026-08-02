# Stage 0: build Rapfi engine (AVX2) + fetch NNUE weights
# GPL v3 — fine for self-hosted personal use; redistribute image only with source.
FROM debian:bookworm-slim AS rapfi-build
RUN apt-get update && apt-get install -y --no-install-recommends \
        clang cmake git build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG RAPFI_REF=250615
WORKDIR /src
# Clone pinned Rapfi tag + the rapfi-networks weights repo (avoids flaky
# shallow submodule init). rapfi-networks has no release tags -> default branch.
RUN git clone --depth 1 --branch ${RAPFI_REF} https://github.com/dhbloo/rapfi.git \
    && git clone --depth 1 https://github.com/dhbloo/rapfi-networks.git /src/rapfi/Networks
WORKDIR /src/rapfi/Rapfi
RUN mkdir -p build/avx2 && cd build/avx2 \
    && cmake ../.. \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
        -DCMAKE_BUILD_TYPE=Release \
        -DUSE_SSE=ON -DUSE_AVX2=ON -DUSE_AVX512=OFF -DUSE_BMI2=OFF -DUSE_VNNI=OFF \
    && cmake --build . -j"$(nproc)"
# Assemble engine dir: binary + config + all NNUE/classical weights flat
# (Rapfi auto-loads weights from the directory containing the executable).
# CMake target outputs "pbrain-rapfi" (Gomocup convention, confirmed by CI build log).
# config.toml's `binary_file` references classical/model210901.bin — copy both
# classical models (model220723 too) so the config matches what's on disk.
RUN mkdir -p /out \
    && cp build/avx2/pbrain-rapfi /out/pbrain-Rapfi \
    && chmod +x /out/pbrain-Rapfi \
    && cp /src/rapfi/Networks/config-example/config.toml /out/config.toml \
    && cp /src/rapfi/Networks/mix9svq/*.bin.lz4 /out/ \
    && cp /src/rapfi/Networks/classical/model210901.bin /out/ \
    && cp /src/rapfi/Networks/classical/model220723.bin /out/

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
    nginx supervisor ca-certificates curl libatomic1 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/log /var/run \
    && rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default 2>/dev/null || true

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=rapfi-build /out/ /opt/rapfi/
COPY --from=frontend /app/dist /usr/share/nginx/html

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend/src
RUN uv sync --no-dev --frozen

EXPOSE 80

CMD ["sh", "-c", "supervisord -c /etc/supervisord.conf & nginx -g 'daemon off;'"]
