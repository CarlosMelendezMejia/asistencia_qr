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

def db_conn():
    return mysql.connector.connect(**DB_CONFIG)

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("is_admin"):
            return f(*args, **kwargs)
        return redirect(url_for("admin_login"))
    return wrapper

@app.get("/")
def index():
    return redirect(url_for("evento_form", slug="ponencia-ia-ago2025"))  # cambia al evento real

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

    # Eventos para selector
    cur.execute("SELECT id, slug, titulo FROM evento ORDER BY creado_en DESC")
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
