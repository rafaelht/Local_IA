@echo off
setlocal

cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker no esta instalado o no esta en el PATH.
  echo Instala Docker Desktop y vuelve a ejecutar este script.
  exit /b 1
)

docker compose version >nul 2>nul
if errorlevel 1 (
  where docker-compose >nul 2>nul
  if errorlevel 1 (
    echo Docker Compose no esta disponible.
    echo Instala Docker Desktop o el plugin docker compose.
    exit /b 1
  )
  set "COMPOSE=docker-compose"
) else (
  set "COMPOSE=docker compose"
)

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker no esta ejecutandose.
  echo Abre Docker Desktop y vuelve a ejecutar este script.
  exit /b 1
)

echo Construyendo y levantando Local IA...
%COMPOSE% up -d --build --remove-orphans --renew-anon-volumes
if errorlevel 1 exit /b 1

echo.
echo Proyecto ejecutandose:
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
echo.
echo Para ver logs:  %COMPOSE% logs -f
echo Para detenerlo: %COMPOSE% down

endlocal
