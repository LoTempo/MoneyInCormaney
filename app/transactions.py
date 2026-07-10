from flask import Blueprint, abort, flash, redirect, render_template, request, url_for


transactions_bp = Blueprint("transactions", __name__)


DEMO_CATEGORIES = [
    {"id": 1, "name": "Продукты"},
    {"id": 2, "name": "Транспорт"},
    {"id": 3, "name": "Связь"},
    {"id": 4, "name": "Зарплата"},
]

DEMO_TRANSACTIONS = [
    {
        "id": 1,
        "description": "Продукты на неделю",
        "category": "Продукты",
        "category_id": 1,
        "member": "Анна",
        "date": "2026-07-10",
        "amount": "−4 850,00 ₽",
        "type": "expense",
        "note": "Пробная операция",
    },
    {
        "id": 2,
        "description": "Заработная плата",
        "category": "Зарплата",
        "category_id": 4,
        "member": "Михаил",
        "date": "2026-07-05",
        "amount": "+85 000,00 ₽",
        "type": "income",
        "note": "Пробная операция",
    },
]


@transactions_bp.get("/transactions")
def transaction_list():
    return render_template(
        "transactions/list.html",
        transactions=DEMO_TRANSACTIONS,
    )


@transactions_bp.route("/transactions/new", methods=("GET", "POST"))
def transaction_create():
    if request.method == "POST":
        flash("Пробный режим: операция получена, но пока не сохранена.", "success")
        return redirect(url_for("transactions.transaction_list"))

    return render_template(
        "transactions/form.html",
        categories=DEMO_CATEGORIES,
    )


@transactions_bp.route(
    "/transactions/<int:transaction_id>/edit",
    methods=("GET", "POST"),
)
def transaction_edit(transaction_id):
    transaction = next(
        (item for item in DEMO_TRANSACTIONS if item["id"] == transaction_id),
        None,
    )

    if transaction is None:
        abort(404)

    if request.method == "POST":
        flash("Пробный режим: изменения получены, но пока не сохранены.", "success")
        return redirect(url_for("transactions.transaction_list"))

    return render_template(
        "transactions/form.html",
        transaction=transaction,
        categories=DEMO_CATEGORIES,
    )
