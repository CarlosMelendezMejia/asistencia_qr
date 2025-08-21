import os
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

# Carga la app Flask principal (debes tener "app" en app.py)
from app import app as asistencia_app

# Prefijo desde variable de entorno; por defecto vacío (raíz '/')
APP_PREFIX = os.getenv("APP_PREFIX", "").strip()

# Montaje condicional: si hay prefijo, se monta en '/<prefijo>'; si no, en '/'
mount_map = {f"/{APP_PREFIX.strip('/')}": asistencia_app} if APP_PREFIX else {"/": asistencia_app}

application = DispatcherMiddleware(
    Response("Not Found", status=404),
    mount_map,
)
