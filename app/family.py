from flask import Blueprint, flash, redirect, render_template, request, url_for


family_bp = Blueprint("family", __name__)


@family_bp.get("/family")
def family_view():
    family = {
        "name": "Семья Ивановых",
        "invite_code": "DEMO-2026",
    }
    members = [
        {
            "name": "Анна Иванова",
            "email": "anna@example.com",
            "is_owner": True,
        },
        {
            "name": "Михаил Иванов",
            "email": "mikhail@example.com",
            "is_owner": False,
        },
    ]
    return render_template("family/view.html", family=family, members=members)


@family_bp.route("/family/create", methods=("GET", "POST"))
def family_create():
    if request.method == "POST":
        flash("Пробный режим: семья пока не сохранена.", "success")
        return redirect(url_for("family.family_view"))

    return render_template("family/create.html")


@family_bp.route("/family/join", methods=("GET", "POST"))
def family_join():
    if request.method == "POST":
        flash("Пробный режим: код принят, но вступление пока не сохранено.", "success")
        return redirect(url_for("family.family_view"))

    return render_template("family/join.html")
