# Local LLM Interface - Phase 1

Esta fase inicial crea la arquitectura base de un cliente web React + backend FastAPI con SQLite.

## Qué incluye
- Estructura modular separando frontend/backend
- React + Vite + TypeScript + TailwindCSS
- FastAPI con JWT / SQLite / SQLAlchemy
- Docker Compose para levantar frontend y backend
- Esqueleto de autenticación y rutas protegidas en FastAPI
- Abstracción de proveedores en frontend lista para extender

## Ejecutar
- `docker compose up -d`
- Frontend en `http://localhost:5173`
- Backend en `http://localhost:8000`

## Pruebas
- `docker compose config` para validar la configuración de Compose
- `npm install` en `frontend` y `python3 -m pip install -r backend/requirements.txt` para validar dependencias

## Próxima fase
- Implementar sistema de diseño y layout principal del chat.
