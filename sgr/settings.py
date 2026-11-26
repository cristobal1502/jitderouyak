"""Configuración del proyecto SGR Municipal (desarrollo)."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

import os


def _cargar_env(ruta):
    """Lee un archivo .env (CLAVE=valor, una por línea) y lo carga en las variables de entorno.
    Las variables ya definidas en el sistema tienen prioridad sobre el archivo."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding='utf-8-sig').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or '=' not in linea:
            continue
        clave, _, valor = linea.partition('=')
        valor = valor.strip()
        if valor[:1] in ('"', "'"):
            valor = valor[1:].split(valor[0], 1)[0]  # entre comillas: se respeta tal cual
        else:
            valor = valor.split(' #', 1)[0].split('\t#', 1)[0].strip()  # quita comentario al final
        os.environ.setdefault(clave.strip(), valor)


_cargar_env(BASE_DIR / '.env')

# En producción define SECRET_KEY propia y DEBUG=False en el archivo .env.
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-sgr-municipal-cambia-esto-en-produccion')
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('1', 'true', 'yes', 'si')
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',  # lista negra de refresh (rotación y logout)
    'drf_spectacular',
    'dashboard',
    'login',
    'sgrApi',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Con HTTPS o dominio detrás de un proxy (nginx, balanceador) agrega el origen, p. ej.:
# CSRF_TRUSTED_ORIGINS=https://mi-dominio.cl,http://54.12.34.56
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]

# WhiteNoise sirve los archivos estáticos con DEBUG=False (si está instalado, ver requirements.txt).
try:
    import whitenoise  # noqa: F401
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass

ROOT_URLCONF = 'sgr.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dashboard.context_processors.sgr',
            ],
        },
    },
]

WSGI_APPLICATION = 'sgr.wsgi.application'

# Base de datos: MySQL/MariaDB (se administra con phpMyAdmin). Valores por defecto de XAMPP/WAMP.
# Puedes cambiarlos con variables de entorno: DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT.
# Para usar un archivo SQLite en vez de MySQL: DB_ENGINE=sqlite
if os.environ.get('DB_ENGINE', 'mysql') == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'sgr_municipal'),
            'USER': os.environ.get('DB_USER', 'root'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }

AUTH_PASSWORD_VALIDATORS = []  # las reglas de contraseña las aplica login/utils.py

LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'  # destino de: python manage.py collectstatic

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'

# ---------------------------------------------------------------- API REST (/api/v1/)
from datetime import timedelta  # noqa: E402

REST_FRAMEWORK = {
    # Solo JWT: el front web sigue usando su propia API con sesión en /dashboard/api/.
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    # Cerrado por defecto: toda vista exige token salvo que diga lo contrario (token/, docs/).
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    # Siempre JSON (sin la interfaz navegable de DRF).
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # Límite de solicitudes por minuto (429 al superarlo). "token" protege el login contra fuerza bruta.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('API_THROTTLE_ANON', '30/min'),
        'user': os.environ.get('API_THROTTLE_USER', '300/min'),
        'token': os.environ.get('API_THROTTLE_TOKEN', '10/min'),
    },
    'EXCEPTION_HANDLER': 'sgrApi.excepciones.manejador_excepciones',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # vida corta: si se filtra, sirve poco tiempo
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,        # cada refresh entrega un refresh nuevo...
    'BLACKLIST_AFTER_ROTATION': True,     # ...y el anterior queda inutilizable
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    # Firma con SECRET_KEY (viene del .env, nunca del código en producción).
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'SGR Municipal — API REST',
    'DESCRIPTION': (
        'API RESTful del Sistema de Gestión Territorial Municipal.\n\n'
        '**Cómo probarla:** 1) `POST /api/v1/token/` con usuario y contraseña; '
        '2) copia el valor de `access`; 3) botón **Authorize** y pégalo. El token dura 15 minutos '
        '(renuévalo con `/api/v1/token/refresh/`).\n\n'
        '**Errores:** siempre `{"error": ..., "campo": ..., "detalle": ...}` con 400, 401, 403, 404, 409 o 429.\n\n'
        '**Datos sensibles:** solo el administrador ve RUT y teléfonos de vecinos y de la directiva de '
        'organizaciones; el resto de los roles recibe la vista básica.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,      # esquemas separados para lo que se envía y lo que se recibe
    'SCHEMA_PATH_PREFIX': r'/api/v1',
    'ENUM_NAME_OVERRIDES': {
        'EstadoRegistroEnum': ['Activo', 'Inactivo'],
        'EstadoAtencionEnum': 'dashboard.models.Atencion.ESTADOS',
    },
    'SWAGGER_UI_SETTINGS': {'persistAuthorization': True, 'displayRequestDuration': True},
    'TAGS': [
        {'name': 'Autenticación', 'description': 'Tokens JWT: login, renovación y logout.'},
        {'name': 'Sesión', 'description': 'Datos del usuario del token.'},
        {'name': 'Delegaciones', 'description': 'Persona 1 · mantenedor.'},
        {'name': 'Tipos de atención', 'description': 'Persona 1 · mantenedor.'},
        {'name': 'Atenciones', 'description': 'Persona 1 · transacción.'},
        {'name': 'Ítems y metas', 'description': 'Persona 2 · mantenedor.'},
        {'name': 'Organizaciones comunitarias', 'description': 'Persona 2 · mantenedor.'},
        {'name': 'Reclamos', 'description': 'Persona 2 · transacción.'},
    ],
}

# Correo (código de recuperación y contraseñas temporales).
# Con EMAIL_HOST_PASSWORD definido en .env se envía por SMTP; si no, se imprime en la terminal.
if os.environ.get('EMAIL_HOST_PASSWORD'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD'].replace(' ', '')
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'no-reply@sgrmunicipal.cl'
