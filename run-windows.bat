@echo off
setlocal

REM ============================================
REM Directorios
REM ============================================
set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"

echo.
echo ROOT_DIR     = %ROOT_DIR%
echo BACKEND_DIR  = %BACKEND_DIR%
echo FRONTEND_DIR = %FRONTEND_DIR%
echo.

REM ============================================
REM Verificar Python
REM ============================================
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en el PATH.
    pause
    exit /b 1
)

REM ============================================
REM Verificar npm
REM ============================================
where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm no esta instalado o no esta en el PATH.
    pause
    exit /b 1
)

REM ============================================
REM Crear entorno virtual
REM ============================================
if not exist "%BACKEND_DIR%\.venv" (
    echo Creando entorno virtual...
    python -m venv "%BACKEND_DIR%\.venv"
)

REM ============================================
REM Instalar dependencias backend
REM ============================================
if not exist "%BACKEND_DIR%\.venv\.deps-installed" (
    echo Instalando dependencias del backend...
    call "%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -r "%BACKEND_DIR%\requirements.txt"

    if errorlevel 1 (
        echo Error instalando dependencias del backend.
        pause
        exit /b 1
    )

    type nul > "%BACKEND_DIR%\.venv\.deps-installed"
)

REM ============================================
REM Instalar dependencias frontend
REM ============================================
if not exist "%FRONTEND_DIR%\node_modules" (
    echo Instalando dependencias del frontend...

    pushd "%FRONTEND_DIR%"
    call npm install

    if errorlevel 1 (
        popd
        echo Error instalando dependencias del frontend.
        pause
        exit /b 1
    )

    popd
)

REM ============================================
REM Levantar Backend
REM ============================================
echo.
echo Levantando backend...

pushd "%BACKEND_DIR%"

start "Backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port 8000"

popd

REM ============================================
REM Levantar Frontend
REM ============================================
echo Levantando frontend...

pushd "%FRONTEND_DIR%"

start "Frontend" cmd /k "set VITE_API_BASE_URL=http://localhost:8000&&npm run dev -- --host 0.0.0.0"

popd

echo.
echo ============================================
echo Proyecto iniciado.
echo.
echo Frontend: http://localhost:5173
echo Backend : http://localhost:8000
echo ============================================
echo.

pause