from .settings import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = "test-secret-key-for-pytest-only-keep-it-long-enough-for-jwt"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
TERMINAL_API_SECRET = "test-terminal-secret"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",  # noqa: F405
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
JWT_REFRESH_COOKIE_SECURE = False
CELERY_TASK_ALWAYS_EAGER = True
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "station-test-cache",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
