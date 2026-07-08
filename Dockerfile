FROM runpod/worker-comfyui:fix-dr-1170-ngc-base-blackwell-base-cuda12.8.1

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_PREFER_BINARY=1
ENV UV_LINK_MODE=copy
ENV ACESTEP_HOME=/opt/ACE-Step-1.5
ENV ACESTEP_API_HOST=127.0.0.1
ENV ACESTEP_API_PORT=8001
ENV ACESTEP_CONFIG_PATH=acestep-v15-xl-sft
ENV ACESTEP_LM_MODEL_PATH=acestep-5Hz-lm-4B
ENV ACESTEP_LM_BACKEND=vllm
ENV ACESTEP_INIT_LLM=true
ENV ACESTEP_DOWNLOAD_SOURCE=huggingface
ENV ACESTEP_CHECKPOINTS_DIR=/runpod-volume/ace-step-models
ENV ACESTEP_OUTPUT_FORMAT=wav
ENV ACESTEP_DEFAULT_DURATION_SECONDS=60
ENV ACESTEP_DEFAULT_INFERENCE_STEPS=64
ENV ACESTEP_DEFAULT_GUIDANCE_SCALE=7.0
ENV ACESTEP_DEFAULT_BATCH_SIZE=1
ENV ACESTEP_DEFAULT_THINKING=true

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates curl git && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir runpod requests soundfile && \
    curl -LsSf https://astral.sh/uv/install.sh | sh

RUN git clone --depth 1 https://github.com/ACE-Step/ACE-Step-1.5.git ${ACESTEP_HOME}

WORKDIR ${ACESTEP_HOME}
RUN /root/.local/bin/uv sync

WORKDIR /worker
COPY handler.py /worker/handler.py
COPY scripts/start-ace-step-worker.sh /usr/local/bin/start-ace-step-worker.sh
RUN chmod +x /usr/local/bin/start-ace-step-worker.sh

CMD ["/usr/local/bin/start-ace-step-worker.sh"]
