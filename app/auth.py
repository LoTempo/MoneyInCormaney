from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from psycopg import errors
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db
from app.utils import normalize_phone, valid_phone


auth_bp = Blueprint("auth", __name__)


@auth_bp.before_app_request
def load_logged_in_user():
    g.user = None
    g.family = None
    user_id = session.get("user_id")

    if user_id is None:
        return

    row = get_db().execute(
        """
        SELECT u.id, u.name, u.email, u.phone, u.currency, u.week_start,
               f.id AS family_id, f.name AS family_name,
               f.invite_code, fm.role AS family_role
        FROM users AS u
        LEFT JOIN family_members AS fm ON fm.user_id = u.id
        LEFT JOIN families AS f ON f.id = fm.family_id
        WHERE u.id = %s
        ORDER BY fm.joined_at
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    if row is None:
        session.clear()
        return

    g.user = {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "currency": row["currency"],
        "week_start": row["week_start"],
    }
    if row["family_id"] is not None:
        g.family = {
            "id": row["family_id"],
            "name": row["family_name"],
            "invite_code": row["invite_code"],
            "role": row["family_role"],
        }


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)

    return wrapped_view


@auth_bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, password_hash FROM users WHERE LOWER(email) = %s",
            (email,),
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Неверная электронная почта или пароль.", "danger")
            return render_template("auth/login.html"), 401

        session.clear()
        session["user_id"] = user["id"]
        session.permanent = request.form.get("remember") == "on"

        next_url = request.args.get("next", "")
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = url_for("dashboard.index")
        return redirect(next_url)

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone_input = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        error = None
        if len(name) < 2 or len(name) > 100:
            error = "Имя должно содержать от 2 до 100 символов."
        elif "@" not in email or len(email) > 254:
            error = "Введите корректную электронную почту."
        elif not valid_phone(phone_input):
            error = "Введите номер в формате +7 XXX XXX-XX-XX."
        elif len(password) < 8:
            error = "Пароль должен содержать не менее 8 символов."
        elif password != password_confirm:
            error = "Пароли не совпадают."
        elif request.form.get("agreement") != "on":
            error = "Необходимо принять правила использования сервиса."

        if error is not None:
            flash(error, "danger")
            return render_template("auth/register.html"), 400

        phone = normalize_phone(phone_input)

        database = get_db()
        try:
            user = database.execute(
                """
                INSERT INTO users (name, email, phone, password_hash)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (name, email, phone, generate_password_hash(password)),
            ).fetchone()
            database.commit()
        except errors.UniqueViolation:
            database.rollback()
            flash("Пользователь с такой почтой уже зарегистрирован.", "danger")
            return render_template("auth/register.html"), 409

        session.clear()
        session["user_id"] = user["id"]
        session.permanent = True
        flash("Аккаунт создан. Личный бюджет уже готов к работе.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/register.html")


@auth_bp.post("/logout")
@login_required
def logout():
    session.clear()
    flash("Вы вышли из аккаунта.", "success")
    return redirect(url_for("auth.login"))
