"""CardioSense AI - main Flask application."""
import json
import os
import sqlite3
import uuid
from datetime import timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (Flask, Response, flash, g, redirect, render_template,
                   request, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from utils.predict import predict_risk
from utils.ocr import ALLOWED_EXTENSIONS, extract_text, parse_values
from utils.report import build_report, report_id
from utils.timefmt import format_dt, is_valid_zone, to_local

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "cardiosense.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.permanent_session_lifetime = timedelta(days=30)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB uploads


@app.template_filter("local_dt")
def local_dt(utc_text):
    """Show a stored UTC time in the user's own timezone."""
    return format_dt(to_local(utc_text, session.get("tz")))


# ---------- Database ----------
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


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                source TEXT NOT NULL DEFAULT 'manual',
                inputs TEXT NOT NULL,
                risk REAL NOT NULL,
                label TEXT NOT NULL,
                flags TEXT NOT NULL,
                bmi REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ---------- Routes ----------
@app.route("/")
def index():
    return redirect(url_for("check") if "user_id" in session else url_for("login"))


@app.route("/sw.js")
def service_worker():
    """Served from the root so it can control the whole app."""
    response = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/offline")
def offline():
    return render_template("offline.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.permanent = bool(request.form.get("remember"))
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            zone = request.form.get("tz", "")
            if is_valid_zone(zone):
                session["tz"] = zone
            return redirect(url_for("check"))
        flash("Wrong email or password.", "error")
    return render_template("login.html", mode="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if "@" not in email:
            flash("Please enter a valid email.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                    (email, generate_password_hash(password)),
                )
                db.commit()
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("An account with this email already exists.", "error")
    return render_template("login.html", mode="register")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# Allowed ranges match the data the model was trained on.
NUMBER_FIELDS = {
    "age": ("Age", 18, 100),
    "height": ("Height", 120, 220),
    "weight": ("Weight", 30, 200),
    "systolic": ("Systolic BP", 80, 250),
    "diastolic": ("Diastolic BP", 40, 150),
    "cholesterol": ("Cholesterol", 80, 500),
    "glucose": ("Glucose", 40, 500),
}


def read_health_form(form):
    """Validate the health form. Returns (values, errors)."""
    values, errors = {}, []
    for key, (label, low, high) in NUMBER_FIELDS.items():
        raw = form.get(key, "").strip().replace(",", ".")
        try:
            number = float(raw)
        except ValueError:
            errors.append(f"{label} is missing or not a number.")
            continue
        if not low <= number <= high:
            errors.append(f"{label} must be between {low} and {high}.")
        values[key] = number
    if "systolic" in values and "diastolic" in values \
            and values["diastolic"] >= values["systolic"]:
        errors.append("Diastolic BP must be lower than systolic BP.")
    values["gender"] = "male" if form.get("gender") == "male" else "female"
    values["smoke"] = form.get("smoke") == "yes"
    values["alcohol"] = form.get("alcohol") == "yes"
    values["activity"] = form.get("activity", "low")
    return values, errors


@app.route("/check", methods=["GET", "POST"])
@login_required
def check():
    values = {}
    if request.method == "POST":
        values, errors = read_health_form(request.form)
        source = "report" if request.form.get("source") == "report" else "manual"
        if source == "report" and not request.form.get("confirmed"):
            errors.append("Please confirm that you have checked the values.")
        if errors:
            for message in errors:
                flash(message, "error")
            if source == "report":
                return render_template("confirm.html", values=values, found=[],
                                       method=request.form.get("method", ""))
        else:
            result = predict_risk(
                age=values["age"], gender=values["gender"],
                height_cm=values["height"], weight_kg=values["weight"],
                systolic=values["systolic"], diastolic=values["diastolic"],
                cholesterol_mg=values["cholesterol"], glucose_mg=values["glucose"],
                smoke=values["smoke"], alcohol=values["alcohol"],
                active=values["activity"] != "low",
            )
            db = get_db()
            cursor = db.execute(
                """INSERT INTO predictions
                   (user_id, source, inputs, risk, label, flags, bmi)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session["user_id"], source, json.dumps(values), result["risk"],
                 result["label"], json.dumps(result["flags"]), result["bmi"]),
            )
            db.commit()
            return redirect(url_for("result", prediction_id=cursor.lastrowid))
    return render_template("check.html", values=values)


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("report")
    if not file or not file.filename:
        flash("Please choose a PDF or photo of your blood report.", "error")
        return redirect(url_for("check"))
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        flash("Only PDF, PNG, JPG or WEBP files are supported.", "error")
        return redirect(url_for("check"))

    # Save with a random name, read it, then delete it right away (privacy).
    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{extension}"
    file.save(temp_path)
    try:
        text, method = extract_text(temp_path)
    except Exception:
        app.logger.exception("Could not read report")
        flash("Sorry, we could not read that file. Try a clearer photo or a PDF.", "error")
        return redirect(url_for("check"))
    finally:
        temp_path.unlink(missing_ok=True)

    found = parse_values(text)
    if not found:
        flash("We could not find any values in this report. Please enter them by hand.", "error")
        return redirect(url_for("check"))
    return render_template("confirm.html", values=found, found=list(found), method=method)


@app.errorhandler(413)
def too_large(_error):
    flash("That file is too big. The limit is 10 MB.", "error")
    return redirect(url_for("check"))


def load_prediction(prediction_id):
    """Fetch one prediction, only if it belongs to the logged-in user."""
    row = get_db().execute(
        "SELECT * FROM predictions WHERE id = ? AND user_id = ?",
        (prediction_id, session["user_id"]),
    ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["inputs"] = json.loads(item["inputs"])
    item["flags"] = json.loads(item["flags"])
    return item


@app.route("/result/<int:prediction_id>")
@login_required
def result(prediction_id):
    item = load_prediction(prediction_id)
    if item is None:
        flash("That result was not found.", "error")
        return redirect(url_for("history"))
    return render_template("result.html", p=item)


@app.route("/result/<int:prediction_id>/pdf")
@login_required
def result_pdf(prediction_id):
    item = load_prediction(prediction_id)
    if item is None:
        flash("That result was not found.", "error")
        return redirect(url_for("history"))
    pdf = build_report(item, session["email"], session.get("tz"))
    local_date = to_local(item["created_at"], session.get("tz")).strftime("%Y-%m-%d")
    filename = f"CardioSense_Report_{report_id(item)}_{local_date}.pdf"
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.route("/history")
@login_required
def history():
    rows = get_db().execute(
        "SELECT id, source, risk, label, created_at FROM predictions "
        "WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    return render_template("history.html", rows=rows)


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
