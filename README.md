# Local LLM Interface - Phase 1

Esta fase inicial crea la arquitectura base de un cliente web React + backend FastAPI con SQLite.

## Qué incluye
- Estructura modular separando frontend/backend de forma fácil
- React + Vite + TypeScript + TailwindCSS
- FastAPI con JWT / SQLite / SQLAlchemy
- Docker Compose para levantar frontend y backend
- Esqueleto de autenticación y rutas protegidas en FastAPI
- Abstracción de proveedores en frontend lista para extender
- Sistema de gestión de usuarios con roles (admin/user)
- Exportación e importación de usuarios en Docker

## Ejecutar
- `docker compose up -d`
- Frontend en `http://localhost:5173`
- Backend en `http://localhost:8000`

### Usuario admin por defecto
- Email: `admin@local`
- Contraseña: `admin`

Este usuario se crea automáticamente en el primer inicio.

## Gestión de usuarios

### Crear usuarios desde el panel de Ajustes
1. Inicia sesión como administrador
2. Ve a Ajustes → Gestión de usuarios
3. Completa el formulario con:
   - Email del nuevo usuario
   - Contraseña
   - Rol: Usuario normal o Administrador
4. Haz clic en "Crear usuario"

### Exportación e importación de usuarios en Docker
Los usuarios se exportan automáticamente a `./backend/export/users.json` cuando se inicia el contenedor.

**Exportar usuarios manualmente:**
```bash
docker exec -it local_ia-backend-1 python -m app.db.export_users export /app/export/users.json
```

**Importar usuarios:**
```bash
docker exec -it local_ia-backend-1 python -m app.db.export_users import /app/export/users.json
```

**Copiar archivo de usuarios a tu máquina:**
```bash
docker cp local_ia-backend-1:/app/export/users.json ./backend/export/users.json
```

### Roles de usuario
- **Usuario normal**: Acceso a chat y preferencias personales
- **Administrador**: Acceso a gestión de usuarios + chat y preferencias

## Pruebas
- `docker compose config` para validar la configuración de Compose
- `npm install` en `frontend` y `python3 -m pip install -r backend/requirements.txt` para validar dependencias

## Próxima fase
- Implementar sistema de diseño y layout principal del chat.
