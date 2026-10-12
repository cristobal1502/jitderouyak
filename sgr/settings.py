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
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


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
    'dashboard',
    'login',
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

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'

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