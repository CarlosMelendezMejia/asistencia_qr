import os
import csv
import io
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    jsonify, session, make_response, abort, flash
)
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "devsecret")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "asistenciaqr"),
    "autocommit": True,
}

DB_POOL_NAME = os.getenv("DB_POOL_NAME", "asistencia_pool")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "15"))

cnx_pool = pooling.MySQLConnectionPool(
    pool_name=DB_POOL_NAME,
    pool_size=DB_POOL_SIZE,
    **DB_CONFIG,
)


def db_conn():
    try:
        return cnx_pool.get_connection()
    except mysql.connector.errors.PoolError:
        abort(503, description="No hay conexiones disponibles. Intenta nuevamente en un momento.")


def get_default_slug():
    """Return slug of the active event or raise a clear error if none is active."""
    cnx = cur = None
    try:
        cnx = db_conn()
        cur = cnx.cursor(dictionary=True)
        cur.execute(
            "SELECT slug FROM evento WHERE activo=1 ORDER BY creado_en DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            # 500 to signal misconfiguration; admin must create/activate an event
            abort(500, description="No hay un evento activo. Crea y/o activa un evento desde Admin > Eventos.")
        return row["slug"]
    finally:
        if cur:
            cur.close()
        if cnx:
            cnx.close()

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("is_admin"):
            return f(*args, **kwargs)
        return redirect(url_for("admin_login"))
    return wrapper

@app.get("/")
def index():
    slug = get_default_slug()
    return redirect(url_for("evento_form", slug=slug))

@app.get("/evento/<slug>")
def evento_form(slug):
    cnx = db_conn()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT * FROM evento WHERE slug=%s AND activo=1", (slug,))
    evt = cur.fetchone()
    cur.close()
    cnx.close()
    if not evt:
        abort(404)
    return render_template("form.html", evento=evt)

@app.post("/api/registro")
def api_registro():
    data = request.get_json(silent=True) or request.form
    required = ["slug", "nombre", "apellidos", "email"]
    for r in required:
        if not data.get(r):
            return jsonify({"ok": False, "error": f"Falta: {r}"}), 400

    slug = data.get("slug").strip()
    nombre = data.get("nombre").strip()
    apellidos = data.get("apellidos").strip()
    email = data.get("email").strip().lower()
    telefono = (data.get("telefono") or "").strip()
    institucion = (data.get("institucion") or "").strip()
    carrera = (data.get("carrera_o_area") or "").strip()
    temas = (data.get("temas_interes") or "").strip()
    consentimiento = 1 if str(data.get("consentimiento", "0")) in ("1", "true", "on") else 0

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")

    cnx = cur = None
    try:
        cnx = db_conn()
        cur = cnx.cursor(dictionary=True)

        # 1) buscar evento
        cur.execute("SELECT id FROM evento WHERE slug=%s AND activo=1", (slug,))
        evt = cur.fetchone()
        if not evt:
            return jsonify({"ok": False, "error": "Evento no encontrado o inactivo"}), 404

        id_evento = evt["id"]

        # 2) insertar (o rechazar duplicado por email en el mismo evento)
        try:
            cur.execute(
                """
                INSERT INTO registro
                (id_evento, nombre, apellidos, email, telefono, institucion, carrera_o_area, temas_interes,
                 consentimiento, asistencia_marcarda_en, ip, user_agent)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW(), %s,%s)
            """,
                (id_evento, nombre, apellidos, email, telefono, institucion, carrera, temas, consentimiento, ip, ua),
            )
            cnx.commit()
        except mysql.connector.Error as e:
            app.logger.warning("Registro duplicado o error de inserción: %s", e)
            if e.errno == 1062:
                return jsonify({"ok": False, "error": "Este email ya está registrado para este evento."}), 409
            raise

        return jsonify({"ok": True})
    except mysql.connector.Error as e:
        app.logger.exception("Error de base de datos en api_registro")
        return jsonify({"ok": False, "error": f"DB error: {e}"}), 500
    except Exception as e:
        app.logger.exception("Error inesperado en api_registro")
        return jsonify({"ok": False, "error": f"Error interno: {e}"}), 500
    finally:
        if cur:
            cur.close()
        if cnx:
            cnx.close()

@app.get("/success")
def success():
    return render_template("success.html")

# ------- Admin --------

@app.get("/admin/login")
def admin_login():
    return render_template("admin.html", view="login")

@app.post("/admin/login")
def admin_login_post():
    user = request.form.get("user", "")
    pwd = request.form.get("password", "")
    if user == ADMIN_USER and pwd == ADMIN_PASSWORD:
        session["is_admin"] = True
        return redirect(url_for("admin_panel"))
    flash("Credenciales inválidas", "danger")
    return redirect(url_for("admin_login"))

@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.get("/admin")
@admin_required
def admin_panel():
    slug = request.args.get("slug", "").strip()
    cnx = db_conn()
    cur = cnx.cursor(dictionary=True)

    # Eventos para selector y administración
    cur.execute("SELECT id, slug, titulo, fecha_inicio, fecha_fin, lugar, activo FROM evento ORDER BY creado_en DESC")
    eventos = cur.fetchall()

    registros = []
    if slug:
        cur.execute("""
            SELECT r.*, e.slug, e.titulo
            FROM registro r
            JOIN evento e ON e.id = r.id_evento
            WHERE e.slug=%s
            ORDER BY r.creado_en DESC
        """, (slug,))
        registros = cur.fetchall()

    cur.close(); cnx.close()
    return render_template("admin.html", view="panel", eventos=eventos, registros=registros, slug=slug)

# ------- Admin: crear/activar evento --------

@app.route("/admin/evento", methods=["GET", "POST"])
@admin_required
def admin_evento():
    if request.method == "GET":
        # La forma de creación está embebida en el panel
        return redirect(url_for("admin_panel"))

    # POST: crear evento
    form = request.form
    slug = (form.get("slug") or "").strip()
    titulo = (form.get("titulo") or "").strip()
    fecha_inicio = (form.get("fecha_inicio") or "").strip()
    fecha_fin = (form.get("fecha_fin") or "").strip()
    lugar = (form.get("lugar") or "").strip()
    activo = 1 if str(form.get("activo", "0")).lower() in ("1", "true", "on", "yes") else 0

    if not slug or not titulo:
        flash("Slug y título son obligatorios", "danger")
        return redirect(url_for("admin_panel"))

    # Parse datetime-local values (YYYY-MM-DDTHH:MM)
    def parse_dt(val):
        if not val:
            return None
        try:
            v = val.replace("T", " ")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
        except Exception:
            return None
        return None

    fi = parse_dt(fecha_inicio)
    ff = parse_dt(fecha_fin)

    cnx = db_conn()
    cur = cnx.cursor()
    try:
        if activo:
            cur.execute("UPDATE evento SET activo=0")
        cur.execute(
            """
            INSERT INTO evento (slug, titulo, fecha_inicio, fecha_fin, lugar, activo)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (slug, titulo, fi, ff, lugar, activo or 0),
        )
        cnx.commit()
        flash("Evento creado correctamente", "success")
    except mysql.connector.Error as e:
        cnx.rollback()
        if e.errno == 1062:
            flash("El slug ya existe. Elige otro.", "danger")
        else:
            flash(f"Error de BD: {e}", "danger")
    finally:
        cur.close(); cnx.close()
    return redirect(url_for("admin_panel"))

@app.post("/admin/evento/<int:event_id>/activar")
@admin_required
def admin_evento_activar(event_id: int):
    cnx = db_conn()
    cur = cnx.cursor()
    try:
        cur.execute("UPDATE evento SET activo=0")
        cur.execute("UPDATE evento SET activo=1 WHERE id=%s", (event_id,))
        cnx.commit()
        flash("Evento activado", "success")
    except mysql.connector.Error as e:
        cnx.rollback()
        flash(f"Error de BD: {e}", "danger")
    finally:
        cur.close(); cnx.close()
    return redirect(url_for("admin_panel"))

@app.get("/admin/export")
@admin_required
def admin_export():
    slug = request.args.get("slug", "").strip()
    if not slug:
        return "Falta slug", 400
    cnx = db_conn()
    cur = cnx.cursor(dictionary=True)
    cur.execute("""
        SELECT e.slug, e.titulo, r.nombre, r.apellidos, r.email, r.telefono,
               r.institucion, r.carrera_o_area, r.temas_interes, r.consentimiento, r.asistencia_marcarda_en, r.creado_en
        FROM registro r
        JOIN evento e ON e.id = r.id_evento
        WHERE e.slug=%s
        ORDER BY r.creado_en DESC
    """, (slug,))
    rows = cur.fetchall()
    cur.close(); cnx.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["slug","titulo","nombre","apellidos","email","telefono","institucion",
                     "carrera_o_area","temas_interes","consentimiento","asistencia_marcarda_en","creado_en"])
    for r in rows:
        writer.writerow([r["slug"], r["titulo"], r["nombre"], r["apellidos"], r["email"], r["telefono"],
                         r["institucion"], r["carrera_o_area"], r["temas_interes"], r["consentimiento"],
                         r["asistencia_marcarda_en"], r["creado_en"]])
    csv_data = output.getvalue().encode("utf-8-sig")  # BOM para Excel
    resp = make_response(csv_data)
    fname = f"registros_{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    resp.headers["Content-Disposition"] = f"attachment; filename={fname}"
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    return resp

if __name__ == "__main__":
    app.run(debug=True)
