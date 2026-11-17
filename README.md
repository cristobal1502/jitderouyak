# SGR Municipal

Sistema de gestión territorial para delegaciones municipales (Django + MySQL). Permite a un gestor territorial registrar actividades con el puntaje de la Matriz SGR, dar seguimiento a compromisos colectivos, llevar el registro de organizaciones comunitarias y realizar búsquedas avanzadas con reportabilidad.

## Vistas incluidas

- **Login** — ingreso con usuario o correo y contraseña; el acceso y el menú dependen del rol.
- **Selector de delegación** — el botón «Delegación …» de la barra superior despliega las delegaciones del usuario (y «Todas»). La elección se guarda en la sesión: el panel muestra solo esa delegación y la búsqueda, la matriz, el ingreso y organizaciones parten con ella seleccionada. Solo aparece si el usuario tiene más de una delegación.
- **Validación mientras se escribe** — RUT (se formatea solo y revisa el dígito verificador), teléfono, correo, nombres, textos mínimos y contraseña muestran el error bajo cada campo al escribir. El servidor vuelve a validar todo.
- **Menú lateral contraíble** — un botón en la barra superior lo reduce a solo íconos (el nombre aparece al pasar el mouse); la preferencia se recuerda en el navegador.
- **Recuperar contraseña** — solicitud de código por correo → **Validar código** (vigencia de 5 min, reenvío cada 30 s y 3 intentos, controlados por el servidor) → **Crear nueva contraseña** → retorno al login.
- **Mi panel** — resumen de metas del período e historial de actividades.
- **Agenda colectiva (tubo de trabajo)** — toda atención ingresada entra al tubo y avanza por etapas: Ingresado → Pendiente → En proceso → Realizado (las que pasan su plazo sin realizarse aparecen como Vencidas). Dos vistas: lista (con selector de etapa por fila) y tablero por columnas, donde las tarjetas se arrastran. Llevar una actividad a «Realizado» la marca como ejecutada y suma su punto.
- **Ingreso de atención** — vecino(a), RUT (opcional), teléfono, si es para una persona natural o una organización, plazo del compromiso, tipo, sub atención, descripción, delegación, responsable y fecha. Reglas de la Matriz SGR:
  - Nombre y teléfono del vecino(a) son obligatorios (sin ellos no se guarda ni suma puntaje).
  - Si el solicitante es el propio Delegado, se guarda como «Otra gestión» y no como atención ciudadana (se marca a mano o se detecta por el nombre).
  - Máximo 7 actividades por funcionario en un mismo día.
  - Cierre semanal: lo de una semana se puede ingresar hasta el lunes siguiente; desde el martes queda cerrada.
  - Cada actividad lleva un ítem de la matriz y un estado: «En preparación» (correos, coordinar, invitar: no suma) o «Ejecutada» (suma 1 punto). Las de preparación se marcan después como ejecutadas.
  - Tope de 120%: cuando un ítem llega al 120% de la meta del trimestre deja de sumar y se avisa cuáles ítems están más bajos.
  - Al escribir el RUT, si la persona es dirigente de alguna organización, se ofrece asociar la atención a esa organización (y se completa el nombre).
- **Matriz SGR (vista de equipo)** — visor por trimestre (Q1 ene-mar … Q4 oct-dic). Avance grupal de la delegación por ítem y por funcionario, con semáforo (≥100% verde, 70–99% amarillo, <70% rojo) y medida de equilibrio. La meta trimestral de cada ítem se define en Ítems y metas y se rebaja en proporción a los días hábiles de ausencia. Lo logrado por sobre el 100% de un ítem al cerrar el trimestre pasa como sobrante al trimestre siguiente, en el mismo ítem y para la misma persona. Solo el Delegado registra ausencias (vacaciones, licencias, días libres) y felicitaciones, estas últimas con respaldo formal obligatorio.
- **Organizaciones** — registro de juntas de vecinos y organizaciones funcionales, con su directiva (presidente, tesorero y secretario, cada uno con nombre y RUT válido; los tres RUT deben ser distintos) (subfamilias: Adulto Mayor, Deportivas, Centros de Madres/Culturales/Juveniles, Comités), con estado «Verificado / Pendiente de revisión». Todos lo consultan; lo editan quienes tienen «Administrar catálogos» o «Gestionar organizaciones».
- **Búsqueda avanzada** — filtros sobre las atenciones (delegación, período, funcionario, tipo, sub atención, fechas y palabras clave), paginación en el servidor y exportación a Excel (.xlsx) y PDF (vista imprimible). Respeta el alcance del rol; exportar requiere el permiso «Exportar informes».
- **Administración (CRUD)** — Delegaciones, Roles, Usuarios, Ítems y metas, Tipos de atención y Sub atenciones.
- **Configuraciones** — perfil, cambio de contraseña y preferencias de notificación.

## Perfiles de cargo (roles)

Los 7 cargos de una delegación vienen creados como roles (se crean solos al correr `migrate`). Sus permisos y alcance se pueden ajustar en Administración → Roles.

| Cargo | Funciones | Permisos principales | Alcance |
|---|---|---|---|
| Delegado | Representante del alcalde en el territorio; dirige al equipo. Único que registra ausencias y felicitaciones. | Registrar, validar, agenda, organizaciones, exportar | Delegación |
| Gestor Social (Trabajador Social) | Atención de personas vulnerables, visitas a domicilio y derivaciones. | Registrar | Propio |
| Apoyo Administrativo | Atención en oficina, agenda del delegado, registro en la planilla SGR. | Registrar, agenda | Delegación |
| Organizaciones Comunitarias | Crea, legaliza y capacita a JJVV y agrupaciones; mantiene su registro. | Registrar, organizaciones | Delegación |
| Gestor de Compras y Proyectos | Compras de materiales y contratación de servicios. | Registrar | Propio |
| Gestión y Planificación | Revisa metas, analiza puntajes de la matriz, informes y reuniones semanales. | Registrar, agenda, exportar | Delegación |
| Coordinador de Servicios Comunitarios | Operativos de limpieza, desmalezado y reciclaje; supervisa cuadrillas. | Registrar, agenda | Delegación |

El permiso nuevo «Gestionar organizaciones» permite editar el registro de organizaciones sin acceso a los demás catálogos. Los roles anteriores (Delegado / Jefatura, Funcionario, etc.) se mantienen para no afectar a los usuarios que ya los tienen.

## Tecnologías utilizadas

- **Backend:** Django 5.2 (Python), MySQL/MariaDB (phpMyAdmin)
- **Frontend:** HTML5, CSS3 (sin frameworks), JavaScript vanilla
- **Librerías:** [SweetAlert2](https://sweetalert2.github.io/) (popups y validaciones), [openpyxl](https://openpyxl.readthedocs.io/) (exportación a Excel)
- **Tipografía:** Public Sans e IBM Plex Mono (Google Fonts)

> **Qué usa base de datos y qué sigue siendo maqueta**
> - Con base de datos: Login y sesión, recuperación de contraseña, Administración (Delegaciones, Roles, Usuarios, Ítems y metas, Tipos de atención, Sub atenciones), Ingreso de atención, Búsqueda avanzada, Organizaciones y Configuraciones.
> - Casos sociales se retiró de la aplicación (pantalla y API). Sus tablas `dashboard_casosocial` y `dashboard_gestionsocial` se conservan en la base para no perder datos.

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

3b. Copia `.env.example` como `.env` y completa tus datos (base de datos y correo). Si no creas `.env`, se usan los valores por defecto.

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

## Despliegue en AWS (EC2 con IP elástica)

La IP **no está escrita en el código**: se configura en el archivo `.env` del servidor.

1. En el servidor clona el repositorio, crea el entorno virtual e instala `pip install -r requirements.txt`.
2. Crea `.env` (copia de `.env.example`) con, como mínimo:
   ```
   SECRET_KEY=<clave larga y aleatoria>
   DEBUG=False
   ALLOWED_HOSTS=<IP elástica>,<dominio si tienes>
   CSRF_TRUSTED_ORIGINS=http://<IP elástica>      # https://<dominio> si usas HTTPS
   DB_NAME=...  DB_USER=...  DB_PASSWORD=...  DB_HOST=<localhost o endpoint de RDS>
   EMAIL_HOST_USER=...  EMAIL_HOST_PASSWORD=...
   ```
3. Crea la base de datos MySQL/MariaDB (local en la EC2 o en RDS) y ejecuta:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py cargar_datos_iniciales --admin-password "<clave segura>"
   ```
4. Ejecuta con gunicorn (idealmente detrás de nginx): `gunicorn sgr.wsgi:application --bind 0.0.0.0:8000`.
5. En el **Security Group** de la EC2 abre el puerto 80/443 (o 8000 si pruebas sin nginx) y el 22 solo para tu IP. El puerto 3306 de MySQL **no** debe quedar abierto a internet.

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
├── dashboard/  dashboard, agenda, ingreso_atencion, busqueda, busqueda_imprimir, matriz,
│               crud (mantenedores y organizaciones), configuraciones
└── login/      login, forgot_password, validar_codigo, reset_password
static/
├── css/        styles.css (dashboard y administración), login.css
└── js/         api.js (cliente fetch), crud.js (motor de los 6 CRUD), ingreso_atencion.js,
                configuraciones.js, login.js, forgot_password.js, validar_codigo.js,
                reset_password.js, script.js, agenda.js, busqueda.js, matriz.js,
                layout.js (menú contraíble y selector de delegación),
                validacion.js (validación en vivo de RUT, teléfono, correo…)
```

> La base de datos vive en MySQL (se consulta en phpMyAdmin). Tablas principales: `dashboard_delegacion`, `dashboard_rol`, `dashboard_perfil`, `dashboard_itemmeta`, `dashboard_tipoatencion`, `dashboard_subatencion`, `dashboard_atencion`, `auth_user`, `login_codigorecuperacion`.

## Evaluación Sumativa #3 — resumen de cumplimiento

**Dashboards por perfil** (`/dashboard/`, datos reales de la BD según permisos y alcance del rol):
- *Administrador* (permiso "Gestionar usuarios"): usuarios, delegaciones, todos los mantenedores, distribución por rol/delegación/tipo.
- *Supervisor* (permisos intermedios): indicadores de sus delegaciones, mantenedores autorizados, equipo.
- *Administrativo* (solo registra): sus propias atenciones, puntos del mes y actividades en preparación; administración restringida (403).

**Transacciones**: (1) Registro de atenciones (`/api/atenciones/`): código correlativo y puntaje se calculan y guardan dentro de un `transaction.atomic()`, con reintento si dos personas toman el mismo código. (2) Marcar una actividad como ejecutada (`/api/atenciones/<id>/ejecutar/`): bloquea la fila con `select_for_update()` mientras recalcula el puntaje y el tope de 120%.

**Usuarios demo** (clave `Demo1234!`): laura.mena (Supervisor), diego.vera (Administrativo), juan.perez / carla.tapia (Funcionario). Admin: `admin` / `Admin123!`.

**Actualizar el servidor**: `git pull && source entornito/bin/activate && python manage.py migrate && python manage.py cargar_datos_iniciales --demo && python manage.py collectstatic --noinput && sudo systemctl restart sgr`
