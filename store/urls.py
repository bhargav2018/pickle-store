from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("ping/", views.ping, name="ping"),
    path("auth/", views.auth, name="auth"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("products/", views.products, name="products"),
    path("add_to_cart/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/", views.cart, name="cart"),
    path(
        "remove_from_cart/<int:product_id>/",
        views.remove_from_cart,
        name="remove_from_cart",
    ),
    path(
        "update_cart/<int:product_id>/",
        views.update_cart,
        name="update_cart",
    ),
    path("checkout/", views.checkout, name="checkout"),
    path("place_order/", views.place_order, name="place_order"),
    path(
        "order/<int:order_id>/confirmation/",
        views.order_confirmation,
        name="order_confirmation",
    ),
    path("orders/", views.orders, name="orders"),
    path("logout/", views.logout, name="logout"),
]
