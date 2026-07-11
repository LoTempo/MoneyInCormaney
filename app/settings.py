from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from psycopg import errors
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import login_required
from app.db import get_db
from app.utils import normalize_phone, valid_phone


settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=("GET", "POST"))
@login_required
def settings_view():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone_input = request.form.get("phone", "").strip()
        currency = request.form.get("currency", "")
        week_start = request.form.get("week_start", "")
        personal_budget_enabled = (
            request.form.get("personal_budget_enabled") == "on"
        )
        family_budget_enabled = request.form.get("family_budget_enabled") == "on"

        error = None
        if len(name) < 2 or len(name) > 100:
            error = "Имя должно содержать от 2 до 100 символов."
        elif "@" not in email or len(email) > 254:
            error = "Введите корректную электронную почту."
        elif not valid_phone(phone_input):
            error = "Введите номер в формате +7 XXX XXX-XX-XX."
        elif currency not in {"RUB", "USD", "EUR"}:
            error = "Выберите поддерживаемую валюту."
        elif week_start not in {"monday", "sunday"}:
            error = "Выберите начало недели."

        if error is not None:
            flash(error, "danger")
        else:
            phone = normalize_phone(phone_input)
            database = get_db()
            try:
                database.execute(
                    """
                    UPDATE users
                    SET name = %s, email = %s, phone = %s, currency = %s,
                        week_start = %s, personal_budget_enabled = %s,
                        family_budget_enabled = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        name,
                        email,
                        phone,
                        currency,
                        week_start,
                        personal_budget_enabled,
                        family_budget_enabled,
                        g.user["id"],
                    ),
                )
                database.commit()
                flash("Настройки сохранены.", "success")
                return redirect(url_for("settings.settings_view"))
            except errors.UniqueViolation:
                database.rollback()
                flash("Эта электронная почта уже используется.", "danger")

    return render_template("settings/index.html", user=g.user)


@settings_bp.post("/settings/password")
@login_required
def password_change():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    new_password_confirm = request.form.get("new_password_confirm", "")
    database = get_db()
    user = database.execute(
        "SELECT password_hash FROM users WHERE id = %s",
        (g.user["id"],),
    ).fetchone()

    if not check_password_hash(user["password_hash"], current_password):
        flash("Текущий пароль указан неверно.", "danger")
    elif len(new_password) < 8:
        flash("Новый пароль должен содержать не менее 8 символов.", "danger")
    elif new_password != new_password_confirm:
        flash("Новые пароли не совпадают.", "danger")
    else:
        database.execute(
            """
            UPDATE users
            SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (generate_password_hash(new_password), g.user["id"]),
        )
        database.commit()
        flash("Пароль изменён.", "success")

    return redirect(url_for("settings.settings_view"))
