from flask import Blueprint, flash, redirect, render_template, request, url_for


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        flash(
            "Пробный режим: вход будет подключён после создания базы данных.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        flash(
            "Пробный режим: регистрация будет подключена после создания базы данных.",
            "success",
        )
        return redirect(url_for("auth.register"))

    return render_template("auth/register.html")
