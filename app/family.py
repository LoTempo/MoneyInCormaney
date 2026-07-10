import secrets

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from psycopg import errors

from app.auth import login_required
from app.db import get_db


family_bp = Blueprint("family", __name__)


def new_invite_code(database):
    for _ in range(10):
        invite_code = secrets.token_hex(4).upper()
        exists = database.execute(
            "SELECT 1 FROM families WHERE invite_code = %s",
            (invite_code,),
        ).fetchone()
        if exists is None:
            return invite_code
    raise RuntimeError("Could not generate a unique family invitation code.")


def owner_required():
    if g.family is None:
        abort(404)
    if g.family["role"] != "owner":
        abort(403)


@family_bp.get("/family")
@login_required
def family_view():
    if g.family is None:
        return render_template("family/view.html", family=None, members=[])

    members = get_db().execute(
        """
        SELECT u.id, u.name, u.email, u.phone, fm.role,
               (fm.role = 'owner') AS is_owner,
               (u.id = %s) AS is_current_user
        FROM family_members AS fm
        JOIN users AS u ON u.id = fm.user_id
        WHERE fm.family_id = %s
        ORDER BY (fm.role = 'owner') DESC, u.name
        """,
        (g.user["id"], g.family["id"]),
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
        invite_code = new_invite_code(database)
        try:
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
        except errors.UniqueViolation:
            database.rollback()
            flash("Не удалось создать семью. Повторите попытку.", "danger")
            return render_template("family/create.html"), 409

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

        try:
            database.execute(
                """
                INSERT INTO family_members (family_id, user_id, role)
                VALUES (%s, %s, 'member')
                """,
                (family["id"], g.user["id"]),
            )
            database.commit()
        except errors.UniqueViolation:
            database.rollback()
            flash("Вы уже состоите в семье.", "danger")
            return redirect(url_for("family.family_view"))

        flash("Вы присоединились к семейному пространству.", "success")
        return redirect(url_for("family.family_view"))

    return render_template("family/join.html")


@family_bp.post("/family/leave")
@login_required
def family_leave():
    if g.family is None:
        abort(404)
    if g.family["role"] == "owner":
        flash("Владелец должен сначала передать права или удалить семью.", "danger")
        return redirect(url_for("family.family_view"))

    database = get_db()
    database.execute(
        "DELETE FROM family_members WHERE family_id = %s AND user_id = %s",
        (g.family["id"], g.user["id"]),
    )
    database.execute(
        "UPDATE families SET invite_code = %s WHERE id = %s",
        (new_invite_code(database), g.family["id"]),
    )
    database.commit()
    flash("Вы вышли из семьи. Личные данные сохранены.", "success")
    return redirect(url_for("dashboard.index"))


@family_bp.post("/family/members/<int:user_id>/remove")
@login_required
def family_remove_member(user_id):
    owner_required()
    if user_id == g.user["id"]:
        abort(400)

    database = get_db()
    member = database.execute(
        """
        SELECT role FROM family_members
        WHERE family_id = %s AND user_id = %s
        """,
        (g.family["id"], user_id),
    ).fetchone()
    if member is None:
        abort(404)
    if member["role"] == "owner":
        abort(400)

    database.execute(
        "DELETE FROM family_members WHERE family_id = %s AND user_id = %s",
        (g.family["id"], user_id),
    )
    database.execute(
        "UPDATE families SET invite_code = %s WHERE id = %s",
        (new_invite_code(database), g.family["id"]),
    )
    database.commit()
    flash("Участник удалён. Код приглашения обновлён.", "success")
    return redirect(url_for("family.family_view"))


@family_bp.post("/family/members/<int:user_id>/make-owner")
@login_required
def family_transfer_owner(user_id):
    owner_required()
    if user_id == g.user["id"]:
        abort(400)

    database = get_db()
    target = database.execute(
        """
        SELECT role FROM family_members
        WHERE family_id = %s AND user_id = %s
        """,
        (g.family["id"], user_id),
    ).fetchone()
    if target is None:
        abort(404)

    database.execute(
        """
        UPDATE family_members SET role = 'member'
        WHERE family_id = %s AND user_id = %s
        """,
        (g.family["id"], g.user["id"]),
    )
    database.execute(
        """
        UPDATE family_members SET role = 'owner'
        WHERE family_id = %s AND user_id = %s
        """,
        (g.family["id"], user_id),
    )
    database.execute(
        "UPDATE families SET created_by = %s WHERE id = %s",
        (user_id, g.family["id"]),
    )
    database.commit()
    flash("Права владельца переданы.", "success")
    return redirect(url_for("family.family_view"))


@family_bp.post("/family/dissolve")
@login_required
def family_dissolve():
    owner_required()
    confirmation = request.form.get("family_name", "").strip()
    if confirmation != g.family["name"]:
        flash("Для удаления точно введите название семьи.", "danger")
        return redirect(url_for("family.family_view"))

    database = get_db()
    database.execute("DELETE FROM families WHERE id = %s", (g.family["id"],))
    database.commit()
    flash("Семейное пространство и его общие данные удалены.", "success")
    return redirect(url_for("dashboard.index"))
