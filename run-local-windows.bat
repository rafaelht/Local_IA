@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python no esta instalado o no esta en el PATH.
    exit /b 1
  )
  set "PYTHON=python"
) else (
  set "PYTHON=py -3"
)

where npm >nul 2>nul
if errorlevel 1 (
  echo npm no esta instalado o no esta en el PATH.
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo Creando entorno virtual de Python...
  %PYTHON% -m venv backend\.venv
  if errorlevel 1 exit /b 1
)

if not exist "backend\.venv\.deps-installed" (
  echo Instalando dependencias del backend...
  backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  if errorlevel 1 exit /b 1
  type nul > backend\.venv\.deps-installed
)

if not exist "frontend\node_modules" (
  echo Instalando dependencias del frontend...
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    exit /b 1
  )
  popd
)

echo Levantando backend y frontend en ventanas separadas...
start "Local IA Backend" cmd /k "cd /d ""%~dp0backend"" && .venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000"
start "Local IA Frontend" cmd /k "cd /d ""%~dp0frontend"" && set VITE_API_BASE_URL=http://localhost:8000&& npm run dev -- --host 0.0.0.0"

echo.
echo Proyecto local ejecutandose:
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
echo.
echo Cierra las ventanas "Local IA Backend" y "Local IA Frontend" para detenerlo.

endlocal
