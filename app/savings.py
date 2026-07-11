from flask import Blueprint, abort, flash, g, redirect, request, url_for

from app.auth import login_required
from app.budget import savings_access_condition, scope_is_available
from app.db import get_db
from app.utils import parse_positive_amount


savings_bp = Blueprint("savings", __name__)


def lock_and_get_balance(scope):
    database = get_db()
    if scope == "personal":
        database.execute(
            "SELECT id FROM users WHERE id = %s FOR UPDATE",
            (g.user["id"],),
        )
    else:
        database.execute(
            "SELECT id FROM families WHERE id = %s FOR UPDATE",
            (g.family["id"],),
        )

    condition, parameters = savings_access_condition(scope)
    row = database.execute(
        f"""
        SELECT COALESCE(SUM(
            CASE
                WHEN entry_type = 'deposit' THEN amount
                WHEN entry_type = 'withdrawal' THEN -amount
                ELSE 0
            END
        ), 0) AS balance
        FROM savings_entries AS s
        WHERE {condition}
        """,
        parameters,
    ).fetchone()
    return row["balance"]


@savings_bp.post("/savings/<scope>/change")
@login_required
def change(scope):
    if scope not in {"personal", "family"} or not scope_is_available(scope):
        abort(404)

    entry_type = request.form.get("entry_type", "")
    amount = parse_positive_amount(request.form.get("amount"))
    reason = request.form.get("reason", "").strip()

    error = None
    if entry_type not in {"deposit", "withdrawal"}:
        error = "Выберите пополнение или трату."
    elif amount is None:
        error = "Введите положительную сумму с двумя знаками после запятой."
    elif len(reason) < 2 or len(reason) > 200:
        error = "Причина должна содержать от 2 до 200 символов."

    database = get_db()
    if error is None:
        balance = lock_and_get_balance(scope)
        if entry_type == "withdrawal" and amount > balance:
            error = "Недостаточно сбережений для этой траты."

    if error is not None:
        database.rollback()
        flash(error, "danger")
    else:
        database.execute(
            """
            INSERT INTO savings_entries
                (scope, family_id, user_id, entry_type, amount, reason)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                scope,
                g.family["id"] if scope == "family" else None,
                g.user["id"],
                entry_type,
                amount,
                reason,
            ),
        )
        database.commit()
        flash(
            "Сбережения пополнены."
            if entry_type == "deposit"
            else "Трата из сбережений сохранена.",
            "success",
        )

    return_to = request.form.get("return_to", "home")
    targets = {
        "home": url_for("dashboard.index"),
        "personal": url_for("dashboard.personal_budget"),
        "family": url_for("dashboard.family_budget"),
    }
    return redirect(targets.get(return_to, targets["home"]))
