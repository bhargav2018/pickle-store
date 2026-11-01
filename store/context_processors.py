from . import cart


def cart_count(request):
    """Make the cart's unit count available to every template."""
    return {"cart_count": cart.count(request.session)}
