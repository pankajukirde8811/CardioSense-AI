"""CardioSense AI - main Flask application."""
import json
import os
import sqlite3
from datetime import timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from utils.predict import predict_risk

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "cardiosense.db"

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.permanent_session_lifetime = timedelta(days=30)


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
        if errors:
            for message in errors:
                flash(message, "error")
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
                   VALUES (?, 'manual', ?, ?, ?, ?, ?)""",
                (session["user_id"], json.dumps(values), result["risk"],
                 result["label"], json.dumps(result["flags"]), result["bmi"]),
            )
            db.commit()
            return redirect(url_for("result", prediction_id=cursor.lastrowid))
    return render_template("check.html", values=values)


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
