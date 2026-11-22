from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Order, OrderItem, Product

User = get_user_model()
STRONG_PASSWORD = "Str0ng-Pickle-Pass-42"

CHECKOUT_DATA = {
    "name": "Asha Rao",
    "email": "asha@example.com",
    "mobile": "9876543210",
    "address": "12 MG Road, Guntur, 522001",
    "payment_method": "Cash on Delivery",
}


class StoreTestCase(TestCase):
    """Shared fixtures: two products and one registered user."""

    def setUp(self):
        self.mango = Product.objects.create(
            name="Mango Pickle", price="150.00", category="pickle", stock=10
        )
        self.chips = Product.objects.create(
            name="Banana Chips", price="70.00", category="snack", stock=5
        )
        self.user = User.objects.create_user("asha", "asha@example.com", STRONG_PASSWORD)

    def login(self):
        self.client.login(username="asha", password=STRONG_PASSWORD)

    def cart_lines(self):
        return self.client.get(reverse("cart")).context["cart"]

    def fill_cart(self):
        """Put 2 x mango and 1 x chips in the cart through the real views."""
        self.client.post(reverse("add_to_cart", args=[self.mango.id]))
        self.client.post(reverse("add_to_cart", args=[self.mango.id]))
        self.client.post(reverse("add_to_cart", args=[self.chips.id]))


class SignUpTests(StoreTestCase):
    def signup(self, **overrides):
        data = {"username": "newuser", "email": "new@example.com", "password": STRONG_PASSWORD}
        data.update(overrides)
        return self.client.post(reverse("signup"), data)

    def test_signup_creates_user_with_hashed_password(self):
        response = self.signup()
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="newuser")
        self.assertNotEqual(user.password, STRONG_PASSWORD)
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password(STRONG_PASSWORD))

    def test_weak_password_is_rejected(self):
        self.signup(password="12345678")
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_duplicate_username_is_rejected(self):
        self.signup(username="ASHA")  # differs only by case
        self.assertEqual(User.objects.filter(username__iexact="asha").count(), 1)

    def test_duplicate_email_is_rejected(self):
        self.signup(email="asha@example.com")
        self.assertFalse(User.objects.filter(username="newuser").exists())


class LoginTests(StoreTestCase):
    def test_login_success_redirects_to_products(self):
        response = self.client.post(
            reverse("login"), {"username": "asha", "password": STRONG_PASSWORD}
        )
        self.assertRedirects(response, reverse("products"))

    def test_login_wrong_password_shows_error(self):
        response = self.client.post(reverse("login"), {"username": "asha", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid credentials!")

    def test_login_follows_safe_next_url(self):
        response = self.client.post(
            reverse("login") + "?next=/cart",
            {"username": "asha", "password": STRONG_PASSWORD},
        )
        self.assertRedirects(response, "/cart", fetch_redirect_response=False)

    def test_login_ignores_external_next_url(self):
        response = self.client.post(
            reverse("login") + "?next=https://evil.example/",
            {"username": "asha", "password": STRONG_PASSWORD},
        )
        self.assertRedirects(response, reverse("products"))

    def test_logout_requires_post(self):
        self.login()
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))
        self.assertRedirects(
            self.client.get(reverse("products")),
            reverse("login") + "?next=/products/",
        )


class ProductTests(StoreTestCase):
    def test_products_requires_login(self):
        response = self.client.get(reverse("products"))
        self.assertRedirects(response, reverse("login") + "?next=/products/")

    def test_products_lists_catalogue(self):
        self.login()
        response = self.client.get(reverse("products"))
        self.assertContains(response, "Mango Pickle")
        self.assertContains(response, "Banana Chips")

    def test_seed_command_is_idempotent(self):
        Product.objects.all().delete()
        call_command("seed_products", verbosity=0)
        call_command("seed_products", verbosity=0)
        self.assertEqual(Product.objects.count(), 8)


class CartTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_add_to_cart_requires_post(self):
        response = self.client.get(reverse("add_to_cart", args=[self.mango.id]))
        self.assertEqual(response.status_code, 405)

    def test_adding_same_product_twice_increases_quantity(self):
        self.fill_cart()
        response = self.client.get(reverse("cart"))
        lines = response.context["cart"]
        quantities = {line["name"]: line["quantity"] for line in lines}
        self.assertEqual(quantities, {"Mango Pickle": 2, "Banana Chips": 1})
        self.assertEqual(response.context["total"], Decimal("370.00"))

    def test_unknown_product_is_not_added(self):
        self.client.post(reverse("add_to_cart", args=[9999]))
        self.assertEqual(self.client.get(reverse("cart")).context["cart"], [])

    def test_cart_uses_current_database_price(self):
        self.fill_cart()
        self.mango.price = Decimal("200.00")
        self.mango.save()
        total = self.client.get(reverse("cart")).context["total"]
        self.assertEqual(total, Decimal("470.00"))

    def test_remove_from_cart(self):
        self.fill_cart()
        self.client.post(reverse("remove_from_cart", args=[self.mango.id]))
        names = [line["name"] for line in self.client.get(reverse("cart")).context["cart"]]
        self.assertEqual(names, ["Banana Chips"])


class CheckoutTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_empty_cart_cannot_check_out(self):
        self.assertRedirects(self.client.get(reverse("checkout")), reverse("products"))
        self.assertRedirects(
            self.client.post(reverse("place_order"), CHECKOUT_DATA), reverse("products")
        )
        self.assertEqual(Order.objects.count(), 0)

    def test_place_order_saves_order_and_items(self):
        self.fill_cart()
        response = self.client.post(reverse("place_order"), CHECKOUT_DATA)

        order = Order.objects.get()
        self.assertRedirects(response, reverse("order_confirmation", args=[order.id]))
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.total_amount, Decimal("370.00"))
        items = {i.product.name: (i.quantity, i.price) for i in OrderItem.objects.all()}
        self.assertEqual(
            items,
            {"Mango Pickle": (2, Decimal("150.00")), "Banana Chips": (1, Decimal("70.00"))},
        )

    def test_order_keeps_price_paid_after_price_change(self):
        self.fill_cart()
        self.client.post(reverse("place_order"), CHECKOUT_DATA)
        self.mango.price = Decimal("999.00")
        self.mango.save()
        item = OrderItem.objects.get(product=self.mango)
        self.assertEqual(item.price, Decimal("150.00"))

    def test_place_order_clears_cart(self):
        self.fill_cart()
        self.client.post(reverse("place_order"), CHECKOUT_DATA)
        self.assertEqual(self.client.get(reverse("cart")).context["cart"], [])

    def test_invalid_mobile_number_is_rejected(self):
        self.fill_cart()
        bad = dict(CHECKOUT_DATA, mobile="12345")
        response = self.client.post(reverse("place_order"), bad)
        self.assertRedirects(response, reverse("checkout"))
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(len(self.client.get(reverse("cart")).context["cart"]), 2)

    def test_invalid_payment_method_is_rejected(self):
        self.fill_cart()
        bad = dict(CHECKOUT_DATA, payment_method="Bitcoin")
        self.client.post(reverse("place_order"), bad)
        self.assertEqual(Order.objects.count(), 0)


class SeedTests(StoreTestCase):
    def test_new_products_get_starting_stock(self):
        Product.objects.all().delete()
        call_command("seed_products", verbosity=0)
        self.assertEqual(Product.objects.get(name="Mango Pickle").stock, 50)

    def test_reseeding_does_not_reset_stock(self):
        Product.objects.all().delete()
        call_command("seed_products", verbosity=0)
        product = Product.objects.get(name="Mango Pickle")
        product.stock = 3
        product.save()
        call_command("seed_products", verbosity=0)
        product.refresh_from_db()
        self.assertEqual(product.stock, 3)


class CartEdgeCaseTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_deleted_product_disappears_from_cart(self):
        self.fill_cart()
        self.chips.delete()
        response = self.client.get(reverse("cart"))
        self.assertEqual([line["name"] for line in response.context["cart"]], ["Mango Pickle"])
        self.assertEqual(response.context["total"], Decimal("300.00"))

    def test_cart_count_reaches_templates(self):
        self.fill_cart()
        response = self.client.get(reverse("products"))
        self.assertEqual(response.context["cart_count"], 3)

    def test_carts_are_separate_per_session(self):
        self.fill_cart()
        other = self.client_class()
        User.objects.create_user("other", "other@example.com", STRONG_PASSWORD)
        other.login(username="other", password=STRONG_PASSWORD)
        self.assertEqual(other.get(reverse("cart")).context["cart"], [])

    def test_cart_pages_require_login(self):
        self.client.logout()
        urls = [reverse("cart"),reverse("checkout"),]
        for url in urls: 
            response = self.client.get(url)
            self.assertRedirects(response,reverse("login") + "?next=" + url)

class StockTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_out_of_stock_product_cannot_be_added(self):
        self.chips.stock = 0
        self.chips.save()
        self.client.post(reverse("add_to_cart", args=[self.chips.id]))
        self.assertEqual(self.cart_lines(), [])

    def test_cannot_add_more_than_stock(self):
        self.chips.stock = 2
        self.chips.save()
        for _ in range(3):
            self.client.post(reverse("add_to_cart", args=[self.chips.id]))
        self.assertEqual([line["quantity"] for line in self.cart_lines()], [2])

    def test_out_of_stock_label_is_shown(self):
        self.chips.stock = 0
        self.chips.save()
        self.assertContains(self.client.get(reverse("products")), "Out of stock")

    def test_checkout_reduces_stock(self):
        self.fill_cart()
        self.client.post(reverse("place_order"), CHECKOUT_DATA)
        self.mango.refresh_from_db()
        self.chips.refresh_from_db()
        self.assertEqual((self.mango.stock, self.chips.stock), (8, 4))

    def test_checkout_fails_if_stock_dropped_after_adding(self):
        self.fill_cart()
        self.mango.stock = 1
        self.mango.save()

        response = self.client.post(reverse("place_order"), CHECKOUT_DATA)

        self.assertRedirects(response, reverse("cart"))
        self.assertEqual(Order.objects.count(), 0)
        self.mango.refresh_from_db()
        self.chips.refresh_from_db()
        self.assertEqual((self.mango.stock, self.chips.stock), (1, 5))
        self.assertEqual(len(self.cart_lines()), 2)


class UpdateCartTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.fill_cart()
        self.url = reverse("update_cart", args=[self.mango.id])

    def quantities(self):
        return {line["name"]: line["quantity"] for line in self.cart_lines()}

    def test_requires_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_sets_exact_quantity(self):
        self.client.post(self.url, {"quantity": 7})
        self.assertEqual(self.quantities(), {"Mango Pickle": 7, "Banana Chips": 1})

    def test_zero_removes_item(self):
        self.client.post(self.url, {"quantity": 0})
        self.assertEqual(self.quantities(), {"Banana Chips": 1})

    def test_quantity_is_capped_at_stock(self):
        self.client.post(self.url, {"quantity": 99})
        self.assertEqual(self.quantities()["Mango Pickle"], 10)

    def test_invalid_quantity_leaves_cart_unchanged(self):
        for bad in ("abc", "-3", "", "2.5"):
            self.client.post(self.url, {"quantity": bad})
        self.assertEqual(self.quantities(), {"Mango Pickle": 2, "Banana Chips": 1})

    def test_updating_a_deleted_product_removes_it(self):
        url = reverse("update_cart", args=[self.chips.id])
        self.chips.delete()
        self.client.post(url, {"quantity": 2})
        self.assertEqual(self.quantities(), {"Mango Pickle": 2})


class SearchAndFilterTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def names(self, **params):
        response = self.client.get(reverse("products"), params)
        return [product.name for product in response.context["products"]]

    def test_search_by_name_is_case_insensitive(self):
        self.assertEqual(self.names(q="MANGO"), ["Mango Pickle"])

    def test_filter_by_category(self):
        self.assertEqual(self.names(category="snack"), ["Banana Chips"])

    def test_search_and_category_combine(self):
        self.assertEqual(self.names(q="mango", category="snack"), [])

    def test_no_matches_shows_message(self):
        response = self.client.get(reverse("products"), {"q": "zzz"})
        self.assertContains(response, "No products found")

    def test_add_to_cart_returns_to_filtered_list(self):
        response = self.client.post(
            reverse("add_to_cart", args=[self.mango.id]), {"next": "/products?q=mango"}
        )
        self.assertRedirects(response, "/products?q=mango", fetch_redirect_response=False)

    def test_add_to_cart_ignores_external_next_url(self):
        response = self.client.post(
            reverse("add_to_cart", args=[self.mango.id]), {"next": "https://evil.example/"}
        )
        self.assertRedirects(response, reverse("products"))


class OrderHistoryTests(StoreTestCase):
    def test_requires_login(self):
        self.assertRedirects(
            self.client.get(reverse("orders")), reverse("login") + "?next=/orders/"
        )

    def test_empty_history_message(self):
        self.login()
        self.assertContains(self.client.get(reverse("orders")), "any orders yet")

    def test_lists_own_orders_with_items(self):
        self.login()
        self.fill_cart()
        self.client.post(reverse("place_order"), CHECKOUT_DATA)
        order = Order.objects.get()
        response = self.client.get(reverse("orders"))
        self.assertContains(response, f"Order #{order.id}")
        self.assertContains(response, "Mango Pickle")
        self.assertContains(response, "Banana Chips")

    def test_does_not_show_other_customers_orders(self):
        self.login()
        self.fill_cart()
        self.client.post(reverse("place_order"), CHECKOUT_DATA)
        self.client.post(reverse("logout"))

        User.objects.create_user("other", "other@example.com", STRONG_PASSWORD)
        self.client.login(username="other", password=STRONG_PASSWORD)
        response = self.client.get(reverse("orders"))
        self.assertNotContains(response, "Mango Pickle")
        self.assertContains(response, "any orders yet")
