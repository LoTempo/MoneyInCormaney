import re
from decimal import Decimal, InvalidOperation


CURRENCY_SYMBOLS = {
    "RUB": "₽",
    "USD": "$",
    "EUR": "€",
}


def format_money(amount, currency="RUB", transaction_type=None):
    value = Decimal(amount or 0)
    value_is_negative = value < 0
    if value_is_negative:
        value = abs(value)
    formatted = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    symbol = CURRENCY_SYMBOLS.get(currency, currency)

    if transaction_type in {"income", "savings_deposit", "deposit"}:
        prefix = "+"
    elif transaction_type in {"expense", "savings_withdrawal", "withdrawal"}:
        prefix = "−"
    elif value_is_negative:
        prefix = "−"
    else:
        prefix = ""

    return f"{prefix}{formatted} {symbol}"


def parse_positive_amount(raw_value):
    try:
        amount = Decimal((raw_value or "").replace(",", "."))
    except InvalidOperation:
        return None

    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        return None

    return amount


def parse_nonnegative_amount(raw_value):
    try:
        amount = Decimal((raw_value or "").replace(",", "."))
    except InvalidOperation:
        return None

    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        return None

    return amount


def transaction_type_label(transaction_type):
    return {
        "income": "Доход",
        "expense": "Расход",
    }.get(transaction_type, transaction_type)


def valid_phone(phone):
    value = (phone or "").strip()
    if value in {"", "+7"}:
        return True
    return re.fullmatch(r"\+7 \d{3} \d{3}-\d{2}-\d{2}", value) is not None


def normalize_phone(phone):
    """Return one storage format for a valid Russian phone number."""

    value = (phone or "").strip()
    if value in {"", "+7"}:
        return None

    digits = re.sub(r"\D", "", value)[1:]
    return f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
