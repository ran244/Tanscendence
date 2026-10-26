from django.db import migrations


DEFAULT_CATEGORIES = (
    ("Antiquities", "Historic objects and archaeological collectibles."),
    ("Books & Manuscripts", "Rare books, documents, maps, and manuscripts."),
    ("Coins", "Coins, medals, banknotes, and numismatic items."),
    ("Jewellery", "Fine, vintage, and collectible jewellery."),
    ("Paintings", "Paintings, drawings, prints, and other visual art."),
    ("Toys & Games", "Vintage toys, models, games, and related collectibles."),
    ("Other", "Auction items that do not fit another category."),
)


def seed_default_categories(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    for name, description in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(name=name, defaults={"description": description})


class Migration(migrations.Migration):
    dependencies = [("products", "0004_alter_product_options_category_description_and_more")]

    operations = [migrations.RunPython(seed_default_categories, migrations.RunPython.noop)]
