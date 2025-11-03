import os
from nautobot.core.settings import *  # noqa

SECRET_KEY = 'HtpmllY7I1JA5uaUvuplOldqubNfWV0Kc1EX_RNue7XxXP-4h9GS9FHEcfozJQyhHN0'

DATABASES = {
  "default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "nautobot",
    "USER": "nautobot",
    "PASSWORD": "nautobot",
    "HOST": "127.0.0.1",
    "PORT": "5432",
    "CONN_MAX_AGE": 300,
  }
}

CACHE = {
  "BACKEND": "django.core.cache.backends.redis.RedisCache",
  "LOCATION": "redis://127.0.0.1:6379/1",
}

RQ_QUEUES = {
  "default": {"HOST": "127.0.0.1", "PORT": 6379, "DB": 0, "SSL": False},
}
DEBUG = True  # dev only

STATIC_ROOT = os.path.join(BASE_DIR, "static")
MEDIA_ROOT  = os.path.join(BASE_DIR, "media")
ALLOWED_HOSTS = ["*", "localhost", "127.0.0.1", "10.224.76.95"]
