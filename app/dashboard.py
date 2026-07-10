from flask import Blueprint, render_template


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    recent_transactions = [
        {
            "description": "Продукты на неделю",
            "category": "Продукты",
            "date": "10 июля 2026",
            "amount": "−4 850,00 ₽",
            "type": "expense",
        },
        {
            "description": "Заработная плата",
            "category": "Зарплата",
            "date": "5 июля 2026",
            "amount": "+85 000,00 ₽",
            "type": "income",
        },
        {
            "description": "Домашний интернет",
            "category": "Связь",
            "date": "3 июля 2026",
            "amount": "−750,00 ₽",
            "type": "expense",
        },
    ]

    return render_template(
        "dashboard/index.html",
        balance="79 400,00 ₽",
        income="85 000,00 ₽",
        expenses="5 600,00 ₽",
        savings="79 400,00 ₽",
        current_month="Июль 2026",
        recent_transactions=recent_transactions,
    )
