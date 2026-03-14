"""
Fake category ma'lumotlarini yaratish uchun management command.
Ishlatish: python manage.py create_fake_categories [--count N] [--clear]
"""
from django.core.management.base import BaseCommand
from apps.categories.models import Category


# Root va child kategoriyalar uchun fake ma'lumotlar (uz, ru, en)
FAKE_ROOT_CATEGORIES = [
    {
        "translations": {
            "uz": {"name": "Elektronika"},
            "ru": {"name": "Электроника"},
            "en": {"name": "Electronics"},
        },
        "order": 0,
        "children": [
            {"uz": {"name": "Smartfonlar"}, "ru": {"name": "Смартфоны"}, "en": {"name": "Smartphones"}},
            {"uz": {"name": "Noutbuklar"}, "ru": {"name": "Ноутбуки"}, "en": {"name": "Laptops"}},
            {"uz": {"name": "Televizorlar"}, "ru": {"name": "Телевизоры"}, "en": {"name": "TVs"}},
        ],
    },
    {
        "translations": {
            "uz": {"name": "Kiyim-kechak"},
            "ru": {"name": "Одежда"},
            "en": {"name": "Clothing"},
        },
        "order": 1,
        "children": [
            {"uz": {"name": "Erkaklar kiyimi"}, "ru": {"name": "Мужская одежда"}, "en": {"name": "Men's clothing"}},
            {"uz": {"name": "Ayollar kiyimi"}, "ru": {"name": "Женская одежда"}, "en": {"name": "Women's clothing"}},
        ],
    },
    {
        "translations": {
            "uz": {"name": "Maishiy texnika"},
            "ru": {"name": "Бытовая техника"},
            "en": {"name": "Home appliances"},
        },
        "order": 2,
        "children": [
            {"uz": {"name": "Muzlatgichlar"}, "ru": {"name": "Холодильники"}, "en": {"name": "Refrigerators"}},
            {"uz": {"name": "Kir yuvish mashinalari"}, "ru": {"name": "Стиральные машины"}, "en": {"name": "Washing machines"}},
        ],
    },
    {
        "translations": {
            "uz": {"name": "Sport"},
            "ru": {"name": "Спорт"},
            "en": {"name": "Sports"},
        },
        "order": 3,
        "children": [
            {"uz": {"name": "Futbol"}, "ru": {"name": "Футбол"}, "en": {"name": "Football"}},
            {"uz": {"name": "Gimnastika"}, "ru": {"name": "Гимнастика"}, "en": {"name": "Gymnastics"}},
        ],
    },
]


class Command(BaseCommand):
    help = "Fake category ma'lumotlarini yaratish (uz, ru, en tillarida)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=0,
            help="Yaratish kerak bo'lgan root kategoriyalar soni (0 = hammasi)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Mavjud barcha kategoriyalarni o'chirish",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count = Category.objects.count()
            Category.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"{count} ta kategoriya o'chirildi."))
            return

        count_limit = options["count"]
        data = FAKE_ROOT_CATEGORIES[:count_limit] if count_limit > 0 else FAKE_ROOT_CATEGORIES

        created_total = 0

        for item in data:
            root = Category.objects.create(
                is_active=True,
                order=item["order"],
            )
            for lang, tr in item["translations"].items():
                root.create_translation(lang, name=tr["name"])
            created_total += 1

            for i, child_tr in enumerate(item.get("children", [])):
                child = Category.objects.create(
                    parent=root,
                    is_active=True,
                    order=i,
                )
                for lang, tr in child_tr.items():
                    child.create_translation(lang, name=tr["name"])
                created_total += 1

        self.stdout.write(self.style.SUCCESS(f"{created_total} ta kategoriya yaratildi."))
