from django.core.management.base import BaseCommand

from store.models import Product

PRODUCTS = [
    ("Mango Pickle", "Spicy and tangy mango pickle made with traditional spices", "150.00", "pickle"),
    ("Lemon Pickle", "Fresh lemon pickle with authentic Indian spices", "120.00", "pickle"),
    ("Mixed Vegetable Pickle", "Assorted vegetables in aromatic pickle masala", "180.00", "pickle"),
    ("Garlic Pickle", "Strong flavored garlic pickle for garlic lovers", "160.00", "pickle"),
    ("Spicy Mixture", "Crunchy and spicy mixture snack", "80.00", "snack"),
    ("Murukku", "Traditional South Indian spiral snack", "90.00", "snack"),
    ("Banana Chips", "Crispy homemade banana chips", "70.00", "snack"),
    ("Roasted Peanuts", "Salted roasted peanuts", "60.00", "snack"),
]


STARTING_STOCK = 50


class Command(BaseCommand):
    help = "Load the starter product catalogue. Safe to run more than once."

    def handle(self, *args, **options):
        created = 0
        for name, description, price, category in PRODUCTS:
            # Starting stock is only set on creation, so re-running the seed
            # never overwrites stock levels that have changed through sales.
            _, was_created = Product.objects.update_or_create(
                name=name,
                defaults={"description": description, "price": price, "category": category},
                create_defaults={
                    "description": description,
                    "price": price,
                    "category": category,
                    "stock": STARTING_STOCK,
                },
            )
            created += was_created
        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue ready: {created} created, {len(PRODUCTS) - created} already existed."
            )
        )
