# ---------------------------------------------------------------------------
# Cambios que debes hacer en settings.py de tu proyecto
# ---------------------------------------------------------------------------

# 1) Apps instaladas (agrega las dos apps del proyecto si no están):
INSTALLED_APPS = [
    # ... las de Django (admin, auth, contenttypes, sessions, messages, staticfiles) ...
    'dashboard',
    'login',
]

# 2) Plantillas: agrega el context processor que entrega nombre, rol y permisos
#    del usuario a todas las pantallas (barra superior y menú).
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
                'dashboard.context_processors.sgr',   # <-- NUEVO
            ],
        },
    },
]

# 3) Sesión e idioma
LOGIN_URL = 'login'            # a dónde manda @login_required si no hay sesión
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_TZ = True

# 4) Estáticos (ya lo tenías)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# 5) Correo para el código de "olvidé mi contraseña".
# Para DESARROLLO: imprime el correo (con el código) en la terminal del servidor.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'no-reply@sgrmunicipal.cl'

# Para PRODUCCIÓN, reemplaza por SMTP real (credenciales en variables de entorno,
# nunca escritas en el repositorio):
#
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.tudominio.cl'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'no-reply@sgrmunicipal.cl'
# EMAIL_HOST_PASSWORD = '...'

# 6) urls.py del proyecto: ya debería incluir ambas apps, por ejemplo:
#    path('', include('login.urls')),
#    path('dashboard/', include('dashboard.urls')),
