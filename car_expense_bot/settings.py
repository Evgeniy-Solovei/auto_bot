import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-local-car-expense-bot")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,*").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "adrf",
    "core.apps.CoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "car_expense_bot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "car_expense_bot.wsgi.application"
ASGI_APPLICATION = "car_expense_bot.asgi.application"

POSTGRES_DB = os.getenv("POSTGRES_DB")
if not POSTGRES_DB:
    raise RuntimeError("POSTGRES_DB is required. Configure PostgreSQL credentials in .env.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": POSTGRES_DB,
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = os.getenv("TIME_ZONE", "Europe/Minsk")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser", "rest_framework.parsers.FormParser", "rest_framework.parsers.MultiPartParser"],
}

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
BOT_API_BASE_URL = os.getenv("BOT_API_BASE_URL", "http://127.0.0.1:8000/api")


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "True").lower() == "true"
LOG_FILE_ENABLED = False
if LOG_TO_FILE:
    try:
        LOG_DIR.mkdir(exist_ok=True)
        test_log_file = LOG_DIR / ".write_test"
        test_log_file.write_text("ok", encoding="utf-8")
        test_log_file.unlink(missing_ok=True)
        LOG_FILE_ENABLED = True
    except OSError:
        LOG_FILE_ENABLED = False

LOGGING_HANDLERS = {
    "console": {
        "class": "logging.StreamHandler",
        "formatter": "verbose",
        "level": LOG_LEVEL,
    },
}

if LOG_FILE_ENABLED:
    LOGGING_HANDLERS.update(
        {
            "django_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": LOG_DIR / "django.log",
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 5,
                "formatter": "verbose",
                "level": LOG_LEVEL,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": LOG_DIR / "django_errors.log",
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 10,
                "formatter": "verbose",
                "level": "ERROR",
                "encoding": "utf-8",
            },
        }
    )

LOGGING_DEFAULT_HANDLERS = ["console", "django_file", "error_file"] if LOG_FILE_ENABLED else ["console"]
LOGGING_ERROR_HANDLERS = ["console", "django_file", "error_file"] if LOG_FILE_ENABLED else ["console"]
LOGGING_ACCESS_HANDLERS = ["console", "django_file"] if LOG_FILE_ENABLED else ["console"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {name}: {message}",
            "style": "{",
        },
    },
    "handlers": LOGGING_HANDLERS,
    "loggers": {
        "django": {
            "handlers": LOGGING_DEFAULT_HANDLERS,
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": LOGGING_ERROR_HANDLERS,
            "level": "WARNING",
            "propagate": False,
        },
        "core": {
            "handlers": LOGGING_DEFAULT_HANDLERS,
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn": {
            "handlers": LOGGING_DEFAULT_HANDLERS,
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": LOGGING_DEFAULT_HANDLERS,
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": LOGGING_ACCESS_HANDLERS,
            "level": os.getenv("UVICORN_ACCESS_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
    },
}

JAZZMIN_SETTINGS = {
    "site_title": "Auto Bot Admin",
    "site_header": "Auto Bot",
    "site_brand": "Auto Bot",
    "welcome_sign": "Админ-панель учета заказов и расходов",
    "copyright": "Auto Bot",
    "search_model": ["core.Car", "core.Expense", "core.TelegramUser"],
    "topmenu_links": [
        {"name": "Админка", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"model": "core.Car"},
        {"model": "core.Expense"},
    ],
    "order_with_respect_to": [
        "core.Car",
        "core.Expense",
        "core.DefectPhoto",
        "core.TelegramUser",
        "core.ExpenseCategory",
        "core.AdminUserProxy",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "core.AdminUserProxy": "fas fa-user-shield",
        "core.Car": "fas fa-car-side",
        "core.Expense": "fas fa-money-bill-wave",
        "core.DefectPhoto": "fas fa-camera",
        "core.ExpenseCategory": "fas fa-tags",
        "core.TelegramUser": "fab fa-telegram",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": ["auth.Group", "auth.User"],
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar": "navbar-dark navbar-primary",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,
    "theme": "flatly",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

