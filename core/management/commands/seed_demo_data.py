from decimal import Decimal

from django.core.management.base import BaseCommand

from core.management.commands.seed_categories import DEFAULT_CATEGORIES
from core.models import Car, Expense, ExpenseCategory


DEMO_ORDERS = [
    {
        "title": "Audi Q3 кузовной ремонт",
        "brand": "Audi",
        "model": "Q3",
        "description": "Дефектовка: нужен капот, крыло правое, фара правая, бампер в сборе.",
        "repair_stage": Car.RepairStage.DEFECT,
        "defect_comment": "Список запчастей: капот, крыло правое, фара правая, бампер в сборе.",
        "expenses": [
            ("Детали", "Капот", "300", "USD", "Купленная запчасть"),
            ("Детали", "Крыло правое", "150", "USD", "Купленная запчасть"),
            ("Детали", "Фара правая", "500", "USD", "Купленная запчасть"),
            ("Детали", "Бампер в сборе", "2000", "USD", "Купленная запчасть"),
            ("Работа", "Вытяжка лонжерона, установка запчастей, выставление зазоров", "0", "BYN", "Кузовные работы, сумму поставить вручную"),
            ("Работа", "Подготовка/покраска капота, крыла и бампера", "0", "BYN", "Покрасочные работы, сумму поставить вручную"),
            ("Сторонние услуги", "Развал", "90", "BYN", "Типовая сторонняя услуга"),
        ],
    },
    {
        "title": "Ford Mustang ТО",
        "brand": "Ford",
        "model": "Mustang",
        "description": "Замена масла и технических жидкостей, рычаг, кондиционер, шиномонтаж.",
        "repair_stage": Car.RepairStage.ACCEPTED,
        "expenses": [
            ("Детали", "Масло", "150", "BYN", "Запчасти/расходники"),
            ("Детали", "Фильтр", "70", "BYN", "Запчасти/расходники"),
            ("Детали", "Рычаг передний правый", "340", "BYN", "Запчасти"),
            ("Работа", "Замена масла, фильтра, рычага переднего правого", "200", "BYN", "Работы"),
            ("Сторонние услуги", "Заправить кондиционер", "90", "BYN", "Сторонние услуги"),
            ("Сторонние услуги", "Шиномонтаж", "150", "BYN", "Сторонние услуги"),
        ],
    },
    {
        "title": "Chevrolet Corvette полировка",
        "brand": "Chevrolet",
        "model": "Corvette",
        "description": "Частичная/полная полировка кузова.",
        "repair_stage": Car.RepairStage.PAINT_ASSEMBLY,
        "expenses": [("Работа", "Полировка кузова", "300", "BYN", "Частичная/полная полировка")],
    },
    {
        "title": "Mercedes E250 регулировка крышки багажника",
        "brand": "Mercedes",
        "model": "E250",
        "description": "Регулировка крышки багажника.",
        "repair_stage": Car.RepairStage.BODY_WORK,
        "expenses": [("Работа", "Регулировка крышки багажника", "200", "BYN", "Работа")],
    },
    {
        "title": "GMC Terrain покраска",
        "brand": "GMC",
        "model": "Terrain",
        "description": "Покраска бампера, крыльев и капота.",
        "repair_stage": Car.RepairStage.PAINT_ASSEMBLY,
        "expenses": [
            ("Работа", "Покраска бампера переднего", "650", "BYN", "Покрасочные работы"),
            ("Работа", "Покраска крыла переднего левого", "450", "BYN", "Покрасочные работы"),
            ("Работа", "Покраска крыла переднего правого", "450", "BYN", "Покрасочные работы"),
            ("Работа", "Покраска капота с 2 сторон", "900", "BYN", "Покрасочные работы"),
        ],
    },
]

TYPICAL_EXPENSES = [
    ("Работа", "Покраска бампера", "650", "BYN"),
    ("Детали", "Дверь", "500", "USD"),
    ("Детали", "Фара", "2000", "BYN"),
    ("Сторонние услуги", "Развал", "90", "BYN"),
    ("Сторонние услуги", "Шиномонтаж", "100", "BYN"),
    ("Работа", "Ремонт фар", "700", "BYN"),
    ("Сторонние услуги", "Электрик", "350", "USD"),
]


class Command(BaseCommand):
    help = "Create demo orders and expenses from the customer examples."

    def handle(self, *args, **options):
        categories = {}
        ExpenseCategory.objects.exclude(name__in=DEFAULT_CATEGORIES).update(is_active=False)
        for name in DEFAULT_CATEGORIES:
            category, _ = ExpenseCategory.objects.get_or_create(name=name, defaults={"is_active": True})
            if not category.is_active:
                category.is_active = True
                category.save(update_fields=["is_active"])
            categories[name] = category

        created_orders = 0
        created_expenses = 0
        for order in DEMO_ORDERS:
            car, was_created = Car.objects.get_or_create(
                title=order["title"],
                defaults={
                    "brand": order["brand"],
                    "model": order["model"],
                    "description": order["description"],
                    "repair_stage": order["repair_stage"],
                    "status": Car.Status.IN_WORK,
                },
            )
            created_orders += int(was_created)
            for category_name, description, amount, currency, comment in order["expenses"]:
                if Decimal(amount) <= 0:
                    continue
                _, was_expense_created = Expense.objects.get_or_create(
                    car=car,
                    category=categories[category_name],
                    description=description,
                    amount=Decimal(amount),
                    currency=currency,
                    defaults={"comment": comment},
                )
                created_expenses += int(was_expense_created)

        typical_car, _ = Car.objects.get_or_create(
            title="Типовые расходы для тестирования",
            defaults={
                "brand": "Demo",
                "model": "Expenses",
                "description": "Заказ-контейнер для проверки типовых расходов из ТЗ.",
                "repair_stage": Car.RepairStage.ACCEPTED,
                "status": Car.Status.IN_WORK,
            },
        )
        for category_name, description, amount, currency in TYPICAL_EXPENSES:
            _, was_created = Expense.objects.get_or_create(
                car=typical_car,
                category=categories[category_name],
                description=description,
                amount=Decimal(amount),
                currency=currency,
                defaults={"comment": "Типовой расход для тестирования"},
            )
            created_expenses += int(was_created)

        self.stdout.write(self.style.SUCCESS(f"Demo data ready. Orders created: {created_orders}. Expenses created: {created_expenses}."))
