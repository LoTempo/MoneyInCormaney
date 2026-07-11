from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.auth import login_required
from app.budget import access_condition, enabled_scopes, scope_is_available
from app.categories import flatten_category_options, get_available_categories
from app.db import get_db
from app.utils import format_money, parse_positive_amount, transaction_type_label


transactions_bp = Blueprint("transactions", __name__)


def get_transaction(transaction_id):
    condition, parameters = access_condition("all")
    transaction = get_db().execute(
        f"""
        SELECT t.id, t.scope, t.family_id, t.user_id, t.category_id,
               t.type, t.amount, t.transaction_date AS date,
               t.description, t.note
        FROM transactions AS t
        WHERE t.id = %s AND {condition}
        """,
        [transaction_id] + parameters,
    ).fetchone()
    if transaction is None:
        abort(404)
    return transaction


def get_category_options():
    return flatten_category_options(get_available_categories())


def resolve_transaction_type():
    form_type = request.form.get("type", "")
    if form_type in {"income", "expense"}:
        return form_type, form_type
    return None, None


def validate_transaction_form(existing=None):
    scope = request.form.get("scope", "personal")
    transaction_type, required_category_type = resolve_transaction_type()
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

    if not scope_is_available(scope):
        return None, "Семейные операции доступны только участникам семьи."
    if existing is not None and scope != existing["scope"]:
        return None, "Область существующей операции изменить нельзя."
    if transaction_type is None:
        return None, "Выберите тип операции."
    if amount is None:
        return None, "Сумма должна быть положительным числом с двумя знаками после запятой."
    if transaction_date is None:
        return None, "Укажите корректную дату."
    if description and (len(description) < 2 or len(description) > 200):
        return None, "Описание должно содержать от 2 до 200 символов или быть пустым."
    if note is not None and len(note) > 2000:
        return None, "Комментарий не должен превышать 2000 символов."

    if scope == "personal":
        category = get_db().execute(
            """
            SELECT id, name, type FROM categories
            WHERE id = %s AND scope = 'personal' AND owner_user_id = %s
            """,
            (category_id, g.user["id"]),
        ).fetchone()
    else:
        category = get_db().execute(
            """
            SELECT id, name, type FROM categories
            WHERE id = %s AND scope = 'family' AND family_id = %s
            """,
            (category_id, g.family["id"]),
        ).fetchone()

    if category is None:
        return None, "Выберите категорию из нужного бюджета."
    if category["type"] != required_category_type:
        return None, "Категория не подходит выбранному типу операции."
    if not description:
        description = category["name"]

    return {
        "scope": scope,
        "family_id": g.family["id"] if scope == "family" else None,
        "type": transaction_type,
        "amount": amount,
        "date": transaction_date,
        "category_id": category_id,
        "description": description,
        "note": note,
    }, None


@transactions_bp.get("/transactions")
@login_required
def transaction_list():
    scopes = enabled_scopes()
    if not scopes:
        flash("Сначала включите личный или семейный бюджет в настройках.", "info")
        return redirect(url_for("settings.settings_view"))

    selected_scope = request.args.get("scope", "all")
    if selected_scope not in {"personal", "family", "all"}:
        selected_scope = "all"
    if selected_scope != "all" and selected_scope not in scopes:
        selected_scope = scopes[0]

    selected_type = request.args.get("type", "")
    month = request.args.get("month", "")
    condition, parameters = access_condition(selected_scope)
    conditions = [condition]

    if selected_type == "income":
        conditions.append("t.type = 'income'")
    elif selected_type == "expense":
        conditions.append("t.type = 'expense'")
    else:
        selected_type = ""

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
        SELECT t.id, t.description, t.transaction_date AS date, t.amount,
               t.type, t.scope, t.user_id, c.name AS category,
               c.color AS category_color,
               u.name AS member, (t.user_id = %s) AS can_edit
        FROM transactions AS t
        JOIN categories AS c ON c.id = t.category_id
        JOIN users AS u ON u.id = t.user_id
        WHERE {' AND '.join(conditions)}
        ORDER BY t.transaction_date DESC, t.created_at DESC
    """
    transactions = get_db().execute(
        query,
        [g.user["id"]] + parameters,
    ).fetchall()

    for transaction in transactions:
        transaction["amount"] = format_money(
            transaction["amount"],
            g.user["currency"],
            transaction["type"],
        )
        transaction["type_label"] = transaction_type_label(transaction["type"])

    return render_template(
        "transactions/list.html",
        transactions=transactions,
        selected_scope=selected_scope,
        selected_type=selected_type,
        selected_month=month,
    )


@transactions_bp.route("/transactions/new", methods=("GET", "POST"))
@login_required
def transaction_create():
    scopes = enabled_scopes()
    if not scopes:
        flash("Сначала включите личный или семейный бюджет в настройках.", "info")
        return redirect(url_for("settings.settings_view"))

    if request.method == "POST":
        data, error = validate_transaction_form()
        if error is not None:
            get_db().rollback()
            flash(error, "danger")
        else:
            database = get_db()
            database.execute(
                """
                INSERT INTO transactions
                    (scope, family_id, user_id, category_id, type, amount,
                     transaction_date, description, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    data["scope"],
                    data["family_id"],
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
        default_scope=scopes[0],
    )


@transactions_bp.route(
    "/transactions/<int:transaction_id>/edit",
    methods=("GET", "POST"),
)
@login_required
def transaction_edit(transaction_id):
    transaction = get_transaction(transaction_id)
    if transaction["user_id"] != g.user["id"]:
        abort(403)

    if request.method == "POST":
        data, error = validate_transaction_form(transaction)
        if error is not None:
            get_db().rollback()
            flash(error, "danger")
        else:
            database = get_db()
            result = database.execute(
                """
                UPDATE transactions
                SET scope = %s, family_id = %s, category_id = %s, type = %s,
                    amount = %s, transaction_date = %s, description = %s,
                    note = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
                """,
                (
                    data["scope"],
                    data["family_id"],
                    data["category_id"],
                    data["type"],
                    data["amount"],
                    data["date"],
                    data["description"],
                    data["note"],
                    transaction_id,
                    g.user["id"],
                ),
            )
            if result.rowcount != 1:
                database.rollback()
                abort(403)
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
@login_required
def transaction_delete(transaction_id):
    transaction = get_transaction(transaction_id)
    if transaction["user_id"] != g.user["id"]:
        abort(403)

    database = get_db()
    result = database.execute(
        "DELETE FROM transactions WHERE id = %s AND user_id = %s",
        (transaction_id, g.user["id"]),
    )
    if result.rowcount != 1:
        database.rollback()
        abort(403)
    database.commit()
    flash("Операция удалена.", "success")
    return redirect(url_for("transactions.transaction_list"))
