from flask import Blueprint, flash, redirect, render_template, request, url_for


settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=("GET", "POST"))
def settings_view():
    if request.method == "POST":
        flash("Пробный режим: настройки получены, но пока не сохранены.", "success")
        return redirect(url_for("settings.settings_view"))

    user = {
        "name": "Анна Иванова",
        "email": "anna@example.com",
    }
    return render_template("settings/index.html", user=user)


@settings_bp.get("/settings/password")
def password_change():
    flash("Изменение пароля будет добавлено вместе с авторизацией.", "success")
    return redirect(url_for("settings.settings_view"))
