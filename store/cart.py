"""Session-backed shopping cart.

The session stores only ``{product_id: quantity}``. Names and prices are always
looked up from the database, so a cart can never carry a stale or tampered price.
Quantities are capped at the product's stock level.
"""
from .models import Product

SESSION_KEY = "cart"


def _items(session):
    return session.get(SESSION_KEY, {})


def quantity_of(session, product_id):
    return _items(session).get(str(product_id), 0)


def add(session, product):
    """Add one unit of ``product``.

    Returns False (and leaves the cart unchanged) when the cart already holds
    every unit in stock.
    """
    current = quantity_of(session, product.id)
    if current + 1 > product.stock:
        return False
    items = dict(_items(session))
    items[str(product.id)] = current + 1
    session[SESSION_KEY] = items
    return True


def set_quantity(session, product, quantity):
    """Set the exact quantity of ``product``; 0 (or less) removes it.

    The quantity is capped at the available stock. Returns the quantity that
    was actually stored so the caller can tell the customer if it was reduced.
    """
    quantity = max(0, min(int(quantity), product.stock))
    items = dict(_items(session))
    if quantity == 0:
        items.pop(str(product.id), None)
    else:
        items[str(product.id)] = quantity
    session[SESSION_KEY] = items
    return quantity


def remove(session, product_id):
    items = dict(_items(session))
    items.pop(str(product_id), None)
    session[SESSION_KEY] = items


def clear(session):
    session.pop(SESSION_KEY, None)


def count(session):
    """Total number of units in the cart."""
    return sum(_items(session).values())


def get_lines(session):
    """Return ``(lines, total)`` with current prices from the database."""
    items = _items(session)
    products = Product.objects.in_bulk([int(pid) for pid in items])

    lines = []
    for pid, quantity in items.items():
        product = products.get(int(pid))
        if product is None:  # product was deleted after being added
            continue
        lines.append(
            {
                "product_id": product.id,
                "name": product.name,
                "price": product.price,
                "image_url": product.image.url if product.image else "",
                "quantity": quantity,
                "stock": product.stock,
                "line_total": product.price * quantity,
            }
        )
    total = sum(line["line_total"] for line in lines)
    return lines, total
