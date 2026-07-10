from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.auth import family_required
from app.categories import flatten_category_options, get_family_categories
from app.db import get_db
from app.utils import format_money, parse_positive_amount


transactions_bp = Blueprint("transactions", __name__)


def get_transaction(transaction_id):
    transaction = get_db().execute(
        """
        SELECT id, category_id, type, amount, transaction_date AS date,
               description, note
        FROM transactions
        WHERE id = %s AND family_id = %s
        """,
        (transaction_id, g.family["id"]),
    ).fetchone()
    if transaction is None:
        abort(404)
    return transaction


def get_category_options():
    return flatten_category_options(get_family_categories())


def validate_transaction_form():
    transaction_type = request.form.get("type", "")
    amount = parse_positive_amount(request.form.get("amount"))
    date_raw = request.form.get("date", "")
    category_raw = request.form.get("category_id", "")
    try:
        category_id = int(category_raw) if category_raw else None
    except ValueError:
        category_id = None
    description = request.form.get("description", "").strip()
    note = request.form.get("note", "").strip() or None

    try:
        transaction_date = date.fromisoformat(date_raw)
    except ValueError:
        transaction_date = None

    if transaction_type not in {"income", "expense"}:
        return None, "Выберите тип операции."
    if amount is None:
        return None, "Сумма должна быть положительным числом с двумя знаками после запятой."
    if transaction_date is None:
        return None, "Укажите корректную дату."
    if len(description) < 2 or len(description) > 200:
        return None, "Описание должно содержать от 2 до 200 символов."
    if note is not None and len(note) > 2000:
        return None, "Комментарий не должен превышать 2000 символов."

    category = get_db().execute(
        """
        SELECT id, type
        FROM categories
        WHERE id = %s AND family_id = %s
        """,
        (category_id, g.family["id"]),
    ).fetchone()
    if category is None:
        return None, "Выберите категорию."
    if category["type"] != transaction_type:
        return None, "Тип категории не совпадает с типом операции."

    return {
        "type": transaction_type,
        "amount": amount,
        "date": transaction_date,
        "category_id": category_id,
        "description": description,
        "note": note,
    }, None


@transactions_bp.get("/transactions")
@family_required
def transaction_list():
    transaction_type = request.args.get("type", "")
    month = request.args.get("month", "")
    conditions = ["t.family_id = %s"]
    parameters = [g.family["id"]]

    if transaction_type in {"income", "expense"}:
        conditions.append("t.type = %s")
        parameters.append(transaction_type)

    if month:
        try:
            month_start = date.fromisoformat(f"{month}-01")
            next_month = (
                date(month_start.year + 1, 1, 1)
                if month_start.month == 12
                else date(month_start.year, month_start.month + 1, 1)
            )
            conditions.extend(
                ["t.transaction_date >= %s", "t.transaction_date < %s"]
            )
            parameters.extend([month_start, next_month])
        except ValueError:
            month = ""

    query = f"""
        SELECT t.id, t.description, t.transaction_date AS date, t.amount, t.type,
               c.name AS category, u.name AS member
        FROM transactions AS t
        JOIN categories AS c ON c.id = t.category_id
        JOIN users AS u ON u.id = t.user_id
        WHERE {' AND '.join(conditions)}
        ORDER BY t.transaction_date DESC, t.created_at DESC
    """
    transactions = get_db().execute(query, parameters).fetchall()

    for transaction in transactions:
        transaction["amount"] = format_money(
            transaction["amount"],
            g.user["currency"],
            transaction["type"],
        )

    return render_template(
        "transactions/list.html",
        transactions=transactions,
        selected_type=transaction_type,
        selected_month=month,
    )


@transactions_bp.route("/transactions/new", methods=("GET", "POST"))
@family_required
def transaction_create():
    if request.method == "POST":
        data, error = validate_transaction_form()
        if error is not None:
            flash(error, "danger")
        else:
            database = get_db()
            database.execute(
                """
                INSERT INTO transactions
                    (family_id, user_id, category_id, type, amount,
                     transaction_date, description, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    g.family["id"],
                    g.user["id"],
                    data["category_id"],
                    data["type"],
                    data["amount"],
                    data["date"],
                    data["description"],
                    data["note"],
                ),
            )
            database.commit()
            flash("Операция добавлена.", "success")
            return redirect(url_for("transactions.transaction_list"))

    return render_template(
        "transactions/form.html",
        categories=get_category_options(),
        today=date.today().isoformat(),
    )


@transactions_bp.route(
    "/transactions/<int:transaction_id>/edit",
    methods=("GET", "POST"),
)
@family_required
def transaction_edit(transaction_id):
    transaction = get_transaction(transaction_id)

    if request.method == "POST":
        data, error = validate_transaction_form()
        if error is not None:
            flash(error, "danger")
        else:
            database = get_db()
            database.execute(
                """
                UPDATE transactions
                SET category_id = %s, type = %s, amount = %s,
                    transaction_date = %s, description = %s, note = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND family_id = %s
                """,
                (
                    data["category_id"],
                    data["type"],
                    data["amount"],
                    data["date"],
                    data["description"],
                    data["note"],
                    transaction_id,
                    g.family["id"],
                ),
            )
            database.commit()
            flash("Операция обновлена.", "success")
            return redirect(url_for("transactions.transaction_list"))

    return render_template(
        "transactions/form.html",
        transaction=transaction,
        categories=get_category_options(),
        today=date.today().isoformat(),
    )


@transactions_bp.post("/transactions/<int:transaction_id>/delete")
@family_required
def transaction_delete(transaction_id):
    get_transaction(transaction_id)
    database = get_db()
    database.execute(
        "DELETE FROM transactions WHERE id = %s AND family_id = %s",
        (transaction_id, g.family["id"]),
    )
    database.commit()
    flash("Операция удалена.", "success")
    return redirect(url_for("transactions.transaction_list"))
