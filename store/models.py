import decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(decimal.Decimal("0.01"))],
    )
    image = models.ImageField(upload_to="products/",blank=True,null=True,)
    category = models.CharField(max_length=50, blank=True, db_index=True)
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock > 0


class Order(models.Model):

    class PaymentMethod(models.TextChoices):
        COD = "Cash on Delivery", "Cash on Delivery"
        UPI = "UPI", "UPI"
        CARD = "Debit/Credit Card", "Debit/Credit Card"
        NET_BANKING = "Net Banking", "Net Banking"

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        PROCESSING = "Processing", "Processing"
        SHIPPED = "Shipped", "Shipped"
        DELIVERED = "Delivered", "Delivered"
        CANCELLED = "Cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    customer_name = models.CharField(max_length=120)
    email = models.EmailField()
    address = models.TextField()
    mobile = models.CharField(max_length=15)

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} by {self.customer_name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="order_items"
    )
    quantity = models.PositiveIntegerField()
    # Price at the time of purchase, so later price changes don't alter old orders.
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product}"

    @property
    def line_total(self):
        return self.price * self.quantity
