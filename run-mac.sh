#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker no esta instalado o no esta en el PATH."
  echo "Instala Docker Desktop y vuelve a ejecutar este script."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose no esta disponible."
  echo "Instala Docker Desktop o el plugin docker compose."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker no esta ejecutandose."
  echo "Abre Docker Desktop y vuelve a ejecutar este script."
  exit 1
fi

echo "Construyendo y levantando Local IA..."
"${COMPOSE[@]}" up -d --build --remove-orphans --renew-anon-volumes

echo
echo "Proyecto ejecutandose:"
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000"
echo
echo "Para ver logs:    ${COMPOSE[*]} logs -f"
echo "Para detenerlo:   ${COMPOSE[*]} down"
