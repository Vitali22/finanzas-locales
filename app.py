import csv
import hashlib
import io
import os
import shutil
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    Response,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

try:
    from openpyxl import Workbook
except ImportError:  # The app still runs; Excel export shows a clear message.
    Workbook = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "finanzas.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
CATEGORIES = ["Transporte", "Comida", "Servicios", "Otros"]
INCOME_CATEGORIES = ["Sueldo", "Venta", "Transferencia", "Regalo"]
PAYMENT_METHODS = ["Efectivo", "Débito", "Transferencia", "Crédito"]
DEFAULT_PASSWORD = "admin123"
CURRENCY = "MXN"
INACTIVITY_MINUTES = 15

app = Flask(__name__)
app.secret_key = os.environ.get("FINANZAS_SECRET", "cambia-esta-clave-local")
app.permanent_session_lifetime = timedelta(minutes=INACTIVITY_MINUTES)


def today_iso():
    return date.today().isoformat()


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def close_current_db():
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.before_request
def enforce_session_rules():
    if request.endpoint == "static":
        return None
    if session.get("logged_in"):
        now = datetime.now()
        last_seen = session.get("last_seen")
        if last_seen:
            last_seen_dt = datetime.fromisoformat(last_seen)
            if now - last_seen_dt > timedelta(minutes=INACTIVITY_MINUTES):
                session.clear()
                flash("Sesion cerrada por inactividad.", "warning")
                return redirect(url_for("login"))
        session["last_seen"] = now.isoformat()
        session.permanent = True
        if setting("password_must_change", "0") == "1" and request.endpoint not in {
            "change_initial_password",
            "logout",
        }:
            return redirect(url_for("change_initial_password"))
    return None


def current_cycle(reference=None):
    reference = reference or date.today()
    if reference.day >= 15:
        start = reference.replace(day=15)
        if reference.month == 12:
            end = date(reference.year + 1, 1, 14)
        else:
            end = date(reference.year, reference.month + 1, 14)
    else:
        end = reference.replace(day=14)
        if reference.month == 1:
            start = date(reference.year - 1, 12, 15)
        else:
            start = date(reference.year, reference.month - 1, 15)
    return start, end


def setting(key, default=None):
    row = query("SELECT value FROM settings WHERE key = ?", (key,), one=True)
    return row["value"] if row else default


def set_setting(key, value):
    execute(
        """
        INSERT INTO settings(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, str(value)),
    )


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'gasto',
            parent_id INTEGER,
            FOREIGN KEY(parent_id) REFERENCES categorias(id)
        );

        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monto REAL NOT NULL,
            categoria TEXT NOT NULL,
            categoria_id INTEGER,
            subcategoria_id INTEGER,
            metodo_pago TEXT NOT NULL DEFAULT 'Efectivo',
            fecha TEXT NOT NULL,
            descripcion TEXT,
            FOREIGN KEY(categoria_id) REFERENCES categorias(id),
            FOREIGN KEY(subcategoria_id) REFERENCES categorias(id)
        );

        CREATE TABLE IF NOT EXISTS ingresos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monto REAL NOT NULL,
            categoria TEXT DEFAULT 'Sueldo',
            categoria_id INTEGER,
            fecha TEXT NOT NULL,
            descripcion TEXT,
            tarjeta_id INTEGER,
            FOREIGN KEY(categoria_id) REFERENCES categorias(id),
            FOREIGN KEY(tarjeta_id) REFERENCES tarjetas(id)
        );

        CREATE TABLE IF NOT EXISTS tarjetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            limite REAL NOT NULL DEFAULT 0,
            tipo TEXT NOT NULL DEFAULT 'credito',
            saldo REAL NOT NULL DEFAULT 0,
            fecha_corte INTEGER,
            fecha_pago INTEGER
        );

        CREATE TABLE IF NOT EXISTS gastos_tarjeta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarjeta_id INTEGER NOT NULL,
            monto REAL NOT NULL,
            fecha TEXT NOT NULL,
            descripcion TEXT,
            FOREIGN KEY(tarjeta_id) REFERENCES tarjetas(id)
        );

        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            monto REAL NOT NULL DEFAULT 0,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS planes_mensuales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ciclo_inicio TEXT NOT NULL UNIQUE,
            ciclo_fin TEXT NOT NULL,
            ingreso_plan REAL NOT NULL DEFAULT 0
        );
        """
    )
    db.commit()

    if not setting("password_hash"):
        set_setting("password_hash", hash_password(DEFAULT_PASSWORD))
        set_setting("theme", "light")
        set_setting("password_must_change", "1")
    else:
        if setting("theme") is None:
            set_setting("theme", "light")
        if setting("password_must_change") is None:
            must_change = "1" if setting("password_hash") == hash_password(DEFAULT_PASSWORD) else "0"
            set_setting("password_must_change", must_change)

    if not query("SELECT id FROM categorias LIMIT 1"):
        seed_categories()
    if not query("SELECT id FROM ingresos LIMIT 1"):
        seed_demo_data()
    auto_backup_if_needed()


def backup_database(kind):
    if not os.path.exists(DB_PATH):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(BACKUP_DIR, f"finanzas_{kind}_{timestamp}.db")
    shutil.copy2(DB_PATH, path)
    return path


def auto_backup_if_needed():
    if not os.path.exists(DB_PATH):
        return
    today = date.today()
    if setting("last_daily_backup") != today.isoformat():
        backup_database("diario")
        set_setting("last_daily_backup", today.isoformat())
    week_key = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
    if setting("last_weekly_backup") != week_key:
        backup_database("semanal")
        set_setting("last_weekly_backup", week_key)


def backup_info():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    files = [
        os.path.join(BACKUP_DIR, name)
        for name in os.listdir(BACKUP_DIR)
        if name.endswith(".db")
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    latest = files[0] if files else None
    return {
        "count": len(files),
        "latest": os.path.basename(latest) if latest else "Sin respaldos aun",
        "folder": BACKUP_DIR,
        "daily": setting("last_daily_backup", "Pendiente"),
        "weekly": setting("last_weekly_backup", "Pendiente"),
    }


def seed_categories():
    for name in CATEGORIES:
        parent_id = execute(
            "INSERT INTO categorias(nombre, tipo, parent_id) VALUES(?, 'gasto', NULL)",
            (name,),
        )
        if name == "Comida":
            for child in ["Super", "Restaurante", "Cafe"]:
                execute(
                    "INSERT INTO categorias(nombre, tipo, parent_id) VALUES(?, 'gasto', ?)",
                    (child, parent_id),
                )
        if name == "Transporte":
            for child in ["Gasolina", "Taxi", "Metro"]:
                execute(
                    "INSERT INTO categorias(nombre, tipo, parent_id) VALUES(?, 'gasto', ?)",
                    (child, parent_id),
                )
    for name in INCOME_CATEGORIES:
        execute(
            "INSERT INTO categorias(nombre, tipo, parent_id) VALUES(?, 'ingreso', NULL)",
            (name,),
        )


def seed_demo_data():
    today = date.today()
    start, end = current_cycle(today)
    execute(
        "INSERT OR IGNORE INTO planes_mensuales(ciclo_inicio, ciclo_fin, ingreso_plan) VALUES(?, ?, ?)",
        (start.isoformat(), end.isoformat(), 24000),
    )
    execute(
        "INSERT INTO ingresos(monto, categoria, fecha, descripcion) VALUES(?, ?, ?, ?)",
        (24000, "Sueldo", start.isoformat(), "Ingreso mensual de prueba"),
    )
    execute(
        "INSERT INTO gastos(monto, categoria, metodo_pago, fecha, descripcion) VALUES(?, ?, ?, ?, ?)",
        (185, "Comida", "Efectivo", today.isoformat(), "Comida corrida"),
    )
    execute(
        "INSERT INTO gastos(monto, categoria, metodo_pago, fecha, descripcion) VALUES(?, ?, ?, ?, ?)",
        (80, "Transporte", "Transferencia", today.isoformat(), "Viaje local"),
    )
    debit_id = execute(
        "INSERT INTO tarjetas(nombre, limite, tipo, saldo, fecha_corte, fecha_pago) VALUES(?, ?, ?, ?, ?, ?)",
        ("Cuenta debito demo", 0, "debito", 6500, None, None),
    )
    credit_id = execute(
        "INSERT INTO tarjetas(nombre, limite, tipo, saldo, fecha_corte, fecha_pago) VALUES(?, ?, ?, ?, ?, ?)",
        ("Credito demo", 18000, "credito", 0, 15, 5),
    )
    execute(
        "INSERT INTO gastos_tarjeta(tarjeta_id, monto, fecha, descripcion) VALUES(?, ?, ?, ?)",
        (credit_id, 620, today.isoformat(), "Compra con credito"),
    )
    execute(
        "INSERT INTO gastos_tarjeta(tarjeta_id, monto, fecha, descripcion) VALUES(?, ?, ?, ?)",
        (debit_id, 240, today.isoformat(), "Compra con debito"),
    )
    execute("UPDATE tarjetas SET saldo = saldo - ? WHERE id = ?", (240, debit_id))
    execute(
        "INSERT INTO eventos(nombre, monto, fecha, tipo) VALUES(?, ?, ?, ?)",
        ("Pago luz", 750, (today + timedelta(days=2)).isoformat(), "gasto futuro"),
    )
    execute(
        "INSERT INTO eventos(nombre, monto, fecha, tipo) VALUES(?, ?, ?, ?)",
        ("Revisar presupuesto", 0, (today + timedelta(days=5)).isoformat(), "recordatorio"),
    )


def money(value):
    return float(value or 0)


def dashboard_data():
    today = date.today()
    start, end = current_cycle(today)
    start_iso, end_iso = start.isoformat(), end.isoformat()
    plan = query(
        "SELECT * FROM planes_mensuales WHERE ciclo_inicio = ?",
        (start_iso,),
        one=True,
    )
    monthly_plan = money(plan["ingreso_plan"] if plan else 0)

    ingresos_total = money(query("SELECT SUM(monto) total FROM ingresos", one=True)["total"])
    gastos_directos_total = money(query("SELECT SUM(monto) total FROM gastos", one=True)["total"])
    tarjetas = card_summaries()
    debit_balances = sum(money(t["saldo"]) for t in tarjetas if t["tipo"] == "debito")
    credit_debt = money(
        query(
            """
            SELECT SUM(gt.monto) total
            FROM gastos_tarjeta gt
            JOIN tarjetas t ON t.id = gt.tarjeta_id
            WHERE t.tipo = 'credito'
            """,
            one=True,
        )["total"]
    )
    available = ingresos_total - gastos_directos_total + debit_balances

    gastos_hoy = money(
        query("SELECT SUM(monto) total FROM gastos WHERE fecha = ?", (today_iso(),), one=True)["total"]
    )
    tarjetas_hoy = money(
        query("SELECT SUM(monto) total FROM gastos_tarjeta WHERE fecha = ?", (today_iso(),), one=True)["total"]
    )
    gasto_dia = gastos_hoy + tarjetas_hoy

    cycle_gastos = money(
        query(
            "SELECT SUM(monto) total FROM gastos WHERE fecha BETWEEN ? AND ?",
            (start_iso, end_iso),
            one=True,
        )["total"]
    )
    cycle_cards = money(
        query(
            "SELECT SUM(monto) total FROM gastos_tarjeta WHERE fecha BETWEEN ? AND ?",
            (start_iso, end_iso),
            one=True,
        )["total"]
    )
    cycle_spent = cycle_gastos + cycle_cards
    days_remaining = max((end - today).days + 1, 1)
    daily_budget = max((monthly_plan - cycle_spent) / days_remaining, 0)

    by_category_rows = query(
        """
        SELECT categoria label, SUM(monto) total
        FROM gastos
        WHERE fecha BETWEEN ? AND ?
        GROUP BY categoria
        ORDER BY total DESC
        """,
        (start_iso, end_iso),
    )
    card_total = money(
        query(
            "SELECT SUM(monto) total FROM gastos_tarjeta WHERE fecha BETWEEN ? AND ?",
            (start_iso, end_iso),
            one=True,
        )["total"]
    )
    by_category = [{"label": r["label"], "total": money(r["total"])} for r in by_category_rows]
    if card_total:
        by_category.append({"label": "Tarjetas", "total": card_total})

    return {
        "currency": CURRENCY,
        "available": available,
        "gasto_dia": gasto_dia,
        "daily_budget": daily_budget,
        "remaining_today": daily_budget - gasto_dia,
        "monthly_plan": monthly_plan,
        "cycle_spent": cycle_spent,
        "cycle_start": start_iso,
        "cycle_end": end_iso,
        "credit_debt": credit_debt,
        "by_category": by_category,
        "budget_chart": [
            {"label": "Gastado hoy", "total": gasto_dia},
            {"label": "Disponible hoy", "total": max(daily_budget - gasto_dia, 0)},
        ],
        "alerts": upcoming_alerts(),
    }


def upcoming_alerts():
    today = date.today()
    limit = today + timedelta(days=3)
    return query(
        "SELECT * FROM eventos WHERE fecha BETWEEN ? AND ? ORDER BY fecha ASC",
        (today.isoformat(), limit.isoformat()),
    )


def card_summaries():
    return query(
        """
        SELECT t.*,
               COALESCE(SUM(gt.monto), 0) AS total_gastado,
               CASE WHEN t.tipo = 'credito' THEN COALESCE(SUM(gt.monto), 0) ELSE 0 END AS total_adeudado
        FROM tarjetas t
        LEFT JOIN gastos_tarjeta gt ON gt.tarjeta_id = t.id
        GROUP BY t.id
        ORDER BY t.nombre
        """
    )


def parse_float(name, default=0):
    raw = request.form.get(name, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def parse_int(name, default=None):
    raw = request.form.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def categories_for(kind):
    return query(
        "SELECT * FROM categorias WHERE tipo = ? ORDER BY parent_id IS NOT NULL, nombre",
        (kind,),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    init_db()
    if request.method == "POST":
        if hash_password(request.form.get("password", "")) == setting("password_hash"):
            session["logged_in"] = True
            session["last_seen"] = datetime.now().isoformat()
            session.permanent = True
            return redirect(url_for("index"))
        flash("Contraseña incorrecta.", "danger")
    return render_template("login.html")


@app.route("/change-initial-password", methods=["GET", "POST"])
@login_required
def change_initial_password():
    init_db()
    if request.method == "POST":
        new_password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()
        if len(new_password) < 6:
            flash("Usa una contraseña de al menos 6 caracteres.", "warning")
        elif new_password != confirm:
            flash("Las contraseñas no coinciden.", "warning")
        elif new_password == DEFAULT_PASSWORD:
            flash("Elige una contraseña diferente a la inicial.", "warning")
        else:
            set_setting("password_hash", hash_password(new_password))
            set_setting("password_must_change", "0")
            flash("Contraseña actualizada. Ya puedes usar la app.", "success")
            return redirect(url_for("index"))
    return render_template("change_password.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    init_db()
    filters = {
        "fecha_inicio": request.args.get("fecha_inicio", ""),
        "fecha_fin": request.args.get("fecha_fin", ""),
        "categoria": request.args.get("categoria", ""),
        "tarjeta": request.args.get("tarjeta", ""),
        "q": request.args.get("q", "").strip(),
    }
    gastos_sql = "SELECT * FROM gastos WHERE 1=1"
    args = []
    if filters["fecha_inicio"]:
        gastos_sql += " AND fecha >= ?"
        args.append(filters["fecha_inicio"])
    if filters["fecha_fin"]:
        gastos_sql += " AND fecha <= ?"
        args.append(filters["fecha_fin"])
    if filters["categoria"]:
        gastos_sql += " AND categoria = ?"
        args.append(filters["categoria"])
    if filters["q"]:
        gastos_sql += """
            AND (
                descripcion LIKE ?
                OR categoria LIKE ?
                OR metodo_pago LIKE ?
                OR fecha LIKE ?
                OR CAST(monto AS TEXT) LIKE ?
            )
        """
        like = f"%{filters['q']}%"
        args.extend([like, like, like, like, like])
    gastos_sql += " ORDER BY fecha DESC, id DESC"

    card_sql = """
        SELECT gt.*, t.nombre tarjeta, t.tipo
        FROM gastos_tarjeta gt
        JOIN tarjetas t ON t.id = gt.tarjeta_id
        WHERE 1=1
    """
    card_args = []
    if filters["fecha_inicio"]:
        card_sql += " AND gt.fecha >= ?"
        card_args.append(filters["fecha_inicio"])
    if filters["fecha_fin"]:
        card_sql += " AND gt.fecha <= ?"
        card_args.append(filters["fecha_fin"])
    if filters["tarjeta"]:
        card_sql += " AND t.id = ?"
        card_args.append(filters["tarjeta"])
    card_sql += " ORDER BY gt.fecha DESC, gt.id DESC"

    context = {
        "dashboard": dashboard_data(),
        "gastos": query(gastos_sql, args),
        "ingresos": query("SELECT * FROM ingresos ORDER BY fecha DESC, id DESC"),
        "tarjetas": card_summaries(),
        "gastos_tarjeta": query(card_sql, card_args),
        "eventos": query("SELECT * FROM eventos ORDER BY fecha ASC"),
        "categorias": categories_for("gasto"),
        "categorias_ingreso": categories_for("ingreso"),
        "metodos": PAYMENT_METHODS,
        "today": today_iso(),
        "filters": filters,
        "theme": setting("theme", "light"),
        "backup_info": backup_info(),
        "inactivity_minutes": INACTIVITY_MINUTES,
    }
    return render_template("index.html", **context)


@app.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    new_password = request.form.get("password", "").strip()
    if len(new_password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres.", "warning")
    elif new_password == DEFAULT_PASSWORD:
        flash("Elige una contraseña diferente a la contraseña inicial.", "warning")
    else:
        set_setting("password_hash", hash_password(new_password))
        set_setting("password_must_change", "0")
        flash("Contraseña actualizada.", "success")
    return redirect(url_for("index"))


@app.route("/settings/theme", methods=["POST"])
@login_required
def set_theme():
    set_setting("theme", request.form.get("theme", "light"))
    return redirect(url_for("index"))


@app.route("/plan", methods=["POST"])
@login_required
def save_plan():
    start, end = current_cycle()
    execute(
        """
        INSERT INTO planes_mensuales(ciclo_inicio, ciclo_fin, ingreso_plan) VALUES(?, ?, ?)
        ON CONFLICT(ciclo_inicio) DO UPDATE SET ingreso_plan = excluded.ingreso_plan
        """,
        (start.isoformat(), end.isoformat(), parse_float("ingreso_plan")),
    )
    flash("Plan mensual actualizado.", "success")
    return redirect(url_for("index"))


@app.route("/categorias", methods=["POST"])
@login_required
def add_category():
    name = request.form.get("nombre", "").strip()
    kind = request.form.get("tipo", "gasto")
    parent_id = parse_int("parent_id")
    if name:
        execute(
            "INSERT INTO categorias(nombre, tipo, parent_id) VALUES(?, ?, ?)",
            (name, kind, parent_id),
        )
        flash("Categoria guardada.", "success")
    return redirect(url_for("index"))


@app.route("/categorias/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_category(item_id):
    execute("DELETE FROM categorias WHERE id = ?", (item_id,))
    flash("Categoria eliminada.", "success")
    return redirect(url_for("index"))


@app.route("/categorias/<int:item_id>/update", methods=["POST"])
@login_required
def update_category(item_id):
    name = request.form.get("nombre", "").strip()
    if name:
        execute("UPDATE categorias SET nombre = ? WHERE id = ?", (name, item_id))
        flash("Categoria actualizada.", "success")
    return redirect(url_for("index"))


@app.route("/gastos", methods=["POST"])
@login_required
def add_expense():
    cat_id = parse_int("categoria_id")
    sub_id = parse_int("subcategoria_id")
    cat = query("SELECT nombre FROM categorias WHERE id = ?", (cat_id,), one=True)
    categoria = cat["nombre"] if cat else request.form.get("categoria", "Otros")
    execute(
        """
        INSERT INTO gastos(monto, categoria, categoria_id, subcategoria_id, metodo_pago, fecha, descripcion)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            parse_float("monto"),
            categoria,
            cat_id,
            sub_id,
            request.form.get("metodo_pago", "Efectivo"),
            request.form.get("fecha") or today_iso(),
            request.form.get("descripcion", "").strip(),
        ),
    )
    flash("Gasto registrado.", "success")
    return redirect(url_for("index"))


@app.route("/gastos/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_expense(item_id):
    execute("DELETE FROM gastos WHERE id = ?", (item_id,))
    flash("Gasto eliminado.", "success")
    return redirect(url_for("index"))


@app.route("/ingresos", methods=["POST"])
@login_required
def add_income():
    cat_id = parse_int("categoria_id")
    cat = query("SELECT nombre FROM categorias WHERE id = ?", (cat_id,), one=True)
    tarjeta_id = parse_int("tarjeta_id")
    amount = parse_float("monto")
    execute(
        """
        INSERT INTO ingresos(monto, categoria, categoria_id, fecha, descripcion, tarjeta_id)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            amount,
            cat["nombre"] if cat else "Sueldo",
            cat_id,
            request.form.get("fecha") or today_iso(),
            request.form.get("descripcion", "").strip(),
            tarjeta_id,
        ),
    )
    if tarjeta_id:
        execute("UPDATE tarjetas SET saldo = saldo + ? WHERE id = ? AND tipo = 'debito'", (amount, tarjeta_id))
    flash("Ingreso registrado.", "success")
    return redirect(url_for("index"))


@app.route("/ingresos/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_income(item_id):
    row = query("SELECT * FROM ingresos WHERE id = ?", (item_id,), one=True)
    if row and row["tarjeta_id"]:
        execute("UPDATE tarjetas SET saldo = saldo - ? WHERE id = ?", (row["monto"], row["tarjeta_id"]))
    execute("DELETE FROM ingresos WHERE id = ?", (item_id,))
    flash("Ingreso eliminado.", "success")
    return redirect(url_for("index"))


@app.route("/tarjetas", methods=["POST"])
@login_required
def add_card():
    execute(
        """
        INSERT INTO tarjetas(nombre, limite, tipo, saldo, fecha_corte, fecha_pago)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            request.form.get("nombre", "").strip(),
            parse_float("limite"),
            request.form.get("tipo", "credito"),
            parse_float("saldo"),
            parse_int("fecha_corte"),
            parse_int("fecha_pago"),
        ),
    )
    flash("Tarjeta/cuenta creada.", "success")
    return redirect(url_for("index"))


@app.route("/tarjetas/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_card(item_id):
    execute("DELETE FROM gastos_tarjeta WHERE tarjeta_id = ?", (item_id,))
    execute("DELETE FROM tarjetas WHERE id = ?", (item_id,))
    flash("Tarjeta eliminada.", "success")
    return redirect(url_for("index"))


@app.route("/tarjetas/gasto", methods=["POST"])
@login_required
def add_card_expense():
    tarjeta_id = parse_int("tarjeta_id")
    amount = parse_float("monto")
    card = query("SELECT * FROM tarjetas WHERE id = ?", (tarjeta_id,), one=True)
    if card:
        execute(
            "INSERT INTO gastos_tarjeta(tarjeta_id, monto, fecha, descripcion) VALUES(?, ?, ?, ?)",
            (
                tarjeta_id,
                amount,
                request.form.get("fecha") or today_iso(),
                request.form.get("descripcion", "").strip(),
            ),
        )
        if card["tipo"] == "debito":
            execute("UPDATE tarjetas SET saldo = saldo - ? WHERE id = ?", (amount, tarjeta_id))
        flash("Gasto de tarjeta registrado.", "success")
    return redirect(url_for("index"))


@app.route("/tarjetas/gasto/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_card_expense(item_id):
    row = query(
        """
        SELECT gt.*, t.tipo FROM gastos_tarjeta gt
        JOIN tarjetas t ON t.id = gt.tarjeta_id
        WHERE gt.id = ?
        """,
        (item_id,),
        one=True,
    )
    if row and row["tipo"] == "debito":
        execute("UPDATE tarjetas SET saldo = saldo + ? WHERE id = ?", (row["monto"], row["tarjeta_id"]))
    execute("DELETE FROM gastos_tarjeta WHERE id = ?", (item_id,))
    flash("Gasto de tarjeta eliminado.", "success")
    return redirect(url_for("index"))


@app.route("/eventos", methods=["POST"])
@login_required
def add_event():
    execute(
        "INSERT INTO eventos(nombre, monto, fecha, tipo) VALUES(?, ?, ?, ?)",
        (
            request.form.get("nombre", "").strip(),
            parse_float("monto"),
            request.form.get("fecha") or today_iso(),
            request.form.get("tipo", "recordatorio"),
        ),
    )
    flash("Evento agregado al calendario.", "success")
    return redirect(url_for("index"))


@app.route("/eventos/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_event(item_id):
    execute("DELETE FROM eventos WHERE id = ?", (item_id,))
    flash("Evento eliminado.", "success")
    return redirect(url_for("index"))


@app.route("/api/calendar")
@login_required
def api_calendar():
    month = request.args.get("month")
    try:
        first = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except (TypeError, ValueError):
        first = date.today().replace(day=1)
    next_month = date(first.year + (first.month // 12), (first.month % 12) + 1, 1)
    end = next_month - timedelta(days=1)
    events = [dict(r) for r in query("SELECT * FROM eventos WHERE fecha BETWEEN ? AND ?", (first.isoformat(), end.isoformat()))]
    expenses = [dict(r) for r in query("SELECT id, descripcion nombre, monto, fecha, 'gasto real' tipo FROM gastos WHERE fecha BETWEEN ? AND ?", (first.isoformat(), end.isoformat()))]
    card_expenses = [
        dict(r)
        for r in query(
            """
            SELECT gt.id, COALESCE(gt.descripcion, t.nombre) nombre, gt.monto, gt.fecha, 'tarjeta' tipo
            FROM gastos_tarjeta gt JOIN tarjetas t ON t.id = gt.tarjeta_id
            WHERE gt.fecha BETWEEN ? AND ?
            """,
            (first.isoformat(), end.isoformat()),
        )
    ]
    return jsonify({"events": events + expenses + card_expenses})


@app.route("/export.xlsx")
@login_required
def export_xlsx():
    if Workbook is None:
        flash("Instala openpyxl para exportar Excel: pip install openpyxl", "warning")
        return redirect(url_for("index"))
    wb = Workbook()
    sheets = {
        "resumen": [dashboard_data()],
        "gastos": [dict(r) for r in query("SELECT * FROM gastos ORDER BY fecha DESC")],
        "ingresos": [dict(r) for r in query("SELECT * FROM ingresos ORDER BY fecha DESC")],
        "tarjetas": [dict(r) for r in query("SELECT * FROM tarjetas ORDER BY nombre")],
        "gastos_tarjeta": [dict(r) for r in query("SELECT * FROM gastos_tarjeta ORDER BY fecha DESC")],
        "eventos": [dict(r) for r in query("SELECT * FROM eventos ORDER BY fecha ASC")],
    }
    first = True
    for title, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(title)
        ws.title = title
        first = False
        clean_rows = []
        for row in rows:
            clean_rows.append({k: (str(v) if isinstance(v, (list, dict)) else v) for k, v in row.items()})
        if clean_rows:
            headers = list(clean_rows[0].keys())
            ws.append(headers)
            for row in clean_rows:
                ws.append([row.get(h) for h in headers])
        else:
            ws.append(["Sin datos"])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"finanzas_{today_iso()}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/backup.db")
@login_required
def backup_db():
    init_db()
    return send_file(DB_PATH, as_attachment=True, download_name=f"finanzas_backup_{today_iso()}.db")


@app.route("/backup-now", methods=["POST"])
@login_required
def backup_now():
    init_db()
    path = backup_database("manual")
    flash(f"Respaldo creado: {os.path.basename(path)}", "success")
    return redirect(url_for("index") + "#respaldo-ajustes")


@app.route("/restore", methods=["POST"])
@login_required
def restore_db():
    uploaded = request.files.get("db_file")
    if not uploaded or not uploaded.filename.endswith(".db"):
        flash("Sube un archivo .db valido.", "warning")
        return redirect(url_for("index"))
    close_current_db()
    backup_path = DB_PATH + ".before_restore"
    shutil.copy2(DB_PATH, backup_path)
    uploaded.save(DB_PATH)
    flash("Base restaurada. Se guardo una copia previa junto al proyecto.", "success")
    return redirect(url_for("index"))


@app.route("/reset-demo", methods=["POST"])
@login_required
def reset_demo():
    close_current_db()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    session["logged_in"] = True
    init_db()
    flash("Datos de prueba recargados.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    with app.app_context():
        init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
