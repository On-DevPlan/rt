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
# Assemble engine dir: binary + config + NNUE weights flat
# (Rapfi auto-loads weights from the directory containing the executable).
# CMake target outputs "pbrain-rapfi" (Gomocup convention, confirmed by CI build log).
#
# The bundled rapfi-networks configs all reference classical binary_file models
# (model210901.bin / model220723.bin) that Rapfi 250615 (ver 0,43,2) rejects
# as an outdated format. The modern Rapfi path is NNUE-only: drop binary_file
# and use the inline eval tables + mix9svq NNUE weights. This config is
# written inline here (rather than copied + sed-patched) so it's the only
# source of truth and the version match is explicit.
RUN mkdir -p /out \
    && cp build/avx2/pbrain-rapfi /out/pbrain-Rapfi \
    && chmod +x /out/pbrain-Rapfi \
    && cp /src/rapfi/Networks/mix9svq/*.bin.lz4 /out/ \
    && cat > /out/config.toml <<'RAPFI_CONFIG'
[requirement]
min_version = [0,43,1]

[general]
reload_config_each_move = false
clear_hash_after_config_loaded = false
default_thread_num = 1
message_mode = "normal"
coord_conversion_mode = "none"
default_candidate_range = "square3_line4"
memory_reserved_mb = 0
default_tt_size_kb = 32768

[model]

[model.evaluator]
type = "mix9svq"
draw_black_winrate = 0.5
draw_ratio = 1.0

[[model.evaluator.weights]]
weight_file = "mix9svqstandard_bs15.bin.lz4"
[[model.evaluator.weights]]
weight_file = "mix9svqfreestyle_bsmix.bin.lz4"
[[model.evaluator.weights]]
weight_file_black = "mix9svqrenju_bs15_black.bin.lz4"
weight_file_white = "mix9svqrenju_bs15_white.bin.lz4"
RAPFI_CONFIG

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
COPY --from=rapfi-build /out/ /opt/rapfi/
COPY --from=frontend /app/dist /usr/share/nginx/html

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend/src
RUN uv sync --no-dev --frozen

EXPOSE 80

CMD ["sh", "-c", "supervisord -c /etc/supervisord.conf & nginx -g 'daemon off;'"]
