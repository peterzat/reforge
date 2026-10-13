#!/usr/bin/env bash
# Start or stop the local vision-language model used as an evaluation
# instrument (reforge/evaluate/vlm.py, docs/cv-instruments.md).
#
#   scripts/vlm_server.sh start     # serve on 127.0.0.1:8100, ~14 GB VRAM
#   scripts/vlm_server.sh stop
#   scripts/vlm_server.sh status
#
# Needs a vLLM install (REFORGE_VLLM_BIN; defaults to the daydream checkout's
# venv when present). The GPU is shared: check nvidia-smi first, and never
# stop another project's server to make room.
set -euo pipefail

VLLM_BIN="${REFORGE_VLLM_BIN:-$HOME/src/daydream/external/vLLM/.venv/bin/vllm}"
MODEL="${REFORGE_VLM_HF_MODEL:-cyankiwi/Qwen3.5-9B-AWQ-4bit}"
REVISION="${REFORGE_VLM_REVISION:-156edc4bbeb8d1910ee7be9196bafaf1bc052156}"
PORT="${REFORGE_VLM_PORT:-8100}"
GPU_FRACTION="${REFORGE_VLM_GPU_FRACTION:-0.80}"
LOG="${REFORGE_VLM_LOG:-/tmp/reforge-vlm.log}"
# Any vLLM server on our port, whatever model it serves.
PATTERN="vllm serve .*--port $PORT"
serving() {  # the model the server on $PORT reports, or empty
  curl -s -m 2 "http://127.0.0.1:$PORT/v1/models" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"][0]["root"])' 2>/dev/null || true
}

case "${1:-status}" in
  start)
    current="$(serving)"
    if [ "$current" = "$MODEL" ]; then echo "already serving $MODEL"; exit 0; fi
    if [ -n "$current" ] || pgrep -f "$PATTERN" >/dev/null; then
      echo "port $PORT is busy (serving: ${current:-starting}); run $0 stop first" >&2; exit 1
    fi
    [ -x "$VLLM_BIN" ] || { echo "vLLM not found at $VLLM_BIN (set REFORGE_VLLM_BIN)" >&2; exit 2; }
    VENV_BIN="$(dirname "$VLLM_BIN")"
    # Loopback-only internal sockets and FlashInfer's ninja on PATH (same
    # settings daydream uses for its server).
    PATH="$VENV_BIN:$PATH" VLLM_LOGGING_LEVEL=WARNING VLLM_HOST_IP=127.0.0.1 \
    GLOO_SOCKET_IFNAME=lo NCCL_SOCKET_IFNAME=lo \
    setsid nohup "$VLLM_BIN" serve "$MODEL" --revision "$REVISION" \
        --host 127.0.0.1 --port "$PORT" \
        --gpu-memory-utilization "$GPU_FRACTION" --max-model-len 16384 --max-num-seqs 4 \
        --limit-mm-per-prompt '{"image": 2}' \
        --default-chat-template-kwargs '{"enable_thinking": false}' \
        --served-model-name qwen-vl > "$LOG" 2>&1 < /dev/null &
    for _ in $(seq 1 90); do
      if [ "$(serving)" = "$MODEL" ]; then echo "ready on :$PORT serving $MODEL (log $LOG)"; exit 0; fi
      pgrep -f "$PATTERN" >/dev/null || { echo "server exited; see $LOG" >&2; exit 1; }
      sleep 2
    done
    echo "not ready after 180s; see $LOG" >&2; exit 1 ;;
  stop)
    if pkill -f "$PATTERN"; then
      for _ in $(seq 1 30); do pgrep -f "$PATTERN" >/dev/null || break; sleep 1; done
      echo "stopped"
    else
      echo "not running"
    fi ;;
  status)
    current="$(serving)"; [ -n "$current" ] && echo "serving $current on :$PORT" || echo "not running" ;;
  *) echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
