"""
Django settings for LottoBooM project.

Configuración corregida, endurecida y lista para producción.
SIN allauth para evitar errores de importación.
"""

import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# ============================================================
# RUTAS BASE
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# SEGURIDAD
# ============================================================
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("DEBUG", "True") == "True":
        SECRET_KEY = "django-insecure-2yuy%z1761p37=66_i8yqqr4-&!9(8#7=$n^r6p*n9r4eltu5h"
    else:
        raise ImproperlyConfigured(
            "La variable de entorno SECRET_KEY es obligatoria en producción."
        )

DEBUG = True   # ⚠️ Cambia a False SOLO cuando el sitio funcione estable

ALLOWED_HOSTS = os.environ.get(
    "ALLOWED_HOSTS",
    "lottoboom.pythonanywhere.com,"
    "www.lottoboom.pythonanywhere.com,"
    "localhost,127.0.0.1,testserver"
).split(",")

# ============================================================
# APLICACIONES INSTALADAS (SIN allauth)
# ============================================================
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",

    # Terceros
    "rest_framework",
    "corsheaders",

    # Locales
    "sorteos",
    "pagos",
    "jugadas",
    "resultados",
    "publico",
    "roles.apps.RolesConfig",
    "banco",
    "comercial",
    "superadmin",
    "ubicaciones",
    "usuarios.apps.UsuariosConfig",
]

# ============================================================
# MIDDLEWARE (orden correcto, sin duplicados)
# ============================================================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',                    # 1) CORS primero
    'django.middleware.security.SecurityMiddleware',            # 2) Seguridad
    'whitenoise.middleware.WhiteNoiseMiddleware',               # 3) Estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',     # 4) Sesión
    'django.middleware.common.CommonMiddleware',                # 5) Common
    'django.middleware.csrf.CsrfViewMiddleware',                # 6) CSRF
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # 7) Auth
    'usuarios.middleware.LastActivityMiddleware',               # 8) Actividad propia
    'roles.middleware.UserActivityMiddleware',                  # 9) Actividad roles
    'publico.middleware.ActualizarUltimaActividadMiddleware',   # 10) Online real
    'django.contrib.messages.middleware.MessageMiddleware',     # 11) Mensajes
    'django.middleware.clickjacking.XFrameOptionsMiddleware',   # 12) Clickjacking
    'publico.middleware.RegistrarVisitaMiddleware',             # 13) Visitas
]

# ============================================================
# URLS Y APLICACIÓN
# ============================================================
ROOT_URLCONF = "LottoBooM.urls"
WSGI_APPLICATION = "LottoBooM.wsgi.application"
ASGI_APPLICATION = "LottoBooM.asgi.application"

# ============================================================
# TEMPLATES
# ============================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "usuarios.context_processors.prestamos_context",
            ],
        },
    },
]

# ============================================================
# BASE DE DATOS
# ============================================================
if os.environ.get("RENDER") or os.environ.get("DATABASE_URL"):
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.config(
            default=os.environ.get("DATABASE_URL"),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {
                "timeout": 60,
            },
            "ATOMIC_REQUESTS": False,
        }
    }

# ============================================================
# CACHE (usado para sesiones)
# ============================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-lottoboom-cache",
        "TIMEOUT": 300,
        "OPTIONS": {
            "MAX_ENTRIES": 5000,
            "CULL_FREQUENCY": 4,
        },
    }
}

# ============================================================
# SESIONES — extendidas (1 año, renovadas en cada request)
# ============================================================
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365        # 365 días
SESSION_SAVE_EVERY_REQUEST = True              # renueva la cookie en cada petición
SESSION_EXPIRE_AT_BROWSER_CLOSE = False        # no expira al cerrar navegador

# Cookies
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_AGE = SESSION_COOKIE_AGE

# Mensajes
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# ============================================================
# VALIDACIÓN DE CONTRASEÑAS
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
]

# ============================================================
# INTERNACIONALIZACIÓN
# ============================================================
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Havana"
USE_I18N = True
USE_TZ = True

DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","
USE_THOUSAND_SEPARATOR = False

# ============================================================
# ARCHIVOS ESTÁTICOS Y MEDIA
# ============================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # ⚠️ CompressedStaticFilesStorage (sin Manifest) — no rompe si falta un estático
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# WhiteNoise: opciones seguras
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

# ============================================================
# MODELOS Y CAMPOS POR DEFECTO
# ============================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# LIMITES DE SUBIDA
# ============================================================
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000      # bajado de 500000 (era un riesgo DoS)
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880

# ============================================================
# AUTENTICACIÓN (SIN allauth)
# ============================================================
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "publico:home"
LOGOUT_REDIRECT_URL = "publico:home"

SITE_ID = 1

# ============================================================
# EMAIL
# ============================================================
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@lottoboom.com")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", "admin@lottoboom.com")

# ============================================================
# CANALES Y EVENTSTREAM
# ============================================================
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

EVENTSTREAM_MAX_EVENTS_PER_CHANNEL = 100
EVENTSTREAM_MAX_EVENT_AGE = 3600

# ============================================================
# SEGURIDAD EN PRODUCCIÓN
# ============================================================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    X_FRAME_OPTIONS = "DENY"

# ============================================================
# PROXY (Render / Producción)
# ============================================================
if os.environ.get("RENDER") or not DEBUG:
    USE_X_FORWARDED_HOST = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ============================================================
# LOGGING
# ============================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "jugadas": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "roles": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "cuadres": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}

# ============================================================
# CONFIGURACIÓN DEL SISTEMA DE CUADRE DIARIO
# ============================================================
CUADRE_CONFIG = {
    "COMISION_PORCENTAJE": 0.15,
    "DIAS_AUTO_CIERRE": 0,
    "GENERAR_AUTO": True,
    "DIAS_HISTORIAL_PREDETERMINADO": 30,
    "FORMAS_PAGO_PRINCIPALES": ["Tarjeta", "Saldo", "CASH"],
}

# ============================================================
# PERMISOS Y ROLES
# ============================================================
ROLES_DISPONIBLES = [
    ("superadmin", "Super Administrador"),
    ("banco", "Banco"),
    ("comercial", "Comercial"),
    ("cliente", "Cliente"),
    ("auditor", "Auditor"),
]

# ============================================================
# API + CORS (para la app Android)
# ============================================================
CORS_ALLOW_ALL_ORIGINS = True          # ⚠️ Cambia a False cuando la app esté fija
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    'https://lottoboom.pythonanywhere.com',
    'https://www.lottoboom.pythonanywhere.com',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# ============================================================
# CHANGELOG DE ESTA REVISIÓN
# ============================================================
# v2 (2026-10-11):
#   - STORAGES: CompressedManifestStaticFilesStorage → CompressedStaticFilesStorage
#   - Añadido WHITENOISE_USE_FINDERS y WHITENOISE_AUTOREFRESH
#   - DATA_UPLOAD_MAX_NUMBER_FIELDS: 500000 → 5000
#   - ALLOWED_HOSTS: añadido www.lottoboom.pythonanywhere.com
#   - CSRF_TRUSTED_ORIGINS: añadido www.lottoboom.pythonanywhere.com