from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from . import cart as cart_service
from .forms import CheckoutForm, QuantityForm, SignUpForm
from .models import Order, OrderItem, Product

User = get_user_model()


def _flash_form_errors(request, form):
    for error_list in form.errors.values():
        for error in error_list:
            messages.error(request, error)


def _redirect_back(request, fallback):
    """Redirect to the (same-site) ``next`` value from a POST, else ``fallback``.

    Lets "Add to cart" return the shopper to the filtered product list they
    were on instead of dumping them back at the unfiltered catalogue.
    """
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(fallback)


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "store/index.html")


def ping(request: HttpRequest) -> HttpResponse:
    return HttpResponse("Backend is live")


def auth(request: HttpRequest) -> HttpResponse:
    return render(request, "store/auth.html")


def signup(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            messages.success(request, "Account created successfully! Please log in.")
            return redirect("login")
        _flash_form_errors(request, form)

    return render(request, "store/signup.html")


def login(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user is not None:
            auth_login(request, user)
            next_url = request.GET.get("next", "")
            if url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("products")

        messages.error(request, "Invalid credentials!")

    return render(request, "store/login.html")


@login_required
def products(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()

    items = Product.objects.all()
    if query:
        items = items.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category:
        items = items.filter(category=category)

    categories = (
        Product.objects.exclude(category="")
        .order_by("category")
        .values_list("category", flat=True)
        .distinct()
    )
    context = {
        "products": items,
        "categories": categories,
        "query": query,
        "selected_category": category,
        "filtering": bool(query or category),
    }
    return render(request, "store/products.html", context)


@login_required
@require_POST
def add_to_cart(request: HttpRequest, product_id: int) -> HttpResponse:
    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        messages.error(request, "Product not found.")
        return redirect("products")

    if not product.in_stock:
        messages.error(request, f"Sorry, {product.name} is out of stock.")
    elif cart_service.add(request.session, product):
        messages.success(request, "Item added to cart!")
    else:
        messages.error(
            request, f"Only {product.stock} of {product.name} available; your cart has them all."
        )
    return _redirect_back(request, "products")


@login_required
def cart(request: HttpRequest) -> HttpResponse:
    lines, total = cart_service.get_lines(request.session)
    return render(request, "store/cart.html", {"cart": lines, "total": total})


@login_required
@require_POST
def remove_from_cart(request: HttpRequest, product_id: int) -> HttpResponse:
    cart_service.remove(request.session, product_id)
    messages.success(request, "Item removed from cart.")
    return redirect("cart")


@login_required
@require_POST
def update_cart(request: HttpRequest, product_id: int) -> HttpResponse:
    product = Product.objects.filter(pk=product_id).first()
    form = QuantityForm(request.POST)
    if product is None:
        cart_service.remove(request.session, product_id)
        messages.error(request, "That product is no longer available.")
    elif not form.is_valid():
        messages.error(request, "Enter a valid quantity.")
    else:
        requested = form.cleaned_data["quantity"]
        stored = cart_service.set_quantity(request.session, product, requested)
        if stored == 0:
            messages.success(request, "Item removed from cart.")
        elif stored < requested:
            messages.error(
                request, f"Only {product.stock} of {product.name} available; quantity adjusted."
            )
        else:
            messages.success(request, "Cart updated.")
    return redirect("cart")


@login_required
def checkout(request: HttpRequest) -> HttpResponse:
    lines, total = cart_service.get_lines(request.session)
    if not lines:
        messages.error(request, "Your cart is empty!")
        return redirect("products")

    return render(request, "store/checkout.html", {"cart": lines, "total": total})



@login_required
@require_POST
def place_order(request: HttpRequest) -> HttpResponse:
    lines, _ = cart_service.get_lines(request.session)
    if not lines:
        messages.error(request, "Your cart is empty!")
        return redirect("products")
    form = CheckoutForm(request.POST)
    if not form.is_valid():
        _flash_form_errors(request, form)
        return redirect("checkout")
    data = form.cleaned_data
    shortages = []
    with transaction.atomic():
        # Lock product rows to prevent simultaneous checkouts
        # from purchasing the same remaining stock.
        locked = Product.objects.select_for_update().in_bulk(
            [line["product_id"] for line in lines])
        purchases = []
        for line in lines:
            product = locked.get(line["product_id"])
            if product is None or product.stock < line["quantity"]:
                shortages.append(line["name"])
            else:
                purchases.append((product, line["quantity"]))
        if not shortages:
            order = Order.objects.create(
                user=request.user,
                customer_name=data["name"],
                email=data["email"],
                address=data["address"],
                mobile=data["mobile"],
                payment_method=data["payment_method"],
                total_amount=sum(
                    product.price * quantity
                    for product, quantity in purchases
                ),
            )
            OrderItem.objects.bulk_create([OrderItem(order=order,product=product,quantity=quantity,price=product.price,)
                    for product, quantity in purchases]
            )
            # Reduce stock after successful order creation.
            for product, quantity in purchases:
                product.stock -= quantity
                product.save(update_fields=["stock"])
    if shortages:
        messages.error(
            request,
            "Not enough stock for: "
            + ", ".join(shortages)
            + ". Please adjust your cart.",
        )
        return redirect("cart")
    # Clear the cart after successful order placement.
    cart_service.clear(request.session)
    # Prepare the confirmation email.
    order_items = order.items.select_related("product").all()
    email_message = f"""
Hello {order.customer_name},

Thank you for shopping with Homemade Pickles & Snacks!

Your order has been placed successfully.

Order ID: #{order.id}
Ordered Products:
"""
    for item in order_items:
        email_message += (
            f"\n{item.product.name} x {item.quantity}"
            f" - Rs. {item.price * item.quantity}"
        )

    email_message += f"""

Total Amount: Rs. {order.total_amount}
Payment Method: {order.payment_method}

Delivery Address:
{order.address}

Thank you for shopping with us!

Homemade Pickles & Snacks
"""
    # Send the email to the customer's checkout email address.
    try:
        send_mail(
            subject="Order Confirmation",
            message=email_message,
            from_email=None,
            recipient_list=[order.email],
            fail_silently=False,
        )
        messages.success(
            request,
            "Your order confirmation email has been sent!",
        )
    except Exception as e:
        print("EMAIL ERROR:", repr(e))
        messages.warning(
            request,
            "Your order was placed successfully, "
            "but the confirmation email could not be sent.",
        )
    return redirect("order_confirmation", order_id=order.id)

@login_required
def order_confirmation(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request,"store/order_confirmation.html",
        {"order_id": order.id, "customer_name": order.customer_name},
    )


@login_required
def orders(request: HttpRequest) -> HttpResponse:
    user_orders = request.user.orders.prefetch_related("items__product")
    return render(request, "store/orders.html", {"orders": user_orders})


@require_POST
def logout(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return redirect("home")
