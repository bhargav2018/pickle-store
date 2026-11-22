from django.contrib import admin, messages
from django.core.mail import send_mail

from .models import Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock")
    list_filter = ("category",)
    search_fields = ("name",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer_name",
        "total_amount",
        "payment_method",
        "status",
        "created_at",
    )

    list_filter = ("payment_method", "status")
    search_fields = ("customer_name", "email", "mobile")
    list_editable = ("status",)
    readonly_fields = ("created_at",)

    inlines = [OrderItemInline]

    def save_model(self, request, obj, form, change):
        old_status = None

        if change:
            old_order = Order.objects.get(pk=obj.pk)
            old_status = old_order.status

        super().save_model(request, obj, form, change)

        if change and old_status != obj.status:
            self.send_status_email(request, obj)

    def send_status_email(self, request, order):

        status_messages = {
            Order.Status.PENDING: (
                "We have received your order!",
                "Your order has been successfully received. "
                "We will keep you updated.",
            ),
            Order.Status.PROCESSING: (
                "Your delicious order is being prepared!",
                "Our team is preparing your order with care.",
            ),
            Order.Status.SHIPPED: (
                "Good news! Your order is on its way!",
                "Your order has been dispatched. "
                "We hope you receive it soon!",
            ),
            Order.Status.DELIVERED: (
                "Your order has been delivered!",
                "We hope you enjoy your delicious products. "
                "Thank you for shopping with us!",
            ),
            Order.Status.CANCELLED: (
                "We regret to inform you that your order has been cancelled.",
                "Your order has been cancelled. "
                "Please contact us if you have any questions.",
            ),
        }

        heading, description = status_messages.get(
            order.status,
            ("Your order status has been updated.", "Please check your order details."),
        )

        order_items = order.items.select_related("product").all()

        product_details = "\n".join(
            f"- {item.product.name} x {item.quantity} "
            f"(Rs. {item.line_total:.2f})"
            for item in order_items
        )

        email_message = f"""
Hello {order.customer_name},

{heading}

{description}

--------------------------------
ORDER DETAILS
--------------------------------

Order Reference: #{order.id}
Order Date: {order.created_at.strftime("%d %B %Y")}
Payment Method: {order.payment_method}
Order Status: {order.get_status_display()}

ORDERED PRODUCTS:

{product_details}

Total Amount: Rs. {order.total_amount:.2f}

--------------------------------

Thank you for choosing Homemade Pickles & Snacks!

We appreciate your support and look forward to serving you again.

Warm regards,
Homemade Pickles & Snacks Team
"""

        try:
            send_mail(
                subject=f"{heading} - Order #{order.id}",
                message=email_message,
                from_email=None,
                recipient_list=[order.email],
                fail_silently=False,
            )

            self.message_user(
                request,
                f"Status updated and notification sent to {order.email}.",
                messages.SUCCESS,
            )

        except Exception as e:
            print("STATUS EMAIL ERROR:", repr(e))

            self.message_user(
                request,
                "Order status updated, but the email could not be sent.",
                messages.WARNING,
            )
