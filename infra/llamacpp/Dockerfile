FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS build
ARG LLAMA_TAG=b9222
ARG CUDA_ARCH=86
RUN apt-get update \
    && apt-get install -y --no-install-recommends git cmake build-essential libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${LLAMA_TAG} https://github.com/ggml-org/llama.cpp /src
WORKDIR /src
RUN cmake -B build \
      -DGGML_CUDA=ON \
      -DLLAMA_CURL=ON \
      -DCMAKE_CUDA_ARCHITECTURES=${CUDA_ARCH} \
    && cmake --build build -j --target llama-server

FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libcurl4 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/build/bin/llama-server /usr/local/bin/llama-server
COPY infra/llamacpp/run-generation.sh \
     infra/llamacpp/run-embeddings.sh \
     infra/llamacpp/run-rerank.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/run-*.sh
