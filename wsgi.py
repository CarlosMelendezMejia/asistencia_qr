import os
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

# Carga la app Flask principal (debes tener "app" en app.py)
from app import app as asistencia_app

# Prefijo desde variable de entorno, por defecto /asistencia_qr
APP_PREFIX = os.getenv("APP_PREFIX", "/asistencia_qr")

# Normalizamos prefijo (sin doble slash)
APP_PREFIX = "/" + APP_PREFIX.strip("/")

# Si tu app ya maneja SCRIPT_NAME o prefijos internamente, puedes montar directo:
application = DispatcherMiddleware(
    Response("Not Found", status=404),
    {APP_PREFIX: asistencia_app}
)
