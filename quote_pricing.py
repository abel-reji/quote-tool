"""Canonical pricing for customer lines and their private package components."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
LIMIT = Decimal("1000000000")


def number(value, label, default=0):
    try:
        if isinstance(value, bool):
            raise ValueError
        result = Decimal(str(default if value in (None, "") else value))
        if not result.is_finite() or abs(result) > LIMIT:
            raise ValueError
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{label} must be a finite number no greater than {LIMIT}.") from None


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_item(item, *, component=False):
    if not isinstance(item, dict):
        raise ValueError("Each item must be an object.")
    kind = item.get("item_type", "single")
    if not isinstance(kind, str) or kind not in {"single", "package"} or (component and kind != "single"):
        raise ValueError("Nested packages and unknown item types are not supported.")
    name = str(item.get("item_name", "")).strip()
    if not name:
        raise ValueError("Item name is required.")
    quantity = number(item.get("quantity"), "Quantity", 1)
    if quantity <= 0 or quantity != quantity.to_integral_value() or quantity > 1000000:
        raise ValueError("Quantity must be a whole number from 1 to 1000000.")
    children = item.get("components", [])
    if not isinstance(children, list):
        raise ValueError("Package components must be a list.")
    if kind == "package":
        if not 1 <= len(children) <= 100:
            raise ValueError("A package must contain between 1 and 100 components.")
        children = [calculate_item(child, component=True) for child in children]
        # Component quantities are per package; outer quantity multiplies the package.
        cost = sum((Decimal(str(c["net_cost_each"])) * c["quantity"] for c in children), Decimal(0))
        sell = sum((Decimal(str(c["line_total"])) for c in children), Decimal(0))
    else:
        if children:
            raise ValueError("Only a package may contain components.")
        cost = money(number(item.get("net_cost_each"), "Net cost"))
        sell = money(number(item.get("sell_price_each"), "Sell price"))
        margin = number(item.get("gross_margin_percent"), "Margin")
        if cost < 0 or sell < 0:
            raise ValueError("Costs and prices cannot be negative.")
        if sell == 0 and margin > 0:
            if margin >= 100:
                raise ValueError("Gross margin percent must be less than 100.")
            sell = money(cost / (1 - margin / 100))
    if not component and sell <= 0:
        raise ValueError("Sell price must be greater than zero.")
    total = money(sell * quantity)
    if max(cost, sell, total, cost * quantity) > LIMIT:
        raise ValueError("Item amount is too large.")
    margin = money((sell - cost) / sell * 100) if sell else Decimal(0)
    return {
        "item_type": kind, "components": children,
        "item_name": name,
        "item_description": str(item.get("item_description", "")).strip(),
        "item_long_description": str(item.get("item_long_description", "")).strip(),
        "lead_time": str(item.get("lead_time", "")).strip(),
        "quantity": int(quantity), "net_cost_each": float(cost),
        "sell_price_each": float(sell), "gross_margin_percent": float(margin),
        "line_total": float(total),
    }
