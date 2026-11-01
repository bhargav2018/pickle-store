from django.db import migrations, models


def give_existing_products_stock(apps, schema_editor):
    """Products created before stock tracking existed start with 50 units."""
    Product = apps.get_model("store", "Product")
    Product.objects.update(stock=50)


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="stock",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(give_existing_products_stock, migrations.RunPython.noop),
    ]
