#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 no esta instalado o no esta en el PATH."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm no esta instalado o no esta en el PATH."
  exit 1
fi

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  echo "Creando entorno virtual de Python..."
  python3 -m venv "$BACKEND_DIR/.venv"
fi

if [[ ! -f "$BACKEND_DIR/.venv/.deps-installed" || "$BACKEND_DIR/requirements.txt" -nt "$BACKEND_DIR/.venv/.deps-installed" ]]; then
  echo "Instalando dependencias del backend..."
  "$BACKEND_DIR/.venv/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
  touch "$BACKEND_DIR/.venv/.deps-installed"
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Instalando dependencias del frontend..."
  (cd "$FRONTEND_DIR" && npm install)
fi

echo "Levantando backend en http://localhost:8000..."
(
  cd "$BACKEND_DIR"
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!

echo "Levantando frontend en http://localhost:5173..."
(
  cd "$FRONTEND_DIR"
  VITE_API_BASE_URL=http://localhost:8000 npm run dev -- --host 0.0.0.0
) &
FRONTEND_PID=$!

echo
echo "Proyecto local ejecutandose:"
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000"
echo
echo "Presiona Ctrl+C para detener ambos procesos."

wait "$BACKEND_PID" "$FRONTEND_PID"
