import re

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from psycopg import errors

from app.auth import family_required
from app.db import get_db


categories_bp = Blueprint("categories", __name__)


def get_family_categories():
    return get_db().execute(
        """
        SELECT id, parent_id, name, type, icon, color
        FROM categories
        WHERE family_id = %s
        ORDER BY type, LOWER(name)
        """,
        (g.family["id"],),
    ).fetchall()


def build_category_tree(categories):
    nodes = {
        category["id"]: {**category, "children": []}
        for category in categories
    }
    roots = []

    for node in nodes.values():
        parent = nodes.get(node["parent_id"])
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)

    return roots


def flatten_category_options(categories, excluded_id=None):
    options = []

    def visit(nodes, depth=0):
        for node in nodes:
            if node["id"] == excluded_id:
                continue
            options.append(
                {
                    **node,
                    "display_name": f"{'— ' * depth}{node['name']}",
                    "depth": depth,
                }
            )
            visit(node["children"], depth + 1)

    visit(build_category_tree(categories))
    return options


def get_category(category_id):
    category = get_db().execute(
        """
        SELECT id, parent_id, name, type, icon, color
        FROM categories
        WHERE id = %s AND family_id = %s
        """,
        (category_id, g.family["id"]),
    ).fetchone()
    if category is None:
        abort(404)
    return category


def validate_category_form(category_id=None):
    name = request.form.get("name", "").strip()
    category_type = request.form.get("type", "")
    icon = request.form.get("icon", "").strip() or None
    color = request.form.get("color", "#2563eb").lower()
    parent_raw = request.form.get("parent_id", "").strip()
    try:
        parent_id = int(parent_raw) if parent_raw else None
    except ValueError:
        parent_id = None

    if len(name) < 2 or len(name) > 80:
        return None, "Название должно содержать от 2 до 80 символов."
    if category_type not in {"income", "expense"}:
        return None, "Выберите тип категории."
    if icon is not None and len(icon) > 2:
        return None, "Символ категории должен содержать не более 2 знаков."
    if re.fullmatch(r"#[0-9a-f]{6}", color) is None:
        return None, "Выберите корректный цвет."

    categories = get_family_categories()
    by_id = {category["id"]: category for category in categories}

    if category_id is not None:
        original = by_id.get(category_id)
        type_is_changing = original is not None and original["type"] != category_type
        if type_is_changing:
            has_children = any(
                category["parent_id"] == category_id
                for category in categories
            )
            has_transactions = get_db().execute(
                "SELECT 1 FROM transactions WHERE category_id = %s LIMIT 1",
                (category_id,),
            ).fetchone()
            if has_children or has_transactions is not None:
                return None, (
                    "Нельзя изменить тип категории с подкатегориями или операциями."
                )

    if parent_id is not None:
        parent = by_id.get(parent_id)
        if parent is None:
            return None, "Родительская категория не найдена."
        if parent["type"] != category_type:
            return None, "Категория и подкатегория должны иметь одинаковый тип."

        current = parent
        while current is not None:
            if current["id"] == category_id:
                return None, "Нельзя переместить категорию внутрь самой себя."
            current = by_id.get(current["parent_id"])

    return {
        "name": name,
        "type": category_type,
        "icon": icon,
        "color": color,
        "parent_id": parent_id,
    }, None


@categories_bp.get("/categories")
@family_required
def category_list():
    categories = build_category_tree(get_family_categories())
    return render_template("categories/list.html", categories=categories)


@categories_bp.route("/categories/new", methods=("GET", "POST"))
@family_required
def category_create():
    if request.method == "POST":
        data, error = validate_category_form()
        if error is not None:
            flash(error, "danger")
        else:
            database = get_db()
            try:
                database.execute(
                    """
                    INSERT INTO categories
                        (family_id, parent_id, name, type, icon, color)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        g.family["id"],
                        data["parent_id"],
                        data["name"],
                        data["type"],
                        data["icon"],
                        data["color"],
                    ),
                )
                database.commit()
                flash("Категория создана.", "success")
                return redirect(url_for("categories.category_list"))
            except errors.UniqueViolation:
                database.rollback()
                flash("Категория с таким названием уже существует на этом уровне.", "danger")

    return render_template(
        "categories/form.html",
        parent_options=flatten_category_options(get_family_categories()),
    )


@categories_bp.route(
    "/categories/<int:category_id>/edit",
    methods=("GET", "POST"),
)
@family_required
def category_edit(category_id):
    category = get_category(category_id)

    if request.method == "POST":
        data, error = validate_category_form(category_id)
        if error is not None:
            flash(error, "danger")
        else:
            database = get_db()
            try:
                database.execute(
                    """
                    UPDATE categories
                    SET parent_id = %s, name = %s, type = %s, icon = %s, color = %s
                    WHERE id = %s AND family_id = %s
                    """,
                    (
                        data["parent_id"],
                        data["name"],
                        data["type"],
                        data["icon"],
                        data["color"],
                        category_id,
                        g.family["id"],
                    ),
                )
                database.commit()
                flash("Категория обновлена.", "success")
                return redirect(url_for("categories.category_list"))
            except errors.UniqueViolation:
                database.rollback()
                flash("Категория с таким названием уже существует на этом уровне.", "danger")

    return render_template(
        "categories/form.html",
        category=category,
        parent_options=flatten_category_options(
            get_family_categories(),
            excluded_id=category_id,
        ),
    )


@categories_bp.post("/categories/<int:category_id>/delete")
@family_required
def category_delete(category_id):
    get_category(category_id)
    database = get_db()
    usage = database.execute(
        """
        SELECT
            EXISTS(SELECT 1 FROM categories WHERE parent_id = %s) AS has_children,
            EXISTS(SELECT 1 FROM transactions WHERE category_id = %s) AS has_transactions
        """,
        (category_id, category_id),
    ).fetchone()

    if usage["has_children"]:
        flash("Сначала удалите или перенесите подкатегории.", "danger")
    elif usage["has_transactions"]:
        flash("Нельзя удалить категорию, которая используется в операциях.", "danger")
    else:
        database.execute(
            "DELETE FROM categories WHERE id = %s AND family_id = %s",
            (category_id, g.family["id"]),
        )
        database.commit()
        flash("Категория удалена.", "success")

    return redirect(url_for("categories.category_list"))
