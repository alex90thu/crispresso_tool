#!/usr/bin/env bash
set -euo pipefail

# Run Streamlit UI for CRISPResso and a background HTTP server for results.
# Usage: ./run.sh [--port 8501] [--address 0.0.0.0]

# --- Config ---
STREAMLIT_PORT="8504"
PORTAL_PORT="8505"  # 结果门户的端口
ADDR="0.0.0.0"
DATA_DIR="/data/lulab_commonspace/guozehua/crispresso_out"
PORTAL_LOG="portal_server.log"
STREAMLIT_LOG="streamlit_app.log"
CONDA_ENV="crispresso-env"

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      STREAMLIT_PORT="$2"; shift 2 ;;
    --address)
      ADDR="$2"; shift 2 ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1 ;;
  esac
done

# Ensure we are in the project root
cd "$(dirname "$0")"

# --- Conda Environment ---
if command -v conda >/dev/null 2>&1; then
  eval "$(conda shell.bash hook)"
  conda activate "$CONDA_ENV"
else
  echo "conda not found; please ensure it is installed and available" >&2
  exit 1
fi

# --- 1. Start the Result Portal Server (Background) ---
echo "Starting Result Portal Server on port ${PORTAL_PORT}..."

# 检查目标目录是否存在，不存在则创建
if [ ! -d "$DATA_DIR" ]; then
    echo "Creating data directory: $DATA_DIR"
    mkdir -p "$DATA_DIR"
fi

# 检查端口是否被占用 (简单的 lsof 检查，可选)
if lsof -Pi :$PORTAL_PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "Warning: Port $PORTAL_PORT is already in use. Assuming portal is running."
else
    # 启动 python http.server，指定目录为 DATA_DIR
    # 使用 nohup 放入后台
    nohup python3 -m http.server "$PORTAL_PORT" --directory "$DATA_DIR" > "$PORTAL_LOG" 2>&1 &
    PORTAL_PID=$!
    echo "Result Portal running at http://${ADDR}:${PORTAL_PORT}/ (PID: $PORTAL_PID)"
fi

# --- 2. Start Streamlit App (Background) ---
echo "Starting Streamlit App on port ${STREAMLIT_PORT} (background)..."

nohup streamlit run streamlit_app.py --server.port "$STREAMLIT_PORT" --server.address "$ADDR" > "$STREAMLIT_LOG" 2>&1 &
STREAMLIT_PID=$!
echo "Streamlit App running at http://${ADDR}:${STREAMLIT_PORT}/ (PID: $STREAMLIT_PID)"