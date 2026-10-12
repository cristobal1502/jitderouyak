# SGR Municipal

Sistema de gestión territorial para delegaciones municipales (Django + MySQL). Permite a un gestor territorial registrar actividades, dar seguimiento a compromisos colectivos, gestionar casos sociales con historial de gestiones, y realizar búsquedas avanzadas con reportabilidad.

## Vistas incluidas

- **Login** — ingreso con usuario o correo y contraseña; el acceso y el menú dependen del rol.
- **Recuperar contraseña** — solicitud de código por correo → **Validar código** (vigencia de 5 min, reenvío cada 30 s y 3 intentos, controlados por el servidor) → **Crear nueva contraseña** → retorno al login.
- **Mi panel** — resumen de metas del período e historial de actividades.
- **Agenda colectiva** — tubo de trabajo con filtros y seguimiento de compromisos.
- **Casos sociales** — historial secuencial de atenciones por usuario (hasta 3 gestiones).
- **Ingreso de atención** — solicitante, tipo, sub atención, descripción, delegación, responsable y fecha.
- **Búsqueda avanzada** — filtros transversales, exportación y paginación de resultados.
- **Administración (CRUD)** — Delegaciones, Roles, Usuarios, Ítems y metas, Tipos de atención y Sub atenciones.
- **Configuraciones** — perfil, cambio de contraseña y preferencias de notificación.

## Tecnologías utilizadas

- **Backend:** Django 5.2 (Python), MySQL/MariaDB (phpMyAdmin)
- **Frontend:** HTML5, CSS3 (sin frameworks), JavaScript vanilla
- **Librerías:** [SweetAlert2](https://sweetalert2.github.io/) (popups y validaciones)
- **Tipografía:** Public Sans e IBM Plex Mono (Google Fonts)

> **Qué usa base de datos y qué sigue siendo maqueta**
> - Con base de datos: Login y sesión, recuperación de contraseña, Administración (Delegaciones, Roles, Usuarios, Ítems y metas, Tipos de atención, Sub atenciones), Ingreso de atención y Configuraciones.
> - Aún maqueta (contenido fijo en el HTML/JS): Mi panel, Agenda colectiva, Casos sociales y Búsqueda avanzada.

## Cómo ejecutarlo

1. Clona o descarga el proyecto y entra a la carpeta raíz (donde está `manage.py`).

2. Crea y activa un entorno virtual:
   ```bash
   python -m venv entornito
   entornito\Scripts\activate      # Windows
   source entornito/bin/activate   # macOS / Linux
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Crea la base de datos en MySQL. Con XAMPP/WAMP, inicia MySQL, abre **phpMyAdmin** (`http://localhost/phpmyadmin`), pestaña **SQL**, y ejecuta:
   ```sql
   CREATE DATABASE sgr_municipal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
   Por defecto el proyecto se conecta con usuario `root`, sin contraseña, a `127.0.0.1:3306` (lo normal en XAMPP). Si tu MySQL es distinto, define las variables de entorno `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT` (o edita `sgr/settings.py`). Requiere MariaDB 10.5+ o MySQL 8+.

5. Crea las tablas:
   ```bash
   python manage.py migrate
   ```

6. Carga los datos base (roles, catálogos y un administrador). Con `--demo` agrega además usuarios y atenciones de ejemplo. Si ya existía un usuario `admin`, agrega `--reset-admin`:
   ```bash
   python manage.py cargar_datos_iniciales --demo
   ```

7. Levanta el servidor:
   ```bash
   python manage.py runserver
   ```

8. Abre `http://127.0.0.1:8000/` e ingresa con:
   | Usuario | Contraseña | Rol |
   |---|---|---|
   | `admin` | `Admin123!` | Administrador (ve todo) |
   | `juan.perez` | `Demo1234!` | Funcionario (alcance propio, sin Administración) |
   | `maria.rojas` | `Demo1234!` | Delegado / Jefatura |

   Todos los usuarios demo usan `Demo1234!`. **Cambia la contraseña del administrador** antes de usarlo fuera de pruebas.

## Si ya tienes otro proyecto Django

Este paquete ya es un proyecto completo y ejecutable (`manage.py` + carpeta `sgr/`). Si prefieres integrarlo a un proyecto existente, copia `dashboard/`, `login/`, `templates/` y `static/` a su raíz y aplica `settings_snippet.py`. Los diagramas de requerimientos están en `docs/`.

## Roles, permisos y alcance

Cada rol tiene una lista de **permisos** y un **alcance**:

- **Gestionar usuarios** → pantallas Roles y Usuarios.
- **Administrar catálogos** → Delegaciones, Ítems y metas, Tipos de atención y Sub atenciones.
- **Registrar actividades** → puede registrar atenciones.
- **Alcance:** *Propio* (solo lo suyo), *Delegación* (las delegaciones asignadas) o *Todas las delegaciones*. Define qué atenciones ve y a qué delegaciones puede registrar.

El menú oculta lo que el rol no puede usar y el servidor lo vuelve a comprobar en cada petición. Protecciones incluidas: nadie puede eliminarse, desactivarse ni quitarse el permiso *Gestionar usuarios*; no se eliminan registros que otros usan (se sugiere pasarlos a Inactivo).

Al crear un usuario el sistema genera una **contraseña temporal** (se muestra una vez y se envía al correo). Con el botón *Clave* de la tabla de usuarios el administrador puede restablecerla.

En desarrollo los correos (incluido el código de recuperación) se **imprimen en la terminal** donde corre `runserver`.

## Pruebas automáticas

```bash
python manage.py test dashboard login
```

Cubren login, bloqueo por intentos, recuperación de contraseña, permisos por rol, CRUD, reglas de negocio y atenciones.

## Estructura relevante

```
dashboard/                      (app)
├── models.py                   Delegacion, Rol, Perfil, ItemMeta, TipoAtencion, SubAtencion, Atencion
├── api.py                      API JSON que usa el front (CRUD, atenciones, perfil)
├── permisos.py                 permisos y alcance según el rol
├── context_processors.py       nombre/rol/permisos disponibles en las plantillas
├── views.py · urls.py · admin.py · tests.py
└── management/commands/cargar_datos_iniciales.py
login/                          (app)
├── models.py                   CodigoRecuperacion
├── views.py · urls.py · utils.py · tests.py
templates/
├── dashboard/  dashboard, agenda, casos_sociales, ingreso_atencion, busqueda,
│               crud (una plantilla para los 6 mantenedores), configuraciones
└── login/      login, forgot_password, validar_codigo, reset_password
static/
├── css/        styles.css (dashboard y administración), login.css
└── js/         api.js (cliente fetch), crud.js (motor de los 6 CRUD), ingreso_atencion.js,
                configuraciones.js, login.js, forgot_password.js, validar_codigo.js,
                reset_password.js, script.js, agenda.js, casos-sociales.js, busqueda.js
```

> La base de datos vive en MySQL (se consulta en phpMyAdmin). Tablas principales: `dashboard_delegacion`, `dashboard_rol`, `dashboard_perfil`, `dashboard_itemmeta`, `dashboard_tipoatencion`, `dashboard_subatencion`, `dashboard_atencion`, `auth_user`, `login_codigorecuperacion`.
