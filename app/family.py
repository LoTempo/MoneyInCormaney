import secrets

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app.auth import family_required, login_required
from app.db import get_db


family_bp = Blueprint("family", __name__)


@family_bp.get("/family")
@family_required
def family_view():
    members = get_db().execute(
        """
        SELECT u.name, u.email, u.phone, fm.role,
               (fm.role = 'owner') AS is_owner
        FROM family_members AS fm
        JOIN users AS u ON u.id = fm.user_id
        WHERE fm.family_id = %s
        ORDER BY (fm.role = 'owner') DESC, u.name
        """,
        (g.family["id"],),
    ).fetchall()
    return render_template("family/view.html", family=g.family, members=members)


@family_bp.route("/family/create", methods=("GET", "POST"))
@login_required
def family_create():
    if g.family is not None:
        return redirect(url_for("family.family_view"))

    if request.method == "POST":
        name = request.form.get("family_name", "").strip()
        if len(name) < 2 or len(name) > 100:
            flash("Название семьи должно содержать от 2 до 100 символов.", "danger")
            return render_template("family/create.html"), 400

        database = get_db()
        for _ in range(5):
            invite_code = secrets.token_hex(4).upper()
            exists = database.execute(
                "SELECT 1 FROM families WHERE invite_code = %s",
                (invite_code,),
            ).fetchone()
            if exists is None:
                break
        else:
            flash("Не удалось создать код приглашения. Попробуйте ещё раз.", "danger")
            return render_template("family/create.html"), 500

        family = database.execute(
            """
            INSERT INTO families (name, invite_code, created_by)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (name, invite_code, g.user["id"]),
        ).fetchone()
        database.execute(
            """
            INSERT INTO family_members (family_id, user_id, role)
            VALUES (%s, %s, 'owner')
            """,
            (family["id"], g.user["id"]),
        )
        database.commit()
        flash("Семейное пространство создано.", "success")
        return redirect(url_for("family.family_view"))

    return render_template("family/create.html")


@family_bp.route("/family/join", methods=("GET", "POST"))
@login_required
def family_join():
    if g.family is not None:
        return redirect(url_for("family.family_view"))

    if request.method == "POST":
        invite_code = request.form.get("invite_code", "").strip().upper().replace("-", "")
        database = get_db()
        family = database.execute(
            "SELECT id FROM families WHERE invite_code = %s",
            (invite_code,),
        ).fetchone()

        if family is None:
            flash("Семья с таким кодом не найдена.", "danger")
            return render_template("family/join.html"), 404

        database.execute(
            """
            INSERT INTO family_members (family_id, user_id, role)
            VALUES (%s, %s, 'member')
            """,
            (family["id"], g.user["id"]),
        )
        database.commit()
        flash("Вы присоединились к семейному пространству.", "success")
        return redirect(url_for("family.family_view"))

    return render_template("family/join.html")
