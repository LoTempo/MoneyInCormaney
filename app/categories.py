from flask import Blueprint, abort, flash, redirect, render_template, request, url_for


categories_bp = Blueprint("categories", __name__)


DEMO_CATEGORIES = [
    {"id": 1, "name": "Продукты", "type": "expense", "icon": "П", "color": "#2563eb"},
    {"id": 2, "name": "Транспорт", "type": "expense", "icon": "Т", "color": "#3b82f6"},
    {"id": 3, "name": "Связь", "type": "expense", "icon": "С", "color": "#60a5fa"},
    {"id": 4, "name": "Зарплата", "type": "income", "icon": "₽", "color": "#15803d"},
]


@categories_bp.get("/categories")
def category_list():
    return render_template(
        "categories/list.html",
        categories=DEMO_CATEGORIES,
    )


@categories_bp.route("/categories/new", methods=("GET", "POST"))
def category_create():
    if request.method == "POST":
        flash("Пробный режим: категория получена, но пока не сохранена.", "success")
        return redirect(url_for("categories.category_list"))

    return render_template("categories/form.html")


@categories_bp.route(
    "/categories/<int:category_id>/edit",
    methods=("GET", "POST"),
)
def category_edit(category_id):
    category = next(
        (item for item in DEMO_CATEGORIES if item["id"] == category_id),
        None,
    )

    if category is None:
        abort(404)

    if request.method == "POST":
        flash("Пробный режим: изменения получены, но пока не сохранены.", "success")
        return redirect(url_for("categories.category_list"))

    return render_template("categories/form.html", category=category)
